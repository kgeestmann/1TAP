# 1TAP Documentation

This is the documentation hub for 1TAP. It is written for contributors and
future maintainers — it explains not just *what* the bot does, but *why* it is
built the way it is.

## Map

| Document | What it covers |
| -------- | -------------- |
| [architecture.md](architecture.md) | System overview, layering, data flow, and the key technical decisions with their rationale. |
| [specs/](specs/README.md) | Per-subsystem specifications. One focused spec per component. |

## How the docs are organised

- **Architecture** is the top-down view: how the pieces fit together and why.
- **Specs** are the bottom-up view: each subsystem (logging, database,
  configuration, moderation, …) gets its own self-contained spec. New features
  add a new spec rather than growing one monolithic document.

See [specs/README.md](specs/README.md) for the spec index, the conventions every
spec follows, and the [`_template.md`](specs/_template.md) to copy when writing a
new one.

## Keeping docs honest

Documentation is part of the change, not an afterthought:

- A change that alters behaviour updates the relevant spec **in the same commit**.
- A new subsystem ships with its spec.
- If a spec and the code disagree, the code is the source of truth — fix the spec.
