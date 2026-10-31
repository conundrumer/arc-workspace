# f8f52ecc

## Departures
- `$SteinerTree` is not formed, and witness `t-junction` is removed from the witness file: the branch fails Relational form. Its claim is the fewest-cell tree that joins a color's cells. That is a minimum Steiner tree, which no fixed set of non-recursive clauses over lib relations computes. No approximation the program runs places a Steiner point.
- `$TurnsFirst` is not formed, and witness `two-walls-snake` is removed: the branch fails Relational form. It reorders the optimization over all routes through a color's cells, with fewest turns first and fewest cells second. That optimization has no relational form, for the same reason the concept's rule has none. The approximation the program runs fixes links by fewest steps and cannot express a turns-first order.
- `join-dots` is restated from `analyze.md` as the hidden polyline. Under it, the `@approximated:` line gives the rule the program runs, not the concept file's rule. That rule has no relational form either: it needs the fewest-cell route through all of a color's cells, which is an optimization over orders of the cells.
- On `t-junction` in `witnesses.json`, the concept case gives the grid of `$SteinerTree` (col 3 rows 1–6 plus row 2 cols 0–3), not the concept file's path. The cause is in the approximation. The end-to-end walk may cut across the rectangle corridor of the link (2,0)–(1,3), which lets it skip the middle dot (1,3). `analyze.md` gives `$SteinerTree` as this witness's verdict, so on this input the program gives the verdict's output.
- The analyze name `$CrossDots` on the `dot-on-line` verdict is written `$KeepDot`, because in the solver `$CrossDots` denotes both crossing cases. The concept branches take the names `OverBackground` (obstacle) and `KeepDot` (crossed-dot).
- `wall_color` has no determination relation: see Unsettled.

## Judgments
- Witness `hook`, built for the `@approximated:` line: 2 at (0,0), (0,6), (3,6), (3,2) on a field of 1. The generator's polyline runs along row 0, down col 6 and left along row 3 to (3,2). The program links (3,2) to (0,0), which is nearer, and paints down col 0 and along row 3. Plausibility `ordinary`: the dots are the ends and bends of one polyline, and the witness breaks no scene claim. Verdict `other`, with the polyline as the judged output. The judged output came from `grid` on a control grid that puts a wall of 8 at row 1 cols 0–4, with that row then restored to 1. The concept file's fewest-cell rule also gives the hook here (9 added cells against the polyline's 10), so the concept file's rule and the generator differ on this input.
- `@derive DominantColor` on `background`: `variant derived`, `@relaxed background` and `dots`, as `analyze.md` gives it.
- Hint `single-consumer` on `piece_id`: accepted, and the relation is inlined. Hint `single-consumer` on `example` in Determine: accepted, and the relation is inlined. Hint `common-subexpr` on `walk.edge`: it stopped firing once a redundant `dir_elem(D)` was dropped from the step edge.
- Hint `determine prediction` on a `wall_color` determination that compared input cells with output cells: accepted. That clause read inputs and outputs together, so it was removed.
- `deletions`: the deletions that change nothing on the pairs stay. The per-color columns of `open`, `lane`, `branched` and `end`, the corridor's source restrictions, `lane` over the color's dots, and the `KeepDot` background test each state structure that the pairs never exercise: other colors as obstacles, routes over multi-cell pieces, and a crossed dot. `outnumbered` states that the background is the commonest color of every input, not just of one.
- Each link and route instance is keyed by the whole `Choice`, because the open cells differ between `OverBackground` and `CrossDots`. The two `CrossDots` cases compute the same routes under two keys. The runs finish in about 2 s, so no performance issue arose.
- Keywords: `markers` (the dots fix the ends and bends) and `route` (a fewest-step route between designated cells).

## Unsettled
- `wall_color` determination: `determination-plan` asks for a relation from SharedColor narrowed to 8. The colors that are in every input and are not the background are 2 and 8. No fact of the inputs alone, or of the outputs alone, found in this pass keeps 8 only. The plan ran 3 times, which is the cap. A fact of one side that singles out the wall color would settle it.

## Concept faults
- f8f52ecc `join-dots`: the fewest-cell route through all of a color's cells, then the fewest turns, is an optimization over every order of the cells. It needs recursion or arithmetic over route lengths, which the program bans, and no lib relation states it. The program runs the approximation that the `@approximated:` line gives.

## Fixes elsewhere
- none

## Tickets filed
- none
