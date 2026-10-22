# b94a9452

## Concept
- Cut out the one square on the empty field, and swap its two colors.

## Scene
- `one-object`: every input is a field of color `background` that holds one solid object of other colors.
- `nested-squares`: the object is a square of one color with a smaller square of a second color centered inside it.

## Rules
- `crop-to-object`: the output is the object's bounding box.
- `swap-colors`: each cell of the outer color takes the inner color, and each cell of the inner color takes the outer color.

## Parameters
- `background`: 0

## Scene parameters
- none
