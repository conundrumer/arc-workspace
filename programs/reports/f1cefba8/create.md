# f1cefba8

## Departures
- The `background=DominantColor` witness: the derived branch gives the input unchanged, where `witnesses.json` gives it as undefined. The solver does not test the `framed-rectangle` scene. With background 4, the colors 0 and 1 close off the frame's 1 cells and nothing changes. The branch still differs from the concept on that witness, and its verdict stays `concept`.
- The witness file renames the analyze group `concept` on the `background=DominantColor` witness to `background=stored`, and the groups on `stray-ring-cell` to `$AdjacentNub` and `$AnyRingCell`, as `record --all` wrote them. The concept nub branch's own name is `$AdjacentNub`.
- `derive` first wrote a witness `bg=DominantColor` (train0 with 0 and 1 swapped). After `bg` was renamed to `background`, the concept file's parameter name, that witness was removed. The `@derive` line records the analyze witness `background=DominantColor` (ordinary, concept).
- New branch `$PaintOutside`, on the choice point `Paint`, from the Not formed item "Painting every cell outside the frame". In this encoding, the concept is defined on an input with a frame-color cell outside the frame, so the two readings separate there. The witness is `stray-on-line`: test0's input with a 1 at (17,6) on the column-6 line. `$BackgroundOnly` keeps the 1, and `$PaintOutside` paints it 8.

## Judgments
- `stray-on-line`, plausibility `borderline`: the stray breaks `framed-rectangle`, since the non-background cells no longer form one rectangle on the background. Verdict `$PaintOutside`: the line is drawn out to the grid edge, and a line that is drawn over a stray cell is the more common ARC reading.
- Frame color and inner color: a `Closed<Color>` instance holds, for each non-background color, the parts that the cells of that color close off from the grid edge. The frame color is the color that closes off a part, and the inner color is the color of that part. The first two forms failed on `stray-ring-cell`. Rim colors fail when an inner-color stray sits on the frame's outer row. Frame-box corner colors fail when a stray outside the frame widens the box.
- Inner rectangle: `Outlines` over the inner-color cells, then `Bbox` over the outline boxes. A nub is a single cell on its row of inner color, so no outline passes through it.
- `one-nub-per-line` is not in the header. No `@claim` or `@relaxed` line names it, and no rule text depends on it.
- Keywords: `markers` (the nubs mark a line and are consumed) and `cast` (the line runs out to the grid edge).
- Lint hints: `axis_elem(A)` in `on_line` was removed, because `nub` binds `A`. `region_color` and `frame_color` were inlined, as the single-consumer hint asks.
- `deletions`: `frame_color(F)` in `inner_color` was removed, because `enclosed.region` already implies it. The `Q` atoms in `framed` stay: the pairs hold one piece of non-background cells, and `stray-on-line` needs those atoms. `dir_elem(D)` in `nub` stays as the narrowing atom.
- `determination-plan` lists `background (DominantColor exact)` as covered on the examples. The concept stores `background` and derives it from no fact, so no Determine comp was written.
- `$NubSideOnly`, `$RingLineInner` and `$NubBothLines` fail Fit at train0, as `analyze.md` gives. `background=SharedColor` and `background=RarestColor` fail Fit at train0, and `derive` does not list them.

## Unsettled
- The `background=DominantColor` branch is defined on its witness here, and undefined in `analyze.md`. A scene check for one solid framed rectangle would make it undefined there. The concept states no such check.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
