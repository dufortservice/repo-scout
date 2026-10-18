---
name: repo-scout
description: Scouts GitHub for the most popular, actively-maintained repositories relevant to the current project's tech stack, scores them by relevance/popularity/maintenance, and produces a ranked shortlist with integration rationale. Use this whenever the user asks to find libraries, tools, or repos to integrate, wants to know "what's trending" that could help their project, asks for alternatives to something they're building by hand, or wants a second opinion on whether to build vs. use an existing open-source solution. Also trigger on phrases like "scout GitHub", "find popular repos for X", "is there already a library for this", or "what should I use instead of building this myself".
---

# Repo Scout

Finds real, currently-maintained open-source projects that fit what the user
is building, instead of relying on training-data memory (which goes stale and
misses anything recent). Works from the actual GitHub Search API, so results
reflect the current state of the ecosystem.

## When to use this

- User is starting a new feature and might be reinventing a wheel that
  already exists as a well-maintained library.
- User asks "what's popular for X" or "what should I look at for Y".
- User wants to sanity-check a build-vs-adopt decision.
- User wants a periodic sweep of their stack to catch newer/better
  alternatives to what they currently use.

Do NOT use this for:
- Looking up a specific named repo the user already knows (just fetch it
  directly, e.g. with `gh repo view` or a web fetch).
- Questions with no open-source angle (pure business/strategy questions).

## Workflow

### Step 1 — Detect the project stack

If the user hasn't described their stack, look at the current working
directory (or the repo path they mention) for manifest files:

| File | Signals |
|---|---|
| `package.json` | JS/TS, framework in `dependencies` (react, astro, next, vue...) |
| `composer.json` | PHP, framework (wordpress plugin/theme conventions, laravel...) |
| `requirements.txt` / `pyproject.toml` | Python, key libs |
| `go.mod` | Go |
| `Cargo.toml` | Rust |
| `Gemfile` | Ruby |
| `*.csproj` | .NET |

Also skim the README or top-level folder names for domain hints (e.g.
"gallery", "booking", "invoicing", "telemedicine", "inventory") — these become
keywords, not just the language.

If there's no local project to inspect (pure conversational request), just
ask the user for: (a) the language/framework, (b) 3-5 keywords describing the
problem domain, (c) anything they explicitly want to exclude (e.g. tools
they've already evaluated and rejected).

### Step 2 — Run the scout script

Use the bundled script (stdlib-only Python 3, no install needed) rather than
trying to hand-roll GitHub queries or trusting memorized repo names. It lives
at `${CLAUDE_PLUGIN_ROOT}/skills/repo-scout/scripts/scout.py`.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/repo-scout/scripts/scout.py" \
  --keywords "wordpress" "booking" \
  --language php \
  --min-stars 300 \
  --active-days 365 \
  --limit 10
```

**Important tuning notes:**

- **Keep `--keywords` to 2-3 terms per run.** GitHub's search API ANDs every
  keyword against name/description/topics — 4+ keywords very often returns
  zero results. If you have more than 3 relevant keywords, run the script
  multiple times with different 2-3-keyword combinations and merge/dedupe the
  results yourself rather than cramming everything into one query.
- `--min-stars` default is 300 — lower it (e.g. 50) for niche domains where
  even the best tool won't have huge star counts.
- `--active-days` default is 365 — this is the "is it actually maintained"
  filter. Loosen it (e.g. 730) only if the domain is niche enough that good
  tools might legitimately be stable/dormant.
- Add `--exclude owner/repo` for anything the user already knows about and
  wants filtered out of results.
- The GitHub Search API allows about 10 unauthenticated requests per minute.
  When running several keyword combinations back to back, keep it to a
  handful of runs; if you hit the limit, wait a minute and retry.
- Use `--format json` when you need to post-process/merge results across
  multiple runs; use the default markdown format for a final human-readable
  report.

### Step 3 — Cross-reference against the user's actual project

Don't just paste the raw ranked list. For each of the top 3-5 candidates:

1. Explain in one sentence how it would plug into what the user is already
   building (which file/module it would replace or augment).
2. Flag effort/risk: does it require replacing existing infrastructure, or
   can it be added alongside? Any migration cost?
3. Note license compatibility with the user's project (if their project is
   closed-source/commercial, flag GPL-family licenses as needing review).
4. If the repo's last push is outside the "actively maintained" window shown
   by the script but the tool is still clearly the best fit, say so explicitly
   rather than silently dropping it — recency is a signal, not an absolute
   filter.

### Step 4 — Present the shortlist

Lead with the single best-fit recommendation and why, then list runner-ups.
Keep it scannable — this is a decision-support list, not an essay. Always
include the repo URL so the user can look themselves.

## Notes on the scoring

The script's score combines four signals (see `scripts/scout.py` for exact
weights):

- **Popularity** — log-scaled star count (avoids mega-repos always winning)
- **Freshness** — recency of last push, decaying over ~2 years
- **Momentum** — stars-per-day-since-creation, a rough trending proxy since
  GitHub has no public trending API
- **Relevance** — fraction of the given keywords found in name/description/topics

This is a heuristic, not ground truth — always sanity-check the top result
against the actual README before recommending it as a serious adoption, not
just a lead worth investigating.
