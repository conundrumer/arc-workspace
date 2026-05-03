# arc-workspace

ARC-AGI-2 work for the 2026 Kaggle competition. Python 3.12, `uv`.

## Layout

```
src/arc/
  patch.py       DSL parser (grammar in module docstring)
  task.py        Task / Example / Alt
  apply.py       apply_patch with assertions
  upstream.py    load v1-preferred upstream
  materialize.py compose upstream + patches → file dict
  jsonio.py      custom JSON formatter
scripts/
  materialize.py writes data/tasks/
data/
  upstream/      arc-agi-1 + arc-agi-2 pinned submodules
  patches/       <id>.arcpatch canonical; <id>_A.arcpatch, <id>_B.arcpatch, <id>_C.arcpatch variants
  tasks/         materialized JSON (build artifact)
docs/
  variants-and-alts.md   variant A/B/C and alt rule/tiebreak semantics
  hardware-probe.md      dev machine specs
```

## Commands

```
uv run pytest -q
uv run python scripts/materialize.py
```

## Conventions

- **Patches are the source of truth** for corrections. `data/tasks/` regenerates from them via `scripts/materialize.py`. Upstream is pinned via submodules; corrections live in patches, not in `data/upstream/`.
- **Type aliases use the `type` keyword** (PEP 695, native to 3.12).
