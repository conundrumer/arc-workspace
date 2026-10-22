# cad67732

## Concept
- A repeating pattern runs along a diagonal of the grid; make the grid larger and continue the pattern along that diagonal to the new far corner.

## Scene
- `diagonal-band`: a square grid of `background` holding a band of colored cells along one corner-to-corner diagonal, either the main diagonal or the anti-diagonal.
- `periodic-band`: the band repeats under a translation of some number of cells along its diagonal, the period, wherever both cells lie in the grid.

## Rules
- `scaled-frame`: the output is `scale` times the input's extent on each axis.
- `anchored-input`: the input sits in the output at the corner where the band's diagonal meets the `anchor-edge` edge.
- `continue-band`: each output cell takes the color of the cell a whole number of periods back along the band toward the anchored input, where that cell lies in the input; a cell that no such input cell reaches is `background`.
- `least-period`: the period is the least positive translation along the band's diagonal under which the input is unchanged where both cells lie in the grid.

## Parameters
- `scale`: 2
- `background`: 0
- `anchor-edge`: `T`, `L`
    - the output edge the input touches; with the band's diagonal it gives the corner the input sits at

## Scene parameters
- none
