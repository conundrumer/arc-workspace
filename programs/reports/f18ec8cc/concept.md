# f18ec8cc

## Concept
- The picture is a row of colored stripes, each speckled with a few dots; take the first stripe off and put it at the other end, every stripe carried whole with its dots.

## Scene
- `stripes`: the grid is cut, along the axis of `from`, into full-length stripes, each a run of whole lines filled by one background color, the stripes' colors pairwise distinct.
- `dots`: inside a stripe, single cells of other colors, each the background color of another stripe; a stripe's two edge lines hold no dot, so each line's commonest color is its stripe's color.

## Rules
- `cycle-stripes`: the output has the input's size, and its stripes are the input's stripes, each copied cell for cell with its dots, in their input order moved `shift` places toward `from`, the stripes that pass that edge wrapping round to the opposite end.

## Parameters
- `from`: DIR_L
    - the edge from which stripes move to the opposite end; its axis is the axis the stripes are laid out along
- `shift`: 1
    - how many stripes move from that edge to the opposite end

## Scene parameters
- none
