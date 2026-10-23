+ document-size-budget: 960
* comment: when editing this doc
    - Readers: the `analyze`, `create` and `refine` agents and [Codex on arc-workspace](prompts/codex.md) inline [grids](#grids) under their Grids heading.
    - Acts, each with its section:
        - Drawing a grid and citing a grid location: [grids](#grids).

# Grid notes
- The statements on drawing a grid and citing a grid location, that more than one entry point inlines.

## grids
- A color: the marks are `3` on a field of `5`. A row: `3 5 5 5 3`. A `0` cell is written `0`. A grid:
    ```
    3 5 5 5 3
    5 5 5 5 5
    3 5 5 5 3
    ```
- A grid location is cited as pair, side, places — `train0 input (11,2), (13,2); test1 output rows 2–4, cols 1–3`, or a single `row N` / `col N` — all 0-based cell coordinates.
