# `Gravity` over diagonal headings — rigid bodies traveling toward a diagonal until first contact

The change widens `Gravity.dir` from `Dir` to `Dir8`, so that a body can travel toward a corner and stop at its first contact.

A diagonal heading has two readings of contact, and they are different models:

- **Pass-through.** A cell of the body stops only at a blocked cell on its own diagonal line ahead. The body slips between two blocked cells that touch only at a corner, so it passes through a diagonal wall whose cells are not on its line.
- **Collide.** A diagonal step is also stopped by the blocked cells beside it, so the body rests against a diagonal wall whatever its alignment with the wall's cells.

The way contact combines is not task data, so one comp that builds in one reading does not serve a task whose concept is the other, and a caller cannot recover the other reading through `blocked`: thickening a wall moves the rest. The change needs one of these before it can be judged: a caller-supplied contact relation that states which cells stop a step, or one comp per reading.

Not: a cast that paints the cells along a diagonal (`Ray`); a single mover whose heading is chosen by which ray meets a target; markers of several headings that stack at one cell, which one heading per key does not state.

Match: a single mover or body that travels toward a `DiagDir` or `Dir8` heading and stops at the first contact with a blocked cell or a body, by a diagonal `Ray.stop`, a `Slide.rest` over diagonal steps, or a walk over `neighbor` toward a diagonal halted on a contact test. Match with the parser (`tests/test_ast_match.py`): a rule holding `neighbor`, `jump`, `Ray` or `Slide` whose direction argument is bound to a `DiagDir` or `Dir8` heading, and whose result is read as a body's rest or travel; then read each hit in its rule set.

Survey: 2026-09-30 18:17 — every solver.

Callers:
917bccba landing — under `$Slide`, the cross's center cell steps toward the stored `params.corner` DiagDir through `slide.stop` of a `Ray` whose `blocked` is the rectangle's border, and the cross is redrawn where that center lands.
a48eeaf7 next — under `$Line(_, $Touch())` and `$Line(_, $PassBy())` with `$Merge`, each marker walks by `neighbor` toward its one Dir8 `aim`, which is diagonal when the marker lies off the block's rows and columns, and `end`/`arrive` read where the walk halts on contact with the block.
88e364bc landed — a marker cell moves by `slide.rest` toward its enclosure's arrow direction (`arrow`, Dir8, diagonal arrows included), through the `closed.region` cells of that color, until the next step would leave them.
18286ef8 dest — under `$Slide`, the gaze cell moves by `slide.rest` toward `look` (Dir8, diagonal when the target's tile is diagonal to the gaze's tile) through its own tile's cells, and stops at the tile's rim.

Near-misses:
Casts that paint or read the cells along a diagonal (`Ray`), with no body coming to rest: 992798f6 elbow (the painted diagonal leg `leg.stop`), 9f8de559 exit (the first cell past the field on `ray.stop` is painted), 342ae2ed link/paint (`shot`), 9f41bd9c moved (`trail.clear_cast` streaks), 508bd3b6 beam, 7e2bad24 enter, a3df8b1e trace, 142ca369 launch_cell, 3d6c6e23 cone, bbc9ae5d grown, 1e97544e flow, a6f40cea phase, 0b17323b walk, 5c0a986e heading, 7ddcd7ec tail.
73251a56 seek — a `Ray` cast from each hole toward `fix_corner`, stopped by intact cells. It reads the stop cell's color, so no body moves: this is the cast exclusion.
35ab12c3 edge — `sight` casts all eight `dir8_elem` headings from every key. It reads `sight.stop` to draw edges, so it is excluded both as a painting cast and by the one-heading-per-key clause.
97c75046 dest — the cardinal travel is picked by the `travel` ray that meets the shape (`landing`), and the diagonal is the one of two (`dir_of(Dg, _, D)`) along which the contact cells continue. The run ends where the `contact` node set ends, not at a blocked cell. Exclusion: a single mover whose heading is chosen by which ray meets a target.
a48eeaf7 landed under `$Stack` — markers that reach one cell settle back along their paths by path-length order. Exclusion: markers of several headings that stack at one cell.
a48eeaf7 next under `$KingPath` — the heading is re-derived from `toward` at each step, so there is no single heading. The Match line does not cover it.
409aa875 shot, 1e5d6875 copy_land — a fixed jump (`params.reach`, one diagonal step) with no contact test, so they fall outside the Match line's stop at first contact.
9def23fe fill, a47bf94d facing — false hits of the Dir8 column. Their direction comes from `dir_elem` and is cardinal only.

Spec:
The spec question should be settled in favor of a caller-supplied contact relation, not one comp per reading. a48eeaf7 is the only site that separates the readings, and it needs two of them side by side plus a reading the entry does not list:
- a48eeaf7 `$PassBy` is the pass-through reading: `next` requires `!block(S, Q)` for the step target only.
- a48eeaf7 `$Touch` is neither reading. It halts at the first cell where `touch(S, P)` holds, meaning P is an 8-neighbor of any block cell, beside, ahead, or behind the heading. A diagonal marker that grazes the block therefore stops on a cell whose contact lies off to the perpendicular diagonal, which the collide reading does not stop. This contact is a test on the occupied cell (`touch(S, P)`), and neither a pass-through comp nor a collide comp states it. A contact relation of the form "a body cell at p heading d stops" states all three readings.
- The entry names no surfacing solver. If a48eeaf7 surfaced this entry, both the two-readings signal and the third-reading signal rest on it alone, and they are caller-only.

The other callers show no preference between the readings:
- 917bccba landing and 18286ef8 dest meet only full orthogonal walls: the box border and the tile rim. There, pass-through, collide, and touch all give one rest.
- 88e364bc landed takes pass-through through `Slide`. A `closed.region` is 4-connected and `slide.node` unions every region of one color, so a diagonal step can cross a wall between two regions at a corner. This is the one site besides a48eeaf7 where the reading matters, and it is consistent with pass-through.

Two interface points follow from the callers:
- 917bccba lands on the first blocked cell itself (`slide.stop`), and `Gravity.travel` stops short of it. As a caller, 917bccba would supply the outside of the box as `blocked`, which holds only while the box does not touch the frame edge. A `stop`-at-contact output, beside the existing `travel`, would serve it directly.
- Every caller moves a single-cell body. No solver moves a multi-cell rigid body toward a diagonal, so the rigid-body part of the widened `Gravity` has no diagonal caller.

Reimplementations:
a48eeaf7 next/end under `$PassBy` — a walk of single steps inside the non-block frame cells toward one `aim` per marker, ended where no step is left. This is `Slide.rest`, keyed by marker, with `node` as the frame cells outside the block and `dir` as `aim`.
Method: a parser matcher found every unit in the solvers' own code that holds `neighbor`/`jump`, or an atom of a `Ray`/`Slide`/`Between`/`Gravity` instance, whose direction argument is a `DIAG_*` constant or a variable that is DiagDir-typed or Dir8-typed and never Dir-typed in the same body. It returned 198 hits across 122 solvers: 124 `neighbor`, 6 `jump`, 45 `.dir` inputs, and 23 reads of `ray`/`stop`/`rest`/`clear`/`cast`. The recursive walks among the hits (9), every `Slide`/`Ray` read, and the non-recursive hits whose head names a move were read in their clauses.
