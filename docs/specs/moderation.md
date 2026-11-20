# Moderation

- **Status:** Stable
- **Last updated:** 2026-11-20
- **Code:** [`modules/moderation.py`](../../modules/moderation.py)

## Purpose

Provide moderator actions (`kick`, `mute`, `unmute`) with consistent safety
checks, error handling, configurable mute behaviour, and an audit trail.

## Scope

- The `kick`, `mute`, and `unmute` commands (slash and prefix).
- Role-hierarchy safety checks shared by all actions.
- The two mute strategies and how `unmute` reverses either.
- Writing each action to the moderation log.

### Non-goals

- Storage of logs and config (see [database.md](database.md)).
- Configuring the log channel / mute mode / muted role (see
  [configuration.md](configuration.md)).

## Commands

Every command is available as both `/command` and `!command`, guild-only.

| Command | Permission (invoker) | Arguments | Behaviour |
| ------- | -------------------- | --------- | --------- |
| `kick` | Kick Members | `member`, `reason?` | Kick the member. |
| `mute` | Moderate Members | `member`, `duration?`, `reason?` | Mute per the server's mute mode. |
| `unmute` | Moderate Members | `member`, `reason?` | Reverse a mute (timeout and/or muted role). |

Slash responses to failures are ephemeral; successes are visible.

## Safety: hierarchy checks

Before any action, `check_hierarchy(guild, author, target)` rejects the request
if the target is:

- the invoker themselves,
- the bot,
- the server owner,
- someone whose top role is **≥** the invoker's (unless the invoker is the
  owner), or
- someone whose top role is **≥** the bot's top role (the bot cannot act on
  them).

This prevents a moderator from acting on peers/superiors and gives a clear
message instead of a Discord `Forbidden` error.

## Mute strategies

The active strategy is the guild's `mute_mode` ([configuration.md](configuration.md)).

### `timeout` (default)

Uses Discord's native timeout (`member.timeout`). Duration is parsed from the
`duration` argument (e.g. `10m`, `2h`, `1d`, `30s`); default **1 hour**, maximum
**28 days** (Discord's limit). Discord enforces and auto-expires it. Requires the
bot's **Moderate Members** permission.

### `role`

Assigns the configured muted role (`member.add_roles`). Requires the muted role
to be configured and below the bot's top role, and the bot's **Manage Roles**
permission.

- **Without `duration`:** indefinite — cleared manually with `unmute`.
- **With `duration`:** the mute is recorded in the `active_mutes` table with an
  expiry time, and a background task removes the role automatically when it
  elapses (see *Auto-unmute* below).

> The muted role only actually restricts a member if it has deny permission
> overwrites in the channels. `/config setupmuterole` creates those; a role set
> via `/config muterole` must already have them, or the mute is cosmetic.

### Auto-unmute (timed role mutes)

Timeout-mode mutes expire natively in Discord. Role-mode mutes with a duration
are expired via the **[Scheduler](scheduler.md)**, not a poll loop:

- On a timed role mute, moderation calls `scheduler.create_timer("unmute", …)`
  with `{guild_id, user_id, role_id}`.
- When it fires, the scheduler dispatches `on_unmute_timer_complete`; the
  moderation cog's listener removes the role, logs the `unmute` (moderator = the
  bot, reason "duration expired"), and posts to the mod-log channel.
- If the member has left or no longer has the muted role, nothing is logged.
- **If removing the role fails** (e.g. the role was moved above the bot's), the
  listener schedules a retry timer `UNMUTE_RETRY_DELAY` (10 min) later, tracking
  `attempt` in the payload. After `UNMUTE_MAX_ATTEMPTS` (3) it gives up and posts
  an "Auto-unmute failed" embed to the mod-log asking for manual removal. A
  failed unmute is never logged as successful.
- Timers are DB-backed, so pending unmutes **survive a restart**.
- `unmute` and re-muting a member both `cancel_timer(...)` first, so there is at
  most one pending auto-unmute per member.

### Duration parsing

`parse_duration` accepts one or more `<number><unit>` tokens where unit ∈
`s,m,h,d` (e.g. `1h30m`). Invalid or zero durations raise a user-facing error.

## Unmute

`unmute` is strategy-agnostic and best-effort: it clears an active timeout **and**
removes the muted role if present. If the member is neither timed out nor holds
the role, it reports that nothing was done.

## Messages

**No pings, ever.** Both the command reply and the mod-log use **usernames**, not
mentions, and every send sets `allowed_mentions=none` as a safety net. Members
are often not pingable in the log channel, and pinging on every action is noise.

- **Command reply** — a compact line via `announce()`:
  `ryan.tf was muted by tannies for 1m (reason: spam).`
- **Mod-log channel** — a rich embed via `build_log_embed()`:
  - title + colour per action (kick red, mute orange, unmute green),
  - target avatar thumbnail,
  - fields: Member (`username` + `id`), Moderator, Duration (if any), Reason,
  - footer: `User ID: <id>` and a timestamp.

Usernames are markdown-escaped (`user_label`) to avoid formatting injection.

## Audit trail

Every successful action calls `repository.add_log(...)`, which records the
**action** (kick/mute/unmute), target, moderator, reason, and timestamp in the
`actions` table. The reason is also written to Discord's server audit log. The
row's id is an internal reference only — it is **not** shown in messages.

## Edge cases & error handling

- **Missing permission / role too high / API failure:** each action catches
  `discord.Forbidden` and `discord.HTTPException` and returns a specific message
  rather than throwing.
- **Role mode without a muted role:** returns a hint to run `/config setupmuterole`.
- **Timeout > 28 days:** rejected with a clear message.
- **Command used in DMs:** blocked by `guild_only`.
- Invoker-permission failures surface through the global app-command / command
  error handlers in `bot.py`.

## Rationale

Native timeout is the modern default (no role or channel overwrites to manage);
role mode remains for servers that want a customised, persistent mute. A shared
hierarchy check and explicit API-error handling make every action safe and
predictable, and a uniform audit trail supports accountability.

## Future work

- `ban` / `unban`, `warn` (+ `warnings` listing), and `purge`.
- Optional DM to the target on mute/kick (with reason).
