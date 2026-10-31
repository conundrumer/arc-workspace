# ddf7fa4f

## Departures
- The case `$Span($FirstHit(), $NoFill())` (the `$FirstHit` branch's model) is left out of `impl_choice`, so the name `$FirstHit` stands for the cases with `$FirstHit` and `$KeepUnmarked` or `$NearestMarker`: it fails Subsumption. `witness` found no input where it is defined and differs from `$FirstHit` & `$KeepUnmarked`. Where every block is reached, the two give the same output.
- The case `$Span($AllHit(), $NearestMarker())` (the `$NearestMarker` branch's model) is left out of `impl_choice`, so the name `$NearestMarker` stands for `$FirstHit` & `$NearestMarker`: it fails Subsumption against `$FirstHit` & `$NearestMarker`. `$FirstHit` reaches a subset of the blocks that `$AllHit` reaches. Where `$AllHit` is defined, a block that `$FirstHit` leaves unreached holds its one marker in its span at gap 0, so the nearest marker is that marker.
- Because of these two removals, `witness --file programs/reports/ddf7fa4f/witnesses.json` reports `$FirstHit` and `$NearestMarker` as names of models that are no case of the solver. It reports no other difference.
- New witness `two-block-colors` (borderline, verdict `$AnyBlockColor`, `@relaxed blocks`): train0 input with its 2-wide block in 3. It separates `$AnyBlockColor`, which recolors the 3 block too, from `$BlockColorFromField`, which takes 5 as the block color and keeps the 3 block. `witness` reported that no witness separated these two cases. A person who sees blocks of two colors would recolor all of them, so the verdict is `$AnyBlockColor`. Blocks of a second color are unusual for the generator, so the plausibility is borderline.
- `$StoredColorMap` and `$Adj8` have no constructor: they fail Fit, as `analyze.md` states.

## Judgments
- `bg=DominantColor` is a `@derive DominantColor` line on `bg`, not a constructor. `derive` gives it. `store` gives no line to add.
- `$BlockColorFromField` and `$EdgeFromMarkers` are constructors with clauses of their own: no built-in proposer gives the commonest non-bg color or the marker edge.
- `Reach` was renamed `Hit`, because `Reach` is a lib component.
- `$Rank`'s rank side is not a parameter. It is derived as both `perp_dir` values of the marker edge, which is the "every value" form, and the case is undefined where the two sides give different colors.
- `$NearestMarker`'s gap is `dist` of the `relative` offset between the marker's place and a span place along the line, kept where it is `>= 0`. This is a distance count, not arithmetic.
- Hints: the single-consumer hint on `assigned` and the pass-through hint on `rank_bad` were taken, and both relations were inlined. The case-section hint was taken, and a `$MarkerLine & $AnyBlockColor` marker was added.
- Deletions: `first_hit.cell` was removed, because `Ray.stop` does not read the domain. The other no-change deletions are guards for undefined outputs (ties, multi-hits, rank mismatch, `broken`) or structure of branches that the pairs never use. They stay.
- Determination: `bg` (commonest color of every input that has an output) and `block_color` (the input color of every changed cell) have determination relations. `marker_edge` has none, because no proposer derives it. The fit over the enumerable domain gives `DIR_T`.
- Keywords: `markers objects rank cast`. `rank` is for `$Rank` and `cast` is for `$FirstHit`.

## Unsettled
- `marker_edge` has no determination relation of its own: a relation that reads the edge from the inputs (the edge whose line holds the markers) would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
