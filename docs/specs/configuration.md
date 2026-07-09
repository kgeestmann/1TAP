# Configuration

- **Status:** Stable
- **Last updated:** 2026-07-09
- **Code:** [`settings.py`](../../settings.py), [`modules/config.py`](../../modules/config.py)

## Purpose

Two distinct layers of configuration:

1. **Deployment settings** — secrets and process-level options, loaded from the
   environment / `.env` at startup (token, DB path, logging).
2. **Per-guild settings** — runtime behaviour each server configures itself via
   `/config` slash commands (mod-log channel, mute mode, muted role).

## Scope

- The Pydantic `Settings` object and its environment mapping.
- The `/config` command group and its subcommands.

### Non-goals

- Storage mechanics for per-guild settings — see
  [database.md](database.md) (`guild_config` table, repository).

## Deployment settings (`settings.py`)

`Settings` is a `pydantic_settings.BaseSettings`. Fields are populated from
environment variables (case-insensitive) or `.env`; unknown keys are ignored
(`extra="ignore"`).

| Field | Env var | Default | Purpose |
| ----- | ------- | ------- | ------- |
| `discord_bot_token` | `DISCORD_BOT_TOKEN` | `""` | Bot token (required to start). |
| `database_path` | `DATABASE_PATH` | `data/bot.db` | SQLite file. |
| `log_level` | `LOG_LEVEL` | `INFO` | Root log level. |
| `log_dir` | `LOG_DIR` | `logs` | Log directory. |
| `log_file_name` | `LOG_FILE_NAME` | `bot.log` | Log file name. |
| `log_max_bytes` | `LOG_MAX_BYTES` | `5000000` | Log rotation size. |
| `log_backup_count` | `LOG_BACKUP_COUNT` | `5` | Rotated files kept. |

Derived helpers: `database_url` (async), `sync_database_url` (Alembic),
`log_file_path`.

A single module-level `settings` instance is imported wherever config is needed.

## Per-guild settings (`/config`)

The `/config` command group is **guild-only** and gated behind the **Manage
Server** permission (`default_permissions`). Responses are ephemeral.

| Command | Arguments | Effect |
| ------- | --------- | ------ |
| `/config show` | — | Show the current settings for this server. |
| `/config logchannel` | `channel` | Set the channel that receives mod-log messages. |
| `/config mutemode` | `mode: timeout \| role` | Choose the mute strategy. |
| `/config muterole` | `role` | Use an existing role as the muted role (role mode). |
| `/config setupmuterole` | — | Create a `Muted` role and deny it messaging/voice in every channel, then switch to role mode. |

All writes go through `repository.set_config`; reads through
`repository.get_config`, which returns a typed `GuildConfigModel`.

### Defaults

A server with no stored row behaves as: `mute_mode = timeout`, no log channel,
no muted role. The row is created on the first `/config` write.

## Edge cases & error handling

- **`mutemode role` with no muted role set** returns a hint to run
  `/config setupmuterole` or `/config muterole`.
- **`setupmuterole`** requires the bot to have **Manage Roles** + **Manage
  Channels**; it reports the missing permission instead of failing silently. It
  reuses an existing configured or `Muted`-named role if present, and reports how
  many channels it could not update.
- Unknown config keys are impossible via commands; the repository whitelists keys
  regardless.

## Rationale

Splitting deployment config (env, one process) from per-guild config (database,
many servers) lets a single deployment serve many servers with different
behaviour, configured by their own admins — no dashboard, no redeploy. Pydantic
gives typed, validated settings instead of scattered `os.getenv` calls.

## Future work

- `/config reset` to restore defaults.
- More per-guild options as features land (e.g. default mute duration).
