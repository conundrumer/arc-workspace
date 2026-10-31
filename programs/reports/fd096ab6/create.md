# fd096ab6

## Departures
- `copy-offgrid` (`$OffgridUndefined`) and `ambiguous-fragment` (`$AmbiguousUndefined`) have no constructor and no case: both fail Subsumption. Each model is the concept model with more inputs left undefined. Where either one is defined, no copy leaves the grid or no two maximal copies hold the same cells, and its output is the concept's. This holds at every assignment, so no witness can show it defined and different. `witness` reported both, and no input resolves them.
- Witness `copy-past-edge` is removed from the witness file: once `$OffgridUndefined` left, every case gives the same output on it, so it separates nothing.
- Witness `background=DominantColor` is removed from the witness file. The `bg=DominantColor` witness that `derive` recorded duplicates it (train0 with the field recoloured to 0). The name `background=DominantColor` is `bg=DominantColor` in the witness file, after the parameter `bg`.
- `witnesses.json`, `background=DominantColor`: it groups `$InputKept` with the undefined cases. At stored `bg` = 1, `$InputKept` draws copies only on cells of colour 1, and there are none, so it gives the input unchanged. The solver follows the branch's own definition.
- `witnesses.json`, `background=DominantColor`: it gives `$TemplateLargestObject` a completed grid. At stored `bg` = 1, the 0 field is the largest non-background object, so it becomes the template, its copies run over the other pieces, and the model is undefined. The completed grid that analyze gives is that model's output at the derived background, not at the stored assignment the witness stands at.
- `complete-fragment` takes analyze's generator reading ("the copy it was cut from"). The concept file's operational rule, inclusion-maximal copies per colour, stands under it as `@approximated:`, and `fragment-fits-several-copies` (borderline, other) stands under that line with `@relaxed fragments`.

## Judgments
- `complete-fragment` has no relational form. "The copy the fragment was cut from" is history the generator keeps and the input does not show. When a fragment's cells lie on several copies alike, no clause can tell which copy the generator erased from. The approximation agrees wherever `fragments` holds. `fragment-fits-several-copies` is borderline, which means the generator can produce such an input, so the `@approximated:` line stays.
- On `fragment-fits-several-copies`, the concept output is not the judged output: it draws all three copies of the 2 fragment, and the judged output draws one. That is the approximation's disagreement, and no fix applies.
- Fragment grouping is per colour. A copy at offset V is kept when no other copy of the same colour holds a strict superset of its held cells (`held`, `not_within`, `dominated`, using defect negation). Copies are translations computed with `relative` and `compose` from template cells.
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
