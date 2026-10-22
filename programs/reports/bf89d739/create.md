# bf89d739

## Departures
- `$OnePairOnly` and its witness `two-aligned-pairs` are gone from the solver and the witness file: the case fails Subsumption. It is defined only where the input has exactly one aligned pair, and there it gives the concept's output at every assignment, so no input shows it defined and differing (`witness` reported this). With it gone, `two-aligned-pairs` separated nothing. The `TrunkCount` field left `Choice` with it.
- `$TrunkSpansAll` is encoded per line, not per pair: each line that holds two dots carries a trunk across the bounding box of all the dots. This is the Analyze model. Each pair's range covers its two dots and every dot off its line. On one line, consecutive pairs share a dot, so the union of their ranges is the extent of every dot along that line. The branch's `@rule trunk` line states the per-line form. `witness --file work/task/bf89d739/witnesses.json` gives the Analyze grid for every branch. The only differences it prints are the `$OnePairOnly` names.
- The `trunk` and `branch` rules take the restated text from the Concept section of analyze.md: every pair of dots that share a line with no dot between them forms a trunk, and trunk and branch paint background cells only.

## Judgments
- Keywords `markers span cast`: the dots fix the ends, the trunk is an extent between marks, and a branch extends from a dot along a line.
- The concept's trunk cells come from a `Between` instance keyed by dot reading and axis. This follows the span-between-marks precedent of 070dd51e. `between_pair` drops the marks, which `Between` counts as between, so the landing cells of `$WithinSpan` are exactly the cells strictly between the two dots of a pair.
- `@scene one-aligned-pair` stays in the header, though no `@claim` or `@relaxed` line names it now: the `within-span` text needs it to say which pair "the pair" is.
- `$FewestCellTree`, `$FewestCellTrunk`, the `line_color` derivations, and a stored trunk axis fail Fit, as analyze.md gives. They get no constructor and no case.
- Determine: `background` is the mode of the input cells, `line_color` is the color of the cells the output changes, and `dot_color` is the input colors off the field. `determination-plan` lists no actions.
- Lint hints: `aligned` only fed `line_dot`, and `line_dot` had one consumer. Both now sit inside `line_cell`.
- Performance: the first branch clause scanned every grid cell for each pair of a dot and a landing cell. On inputs where every cell is a dot (sweep at `background` 2 or 3, `dot_color` 0), runs passed the sweep's 2 s limit. The `dot_line` relation, which gives the cells of the line through a dot, fixed this. The sweep then ran clean.
- `deletions` lists four removals that change nothing, and each stays:
    - `dot_line.a`: it states which line the branch runs on.
    - `!dot(R, P)` in `between_pair`: it makes a landing cell strictly between the pair's two dots, as the `branch` rule states. Without it, a branch can land on a dot. The cells it then paints are the trunk cells between the two dots, so no grid changes, but the model no longer states the rule.
    - `dot_line(R, A2, X, T)` in `paint`: it ties the dot to the landing cell level with it.
    - `axis_of(D, A2)` in `paint`: it states the direction along the branch.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
