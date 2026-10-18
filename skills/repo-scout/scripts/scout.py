#!/usr/bin/env python3
"""
scout.py - Query GitHub for popular, actively-maintained repositories and
rank them by relevance to a given project stack.

Stdlib-only (urllib), no external dependencies, so it runs anywhere Python 3
is available (Claude Code, Codex CLI, Gemini CLI, or a bare terminal).

Usage:
  python3 scout.py --keywords "wordpress" "woocommerce" "booking" \
                    --language php \
                    --min-stars 300 \
                    --active-days 365 \
                    --limit 10

  python3 scout.py --keywords "static site" "astro" \
                    --language typescript \
                    --limit 8 \
                    --format json

Auth (optional but recommended): set GITHUB_TOKEN env var to raise the
GitHub Search API rate limit from 10 req/min (unauthenticated) to 30 req/min.
"""

import argparse
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone


API_URL = "https://api.github.com/search/repositories"


def build_query(keywords, language, min_stars, active_days, topic, exclude):
    parts = []
    for kw in keywords:
        # Multi-word keywords need quoting for the GitHub search query syntax.
        if " " in kw:
            parts.append(f'"{kw}"')
        else:
            parts.append(kw)

    if language:
        parts.append(f"language:{language}")

    if topic:
        parts.append(f"topic:{topic}")

    if min_stars:
        parts.append(f"stars:>={min_stars}")

    if active_days:
        cutoff = datetime.now(timezone.utc) - timedelta(days=active_days)
        parts.append(f"pushed:>={cutoff.strftime('%Y-%m-%d')}")

    for ex in exclude or []:
        parts.append(f"-repo:{ex}")

    return " ".join(parts)


def fetch(query, per_page, token):
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": str(per_page),
    }
    url = f"{API_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "repo-scout-skill")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            remaining = resp.headers.get("X-RateLimit-Remaining")
            return data, remaining
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        print(f"GitHub API error {e.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Network error reaching GitHub API: {e}", file=sys.stderr)
        sys.exit(1)


def score_repo(repo, keywords):
    stars = repo.get("stargazers_count", 0)
    pushed_at = repo.get("pushed_at")
    created_at = repo.get("created_at")

    now = datetime.now(timezone.utc)
    days_since_push = 9999
    if pushed_at:
        pushed_dt = datetime.strptime(pushed_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        days_since_push = (now - pushed_dt).days

    age_days = 1
    if created_at:
        created_dt = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age_days = max((now - created_dt).days, 1)

    # Popularity: log-scaled so mega-repos don't totally drown out smaller,
    # more targeted ones.
    popularity = math.log10(stars + 1)

    # Freshness: 1.0 if pushed today, decaying to 0 over ~2 years.
    freshness = max(0.0, 1 - (days_since_push / 730))

    # Momentum: stars accrued per day since creation, log-scaled. A rough
    # proxy for "trending" since GitHub has no public trending API.
    momentum = math.log10((stars / age_days) * 365 + 1)

    # Relevance: fraction of keywords found in name/description/topics.
    haystack = " ".join([
        repo.get("full_name", ""),
        repo.get("description") or "",
        " ".join(repo.get("topics", [])),
    ]).lower()
    hits = sum(1 for kw in keywords if kw.lower() in haystack)
    relevance = hits / len(keywords) if keywords else 0.5

    score = (
        popularity * 1.0
        + freshness * 2.5
        + momentum * 1.5
        + relevance * 4.0
    )

    return {
        "score": round(score, 2),
        "days_since_push": days_since_push,
        "relevance": round(relevance, 2),
        "popularity": round(popularity, 2),
        "momentum": round(momentum, 2),
    }


def rationale(repo, metrics, keywords):
    bits = []
    if metrics["relevance"] >= 0.5:
        bits.append("matches most of your target keywords")
    elif metrics["relevance"] > 0:
        bits.append("partially matches your target keywords")
    else:
        bits.append("surfaced by stars/topic, not keyword match — verify relevance manually")

    if metrics["days_since_push"] <= 30:
        bits.append("pushed to in the last month (actively maintained)")
    elif metrics["days_since_push"] <= 180:
        bits.append("maintained within the last 6 months")
    else:
        bits.append(f"last push {metrics['days_since_push']} days ago — check if still maintained")

    license_info = repo.get("license")
    if license_info:
        bits.append(f"license: {license_info.get('spdx_id', 'unknown')}")
    else:
        bits.append("no license detected — check before using in production")

    return "; ".join(bits)


def main():
    ap = argparse.ArgumentParser(description="Scout GitHub for repos relevant to a project.")
    ap.add_argument("--keywords", nargs="+", required=True, help="Keywords describing the project/domain")
    ap.add_argument("--language", default=None, help="Primary language filter (e.g. php, typescript, python)")
    ap.add_argument("--topic", default=None, help="GitHub topic filter (e.g. wordpress, static-site-generator)")
    ap.add_argument("--min-stars", type=int, default=300, help="Minimum stars (default: 300)")
    ap.add_argument("--active-days", type=int, default=365, help="Only repos pushed to within N days (default: 365)")
    ap.add_argument("--limit", type=int, default=10, help="Number of results to show (default: 10)")
    ap.add_argument("--exclude", nargs="*", default=[], help="Repos to exclude, e.g. owner/repo")
    ap.add_argument("--format", choices=["json", "markdown"], default="markdown")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"), help="GitHub token (or set GITHUB_TOKEN env var)")
    args = ap.parse_args()

    query = build_query(
        args.keywords, args.language, args.min_stars, args.active_days, args.topic, args.exclude
    )
    data, remaining = fetch(query, per_page=min(args.limit * 3, 100), token=args.token)

    items = data.get("items", [])
    ranked = []
    for repo in items:
        metrics = score_repo(repo, args.keywords)
        ranked.append((repo, metrics))

    ranked.sort(key=lambda x: x[1]["score"], reverse=True)
    ranked = ranked[: args.limit]

    if args.format == "json":
        out = [
            {
                "full_name": r.get("full_name"),
                "url": r.get("html_url"),
                "description": r.get("description"),
                "stars": r.get("stargazers_count"),
                "score": m["score"],
                "days_since_push": m["days_since_push"],
                "relevance": m["relevance"],
                "rationale": rationale(r, m, args.keywords),
            }
            for r, m in ranked
        ]
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    print(f"# Repo Scout results — query: `{query}`\n")
    print(f"Total matches on GitHub: {data.get('total_count', '?')} | Showing top {len(ranked)}")
    if remaining is not None:
        print(f"(GitHub API calls remaining this window: {remaining})\n")
    else:
        print()

    for i, (repo, m) in enumerate(ranked, 1):
        print(f"## {i}. [{repo.get('full_name')}]({repo.get('html_url')})  — score {m['score']}")
        print(f"⭐ {repo.get('stargazers_count'):,}  |  🍴 {repo.get('forks_count'):,}  |  last push {m['days_since_push']}d ago")
        if repo.get("description"):
            print(f"> {repo.get('description')}")
        print(f"**Why it's here:** {rationale(repo, m, args.keywords)}\n")


if __name__ == "__main__":
    main()
