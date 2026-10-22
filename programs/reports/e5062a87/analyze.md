# e5062a87

## Concept
- Fits every pair, train and test: the translates of the red template that lie wholly on black cells are two in train0, three in train1 and two in test0, and in each pair they share no cell.
- No witness has the verdict `other`. The concept rule has a relational form, and the generator applies it as `stamp-every-fit` states it: every translate of the template that lies wholly on hole cells takes the shape color.
- The variant-C patch keeps only inputs whose fits are disjoint and definite, which is the scene claim `placements-disjoint`. What the generator does where fits overlap is the `overlapping-fits` point.

## Choice points
- `copy-orientations`: which transforms of the template are copied
    - `concept`: the template's own orientation only
    - `$MirrorCopies`: replaces `stamp-every-fit`: copies also include the template mirrored across a stored axis; parameter `mirror_axis`: AXIS_V (the flip D4_TB), the one value that fits both train pairs, since AXIS_H (D4_LR) fails train1; defined wherever the concept is. Fits every pair. Witness `mirrored-hole`: a hole shaped like the template flipped top to bottom; breaks no scene claim; stored assignment; `ordinary`, verdict `concept`.
    - `$TurnedCopies`: replaces `stamp-every-fit`: copies under every element of D4. Fails train0: the bar turned upright fits in col 5, rows 0–4.
    - `$RotatedCopies`: replaces `stamp-every-fit`: copies under every rotation (C4). Fails train0, at col 5 as `$TurnedCopies` does.
    - `$HalfTurnCopies`: replaces `stamp-every-fit`: copies under the identity and the half turn. Fails train1: the half-turned L fits at (7,4), (7,5), (8,5), (9,5).
    - `$DiagMirrorCopies`: replaces `stamp-every-fit`: copies also include the template mirrored across a stored diagonal axis. Fails train0 at both diagonal axes: the transposed bar fits in col 5.
- `frame-clipping`: whether a copy must lie wholly in the frame
    - `concept`: a copy lies wholly in the frame
    - `$ClippedCopies`: replaces `stamp-every-fit`: a translate that the frame edge cuts is a fit when its cells inside the frame are all black. Fails train0: the bar cut at the left edge fits at (0,0), which stays black.
- `seat`: which cells a copy may cover
    - `concept`: cells of the hole color
    - `$NonFieldSeat`: replaces `stamp-every-fit`: a copy may cover any cell that is neither of the field color nor of the shape color; parameter `field_color`: 5, the one value that fits the train pairs, and `hole_color` is not read; defined wherever the concept is. Fits every pair. Witness `third-color`: a green cell ends a run of three black cells; breaks `field-with-holes`; stored assignment; `borderline`, verdict `concept`; breaks the invariant that every input holds only gray, black and red.
        - `field_color`: how the field color is set
            - `concept`: stored
            - `field_color=DominantColor`: the field color is the commonest color of the input; undefined where two colors tie for it. Fits every pair. Witness `field_color=DominantColor`: black outnumbers gray, so the derivation takes black as the field and no copy fits; breaks no scene claim; stored assignment; `borderline`, verdict `concept`; breaks the invariant that gray is the commonest color.
    - `hole_color` (under `concept`): how the hole color is set
        - `concept`: stored, 0
        - `hole_color=DominantColor`: the commonest input color, 5. Fails train0.
        - `hole_color=RarestColor`: the rarest input color, 2. Fails train0.
        - `hole_color=SharedColor`: every color in the input, so every cell is a seat. Fails train0.
- `seat-on-template`: whether a copy may cover template cells
    - `concept`: no
    - `$SeatOnShape`: replaces `stamp-every-fit`: a copy may also cover cells of the shape color; defined wherever the concept is. Fits every pair. Witness `fit-over-template`: a black cell at (5,0) beside the bar; breaks no scene claim; stored assignment; `ordinary`, verdict `concept`.
