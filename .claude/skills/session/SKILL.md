---
name: session
description: Bootstrap a solver or meta session for arc-workspace.
argument-hint: [solver|meta|meta end]
disable-model-invocation: true
---

Read `docs/wf-solver/*.md` in order.

Then dispatch on `$ARGUMENTS`:

- `solver` — read `programs/lib.dl`.
- `meta` — run `uv run python scripts/inspect-session.py` (no arg) and read output in full.
- `meta end` — close the meta session per the protocol in the docs.
