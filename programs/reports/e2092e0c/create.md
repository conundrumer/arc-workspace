# e2092e0c

## Departures
- `$OnlyCopy` and `$RingInGrid` have no constructor, and their witnesses `two-copies` and `copy-at-edge` are left out of the witness file: both fail Subsumption. Where either model is defined, the concept case gives the same output. With both branches gone, those two witnesses separate nothing.
- `$KeySizeFromFence`, and the `mark-color` & `key-size` combination, take the least line k > 0: a side of 0 is a key with no cells. The literal "least k" reading gives k = 0 wherever the corner cell has the fence color, as on `mark-color-key`. `witnesses.json` gives `$KeySizeFromFence` a 1 × 1 key there, so the solver follows `witnesses.json`.
- `impl_choice` leaves out every combination of `$RingFenceColor & $KeySizeFromFence & $KeyCornerFromFence`: each one fails Fit. On train 1 and train 2 and on test 0, a second corner also has a line of one color, so the model is undefined there.
- `scattered-field` stands in the header: the `bg=DominantColor` witness's `@relaxed` line refers to it.
- `bg` has two `@derive` branches that `analyze.md` does not give (`run_dl.py derive` reports that both fit):
    - `bg=DominantColor`: `foreign`, verdict `concept`. Its witness is near-copy with most free background cells turned 7. It breaks `scattered-field`.
    - `bg=RarestColor`: `borderline`, verdict `concept`, on near-copy. A second witness, `rare-key-cell`, separates `$MatchMarks & bg=RarestColor` from `$AllCells`: the key and its copy hold the rarest color 3 at the center, and a near copy holds 2 there. `borderline`, verdict `concept`, for the reason near-copy has.

## Judgments
- The `$SameOrientation` transform set is the identity, derived as the D4 element that composes with itself to give itself (`d4_compose(D, D, D)`). The other choice was to store `D4_ID` as a parameter, and that would add a parameter the concept does not have.
- The copy is matched with `Occurrences` keyed by `[corner, size, cells, image]`. Cases that find the same key place share the same instance.
- Ring width under `$RingFenceWidth` is the `Tally` of the consecutive fence lines from the key's side outward, and the ring is the copy box grown by that count.
- Hint `case section` on `key_at`, `xform_image` and `params.key_corner`: each one is dismissed with `@ignore`. Each clause derives the rows of its own branch alone, so the static reading over-reports.
- Hint `common-subexpr` (`fenced` against `key_cell`): resolved. `fenced` is now `key_cell` or `corner_line`.
- `store` lines on `key_base`, `least_mark.cand` and `least_mark.low`, `fence_run` and `fence_width.item`: dismissed with `@ignore: store`. A stored copy repeats the stored corner or side, or is undefined where those differ, so it fails Equivalence or Subsumption.
- Determination: `mark_color` is the color of the changed cells. `key_corner` and `key_size` come from the fence lines that every train input fills with that color. `bg` gets no relation: DominantColor is the concept's own reading of the background.
- Sweep: `bg` admits every color on the train pairs. It is not an open parameter, because background 0 is a scene parameter of the concept, so nothing more is stored.
- Deletions:
    - 37 of the deletions change no output. Each one removes a branch feature that the pairs never use, such as the fence-width gap clauses, `two_fenced`, `overlaps_fence` and `undefined`.
    - One of them is truly redundant: the `key_cell` atom in `key_image`, because `crop` already tests that the cell is in the key box. It stays, because the edit came after the one `deletions` run.
- Performance: a pairs run takes 1–7 s. `audit` took 78 s with 512 combinations, and 17 s after the combinations were cut.

## Unsettled
- `rare-key-cell`, `bg=DominantColor`: the plausibility and verdict are this pass's own judgment. An annotator's review would settle them.

## Concept faults
- none

## Fixes elsewhere
- `scripts/run_dl.py deletions`: run in a worktree with a bare task id, it resolves the solver path against the main worktree. It needs to resolve the path against the current worktree.

## Tickets filed
- none
