# Different parse: the structures found, or the input cells read

Open question in `principles.md`, Coverage — Prior or setup, the Different parse bullet.

## The question

The Different parse test names both the input cells a rule reads and the structure the other encoding omits, and it does not say which of the two it ranges over. A peer that leaves a cell of a shared structure unread is a second parse under Cells and the same parse under Structures.

A peer that finds a further structure over cells a shared structure already holds, and reads only that structure's extents, is a second parse under Structures and the same parse under Cells.

A third shape is the rule that builds a structure: when two encodings agree on the structure and differ in which cells qualify for it, the rule that reads the extra input cells is the definition itself.

## The text

> - **Different parse.** A peer model that parses the task differently gets a case.
>     - Two encodings parse the task differently when a rule of one reads an input cell that the other's structure omits.
>         - A read of a structure's extents or place reads no cell.
>         - A read that binds a position to a cell of the structure reads a cell.
>             - Bound to the structure's own cells it is the same parse.
>             - Over an unrestricted position it is a different parse.
>         - A write through the structure as a frame reads no cell.
>         - A rule that reads a cell of the box the set omits makes the box a different parse.
>     - An encoding that finds the same structure over the same cells another way is the same parse. Same model decides whether it is a peer.

## Candidate readings

1. **Structures.** "The test ranges over the structures the encodings find. A peer that leaves a cell of a shared structure unread parses the task the same way, and an encoding that narrows a structure to the cells its own rules use finds the same structure." A peer that only leaves a cell of a shared structure unread gets no case on parse grounds, and needs Same model and Peer priors to earn one. No approved case changes. The `Passthrough | Repaint` cases of 6f8cd79b and a406ac07 rest on Peer priors, the question in `peer-priors.md`.
2. **Cells.** "The test ranges over the input cells the rules read. A peer whose rules leave a cell of a shared structure unread parses the task differently, and an encoding that narrows a structure to the cells its own rules use finds a different structure." Any peer that consumes fewer cells of a shared structure gets a case. The `Passthrough | Repaint` pairs of 6f8cd79b and a406ac07 stand as different parses, and no longer depend on the Peer priors question.

## Solvers

- 9356391f (draft) — `$Paint` paints every ring; `$Survive` paints every ring and keeps the marker cell its input color. Both find the same rings. The create pass read the Different parse test as admitting `$Survive`, and recorded it in its review; the refine pass read that test as ranging over the structures found, and gave it no case. Under reading 1 `$Survive` gets no case on parse grounds; under reading 2 it is a third case beside `$Paint` and `$Skip`.
- 6e4f6532 (draft) — `$Backed` tests the object cell behind a wall-colored cell; `$Edge` tests the same cell against the edge of the object's bounding box that the transform turns toward the wall. `$Edge` finds a structure `$Backed` does not, and its rule binds positions only to the object's own cells, so it reads no cell outside the shared structure. Under reading 1 `$Edge` is a second parse and keeps its case; under reading 2 the two parse alike and Peer priors decides.
- 97c75046 (draft) — `contact` holds the background cells that touch the shape by a cardinal step. The 8-adjacency peer holds the cells that touch it at a corner as well. Both find the contact set, and the only rule that reads the extra input cells is `contact` itself. Under reading 1 the two parse alike and the solver keeps one case; under reading 2 the peer is a second parse and gets one.

## Witnesses

9356391f, a legend `4 3` above the divider and a marker 2 below it. Legend entry 0 is 4, and it names the marker's own cell:

```
input              $Paint, $Skip      $Survive
4 3 . . . . . .    4 3 . . . . . .    4 3 . . . . . .
5 5 5 5 5 5 5 5    5 5 5 5 5 5 5 5    5 5 5 5 5 5 5 5
. . . . . . . .    . . . . . . . .    . . . . . . . .
. . . . . . . .    . . 3 3 3 . . .    . . 3 3 3 . . .
. . . 2 . . . .    . . 3 4 3 . . .    . . 3 2 3 . . .
. . . . . . . .    . . 3 3 3 . . .    . . 3 3 3 . . .
. . . . . . . .    . . . . . . . .    . . . . . . . .
. . . . . . . .    . . . . . . . .    . . . . . . . .
```

6e4f6532, wall `4` on row 0, the marker `4` at (2,2) on the top edge of the object's box and backed only from the right, the target `9` at (6,7):

```
input                  $Backed                $Edge
4 4 4 4 4 4 4 4 4 4    4 4 4 4 4 4 4 4 4 4    4 4 4 4 4 4 4 4 4 4
. . . . . . . . . .    . . . . . . . . . .    . . . . . . . . . .
. . 4 8 8 8 . . . .    . . . . . . . . . .    . . . . . . . . . .
. 8 . . . 8 . . . .    . . . . . . . . . .    . . . . . . . . . .
. 8 8 9 . 8 . . . .    . . . . . . . 8 8 .    . . . . . . 4 8 8 8
. . . . . . . . . .    . . . . . . . 8 . 4    . . . . . 8 . . . 8
. . . . . . . 9 . .    . . . . . . . 9 . 8    . . . . . 8 8 9 . 8
. . . . . . . . . .    . . . . . . . . . 8    . . . . . . . . . .
. . . . . . . . . .    . . . . . . . 8 8 8    . . . . . . . . . .
. . . . . . . . . .    . . . . . . . . . .    . . . . . . . . . .
```

`$Backed` turns the object a quarter turn clockwise; `$Edge` keeps the identity.

97c75046, background `7`, the marker `5` at (0,3), shape cells at (2,3), (2,4), and (4,0). The 8-adjacency peer is the shipped solver with `dir_elem` in `contact` replaced by `dir8_elem`:

```
input            4-adjacency      8-adjacency
7 7 7 5 7        7 7 7 7 7        7 7 7 7 7
7 7 7 7 7        7 7 7 7 7        7 7 7 7 7
7 7 7 . .        7 7 5 . .        7 7 7 . .
7 7 7 7 7        7 7 7 7 7        7 5 7 7 7
. 7 7 7 7        . 7 7 7 7        . 7 7 7 7
```

The marker rests at (2,2) under the cardinal join and at (3,1) under the corner join, which carries it on past (2,2) to the cell that touches (4,0) at a corner.
