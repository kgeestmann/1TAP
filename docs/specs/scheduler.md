# Scheduler

- **Status:** Stable
- **Last updated:** 2026-07-09
- **Code:** [`modules/scheduler.py`](../../modules/scheduler.py), timers in [`database/`](../../database)

## Purpose

Run arbitrary actions at a future time, precisely and durably. A generic,
persistent job scheduler that any feature can use (auto-unmute today; temp-ban
expiry, reminders, scheduled posts later).

## Scope

- The `timers` table and its repository functions.
- The `Scheduler` cog: a single dispatch task and the public timer API.
- The event-dispatch contract that decouples scheduling from handling.

### Non-goals

- Knowing what any specific timer *means* — handlers own that (e.g. moderation
  handles `unmute`). See [moderation.md](moderation.md).
- Cross-process scheduling (single process today; see *Scaling*).

## Design

Modelled on the well-known discord.py "RoboDanny" reminder pattern.

- **One background task**, not one-per-timer. It asks the DB for the *next* due
  timer and `asyncio.sleep`s **exactly** until then — no fixed poll interval.
- **Persistent:** every timer is a row in `timers`. Pending jobs survive
  restarts; on boot the task simply reads the DB and continues.
- **Idle = zero CPU:** with no timers, the task waits on an `asyncio.Event`
  (`_have_data`) until one is created. No busy-looping.
- **Preemption:** creating a timer sooner than the one currently being slept on
  cancels and restarts the task so it picks up the nearer deadline.
- **Bounded sleep:** only timers due within `MAX_SLEEP_DAYS` (40) are actively
  slept on; longer ones wait in the DB until they enter the window. This bounds a
  single `asyncio.sleep` and tolerates clock/library limits.
- **Decoupled firing:** when a timer elapses the scheduler deletes the row and
  calls `bot.dispatch("<event>_timer_complete", timer)`. Handlers are ordinary
  cog listeners — the scheduler never imports them.
- **Resilient loop:** per-iteration errors are logged and backed off (5s); they
  never kill the loop or hot-respawn it. Cancellation (reschedule/unload)
  propagates cleanly.

## Interface

`Scheduler` cog (obtain with `bot.get_cog("Scheduler")`):

| Method | Description |
| ------ | ----------- |
| `create_timer(event, expires_at, payload) -> TimerModel` | Schedule `event` to fire at `expires_at` with `payload`. |
| `cancel_timer(event, **payload_match) -> int` | Delete timers of `event` whose payload matches all given fields; returns count. |

**Firing contract:** a handler listens for `on_<event>_timer_complete(timer)`,
where `timer` is a `TimerModel` (`id`, `event`, `expires_at`, `created_at`,
`payload`). Handlers must be idempotent-friendly and tolerant of stale state
(the target may have left, the role may be gone, etc.).

### Example (auto-unmute)

```python
# schedule (moderation, on a timed role mute)
await scheduler.create_timer(
    "unmute", expires_at, {"guild_id": g, "user_id": u, "role_id": r}
)

# handle (moderation cog)
@commands.Cog.listener()
async def on_unmute_timer_complete(self, timer):
    ...  # remove the role, log, announce
```

## Edge cases & error handling

- **Restart while a timer is pending:** re-read from DB on boot; nothing lost.
- **Bot offline when a timer was due:** it fires on next startup (it is now
  past-due, so it runs immediately).
- **Handler errors** are the handler's responsibility; a raising listener does
  not stop the scheduler.
- **Cancel of the in-flight timer** restarts the dispatch task so it re-selects.

## Scaling

Single-process today (SQLite + an in-process `asyncio.Event`). For multiple
processes/shards, the same table works with a coordination signal instead of the
in-process event — e.g. Postgres `LISTEN/NOTIFY` or a Redis pub-sub — so a writer
in one process can wake the scheduler in another. No table/handler changes
needed; only the "wake" mechanism.

## Rationale

Precise (sleeps to the deadline), cheap (one idle task), durable (DB-backed), and
generic (event dispatch) — the pattern larger bots converge on, without external
infrastructure at current scale.
