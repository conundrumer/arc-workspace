---
name: session
description: Bootstrap a solver or meta session for arc-workspace.
argument-hint: [solver|meta|meta end]
disable-model-invocation: true
---

Read all the docs in `docs/wf-solver`:
- `0-meta-process.md`
- `1-meta-session.md`
- `3-principles.md`
- `4-style.md`
- `5-session.md`
- `6-patterns.md`
- `7-proposals.md`

Then dispatch on an exact keyword match for `$ARGUMENTS`:

- `solver` — read `programs/lib.dl`, then run `bash scripts/queue.sh` to get the next queued solver and begin working it per the session cadence.
- `meta` — run `uv run python scripts/inspect-session.py` (no arg) and read output in full.
- `meta end` — close the meta session per the protocol in the docs.

Any other `$ARGUMENTS` is an ordinary working request — do not infer a session type and do not run any bootstrap. Proceed with the task using the docs above as context. A meta or solver session is something the user declares with a keyword, never inferred from prose.
