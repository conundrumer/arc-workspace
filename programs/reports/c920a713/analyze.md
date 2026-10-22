# c920a713

## Concept
- Fits every pair (`probe.py` reproduces train0–2 and test0).
- train2 input (16,6) shows 9 and (16,13) shows 4, and both cells lie on outlines 4 and 9. The `layer-order` rule therefore gives the pair 4, 9 no direct order, and the closure orders it through 3 (4 < 3 < 9). This is the stack the output shows.
- The generator's rule: each outline is drawn whole, in stack order from the bottom, and covers what lies under it; one outline is above another when it was drawn later. The concept file's `layer-order` approximates this rule: an outline is the border of its color's bounding box, and the order is read from the cells that two such borders share.
- Witness `hidden-side` (verdict `other`)
    - Outline 3's top side lies wholly under outline 2's bottom side, so the box of 3's cells stops one row short. Outline 4 lies inside 3 and shows on that row.
    - The concept reads 4 over 3, and with 3 over 5 over 4 this closes a cycle, so the concept is undefined. No branch is defined on it.
    - The generator stacks 4, 5, 3, 2 from the bottom, which gives a 7×7 output with rings 4, 5, 3 and centre 2.
    - Scene claim broken: `visible-extent`.
    - Assignment: the stored one.
    - Plausibility: `borderline`.
    - Invariant of the inputs it breaks: in every input, the order read from the colors' boxes, with conflicting pairs dropped, ranks every outline with no cycle.

## Choice points
- `conflict-resolution`: how a pair of outlines is ordered when their shared cells show both colors.
    - `concept`: the pair takes no direct order, and the closure over the other pairs orders it.
    - `$KeepConflicts`: replaces `layer-order`. Each shared cell orders the pair by the color it shows, and both directions are kept. Undefined where this closes a cycle. Fails Fit at train2: cells (16,6) and (16,13) close the cycle 4 < 3 < 9 < 4.
    - `$Majority`: replaces `layer-order`. The pair is ordered by the color that more of the shared cells show, and a tie gives no direct order. Undefined where the closure has a cycle or leaves two outlines unordered. Fits every pair.
        - Witness `outvoted-crossing`: two outlines cross at four cells, three show 2 and one shows 3, and no third outline orders them.
            - Scene claim broken: `one-stack`.
            - Assignment: the stored one.
            - Plausibility: `borderline`.
            - Verdict: `$Majority`.
            - Invariant of the inputs it breaks: in every input, a pair whose shared cells show both colors is ordered through other outlines (train2: 4 and 9, through 3).
- `unordered-outlines`: the output where the stack leaves two outlines unordered.
    - `concept`: undefined.
    - `$EachExtension`: replaces `one-stack`. The output holds one grid per total order that extends the stack. Undefined where the stack has a cycle. Fits every pair.
        - Witness `apart`: two outlines share no cell.
            - Scene claim broken: `one-stack`.
            - Assignment: the stored one.
            - Plausibility: `borderline`.
            - Verdict: `$EachExtension`.
            - Invariant of the inputs it breaks: in every input, the cells the outlines share order every two outlines.
- `background`
    - `concept`: stored, 0.
    - `background=DominantColor`: derives the background as the input's commonest color. Undefined where two colors tie for commonest. Fits every pair.
        - Witness `background=DominantColor`: two overlapping outlines cover 14 of 16 cells, so the derived background is 2. The derived model then finds 0 as an outline under 3.
            - Scene claim broken: none.
            - Assignment: the stored one.
            - Plausibility: `variant`.
            - Verdict: `concept`.
            - Invariant of the inputs it breaks: in every input, the background is the commonest color.
- `conflict-resolution` & `unordered-outlines`, `conflict-resolution` & `background`, `unordered-outlines` & `background`: the two branches' changes applied together.

## Open parameters
- none

## Not formed
- Ranking the outlines by box area: this fails Fit at train0. From the bottom, the stack 5, 2, 3, 1, 7 has areas 54, 28, 30, 55, 80.
- Ranking the outlines by their count of hidden cells: this fails Fit at train0, because outlines 1 and 3 each have 2 hidden cells and the ranking leaves them unordered.
- Ordering by a visible cell of one rectangle that lies inside another's box (b7955b3c's reading): this fails Fit at train1. Cells (6,8) and (7,8) of outline 1 lie in outline 4's box, and 4's cells lie in 1's box, so the order has a cycle.
- Ordering by any cell of one color's box border that shows another color (68bc2e87's reading): each color's cells lie on its box border (`stacked-outlines`), so this reading gives the concept's evidence on every input where that color has an outline to read. Its conflict handling is `$KeepConflicts`.
- The stack as a chain in which each outline lies directly on the next: wherever no pair's shared cells conflict and the closure is total, this chain is the concept's order. On a conflict, it reads both directions as steps of the chain, which no person reads as a stack, and no solver header or proposer offers it.
- Shared collinear runs giving no order (crossings only): no person reads a shared run as saying nothing about which outline is on top, and no solver header or proposer offers it.
- Two outlines of one color: this breaks `stacked-outlines`, and their two boxes merge into one. The generator gives each outline its own color.
- Storing the stack order: the colors and the count of outlines differ in every pair.

## Tickets filed
- 10-563_task_c920a713_analyze.md
