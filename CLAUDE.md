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
  lib.dl           Souffle primitives (types, body relations, Consts helpers)
  lib_functors.cpp C++ functors backing lib.dl's dispatch/projection primitives
  solvers/<id>.dl  per-task Souffle solver
  run_dl.py        run Souffle solvers (all or one); auto-builds lib_functors
scripts/
  materialize.py writes data/tasks/
data/
  upstream/      arc-agi-1 + arc-agi-2 pinned submodules
  patches/       <id>.arcpatch canonical; <id>_A.arcpatch, <id>_B.arcpatch, <id>_C.arcpatch variants
  tasks/         materialized JSON (build artifact)
docs/
  wf-solver/            workflow docs for solver and meta sessions
  arcpatches.md          .arcpatch format: file layout, verbs, variants, alts
  hardware-probe.md      dev machine specs
```

## Commands

```
uv run pytest -q
uv run python scripts/materialize.py
uv run python programs/run_dl.py          # run all Souffle solvers
uv run python programs/run_dl.py <stem>   # run one
```

Souffle binary required for `.dl` solvers (`brew install souffle`).

## Conventions

- **Patches are the source of truth** for corrections. `data/tasks/` regenerates from them via `scripts/materialize.py`. Upstream is pinned via submodules; corrections live in patches, not in `data/upstream/`.
- **Type aliases use the `type` keyword** (PEP 695, native to 3.12).
- **Keep `README.md` in sync** with anything human-facing: setup steps, layout, editor tooling, doc index. It's the human entry point; this file is the Claude entry point. Don't duplicate Claude-only conventions into the README.
