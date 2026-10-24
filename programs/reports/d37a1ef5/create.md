# d37a1ef5

## Departures
- The solver adds `// @derive SharedColor: variant derived` (`@relaxed one-frame`) on `frame_color`, though `analyze.md` says `frame_color=SharedColor` fails Fit at train0: the runner's SharedColor proposer ("a color present in every input") gives every color of the input on a one-input run, and `derive` reports that it fits at the concept base. At 0 and 5 it closes off only single mark cells, which keep their box, so the pairs are unchanged. Its witness `frame_color=SharedColor` (train0 with 2 and 1 swapped) is recorded by `derive`.
- The witness file has one witness that witnesses.json does not have, `frame_color=SharedColor`. Its groups were rewritten by `record --all`, and `stray-mark-outside`, `broken-outline` and `empty-frame` had their names rewritten to the listed form. Run against witnesses.json, `witness --file` reports no difference.

## Judgments
- Each choice point that `analyze.md` gives a witness for is a field of a record `Choice`: `MarkSet` (`NonBackgroundMarks` / `$MarkColorStored`), `MarkScope` (`InteriorMarks` / `$GlobalMarksBox`), `Interior` (`EnclosedInterior` / `$InteriorByFrameBox`), `EmptyFrame` (`EmptyFrameFilled` / `$EmptyFrameKept`) and `FrameColor` (`StoredFrameColor` / `$FrameColorFromOutline`). The concept constructor names are my own. `impl_choice` holds all 32 combinations, and all of them pass every pair. The `kept-region` branches fail Fit and have no witness, so they get no constructor.
- `$FrameColorFromOutline` derives its color in program clauses, not by a built-in derivation, so it is a constructor. `background=DominantColor` and `mark_color=RarestColor` are `@derive` lines, with the plausibility and verdict `analyze.md` gives.
- `Closed`, `Bbox` (frame box) and the `wall`/`frame`/`mark` relations are keyed by a `Wall = [f: FrameColor, c: Color]` record. The first draft keyed them by color and read `frame(_, C)`, which drew seven case-section hints: cases could read the colors of another frame-color reading. Keying by the `Choice` field the input varies with ("Instance-level inputs") clears them.
- `$InteriorByFrameBox` gives its one interior an id with `IdentOf<Box>` on the frame's bounding box, so that both interior readings share one `Region` key and one `kept` Bbox instance.
- `$GlobalMarksBox & $EmptyFrameKept`: I read "an interior with no mark" literally. An interior with no mark of its own keeps its input, even when the global box exists.
- `@ignore: derive VanishedColor`: with no train output, VanishedColor gives every color of the input, as SharedColor does. The two models are equivalent, so it fails Equivalence. Its witness was removed from the witness file.
- `@ignore: derive $MarkColorStored` and `@ignore: derive $InteriorByFrameBox` under the SharedColor line: those cases fail Fit. At train0, 0 closes the frame off from the grid edge, and the fill at 0 erases the frame. At train2, the fill at 5 turns (5,5) to 5.
- Header: I left out `gap-to-frame`. No `@claim` or `@relaxed` names it, no rule text depends on it, and no branch replaces it (Style, Header). Keywords: `enclose bbox`.
- Determine: `background` is the input color of the cells a pair changes, and `frame_color` is their output color. `mark_color` is the color of a kept cell that is neither of those two colors, kept only where every train pair that has marks shows it. The first draft filtered input colors by `!background`/`!frame_color`, which drew the "determine prediction" hint. The plan then flagged `other-color-mark` and then `empty-frame`, and the universal over pairs with marks fixes both. The final plan reports no actions.
- Develop, Not formed: none of the three items is formed as a branch. A stored fill color is a redundant value, by Principles "Redundant value". Clearing the box's non-mark cells gives a model equivalent to the concept. Marks touching the frame state no model.
- Deletions: I removed `frame(W)` from the `$EnclosedInterior` `region_cell` clause, because `enclosed.region` implies it. I dropped the `neighbor` atom from Determine's mark read, since every kept non-background, non-fill cell is a mark. I kept `corner_color`, `fillable`, `frame([F, _])` in `out`, and `unmarked`: the pairs never use them, but witnesses do (`background=DominantColor`, `empty-frame`, `broken-outline`, `other-color-mark`).
- Lint: no remaining findings or hints. The audit is clean: witness, dropped cases, derive, store, open values and relabelings are all ok.

## Unsettled
- A `corner_color` store branch under `$FrameColorFromOutline`: `store` printed "no witness" and no line to add, so it is not held. By hand, the `background=DominantColor` witness input appears to separate it from the derived corner color (stored 0 makes 2 the outline color and fills; the derived 2 gives back the input). Running `grid` on that input with a stored corner color would settle it, and so would `store` searching the witness-file inputs.
- No witness was built in this pass. Every case pair is separated by an existing witness, according to `witness`.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/d37a1ef5/analyze.md`, the line "`frame_color=SharedColor`: replaces the stored `frame_color` with each color of the input. Fails Fit at train0.": the runner's SharedColor fits at the concept base and fails only with `$MarkColorStored` or `$InteriorByFrameBox`.

## Tickets filed
- none
