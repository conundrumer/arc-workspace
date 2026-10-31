# d93c6891

## Departures
- Witness `grid-edge-block` is added to the witness file. It has the verdict `$FieldByColors`, plausibility `borderline`, and `@relaxed blocks`. The first audit reported that no run showed `$FieldByColors` defined and differing from `$NonBackground`, and none of the Analyze witnesses does: on `stray-color-row`, `$FieldByColors` is undefined. In the new witness, the field reaches the grid's top edge and a block sits on that edge with two bars beside it. The concept finds no side of the block that faces the background, so it is undefined. `$FieldByColors` counts the off-grid side as facing no field cell, so it fills the block's two rows. That keeps `$FieldByColors` under Subsumption. I judge the verdict to be `$FieldByColors` because a person would fill from the grid edge. I judge it `borderline` because it breaks `blocks`: no input has a block on a field side that meets the grid edge.

## Judgments
- Run: every train pair and the test pass with 9 witnessed cases of the 144 base cases. Lint is clean. Determination gives `bar` 5, `block` 7, `floor` 4 and `background` 0, and the sweep finds each value unique. `witness`, `witness --file programs/reports/d93c6891/witnesses.json` and the final audit all report ok. `record --all` changed no groups, so every branch's output matches `witnesses.json`.
- Choice shape: `Choice` is `[c: Contact, s: Side, r: Remainder, o: Overflow, l: Loose, f: Field]`, with one field for each choice point that `analyze.md` gives a witness for. All combinations are cases, because every combination fits.
- Concept-branch names are my own: `$Contact4`, `$FromBorder`, `$WholeOnly`, `$WithinBlock`, `$EraseAll`, `$NonBackground`. No witness-file name needed rewriting.
- Branches without a constructor: `$SameSide`, `$PerBar`, `$FromContact` and `$Inner` fail Fit, according to `analyze.md`. Every color derivation fails Fit, and `derive` reports that no built-in derivation fits. `store` reports nothing.
- Not formed: none of the items states a model to add. The slide reading gives the concept's output plus `$PartialFromBar`. The fill color is derived data. No parameter is a pair of colors. No rule splits a bar between two blocks.
- Layer count: the lib relation `stride(N, E, 0, Layers, Rest)` reads the count `N` as cells poured into layers of `E` cells. Cell `N` lands in layer `Layers`, at place `Rest` in that layer. So `Layers` is the number of whole layers and `Rest` is the cells left over. The concept is undefined where `Rest > 0` or `N` is more than the block's area (a `Tally`). A block whose definedness check fails emits no cells, so the case's grid is not total.
- Border side: a block's side whose neighbour cell beyond it is `background` (`$NonBackground`), or is not a `floor`, `bar` or `block` cell, off-grid included (`$FieldByColors`, following analyze.md's "faces no field cell"). A block that takes bars and has no single side to fill from is undefined.
- `$FromBarLine`: a bar's axis is the axis of a step between two of its cells. The fill side lies on the other axis, and it is the side whose edge is nearer the bar (`dist_pair` in the block's frame). A one-cell bar takes the border side. More than one side makes the block undefined.
- `$PartialFromBar`: a block end is a side across the fill side, and the bars touch it where a taken bar cell lies beyond that edge (`nearer`). The case is undefined where cells are left over, the next layer exists, and the bars touch both ends or neither. analyze.md names only "both ends". Neither end, as when a bar touches the inner side, gives no end to start from.
- `$RingPath`: the ring is the cells that face outside the field under the case's `Field` branch. A walk (`Reach` keyed by field branch and block) runs from the block's ring cells through ring bar cells.
- Determination: `bar`, `block` and `floor` read a repaint chain from the train pairs: block cells turn bar color, and bar cells turn floor color. The first `background` relation kept the input color outside that chain. It drew the "determine prediction" hint, which was valid because that test read inputs and outputs together. I replaced it with a test on inputs alone: the color none of whose cells lie inside the box of the other colors' cells, in every train input.
- Hint "case section" on `border_side` (a shared clause under the `$FieldByColors` marker): valid. It now stands under an every-case marker.
- `deletions`: I removed `box_edge` and `block_box.box` from `border_side`. A block cell that faces outside the field is already on that side's edge. I removed the `ring` relation and `field($NonBackground)`, because the walk's nodes are bar and block cells, which are field cells under both branches, so `faces` alone gives the ring. I kept the other reported deletions:
    - `dir_elem` in `$Contact4`: it is the concept's 4-contact.
    - `bar_axis` and the first `$FromBarLine` clause: they define the branch.
    - `area`, `overfull`, `sides_clash`, `next_layer`, `touched_end`, `one_end` and the `undefined` rules: they define where cases are undefined, and the pairs never exercise that.
    - `params.block` in `field_cell`: it states the branch's field.
    - The `ex_out` atoms in Determine: the test-inputs rule.
    - The bound enumerators stay, as the report directs.
- Keywords: `objects count`.
- Performance: a full run takes 1–5 s, and the audit takes 11 s. No issue.

## Unsettled
- 135 of the 144 base cases are combinations of branches that no input shows giving an output beyond what their single branches give, so no run includes them. A witness for one of them, such as `$Contact8 & $PartialFromBar` on a block that takes a diagonal bar and is left with a partial layer, would settle whether it adds anything.
- `$PartialFromBar` is undefined where the bars touch neither end. A verdict on a witness with a remainder and a bar touching only the inner side would settle this.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/d93c6891/analyze.md`, Concept line "Fits every pair (`work/task/d93c6891/probe.py`)": the file does not exist under `work/task/`.

## Tickets filed
- none
