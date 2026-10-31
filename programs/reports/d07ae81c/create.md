# d07ae81c

## Departures
- `marker-background` is a top-level `Choice` field (`Background`), not nested under the concept branch of `ray-color`: `ray-color`'s other branches (`$StoredColorMap`, `$RayOwnColor`) and `ray-directions`' `$EightWayRays` fail Fit and have no witness, so none of them gets a constructor. That leaves `ray-color` and `ray-directions` with only their concept branches, so a one-constructor wrapper type would add nothing.
- I added witness `full-line-field` to the witness file. `witness` reported that no run showed `$FullLineBackground` defined and differing from `$NeighborMajority`. The new input has a 1 marker on the 8 field next to a band crossing and a 4 marker on a 2 band row. Layout and full-line readings both give 8→1, 2→4. The neighbor reading puts both markers on 2 and is undefined. Plausibility `variant`: its only band column is one cell wide, the same invariant `marker-at-field-corner` breaks. Verdict `concept`. It has no `@witness` line, because it separates two non-concept branches and not a branch from the concept.

## Judgments
- The background colors are the commonest color and the commonest of the rest (two `Mode` instances). When two colors tie as commonest, those two are the background (`tied_commonest`): the concept names no parameter for them, and its scene parameter `background_colors` is 2. This agrees with `banded-background` on every input the generator produces, because markers are a few cells. I checked a tied grid (`8188/8888/2222/2242`) with `grid`. It fails only when markers outnumber a background color, which is `foreign`.
- I made the concept and every branch undefined where some marker sits on two colors (`torn`). `analyze.md` says the concept is undefined there, and `$FullLineBackground` is undefined where full lines of both colors cross the marker. Without `torn`, `marker-at-field-corner` gave a defined `$FullLineBackground` grid, because both readings mapped to 4, and that disagreed with `witnesses.json`.
- A background color that two marker colors share, or that no marker sits on, gives the ray cell two colors or none, so the case is undefined there. That matches `one-marker-color-per-background`.
- `$FullLineBackground`'s field color is the background color that fills no full line once markers are left out. If both colors fill full lines, a marker with no full line through it has no reading.
- Hint `single-consumer` on `color_map`: kept, with an `@ignore`. The map is the object of rule `marker-color-map`.
- Not formed item "rays that stop at the next marker": I formed it as a branch in a scratch solver (`work/task/d07ae81c/d07ae81c_notformed.dl`) and dropped it under Equivalence. `witness` reported no input separating it from the concept, and the continuation past a blocking marker is that marker's own ray in the same direction.
- Not formed item "rays that repaint the markers they cross": formed in the same scratch solver and dropped under Subsumption. A crossed marker takes the map of the color it sits on, and that map holds the marker's own color. So wherever the model is defined, its output is the concept's.
- Not formed item "background read from a marker's connected piece or bounding box": no case. It fails Fit at train0, as `analyze.md` states.
- `derive`: no built-in derivation fits. `store`: no value to store with a case. Sweep and determination plan: nothing to do, since the solver has no parameters and no `Determine` comp.
- Deletions: I removed `in(P, Col)` from `full_line`, `marker(M, P)` from `on_full_line`, and the non-background filter on `around.item`. Each was implied by another atom or only narrowed the computation. The rest of what the report listed is structure the pairs never exercise (the tie guard, `torn`, the `$SingletonMarkers` test, marker exclusions in the line comparisons), and it stays.
- Witnessed cases: 4 of 6, namely the concept, `$FullLineBackground`, `$NeighborMajority` and `$SingletonMarkers`. The two combinations with `$SingletonMarkers` take two rejected or verdict-bearing branches, and no input shows them giving a new output.

## Unsettled
- No witness shows a combination of `$SingletonMarkers` with `$FullLineBackground` or with `$NeighborMajority` giving its own output. A witness with adjacent markers on which the full-line or neighbor reading also differs would settle whether those combinations are cases.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/d07ae81c/analyze.md`, Concept section, "(`work/task/d07ae81c/probe.py`)": the probe is not in `work/`. Restore it or drop the citation.

## Tickets filed
- none
