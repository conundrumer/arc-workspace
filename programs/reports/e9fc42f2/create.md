# e9fc42f2

## Departures
- The concept is undefined where two connectors of one color lie on one piece (`joined_in_place`): `witnesses.json` gives the concept as undefined on `bg=DominantColor` and `pair-on-one-piece`, and before the fix the solver gave grids there. With the fix, the run against `witnesses.json` matches every group.
- The witness id and the group name `background=DominantColor` are now `bg=DominantColor`: that is the name [Witness file](docs/handbook/solver-file.md#witness-file) gives the `@derive DominantColor` line on `bg`.
- Three witnesses were added (`dense-body`, `corner-touch`, `corner-touch-field-2`), and `diagonal-cell-field` was built. `witness` reported cases that no run separated: `bg=stored` against `bg=DominantColor` among the `$EightConnected` cases, and `$FourConnected` against `$EightConnected` among the `$NoOverlapJoin` and `bg=DominantColor` cases. Some input separates each of these pairs, and each new witness shows one. None of them has a `@witness` line. The verdict for `diagonal-cell-field` and `corner-touch` is `$EightConnected & bg=DominantColor` and `concept & bg=DominantColor`, both `borderline`, because they break `field` (the field is 5). The verdict for `dense-body` is `concept`, `variant` plausibility (a 9×4 grid where the body outnumbers the field). For `corner-touch-field-2` it is `concept`, `borderline`, because two pieces touch at a corner.

## Judgments
- The branches are `$Snap{$Translate | $TurnToFace}` and `$NoOverlapJoin` at `join-placement`, `$FourConnected | $EightConnected`, `$AnyColor | $StoredConnectorColors`, and `@derive DominantColor` on `bg`. `connector-facing` and `piece-motion` stand under the concept branch of `join-placement`, because the facing they turn on exists only there. `$FreeNeighborSide`, `$MergeConnectors`, `$DropUnpaired` and `$InPlace` fail Fit, as `analyze.md` gives, and have no constructor.
- The assembly is a Propagation over placements `[piece, turn, shift]`, with every cell taken as an offset from an origin connector. A turn is applied to offsets, so it does not depend on the frame's shape. The edges range over the translations between two cells of the input frame. That bound is the finite domain the closure needs, since recursion is banned.
- The origin is every connector under `$Translate` and `$NoOverlapJoin`, where the choice of root changes no output. It is each connector of a piece with the most cells under `$TurnToFace`, as that branch's rule states.
- `$NoOverlapJoin` resolutions are a `TiebreakResolutions` over pair colors. Each item is `[color, connector nearer the origin, direction]`, with "nearer" taken from a GraphDistance tree. An item means the same assembly from any origin, so one resolution gives one grid. An Ident comparison would have given an unordered pair one description, but the lint's `typed-order` finding does not accept an `@ignore` line.
- The identity turn is written as `d4_compose(T, T, T)` and is not stored in Params. Writing it through a `no_turn` relation drew the `alias-inline` finding.
- `head-repeat` on `join_step` is ignored. Under `$Translate` and `$NoOverlapJoin`, a piece takes the turn of the piece it joins.
- Determination: `bg` is the commonest color of every input, and `body` is the commonest color of every input's non-`bg` cells (Mode). `connector` has no clauses that read it from the evidence, and the sweep leaves it to the fit set.
- Deletions: the 27 deletions that change nothing remove structure the pairs never instantiate (`incomplete`, `joined_in_place`, the `$TurnToFace` origin) or columns that another column implies. The witnesses need the first two, so the solver keeps them.

## Unsettled
- The audit's relabeling check timed out (20 s), and `store` did not check `asm.edge` (over 20000 rows). A faster assembly encoding would settle both.
- Develop step 5 `store` was not run, because the pairs run took 30 s or more. The audit's store report found no line to add.
- The translation domain is the offsets between two cells of the input frame. An assembly whose pieces need a larger translation from the origin is cut off, so it is incomplete and the model is undefined there. No pair or witness reaches that bound. A lib construction for a closure over sums of offsets would settle it.

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
- none
