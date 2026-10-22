# d8e07eb2

## Concept
- Fits every train and test pair (`work/task/d8e07eb2/check_concept.py`, and the `concept` row of `work/task/d8e07eb2/probe.py fit`).
- Every rule has a relational form: slot bands are runs of inked lines, a match is equality of slot contents, the halo is a grown box, and a line is a band whose slots are all called. No rule approximates one.
- No witness has the verdict `other`.
- The witness `shifted-key-shape` has the verdict `$UpToTranslation`. There the concept compares slot contents cell by cell, so a key shape moved within its slot calls nothing.
- The concept is undefined on any input whose two outer panels both hold ink, because it finds the status panel as the empty outer panel (witness `whole-status`).

## Choice points
- `match-color`
    - `concept`: a card slot matches a key slot only where the colors agree too
    - `$IgnoreColor`: replaces `ring-called`; the slots match where their non-background cells sit at the same places, whatever the colors. Fits every pair. Witness `ignore-color`: breaks `key-on-card`; plausibility `variant`; verdict `concept`; it breaks the invariant that each key shape is on the card in its own color.
- `match-geometry`
    - `concept`: the two slot contents are equal cell for cell
    - `$UpToTranslation`: replaces `ring-called`; the slots match where their shapes, the non-background cells with their colors, are equal up to translation. Fits every pair. Witness `shifted-key-shape`: breaks `key-on-card`; plausibility `borderline`; verdict `$UpToTranslation`; it breaks the invariant that each key shape sits at the same place in its slot as its card copy.
    - `$UpToD4`: replaces `ring-called`; the shapes are equal up to translation and a D4 transform. Fits every pair. Witness `rotated-copy`: breaks no scene claim; plausibility `variant`; verdict `concept`; it breaks the invariants that the card is the same in every input and that no two card shapes are congruent.
    - `$IgnoreShape`: replaces `ring-called`; the slots match where their colors agree, whatever the shape. Fails Fit at train0: the key's 0 block also calls the 0 shape at rows 8-10, cols 7-9.
- `key-slots`
    - `concept`: the key slots are the key panel's run of inked lines crossed with the card's column bands
    - `$KeyOwnBands`: replaces `key`; the key slots take the key panel's own column bands. Fails Fit at train0: the key's 6 shape spans only cols 18-19, so its slot holds a 3 by 2 content that no card slot equals.
- `halo-box`
    - `concept`: the slot's box grown by `halo_margin`
    - `$ShapeBboxHalo`: replaces `ring-called`; the halo is the bounding box of the slot's shape grown by `halo_margin`. Fails Fit at train0: the 6 shape at cols 13-14 leaves col 11 of rows 12-16 at 8.
    - `$HaloLatticeCell`: replaces `ring-called` and `halo_margin`; the halo is the slot's lattice cell, the box grown by half the gap between neighboring bands. Fits every pair. Witness `halo-lattice-cell`: breaks `card` at `card_size` 4; plausibility `variant`; verdict `concept`; it breaks the invariant that the card is 4 by 4 with slots 2 apart.
- `line`
    - `concept`: the called slots include every slot of one card row band or one card column band
    - `$Collinear`: replaces `bingo`; the card has a line when every called slot lies in one row band or one column band. Fits every pair. Witness `three-in-column`: breaks no scene claim; plausibility `ordinary`; verdict `concept`.
    - `$WithDiagonals`: replaces `bingo`; one of the two corner diagonals of the card also counts as a line. Fits every pair. Witness `diagonal`: breaks no scene claim; plausibility `ordinary`; verdict `concept`.
    - `$AllOnLine`: replaces `bingo`; the card has a line when the called slots are exactly the slots of one row band or one column band. Fits every pair. Witness `duplicate-slot`: breaks `card`; plausibility `borderline`; verdict `concept`; it breaks the invariant that no two card slots hold the same content.
    - `$CountWin`: replaces `bingo`; the card has a line when as many slots are called as the card has rows. Fails Fit at train2: four slots are called and the output bar is 2.
- `bar-panels`
    - `concept`: a win paints the key and status panels, a loss paints the status panel
    - `$WinStatusOnly`: replaces `win-bars`; a win paints the status panel alone. Fails Fit at train0: the key panel's background turns 3.
    - `$LoseBothPanels`: replaces `lose-bar`; a loss paints the key panel's background too. Fails Fit at train2: the key panel stays 8.
- `win-color`
    - `concept`: `win_color` stored
    - `$WinIsHalo`: derives `win_color` as `halo_color`, and replaces `win-bars`. Fits every pair. Witness `win-is-halo`, at `halo_color` 4: breaks no scene claim; plausibility `variant`; verdict `any`; the input is train0, and the divergence needs a halo color that differs from the win color, which no pair shows.
- `background`
    - `concept`: `background` stored
    - `background=DominantColor`: derives `background` as the commonest color of the input. Fits every pair. Witness `background=DominantColor`: breaks `card` at `card_size` 4; plausibility `foreign`; verdict `concept`; it breaks the invariant that the background is the commonest color.
- `halo-color`
    - `concept`: `halo_color` stored
    - `halo_color=OutNewColor`: derives `halo_color` as a color in every train output and no input. Fails Fit at train0: on an input alone `ex_out` is empty, so the derivation gives no value and the case is undefined.
