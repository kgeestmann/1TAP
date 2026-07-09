# Moderation

- **Status:** Stable
- **Last updated:** 2026-07-09
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

Assigns the configured muted role (`member.add_roles`). Indefinite — cleared
with `unmute`. The `duration` argument is ignored in this mode. Requires the
muted role to be configured and below the bot's top role, and the bot's **Manage
Roles** permission.

### Duration parsing

`parse_duration` accepts one or more `<number><unit>` tokens where unit ∈
`s,m,h,d` (e.g. `1h30m`). Invalid or zero durations raise a user-facing error.

## Unmute

`unmute` is strategy-agnostic and best-effort: it clears an active timeout **and**
removes the muted role if present. If the member is neither timed out nor holds
the role, it reports that nothing was done.

## Audit trail

Every successful action calls `repository.add_log(...)` (`kick` / `mute` /
`unmute`) and, if a mod-log channel is configured, posts a summary line there.

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
- Auto-expiry for role-mode mutes (scheduled unmute) if role mode needs
  time-limited mutes.
