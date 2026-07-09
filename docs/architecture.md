# Architecture

## Overview

1TAP is a single-process Discord bot. At startup it configures logging, runs
database migrations, loads command modules ("cogs"), and connects to Discord.
From then on it reacts to gateway events (commands, presence updates).

```
                         ┌──────────────────────────────┐
                         │            bot.py            │
                         │  OneTapBot(commands.Bot)     │
                         │  • setup_hook (migrate,      │
                         │    load cogs, sync commands) │
                         │  • event + error handlers    │
                         └──────────────┬───────────────┘
                                        │ loads
                     ┌──────────────────┼───────────────────┐
                     ▼                  ▼                   ▼
             modules/general    modules/moderation   modules/config
                     │                  │                   │
                     └──────────────────┴───────────────────┘
                                        │ calls
                                        ▼
                            database/repository.py
                          (async data-access functions)
                                        │
                          ┌─────────────┴─────────────┐
                          ▼                           ▼
                database/session.py            database/schemas.py
              (async engine + session)        (Pydantic read models)
                          │
                          ▼
                database/models.py  ──────►  SQLite (via aiosqlite)
              (SQLAlchemy ORM models)         schema owned by Alembic
```

Cross-cutting concerns:

- **[settings.py](../settings.py)** — a single Pydantic `Settings` object,
  loaded from the environment / `.env`, imported everywhere configuration is
  needed.
- **[logging_config.py](../logging_config.py)** — configures root logging once
  at startup.

## Layers

| Layer | Location | Responsibility |
| ----- | -------- | -------------- |
| Entry point | `bot.py` | Process lifecycle, event wiring, global error handling. |
| Commands (cogs) | `modules/` | Translate Discord interactions into actions; no direct DB/SQL. |
| Data access | `database/repository.py` | The **only** place cogs touch persistence. Returns typed models. |
| Persistence | `database/{models,session}.py` | ORM models and the async engine/session. |
| Schemas | `database/schemas.py` | Pydantic models the repository returns to cogs. |
| Migrations | `migrations/` | Alembic environment and versioned schema changes. |

**Rule of thumb:** cogs call the repository, the repository owns sessions and
SQL. A cog should never import `session` or write a query inline.

## Startup sequence

1. `setup_logging()` — console + rotating file handlers.
2. `run_migrations()` — `alembic upgrade head` (sync, in a worker thread).
3. `load_extension(...)` for each cog in `modules/`.
4. `tree.sync()` — register slash commands with Discord.
5. Presence rotation task starts; bot goes online.

## Key decisions

### discord.py 2.x
The mainstream, actively maintained library. Slash commands via
`app_commands`, cogs, and async extension loading are its modern idioms. (The
project was migrated off Pycord to land on this standard.)

### SQLite + SQLAlchemy 2.0 (async) + Alembic
- **SQLite** keeps operations trivial (one file, no server) while remaining a
  real relational store we can migrate.
- **SQLAlchemy 2.0 async** gives typed models and non-blocking I/O that fits the
  bot's event loop.
- **Alembic** owns the schema so changes are versioned and reproducible.
  SQLite's limited `ALTER TABLE` is handled with Alembic **batch mode**
  (`render_as_batch=True`); migrations run with a synchronous engine while the
  app uses the async one. See [specs/database.md](specs/database.md).

### Pydantic everywhere config-shaped
`pydantic-settings` gives typed, validated environment config, and the
repository returns Pydantic schemas so cogs work with typed objects and enums
instead of raw dicts. See [specs/configuration.md](specs/configuration.md).

### Per-guild config in the database (not a web dashboard)
Servers configure the bot at runtime through `/config` slash commands. Settings
are stored per guild, so one deployment serves many servers with different
behaviour.

## Conventions

- Every user-facing command is offered as both slash and prefix.
- All moderation actions pass role-hierarchy checks and handle Discord API
  errors explicitly (see [specs/moderation.md](specs/moderation.md)).
- No `print` — use module loggers (`logging.getLogger(__name__)`).
- Runtime artifacts (`data/`, `logs/`, `.env`, `.venv/`) are gitignored.
