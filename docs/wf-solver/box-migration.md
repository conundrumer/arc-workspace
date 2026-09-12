# Box migration

The steps that remain of the Box change, `docs/wf-solver/proposals/Box.md`, for the session that runs them. The entry's Comps and Surface sections say what retires and what replaces it; this file says the order and the checks.

## Before acting

Check the handbook in the system context against the promoted lib. It shows the change when lib.dl's header states the Box algebra, the type block declares `Box` with `Position` and `Offset` as its readings, `ZERO` stands where `ORIGIN` stood, the inlines `relative`, `inside`, `interior`, `crop`, `box_edge`, `box_corner`, `box_extent`, the inset, outset, and offset constructors are declared, `Bbox` has a `box` readout with `// retired:` markers on the rest, and the comps read `OffsetInvariance`, `Outlines`, and `DividerTiles`. If any of these is missing, the session started before the handbook was rewritten: stop and ask the user to restart.

## State

Done, each as its own commit: the entry's rulings and delta survey; the promote (lib, docs, tooling, the retired-name lint); the rename classes, `ORIGIN` to `ZERO`, the constructors, `relative`/`inside`/`interior`, `Shift`/`Inset` to `Offset`/`Box`, the comp names, and `Bbox.margin`/`DirPack.pos` to `box`. The corpus runs green throughout, apart from 898e7135, which sits at the 5 s CPU limit on the committed baseline too and fails only under a full run's load.

`uv run python scripts/run_dl.py lint` lists what remains under `retired name`, one finding per use. At the last count, 587 findings in 314 files:

| Retired | Files | Replacement |
| --- | --- | --- |
| `BoxCells` | 33 | `box_edge`, `interior` |
| `MarginFrame` | 11 | an inset constructor or `DirPack`, then `crop` |
| `Reframe` | 18 | `relative`, or `crop` where the outer is a box |
| `Bbox.inside`, `Bbox.grid` | 57 | `inside` over the caller's own domain |
| `Bbox.edge_cell`, `Bbox.corner` | 23, 15 | the set's cells beside `box_edge`, `box_corner` |
| `Bbox.edge_min` | 23 | `dist` on `box` |
| `Bbox.extent`, `Bbox.extents` | 17, 22 | `box_extent` against a named frame cell |
| `BoxFrame` | 189 | `Bbox`, then `crop` |

## The batches

Each batch is one `migrate` spawn followed by one `cleanup` spawn, both as the `handbook` agent with the role text from `.claude/roles/` and the brief after it, then a run of the batch's solvers and a commit. A batch is about ten files. The order goes from the exact retirements to the ones that need judgment:

1. `BoxCells`. `on_edge(K, P, D)` is `box(K, B), cell(K, P), box_edge(P, B, D)` verbatim, and `hole` is `interior`. The `Outlines` instances feed these, so they are in this batch.
2. `MarginFrame`. A uniform or one-sided width is an inset constructor; 4522001f and 5daaa586 feed four per-edge scalars and keep `DirPack`.
3. `Reframe`. A box outer is `crop` where the site tests coverage and `relative` where it seats; an anchor-cell outer is `relative`.
4. The `Bbox` readouts, `inside` and `grid` first, then `edge_cell` and `corner`, `edge_min`, `extent` and `extents`.
5. `BoxFrame`, in three sub-batches: instances fed `cell` only, which read the set in its own frame (`set(K, P), bbox.box(K, B), crop(P, B, P_in)`); instances fed `grid`, which crop (`in(P, _), bbox.box(K, B), crop(P, B, P_in)`); and the reads that wildcard the cell, which add the domain atom the instance had.
6. The negated reads, last: each wraps a local relation over the site's own domain, the idiom style.md gives for an inline under negation. `grep -nE "!\s*[a-z_.]+\.(inside|inner|view|edge_cell|corner|on_edge|hole)\(" programs/solvers/*.dl` lists them.

The migrate brief names the entry's path, the sites (file, relation, line), and a time: the time of the newest commit on `programs/solvers`, since the role skips a file newer than that time and the rename commits touched most files. The cleanup brief names the regions the migrate report changed and the primitives they now call. The migrate role's rule holds throughout: what each site derives stays the same, and a replacement that narrows or widens it is restored.

Reimplementations the surveys met, to fix when their files are open: 212895b5 `Parse.seed`, 4290ef0e `paint`, 42918530 `outline`, 4e469f39 `gap`, 78332cb0 `port` (an `inner` read beside `dist(_, D, 0)`: `box_edge`); 4c177718 `placement`, 6cbe9eb8 `obox` (`inner` beside a corner test: `box_corner`); 3eda0437 `Parse.box_ink` and `Parse.hole_cell`, 8698868d `core.cell`, 8f215267 `view.cell`, 84f2aca1 `region` (a hand-written `inside` or `interior`).

The console stays idle from the first batch to the closeout: its workers edit `programs/solvers` in place and its commit stages that directory, and 284 of the files in scope are drafts.

## Closeout

1. Remove the retired comps and readouts from lib.dl, with their `// retired:` markers, and the `_inside`/`_interior` wrappers if no lib comp body reads them.
2. Remove the retired-name lint (`RETIRED_CAT`, `_retired`, `_retired_uses` in `src/dl/lint.py`) and its three tests.
3. Rewrite the `BoxFrame` example in `docs/souffle-undocumented.md` on `Bbox` and `crop`.
4. Re-read the entries the Box entry's Related line names, and note in each what the change does to it.
5. Move `docs/wf-solver/proposals/Box.md` to `docs/wf-solver/box.md` as the record of the change; do not delete it.
6. Delete this file.
