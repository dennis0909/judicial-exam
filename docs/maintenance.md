# Maintenance

## Goal

Keep this repo's scraper pipeline, notes, and support docs compact enough that Claude, Codex, and Gemini can hand off work without re-discovery.

## Cadence

- After any scraper/schema change: update `NEXT_SESSION.md`
- After each major session: prune stale notes in `docs/`
- Once per week: review `memory / md / skill` style notes and archive anything no longer on the active path

## Rules

- Keep one source of truth per topic. Do not leave the same workflow half-documented in multiple markdown files.
- When a script contract changes, update the downstream script and the usage doc in the same commit.
- Prefer short operational notes over long chat-history dumps.
- Archive stale planning notes instead of keeping contradictory versions in place.

## Minimum Checklist

- `scripts/` still agree on file locations and schema keys
- `NEXT_SESSION.md` reflects the current pipeline
- `docs/` does not contain obsolete commands or dead TODOs
- Newly added memory/skill notes are either linked from an index doc or removed
