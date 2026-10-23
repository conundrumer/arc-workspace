# d8e07eb2

## Concept
- Bingo: the shapes in the top strip are called out, each called shape is ringed where it sits on the card, and the bars show whether the called shapes complete a row or a column of the card.

## Scene
- `three-panels`: two full lines of the `divider` color cut the `background` grid into three panels across one axis: a key panel, a card panel, and an empty status panel, with the card panel between the other two.
- `slot-tiling`: the card's shapes sit in square slots of side `slot_size`, laid out on a tiling whose bands on each axis are the maximal runs of card-panel lines that hold a non-background cell.
- `card`: the card panel holds `card_size` by `card_size` slots, each with one single-color shape, and no two slots of the card hold the same shape in the same color.
- `key`: the key panel holds one band of slots: its rows are the key panel's run of lines that hold a non-background cell, and its columns are the card's column bands; each key slot holds one single-color shape or nothing.
- `key-on-card`: each key shape occurs exactly once on the card, as a slot whose content equals the key slot's content: the same color at the same cells of the slot.
- `status-empty`: the status panel holds only `background`.

## Rules
- `ring-called`: for each card slot whose content equals a key slot's content, every `background` cell of the slot's box grown by `halo_margin` on each side becomes `halo_color`.
- `bingo`: the card has a line when the called slots include every slot of one card row band or of one card column band.
- `win-bars`: when the card has a line, every `background` cell of the key panel and of the status panel becomes `win_color`.
- `lose-bar`: when the card has no line, every `background` cell of the status panel becomes `lose_color`, and the key panel is unchanged.
- `rest-kept`: every other cell keeps its input color.

## Parameters
- `background`: 8
- `halo_color`: 3
- `halo_margin`: 1
- `win_color`: 3
- `lose_color`: 2

## Scene parameters
- `divider`: 6
- `slot_size`: 3
- `card_size`: 4
