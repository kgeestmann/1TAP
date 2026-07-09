# Database & Migrations

- **Status:** Stable
- **Last updated:** 2026-07-09
- **Code:** [`database/`](../../database), [`migrations/`](../../migrations), [`alembic.ini`](../../alembic.ini)

## Purpose

Persist per-guild configuration and moderation logs in a relational store, with
a typed async data-access layer and versioned schema migrations.

## Scope

- SQLAlchemy 2.0 ORM models (`database/models.py`).
- Async engine and session factory (`database/session.py`).
- The repository — the single data-access surface (`database/repository.py`).
- Pydantic read schemas returned to callers (`database/schemas.py`).
- Alembic migration environment and versions (`migrations/`).

### Non-goals

- Business logic (lives in cogs) and multi-database support (SQLite only).

## Data model

### `guild_config`

One row per guild. Absent row ⇒ defaults (see the repository).

| Column | Type | Notes |
| ------ | ---- | ----- |
| `guild_id` | BigInteger, PK | Discord guild ID (not autoincrement). |
| `log_channel_id` | BigInteger, null | Mod-log channel; null = logging off. |
| `mute_mode` | String, not null | `timeout` or `role` (see `MuteMode`). |
| `muted_role_id` | BigInteger, null | Role used in `role` mute mode. |

### `mod_logs`

Append-only record of moderation actions.

| Column | Type | Notes |
| ------ | ---- | ----- |
| `id` | Integer, PK autoincrement | |
| `guild_id` | BigInteger, null | |
| `action` | String, not null | e.g. `kick`, `mute`, `unmute`. |
| `user_id` / `user_name` | BigInteger / String, null | Target. |
| `moderator_id` / `moderator_name` | BigInteger / String, null | Actor. |
| `reason` | String, null | |
| `timestamp` | DateTime, not null | UTC; defaulted in the model. |

Discord snowflake IDs use `BigInteger` (they exceed 32-bit).

## Data access (repository)

Cogs call the repository; they never open sessions or write SQL. Each function
opens its own `async_session`, commits, and closes.

| Function | Returns | Description |
| -------- | ------- | ----------- |
| `get_config(guild_id)` | `GuildConfigModel` | Config for a guild, or a defaults object if none exists. |
| `set_config(guild_id, **fields)` | `None` | Upsert one or more config fields. Keys are whitelisted. |
| `add_log(guild_id, action, user, moderator, reason=None)` | `ModLog` | Insert a moderation-log row. |

`get_config` returns a **Pydantic** `GuildConfigModel` (validated, typed, with
enum `mute_mode` and sane defaults) rather than an ORM object or dict, so cogs
work with a stable, decoupled shape. `set_config` rejects unknown keys with
`ValueError`, which also guards the internal `UPDATE` from injection.

## Migrations (Alembic on SQLite)

Alembic owns the schema. The initial schema is `migrations/versions/0001_initial.py`.

- **The app uses the async engine** (`sqlite+aiosqlite://`); **Alembic uses a
  sync engine** (`sqlite://`). Both derive their URL from
  `settings` — one source of truth (`migrations/env.py`).
- **Batch mode is on** (`render_as_batch=True`). SQLite cannot `ALTER TABLE` to
  drop/alter columns; batch mode makes Alembic rebuild the table so such
  migrations work. This is the key enabler for evolving the schema on SQLite.
- **Auto-upgrade on startup:** `bot.py` runs `alembic upgrade head` in a worker
  thread during `setup_hook`, so a fresh checkout is migrated automatically.

### Workflow: changing the schema

1. Edit the models in `database/models.py`.
2. Generate a migration:
   ```bash
   alembic revision --autogenerate -m "describe the change"
   ```
3. Review the generated file in `migrations/versions/`.
4. Apply it: `alembic upgrade head` (or just restart the bot).

`alembic check` reports whether the models and the latest migration are in sync
(useful in CI).

## Configuration

| Setting | Env var | Default | Meaning |
| ------- | ------- | ------- | ------- |
| `database_path` | `DATABASE_PATH` | `data/bot.db` | SQLite file location. |

`data/` is gitignored. Point `DATABASE_PATH` at a temp file for a scratch DB.

## Edge cases & error handling

- **Unknown guild:** `get_config` returns defaults; no row is created until
  `set_config` writes one.
- **Unknown config key:** `set_config` raises `ValueError` before touching the DB.
- **Concurrent writes:** each call uses its own short-lived session/transaction;
  SQLite serialises writes.

## Rationale

SQLite removes operational overhead while staying a real, migratable relational
DB. The async ORM matches the bot's event loop. A thin repository keeps SQL in
one place and hands cogs typed objects. Batch-mode Alembic makes "no painful
migrations later" true even on SQLite.

## Future work

- Additional tables as features land (e.g. `warnings`).
- Indexes on `mod_logs(guild_id, timestamp)` once query patterns exist.