- `region-match`: which fits count
    - `concept`: every fit
    - `$ExactRegion`: replaces `stamp-every-fit`: only a fit whose cells are a whole 4-connected region of hole cells. Fails train0: the black region holding row 1, cols 3–6 also holds col 5, rows 0–4.
    - `overlapping-fits` (under `concept`): what fits that share cells paint
        - `concept`: the union of all fits
        - `$ExclusiveFits`: replaces `stamp-every-fit`: only fits that share no cell with another fit paint; defined wherever the concept is. Fits every pair. Witness `overlapping-fits`: a run of five black cells, row 1 cols 3–7; breaks `placements-disjoint`; stored assignment; `borderline`, verdict `concept`; breaks the invariant that the fits of the template in each input share no cell.
        - `$ForcedFits`: replaces `stamp-every-fit`: only the fits that every exact cover of the hole cells by fits contains; undefined where no cover exists. Fails train0: (0,0) is a black cell that no fit covers, so no cover exists.
- `footprint-source`: where the footprint comes from
    - `concept`: the template in the input
    - `footprint=stored`: replaces `stamp-every-fit`: a stored footprint. Fails train1: no footprint fits both train pairs, since the train0 bar fails train1 and the train1 L fails train0.
    - `footprint-unit` (under `concept`): what one footprint is
        - `concept`: all cells of the shape color together
        - `$PerObject`: replaces `one-shape` and `stamp-every-fit`: each 4-connected component of the shape color is its own footprint and stamps at its own fits; defined wherever the concept is. Fits every pair. Witness `two-templates`: a second red bar at row 8, cols 5–8; breaks `one-shape`; stored assignment; `borderline`, verdict `$PerObject`; breaks the invariant that every input holds one red drawing.
            - `object-adjacency` (under `$PerObject`): how template cells join into one object
                - `concept`: 4-adjacency
                - `$Join8`: diagonal neighbors join as well; defined wherever `$PerObject` is. Fits every pair. Witness `diagonal-template`: the template is a vertical domino plus a cell that touches it at a corner only; breaks `one-shape`; stored assignment; `borderline`, verdict `$Join8`; breaks the invariant that the red cells are 4-connected.
- `template`: what happens to the template
    - `concept`: kept (`rest-kept`)
    - `$EraseTemplate`: replaces `rest-kept`: the template cells turn black. Fails train0.
- `paint-color`: the color of the copies
    - `concept`: the shape color
    - `paint_color=stored`: replaces `stamp-every-fit`: a stored paint color apart from the shape color, stored as 2. Fits every pair. Witness `paint_color=stored`: train0's input; breaks no scene claim; stands at `paint_color` 3; `ordinary`, verdict `concept`.
- `shape_color`: how the shape color is set
    - `concept`: stored, 2
    - `shape_color=RarestColor`: the rarest color of the input; undefined where colors tie. Fits every pair. Witness `shape_color=RarestColor`: a 3×4 grid in which gray is rarer than the red bar; breaks no scene claim; stored assignment; `borderline`, verdict `concept`; breaks the invariants that every input is 10×10 and that gray is the commonest color and red the rarest.
    - `$ThirdColorShape`: the shape color is the one input color other than the field color and the hole color; reads `field_color`, 5; undefined where there is not exactly one such color. Fits every pair. Witness `recolored-shape`: train0's input with the template drawn in green; breaks `field-with-holes` and `one-shape`; stored assignment; `variant`, verdict `$ThirdColorShape`. The rarest-color derivation gives the same output there.
    - `shape_color=DominantColor`: the commonest input color, 5. Fails train0.
    - `shape_color=SharedColor`: every color in the input. Fails train0.
