# Logging

- **Status:** Stable
- **Last updated:** 2026-11-20
- **Code:** [`logging_config.py`](../../logging_config.py), configured in [`bot.py`](../../bot.py)

## Purpose

Provide a single, consistent logging setup for the whole process: human-readable
output on the console and a durable, size-rotated log file on disk. Replaces all
ad-hoc `print` calls.

## Scope

- Root logger configuration (level, handlers, format).
- A rotating file handler writing to a gitignored `logs/` directory.
- Taming noisy third-party loggers (`discord`, `sqlalchemy`, `aiosqlite`).

### Non-goals

- Structured/JSON logging, log shipping, or external aggregation.
- Per-module log files. Everything goes to one rotating file.

## Behaviour

`setup_logging()` is called once, first thing in `__main__` (before the token
check and `bot.run`). It:

1. Ensures `settings.log_dir` exists.
2. Sets the **root** logger level from `settings.log_level`.
3. Installs two handlers, both using the same formatter:
   - a `StreamHandler` (console),
   - a `RotatingFileHandler` writing to `settings.log_file_path`.
4. Clears any pre-existing handlers so configuration is deterministic.
5. Raises the threshold of chatty libraries to `WARNING`.

`bot.run(..., log_handler=None)` tells discord.py **not** to install its own
handler, so all logs flow through our root configuration.

The entry point uses `getLogger("onetap")`; modules use a child logger named
`onetap.<module>` (e.g. `getLogger("onetap.scheduler")`), so the whole bot sits
under one `onetap` hierarchy. Nobody calls `print`.

### Format

```
2026-07-09 16:05:24 [INFO] Ready and serving 1 guild(s)
```

`%(asctime)s [%(levelname)s] %(message)s`, dated `%Y-%m-%d %H:%M:%S`. Bracketed
level, no logger name — compact and easy to scan.

### Rotation

Size-based via `RotatingFileHandler`: at `log_max_bytes` the file is rolled to
`bot.log.1`, `bot.log.2`, …, keeping `log_backup_count` backups. Old files are
discarded automatically, so disk usage is bounded.

## Interface

| Symbol | Description |
| ------ | ----------- |
| `setup_logging() -> None` | Configure root logging. Idempotent: clears handlers on each call. |

## Configuration

From [`settings.py`](../../settings.py) (env / `.env`):

| Setting | Env var | Default | Meaning |
| ------- | ------- | ------- | ------- |
| `log_level` | `LOG_LEVEL` | `INFO` | Root log level (`DEBUG`/`INFO`/`WARNING`/…). |
| `log_dir` | `LOG_DIR` | `logs` | Directory for log files (gitignored). |
| `log_file_name` | `LOG_FILE_NAME` | `bot.log` | Log file name. |
| `log_max_bytes` | `LOG_MAX_BYTES` | `5000000` | Rotation threshold (~5 MB). |
| `log_backup_count` | `LOG_BACKUP_COUNT` | `5` | Number of rotated files kept. |

## Edge cases & error handling

- **Unhandled command/app-command errors** are logged with `exc_info` so the
  full traceback lands in the file (see the handlers in `bot.py`).
- **Missing token** logs an error and aborts startup instead of printing.
- An **invalid `LOG_LEVEL`** falls back to `INFO` (`getattr(logging, …, INFO)`).
- The `logs/` directory is created if absent.

## Rationale

Size-based rotation keeps disk usage predictable with zero external
dependencies. Owning the root config (rather than relying on discord.py's
handler) means library and application logs share one format and destination.

## Future work

- Optional JSON formatter for machine parsing.
- Optional timed rotation (daily) if operational needs change.
