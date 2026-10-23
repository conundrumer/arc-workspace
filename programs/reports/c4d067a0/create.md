# c4d067a0

## Departures
- The `$NoClip` branch's model, and every combination of `$NoClip` with `$UniqueMatch`, is no case: under one match, a drawing that runs past the grid is undefined or is the clipped one, so each such combination is subsumed by the same combination with `$Clip`. `impl_choice` holds `$NoClip` only with `$EveryMatch`. This is a Subsumption result, and the Analyze report did not err. `witness --file work/task/c4d067a0/witnesses.json` reports for each of its six witnesses that `$NoClip` names a model that is no case.
- `$EveryMatch` gives a grid for each placement through an `out` column of type `TiebreakResolution`, `Run {a, q, step, pitch}`, on a task with no alt: no other column type the handbook allows holds one grid per match (ticket 10-692). Every case reads that column. The concept case reads one distinct grid there, because it gives no output where some given block receives two key dots.
- The witness file adds `run-off-top`, `corner-dots` and `grid-21` (see Judgments), and the `derive` witness `key_pitch=TileDim`.
- The `@derive TileDim` branch on `key_pitch` is a case point that the Analyze report does not give. `derive` lists it as a derivation that fits.
- The header has no `@scene key-corner`: no `@claim`, `@relaxed`, rule text or branch reads it ([Style > Header](docs/handbook/style.md)). `given-blocks` gives `blocks-axis` as the horizontal axis.
- Each placement carries the key pitch it matched at. So a multi-valued `key_pitch`, as `TileDim` gives, draws one key reading per pitch and does not mix them. With this, the `TileDim` cases that take `$BackgroundBlocks` fit every pair, and no `@ignore: derive` line is needed.

## Judgments
- The first Not formed item, the key found at a stored corner, is not formed. It does not say which cells near the corner form the key. The reading that makes it one model, the cluster of cells one key pitch apart, makes the key depend on the pitch, and under `$KeyPitchFromKey` the pitch depends on the key. The second item gives no model other than `$StoredCrossGap`, which fails Fit.
- `@derive TileDim: variant derived`, `@relaxed key-period`. On `key-pitch-three`, TileDim gives a pitch set that includes 3, which is the key's pitch, so it gives the output that `$KeyPitchFromKey` gives and the generator would pair with that input.
- `corner-dots` is train0's input with its four corners set to 1. It is `borderline concept`, `@relaxed key-period`: the corner cells are single non-background cells off the key's period class, which a generator rarely places, and a person still draws the key. It shows `$BackgroundAtCorners` defined and different from `$Commonest`, so that case meets Subsumption. It has a `@witness` line under that branch.
- `grid-21` is train1's input cut to 21×21. It is `ordinary concept`: 2 is no TileDim tile size of a 21-cell side, so `key_pitch=TileDim` is undefined, and the stored and derived pitches give the concept output. It separates `$KeyPitchFromKey` from `$StoredPitch & key_pitch=TileDim`. It has no `@witness` line, as a further witness of a `@derive` branch.
- `run-off-top` is `borderline`, with verdict `$EveryMatch & $NoClip`, and breaks `blocks-match-key` and `fits-grid`. Two runs match, and one drawing runs past the top. A person would keep the drawing that fits. It shows `$EveryMatch & $NoClip` defined and different from `$EveryMatch & $Clip`. It has no `@witness` line, because the `$NoClip` branch's model is undefined there, as the concept is.
- Hint `case section`: relations that dropped a choice field while they read a field-keyed relation (`key_slot`, `block_slot`, `drawn` through `pitch` and `key_point`) did read both branches' facts. Each placement-keyed relation now carries the pitch, background, spacing and overlap fields it varies with.
- Finding `choice-tag` on `key_point`: the `$PaintOver` and `$UnderlayDrawing` clauses are one clause over `overlap_choice(Ow), Ow != $BackgroundBlocks()`.
- Determination: the plan asked for a relation from the fact the concept derives the pitch from. `Determine` keeps the pitch that every input's key has, the greatest pitch that divides every key-dot offset. The key-dot parse, that pitch derivation, and the commonest-color `Mode` moved into `Parse<Key>`, which the program keys by `Background` and `Determine` keys by `Example`.
- Deletions: `run_match`'s `q2` column and the `stride` atom in `pitch_cand` are removed, because neither changed any output. The other deletions that change nothing remove structure the pairs never instantiate: the ambiguity test, the off-grid test, background key points, the square test on blocks, the pure-translation test between blocks, and the per-placement key columns. They stay.
- Keywords `objects scale match`: the key and the blocks are one-color pieces, the drawing is the key at a larger scale, and the blocks pair off with a key run by color and order.

## Open
- The audit's `store` check skipped `block_slot`: it has over 20000 rows on an input. A store check that handles relations of that size would settle it.
- Whether a key found at a stored corner is a model of this task: a rule for which cells around the corner form the key, one that does not depend on the key pitch, would settle it.
- Whether `TiebreakResolution` may carry `$EveryMatch`'s grids on a task with no alt: a ruling on ticket 10-692 would settle it.

## Concept faults
- none

## Fixes elsewhere
- none

## Tickets filed
- 10-692_task_c4d067a0_create.md
