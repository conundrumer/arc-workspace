# ea959feb

## Departures
- The rule `restore-period` keeps the concept file's text, and the restated rule of `analyze.md` goes to `$ColorCycle`: where a patch covers every copy of a phase pair, the steps of the color cycle along each row fix the pattern there, so that reading has a relational form, and the witness `fully-covered-phase` stands under that branch.
- The witness file has two witnesses that `witnesses.json` does not have, `line_known=stored` and `dominant-mask-in-cycle`: Develop step 4 holds the `@store` branch on `line_known`, and no other run showed `$ColorCycle & mask_color=DominantColor` defined and differing from `$ColorCycle`.
- `$ColorCycle` reads a known cell of a counterpart's line only where the cell's own line has none, as `analyze.md` states; where the column phase has no known cell, the cell takes the next step along its row from the two stepped cells beside it or beside a cell of its phase, and with neither it keeps its input color. A clause cannot close a cycle, so this reaches one line past a line of stepped cells. On `mirror-restores-covered-column` this gives the output `witnesses.json` gives `$ColorCycle`.

## Judgments
- No item under Not formed states one model: the shape-based mask has no size or shape criterion, and the other items add no model or give the concept's output.
- `$StoredPeriods` is not formed: it fails Fit, as `analyze.md` shows, and `store` reports that the periods differ between train pairs.
- `mask_color=DominantColor` is a `@derive` line, borderline, verdict `concept`, from the witness of `analyze.md`.
- `dominant-mask-in-cycle`: the test pattern with 1 recolored 0 and one 1 cell over a 4. The derived mask 4 makes the lone 1 the cycle step between 3 and 5, and `$ColorCycle & mask_color=DominantColor` turns every 4 cell to 1. Plausibility `borderline`, since it breaks `mask-color-in-pattern`. Verdict `concept`, since the generator's output is the pattern.
- `line_known=stored` (`@store: variant concept`): the witness that `store` built is train 0 turned a quarter turn. A turned train input is a variant task, and the generator's output is the turned pattern.
- `// @ignore period: store` above `wp_m`: the axis of each period follows from `cycle_axis`, so a stored axis is a redundant value.
- Hints: the common-subexpr hints on `period` and `cyc.succ` were resolved by one shared `period` relation and a disjunction. The head-repeat hint on `source` was resolved by `step_line`, which names the line a cell reads.
- Determination: `mask_color` is read from the evidence as the input color of the cells the output changes. `cycle_axis` keeps each axis on which no output color has two different successors.
- Deletions: removing the identity transform and the cells of `wp_t` changed nothing, because Wallpaper acts by the period translations whatever its transforms, so they were removed, and so were `impl_choice` and the enumerator that only it read. The other deletions that change nothing remove structure that the pairs do not instantiate, such as reflections, fully covered columns, and the restriction to `cycle_axis`, so they stay.
- Keywords: `wallpaper symmetry repair color-class`. The cyclic color order of `$ColorCycle` fits no keyword exactly. `rank` comes nearest, and it was not added.

## Unsettled
- `deletions` ran before the last edits, which removed what it reported: run it again on the current solver to settle it.
- The `deletions` run timed out on `neighbor(P, D, Q)` in `Determine.branching`: a longer determination timeout would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
