# d2abd087

## Departures
- The witness file's group names are rewritten by `record --all`: `concept` becomes `$Comp4` or `$ShapeInk & shape_color=stored`, `$AnyInk & background=DominantColor` becomes `background=DominantColor`, and the other combinations become the fewest names for the same cases: `concept` covers the base `[Comp4, ShapeInk]` and so includes the `shape_color=RarestColor` case. The grids are unchanged, and `witness --file programs/reports/d2abd087/witnesses.json` reports `witness: ok`.

## Judgments
- Constructors: `Adjacency = Comp4 | Diag8` and `Ink = ShapeInk | AnyInk`, in `Choice = [adj, ink]`. `Comp4` and `ShapeInk` are names I chose for the concept branches. The `selection`, `match_color source` and `other_color source` branches all fail Fit, and `analyze.md` gives them no witness, so they get no constructor. `background=DominantColor` and `shape_color=RarestColor` are `@derive` lines, not constructors.
- `@derive RarestColor: variant derived` with `@relaxed shapes-on-background` on `shape_color` (under `$ShapeInk`), and `@derive DominantColor: borderline concept` on `background` (under `$AnyInk`). Both take the plausibility and verdict `analyze.md` gives them. `derive` lists only these two. The derivations of `match_color` and `other_color` do not fit, and `derive` asks for no `@ignore` line for them.
- `store` finds no derived value that is the same on every input, so there is no `@store` line.
- Five cases are witnessed: concept, `$Diag8`, `$AnyInk`, `shape_color=RarestColor`, and `background=DominantColor`. The run excludes `$Diag8 & $AnyInk` and the derived combinations under `$Diag8`, because they give no output that their sub-combinations do not give. `witness` reports no pair of cases left unseparated and no case left undefined or undifferentiated.
- Hint "case section" at the `Tally` instance, which sat under the `$Diag8` marker: I moved the instance above the case markers in `Parse`, because every case reads it.
- Determine: `match_color` is the color that the train shapes of one size, and no other size, take. `target_size` is the size whose shapes take that color. `other_color` is the color of the shapes of every other size. `background` is a color some train cell keeps from input to output, which is what `rest-kept` says. The plan asked for these because the proposers derive them from facts the concept does not use (new output colors, enumeration, cell counts). Now the run gives `determination: ok (background, match_color, other_color, target_size)`.
- The plan still lists `shape_color (ChangedColor exact)`. I wrote no determination relation for it, because the concept reads the shape color from the same fact: shape cells are the cells the output recolors. This is my reading of the plan's wording.
- Hint "determine prediction" on a first `background` clause, which tested an `absent` relation that read inputs and outputs together. `deletions` then showed that its universals change nothing, so I replaced it with the single join on kept cells. That clause reads the value from the evidence and does not filter guessed values.
- Keywords `objects count`: shapes are components, and a cell count picks the color.
- The audit is clean, and it skipped no check. `deletions` reports that every deletion changes the result.

## Unsettled
- Whether `shape_color` needs a determination relation even though ChangedColor reads the concept's own fact: a clearer `determination-plan` line would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
