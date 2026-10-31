# f15e1fac

## Departures
- `$SharedHeading` is not in the solver. It fails Subsumption. It is undefined on every input whose markers lie on both edges perpendicular to the seed edge, and on every other input it gives the concept's output, so no input shows it defined and different from the concept. `witness` reported it in this way. The solver has one case, so it has no `Choice`, `impl_choice` or case column.
- The witness file holds no witnesses. `markers-on-two-edges` separated only `$SharedHeading` from the concept. After `$SharedHeading` left, that witness separated nothing, so it was removed. Before the removal, `witness --file programs/reports/f15e1fac/witnesses.json` gave `witness: ok`, and the concept's output on that witness matched the one in `witnesses.json`.
- A ray cell that steps off the grid gets no outgoing edge, so that ray ends there. This follows the concept file ("a line that steps off the grid is gone"). The analyze file's relational form is a sum of the steps, and under that reading a ray could come back onto the grid when markers lie on both perpendicular edges. The two readings differ only on inputs that break `markers-on-adjacent-edge`. No witness separates them.

## Judgments
- The ray is a walk: a `Propagation<Unit, Position>` instance. Each edge advances a cell one line away from the seed edge, and on a marker's line it then `jump`s `step` cells away from that marker's edge. This states "the steps add up marker by marker" with no arithmetic. A marker count times `step` would need multiplication, which the program bans.
- `kinked` cancels two opposite kinks on one line, as the concept's sum gives. `deletions` reports that `!kink(P, D2)` changes nothing on the pairs. No pair has markers on both edges, and that is why. It stays.
- `seed_edge(K, D_s)` in `marker` changes nothing on the pairs, but it states `markers-on-adjacent-edge`, so it stays.
- `Parse<Key>` holds the seed edge, the markers and the marker lines. The program and `Determine` both use it.
- In `Determine`, `seed_color` is the color the output paints over input cells of another color (the rays). `marker_color` is an input color that the output never changes and never paints. `step` is the shift that maps each ray cell before a marker's line onto a ray cell on that line, with no unsourced ray cell on that line. Each of the two `contradicted` clauses is enough on its own on these pairs (`deletions` reports one of them). Both stay, because together they state that the marker line's ray cells are exactly the shifted ones. The determination's `Parse<Example>` reads the stored seed and marker colors to find the edges.
- The `determine prediction` hint on `marker_color` has `@ignore`. The background differs from the marker color only in that the rays paint over background cells, so the test has to read inputs and outputs together.
- The `ex_out(E, _, _)` atoms that `deletions` reports in `parse.cell` and `marker_color` stay. They keep test inputs out of the determination.
- `derive` found no fitting built-in derivation. `store` found nothing to store. The audit is clean.
- Keywords: `markers cast walk`.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
