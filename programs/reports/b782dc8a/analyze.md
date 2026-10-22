# b782dc8a

## Concept
- Fits every pair (`probe.py`). Its rules are relational: a 4-adjacent flood through `background` from the seed cells (lib `Components`), and a color per row+column parity read off the seed cells.
- No witness has the verdict `other`.
- The concept model is undefined on every input where one parity class of the flooded cells has seed cells of two colors (`uneven-seed`, `two-seeds`). Each of those witnesses is listed under a branch.
- Invariants of the inputs that the scene claims do not state, from probes over the inputs:
    - The walls are one cell thick and the corridors one cell wide: no 2×2 block is all `wall` or all `background`.
    - No 2×2 block holds `background` on one diagonal and `wall` on the other, so no two corridor cells touch only at a corner.
    - Every non-`wall`, non-`background` cell belongs to the one seed.

## Choice points
- `flood-adjacency`
    - `concept`: the flood walks between 4-adjacent cells.
    - `$Flood8`: replaces `flood-seed-region` with a walk between 8-adjacent cells, and the color is still read by row+column parity. No parameter is added, and the model is undefined where the concept is. Fits every pair. Witness `diagonal-corner`: breaks no scene claim. It stands at the stored assignment, with plausibility `borderline` and verdict `concept`. It breaks the invariant that no 2×2 block holds `background` on one diagonal and `wall` on the other.
- `paint-color`
    - `concept`: a cell takes the color of the seed cells of its own row+column parity.
    - `$PathParity`: replaces `flood-seed-region` and `seed-checkerboard`. A cell takes, from each seed cell nearest to it by a walk, that cell's color at an even distance and the seed's other color at an odd one. No parameter is added. The model is undefined where the seed has other than two colors, or where two nearest seed cells disagree. Fits every pair. Witness `uneven-seed`: breaks `seed` and `seed-checkerboard`. It stands at the stored assignment, with plausibility `foreign` and verdict `$PathParity`. It breaks the invariant that the seed is one center cell and its non-`wall` neighbors, in alternating colors.
    - `$CenterParity`: replaces `flood-seed-region` and `seed-checkerboard`. The center is the one seed cell whose non-`wall` 4-neighbors all hold the other seed color. A cell of the center's parity takes the center's color, and every other cell takes the other seed color. No parameter is added. The model is undefined where the seed has no center, or more than one, or other than two colors. Fits every pair. Witness `uneven-seed`, as for `$PathParity`. The output of `$CenterParity` there is its own group.
- `passable`
    - `concept`: the flood passes through `background` cells and paints them.
    - `$PassNonWall`: replaces `flood-seed-region`. The flood passes through every non-`wall` cell outside the seed and paints it. `wall` becomes a parameter (8), and the model reads no `background`. It is undefined where the concept is. Fits every pair. Witness `stray-color`: breaks `maze`. It stands at the stored assignment, with plausibility `borderline` and verdict `any`. It breaks the invariant that every cell is `wall`, `background` or a seed cell.
        - `wall`
            - `concept`: stored, 8.
            - `wall=DominantColor`: train1 has a tie between 0 and 8, so `wall` takes both values and nothing is painted. Fails train1.
            - `wall=RarestColor`: gives 2 on train0. Fails train0.
            - `wall=SharedColor`: gives every color of the input. Fails train0.
- `seed-scope`
    - `concept`: one color per parity class, read from every seed cell in the grid.
    - `$PerSeed`: replaces `flood-seed-region`. Each corridor system that holds seed cells is flooded with the colors of its own seed cells. No parameter is added. The model is undefined where one system's seed cells put two colors on one parity class. Fits every pair. Witness `two-seeds`: breaks `seed`, which states one seed. It stands at the stored assignment, with plausibility `variant` and verdict `$PerSeed`. It breaks the invariant that each input holds one seed.
- `flood-extent`
    - `concept`: only the background cells joined to the seed are painted.
    - `$FillAll`: replaces `flood-seed-region`. Every `background` cell takes the color of its parity class. No parameter is added. Fails train0, where col 23 stays 0.
- `paint-source`
    - `concept`: the two paint colors are read from the seed cells of each input.
    - `$StoredPaint`: replaces `flood-seed-region`. The center color and the arm color are stored as a parameter, and the seed's colors are not read. Fails train1: train0 paints 2 and 3, and train1 paints 4 and 1.
- `background`
    - `concept`: stored, 0.
    - `background=DominantColor`: gives 8 on train0, so the flood passes through the walls. Fails train0.
    - `background=RarestColor`: gives 2 on train0. Fails train0.
    - `background=SharedColor`: gives every color of the input. Fails train0.
- `flood-adjacency` & `paint-color`, `flood-adjacency` & `passable`, `flood-adjacency` & `seed-scope`, `flood-adjacency` & `paint-source`, `flood-adjacency` & `background`, `paint-color` & `passable`, `paint-color` & `seed-scope`, `paint-color` & `paint-source`, `paint-color` & `background`, `passable` & `seed-scope`, `passable` & `paint-source`, `seed-scope` & `paint-source`, `seed-scope` & `background`, `paint-source` & `background`, `flood-extent` & `passable`, `flood-extent` & `paint-color`, `flood-extent` & `paint-source`, `flood-extent` & `background`: the two branches' changes applied together.
    - `$Flood8` & `$PathParity` fails train0. With diagonal steps, the walk distance cuts across a corridor's corners, and the alternation breaks there.
    - `$FillAll` & `$PathParity` is undefined on every pair, because some `background` cell in each pair has no walk to a seed cell. Fails train0.
- `passable` & `background`: the model is `$PassNonWall` alone. That branch reads no `background`, so the `background` point stands under the concept branch of `passable`.
- `flood-extent` & `flood-adjacency`, `flood-extent` & `seed-scope`: the model is `$FillAll` alone. That branch has no flood and no corridor systems, so those points stand under the concept branch of `flood-extent`.

## Open parameters
- none

## Not formed
- Distance parity from the seed under 4-adjacency, read from the center alone: the grid graph is bipartite, so the walk distance from the center has the parity of the row+column offset. That reading is `$CenterParity`'s model.
- `background` from a derivation that reads `ex_out` (`ChangedColor`, `UnchangedColor`, `ChangedPairs`, `VanishedNewPairs`, `OutNewColor`, `VanishedColor`): with `ex_out` empty on a single input, these give no value, so the branch is undefined on every pair and fails train0.
- `wall` as a parameter of the concept: the concept's rules never read it, so it stays a scene parameter. It becomes a rule parameter only under `$PassNonWall`.
- A wider corridor or a 2×2 open room: no rule reads corridor width, and coordinate parity and walk parity agree on any 4-adjacent region, so no claim changes.

## Tickets filed
- none
