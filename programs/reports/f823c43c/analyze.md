# f823c43c

## Concept
- The concept fits every pair (train0 at period 2 by 2, train1 and test0 at 3 by 3, noise_color 6; checked by `work/task/f823c43c/check_concept.py` and `probe.py`). It has relational form: the period is the componentwise-least period at which the visible cells of each tile place all agree, and each cell takes its place's color.
- The rule as the generator applies it: draw a wallpaper, scatter 6 over it, and pair the input with the clean wallpaper. The concept's rule recovers that wallpaper exactly when every tile place has a visible copy (`phase-visible`). It is undefined where a place is fully hidden, the generator still has an output there, and the `hidden-phase` point covers that case.
- No witness with verdict `other` is left that no branch lists.
- `$PeriodPerAxis` is subsumed by the concept. Where it is defined, its per-axis periods are class-consistent, and every class-consistent period is at least as long on each axis as the concept's least one, which the pairwise check also passes. So the two periods are the same.

## Choice points
- `noise-color`
    - `concept`: `noise_color` is stored, 6
    - `$NoiseByPeriod`: derives `noise_color` by clauses as the one color whose cells, left out, let the rest repeat with a period at most half the grid on each axis; replaces the stored `noise_color`; no parameters; undefined where no color or more than one color qualifies, fits every pair; witness `noise-of-another-color` (train1's input with its noise recolored 5), at the stored assignment; breaks `noise-overwrites` (no cell is `noise_color`); plausibility `variant`; verdict `$NoiseByPeriod`; it breaks the invariant that every input's noise is 6
    - `noise_color=RarestColor`: derives `noise_color` with RarestColor on the input alone; undefined where the rarest color ties; fails Fit at train1, where 8 (13 cells) is rarer than 6 (23 cells)
    - `noise_color=DominantColor`: derives `noise_color` with DominantColor on the input alone; fails Fit at train0, where it removes the background 8
    - `noise_color=SharedColor`: derives `noise_color` with SharedColor on the input alone, which gives every color of the input, so every cell counts as noise; undefined on every input, fails Fit at train0
- `restore`
    - `concept`: `restore-by-phase`, where each cell takes its tile place's color
    - `$RecolorToBackground`: replaces `restore-by-phase`, so each noise cell takes the input's commonest color and the period is never read; no parameters; defined everywhere; fails Fit at train0 (train0 input (1,8) is 6 and the output has 4 there)
- `period`: stands under the concept branch of `restore`, since `$RecolorToBackground` reads no period
    - `concept`: the period shortest on both axes among those at which the visible cells of each tile place agree (`periodic-pattern`)
    - `$PeriodPerAxis`: replaces how `periodic-pattern` finds the period. Each axis takes alone the least shift under which every two visible cells that far apart on a line agree. No parameters. Undefined where those periods leave a tile place whose visible cells disagree, or a place fully hidden. Fits every pair. Fails Subsumption: it is subsumed by the concept. Witness `chain-broken-by-noise` (9 by 9, half the cells noise): its row period comes out as 1, so it is undefined, and the concept restores the 3 by 3 tile. At the stored assignment; breaks no scene claim; plausibility `borderline`; verdict `concept`; it breaks the invariants that noise covers at most about a quarter of the cells (16% to 24%) and that grids are at least 12 on each side
    - `$PeriodStored`: stores the period, which the program derives, and replaces how `periodic-pattern` finds it. Parameter `period`. Fails Fit, since no one value fits both trains: at 2 by 2 it fails train1, and at 3 by 3 it fails train0
    - `period=Period`: derives a stored period with the Period proposer on the input alone, noise included; fails Fit at train0, where the noise leaves only the full grid (15 by 19) as period, so the input comes back unchanged
- `hidden-phase`: stands under the concept branch of `restore`
    - `concept`: undefined where a tile place has no visible copy (`phase-visible`)
    - `$HiddenPhaseKeepsNoise`: adds that a fully hidden tile place keeps `noise_color`; defined there; fits every pair; witness `tile-place-all-hidden` (6 by 6, every copy of the block's top-left cell hidden), at the stored assignment; breaks `phase-visible`; plausibility `borderline`; verdict `$IsometryOrbit`; it breaks the invariants that each tile place shows many visible copies and that grids are at least 12 on each side
    - `$HiddenPhaseTakesDominant`: adds that a fully hidden tile place takes the commonest non-noise color; defined there; fits every pair; witness `tile-place-all-hidden`, the same standing and verdict as above
    - `$IsometryOrbit`: replaces `restore-by-phase`, so each cell takes its orbit's color under the periods and under the D4 maps of the tile that some visible pair shows and none contradicts. Differs from the concept only on fully hidden places. Undefined where no such map reaches a hidden place. Fits every pair. Witness `tile-place-all-hidden`, the same standing as above, and verdict `$IsometryOrbit`: the mirror the visible cells show fills the block
- `noise-color` & `restore`, `noise-color` & `period`, `noise-color` & `hidden-phase`, `period` & `hidden-phase`: the two branches' changes applied together
- `restore` & `period`: `$RecolorToBackground`'s model alone, so the `period` point stands under the concept branch of `restore`
- `restore` & `hidden-phase`: `$RecolorToBackground`'s model alone, so the `hidden-phase` point stands under the concept branch of `restore`

## Open parameters
none

## Not formed
- Mode at each tile place in place of agreement: the concept's period makes every place's visible cells agree, so the mode is that one color. The model is equivalent.
- Recoloring only the noise cells in place of every cell: visible cells already hold their place's color, so the model is equivalent.
- ChangedColor, VanishedColor, ChangedPairs, VanishedNewPairs, OutNewColor and AnyOutNewColor as derivations of `noise_color`: each reads train outputs, and under `@derive` it reads one input and no output, so it derives no noise color.
- A motif-lattice reading (motifs placed on a lattice over the background): where every tile place is visible it gives the concept's output. Where a place is hidden it fills the background, which is `$HiddenPhaseTakesDominant`.
- A separator-and-tile (`decompose`) reading: train1 has no separator lines (its period-3 rows alternate between all 7 and a row with 8s), so it cannot parse train1.

## Tickets filed
- none
