# b7fb29bc

## Departures
- `frame_color` and `background` are Params relations, though the concept file lists them under Scene parameters: the program reads both colors to find the box, the dot and the ring cells, and literals are banned.
- The header has no `@scene empty-inside` line: no `@claim` or `@relaxed` denotes it, no rule text depends on it, and no branch replaces it (Style, Header).
- The Choice is the record `[dot_find, dot_count, region]`, with no constructor for the `ring-origin` point or the `metric` point: `$DepthRings` fails train1 and `$Diamond` fails train0, so each of those points has only its concept branch. `dot-find` and `dot-count` sit as fields beside `region`.
- `box=stored` is the `@store box` line on the Bbox instance `frame`, and the witness file names that branch `frame.box=stored`. The Analyze witness `box=stored` is renamed `frame.box=stored` and serves as that branch's witness.
- `dist_color=stored` is not held: `store` reports that the per-distance color varies by `k`, an id the runner stores nothing under, and prints no `@store` line for it. Its name is removed from every group. The Analyze witness of that id still separates the stored box from the derived one, so it stays under the id `wide-box`, with a rewritten `separates` text.
- `$AnyInkDot & $OneDot` (every region and every derive/store branch) fails Subsumption against `$AnyInkDot & $NearestDot`. Where one non-background dot is inside the box, both give the same rings. Where there is no dot or more than one, the one-dot case is undefined. `impl_choice` excludes those combinations, and `$AnyInkDot & $NearestDot` is the case that stands for the `$AnyInkDot` branch. `witness --every-case` confirms this.
- `@derive RarestColor` on `frame_color` and `@derive DominantColor` on `background` are added as branches, from `derive`. The Analyze report does not give them.

## Judgments
- `@derive RarestColor: variant derived` and `@derive DominantColor: variant derived`, each `@relaxed box-outline`: each witness is train0 with a color swapped (outline 1, or field 1). That is a color-permuted variant task, and its generator would ring the inside. The swapped color breaks the outline color or the field color that `box-outline` states.
- `@store box: variant concept`: this keeps the Analyze plausibility and verdict. A larger box is a variant task, and the generator rings its whole inside.
- Witness `ink-beside-dot` (built): train0 with a 6 at (4,5) inside the box. It shows `$FrameDot` defined and differing from `$AnyInkDot` under the stored box. It also separates `$AnyInkDot` from `frame_color=RarestColor` under the stored box. I judge it `borderline` (it breaks the concept's empty-inside reading), with a verdict of `concept`: ring the frame-color dot and keep the 6. The file records groups only.
- Chebyshev rings: a cell is on ring K of dot O when it lies on the outline of the square that reaches K cells past O on each side (`relative`, `dist`, `uniform_outset`, `compose`, `box_edge`). This states the square rings directly, with no arithmetic.
- Alternation: a `CycleWalk` over the two `ring_colors` advances one step per ring from the even color at the dot. This follows the `$Toggle` case of 97999447, so no parity number or stride width is stored.
- One dot: `Unanimous<DotFind, Position>` gives the dot only where one exists, so the concept is undefined on two dots even where the two parities agree.
- Not formed items: the stored-length color cycle has length 2 in every task of the generator, so its model is the concept's and it fails Equivalence. Ring colors derived from the input fail Fit, because 4 and 2 appear in no input. A separate `dot_color` is a redundant value of `frame_color`, so it is not a parameter. A stored outermost color fails Fit on train0 against train2. None of these was added as a case.
- `deletions`: these atoms stay. The background test in the `$EnclosedRegion` ring cells keeps a non-background cell from being painted. The `dot_dist.o` column and `the_dot.value` carry `one-dot`. `impl_choice` in the ring `out` clause keeps the dropped combinations out of `out`. The removable `dot_dist` atom in the ring color was removed, and that relation was inlined into `out`.
- Determine: `sweep` gives unique values, and `determination-plan` lists no actions. Derivations or pairs-exact enumeration cover all three parameters, so the solver has no Determine comp.

## Open
- none

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-478_task_b7fb29bc_create.md
- 10-479_task_b7fb29bc_create.md
