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
  lib.py           Python primitives for solvers
  lib.dl           Souffle primitives (types, body relations, Consts helpers)
  solvers/<id>.py  per-task Python solver
  solvers/<id>.dl  per-task Souffle solver
  run.py           run Python solvers (all or one)
  run_dl.py        run Souffle solvers (all or one)
scripts/
  materialize.py writes data/tasks/
data/
  upstream/      arc-agi-1 + arc-agi-2 pinned submodules
  patches/       <id>.arcpatch canonical; <id>_A.arcpatch, <id>_B.arcpatch, <id>_C.arcpatch variants
  tasks/         materialized JSON (build artifact)
docs/
  wf-solver/            workflow docs for solver and meta sessions; read at session start
  arcpatches.md          .arcpatch format: file layout, verbs, variants, alts
  hardware-probe.md      dev machine specs
```

## Commands

```
uv run pytest -q
uv run python scripts/materialize.py
uv run python programs/run.py             # run all Python solvers
uv run python programs/run.py <task_id>   # run one
uv run python programs/run_dl.py          # run all Souffle solvers
uv run python programs/run_dl.py <stem>   # run one
```

Souffle binary required for `.dl` solvers (`brew install souffle`).

## Sessions

Solver session: user opens with `SESSION START`.
Meta session: user opens with `META SESSION START` and closes with `META SESSION END`.
In both, bootstrap by `cat docs/wf-solver/*.md` to read the workflow docs in order. For meta sessions, also run `uv run python scripts/inspect-session.py` (no arg) to load the multi-session window — read the output in full, no truncation. Pass a session-id to inspect one specifically.

## Conventions

- **Patches are the source of truth** for corrections. `data/tasks/` regenerates from them via `scripts/materialize.py`. Upstream is pinned via submodules; corrections live in patches, not in `data/upstream/`.
- **Type aliases use the `type` keyword** (PEP 695, native to 3.12).
- **Keep `README.md` in sync** with anything human-facing: setup steps, layout, editor tooling, doc index. It's the human entry point; this file is the Claude entry point. Don't duplicate Claude-only conventions into the README.
