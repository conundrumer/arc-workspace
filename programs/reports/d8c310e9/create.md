# d8c310e9

## Departures
- `$GroundPeriod` is not formed: its encoding needs a workaround, and a non-concept branch takes none.
- I added the branch `seg.min_period=stored` (`@store min_period` above `.init seg`) because `store` printed it (Develop step 4). The witness is the one `store` wrote: train 0 turned a quarter turn clockwise.
- I added the witnesses `dominant-flip` and `stored-period-left` to the witness file. `witness` reported two cases that no run showed defined and differing from the case without their extra branch: `$DirFromScene & bg=DominantColor` and `$DirFromScene & seg.min_period=stored`. These witnesses show each one defined and differing, so both meet Subsumption and stay. `stored-period-left` reassigns `seg.min_period` to `(DIR_L, AXIS_H, 3)`.
- Where two directions both meet `$DirFromScene`'s test, the solver puts both directions' facts into the one case. If they disagree, the case is undefined; it does not give one grid per direction as `analyze.md`'s "each direction d" may intend. No pair or witness has two qualifying directions: one grid per direction would need a `TiebreakResolution` column, and the concept case reads its direction from a parameter.
- The concept case's period includes the vacuous one, the segment's whole length, when the segment has no shorter exact period. This follows the concept's "least p ≥ 1". `mirrored-scene` and `bg=DominantColor` rely on it, as `witnesses.json` gives them (the grid stays as it is). This is a reading of the concept file rather than a change to it, and is listed here because `OffsetInvariance.min_period` alone leaves it out.

## Judgments
- The concept branches are named `StoredDir` and `Whole`. `witnesses.json` names no concept branch other than `concept`, so no name in the witness file needed rewriting.
- `bg=DominantColor` gets `@derive DominantColor: variant concept`, as `analyze.md` gives it. `derive` lists no derivation for `dir`.
- `seg.min_period=stored` is `variant $DirFromScene`, `@relaxed segment-at-edge`. Its witness is a D4 image of train 0, so it occurs routinely in a variant task. The generator would pair it with the strip continued downward, and that is `$DirFromScene`'s output. The branch stores which direction's segment has a period. That is an artifact of keying the segment by every `Dir`, which `$DirFromScene`'s derivation needs.
- `dominant-flip` and `stored-period-left` show cases that each take two non-concept branches, so neither gets a `@witness` line or a plausibility.
- Determine reads each value from the evidence:
    - `bg` is the input color of cells the output changes.
    - `dir` is the edge that an output's ink reaches and its input's ink does not.
    The plan then reports no actions.
- Hints: `long-clause` and the determine-schema finding both fired once, and both are fixed. No other hint fired. Every run takes 3 s or less, so there is no performance issue.
- `deletions`: the 23 deletions that change nothing remove structure that no pair exercises, and all of it stays:
    - the vacuous-length clauses and their `Tally` items (shown by `mirrored-scene` and `short-row-run`);
    - the `reach` test and the start-edge test of `$DirFromScene`;
    - the per-line `split` atoms;
    - the axis atoms that keep a period on dir's axis;
    - the `line.a` and `period_at.l` columns.
  The three bound `dir_elem` enumerators stay, as the report says.
- Simplify left the code unchanged. `segment` and `run` differ in the same-line atoms. `seg_period` and `run_period` read different instances, and the runner's store clash rules out merging those instances.
- Dropped branches:
    - `$FirstRecur` fails Fit at train 1, where col 1 equals col 0 and the period comes out 1.
    - A stored period fails Fit, because the train pairs need 3, 4 and 6.
    - A phase counted back from the segment's end fails Equivalence. The cell it picks is in the same residue class mod p as the cell counted from the start edge, and the segment is periodic by p, the vacuous p included, so the output is the same on every input.
- No rule is approximated: `period` compares each line with the line p further on through `OffsetInvariance`, and `extend` reads the cell at the same place within the period through `stride`.
- Keywords are `wallpaper` and `lines`; `lines` is there for `$PerLine`.
- No audit check was skipped, and the last audit is clean.

## Unsettled
- `$DirFromScene` on an input where two directions qualify: either it is undefined there, as now, or it gives one grid per direction. A ruling on whether "each direction d" in `analyze.md` means several outputs would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- none
