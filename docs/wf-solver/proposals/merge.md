# `merge` — like neighbors fuse into one unit

A Prior term for `concepts.md`: like-valued items — cells, lines, tiles, marks — fuse into one unit under a task-given nearness (adjacency, or a bridged gap), and the output treats the unit as one thing. What the unit renders as — its box, a single cell, a fill of its own — is the task's business, not the term's: a program whose join rule only ever builds rectangles still claims fusion, not rectangles.

No code form: the term names a model hypothesis, not an operation.

Not: `objects` (setup — connected components as the medium the model reads; `merge` is the transformation hypothesis that the fusion itself is what the task teaches); `move` (content relocates or stacks; nothing fuses); `mapping` (cells recolor with no spatial joining); a band frame whose members group by a divider or an empty gap rather than by a shared value (a decomposition hypothesis); a per-cell like-neighbor test that recolors or selects the cell with no group closed (`classify`, `select`); a comp name such as `Components` or `Canon` (grep-derivable, so disqualified as a concept).

Match: a solver whose program closes a like-value nearness into groups and treats each group as one unit — `Canon` or `Components` over an equivalence seeded by same-valued neighbors, or a boundary count that collapses runs of identical lines. Grep: `Canon<` and `Components` inits whose feed joins two atoms of one value variable; then judge whether the group renders as a single unit. Spec question: does any site fuse into a unit that is not a rectangle, or does every site's render reduce to a box?

Survey: 2026-09-02 13:24

Result: four callers corpus-wide. 33067df9 fuses like lattice tiles into groups and paints each group's box; 746b3537 fuses adjacent like-colored lines into runs and emits one cell per run; e1baa8a4 collapses consecutive identical lines into bands and emits one cell per band×band block, stated by boundary counts with no `Canon` and no `Components`; 36fdfd69 clusters marks joined across one-cell gaps and repaints each cluster's box in a stored fill. On the spec question: 36fdfd69's cluster is a scatter, not a rectangle, and it renders as its box; the other three units are rectangles by construction, and every render in the corpus is a box or a single cell, so the union render stands permissive and unwitnessed. The survey sharpened the entry: the render's value and its absorption of separators moved out of the definition (36fdfd69 renders in a stored fill; 746b3537 and e1baa8a4 keep no member cells), and the `Not:` line gained the divider-band and per-cell exclusions it now carries. Near-misses cluster in three kinds: same-color components as medium (the `objects` setup, 129 files), fusion consumed identically by every peer case (22a4bbc2, where the prior is `rank`), and groups with no nearness (1caeab9d's color classes, which `move`). Of the callers, only 36fdfd69 carries a prior term today (`span`); 33067df9, 746b3537, and e1baa8a4 sit on setup-only concept lines.

Callers:

- 33067df9 (`join`/`group`)
- 746b3537 (`runs`)
- e1baa8a4 (`boundary`/`bands`)
- 36fdfd69 (`meet`/`cluster`)
