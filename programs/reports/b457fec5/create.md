# b457fec5

## Departures
- `$KeyLexOrder` is defined on a key that is not a straight line, and the Analyze file makes it undefined there. On the witness `background=DominantColor` (background 7 against the stored 0), `$KeyLexOrder` paints the trail 7 where the Analyze file gives undefined: this rests on the `@store` branch `key_axis=stored`. With a line check that reads `key_axis`, `$KeyLexOrder` is subsumed by `$KeyLexOrder & key_axis=stored`, because no value of `key_axis` in Θ separates the two, so the check would only remove the branch's own case. The reading order itself is defined on any set of key cells.
- On `trail-recolored`, the concept case gives the input unchanged, and the Analyze file gives undefined: with the stored shape color 5 the input has no trail, `step-paint` paints nothing, and `keep-rest` keeps every cell. No claim makes the model undefined on an input with no trail. The witness still separates the concept from `$ShapeColorBulk`.
- Added the `@store` branch `key_axis=stored` on `key_axis`, the axis the key lies along, with `// @store: variant background=DominantColor`, `@relaxed background`. Its witness `key_axis=stored`, which `store` built, is train 1 with colors 0 and 2 swapped. The concept is undefined there, `$PhaseFromHead & key_axis=stored` paints the trail 2, and the generator pairs the output of `background=DominantColor`. The concept key order reads `key_axis` because `key-line` puts the key along the axis of `key_start`, so the concept is undefined on a key off that axis, as the Analyze file makes it.
- Named the concept branches `$HeadDir`, `$KeyFromStart`, `$PhaseFromHead`, `$FarStep` and `$ShapeStored`.
- `$HeadNearKeyLine` measures an end square's distance to the key's line on the trail's cells along the box edge at that end, perpendicular to the key's axis. Only step 0 or step T reaches that edge, so those cells span the end square's lines across the key's axis, and the distance is the same one the Analyze report gives.
- Added the witnesses `key-from-right` and `key-axis-vertical` to the witness file. They resolve the pairs that `witness` reported, as stated under Judgments.

## Judgments
- `lex_corner` and `lex_axis` are not open, though the sweep says the pairs also admit `DIAG_BL` and `AXIS_H`: `$KeyLexOrder` claims reading order, which fixes the top-left corner with rows first. No reader of that claim takes a different corner or primary axis.
- Witness `key-from-right` resolves the report that no run shows `$KeyFromStart & key_axis=stored` defined and differing from `$KeyLexOrder`. Its input is the left-right mirror of an ordinary input (key 4 3 1), at `key_start` DIR_R. Plausibility `variant`: a mirrored variant task stores DIR_R. Verdict `concept`: the key is read from the right, so the head stripe is 1.
- Witness `key-axis-vertical` resolves the report that no run shows `key_axis=derived` defined and differing from `key_axis=stored` under `$CycleFromTail`. Its input is ordinary (key 1 3 4, a 3×3 square sliding 2 steps), at `key_axis` AXIS_V. Plausibility `ordinary`, verdict `concept`: the derived cases paint the trail, and the stored ones find no key along the axis of `key_start`.
- Each item under the Analyze report's Not formed fails Fit, for the reason that report gives, so no case was added for any of them.
- `derive` lists only `background` / `DominantColor`, which stands as the `@derive` line the Analyze report gives. `$ShapeColorBulk` matches no built-in derivation, so it keeps its constructor.
- Determine derives `head_dir` from the train outputs. A trail end is a head when the output color changes one step inward along the diagonal, because the far square is solid. The direction shared by every head corner is `head_dir`. The plan needed one parameter determined to bring the enumeration under its limit. `head_dir` was the one with a principled derivation: `lex_corner` and `lex_axis` have none, and `key_start` is tied to the head corner. The trail parse moved into `Parse<Key>`, which the program and Determine share.
- Deletions:
    - Removed the atoms that other atoms imply: `diag_opposite` in the `$HeadNearKeyLine` head corner (the only other end corner with an `end_gap` row is the opposite one), `impl_choice` in the `$FarStep` paint clause (every `$FarStep` combination is a case), and `ex_out` in Determine's `parse.cell` (`head` reads `ex_out`).
    - Kept the structure that the pairs never use: `head_key.i` (T per trail under `$CycleFromTail`), `bulk_clash`, the line check in `key_seq.elem`, `parse.trail.label` in the paint clauses (multi-trail inputs), `params.shape_color` in Determine, and `head(_, _)` in `head_dir`.
- Lint hints:
    - The case-section hints came from shared clauses that stood under a `// --- concept ---` marker. Those clauses now stand above the case markers.
    - The common-subexpr hint between `head_dist` and `slide` was resolved by the shared relation `trail_cell`.
    - The hint on the two `$TailLastColor` paint clauses was resolved by one clause with a disjunction.
- Keywords `objects markers chain walk bbox`:
    - `objects`: the trails are components.
    - `markers`: the key fixes the colors.
    - `chain`: the key is read in order along its line.
    - `walk`: the color is a walk around the key cycle, one step per slide step.
    - `bbox`: the distances are read in the trail's box.
- `min(u, v, T)` and T are least values from `Extremes`, and `mod K` is a walk around the key's cycle (`CycleWalk`). `$CycleFromTail` walks the reversed cycle T steps back from the last color to get the head's color.
- Performance: every command finished in under 15 s, and the solver runs in 1–2 s.

## Open
- `store` lists `key_off_axis` as stored already by `lex_axis`, only because both hold AXIS_V on every input. That line kept `store` from printing a `@store` line to add for `key_off_axis`. A survey that matches a derived relation to a parameter by meaning would settle whether `key_off_axis` needs a branch (ticket filed).
- The solver has 9 witnessed cases. `$CycleFromTail & $TailLastColor` is excluded from `impl_choice`, as the Analyze report gives it the model of `$CycleFromTail` alone.

## Lib
- The axis a cell set lies along, where every two cells of the set share a line of that axis. Solver-local form:
  `key_off_axis(S, A) :- key_cell(S, P), key_cell(S, Q), perp(A, A_x), axis_of(D, A_x), !same_dist(D, P, Q).`
  `key_axis(S, A) :- key_cell(S, _), axis_elem(A), !key_off_axis(S, A).`
  A keyed comp `LineAxis<Key>`, with input `cell(key, p)` and output `axis(key, a)`, would state it. Grep site: `programs/solvers/12997ef3.dl` lines 34–41 (`off_axis`, `layout_axis`, the axis the markers spread along).

## Fixes elsewhere
none

## Tickets filed
- 10-301_task_b457fec5_create.md
