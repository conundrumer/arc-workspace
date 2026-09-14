# Different parse: the structures found, or the input cells read

Open question in `principles.md`, Coverage — Prior or setup, the Different parse bullet.

## The question

The Different parse test names both the input cells a rule reads and the structure the other encoding omits, and it does not say which of the two it ranges over. A model that finds the same structures as its peer, and leaves one cell of a shared structure unread, reads either as the same parse or as a second parse.

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
