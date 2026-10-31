# f0100645

## Departures
- `$CollideOpposite` has no case, and the witness `opposite-cross` is gone from the witness file: the branch fails Relational form. Its rule moves bodies of both headings one cell per step together, and a body stops against a body of the other heading. That rule needs a step-by-step simulation across the two headings, which is recursion. The program bans recursion. `Gravity` takes one heading per key, and no lib relation states a joint slide of bodies with opposite headings. Once that branch was gone, `opposite-cross` separated no remaining case.
- `$StoredAxis` has no case, and the witness `$StoredAxis` is gone from the witness file: the branch stores a derived value, the wall axis. `store` reports `wall_axis` with "no witness" and prints no line to add. Per Develop, `wall_axis` carries a `@workaround` line in place of a `@store` line. With no case for the branch, the witness separated nothing. `analyze.md` also has this branch failing Subsumption.
- `background=DominantColor` is a `@derive DominantColor: variant derived` line on `background`, with `@relaxed background`. It is not a constructor. Its witness keeps the id `background=DominantColor`.
- The concept constructor is `Erase`, and the concept branch of `stray-blocking` is `PassOver`. `record --all` rewrote the witness groups. `$StrayStays`'s own model is now named `$PassOver`, and the concept's group on `background=DominantColor` is named `$Erase & background=stored`.
- The header leaves out `@scene shapes-clear-of-walls`: no `@claim` or `@relaxed` line uses it, no rule text depends on it, and no branch replaces it (Style, Header).

## Judgments
- Hint single-consumer on `wall_axis`: kept with `@ignore`. It is the value that a stored wall axis would replace, and the `@workaround` line marks it.
- Hint common-subexpr on the two `$StrayStays` `out` clauses: they were merged into one clause with a disjunction.
- Determination plan: `background (DominantColor exact)`. The concept reads the background as the field color that is no wall color, which is a fact other than the commonest color. `Determine.background` keeps a color that is a non-wall field color in every input. The wall-edge derivation that the program and `Determine` share moved into `Parse<Key>` (`edge_defect`, `edge_color`, `wall_pair`). The second plan run: no actions, `background` determined.
- `Gravity` is keyed by `[Choice, Color]` (`FallKey`): each wall color has one heading, and `$StrayBlocks` adds stray cells to `blocked` at its own key.
- `field` requires both walls on the wall axis, so every case is undefined on an input with no wall pair, as `analyze.md` gives for the concept.
- Deletions: 22 deletions change nothing on the pairs. Each one removes a guard for structure that the pairs do not have: stray cells, a uniform edge line off the wall axis, wall cells inside the node set, a field color that some input lacks. The guards stay.
- Develop step 3: no Not formed item states a model that an input separates, so none became a branch.

## Unsettled
- `wall_axis` `@workaround`: a `@store` line on it, once `store` prints one. Then `$StoredAxis` would get a case, which is then likely to leave under Subsumption, as `analyze.md` gives.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
