# de809cff

## Departures
- `clean` has an `@approximated:` line, and the witness file has a new witness, `thin-strip` (`ordinary other`): the analyze files give `clean` no approximation. The program has to find each rectangle from noisy cells. It takes a rectangle as the box that bounds a 4-connected set of solid cells of one color. A solid cell lies in a 2×2 block of cells that have the color, or that have it on all four 4-neighbors. `clean` has no relational form, because the input does not always fix a rectangle's extent. Where a rectangle's last line shows three cells, as the `1` rectangle of test0 does at row 19, a line that holds one ink cell and two `background` cells has two readings that satisfy every scene claim: a stray touching the rectangle's edge, or the rectangle's last line with two adjacent pinholes. The two readings give different outputs on one input, so no set of clauses agrees with the rule on both. A narrow visible strip that two adjacent pinholes cut across has no solid cell in the cut row, so the parse leaves that row out of every rectangle. On `thin-strip`, every case cleans that row to `background`. One layout of rectangles explains that input, and the generator rings and marks both pinholes.
- The witness file and `witnesses.json` agree on every analyze witness. `witness --file` printed no difference.

## Judgments
- Choice: `[f: Foreign, h: Hole, rc: RingColor, cl: Clash]` holds the four choice points that have a witness in `analyze.md`. Concept constructors: `FillForeign`, `AllHoles`, `OtherColor`, `ClashUndefined`. All 24 combinations fit every pair. The run witnesses 6 of them: the concept case and one case for each branch.
- No constructor for these branches: the ones that fail Fit (`$ForeignHoles`, `$KeepForeignStrays`, `$EnclosedHoles`, `$KeepAttachedStrays`, `$ComponentBbox`, `$StoredLayerOrder`, `$CardinalRing`, `$RingInsideRect`, `$RingOverMark`), `ring_color=stored` (a lookup table that fails Fit at test0), and `background=DominantColor`, `background=SharedColor`, `mark_color=OutNewColor` and `mark_color=AnyOutNewColor`. Each fails Fit, as `analyze.md` gives, and `derive` reported that no built-in derivation fits. `store` reported no value to store.
- Parse design: an earlier draft found rectangles with plain 2×2 blocks of the input color. That draft failed test0: a pinhole at (2,10) and a foreign cell at (4,10) cut the upper `6` rectangle's visible strip, rows 1–4, in two. A two-sided closing failed train1: the strays (7,7) and (7,9) of `2` closed over (7,8) and grew the `2` rectangle by a row. The four-sided closing passes every pair.
- A rectangle is drawn over another where its solid cells lie in the other's box. A cell is visible in a rectangle's box unless a rectangle drawn over it covers the cell. Under-color strays are lone cells and so are never solid, which keeps the layer order sound.
- Undefinedness comes from the output facts. Two ring colors at one cell give two facts, so a ring clash under `ClashUndefined` is undefined, and so is a third ink color under `OtherColor`. A pinhole whose rectangle has no ring color gets no fact, so the grid is not total.
- Determination: `ring_reach` is the least length over the output runs of one non-mark color that start beside a mark and stop at a non-mark cell. The plan's first run listed `ring_reach` under DivisorRatio, which is a fact the concept does not use. The plan still lists `background` (SharedColor) and `mark_color` (AnyOutNewColor). Those proposers read the same facts that the concept states: the field color that every input shares, and the color that the outputs add. So they have no determination relation.
- Simplify: I acted on two of the `deletions` findings. The `ink(_, Col)` atom in `open_side` was redundant, because `neighbor_in` binds `Col`. The `run_size.domain` rule was redundant, because each run has its first cell. The other findings are structure that the pairs do not exercise: the clash resolution, `$NeighborHoles`' `open_sides`, the diagonal cell of the 2×2 block, and the box test of `$UnderColorHoles`. I kept them. These two edits came after the one `deletions` run. The final pairs run came after them.
- Keywords: `objects noise bbox occlude stamp`.
- No hint was left open. I resolved the single-consumer hint on `ink_color` by inlining it, and the case-section hints by moving the shared `ring`, `clash` and `out` clauses above the case markers. I wrote the negated-use findings in the form the lint gives.

## Unsettled
- `thin-strip` stands for a class of inputs on which the parse is wrong: a narrow visible strip whose pinholes leave it no solid cell. A parse that grows each box through the lines beyond it, skipping the cells another rectangle covers, and merges the boxes of one color fits every pair and `thin-strip`. That parse is a larger approximation of `clean`: it cannot separate the two readings above.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
