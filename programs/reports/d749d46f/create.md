# d749d46f

## Departures
- `$GapFromInput` has no constructor and no clauses in the final solver, and its name is gone from `programs/witnesses/d749d46f.wit.json` (the `gap-two` group and the `gaps-unequal` undefined group, with both `separates` texts rewritten): it fails Subsumption. Wherever it is defined, every gap between neighbors (a gap of 0 included) is the one shared value, so `$GapPerNeighbor` gives the same grid. `witness` reported that no run shows it differing from `$GapPerNeighbor`, and no input can. `analyze.md` reaches the same verdict. The `--file` run against `witnesses.json` differs only in the `$GapFromInput` names.
- The `gaps-unequal` `@witness` line (borderline `$GapPerNeighbor`, `@relaxed bars-in-a-row`) now stands under `$GapPerNeighbor`, because its first branch left. It still separates `$GapPerNeighbor` from the concept.
- `$BackgroundAtBottomLeft` has no constructor: it fails Fit at train2, and `analyze.md` gives it no witness.
- `output-height=ConstOutDim` has no `@derive` line: `derive` reports that no built-in derivation fits. It also fails Fit at train0, as `analyze.md` gives.
- The header leaves out the `height-is-tallest-bar` scene claim: no `@claim` or `@relaxed` denotes it, no rule's text depends on it, and no branch replaces it (Style, Header).
- `$GapPerNeighbor` reads the input gap before a bar as the cells of the hang-edge row whose columns hold no bar cell, running up to that bar from the bar before it. Only gaps between two bars count. On every generator input this is the run of background cells between two bars on the top row. Where a bar does not reach the hang edge, or background comes before the first bar, it still gives "the input gap between those two bars", which `analyze.md` states. My first version, which read background runs on the top row, gave neither.
- The witness file gains `minority-bars-gap-two` (input `8 8 1 8 8 1 8 8` on two rows). Without it, the case `$GapPerNeighbor & $BarColorMinority` was unwitnessed: on every other input it agreed with one of its sub-cases.

## Judgments
- The rules all have relational forms, and nothing is approximated. Both rows of bars come from one `Order` over slots, ranked into output columns:
    - a bar's flat-row slots are the cells of its longer side, and its standing-row slots the cells of its shorter side; a square uses its hang side in both rows;
    - the stored gap is `params.gap` cells toward the pack edge from the corner of each bar but the first.
  A rank counts the columns before a slot, so no sum is computed.
- An output cell takes the bar color when the bar holds a cell as far in from the slot as the output cell lies from the row's edge. Because bars are solid, this needs no min or max of the extents.
- `>=`, `>`, `<` between two side counts, and `<` between two color counts, are comparisons, not arithmetic. Lint accepts them.
- Hint `common-subexpr` on `slot_side`: I merged the two clauses into one disjunction (flat row: longer side; standing row: shorter side).
- `store` showed `one_gap.item` and `one_gap.value` (under `$GapFromInput`) holding 1 on every input. A stored value there is the `$StoredGap` model, so those branches failed Equivalence. They went away with `$GapFromInput`. `gap_width` was "stored already", and the gap-strip and `gap_run.rest` values had no witness.
- Determination: I wrote `Determine.gap` from the input's background runs on the hang edge that lie between two bars. The plan's proposer, `TileDim`, gets 1 from tile fits, which is a different fact. I wrote no relation for `output_height`: `ConstOutDim` reads the output row count, the same fact the concept reads. `hang_edge` and `pack_edge` are set by fit over their enumerable type (pairs-exact). Determine repeated the corner-color derivation, so it moved into `Parse`.
- `Bbox<Ident>` and the bar ids are shared across the `BarColor` keys of `Components`. Under the two bar colors the node sets are either equal or disjoint, so one id names one bar.
- `deletions`: I removed `axis_of` from `corner` (`diag_dirs` grounds the axis), the hang-row restriction from `spanned`, and `row_edge(D)` from `covered` (`row.rank` and `bar_slot` ground `D`). The other atoms it listed stay. Each restricts to the hang row, the hang or pack edge, or bars that have a predecessor, which only scene-breaking inputs exercise. `open_run` in Determine is the same: the pairs never have an open run.
- Witness `minority-bars-gap-two`: plausibility `ordinary`, verdict `concept`. Under the concept it is three 2x2 bars of color 8, one column apart, filling the strip from edge to edge in two colors. It breaks no scene claim, and the concept output is the one the generator would pair with it. It has no `@witness` line, because it is a case's witness, not a branch's.
- Not formed items in `analyze.md`: none of them states one model that fits, so no branch was added.
- Keywords: `objects tile-arrangement d4 rank`. The bars are pieces, the output lays turned copies of them out in two rows, each bar is transposed by its aspect, and the input order sets each bar's place.
- Performance: every run takes about 1 s, and `deletions` takes 13 s.
- Process slip: I piped one `audit` run through `grep` to hide grid rows, which "Reading files and outputs" does not allow. Every later `audit` was read whole.
- I did not read `src/`.

## Unsettled
- A standing bar longer than `output_height`, or a flat bar and a standing bar that overlap: the model clips them to the 10-row canvas. No pair shows it. A pair with a bar longer than 10, or one where the flat and standing rows meet, would settle it.
- Whether `output_height` needs a determination relation, given that `ConstOutDim` covers it from the same fact: the plan's wording, "a proposer derives from a fact other than any the concept derives it from", reads as no, and a reviewer of the plan's intent would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
