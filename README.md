# arc-workspace

ARC-AGI-2 work for the 2026 Kaggle competition. Python 3.12, `uv`.

## Setup

```sh
uv sync
uv run pytest -q
```

## Layout

```
src/arc/         core library (patch DSL parser, task model, materializer)
scripts/         CLI utilities
data/upstream/   pinned arc-agi-1 + arc-agi-2 submodules
data/patches/    .arcpatch corrections (canonical + variants A/B/C)
data/tasks/      materialized task JSON (build artifact, checked in)
tools/           dev tooling (VSCode extension)
docs/            design notes
```

Corrections live in `.arcpatch` files, never in `data/upstream/` — upstream stays pinned to the published datasets.

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

## Docs

- [`docs/variants-and-alts.md`](docs/variants-and-alts.md) — variant A/B/C and alt rule/tiebreak semantics
- [`docs/datalog-lite.md`](docs/datalog-lite.md) — Python style for relational derivations
- [`docs/hardware-probe.md`](docs/hardware-probe.md) — dev machine specs
