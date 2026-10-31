# e376de54

## Departures
- The past-edge choice point and its branch `$RefusePastEdge` are not in the solver, and the witness file lists `$RefusePastEdge` in no group. Its witness `extension-past-edge` stays, with its `separates` text rewritten, because it still separates the concept from `$SecondLongest`. Reason: `witness` found no run where `$RefusePastEdge` is defined and differs from the concept branch `$Clip`. Its model is defined only where the concept is defined, and gives the concept's output there. So it fails Subsumption, as `analyze.md` predicts. When `witness --file` runs against `witnesses.json`, it reports only that the name `$RefusePastEdge` denotes no case.
- The `Choice` is the ADT of the `reference-length` point (`Middle`, `SecondLongest`) and not a record. Reason: the past-edge point left, so one point is left in `Choice`.
- The witness file has an added witness `dense-lines`, for the `bg` point inside `$SecondLongest`. Reason: `witness` reported that no run showed `$SecondLongest & bg=stored` defined and different from `$SecondLongest & bg=DominantColor`. On a 4x9 grid with five column lines of color 4, color 4 outnumbers the field 7. At the stored bg, `$SecondLongest` sets every line to 3 cells. `bg=DominantColor` takes 4 as bg and gives a different grid. My judgment: plausibility `borderline`, because the generator draws sparse lines on a 16x16 field. Verdict `concept`: the middle line has 4 cells, so every line gets 4 cells. The witness is a further witness of a `@derive` branch, so it has no `@witness` line.

## Judgments
- Segments are the pieces of `Components8` over the cells that are not bg. Reason: no two segments touch, and diagonal segments link only at corners.
- The middle line is ordered by its segment's cells, not by its start cell. Reason: along a direction of the cross axis, every cell of a segment has the same `nearer` distance. With this order, the middle is found before the start direction is known.
- Start direction: the direction along the line axis whose segment ends all lie on one cross line (`same_line` on the cross axis). Suppose every line has one length. Then both directions qualify, and both give the same output.
- Lengths are Ray step counts from each start, compared only against the reference count (`K <= K_ref`). No count is computed.
- Single-consumer hints on `seg_color` and `middle`: both relations were inlined.
- Deletions: 9 deletions changed no output. I kept them all, because each one states structure from a scene claim. The atoms are: `line_axis` and `axis4_of` in `end`, `cross_axis` in `aligned` and in `across.before`, `start_dir` in the `cast` inputs, `end(I, S, Src)` in `seg_reach`, and the column `reach.s`. On the pairs, other atoms imply them. A `reach.s` column is needed because each start direction has its own reference count.
- Determine: `bg` is the mode of the input cells, as in the 0ca9ddb6 precedent. `determination-plan` then printed no actions.
- `store` listed `cast.cell[p]`, the grid frame, with no witness and no line to add. As Develop directs, I put a `@workaround` mark on it.
- `bg=DominantColor` is a `@derive DominantColor: variant derived` line, `@relaxed field`.
- `@keywords: objects rank cast`.
- On inputs that break `parallel-lines`, such as `dense-lines` at bg 4, the model can give a grid. It does not refuse those inputs. The concept states the scene as a claim and does not check it.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- `docs/handbook` Develop, "Where `store` prints no line to add for a value, mark that value with a `@workaround` directive": a value that `store` lists with no witness, such as the grid frame, gets a `@workaround` mark that stands in for nothing. The line needs an exception for values where storing is no reader's interpretation.

## Tickets filed
- none
