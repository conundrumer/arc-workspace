# f8a8fe49

## Departures
- The witnesses `$WholeShape` and `$FourAdjacent` of `witnesses.json` are `straddling-bar` and `diagonal-chain` in the witness file: a witness id must be a slug, and the lint rejects an id that starts with `$`.
- `record --all` rewrote the groups of `straddling-bar`, `diagonal-chain` and `marks-off-arm-line` into the solver's case names. In the Analyze groups, `$WholeShape` stands for the 8-adjacent case alone, and `mark_color=RarestColor` leaves out its `$FlipToGap` combination. The grids the branch models give are unchanged, and `witness --file programs/reports/f8a8fe49/witnesses.json` reports ok.
- The program is undefined where the bracket color is also the mark color or the background (`shared_role`). `analyze.md` makes `mark_color=RarestColor` and `background=DominantColor` undefined where the derived color is the bracket color, and without this guard both cases gave a defined output on their Analyze witnesses. At the stored colors the guard never holds.
- Two witnesses are added, because without them no run shows each `@derive` case defined and differing from the stored case. `stray-color` is train0 with a 3 at (0,0): the rarest color is 3, so the real marks stay and the stray cell is cleared. `wide-side-fields` is train0 with columns 0–3 and 11–14 filled with 3: the dominant color is 3, so each mark's old cell becomes 3. Both have verdict `concept` and are `foreign`, because they break `background` with a color the generator never draws.

## Judgments
- Bases: the two bases are the edges of the box both brackets span whose cells are all `bracket_color`. The arm sides have a background gap. This reads both axes, so no axis parameter is needed (Every value).
- The mirror is two jumps from the mark by its depth: one to the base cell in its line, and one more past the base. The depth is the mark's distance to the base edge of the bracket box. "Nearer" compares the two depths. No arithmetic.
- `$FlipToGap` lands each mark `out_gap` lines plus one past the base, and then by its depth inside its group's box. That is the group, flipped, with its near edge after the gap.
- Not formed, "split at an empty middle line": this gives no single model, because which empty line splits is not fixed. `analyze.md` judges that it adds no output, so it would leave under Subsumption. No branch for it.
- The hints at `base_dir` (single consumer) and `landing.p` (column no clause reads, from `deletions`) were acted on: the relation was inlined and the column dropped. The `common-subexpr` hint on `Determine.background` is dismissed with `@ignore`: `changed` drops the color the cell takes.
- Determination: `determination-plan` asked for relations where a proposer reads another fact than the concept does. `background` is the color a cell of a never-kept color turns into. `out_gap` is the least count of empty lines between an output mark and its base, per group. `bracket_color` (UnchangedColor) and `mark_color` (ChangedColor) read the concept's own facts, so they have no relations.
- `deletions`: these are kept because the pairs never instantiate them, and witnesses or inputs outside the pairs do: `shared_role`, `tie`, the `!landing` negations, `side` in `$FlipToGap`, and `gap.domain` (gap 0). `opposite` in `side` is kept because it states "the other base". With only two bases it is implied. The determination atoms `ex_out(E, _, _)` and `changed(C)` are kept: the first restricts to examples that have outputs, and the second limits marks to changed colors.
- Keywords: `d4 bbox objects`.

## Unsettled
- The `$WholeShape` × `$FlipToGap` combinations and the `@derive` × branch combinations are not witnessed cases. `witness` and `audit` report no pair that is left unseparated. A witness on which a combination gives an output that no case with part of its branches gives would settle them.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
