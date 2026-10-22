# baf41dbf

## Departures
- Witness `marker_color=RarestColor`: the Analyze file's tie input stands in the witness file as `marker-color-tie`, with the Analyze file's text. The Analyze file gives two grids there, one per derived color. The runner gives `marker_color` both derived values (3 and 6) in one run, and the program reads `marker_color` as a set of colors. A marker is a cell of that set outside the input frame's box, so the frame's cells are not markers, and the case gives the concept's grid alone, the output of `marker_color=stored`.
- Witness `marker_color=RarestColor` in the witness file: a 2x2 frame and five markers, so 3 alone is rarest. The derived marker color marks no cell, and the frame stays where it is. Judged borderline concept, as the `@derive` line gives: a 2x2 frame has no inside, unlike every frame of the pairs.

## Judgments
- The concept's new box is one move of the input frame's box. Each side takes the least distance from its edge among the lines that the markers beyond it pull it to (`Extremes.low`), and `DirPack` assembles the box.
- `$InLineMarkers` repeats the moves until no side moves. For this, the program enumerates every box whose sides stand at the frame's own margins or at a marker's pull line. Then it computes one move from each such box, closes the moves from the input box with `Propagation<Pick, Box>`, and takes the reached box that a move leaves unchanged. This form uses no recursion in the solver's clauses, and it gives `$InLineMarkers & $NearestMarker` a relational form. With the nearest pick, the moves are not monotone, so a closure over markers cannot state that case.
- `impl_choice` leaves out `[$Beyond, $NearestMarker, _]`: `$NearestMarker` alone fails Fit at test0 (Analyze report). `$InLineMarkers & $EnclosedMarkersCleared` and `$InLineMarkers & $NearestMarker & $EnclosedMarkersCleared` stay in `impl_choice`. Every verdict on `$InLineMarkers` and on `$EnclosedMarkersCleared` is `concept`, so those cases are not witnessed, and the runner checks six witnessed cases.
- Branches with no constructor: `$InLineOnce`, `$DividerKeepsNearSideDistance`, `$DividersKeepLength` and `$OldOutlineKept` fail Fit (Analyze report), and none has a witness. The derivations `background=RarestColor`, `background=SharedColor`, `marker_color=DominantColor`, `marker_color=SharedColor` and every `frame_color` derivation fail Fit, and `derive` does not list them.
- Not formed (Develop step 3): no case was added from these items. Content inside the frame states no model. The frame that moves instead of stretching fails train0. `derive` lists no derivation of `marker_gap`. The proposers that read `ex_out` are undefined on every pair.
- `@derive DominantColor` on `background` and `@derive RarestColor` on `marker_color`: borderline concept, as the Analyze report gives them. `store` lists no `@store` line to add.
- Determination: the sweep gives one value for each parameter. The plan asked for determination relations for `background` and `marker_color`, the values a proposer derives from cell counts. `Determine.background` reads the color that the old outline's cells take in the output. `Determine.marker_color` reads the input colors other than `frame_color` and `params.background`. That clause reads `params.background`, not `Determine.background`: the hint said a test that reads facts of both inputs and outputs must not choose the value. The plan leaves `frame_color` and `marker_gap` covered by the pairs, and no proposer gives either of them.
- Deletions that changed nothing, kept: the `a` columns of `broken` and `divider` (they name the line's axis, which keeps a line identity on a degenerate grid); `!kept` in the drawn-cell `out` clause (a nearer marker can stand on the new outline, and `markers-stay` keeps it); the old-frame, cleared-marker and rest-of-grid disjuncts and their atoms (the pairs have no enclosed marker and no other color in the field); the `d` column of `side_margin`, and the `opposite`/`perp_dir` atoms in `state` (they assemble each candidate box from one margin per side); `!inside` in the `$EnclosedMarkersCleared` clause (witness `two-markers-one-side` needs it).
- Deletions applied: `params.frame_color(Col)` in `divider` (`!broken` already implies it), `frame.box` in the `$Beyond` `box` clause (`state($Beyond(), _)` holds only the frame's box), and the first `beyond` atom in `off_line`.
- Performance: the `$InLineMarkers` state space grows as (markers + 1)^4 boxes. With the task's inputs it has at most a few hundred boxes, and each run takes about 1 s. In the deletion run, the variant that drops `params.marker_color` from `mark` timed out, because every cell then counts as a marker.
- Keywords `markers span bbox border lines rank walk`: `walk` covers the repeated moves of `$InLineMarkers`.
- No lint hint is left. The case-section hints about `state` and `side_margin` were fixed by keying `beyond` on `Side`.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
