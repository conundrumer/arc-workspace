# ba97ae07

## Concept
- Two straight bands cross, one over the other; swap which band lies on top at the crossing.

## Scene
- `background`: every cell outside the two bands is `background`.
- `two-crossing-bands`: one vertical band of whole columns and one horizontal band of whole rows, each of one color other than `background`, the two colors different, cross once.
- `one-band-on-top`: the crossing cells all hold the color of one of the two bands, the band on top.

## Rules
- `swap-on-top`: the output is the input with every crossing cell painted the color of the band that was underneath.
- `rest-kept`: every cell outside the crossing keeps its input color.

## Parameters
- `background`: 0

## Scene parameters
none
