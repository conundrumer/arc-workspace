# c0f76784

## Concept
- Fits every pair at `fill_by_side` 1 → `6`, 2 → `7`, 3 → `8`, and every test key is a train key. Every claim has a relational form: the holes are the `background` cells that no 4-step walk through `background` reaches from the grid edge (`Closed`), and a hole's side is read off its cells. No witness has the verdict `other`. Each branch below fits every pair, and each has a witness on which its model is defined and parts from the concept case and from each other branch, so no two models are equivalent and no branch's model is subsumed by another's.

## Choice points
- `hole-measure`: what of a hole keys the fill table
    - `concept`: the side of the hole; undefined on a hole that is not a solid square, or whose side is no key of `fill_by_side`
    - `$KeyByArea`: replaces `fill-hole-by-side` and `hole-sizes-keyed`; the hole's cell count keys `fill_by_area` 1 → `6`, 4 → `7`, 9 → `8`; undefined where a hole's cell count is no key. Fits every pair. Witness `hole-1x4` (one 1×4 hole): breaks `square-outlines`, at the stored assignment, `borderline`, verdict `any`; it breaks the invariant that every hole in the evidence is a solid square.
    - `$KeyByMinSide`: replaces `fill-hole-by-side` and `hole-sizes-keyed`; the shorter side of the hole's bounding box keys `fill_by_side`; undefined where it is no key. Fits every pair. Witness `hole-2x3` (one hole 2 rows by 3 columns), on which it fills 7: breaks `square-outlines`, at the stored assignment, `borderline`, verdict `any`; it breaks the invariant that every hole is a solid square.
    - `$KeyByMaxSide`: replaces `fill-hole-by-side` and `hole-sizes-keyed`; the longer side of the hole's bounding box keys `fill_by_side`; undefined where it is no key. Fits every pair. Witness `hole-2x3`, on which it fills 8: as for `$KeyByMinSide`.
    - `$KeyByOutlineSide`: replaces `fill-hole-by-side` and `hole-sizes-keyed`; the side of the `frame_color` object that borders the hole keys `fill_by_outline_side` 3 → `6`, 4 → `7`, 5 → `8`, and the program reads `frame_color`; undefined where that object's bounding box is not square, or its side is no key. Fits every pair. Witness `thick-outline` (a two-cell-thick 5×5 outline around a 1×1 hole), on which it fills 8 and the concept case fills 6: breaks `square-outlines`, at the stored assignment, `borderline`, verdict `concept`; it breaks the invariant that every outline is one cell thick.
        - `outline-measure`
            - `concept`: `$KeyByOutlineSide`
            - `$KeyByOutlineCount`: the cell count of that object keys `fill_by_outline_count` 8 → `6`, 12 → `7`, 16 → `8`; undefined where the count is no key. Fits every pair. Witness `corner-touch` (two 3×3 outlines touching at a corner), on which the merged outline's 16 cells fill both holes 8 and `$KeyByOutlineSide` is undefined: breaks `outlines-apart`, at the stored assignment, `foreign`, verdict `concept`; it breaks the invariant that no two outlines touch.
        - `outline-adjacency`: the same point as under `$FillBboxInterior`; a case that takes both branches reads one adjacency
            - `concept`: 8-adjacent `frame_color` objects
            - `$OutlineAdj4`: 4-adjacent `frame_color` objects. Fits every pair. Witness `corner-touch`, on which `$KeyByOutlineSide & $OutlineAdj4` and `$KeyByOutlineCount & $OutlineAdj4` give the concept case's output: breaks `outlines-apart`, at the stored assignment, `foreign`, verdict `concept`; it breaks the invariant that no two outlines touch.
- `fill-key`: what the fill table is keyed by
    - `concept`: the measure itself
    - `$RankBySize`: replaces `fill-hole-by-side`; the dense rank of the hole sides, largest first, keys `fill_by_rank` 0 → `8`, 1 → `7`, 2 → `6`; undefined where a hole is not a solid square or a rank is no key. Fits every pair. Witness `rank-two-sizes` (holes of side 1 and 2 only), on which it fills 7 and 8 and the concept case fills 6 and 7: breaks no scene claim, at the stored assignment, `ordinary`, verdict `concept`.
- `hole-region`: which cells form a hole
    - `concept`: the `background` cells that no 4-step walk through `background` reaches from the grid edge
    - `$Enclose8`: replaces `fill-hole-by-side`'s hole with the `background` cells that no 8-step walk through `background` reaches from the grid edge. Fits every pair. Witness `corner-gap` (a 4×4 outline missing one corner cell), on which it fills nothing and the concept case fills 7: breaks `square-outlines`, at the stored assignment, `foreign`, verdict `concept`; it breaks the invariant that every outline is closed.
    - `$WallsOfFrameColor`: the hole is the `background` cells of a region that no walk through cells other than `frame_color` reaches from the grid edge, and the program reads `frame_color`. Fits every pair. Witness `third-color-outline` (a 3×3 outline in `3` beside a 4×4 outline in `5`), on which it leaves the `3` outline's hole unfilled and the concept case fills it 6: breaks `square-outlines`, at the stored assignment, `foreign`, verdict `concept`; it breaks the invariant that every input holds only `0` and `5`.
    - `$FillBboxInterior`: the hole is the `background` cells inside each `frame_color` object's bounding box, one cell in from its edge, and the program reads `frame_color`. Fits every pair. Witness `broken-outline` (a 4×4 outline with a gap in its top side), on which it fills the 2×2 interior 7 and the concept case leaves it unfilled: breaks `square-outlines`, at the stored assignment, `foreign`, verdict `concept`; it breaks the invariant that every outline is closed.
        - `outline-adjacency`: the same point as under `$KeyByOutlineSide`
            - `concept`: 8-adjacent `frame_color` objects
            - `$OutlineAdj4`: 4-adjacent `frame_color` objects. Fits every pair. Witness `corner-touch`, on which `$FillBboxInterior` is undefined and `$FillBboxInterior & $OutlineAdj4` gives the concept case's output: breaks `outlines-apart`, at the stored assignment, `foreign`, verdict `concept`; it breaks the invariant that no two outlines touch.
- `hole-measure` & `fill-key`, `hole-measure` & `hole-region`, `fill-key` & `hole-region`, `outline-measure` & `fill-key`, `outline-measure` & `hole-region`, `outline-adjacency` & `fill-key`, `outline-adjacency` (under `$FillBboxInterior`) & `hole-measure`, `outline-adjacency` (under `$KeyByOutlineSide`) & `hole-region`: the two branches' changes applied together; the rank of `$RankBySize` ranks the measure that `hole-measure` takes

## Not formed
- The fill color as `5` plus the hole's side: colors have identity and no other properties, so arithmetic on a color has no relational form.
- An ascending rank under `$RankBySize`: the order is a value of that branch's stored order, and ascending fails Fit at train2, whose holes of side 2 and 3 it would fill 6 and 7 where the pair fills 7 and 8.

## Tickets filed
- 10-494_task_c0f76784_analyze.md
- 10-495_task_c0f76784_analyze.md
