# bda2d7a6

## Departures
- The `predecessor` point is split: `Predecessor` has the concept branch `ListCycle {order: ListOrder}` and `$EnclosingColor`, and `$CountOrder` stands under `ListOrder` beside the concept branch `FirstSeen`. The report puts `$CountOrder` and `$EnclosingColor` side by side under one point: [Choice points and open parameters](docs/handbook/principles.md#choice-points-and-open-parameters) puts a property that exists only with some branches under a branch of its own, and the order of the list exists only where a color takes the one before it in a list. The witness names are unchanged.
- The concept file's parameter `step` (1) is not stored. The program reads the color just before each color through `Order.next`, and reads the last color for the first through `first`/`last`, so the header's `cycle-colors` is restated without `params.step`. The rests: the sweep reported that the determination of `step` keeps fewer values than those the train pairs admit (1, 4 and 7), and the concept fixes the value ("the color that comes just before it"). For such a value, the Determine operation has the program derive it.
- `@store tally` stands on `others`, the count that `$RingShift` reads, with witness `others.tally=stored`, `variant concept`, `@relaxed color-cycle`. The report's Not formed item says that no rule reads `color-count`, but `$RingShift`'s rule reads it ("ring `color-count` − 1"). `store` printed no line, as no D4 image or color swap of a train input changes the count. The witness has rings 8 0 5 2: the derived count gives the outermost ring color 2, as the concept does, and a stored count of 2 gives it color 5.

## Judgments
- `$RingShift`'s ring "`color-count` − 1" is the ring whose depth equals the count of the input's colors other than the outermost ring's color. That count equals the probe's `len(first_order(seq)) - 1` on every input, and it counts things the input has, so the program uses no arithmetic. Both Analyze witnesses give the report's outputs.
- `$CountOrder` is undefined where two colors tie on count, as the report gives. With a tie, the `Order` gives some color two colors just before it, or (when every color ties) gives each color every color, so a cell gets two colors.
- `$EnclosingColor` takes the last color to appear from its own `Extremes` instance (`newest`), and does not read the `$FirstSeen` key of `order`. This keeps each case's clauses under its own marker.
- `uneven-ring` is `foreign`, because the generator draws each ring in one color. Its verdict is `concept`, because the list order is the concept's ring-by-ring order.
- `others.tally=stored` is `variant`, because a sibling task with a fourth color is routine. Its verdict is `concept`, because the concept cycles every color.
- `$StoredMapping`, `$RingRoll` and `$ReverseRings` fail Fit, as the report gives (train1, train2 and train0). They have no witness, so they have no constructor.
- Not formed `step` at other values: no branch. It is a value of a parameter, and the solver now stores no such parameter.
- Not formed stored or derived `ring-width`: not formed. No case reads a ring width. A `$RingShift` that shifts bands of a stored width is a new rule that the report does not give.
- Lint hints `case section`, which fired on the first two encodings of the shared list cycle: the hints were imprecise, because the feeding relations hold only the listed cases' keys. The present nesting draws no hint, and the solver keeps no `@ignore`.
- `deletions` reported `dir_elem(D)` in `outer_ring` as a deletion that changes nothing. In a full grid, the depths of the 8 neighbors of a cell differ from its depth by at most 1, so a deeper-to-shallower diagonal step also lands in the ring just outside. The atom was removed.
- In the first audit, the relabeling findings on `scan_corner`/`scan_axis` suggested `RIGID`. That does not apply, as no shape is stored. The findings left once `scan` was made open and `uneven-ring` separated the scans. The last audit is clean.
- Determine: the solver has no `Determine` comp. The plan lists no actions, and the train pairs give `scan`, as the set of values at which the model fits every train pair.
- Keywords `rings rank permutation mapping count`: `count` is there for `$CountOrder`.

## Open
- Whether a sibling task turns the cycle outward, which would make the place offset task data again (the dropped `step`): a variant task of this generator would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-611_task_bda2d7a6_create.md
