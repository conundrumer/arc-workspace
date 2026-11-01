# e26a3af2

## Departures
- `$AxisPlurality` is not in the solver, and the witness file no longer names it in its groups or its `separates` texts: it fails Subsumption. Where it is defined, one axis has no tied line and the other axis has one, so `$AxisFewestChanges` takes the same axis and gives the same output (`analyze.md` gives this proof). The audit found no run that shows it defined and different from `$AxisFewestChanges`.
- The concept constructor is named `AxisMajority`. The witness file keeps the name `concept` for it.
- The header has no `@scene adjacent-stripes-differ`: no `@claim`, `@relaxed` or rule text refers to it, and no branch replaces it ([Style: Header](docs/handbook/style.md#header)).

## Judgments
- `line-mode` paints each line with its commonest color. A task in which noise ties with or outnumbers a stripe's color in a line is invalid, so that color is the stripe's color before the noise.
- Not formed, "painting each stripe, a maximal run of adjacent lines with one commonest color": no branch. Under each axis rule, every line has one commonest color with no tie, so that run's commonest color is the color of each of its lines. Its cases would be equivalent to the line cases, so they would fail Equivalence.
- Not formed, "reading a line's color at one fixed cell": no branch. It fails Fit, because train1 row 0 col 7 holds 1 in the stripe of 8, and noise can stand at any cell of a line.
- Not formed, "reading the axis by how many adjacent lines share their commonest color": no branch. The item does not state one model: it does not say whether more or fewer shared neighbors win, or how a line with a tied commonest color counts.
- `$AxisStored` and `$LocalMajority`: no constructor. Both fail Fit, as `analyze.md` states, and `analyze.md` gives neither one a witness. `store` reports no derived value that is the same on every input, so `$AxisStored` has no `@store` line.
- `derive`: no built-in derivation fits. The solver has no parameters, so `sweep` and `determination-plan` report nothing to do, and the solver has no Determine comp.
- `deletions`: 10 deletions change no pair's output. Each one removes the test that the other axis fails (the concept), or the tie and count tests of `$AxisFewestChanges`. On each pair, only one axis has a majority color in every line and no tied line, so the pairs do not instantiate these tests. The witnesses `wide-stripe` and `heavy-noise-line` instantiate them. All of these deletions stay.
- `deletions` reports `axis_elem(A)` in the `$AxisMajority` clause as a bound enumerator, and it stays as the run says.
- The `@keywords` are `lines noise repair count rank`. `count` covers the majority test, and `rank` covers the commonest color and the fewest-changes axis.

## Unsettled
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
