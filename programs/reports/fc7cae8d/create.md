# fc7cae8d

## Departures
- The parameterization is not empty. `bg` (0) and `noise` (5) are Params relations under the `$ContentBox` marker: the analyze file defines `$ContentBox` as excluding cells of `background` and `noise_color`, so its cases read those two values. No case that takes `$StripBox` reads a parameter.
- The solver finds the frame edges by a different parse than the analyze check uses. That check reads each edge without its two end cells. The program cannot do that, because the literal 2 would have to be a stored parameter. Instead, each edge's color is the commonest color of its line (`Mode`), and the frame is the pair of adjacent edges whose two lines hold no color besides their two commonest colors. All four pairs give the analyze file's edges.
- A `@derive DominantColor` branch was added on `bg`, and `@derive DominantColor` and `@derive RarestColor` branches on `noise` (Develop step 4). Each one fits every pair. Their witnesses are in the witness file. Only the cases that take `$ContentBox` read these parameters.
- The `noise-edges` scene claim is in the header. The `@relaxed` line of `noise=DominantColor` cites it.

## Judgments
- Strip parse: a strip corner is a cell x, of neither strip color, that has a cell of one frame color one step toward u and a cell of the other frame color one step toward r, where u and r are the two cardinal directions of a diagonal. Each strip is the run of its color away from x (`Slide`). The box is the bounding box of the cells beside the strips. A corner is rejected under either of two conditions: a strip cell has a neighbor of the strip's color across the strip (the strip is not one cell wide), or the box holds a frame color (`picture-colors`). The width test is needed. Without it, on train 2 the picture's own corner cell (5,4) also acts as a strip corner: the strip ends (4,4) and (5,3) meet there, and the box is 1x1 at (4,3).
- `bg=DominantColor`, witness `bg=DominantColor` (train 0 with 0 and 7 swapped): `variant concept`. A color swap is a variant task. The derived background gives the concept's picture, and the stored background 0 makes the content box cover the whole field.
- `noise=RarestColor`, witness `noise=RarestColor` (train 2 with the picture's right column background, apart from one cell of a color held nowhere else): `variant concept`. The input breaks no scene claim in the header. The concept keeps the 5x5 box. RarestColor takes that one color as noise and gives 5x4.
- `noise=DominantColor`, witness `noise=DominantColor` (the same input, with that one cell holding 5): `borderline concept`, `@relaxed noise-edges`. A noise cell inside the picture is outside what the inputs show. The derived noise is the background color, so that 5 cell counts as content and gives 5x5. The stored noise gives 5x4.
- Sweep: `noise` admits other values on the train pairs. It is not an open parameter. No reader of the concept would take a color other than the scattered edge color as noise, so 5 stays the only stored value.
- Determination: `bg` is the commonest color of every input, and `noise` is the color that every input holds and that no output holds. A first form of `noise` combined input and output facts in one test. The lint hint against that form was correct, so the input part and the output part are now separate tests.
- Deletions: a group of the deletions changes no pair. These stay, because each one states part of a claim that the pairs do not test: `perp_dir` in `frame_cand`, the `D2` disjunct of `frame_defect`, `frame_color` in `run.node`, the `Q = E1` disjunct of `strip`, the `picture-colors` rule of `tainted`, the corner columns of `orient` and `extent`, `!params.noise` in `content.node`, and `uncommon` in the determination. Three deletions were applied: the unused `c2` column of `strip_corner`, `picture(K, _)` in the `$ByColor` `orient` clause (the join with `extent` already requires it), and `content_size.domain`. After those edits, the shared `out` clause was put back under a case marker. `deletions` was not run again after that.
- Witness checks: the run against the witness file and the run against `witnesses.json` both pass. The audit is clean. Six cases are witnessed. The cases that combine `$CornerSwap` with `$ContentBox`, and the combinations of the derived branches, are not witnessed, because no input shows them giving an output that a case with fewer non-concept branches does not give.

## Unsettled
- The frame parse uses the commonest color and the "only two colors" test, which is weaker than "solid line". A variant input whose noise edge holds only the background color and one frame color would break that parse. A witness on such an input would show whether the parse needs a stricter form.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
