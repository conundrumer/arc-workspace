# b91ae062

## Departures
- The witness file has no group for `background=SharedColor` or `background=RarestColor`: the Analyze report finds both equivalent to `background=DominantColor` and failing Equivalence, `derive` lists only DominantColor, and `witness` lists no case for either name. Each is recorded as an `@ignore: derive` line on `background`.
- The `small-grid` scene claim and its `size` parameter are left out of the header: no `@claim` or `@relaxed` line names it, no rule text depends on it, and no branch replaces it.

## Judgments
- Choice is `Count` (the concept branch of `count-to-scale`) | `ScaleTable`. That point is not nested under `scale-source`, because `$ConstScale` fails Fit and has no witness. `$AllColorCount` and `$CellCount` also fail Fit and get no constructor.
- `ScaleTable & background=DominantColor` is not a witnessed case. Every verdict on both branches is `concept`, so an output that only this combination gives does not witness it.
- Not formed (counts of same-color objects under 4- or 8-adjacency, of all objects, and of occupied rows or columns): rerunning `work/task/b91ae062/probe_counts.py` confirms that no such count gives k on every pair, either as the identity or through a table. So no case was added.
- `store` printed no `@store` line to add. It reports that no witness exists for `block.extent`.
- Sweep: the train pairs leave rows of `scale_by_count` for unseen counts unpinned. These rows are not open values, because the table holds only the counts the pairs show. No value was added.
- `scale_by_count` is determined from each example's output extent cut into as many parts as the input has lines. It reads `ex_out`, so only examples with outputs contribute. The palette tally moved into `Parse` and is shared by the program and `Determine`.
- Deletions: `ex_out(E, _, _)` in `Determine`'s `parse.cell` was redundant, because the `scale_by_count` clause already joins `ex_out`. It was removed.
- Lint gave no hints. The run passes all pairs with 3 witnessed cases. Audit, `witness`, and determination are ok.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
