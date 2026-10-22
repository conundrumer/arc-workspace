# b20f7c8b

## Concept
- Fits every pair (`check_concept.py`, `probe_models.py`). No witness has the verdict `other`.
- Each glyph box in the pairs shows its glyph turned or flipped, apart from one (train2 rows 8–12, cols 15–19). Train2's 3 box needs a reflection, so `match_group` is `SYM_D4`.
- Each solid box in the pairs draws its glyph as the legend shows it, including train1's 3 glyph, which has no symmetry.

## Choice points
- `legend-source`: where each color's glyph comes from
    - `concept`: read off the legend strip of each input
        - `glyph-parse`: which strip cells form one glyph
            - `concept`: all strip cells of one color
            - `$GlyphByComponent`: replaces `legend-glyphs`; a glyph is one 8-connected component of one color in the strip. It is undefined where a color has several glyphs and a solid box of that color asks for its glyph, and where a box matches glyphs of two colors. Fits every pair. Witness `shared-glyph-color` breaks `legend-glyphs` (each glyph its own color) and stands at the stored assignment. Plausibility `borderline`, verdict `$GlyphByComponent`. It breaks the invariant that the legend's glyph colors are distinct.
        - `panel_color`
            - `concept`: stored, 8
            - `$PanelColorRead`: replaces `legend-strip`'s stored color with a derived one: the commonest color of the side edge line that holds no `board_color` cell. Undefined where no such edge line, or two of them, give one color. Fits every pair. Witness `recolored-strip` breaks `legend-strip` and stands at the stored assignment. Plausibility `variant`, verdict `$PanelColorRead`. It breaks the invariant that the strip is 8.
    - `$StoredLegend`: replaces `legend-glyphs`; a stored table pairs glyphs with colors. Fails Fit at train2: color 6 pairs with one glyph in train0 and another in train2, so train2's solid 6 box gets two glyphs. Test0's glyphs are also unseen keys.
- `glyph-match`: which legend color a glyph box takes
    - `concept`: the one color whose glyph equals the box's ink under `match_group`
    - `$ExactFirst`: changes `glyph-to-solid`; the color whose glyph equals the box's ink untransformed, when there is one, and otherwise the concept's match. Undefined where no exact match exists and two colors match under `match_group`. Fits every pair. Witness `congruent-legend-glyphs` breaks `legend-glyphs` (no two glyphs the same under `match_group`) and stands at the stored assignment. Plausibility `borderline`, verdict `$ExactFirst`. It breaks the invariant that the legend glyphs are pairwise distinct under D4.
    - `$MatchByCount`: changes `glyph-to-solid`; the color whose glyph has as many cells as the box's ink. Undefined where several colors tie. Fails Fit at train0: the box at rows 8–12, cols 15–19 has 5 ink cells, as do the 4, 5 and 6 glyphs.
- `box-kind`: which boxes are glyph boxes and which are solid
    - `concept`: a box of one color is solid, and any other box is a glyph box
    - `$KindByFrame`: changes `box-forms`; a box whose border is `frame_color` is a glyph box, and any other box of one color is solid. Undefined on a box of `frame_color` alone, and on a box of several colors whose border is not `frame_color`. Fits every pair. Fails Subsumption: the concept's model gives its output wherever it is defined. Witness `solid-frame-color-box` breaks no scene claim and stands at the stored assignment. Plausibility `ordinary`, verdict `concept`.
    - `$KindByInk`: changes `box-forms`; a box that holds `ink_color` is a glyph box. Undefined on a solid box of `ink_color`. Fails Fit at train2: the solid 1 box at rows 1–5, cols 15–19.
- `board_color`
    - `concept`: stored, 0
    - `board_color=DominantColor`: replaces `legend-strip`'s stored board color with the commonest color of the input. Fits every pair. Witness `board_color=DominantColor` breaks `legend-strip` (the rest of the grid is `board_color`) and stands at the stored assignment. Plausibility `variant`, verdict `board_color=DominantColor`. It breaks the invariant that the board is 0.
- `frame-ink`: `frame_color` and `ink_color`
    - `concept`: stored, 2 and 1
    - `$BoxColorsRead`: replaces `box-forms`'s stored colors with derived ones: the frame color is the border color of the boxes of several colors, and the ink color is their other color. Undefined where no box has several colors, or where those boxes give more than one frame or ink color. Fits every pair. Witness `recolored-glyph-boxes` breaks `box-forms` and stands at the stored assignment. Plausibility `variant`, verdict `$BoxColorsRead`. It breaks the invariant that glyph boxes draw 1 on 2.
- `glyph-match` & `box-kind`, `glyph-match` & `board_color`, `glyph-match` & `frame-ink`, `glyph-match` & `legend-source`, `glyph-match` & `glyph-parse`, `glyph-match` & `panel_color`, `box-kind` & `board_color`, `box-kind` & `frame-ink`, `box-kind` & `legend-source`, `box-kind` & `glyph-parse`, `box-kind` & `panel_color`, `board_color` & `frame-ink`, `board_color` & `legend-source`, `board_color` & `glyph-parse`, `board_color` & `panel_color`, `frame-ink` & `legend-source`, `frame-ink` & `glyph-parse`, `frame-ink` & `panel_color`, `glyph-parse` & `panel_color`: the two branches' changes applied together

## Open parameters
- none

## Not formed
- `match_group` narrower than `SYM_D4` (rotations only, or the identity): the pairs separate these values of one parameter. Train2's 3 box needs a reflection of the 3 glyph, and train0's boxes need rotations.
- A solid box drawing its glyph under a stored D4 element other than the identity: the pairs separate these values of one transform. Train1's solid 3 box shows the 3 glyph, which has no symmetry, as the legend shows it.
- `panel_color`, `frame_color` or `ink_color` derived by a proposer: no single-color proposer in `programs/proposers.dl` gives 8, 2 or 1 on each input alone. 8 and 2 are the second and third commonest colors, apart from train2, where 1 outnumbers 2.

## Tickets filed
- none
