# b527c5c6

## Departures
- The witness file has no `mark_color=RarestColor` witness: the `derive` run wrote it, and the branch it records left under Subsumption (see Judgments).
- The witness file has a new witness, `short-side-mark`. Without it, no run showed `$MarkSide & $ClipToBar` defined and differing from `$LongSide & $ClipToBar`.
- `corner-mark` has new groups and a rewritten `separates` text. `$LongSide` splits by span: `$LongSide & $PastEnd` gives the Analyze file's grid, and `$LongSide & $ClipToBar` drops the flank past the bar's end. The run against the Analyze file shows no difference.

## Judgments
- The solver has 48 cases: each combination of `Side` (`$MarkSide`, `$LongSide`), `Span` (`$PastEnd`, `$ClipToBar`), `Block` (`$PaintOver`, `$Underlay`, `$Blocked`), `Overlap` (`$NoOverlap`, `$CoreOnTop`) and `Colors` (`$StoredColors`, `$OwnColors`). Each fits every pair. The runner witnesses 9 of them, plus the `background=DominantColor` cases.
- `$StoredWidth` has no constructor. It fails Fit at train1, as the Analyze report states.
- `// @derive DominantColor: variant derived`: the derive witness is train 0 with 0 and 1 swapped. A color permutation is a variant task, and the generator pairs that input with the derived output.
- `mark_color` takes `// @ignore: derive RarestColor`, which fails Subsumption. Only `$StoredColors` cases read `mark_color`. With the derived value, such a case is defined only where every piece is `bar_color` with exactly one cell of another color, and `$OwnColors` gives the same output on that input. A piece of two cells could break this, but its mark sits on three sides, so the case is undefined there.
- Not formed, "flank width as the distance from the mark to the bar's far side": this is not a constructor because it fails Equivalence. The mark sits on the marked side, so on every input where a beam side is defined, that distance is the bar's extent across the side less one. No input separates it from the concept.
- How the flank width is encoded: each line of the beam stands at a "foot". A foot is a cell on a diagonal through the mark and within the bar's rows or columns across the marked side. For `$ClipToBar`, the foot must also lie within the bar. A foot k cells across lies k cells behind the mark, so the feet give k up to the thickness less one with no arithmetic.
- The core takes the input color of the mark cell. Under `$StoredColors`, the mark cell is `mark_color`, so this is the concept's `beam-core`. Under `$OwnColors`, the core takes the piece's own mark color.
- A mark on no side of its bar (an interior mark) leaves every case undefined. This agrees with `probe.py`. The concept file states only the case of more than one side.
- `short-side-mark`, which I built: a 3-wide bar with the mark at the middle of a short side. Plausibility `borderline`, because it breaks `one-mark-per-bar` (the mark is on a long side). Verdict `concept`, because the concept's reading shoots the full-width beam from the marked side. It is not a branch's witness, so it has no `@witness` line.
- `@claim clear-paths` under `PaintOver` and under `NoOverlap`: each of those points turns on what a beam does where the path is not clear. That case is the one `clear-paths` excludes.
- Lint hint `pass-through` on `stray`: `stray` fed only `bad_piece`, so I folded it into a `$StoredColors` clause of `bad_piece`.
- Deletions: 24 deletions change no pair output. They are the defect relations (`hollow`, `bad_piece`, `undefined`), the branch-only clauses of `$LongSide`, `$Underlay`, `$Blocked` and `$CoreOnTop`, and the `piece.label` join that gives `flank` its own bar's color. The pairs do not instantiate any of these, and the witnesses need each one. Of these deletions, I applied only the unused `beam.id` column.
- Performance: a full run takes about 2 s, so no workaround was needed.
- Determine: the sweep and the plan list no actions, so the solver has no `Determine` comp.

## Open
- `@claim` of the concept constructors under `Block` and `Overlap`: the branches change `beam-direction`, `beam-core` and `beam-flanks`, and add `core-on-top`, but no single header claim covers them. A review of which slug the directive should name would settle it.

## Lib
- Solid-piece test, "a component that does not fill its bounding box": the solver-local form is `hollow(Id) :- piece_box.box(Id, B), in(P, _), inside(P, B), !piece.label(_, P, Id).` The grep finds the same shape in 538b439f (`hole`), a32d8b75 (`region_gap`) and abbfd121 (`part_gap`). All three are drafts.

## Fixes elsewhere
none

## Tickets filed
none
