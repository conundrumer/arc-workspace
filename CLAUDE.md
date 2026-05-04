# arc-workspace

ARC-AGI-2 work for the 2026 Kaggle competition. Python 3.12, `uv`.

## Layout

```
src/arc/
  patch.py       DSL parser (grammar in module docstring)
  task.py        Task / Example / Alt; load(task_id) → materialized Task
  apply.py       apply_patch with assertions
  upstream.py    load v1-preferred upstream
  materialize.py compose upstream + patches → file dict
  jsonio.py      custom JSON formatter
programs/
  lib.py         types + primitives for solvers
  solvers/<id>.py  per-task solver
  run.py         run all solvers (or one) against materialized tasks
scripts/
  materialize.py writes data/tasks/
data/
  upstream/      arc-agi-1 + arc-agi-2 pinned submodules
  patches/       <id>.arcpatch canonical; <id>_A.arcpatch, <id>_B.arcpatch, <id>_C.arcpatch variants
  tasks/         materialized JSON (build artifact)
docs/
  solvers.md             entry point for solver work — relational style, principles, conventions
  wf-solver/            workflow docs for solver and meta sessions; read at session start
  arcpatches.md          .arcpatch format: file layout, verbs, variants, alts
  hardware-probe.md      dev machine specs
```

## Commands

```
uv run pytest -q
uv run python scripts/materialize.py
uv run python programs/run.py             # run all solvers
uv run python programs/run.py <task_id>   # run one
```

## Sessions

Solver work session: user opens with `SOLVER START`.
Meta session: user opens with `META SOLVER START` and closes with `META SOLVER END`.
In both, bootstrap by `cat docs/wf-solver/*.md` to read the workflow docs in order.

For meta sessions, `bash scripts/inspect-session.sh` renders previous sessions for inspection — pass a session-id to inspect one, no arg for the multi-session window since the previous meta session.

## Conventions

- **Patches are the source of truth** for corrections. `data/tasks/` regenerates from them via `scripts/materialize.py`. Upstream is pinned via submodules; corrections live in patches, not in `data/upstream/`.
- **Type aliases use the `type` keyword** (PEP 695, native to 3.12).
- **Keep `README.md` in sync** with anything human-facing: setup steps, layout, editor tooling, doc index. It's the human entry point; this file is the Claude entry point. Don't duplicate Claude-only conventions into the README.
