# c444b776

## Departures
- The branch `tiling=stored` is the constructor `$StoredTiling`, and its witness's id is `small-panels` in place of `tiling=stored`: Write gives a constructor of the solver's own name to a branch that the report names in a form other than a constructor name. `store` prints no storable value for the tiling, because `tiling.tile_of` stands at another place on each input. The new id keeps the witness id apart from the name form `<rel>=stored`.
- The witness file adds `gap=SepThickness`, `gap=TileDim`, `broken-divider` and `gap-six`: `derive` printed two fitting derivations of `gap`, and `witness` reported pairs of cases that no witness separated.

## Judgments
- The three Not formed items give no branch. The period-10 tiling does not say on which edge a partial panel stands, or how the drawn panel is found without a tiling. The copy into panels of another size needs an anchor corner, and that gives four models. Replacing `drawing-avoids-divider` changes no output.
- `$ReflectCopy`, `$SameBandCopy` and `background=SharedColor` have no constructor: the report gives each one a Fit failure and no witness.
- `@derive SepThickness` and `@derive TileDim` on `gap` are each `variant concept`. The witness is the train1 layout with 2-wide divider rows. It breaks no scene claim, but this generator always draws 1-wide lines, and the generator would copy the drawing.
- `broken-divider` (a 3 in the divider row) separates `gap=SepThickness` from `gap=TileDim`. `gap-six` (a 14×14 grid of 4×4 panels, with `panel_size` reassigned to 4) shows `gap=stored` and `gap=SepThickness` defined and different from `gap=TileDim`. On that grid, TileDim's derived gaps do not hold 1, and only a gap of 6 fits 4-wide panels. On grids of at most 30 cells a side, the stored 9×9 panels give no such input.
- The sweep found 45 single-row changes of `panel_size` that give every train output. None was added: a reader of `$StoredTiling` takes 9, so `panel_size` is not an open parameter.
- Determination: `divider` is the color that fills a line in every train input, and `background` is the color that fills a whole panel in every train input. `gap` is the width of every run of adjacent divider lines. The train pairs' fit gives `panel_size`, as the plan states.
- The line colors, the divider tiling and the in-panel positions are in `Parse<Key>`, because Determine uses them too. This follows the `Parse` of 0bb8deee (Unanimous line colors into DividerTiles).
- Deletions: these atoms and rules stay. `cut(Ky, _)` makes `$DividerFromLines` undefined when no divider color is found. `in_panel(Pn, _)` makes `$StoredTiling` undefined where no tiling fits. `drawn_count.domain` lets a blank panel count 0, so one blank panel is the most drawn. `ex_out` in Determine follows "Test inputs". `unblank` states the universal over train inputs. `band_width.domain` was removed, because every run of divider lines holds a line.
- Keywords: `decompose`, `tile-arrangement` and `select` for the concept, `overlay` for `$Overlay`, and `rank` for `$MostDrawn`.
- No lint hint appeared. There was no performance issue.

## Open
- `$Overlay` is defined where the panels differ in size: each set of panels of one size overlays on its own. The Analyze report says every branch is undefined there. No witness exercises this. An annotator's judgment of a witness with unequal panels would settle whether `$Overlay` needs an equal-size condition.

## Concept faults
none

## Fixes elsewhere
none

## Tickets filed
- 10-679_task_c444b776_create.md
