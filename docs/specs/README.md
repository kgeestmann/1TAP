# Specifications

Each subsystem of 1TAP has its own spec: a focused, self-contained document that
describes what it does, how it behaves, and why. We keep **one spec per
component** rather than a single monolithic document — specs are easier to read,
review, and evolve, and produce clean diffs.

## Index

| Spec | Subsystem | Summary |
| ---- | --------- | ------- |
| [logging.md](logging.md) | Logging | Console + rotating file logging, levels, format. |
| [database.md](database.md) | Persistence | SQLAlchemy models, sessions, Alembic migrations on SQLite. |
| [configuration.md](configuration.md) | Configuration | Env settings (Pydantic) and per-guild `/config` commands. |
| [scheduler.md](scheduler.md) | Scheduler | Persistent, precise timed jobs (auto-unmute, future temp-bans/reminders). |
| [moderation.md](moderation.md) | Moderation | `kick`, `mute`, `unmute`, hierarchy rules, mute modes. |

## Conventions every spec follows

- **Copy [`_template.md`](_template.md)** when starting a new spec.
- Keep the **Status** and **Last updated** fields current.
- Document **behaviour and rationale**, not line-by-line code — the code is the
  source of truth for implementation detail; link to it.
- Call out **edge cases and error handling** explicitly.
- Update the spec **in the same commit** as the behaviour change, and add a row
  to the index above when introducing a new spec.

## Spec statuses

- **Draft** — proposed or in progress; behaviour may change.
- **Stable** — implemented and current.
- **Deprecated** — kept for history; superseded by another spec (link it).
