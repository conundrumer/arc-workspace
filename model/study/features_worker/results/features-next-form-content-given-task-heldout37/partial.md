# Next form content given the task and the found tables

Status: finished through the held read. Numbers are in `read-held.md`, `read-held.json`, `slices.json` and `gold-revision-check.json`. Tune numbers are in `read-dev.md`.

## Unit and state

- Unit: gold forms in gold's order, RULE, DET and INIT.
- State before a form: the task's grids, and gold's earlier forms with their tables. This is an upper bound on what a search has found: a search holds junk forms beside these, and it may lack many of them.
- Rows come from a gold replay on engine `runtime-ba0754492` (`next_form_rows.py`), with the test output removed. The node records hold only the first third of gold's depth and no held task, so the replay takes their place.
- Check of the replay: on 3,170 seeded forms that match by text, 3,158 have equal row counts per train example (`gold-revision-check.json`).

## Tasks and gold revisions

- Fit: 15,153 forms of 1,011 tasks outside the 99. Text: `gold-v3-cover-forms-a036da074/corpus-view`.
- Dev: 1,535 forms of the 62 evaluation tasks outside the 37. Text: the census's own. Tune reads only.
- Held: 1,011 forms of the 37 tasks. Text: the census's own, so each row's text equals its census row's. By source, at forms of 25 bits or more: cover 85 forms on 10 tasks, helper 138 on 15, round 50 124 on 12 (`read-held.json`, `by_source`).
- Node records against the census: no stem is in both, as the node records hold none of the 99. So the separate count the brief asks for is 0 stems on held and dev.
- Node records against the fit text: 370 of 881 stems have a seeded form whose text differs from the cover view (`gold-revision-changed-stems.txt`). No fit row reads the node records, so these rows stand. Node junk serves only the pool gap below.

## Targets

- Component: the component of an INIT or of a DET, or `body` for a DET with a body.
- Reads: the set of tokens a RULE, DET or INIT form reads: lib relations, relation macros, fact relations, and a derived key.
- Derived key, my choice: for an INIT's relation, the component and the relation's declared ordinal, such as `D:Connectivity#0`. For a DET, its component or its column types. For a RULE, its column types with duplicates removed, such as `D:RULE:Color+Position`. A derived key is open only where a found form has it.
- Columns: `cols`, the sorted column types of the head table. `coarse cols`, with duplicates removed. An INIT's head table is its lowest declared relation with a table.
- Geometric shape, on the head's Position column with the most distinct values, one class per train example, then the most common class: empty, single cell, whole grid, h line, v line, h gapped, v gapped, diagonal, grid border, full rows, full cols, rectangle, ring, blob, lattice, dots, lines, blocks, scatter. `no position` and `no table` stand apart. See `shape_facts.py`.
- Relational shape, on the rows with constant columns dropped: empty, one row, set, cross product, equivalence, symmetric, order, permutation, chain, one to one, function, keyed, many to many. See `shape_facts.py`.
- `shape` is the two shapes as one value. `content` is component, coarse columns and both shapes as one value, with values of under 5 fit forms in `<other>`: .36 of dev forms and .43 of held forms fall there.

## Conditioning facts

- Need, `n_` and `n0_`. Changed cells: output cells that differ from the input, or all output cells where the shapes differ.
    - Cover: a changed cell is covered when a found table has a row with that position and that output color. A position alone gives position cover.
    - Explained: a cell's signature is its input color and what each found table says of it. A map from signature to output color, read on the other train examples, predicts the left-out example. Changed cells that it gets wrong are unexplained.
    - On the uncovered and the unexplained cells: count, share, colors, new colors, shape, components, adjacency to input objects, enclosure, on-object share. Also the best Jaccard of a found position table with the uncovered cells, and the share of need colors found. `n0_` holds the same at the task's start, and resize class, crop, embed, symmetry, period and color map.
- Found set, `fs_`: components, column types, row shapes and unread forms of the found tables, as a set, with no use of gold's order.
- Grid, `g_`: size, example count, object count, color count, input period.
- Order, `f_`: the last form written, its columns, shapes and component, the form count. A pool has no such order. Facts of this family are an upper bound. 72% of fit forms read the form written just before them (`slices.json`).

