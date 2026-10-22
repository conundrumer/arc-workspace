# d22278a0

## Concept
- Fits every pair: each cell goes to the seed at the least taxicab distance, a cell tied there is 0, and a cell that goes to a seed takes its color at even Chebyshev distance from it.
- No witness has the verdict `other`. Each rule has a relational form: the taxicab and the Chebyshev distance count steps and rings between two cells, and the nearest seed is the least of those counts over the seeds.
- The concept is undefined only where the input has no non-background cell.
- On a square grid with every seed at a corner, the taxicab, the Euclidean, and the Chebyshev-then-taxicab territory give each cell the same seed, so the territory branches below part only on a rectangular grid or with a seed off a corner.

## Choice points
- `territory metric`
    - `concept`: the taxicab distance (row distance plus column distance) picks a cell's seed
    - `$ChebyshevTerritory`: replaces `nearest-seed` with the Chebyshev distance, as when the rings of every seed grow one step at a time and a cell two rings reach at one step stays blank; no parameter; undefined where the concept is. Fails train0: (6,5) is at Chebyshev distance 6 from both seeds, so the branch gives it 0, and the output has 2.
    - `$EuclideanTerritory`: replaces `nearest-seed` with the Euclidean distance; no parameter; undefined where the concept is. Fits every pair. Fails Relational form: a Euclidean distance counts nothing the task has.
        - Witness `wide-grid`: a 6×11 grid with 1 at (0,0) and 2 at (5,10). The concept gives (1,6) 1 and (4,4) 2, and the branch gives (1,6) 2 and (4,4) 1. It breaks `square-grid`. Plausibility `variant`, verdict `concept`. The invariant it breaks: every grid is square.
    - `$RingThenTaxicab`: replaces `nearest-seed`: a cell goes to the seed at the least Chebyshev distance, and among the seeds tied there, to the one at the least taxicab distance; it is 0 where both tie. No parameter; undefined where the concept is. Fits every pair.
        - Witness `wide-grid` (above): the branch gives (1,6) 2 and (4,4) 1 as `$EuclideanTerritory` does, and gives (0,6) and (5,4) 0, where the concept gives 1 and 2. It breaks `square-grid`. Plausibility `variant`, verdict `concept`. The invariant it breaks: every grid is square.
- `blank cells`
    - `concept`: a cell is 0 where two or more seeds tie for the least distance from it
    - `$AnyTieBlank`: replaces `nearest-seed`, so a cell is 0 wherever two seeds are at one distance from it, nearest or not; no parameter; undefined where the concept is. Fails train3: (2,2) is at taxicab distance 4 from the top-left seed and 6 from the two others, so the branch gives it 0, and the output has 1.
- `ring distance`
    - `concept`: the Chebyshev distance from the seed sets a cell's ring
    - `$TaxicabRings`: replaces `alternating-rings` with the taxicab distance, so the rings are diagonal lines; no parameter; undefined where the concept is. Fails train0: (1,1) is at taxicab distance 2 from the top-left seed, so the branch gives it 1, and the output has 0.
- `ring anchor`
    - `concept`: the rings center on the seed's cell
    - `$CornerRings`: replaces `alternating-rings`, so the ring distance is the distance from the two edges of the corner the seed sits at; no parameter; undefined where a seed is off a corner. Fits every pair. Fails Subsumption: where the branch is defined, every seed sits at its corner, so the distance from the corner's edges is the Chebyshev distance from the seed, and the branch's output is the concept's at every assignment.
        - Witness `edge-seed`: a 7×7 grid with 1 at (0,0) and 2 at (3,6). The concept draws square rings around (3,6), cut off by the grid, and the branch is undefined. It breaks `corner-seeds`. Plausibility `borderline`, verdict `concept`. The invariant it breaks: every seed sits at a corner. On this witness, `$EuclideanTerritory` and `$RingThenTaxicab` give (0,4), (3,2) and (6,1) 0, where the concept gives 1, 2 and 1.
- `background`
    - `concept`: stored `background` (0)
    - `background=DominantColor`: derives `background` on each input as its commonest color; undefined where that color ties. Fits every pair.
        - Witness `background=DominantColor`: train3 input with 0 and 3 swapped. With the stored background 0, every cell is a seed, and the concept gives the input. The branch gives train3's output with 3 for 0. `$CornerRings` is undefined. It breaks `square-grid` and `corner-seeds`. Plausibility `variant`, verdict `background=DominantColor`. The invariant it breaks: every field is 0.
    - `background=SharedColor`: derives `background` on each input as a color the input holds. Fails train0: on train0's input alone it gives 0, 1 and 2, and the model is undefined.
- `territory metric` & `blank cells`, `territory metric` & `ring distance`, `territory metric` & `ring anchor`, `territory metric` & `background`, `blank cells` & `ring distance`, `blank cells` & `ring anchor`, `blank cells` & `background`, `ring distance` & `ring anchor`, `ring distance` & `background`, `ring anchor` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Tied cells take one seed's color by a stored priority: train1 (1,1) is at Chebyshev distance 10 and taxicab distance 11 from both 3 and 8, and it is 0.
- Each seed owns the quadrant of its corner: train3 (4,5) is in the bottom-right quadrant, which has no seed, and it is 2, from the top-right seed.
- Rings that start one step out, with the seed's cell blank: every seed's cell keeps its color in every output.
- `ring_period` derived: no proposer gives a ring step, and the pairs fix it to 2. It is not a choice point.

## Tickets filed
- 10-648_task_d22278a0_analyze.md
