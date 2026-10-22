# d282b262

## Concept
- Every object slides to the right as a solid piece until it hits the grid's right edge or an object that has already stopped, so the objects pile up against the right side.

## Scene
- `objects`: every input holds several objects on a background of color `bg`; an object is a connected group of non-`bg` cells, and it can hold more than one color.
- `apart`: no two objects touch in the input, at a side or at a corner.

## Rules
- `slide`: each object moves as a rigid piece toward `heading`, by the least distance that brings one of its cells against the frame edge or against a cell of another object at that object's resting place.
- `keep`: each object keeps its shape and its colors; every cell no object covers after the slide is `bg`.

## Parameters
- `heading`: R
    - the direction every object slides
- `bg`: 0

## Scene parameters
- none
