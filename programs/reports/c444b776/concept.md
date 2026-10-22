# c444b776

## Concept
- Lines cut the grid into equal panels, and one panel holds a drawing: copy that drawing into every panel.

## Scene
- `divider-lines`: full rows and full columns of the `divider` color cut the grid into equal panels, with no divider on the grid edge.
- `one-drawn-panel`: exactly one panel holds cells other than the `background` color, and every other panel is all `background`.
- `drawing-avoids-divider`: no cell inside a panel has the `divider` color.

## Rules
- `copy-to-every-panel`: each panel of the output is the drawn panel of the input, and the divider lines stay as they are.

## Parameters
- `divider`: `4`
- `background`: `0`

## Scene parameters
none
