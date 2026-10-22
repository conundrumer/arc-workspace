# cf133acc

## Concept
- Fits every pair (`work/task/cf133acc/probe.py`). No witness has the verdict `other`.
- The witness `bar-end-beside-pole` (ordinary) has the verdict `concept`. The concept's output is the output on it that the generator would pair with it.
- The generator applies the rule as follows. It draws full pole lines and the bars. It colors each pole segment by the bar at its lower end, and the bottom segment by the post. Then it erases each pole line except a stub at the `post-side` edge, and this leaves a gap at each crossing. The concept's rule gives the same output on every input that this generator produces.

## Choice points
- `pole-lines`
    - `concept`: the lines that hold a post at the `post-side` edge.
    - `$PolesFromGaps`: replaces `posts` and `post-grows`. The pole lines are the lines that hold a gap. A pole line with no post keeps its cells between the `post-side` edge and its nearest gap. It reads `background` and `post-side`. It is defined on every input. It fits every pair. Witness `gap-without-post`: a bar gap at col 9 with no post below it. It breaks `poles`, and it is `borderline`. It breaks the invariant that each gap line holds a post of at least one cell at the bottom edge. Verdict `$PolesFromGaps`.
        - `postless-pole`
            - `concept`: a pole line with no post keeps its cells between the `post-side` edge and its nearest gap.
            - `$PostlessPoleUndefined`: undefined on an input with a pole line that holds no post. It fits every pair. Witness `gap-without-post`, where this model is undefined. It is defined on no witness that separates it from `$PolesFromGaps`, because wherever it is defined it gives the output of `$PolesFromGaps`. The witness breaks `poles`, and it is `borderline`. It breaks the invariant that each gap line holds a post. Verdict `$PolesFromGaps`.
- `gap-shape`
    - `concept`: a gap is a `background` cell in a pole line whose two neighbors along the bar's line have one bar color.
    - `$OneSidedGap`: replaces `poles`. A gap is a `background` cell in a pole line that has a non-`background` neighbor along the bar's line on one side or on both sides. It takes the color of that neighbor. It reads `background` and `post-side`. It is undefined where the two neighbors have different non-`background` colors. It fits every pair. Witness `bar-end-beside-pole`: the bar in row 6 of the test input, extended to col 7, ends beside pole col 8. It breaks no scene claim, and it is `ordinary`. Verdict `concept`.
- `gapless-crossing`
    - `concept`: a bar that spans a pole line with no gap there is not a crossing. The color of the post or of a lower bar covers its cell.
    - `$GaplessBar`: replaces `post-grows` and `bar-color-climbs`. A non-`background` pole-line cell whose two neighbors along the line have its color is also a crossing of that color. It reads `background` and `post-side`. It is defined on every input. It fits every pair. Witness `bar-without-gap`: train0 input with row 9 col 9 set to 3. It breaks `bars`, and it is `foreign`. It breaks the invariant that every bar has a gap in each pole line it spans. Verdict `$GaplessBar`.
- `color-direction`
    - `concept`: each bar's color climbs from its gap away from `post-side`.
    - `$ColorFalls`: replaces `post-grows` and `bar-color-climbs`. Each bar's color runs toward `post-side`, from its gap to the next gap or to the post. The post keeps its cells. The cells past the gap farthest from `post-side` keep their colors. It is defined on every input. It fails Fit at train0: at row 10 col 3, it gives 2 and the output is 3.
- `post-side`
    - `concept`: stored `bottom`.
    - `$PostSideFromInput`: replaces the stored `post-side` with a derived value. On each input, `post-side` is the one edge that holds a non-`background` cell while the opposite edge holds none. It is undefined where no edge, or more than one edge, meets this condition. It fits every pair. Witness `posts-on-top`: train0 input flipped top to bottom. It breaks `poles` at the stored `bottom`, because the gaps lie in no pole line there, and it is `variant`. It breaks the invariant that the posts stand on the bottom edge in every input. Verdict `$PostSideFromInput`.
- `background`
    - `concept`: stored 0.
    - `background=DominantColor`: the commonest color of the input. It is undefined where the derivation gives no color. It fits every pair. Witness `background=DominantColor`: train0 input with 0 and 5 swapped. It breaks `background`, and it is `variant`. It breaks the invariant that the background is 0 in every input. Verdict `background=DominantColor`.
    - `background=RarestColor`: the rarest color of the input. It fails Fit at train0, where it takes 4 as the background.
    - `background=SharedColor`: on a lone input, every color of that input. It fails Fit at train0, where every bottom cell is then background, no post exists, and the output is the input.
- `pole-lines` & `gap-shape`, `pole-lines` & `gapless-crossing`, `pole-lines` & `color-direction`, `pole-lines` & `post-side`, `pole-lines` & `background`, `gap-shape` & `gapless-crossing`, `gap-shape` & `color-direction`, `gap-shape` & `post-side`, `gap-shape` & `background`, `gapless-crossing` & `color-direction`, `gapless-crossing` & `post-side`, `gapless-crossing` & `background`, `color-direction` & `post-side`, `color-direction` & `background`, `post-side` & `background`, `postless-pole` & `gap-shape`, `postless-pole` & `gapless-crossing`, `postless-pole` & `color-direction`, `postless-pole` & `post-side`, `postless-pole` & `background`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- Derivations of `background` that read train outputs (`OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`): on a lone input `ex_out` is empty, so they give no value, and every case that takes one of them is undefined on every pair.
- A separate parameter for the bars' axis: in every variant task, the bars lie perpendicular to the axis of `post-side`. Thus the axis is derived data of `post-side`.

## Tickets filed
- none
