# arc-workspace

ARC-AGI-2 work for the 2026 Kaggle competition. Python 3.12, `uv`.

## Setup

```sh
uv sync
uv run pytest -q
```

Souffle is required for the Datalog (`.dl`) solvers:

```sh
brew install souffle    # macOS; see souffle-lang.github.io for other OSes
```

The `.dl` solvers also need a C++ compiler; `run_dl.py` builds their functor
library automatically.

`scripts/queue.sh` requires bun to minify
TS sources before sizing them.

## Editor setup

The VSCode extension at `tools/vscode/arc-grids/` highlights grid digits in materialized task JSON with the ARC palette (bold) and adds syntax highlighting for the patch DSL.

Activate by symlinking the extension into VSCode's extensions directory:

```sh
ln -s "$PWD/tools/vscode/arc-grids" ~/.vscode/extensions/local.arc-grids-0.1.0
```

Then reload the window (`Cmd+Shift+P` → "Developer: Reload Window").

File associations and the digit color palette live in `.vscode/settings.json`. To swap colors, edit the `editor.tokenColorCustomizations.textMateRules` entries — digit scopes run `constant.numeric.arc.0` through `constant.numeric.arc.9`.

If highlighting doesn't appear after reload, check the language mode in the status bar — it should read `ARC Patch` or `ARC Task JSON`.

## Editing patches

Corrections live in `.arcpatch` files, never in `data/upstream/` — upstream stays pinned to the published datasets.

Patch editing needs the upstream submodules — the materializer composes fixes against them:

```sh
git submodule update --init
```

To start a new patch, scaffold a stub from the upstream task:

```sh
uv run python scripts/patch_stub.py <task_id>
```

This writes `data/patches/<task_id>.arcpatch` containing every train/test grid in patch column form, ready to hand-edit into a real patch.

After changing a patch, regenerate task JSON:

```sh
uv run python scripts/materialize.py
```

## Solver console

A local web console for batch solver work: launch `claude -p` workers in waves, review and commit their solvers.

```sh
uv run python tools/console/server.py
```

## Docs

- [`docs/arcpatches.md`](docs/arcpatches.md) — `.arcpatch` format: file layout, verbs, variants, alts
- [`docs/wf-solver/`](docs/wf-solver/) — solver work: principles, style, patterns, proposals, backlog. The session protocol lives in `.claude/skills/session/SKILL.md`.
- [`docs/hardware-probe.md`](docs/hardware-probe.md) — dev machine specs
