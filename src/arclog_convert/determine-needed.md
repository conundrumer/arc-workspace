# Stored readings that need a Determine relation

A `DET_OR_RULE` line with no body has a stored reading that gives the line's proposer's values. Where the stored value is not one of them, the stored reading fits no train pair. The solver's `.dl` needs a `Determine` relation for the value, which the converter writes as the line's body (`solver.py`, "Stored gets the body, Derived its proposer"). The determination plan names a proposer that gives the value, but that proposer gives it by chance, so the converter does not write it as the body.

Each task below has such a line. Its proposer, then the plan's, are in parentheses.

- b2862040: `&hole_count`, `&min_hole_size` (TileDim, DivisorRatio). `&min_hole_size` needs a determination over all train examples: the least hole size of the recolored shapes.
- 351d6448: `&divider_color` (SharedColor, VanishedColor)
- a09f6c25: `&figure_color` (RarestColor, ChangedColor)
- a61f2674: `&bar_color` (RarestColor, ChangedColor)
- ad38a9d0: `&fg` (RarestColor, ChangedColor)
- b230c067: `&object_color` (RarestColor, ChangedColor)
- ac0c2ac3: `&bg` (DominantColor, ChangedColor)
- c3fa4749: `&min_block_cells` (ConstInDim, a type domain)

In the tasks below, the line's proposer gives the stored value on the task's inputs, so the stored reading fits without a body. The `.dl` has a `Determine` relation for the value too.

- 9ddd00f0: `&gap` (SepThickness, DivisorRatio)
- 9f41bd9c: `&comb` (RarestColor, ChangedColor)
- b548a754: `&marker_color` (RarestColor, ChangedColor)
- aaef0977: `&bg` (DominantColor, ChangedColor)
