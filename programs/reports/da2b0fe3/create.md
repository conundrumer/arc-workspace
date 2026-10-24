# da2b0fe3

## Departures
- `$SingleGap` has no constructor, and its name is gone from the witness file. It fails Subsumption. `witness` reported that no run shows `$SingleGap` defined and differing from `$AnyGaps`. Wherever exactly one gap line exists, that line is the concept's whole output, so no input at any assignment can separate the two. `analyze.md` reached the same finding.
- `$TwoParts` has no constructor, and its name is gone from the witness file. It fails Subsumption. `witness` reported that no run shows `$TwoParts & $Four` or `$TwoParts & $Eight` defined and differing from `$OneFigure`. A connected part has a cell on every line of its bounding box, so with two parts, the lines between their boxes are exactly the empty lines of the figure's box. `analyze.md` reached the same finding.
- The witnesses `two-axis-gaps` and `split-half` are removed from `programs/witnesses/da2b0fe3.wit.json`. Once the `$SingleGap` and `$TwoParts` names were taken out, concept and `$GapCenter` give the same output on each of them, so they separate nothing. `wide-gap` keeps only the concept and `$GapCenter` groups, and its `separates` text is rewritten to match. `witness --file programs/reports/da2b0fe3/witnesses.json` now reports only that `$SingleGap` and `$TwoParts` denote no case.
- Before those branches were dropped, the solver agreed with `witnesses.json` on all three witnesses (`witness --file` printed ok).

## Judgments
- I formed the Not formed item "`$TwoParts` with 8-adjacency" as `$Eight` under `$TwoParts {adj: Adjacency}`, following Develop step 3. Its cases fit every pair. They then left under Subsumption together with `$TwoParts`: an 8-connected part also has a cell on every line of its box, so its output wherever it is defined is the concept's. `witness` also reported that no witness separates `$Eight` from `$Four`. I built no witness for that pair, because both cases were leaving under Subsumption and the pair finding goes with them.
- The other two Not formed items each state no model that could be formed. No derivation gives `line_color`. A line that keeps or stops at other content gives the concept's output under `one-figure`, so it would fail Equivalence.
- The cases `$GapCenter & $SingleGap & *` were left out of `impl_choice` when the solver had all three points. `analyze.md` gives them the model of `$SingleGap` alone, so they fail Equivalence.
- `@derive DominantColor: variant derived`, `@relaxed one-figure` on `bg`: `derive` reported that DominantColor fits, with train 0 as witness after swapping colors 0 and 1. The generator routinely produces a variant task on a non-black field, which breaks the `background 0` part of `one-figure`. On that field the generator would draw the gap line, which is the derived branch's output.
- `$GapCenter` stands at `borderline any` with `@relaxed one-gap-line` on `wide-gap`, as `analyze.md` gives. I checked by `grid` that `$GapCenter` emits nothing on a gap two rows wide, while concept fills both rows.
- `store` found no relation with one value per input that it could store; it named only `crossing`, `inked` and `part_line`, each of which varies by line. The audit was clean after the Witness step.
- Determine: the sweep found each of `bg` and `line_color` uniquely fixed. The plan asks for a determination relation only where a proposer derives the value from a fact other than any the concept derives it from. DominantColor reads the field the concept calls the background, and AnyOutNewColor reads the color the concept draws, so I wrote no relation and the solver has no `Determine` comp.
- Simplify: `deletions` showed the axis column of `inked` was redundant, because an axis-only line already names its axis. I dropped it. The other deletions that changed nothing are `!undefined`, `center.id`, `runs.label` in `center`, `centered`, and the `undefined($GapCenter())` rule. Each serves even-width runs, which no pair has, so I kept them.
- Lines are axis-only positions from `split`. A line crosses the figure's box when it lies `inside` the box's own `split` component on that axis. A run of adjacent gap lines is a 4-connected component of those positions, and its center is the line that `crop` to the run's `Bbox` leaves `centered`.
- Keywords: `lines bbox`.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
