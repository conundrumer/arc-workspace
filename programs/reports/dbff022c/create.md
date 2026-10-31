# dbff022c

## Departures
- The concept branches take constructor names of their own: `$OnEdge` at `key-line` and `$Enclosed` at `hole`. `record --all` rewrote the witness file's groups to these names and to `bg=stored`: [Write](#write) gives a concept branch a name of its own.
- `bg=DominantColor` is a `@derive` line on `bg` (`variant derived`, `@relaxed outlines`) and has no constructor: `derive` lists DominantColor as a fitting derivation, and Write step 2 leaves out a branch that a built-in derivation gives.
- The witness file holds the three witnesses of `witnesses.json` with their grids unchanged. `witness --file programs/reports/dbff022c/witnesses.json` reports no difference.

## Judgments
- The legend is the one ink object (4-adjacent component of non-bg cells) whose cells hold more than one color. `Unanimous` gives that as `clash`, and gives one color to every outline. This rests on scene claims `outlines` and `legend`.
- "Two lines thick" is stated with no number. A side D of the legend's box is a thin side when a legend cell on side D has the legend cell beside it, toward the opposite side, on the box's opposite side (`cross_line`). The key line of `$OnEdge` is the thin side whose box margin is 0. The key line of `$KeyLineNearEdge` is the thin side of least margin (`ArgExtremes.low`). Two key sides (`key_tie`) leave the case undefined. This gives the undefined square 2×2 legend in a grid corner that `analyze.md` states, and the undefined tie of `$KeyLineNearEdge`.
- A case is undefined where it finds no key pair (`key_paint(K, _, _)` gates `out`). This gives the concept's undefined output on `legend-off-edge` and on `bg=DominantColor` at bg 0.
- A hole of `$Enclosed` whose wall meets two colors (`wall.clash`) gives no output on its cells, so the case is undefined there, as the concept states.
- `$PerColorWalls` keys `Closed` by each legend color, over the cells of every other color, and paints only the bg cells of those regions. A cell that two keys close off gets two colors, and the case is undefined there.
- Hint `common-subexpr` on `key_paint` against `thin_side`: accepted. The shared box, edge and neighbor atoms became one relation, `cross_line`, which both read.
- The `bg` determination reads the color of the input cells that the output changes. These are the hole cells, which the concept reads as bg. `determination-plan` asked for a relation from a fact other than DominantColor's commonest color. After the change it reports no actions, and `bg` is determined.
- `store` printed no line to add. `nearest.low` has no witness, so no `@store` line stands.
- `deletions` lists 10 removals that change no pair. Each is kept:
    - `legend(Q, _)` in `cross_line` states that the paint cell is a legend cell.
    - `key_tie`, `!key_tie`, `key_paint(K, _, _)` in `out`, and `unsettled` with its `p` column give the undefined places above, which no pair holds.
    - `dir_elem(D)` keeps the hole wall to the four cardinal neighbors.
    - `in(P, Bg), params.bg(Bg)` in the `$PerColorWalls` clause keeps a non-bg cell inside a closed area unpainted, as on `stray-cell-in-hole`.
- The case `$KeyLineNearEdge & $PerColorWalls` is in `impl_choice`. No witness shows it giving an output that neither single branch gives, so it is not a witnessed case, and `witness` reports no pair or case to resolve.
- No item under Not formed states one model, so Develop step 3 adds no branch.
- Keywords `objects enclose mapping`: the legend gives a color-to-color relation that supplies the fill color (`mapping`). The fill goes into closed regions (`enclose`). `induce` is not listed: the task is not a nested task, because the legend states each key-paint pair outright and demonstrates no rule.

## Unsettled
- The concept's reading of a square 2×2 legend in a grid corner is undefined in every case: a pair or a sibling task with such a legend would settle which axis holds the keys.

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
- none