## Models

- A situation key is one fact or a pair of facts, inside the form's kind.
- A key's table gives a rate per value, with a Dirichlet fallback on the kind's rate for a sparse cell.
- The model is a softmax that starts at the kind's rates and adds the weighted log lift of each key. Weights are non-negative and fit on out-of-fold tables over task folds.
- Keys come from a greedy pick on fit rows, one target and one fact family at a time. Tiers: `need`, `foundset`, `need+foundset` (the union of those keys), `all` (those keys and the keys picked with the order family open).
- Reads as a tilt: at each relation pick of the census walk, each option's weight is multiplied by lift^gamma and normalized, so the saving is an exact change of the census's bits. Gamma is tuned on dev.
- Walks: totals equal the census on 1,519 of 1,519 dev forms and 1,005 of 1,005 held forms with bits, and the relation parts equal on the same forms (`walk-check.json`).

## Results on held

Forms of 25 bits or more: 347, mean 65.6 bits. 50 model reads, each once, and 3 pool gap reads. Intervals are 95%, from 10,000 resamples of the tasks.

Component and relation picks on one census walk, saved per form:

| Tier | All forms | 25 bits or more | Taken under 25, of 347 | Tasks under 25 |
|---|---|---|---|---|
| need | +.07 (+.02 to +.11) | +.13 (-.01 to +.26) | 2 | 0 |
| foundset | +.19 (+.07 to +.30) | +.15 (-.04 to +.36) | 6 | 0 |
| need+foundset, the primary number | +.21 (+.10 to +.33) | +.20 (-.01 to +.43) | 8 | 0 |
| all, upper bound with gold's order | +.84 (+.56 to +1.12) | +.23 (-.32 to +.88) | 14 | 0 |
| shuffled facts, tilt | 0 | 0 | | |

Against the bars: +.20 is under the .5 bar, and the whole interval is too. This form of the question closes. Dev read +.26 (+.04 to +.49) on the same tier.

`content` against its marginal, jointly over component, columns and shapes, need+foundset: +.32 (+.25 to +.39) on all forms, +.29 (+.17 to +.41) at 25 bits or more. Tier all: +.89 and +.67.

Share at forms of 25 bits or more: need facts add .25 of the census-unit saving and .15 of `content`.

Per target, need+foundset, on all forms: see `read-held.md`.

## What the need facts did

The need barely moves across gold's forms. Of 14,142 fit form steps, the uncovered count changes at 442, the position-uncovered count at 1,092 and the unexplained count at 751 (`slices.json`). So at most forms a need fact is a fact of the task's start. Gold builds long chains of tables that don't touch output cells until the last forms.

The clearest need signal is in DETs: where a needed color is found or new, DET picks shift between `DominantColor`-type components and a body.

## Prediction check

See `prediction.md`.

- Best single target at about .7: on the primary tier, `comp DET` reads +1.08 at 25 bits or more on 27 forms of 10 tasks. Next come INIT reads as a bag against the marginal at +.38 and `coarse cols` at +.30.
- INIT component saves most: missed. It reads +.19 on all forms and +.01 at 25 bits or more.
- Need under half of the saving: held, .25 and .15.
- Late forms gain more than early forms: missed. On all forms, the first third saves +.56 (+.31 to +.81), the middle +.05, the last +.01.
- Primary about +.25: held at +.20. Upper bound about +1.3 at 25 bits or more: missed at +.23.

## Pool gap, not a result

`pool-gap-held.json` reads log2 of gold's marginal over the pool's share of a head's columns: +3.22 at forms of 25 bits or more. This number is biased upward, so it isn't counted against any bar:
- Junk rows with no table are left out, so a gold head with no table has a ratio near 10 bits.
- An INIT's junk row is a random relation of the clause, and gold's is the lowest declared one.
- Junk nodes are distinct tables, so a repeated cheap table counts once.
- The pool's share is a kind marginal, not the sampler's chance at a state.
