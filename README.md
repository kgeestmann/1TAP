# 1TAP

> The multipurpose Discord bot that does it all.

A Discord bot built on **discord.py 2.x**, with a typed configuration layer
(**Pydantic**), an async **SQLAlchemy 2.0** data layer on **SQLite**, and
schema migrations managed by **Alembic**.

---

## Features

- **Slash + prefix commands** — every user-facing command is available as both
  `/command` and `!command`.
- **Moderation** — `kick`, `mute`, `unmute`, with role-hierarchy safety checks.
- **Per-guild configuration** — each server configures its own mod-log channel
  and mute behaviour at runtime via `/config`, no redeploy or dashboard needed.
- **Two mute strategies** — native Discord **timeouts** or a managed **Muted
  role**, selectable per server.
- **Persistent moderation logs** — stored in SQLite.
- **Rotating file logs** — structured application logs on console and disk.

## Quickstart

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env        # then put your bot token in .env
python bot.py
```

The bot applies database migrations automatically on startup. The required
**privileged intents** (Server Members, Message Content) must be enabled in the
[Discord Developer Portal](https://discord.com/developers/applications), and the
bot must be invited with the **Kick Members**, **Moderate Members**, **Manage
Roles**, and **Manage Channels** permissions.

## Configuration

All configuration is loaded from the environment / `.env` (see
[`settings.py`](settings.py) and [`.env.example`](.env.example)).

| Variable             | Default        | Purpose                              |
| -------------------- | -------------- | ------------------------------------ |
| `DISCORD_BOT_TOKEN`  | —              | Bot token (required)                 |
| `DATABASE_PATH`      | `data/bot.db`  | SQLite database file                 |
| `LOG_LEVEL`          | `INFO`         | Root log level                       |
| `LOG_DIR`            | `logs`         | Directory for rotating log files     |

Runtime, per-server settings (mod-log channel, mute mode, muted role) are set
with the `/config` slash commands — see
[docs/specs/configuration.md](docs/specs/configuration.md).

## Project layout

```
bot.py               # entry point: bot subclass, events, error handlers
settings.py          # Pydantic settings (env / .env)
logging_config.py    # console + rotating-file logging setup
database/            # SQLAlchemy models, Pydantic schemas, session, repository
modules/             # cogs: general, moderation, config, scheduler (timed jobs)
migrations/          # Alembic environment + versioned migrations
docs/                # architecture overview and component specs
```

## Documentation

Full documentation lives in [`docs/`](docs/README.md). Start with the
[architecture overview](docs/architecture.md), then the individual
[specs](docs/specs/README.md).

## Development

- **Run the tests:** `pytest` (installed via `requirements.txt`).
- **Add a migration:** `alembic revision --autogenerate -m "describe change"`,
  then `alembic upgrade head` (or just restart the bot).
- **Run against a scratch database:** set `DATABASE_PATH` to a temp file.
- **Coding conventions and the spec format** are documented in
  [docs/specs/README.md](docs/specs/README.md).
