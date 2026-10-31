# ff805c23

## Departures
- `$FoundCenter` is a narrower model than the one in `analyze.md`. Here, a candidate center is the center of a square frame that lies inside the grid and holds the mask. The images are taken within that frame, and the D4Map check reads only the visible cells of the frame. In `analyze.md`, a candidate is any center, and the images are any images that fall in the grid. On `broken-symmetry-two-copies`, the model in `analyze.md` gives the grid with the 8 at (14,7). The solver's `$FoundCenter` finds no frame there and is undefined. `record --all` recorded the solver's output: the program states centers with Box margins, and no lib relation gives the center of a cell pair. One attempt allowed non-square frames for groups that keep each axis. That attempt timed out on every witness (progress note), so the square form stays.
- `$StoredCenter` and `$StoredOutSize` are not cases. `analyze.md` gives both as stored values of derived quantities (the center, and the output size). `store` gives no line for either one: `center` is "no witness: no D4 image or color swap of a train input changes the value", and the mask's cells stand at another place on each input. Each one is marked `@workaround` at the relation it would store, and their names were taken out of the witness groups.
- The witness `$StoredOutSize` was removed. After its `$StoredOutSize` group was taken out, every case gave one grid on it, so it separated nothing. The witness `$StoredCenter` was renamed `top-left-pattern`, and its `separates` text was rewritten to name the found center in place of the stored one.
- Added witness `stray-corner-cell`: train1 with (0,0) changed to a new color 9. This witness separates `$StoredColor & mask_color=RarestColor` from `$MaskBySolidBlock`. Before it, `witness` reported that no witness separated that pair. On it, RarestColor takes 9 as the mask and gives `0`, and the solid-block derivation takes both 1 and 9 and is undefined.
- `Determine` derives `mask_color` as each color that every input holds and no train output holds. `determination-plan` asked for this because RarestColor covers the value.
- `symmetry` is not an open parameter: no alt of the task accepts more than one of its values, so a case reads both and is undefined where they disagree.

## Judgments
- `TiebreakResolution` is `About {b}` or `Through {b, d}`. With it, `$FoundCenter` gives one grid per qualifying center, and `$BlockImage` gives one grid per element of the group. The concept writes `$About(ZERO)`, so it gives one grid.
- `stray-corner-cell`: plausibility `foreign`, because a stray cell breaks `symmetric-pattern`. Verdict `concept`, because the 9 is not an image of any 1 cell, so the 1 block restores as it does in train1.
- `@ignore: head-zero` on `center`: the frame of the grid-center case is the grid itself, which is `ZERO`, and no relation measures it.
- The common-subexpr hint on `frame_sym.src` and `frame_sym.dst` was resolved with the shared relation `frame_cell`.
- `deletions`: the `restoration_choice` enumerator was removed, because the head's constructor fixes the branch. Also removed: `color_box.box` in `masked`, `axis_of` in `cand_frame`, and the column `cand_image.p2`. `perp_dir` stays because it states the second axis.
- `@keywords` follows the 67b4a34d family: `symmetry crop repair occlude latent-canvas`.

## Unsettled
- `deletions` ran before the last simplifying edits, which removed atoms that `deletions` had listed. The marker rename came after it too. A `deletions` run on the current file would settle whether anything else can go.
- `determination-plan` lists `symmetry` as undecided: no clauses read it, and the train pairs also admit SYM_HT, SYM_DG, SYM_X and SYM_C4. A determination clause that keeps only groups holding both midline mirrors would settle it.
- `$StoredCenter` and `$StoredOutSize` (`@workaround`): a `store` line for a center stored in absolute coordinates, or for the output size, would settle them. Each needs a derived relation that `store` can report.
- `$FoundCenter` on frames that are not square or that reach past the grid: an encoding fast enough to enumerate those frames would settle whether it matches `analyze.md` on `broken-symmetry-two-copies`.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