- `copy-orientations` & `frame-clipping`, `copy-orientations` & `seat`, `copy-orientations` & `seat-on-template`, `copy-orientations` & `region-match`, `copy-orientations` & `footprint-source`, `copy-orientations` & `template`, `copy-orientations` & `paint-color`, `copy-orientations` & `shape_color`, `copy-orientations` & `hole_color`, `copy-orientations` & `field_color`, `copy-orientations` & `overlapping-fits`, `copy-orientations` & `footprint-unit`, `copy-orientations` & `object-adjacency`, `frame-clipping` & `seat`, `frame-clipping` & `seat-on-template`, `frame-clipping` & `region-match`, `frame-clipping` & `footprint-source`, `frame-clipping` & `template`, `frame-clipping` & `paint-color`, `frame-clipping` & `shape_color`, `frame-clipping` & `hole_color`, `frame-clipping` & `field_color`, `frame-clipping` & `overlapping-fits`, `frame-clipping` & `footprint-unit`, `frame-clipping` & `object-adjacency`, `seat` & `seat-on-template`, `seat` & `region-match`, `seat` & `footprint-source`, `seat` & `template`, `seat` & `paint-color`, `seat` & `overlapping-fits`, `seat` & `footprint-unit`, `seat` & `object-adjacency`, `seat-on-template` & `region-match`, `seat-on-template` & `footprint-source`, `seat-on-template` & `template`, `seat-on-template` & `paint-color`, `seat-on-template` & `shape_color`, `seat-on-template` & `hole_color`, `seat-on-template` & `field_color`, `seat-on-template` & `overlapping-fits`, `seat-on-template` & `footprint-unit`, `seat-on-template` & `object-adjacency`, `region-match` & `footprint-source`, `region-match` & `template`, `region-match` & `paint-color`, `region-match` & `shape_color`, `region-match` & `hole_color`, `region-match` & `field_color`, `region-match` & `footprint-unit`, `region-match` & `object-adjacency`, `footprint-source` & `template`, `footprint-source` & `paint-color`, `footprint-source` & `shape_color`, `footprint-source` & `hole_color`, `footprint-source` & `field_color`, `footprint-source` & `overlapping-fits`, `template` & `paint-color`, `template` & `shape_color`, `template` & `hole_color`, `template` & `field_color`, `template` & `overlapping-fits`, `template` & `footprint-unit`, `template` & `object-adjacency`, `paint-color` & `shape_color`, `paint-color` & `hole_color`, `paint-color` & `field_color`, `paint-color` & `overlapping-fits`, `paint-color` & `footprint-unit`, `paint-color` & `object-adjacency`, `shape_color` & `hole_color`, `shape_color` & `field_color`, `shape_color` & `overlapping-fits`, `shape_color` & `footprint-unit`, `shape_color` & `object-adjacency`, `hole_color` & `overlapping-fits`, `hole_color` & `footprint-unit`, `hole_color` & `object-adjacency`, `field_color` & `overlapping-fits`, `field_color` & `footprint-unit`, `field_color` & `object-adjacency`, `overlapping-fits` & `footprint-unit`, `overlapping-fits` & `object-adjacency`: the two branches' changes applied together
- `seat` & `shape_color`: the derived shape colors apply together with `$NonFieldSeat`; the seats exclude the derived shape color.
    - `$NonFieldSeat` & `$ThirdColorShape`: copies may cover any cell that is neither of the field color nor of the shape color, and the shape color is the one input color other than the field color and the stored hole color. In this case `hole_color` is read by the shape-color derivation alone, so the `hole_color` point reaches this case too.
- `hole_color` & `field_color`: the two points stand under different branches of `seat`, so only a case with `$ThirdColorShape`, which reads both colors, takes a branch of each. There their changes apply together.

## Open parameters
- none

## Not formed
- A packing that keeps one of each set of overlapping fits in a fixed order: the order reads an orientation, such as a scan corner, and the task distinguishes none.
- Copies under each other D4 subgroup as a stored `Sym`: each subgroup gives the model of a listed `copy-orientations` branch, or fails Fit. SYM_TB is `$MirrorCopies`. SYM_LR, SYM_HT and SYM_BOX fail train1. SYM_DG, SYM_AD, SYM_X, SYM_C4 and SYM_D4 fail train0.
- Derivations of the hole, shape or field color by the proposers that read train outputs (`OutNewColor`, `AnyOutNewColor`, `VanishedColor`, `ChangedColor`, `UnchangedColor`, `ChangedPairs`, `VanishedNewPairs`): under `@derive`, `ex_out` is empty on an input alone, so they give no value and the branch would be undefined on every input.
- Derivations by `CountRankAsc` and `CountRankDesc`, and by the dimension, ratio, tile and period proposers: they give a rank per color or a number, and none of them gives a color.
- `$ExactRegion` with 8-connected hole regions: those regions contain the 4-connected ones, so this fails train0 at the same region.

## Tickets filed
- none
