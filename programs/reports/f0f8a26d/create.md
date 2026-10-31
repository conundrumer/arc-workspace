# f0f8a26d

## Departures
- `frame-edge` choice point and `$UndefinedPastFrame` removed, and witness `turn-past-frame` removed from the witness file: no input shows `$UndefinedPastFrame` defined and differing from `$Clip`, so it fails Subsumption, as `analyze.md` predicts. With the case gone, `turn-past-frame` separates nothing.
- Cases `$Straight & $PartColors`, `$ObjectD4 & $OneColor` and `$Runs & $OneColor` left `impl_choice`: `witness` reported that no run shows each one defined and differing from its partner case. The parts are found per color in every case, and `$OneColor` only adds the gate that leaves the case undefined on a two-color input. So on every input where `$OneColor` is defined, it agrees with `$PartColors`. And `$Straight` is defined only where every part is an odd straight bar, and there it agrees with `$ObjectD4`. The concept case is exempt from Subsumption. The cases left are the concept, `$ObjectD4 & $PartColors` and `$Runs & $PartColors`, each with or without `background=DominantColor`. So `$PartColors` stands for its branch through the case of the solver that takes it and differs least from the concept.
- `$ObjectD4`'s `@witness` line is `plus-part`, a new witness, in place of `touching-bars`: on `touching-bars`, `$ObjectD4` and the concept are both undefined, so it witnesses `$Runs` alone. `touching-bars` keeps its `@relaxed straight-bars` line under `$Runs`.
- New witness `wide-zero-field`: no other input showed `$Straight & $OneColor & background=DominantColor` differing from `$ObjectD4 & $PartColors` at the stored background. On the 5-by-5 `background=DominantColor` witness, `$ObjectD4` turns the square 0 field onto itself and gives the same grid as the derived background. On a 5-by-7 field it does not.
- `witness --file programs/reports/f0f8a26d/witnesses.json` now reports `$Runs`, `$ObjectD4`, `$PartColors` and `$UndefinedPastFrame` as names that denote no case: each such model takes `$OneColor`, or takes `$UndefinedPastFrame`, and those cases left under Subsumption. Before the cases left, the same run gave each branch the grid `witnesses.json` gives it.

## Judgments
- Concept-branch names: `Components` (`parts`), `Straight` (`shape-scope`), `OneColor` (`mark-colors`). `$Adjacency8` has no witness in `analyze.md` and fails Fit at test0, so it has no constructor.
- Quarter turn: for a bar, the program takes the union over both quarter turns, `rotation(S, D)` over every `Sense`. The two give one image of a straight bar, so no parameter picks one. This follows the Every-value rule.
- `$ObjectD4`: `obj_turn` stores the four axis-swapping elements, as `analyze.md` gives. A cell is background when some element leaves it undrawn, so values that disagree put two colors on one cell, and the case is undefined there. The rotation centre is the square box that has the part box's centre, grown by k on both sides of its short axis. Where height and width differ in parity, no such square exists, and the case is undefined.
- `$Runs`: a run is the set of cells that `Slide.rest` takes to one end toward a direction. The middle is the cell m with e2 = m + (m − e), so no box and no arithmetic are needed.
- Audit open values: removing any one `obj_turn` fact changes no output. If three elements agree on a part, the part has half-turn symmetry, and then all four agree. So no input separates a single fact, and the facts stay.
- `determination-plan`: `obj_turn` is undecided. No clause reads it from the evidence, and the sweep finds that the model fits at the set of all four. `background`'s DominantColor proposal reads the same fact as `background-field`, a field of the background color. So no Determine relation was written, and the solver has no Determine comp.
- `store` printed no line to add: `drawn[d]` and `runs.dir[d]` have no witness.
- Deletions: each "changes nothing" item is an undefinedness gate (`undefined`, `bent`, `straight`, `mark_color`, the square test), or a column that only inputs with no pair separate (`drawn.d`, `run_middle.c`, `run_middle.d`). They stay. The bound enumerators stay. `joined` lost its color column, because the cell gives the color. `deletions` ran a second time, because that edit came after its first run.
- Built witnesses: `plus-part` is `borderline` with verdict `$ObjectD4`. Crossing bars could give a plus, but it breaks `straight-bars`, and `$ObjectD4` and `$Runs` both give the plus unchanged. `wide-zero-field` is `variant` with verdict `background=DominantColor`, the same judgment as the analyze witness of that branch.
- Hints: the lint flagged `turn` as a lib name, `covered` as a negated single use, and two common-subexpression `out` clauses. Each was fixed: the relation was renamed `turned_by`, `covered` was inlined, and the two clauses were merged into one disjunction.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