- `card-source`
    - `concept`: the slot bands and the slot contents are read from the input
    - `slot_bands=stored`: stores the card's row and column bands and the key's row band, and replaces `slot-lattice`. Fits every pair. Witness `slot_bands=stored`: breaks no scene claim; plausibility `variant`; verdict `concept`; it breaks the invariant that the slot layout is the same in every input.
    - `card_slots=stored`: stores the card's slot boxes with each slot's content, and replaces `slot-lattice` and `card`. Fits every pair. Witness `card_slots=stored`: breaks no scene claim; plausibility `variant`; verdict `concept`; it breaks the invariant that the card is the same in every input.
- `key-side`
    - `concept`: the key panel is the inked outer panel and the status panel is the empty one
    - `key_side=stored`: stores the key panel as the top outer panel and the status panel as the bottom one, and replaces `three-panels`. Undefined where the top panel has no run of inked lines. Fits every pair. Witness `key_side=stored`: breaks no scene claim; plausibility `variant`; verdict `concept`; it breaks the invariant that the key panel is at the top.
        - `status-paint`
            - `concept`: the bars paint the status panel's `background` cells
            - `$WholeStatus`: replaces `win-bars` and `lose-bar`; the bars paint every cell of the status panel. Fits every pair. Witness `whole-status`: breaks `status-empty`; plausibility `foreign`; verdict `any`; it breaks the invariant that the status panel is empty. The concept is undefined on it.
- `divider-color`
    - `concept`: the dividers are the full lines of one non-background color
    - `divider_color=stored`: stores `divider` as 6, and replaces `three-panels`. Undefined where no two full lines of that color exist. Fits every pair. Witness `divider_color=stored`: breaks `three-panels` at `divider` 6; plausibility `variant`; verdict `concept`; it breaks the invariant that the dividers are 6.
- `match-color` & `match-geometry`, `match-color` & `key-slots`, `match-color` & `halo-box`, `match-color` & `line`, `match-color` & `bar-panels`, `match-color` & `win-color`, `match-color` & `background`, `match-color` & `halo-color`, `match-color` & `card-source`, `match-color` & `key-side`, `match-color` & `divider-color`, `match-geometry` & `halo-box`, `match-geometry` & `line`, `match-geometry` & `bar-panels`, `match-geometry` & `win-color`, `match-geometry` & `background`, `match-geometry` & `halo-color`, `match-geometry` & `card-source`, `match-geometry` & `key-side`, `match-geometry` & `divider-color`, `key-slots` & `halo-box`, `key-slots` & `line`, `key-slots` & `bar-panels`, `key-slots` & `win-color`, `key-slots` & `background`, `key-slots` & `halo-color`, `key-slots` & `card-source`, `key-slots` & `key-side`, `key-slots` & `divider-color`, `halo-box` & `line`, `halo-box` & `bar-panels`, `halo-box` & `win-color`, `halo-box` & `background`, `halo-box` & `halo-color`, `halo-box` & `card-source`, `halo-box` & `key-side`, `halo-box` & `divider-color`, `line` & `bar-panels`, `line` & `win-color`, `line` & `background`, `line` & `halo-color`, `line` & `card-source`, `line` & `key-side`, `line` & `divider-color`, `bar-panels` & `win-color`, `bar-panels` & `background`, `bar-panels` & `halo-color`, `bar-panels` & `card-source`, `bar-panels` & `key-side`, `bar-panels` & `divider-color`, `win-color` & `background`, `win-color` & `halo-color`, `win-color` & `card-source`, `win-color` & `key-side`, `win-color` & `divider-color`, `background` & `halo-color`, `background` & `card-source`, `background` & `key-side`, `background` & `divider-color`, `halo-color` & `card-source`, `halo-color` & `key-side`, `halo-color` & `divider-color`, `card-source` & `key-side`, `card-source` & `divider-color`, `key-side` & `divider-color`, `match-color` & `status-paint`, `match-geometry` & `status-paint`, `key-slots` & `status-paint`, `halo-box` & `status-paint`, `line` & `status-paint`, `bar-panels` & `status-paint`, `win-color` & `status-paint`, `background` & `status-paint`, `halo-color` & `status-paint`, `card-source` & `status-paint`, `divider-color` & `status-paint`: the two branches' changes applied together
- `match-geometry` & `key-slots`: under `$UpToTranslation`, `$UpToD4` and `$IgnoreShape`, a match does not read the box a key slot is cut by, so `key-slots` exists only with the concept branch of `match-geometry`
    - `$UpToTranslation` & `$KeyOwnBands`: the model of `$UpToTranslation` alone
    - `$UpToD4` & `$KeyOwnBands`: the model of `$UpToD4` alone
    - `$IgnoreShape` & `$KeyOwnBands`: the model of `$IgnoreShape` alone

## Open parameters
- none

## Not formed
- A halo color derived from the win color: it is `$WinIsHalo` with the shared parameter under the other name, an equivalent model.
- A derivation of `lose_color`: 2 occurs in the inputs, and no proposer in `programs/proposers.dl` gives it from an input alone.
- A stored `card_size`: the program reads no card size, since the bands give the slots, and `slot_bands=stored` stores the layout that a card size would fix.

## Tickets filed
- none
