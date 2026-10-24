# d255d7a7

## Departures
- `$SharedHeading` and its witness `split-heading` are removed from the solver and the witness file. The branch fails Subsumption. `witness` found no run where it is defined and differs from `$OwnHandle`. Where every cup's handle gives the same heading, the shared heading is each cup's own heading. Where they differ, the branch is undefined. `analyze.md` says the same thing ("no witness where it is defined exists"). With the branch gone, the scene claim `same-facing` is no longer used and left the header.
- `cup_width=stored` is the constructor `$StoredWidth`, with `Params.cup_width(3)`, and is not a `@store` line. Its witness is renamed from `cup_width=stored` to `deep-cup`, and its group name to `$StoredWidth`. The value it stores is the cup depth, which the concept derives per frame component. Every relation that holds that value is keyed by a component `Ident`, and `store` reported no relation with one value on every input.
- A `@derive TileCount` branch on `cup_width` (variant, concept, `@relaxed cup`) and its witnesses `cup_width=TileCount` and `tiny-grid` are not in `analyze.md`. `cup_width` exists only because `$StoredWidth` is a constructor, and `derive` reports that TileCount fits it.
- The Params relation is named `background`, following the concept file's Parameters section. The concept branches are named `$BracketBox`, `$HandleEnd`, `$CupOnTop` and `$Spanning`.
- The text of `slide-to-handle-end` ends at "the handle's last cell". The concept file has "the grid edge where the handle ends", but `analyze.md` gives the concept branch of `landing` as the handle's last cell and makes the grid-edge reading `$EdgeLanding`.
- `background`, `cup-contents` and `loose-marks` are left out of the header. No `@claim`, `@relaxed`, rule text or branch reads them (Style, Header).

## Judgments
- `contents-reach` is a top-level `Choice` field, not nested under `carried`. `carried`'s only non-concept branch, `$BracketOnly`, fails Fit and has no constructor, so nesting it under `carried`'s concept branch is the same as placing it at the top.
- The failing branches `$MirrorContents`, `$BracketOnly`, `$Reflect`, `$KeepHandle` and the derives that do not fit have no witness in `analyze.md`, so they get no constructor.
- Neither item under Not formed states a single model that fits. A single stored slide direction fails Fit, and no model reads where the handle meets the cup. So Develop step 3 adds no branch.
- Every case uses the concept's cup reading. A cup cell is a piece cell whose line across the handle has piece cells on both sides of the piece's box. The slide direction is the side where the cup box stops short of the piece box (`!dist(B_rel, D, 0)`), and the slide distance is that margin.
- `$StoredWidth` finds the open side as the side of the piece box whose two corners both hold piece cells. It is undefined, with no cup, where the piece is not `cup_width` across.
- A piece that gets no heading leaves its cells without `out` facts, so the case is undefined there and does not echo the input.
- `cup_width=TileCount` witness: 5 × 10 grid with a 5-wide cup. Plausibility is `variant`, since a variant task can have wider cups; it is `@relaxed cup`. The verdict is `concept`: the generator slides the 3-deep cup to the handle end.
- `tiny-grid` witness: 4 × 4 grid. It is `borderline`, because the task's grids are 8 to 20 wide. The verdict is `concept`. It shows the stored `$StoredWidth` defined where `$StoredWidth & cup_width=TileCount` is undefined.
- Determination: `background` is the commonest color of every train output. `frame` is the commonest non-background color of every train input. `cup_width` is the box extent of each frame component of the outputs, read through a shared `Parse<Key, Piece>`; the program uses the same `Parse` for its pieces. The plan printed `no actions`.
- Deletions: the 14 deletions that change nothing all stay. `axis_of` and `params.cup_width` hold the claim's structure. The `handle` and `!parse.piece.label` atoms keep a piece that does not move undefined. The `$MarksOnTop` clauses are a branch the pairs never exercise. The defect relations state the universal over examples.
- No lint hint appeared. No performance issue appeared: every run finished within 16 s.
- `analyze.md` cites a probe, `work/task/d255d7a7/probe.py`, that does not exist. I checked the concept against the task pairs directly, and all four pass.

## Unsettled
- Whether the TileCount derive branch belongs in the corpus. It ties the cup width to how many tiles fit the grid's dimensions, which is a coincidence. It was held only because it fits. An `@ignore: derive TileCount` would need it to fail a case condition, and none failed here.

## Concept faults
- none

## Fixes elsewhere
- `docs/handbook/procedure.md`, Write step 2, the line "other than one that ... stores a value the program derives": it should also say that a value derived per object, keyed by an `Ident`, is held as a constructor, because `store` cannot report it.

## Tickets filed
- none
