# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

1TAP is a single-process Discord bot: discord.py 2.x, async SQLAlchemy 2.0 on SQLite, Alembic, Pydantic. The main dev machine is Windows (PowerShell, venv in `.venv`).

## Commands

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt     # runtime + test deps; keep a single requirements file
python bot.py                       # needs DISCORD_BOT_TOKEN in .env; applies migrations on startup
pytest                              # whole suite
pytest tests/test_auto_unmute.py::test_removes_role_and_logs_unmute   # single test
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

No linter or formatter is configured. Match the surrounding style.

## Architecture

The full picture is in `docs/architecture.md`. These are the parts that take several files to piece together:

- **Startup (`bot.py` `setup_hook`):** `alembic upgrade head` (in a worker thread), then every `modules/*.py` is auto-loaded as an extension, then `tree.sync()` (global). Every module in `modules/` needs `async def setup(bot)`. A module that fails to load is logged and skipped, not fatal.
- **Layering:** cogs never open sessions or write SQL. They call functions in `database/repository.py`, which own the sessions and return Pydantic models from `database/schemas.py`, never ORM objects. `set_config` only accepts keys in `_ALLOWED_CONFIG_KEYS`, so a new `GuildConfig` column must be added there too.
- **Schema changes:** Alembic owns the schema. A model change needs a migration in `migrations/versions/` (named `000N_description.py`). SQLite needs batch mode (`render_as_batch=True` is set in `migrations/env.py`).
- **Configuration:** process-level settings come from env / `.env` via `settings.py`. Per-server settings (mod-log channel, mute mode, muted role) live in the DB and are changed at runtime with `/config`.
- **Commands:** every user-facing command exists as both prefix (`!`) and slash (`/`). Both are thin wrappers around a shared `_apply_*` helper that returns `(message, error)`, with exactly one of the two set. Replies and logs use `user_label()` and `allowed_mentions=NO_PING`. The bot never pings users.
- **Scheduler (`modules/scheduler.py`):** a DB-backed job queue. Get it with `bot.get_cog("Scheduler")`. `create_timer(event, expires_at, payload, guild_id=...)` fires `on_<event>_timer_complete(timer)`, which any cog can listen for. `cancel_timer(event, **fields)` matches on payload fields. Delivery is **at-most-once**: the row is deleted before dispatch, so a handler that can fail must reschedule itself. The auto-unmute in `modules/moderation.py` shows the pattern (retry counter in the payload, mod-log alert at the end). A guild's timers are deleted in `on_guild_remove`.
- **Logging:** use module loggers named `onetap.<module>` (e.g. `onetap.moderation`), never `print`.

## Tests

- `tests/` uses pytest with `asyncio_mode = auto`, so async tests need no markers.
- Tests are pure unit tests: no Discord connection and no database. Build the cog with a `MagicMock` bot, `monkeypatch` the `repository` functions, and use `AsyncMock` for awaited Discord calls. `tests/test_auto_unmute.py` is the reference.
- A bug fix comes with a test that fails on the old code.

## Keeping docs in sync

The docs live in `README.md`, `docs/architecture.md` and `docs/specs/*.md` (one spec per subsystem). They are part of the change, not a follow-up:

- If behaviour changes, update the matching spec **in the same PR** and bump its **Last updated** date.
- A new subsystem gets a new spec copied from `docs/specs/_template.md`, plus a row in the index in `docs/specs/README.md`.
- A new env var goes into the README configuration table and `.env.example`.
- If a doc and the code disagree, the code wins. Fix the doc, or file an issue if the code is what's wrong.

## Filing issues

If you find a bug, a gap or a docs/code mismatch outside the current task, **file it right away** with `gh issue create`. Don't silently fix it inside an unrelated change. Include the `file:line`, a concrete failure scenario and the expected behaviour. Mention the issue number in your summary or PR description.

## Git & PR workflow

Every change (feature, fix or docs) starts from a GitHub issue and gets its own branch and PR:

1. **Issue:** use the existing one, or create it first with `gh issue create`. One issue = one branch = one PR.
2. **Branch from the issue:**
   ```bash
   gh issue develop <n> --name <type>/<n>-short-description --base master --checkout
   ```
   This links the branch under the issue's *Development* section. `<type>` is the Conventional Commit type (`feat`, `fix`, `docs`, …). Never commit directly to `master`.
3. **Commit** using Conventional Commits.
4. **Before the PR:** run `pytest`.
5. **PR:** put `Closes #<n>` in the description so the merge closes the issue and links it to the PR.
6. **Review and merge:** the `claude-code-review` workflow reviews each PR automatically. For an on-demand review or a question, write `@claude` in a PR or issue comment. Act on valid findings, then merge with `gh pr merge <n> --merge --delete-branch`.

Also:

- No confirmation is needed in this repo to commit, push, open or merge your own PRs. Force-push and history rewrites still need explicit approval.
- Gotchas for the review workflow:
  - It does not review PRs that change `.github/workflows/claude*.yml`, because the action only runs when the workflow file matches `master`.
  - It skips PRs that Claude has already commented on. Use `@claude` to get a re-review.
