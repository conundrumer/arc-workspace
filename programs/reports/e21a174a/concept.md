# e21a174a

## Concept
- The picture is a stack of layers, one color each; turn the stack upside down, keeping each layer's own picture upright.

## Scene
- `background`: every cell that is not part of a layer has the color `background`.
- `color-layers`: the cells of each non-background color form one layer, and that layer may be disconnected.
- `disjoint-bands`: along `stack_axis`, each layer spans a band of lines, and no line holds cells of two layers.
- `packed-stack`: the bands follow one another along `stack_axis` with no empty line between them.

## Rules
- `reverse-order`: each layer's band moves to its mirror image within the span the stack holds along `stack_axis`, so the layers come in reverse order and the stack keeps its place.
- `layer-kept`: each layer keeps its own picture unchanged, with no flip, and keeps its place on the other axis.
- `rest-background`: every other cell of the output is `background`.

## Parameters
- `background`: 0
- `stack_axis`: V
    - the axis along which the layers are stacked

## Scene parameters
- none
