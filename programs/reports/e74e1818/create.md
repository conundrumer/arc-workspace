# e74e1818

## Departures
- The witness file has a fifth witness, `dominant-defined`. It is not in `witnesses.json`. The input is 3 3 3 3 3 / 3 0 3 0 3 / 3 3 3 3 3 / 3 3 3 3 3 / 4 4 4 4 4. Rests on: `witness` reported that no run showed `bg=DominantColor` defined and differing from `bg=stored`, because on the `bg=DominantColor` witness that branch is undefined. On `dominant-defined`, the concept flips the 3 layer over rows 0–3, so the 0 cells move to row 2. `bg=DominantColor` takes 3 as the background, and its one-row 0 layer stays on row 1.
- The concept branches take names of my own: `$ColorLayer` at `layer` and `$FlipInSpan` at `layer-transform`. `bg=DominantColor` is a `@derive DominantColor` line on `bg`, not a constructor. `record --all` rewrote the witness groups to the listed form, and `bg=stored` now names the concept branch at `bg`.

## Judgments
- `dominant-defined` is `borderline concept`: 0 is not the commonest color and leaves no frame, which is the same invariant `analyze.md` gives for `bg=DominantColor`. A reader with background 0 flips the 3 layer as a whole.
- The `bg=DominantColor` line is `borderline concept`, as `analyze.md` gives it. It has no `@relaxed` line, because that witness breaks no scene claim.
- I wrote the transforms as a D4 element applied in a frame box. `crop`, `apply` and `compose` do that work. The concept and `$Rot180InSpan` use the layer's span (`split` of its box on `params.axis`). `$Rot180InBox` uses the bounding box. The flip is `flip_of(axis)`. The half turn is the two axis flips composed, so the program needs no D4 literal.
- `$RowBandLayer` finds the line colors with `Unanimous` and the bands as `Components<Color>` over axis-only line positions. It is undefined where a line holds two colors: when `line_color.clash` holds, `layering` excludes the branch, so the branch writes no background cells and its output is not total.
- The case-section hints came from a `reframe` relation that read `layer_box` with the layer column as a wildcard. I fixed them: `framed` keys each cell's frame by the full `Choice`.
- Hint `common-subexpr` on `band_box.cell`: fixed with the `ink_line` relation.
- Hint `head-repeat` on `reframe`: that relation was removed.
- Finding `shared-read` on `axis`: `axis` moved under `// --- $FlipInSpan, $Rot180InSpan, $RowBandLayer ---`, because `$ColorLayer & $Rot180InBox` does not read it.
- Hint `pass-through` on `half_turn`: I kept it with `@ignore`. It states the half turn once for the two transforms that use it.
- Hints `determine prediction` on a first Determine: they fired on an `axis` relation that tested input and output together. I removed that relation. The `bg` relation keeps the colors whose removal leaves the other colors on disjoint lines along some axis, which is a fact of the inputs (the `stacked-layers` scene claim). Its `ex_out(E, _, _)` atom only selects the train examples, as "Test inputs" in Determination requires. `deletions` reports that removing it changes nothing, and I kept it for that rule.
- `deletions` reports that column `framed.p` can go with no change. I kept it. Without it, a cell moves in every frame that covers it, and not only in its own layer's frame. That frame choice holds only while the spans are disjoint, so it fails on `repeated-color`, where the concept's 2 span covers the 3 layer.
- Not formed in `analyze.md`: none of its items gives a model that a reader takes or that fits, so Develop step 3 added no branch. `store` printed no findings.
- Four of the six `Choice` combinations are witnessed cases. With `bg=DominantColor`, five cases run.
- Proposed keyword gloss: none. Keywords used: `lines d4 bbox color-class`.

## Unsettled
- `determination-plan` still lists `axis` (domain enumerable(2), pairs-exact: AXIS_V) after three runs. No proposer derives an axis from the inputs alone, and a test of input against output is not a valid determination. To settle it, confirm that the pairs-exact enumeration is the determination for `axis` and that it needs no relation.
- `deletions` ran before the last edit, which only removed an `@ignore` comment line from Determine.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
