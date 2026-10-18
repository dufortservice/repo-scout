# Repo Scout

**Find the library before you write it.**

Repo Scout is a Claude plugin that searches GitHub for popular, actively
maintained open-source projects that fit what you're building, and ranks them
for your stack. Claude then explains how the best candidates would plug into
your project, what they would cost to adopt, and whether their licenses fit.

It works from the live GitHub Search API, not from what a model remembers, so
results reflect the ecosystem as it is today.

## When it helps

- You're about to build a feature that probably already exists as a library.
- You want to know what's popular and maintained for a given problem.
- You're weighing build vs. adopt and want a second opinion.
- You want a periodic sweep of your stack for newer or better alternatives.

Just ask in plain language, for example:

> Is there already a library for PDF invoice generation in our Laravel app?

> Scout GitHub for booking calendars that would work with this project.

## How it works

1. **Detects your stack** from manifest files in the current project
   (`package.json`, `composer.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`,
   `Gemfile`, `*.csproj`) plus domain hints from the README and folder names.
   With no project open, Claude asks for the language and a few keywords.
2. **Queries GitHub** with a bundled script that filters by language, minimum
   stars and recent activity.
3. **Scores each repository** on four signals:
   - *Relevance*: how many of your keywords appear in its name, description and topics
   - *Freshness*: how recently it was pushed to
   - *Popularity*: star count, log-scaled so giant repos don't always win
   - *Momentum*: stars gained per day since creation, a rough "trending" signal
4. **Cross-references the top results with your project** and presents a short
   list: the best fit first, with how it would integrate, the effort and risk
   involved, and license notes.

The score is a heuristic for finding leads, not a verdict. Claude is instructed
to say so and to point you to each repository so you can check it yourself.

## Installation

Install Repo Scout from the [Claude plugin directory](https://claude.ai/directory).
It works in the Claude app and in Claude Code.

In Claude Code you can also install it straight from this repository:

```
/plugin install repo-scout --marketplace dufortservice/repo-scout
```

## Requirements

- Python 3 (standard library only, nothing to install)
- Network access to `api.github.com`

No account or token is needed. The plugin uses the public, unauthenticated
GitHub Search API, which allows about 10 requests per minute: plenty for
occasional use. If you hit the limit, wait a minute and ask again.

## Data and privacy

- **What the script sends:** search keywords, an optional language and topic
  filter, and minimum-stars and activity thresholds. These go only to the
  GitHub Search API (`api.github.com`).
- **What the script does not send:** it never uploads your source code, file
  contents or file names. Claude reads your manifest files in the conversation,
  as it normally does, and only the keywords it derives are used in the query.
- **No credentials:** the plugin reads no tokens, keys or passwords, from your
  machine or anywhere else.
- **No other services:** the plugin has no server of its own, collects no
  analytics and stores nothing.

## Using the script directly

The script also runs on its own:

```bash
python3 skills/repo-scout/scripts/scout.py \
  --keywords "static site" "markdown" \
  --language typescript \
  --min-stars 300 \
  --active-days 365 \
  --limit 10
```

Options: `--keywords` (required, 2-3 terms work best), `--language`, `--topic`,
`--min-stars` (default 300), `--active-days` (default 365), `--limit`
(default 10), `--exclude owner/repo ...`, `--format markdown|json`.

## License

[MIT](./LICENSE) © 2026 Dufort, [DufortService](https://dufortservice.com)
