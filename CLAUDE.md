# arc-workspace

ARC-AGI-2 work for the 2026 Kaggle competition. Python 3.12, `uv`.

## Commands

```
uv run pytest -q
uv run python scripts/materialize.py
uv run python scripts/run_dl.py          # run all Souffle solvers; --help for per-solver tooling
uv run python scripts/run_dl.py <stem>   # run one
```

Souffle binary required for `.dl` solvers (`brew install souffle`).

## Conventions

- **Patches are the source of truth** for corrections. `data/tasks/` regenerates from them via `scripts/materialize.py`. Upstream is pinned via submodules; corrections live in patches, not in `data/upstream/`.
- **Type aliases use the `type` keyword** (PEP 695, native to 3.12).
- **Keep `README.md` in sync** with anything human-facing: setup steps, editor tooling, doc index. It's the human entry point; this file is the Claude entry point. Don't duplicate Claude-only conventions into the README.
