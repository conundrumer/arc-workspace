# d59b0160

## Departures
- `$FixedLegendSize` is a `@store` line on `parse.legend_extent`, named `parse.legend_extent=stored`, and not a constructor. The witness file's `larger-legend` is renamed to that id, and every group name changes with it. This rests on Write ("other than one that … stores a value the program derives") and Develop step 4: the concept derives the legend's extent on each axis from the divider L, and the branch stores it as 3.
- Witness `legend-other-corner`: `parse.legend_extent=stored` gives the input unchanged, where `witnesses.json` puts `$FixedLegendSize` in the `null` group. `witnesses.json` is wrong here. The model `analyze.md` gives the branch (a stored 3×3 box at `key_corner`, with the L beyond it not read) finds a legend at TL on this input: 0, 4, 1, 2. It keeps both panels, because neither holds all four, and it keeps the L piece too.
- Added branch `parse.legend_area=stored`, which is not in `analyze.md`. `store` printed it after `legend_found` was changed to require a legend box. Its witness, built by `store`, is train 0 turned a quarter turn clockwise. I judged it `variant $LegendAnyCorner` with `@relaxed legend-corner`: it is a D4 image of a train pair, the generator would pair it with the rotated train output (the legend read at TR), and it breaks `legend-corner` at `key_corner` TL.
- I named the concept constructors myself: `EveryColor`, `Adjacency4`, `PanelCells`, `StoredCorner`.
- The concept tests that the L is complete (`wall_gap`), and it is undefined where the legend's corner has no box with a divider on both axes. `analyze.md` states this only as "undefined on an input with no divider L at `key_corner`".

## Judgments
- Dropped under Fit, at train 0, with no constructor: `$ExactColorSet`, `$AnyLegendColor`, `$LegendLayoutMatch`. Also dropped: `background=DominantColor`, which fails at train 2, and `derive` reports no fitting derivation.
- Not formed: none of the three items states a single model, so no branch was formed from them.
- `walled=stored`: `store` first printed it, and its witness came from `legend_found` holding with a one-axis extent. That was a fault in the program: a legend is a box. Once `legend_found` read `legend_area`, `store` reports no witness for `walled`, so the branch is not held.
- Determine: the first version had `divider` and `key_corner` each reading the other's stored value, which is circular. `key_corner` now keeps the corners that some non-background color's L walls off in every input. `divider` keeps the colors whose L walls off `key_corner` in every input. `background` is the one color the changed cells become. `legend_need` is the count of legend colors, which is the same in every input. The plan also listed `key_corner` as "domain enumerable", and I wrote a relation for it too.
- Hints: the case-section hints came from `panel_box` reading `erased`; it now reads every panel. Pass-through `corner_of`: removed, and the clauses write `parse.corner` directly. Head-repeat on `parse.divider` in Determine: kept with `@ignore`, because the key names the candidate divider so each candidate gets its own parse. The long-clause finding and the Determine schema findings are fixed.
- Deletions removed: `wall_ray.cell` (`stop` does not read it), the legend-color atom in `shortfall.minus` (the plus side already keys the colors), and `legend_hits.domain` (a tally of 0 never reaches `legend_need`). Kept: the atoms that pair a corner with its own ray and axis, the `perp` atoms that cover non-square legends, the `corner`/`walled` atoms, `legend_found`, `corner_tie`, `background_defect`, and `legend_size.domain`. The pairs never exercise any of them, but each one is needed in general.
- Approximations: none; every claim has a relational form.
- Witnessed cases: 11 of 96. `witness` and `audit` are clean, and no check was skipped.
- Keywords: `objects markers select count bbox`.
- Performance: no issue; a run takes about 1 s.
- Procedure: I piped two `run_dl.py` outputs to another command (`store | head -40` and the final `audit | grep`), against "Reading files and outputs". The unpiped `audit` run just before the final one was clean.

## Unsettled
- `parse.legend_area=stored` stores grid positions, which are margin records of the 16×16 frame. On a witness grid of another size, its stored legend falls outside the grid, so its legend is empty and every panel, the L included, is erased. That follows from storing a cell set, but no line says whether such a frame-size-dependent store is a case or should be dismissed with `@ignore: store`. A handbook line on stored `Position` sets across grid sizes would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
