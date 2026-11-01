# fd096ab6

## Departures
- `copy-offgrid` (`$OffgridUndefined`) and `ambiguous-fragment` (`$AmbiguousUndefined`) have no constructor and no case: both fail Subsumption. Each model is the concept model with more inputs left undefined. Where either one is defined, no copy leaves the grid or no two maximal copies hold the same cells, and its output is the concept's. This holds at every assignment, so no witness can show it defined and different. `witness` reported both, and no input resolves them.
- Witness `copy-past-edge` is removed from the witness file: once `$OffgridUndefined` left, every case gives the same output on it, so it separates nothing.
- Witness `background=DominantColor` is removed from the witness file. The `bg=DominantColor` witness that `derive` recorded duplicates it (train0 with the field recoloured to 0). The name `background=DominantColor` is `bg=DominantColor` in the witness file, after the parameter `bg`.
- `witnesses.json`, `background=DominantColor`: it groups `$InputKept` with the undefined cases. At stored `bg` = 1, `$InputKept` draws copies only on cells of colour 1, and there are none, so it gives the input unchanged. The solver follows the branch's own definition.
- `witnesses.json`, `background=DominantColor`: it gives `$TemplateLargestObject` a completed grid. At stored `bg` = 1, the 0 field is the largest non-background object, so it becomes the template, its copies run over the other pieces, and the model is undefined. The completed grid that analyze gives is that model's output at the derived background, not at the stored assignment the witness stands at.
- `complete-fragment` takes the copies `CoverForcing` forces, read as `forced` with `!ruled_out`, the form other solvers use. The scene claim `one-split` rules out an input whose fragment color splits in two ways.
- Witness `fragment-fits-several-copies` is removed from the witness file. It broke `fragments`, which the pairs support: all 16 fragments lie on one copy alone, and cuts drawn at random with the same sizes would do so 1.9% of the time, since 40% to 50% of a template's two-cell cuts lie on more than one copy. Its judged output took one of three alike copies with nothing in the pairs to choose it, and its `separates` text named the dropped `$AmbiguousUndefined`.
- `paint` drops a copy that `CoverForcing` rules out. Inclusion-maximal copies alone drew a third copy across two fragments of one colour, on train0's input with 2 cells added at (10,16) and (12,16), which breaks no scene claim. Train and test give the same output as before.

## Judgments
- Fragment grouping is per colour. A copy at offset V is kept when no other copy of the same colour holds a strict superset of its held cells (`held`, `not_within`, `dominated`, using defect negation), and when `CoverForcing` does not rule it out. Copies are translations computed with `relative` and `compose` from template cells.
- Of those 171074 second fragments, 14178 leave a copy across the two fragments that inclusion-maximal copies keep, and `CoverForcing` removes it from 13244. It is partial, so 858 of the other 934 keep an extra copy although one split alone keeps every scene claim.
- Undefinedness comes from conflicting facts. Under `$CopiesClear`, a copy on a cell of another colour gives both colours, and copies of two colours that meet do the same. Under every case, an off-grid copy cell is clipped by `in(P, _)`.
- The template choices `$TemplateLargestObject` (Components8 per colour, Tally, ArgExtremes, Unanimous) and `$TemplateLargestColor` (Tally per colour, ArgExtremes, Unanimous) are undefined on a tie, because `Unanimous` gives no value there.
- The `Edge` and `Ambiguity` choice points are removed, so `impl_choice` and `template_choice` are gone. Clauses ground the template through `template_color(T, _)` and enumerate `Overlap` through `overlap_choice`.
- Lint hint `enumerator name` on the helper relations `overlap_keeps` and `overlap_covers`: I removed both relations and wrote the `out` clauses per overlap branch.
- Lint hint `single-consumer` on `copy`: I inlined it into `paint`.
- Lint hint `determine prediction` on Determine's `template_color`: I kept it with `@ignore`. The template is the one non-background colour that every input holds and that no output adds cells to. That reads input and output together. The only input-only fact, a colour shared by all inputs, leaves 3, 4, 6 and 8.
- Determine's `bg` is the colour that is the commonest in every input, using Mode and defect negation.
- `deletions` results that I kept: `!template_color` in `fragment_cell`, the colour columns of `not_within` and `dominated`, the background test on the shared copy clause, the `$CopiesClear` disjuncts, `!params.bg` in the `$CopyOverwrites` clause, and `not_commonest`. The pairs never contain the structure each one handles: a template-coloured piece, a copy over a non-background cell, a mixed-colour comparison, or an input whose commonest colour differs. I removed the `domain` rules of both Tally instances and the `in(P, _)` in the former `painted`, because nothing needed them.
- Keywords: `objects repair stamp rank color-class`. `rank` and `color-class` come from the largest-object and largest-colour template cases.
- Witnessed cases: 6 of 18, plus the `bg=DominantColor` branch.
- Performance: the sweep timed out (2 s) at `bg` values 2 to 9 on train0. With a wrong background, the field becomes a fragment colour, and `held` and `not_within` grow with the square of its offsets. The principled form was kept, with no workaround.

## Unsettled
- `template_color` determination reads inputs and outputs together, and the `determine prediction` hint flags that. It would be settled by a ruling on whether "the colour no output adds to" counts as a read of the evidence, or by a determination from one side alone that narrows {3, 4, 6, 8} to 4.

## Concept faults
- none

## Fixes elsewhere
- `programs/reports/fd096ab6/witnesses.json`, witness `background=DominantColor`: list `$InputKept` with the input as its grid, not with the undefined cases. List `$TemplateLargestObject` as undefined at the stored `bg` = 1.

## Tickets filed
- none
