# Experiment: can table features tell informative tables from redundant ones?

## Question

A search that uses arclog queries to perceive a task sees the task only through the tables that `RULE` and `DET` queries give. A person who reads such a table sees patterns, judges what is relevant, and compares the table with earlier tables. A model that guides the search needs numbers that carry the same information. This experiment asks whether handwritten feature extractors over tables give enough signal for a model to learn which tables are worth making.

## Theory under test

- A query is a set of hypotheses about the task, for example "the result is not empty" or "the table has one row at every example". A feature extractor tests one of these hypotheses on the query's table.
- Feature, label, class and test are four views of one object: a function of a table and of the tables that table derives from.
- A hypothesis gives signal only when it can both hold and fail while every input of the query is correct. Such a hypothesis is contingent. A hypothesis that the inputs entail, or that the inputs rule out, tests nothing.
- A hypothesis may read the task's base tables (`input`, `ex_input`, `ex_output`). That is how a hypothesis links a table to the output and so becomes relevant.
- Features are handwritten. The model learns how to interpret them. Any code that classifies tables is a development tool. It is kept apart from the features and it is never model input.
- Labels are diagnostics. A disagreement between a label and a human reading is useful when its cause is known. The cause is a flaw in the theory, a gap in the feature library, or a limit of the test.

## Terms

| Term | Meaning |
|---|---|
| Feature | A function from tables to a value. It may read the query's table, the tables upstream of it, and the task's grids. |
| Precondition | A constraint on the input tables of a query. It is the set of postconditions of the tables the query reads. |
| Postcondition | A feature with the values that count as holding. On the task's examples a postcondition is the feature's value (one value, a set of values, or a range for a number). |
| Entailed | Every input that meets the preconditions meets the postcondition. |
| Contingent | Some input that meets the preconditions meets the postcondition, and another does not. |
| Counterexample | An input that meets the preconditions and fails the postcondition. One counterexample proves that a postcondition is contingent. |
| Informative table | A table with a postcondition that is contingent, true on the evidence, and not equivalent to a postcondition of an earlier table. |
| Redundant table | A table whose postconditions are all entailed or equivalent to postconditions of earlier tables. |
| Live or dead (redundant table) | Known after the fact. A redundant table is live when an informative table or the output reads it, and dead otherwise. |
| Instrumental value | Known before the fact. It is the estimated chance that a redundant table leads to an informative table or to the output. A model has to estimate it. |

Earlier working names were signal (informative) and plumbing (redundant). Related ideas in the literature are design by contract, assume-guarantee reasoning, vacuity checking, Popper's empirical content, the Duhem-Quine problem, prior necessity in inductive logic programming, witness functions in program synthesis, and premise selection.

## Design

### Feature structure

Each feature has three coordinates, recorded in `features/schema.py`.

- What it reads: static (the query text and the column types the checker infers from it) or dynamic (the rows).
- Level: per example, per assignment (pooled over the examples), or across assignments (pooled over the assignments). The constraint-model level is skipped.
- Arity: the owner table plus every other table the feature reads. Each other table is a parent (the query reads it), an ancestor at a depth, or a base table.

A pooling operator lifts a feature from one level to the next: all equal, count of distinct values, range, spread, share that hold, and "f is a function of g". A row count needs no special case, because it is a per-example feature that these operators lift.

### Layers

- `features/` is model input. It reads no label, reading or variant.
- `guarantees/` holds facts that a lib component fixes by construction, for example that a `BoundingBox` without a key has one row. The labeling uses it, and it is never model input.
- `dev/` holds the labeling and the test harness.

### Variants and verdicts

Variants play the part of counterexamples. They edit the task data only. Edits to a table are not made, because any postcondition fails when a table is edited directly.

- Input variant: a mutated train input, run as an extra test input with a placeholder output. The train pairs and stored values stay fixed.
- Output variant: a train output with edited cells. It checks input-side preconditions only.
- Cell edits: erase, grow, recolor, speck, swap. Object edits: move, copy, recolor and remove a whole object.
- A targeted search keeps a pool of variants that meet a table's preconditions, edits them further, and keeps a result that still meets them.

A variant counts for a postcondition only when it changes the table and meets the preconditions. For each postcondition the verdict is one of: new, redundant (the same failure vector as an earlier postcondition), entailed, by construction, untested.

A table is informative when any postcondition is new. The preconditions of a table are the postconditions of every table upstream of it, of the input grid, and of the input ports of its own instance.

### Tasks and readings

- Tasks come from the train and dev splits. None of the ARC-AGI-2 evaluation tasks is used.
- Twelve tasks form the development set. Two batches of twelve further train tasks form the held-out batches. Held-out means that the readings were written before the analysis ran and that the library was not tuned on them at that point.
- Before any verdict was computed, each table of each task was given a reading: claim (the task's concept implies it), redundant live, or redundant dead. These readings are the reference for agreement. One person wrote all of them.

## Procedure and results

### Reading tables by hand

Every table of three solvers was dumped and read: 3194b014 (small), 25d487eb (medium) and 6b9890af (a large `&output` clause). The reading gave fourteen candidate features, grouped as follows.

- Inside one table: row count of 0 or 1, size against the input, degenerate values (a box that is the whole grid, an empty table), the shape of a cell set.
- Across train examples: a row count that stays the same while values change, a value that stays the same, an invariant in a column's distribution.
- Against the train output: overlap with the cells that change, color agreement, size agreement, agreement in another frame.
- Between tables: subset, complement and partition relations; redundant re-encodings, such as the unused outputs of an `Order` instance.
- Across assignments: a wrong assignment shows early, as in 6b9890af, where a background-colored frame value gives a whole-grid box.

### Gold against search noise

A labeled set of gold tables and noise tables did not exist. The search draws of one dev task (9af7a82c) were replayed into rows and labeled by table hash against the gold graph. The labels were consistent, but the data was rejected for these confounds.

- State search: about half of the noise tables are `RIGID_DET`, and gold has none.
- Both searches: empty tables occur only in the noise.
- Pool search: all noise sits at depth 0 to 2, and gold reaches depth 12.
- Gold includes redundant tables, for example every output of an `Order` instance, so gold does not mean claim.

The study continued with gold programs only.

### Falsification by hand on 25d487eb

Eleven hypotheses about five clauses were falsified by edits of 1 to 5 cells of one train input. A twelfth, "`&beam` lies on one line", also failed, although the `Ray` component seemed to guarantee it. Two beams from two marks give two rays.

Some of these edits corrupted an earlier table first. For example, blanking the grid empties `&ink` before `&body.maximal` can fail. The rule was then tightened: a failure counts only when every table the query reads still meets its own postconditions. With this rule, fifteen postconditions were contingent and five were entailed. Content constraints upstream made some count constraints downstream entailed. For example, once "the mark is at the middle of its box edge" holds upstream, "`&cast_dir` has one row" cannot fail. Whether a postcondition is entailed therefore depends on what sits upstream of it.

A run on the tables that the solver does not need to state a claim gave this pattern.

- The unread `Order` outputs and `&rays_cell` (the complement of `&ink`) are redundant. Each postcondition is entailed, or equal to a postcondition on `&body_count` or `&ink`.
- `&rays.ray` is informative. "The changed cells lie on the ray" is contingent, and no earlier table can state it.
- A component output that the solver reads carries a hypothesis. `&body.maximal` having one row means that no two colors tie.

### Automated baseline on four tasks

The harness above (25d487eb, 3194b014, 6b9890af, a61ba2ce) computed verdicts from generated variants.

- Agreement with the readings: claims such as `&ink`, `&mark`, `&beam`, `&frame_box.box`, `&comp4.component` came out informative. Redundant tables such as `&bbox.box`, `&hole.box`, `&body_count.size` and most unread `Order` outputs came out redundant.
- Disagreements per task went from 7, 8, 5, 8 to 7, 8, 6, 9 after whole-object edits and two new features. Causes of the disagreements:
  - Untested: small edits cannot reach stored values (`&bg`, `&frame`, `&side`), ties, or exact shapes.
  - The redundancy check cannot see arithmetic, such as a cell count equal to the grid size minus another count.
  - A pair feature compares a table only with tables upstream, so the first reader of a table gets credit for facts about that table.
  - The earliest table that carries a fact gets the credit, even a dead sibling.
  - A range from three or four examples is often a coincidence and counts as new.
  - Gaps in the library: box side lengths, and the distance between objects.
- A variant that removes a proposer's value (for example the frame color) left no assignment that solves the train pairs, and the engine silently took the first assignment. This hit 554 of 5850 input variants in 6b9890af. Each variant now has a status, and a variant that breaks a stored value tests only that relation.

### Scaling to 36 tasks

The library gained box sides, bounding boxes of cell sets (whole and per group), grouping by color, counts per group, the least distance between groups, and "column A fixes column B". The pooling operators filled the per-assignment level. Variants (53,190 for the first twelve tasks) are saved per task in `corpus/`.

For each generic hypothesis the experiment counts the tables where some variant falsifies it while the preconditions hold. The table shows that count among tables whose reading is claim, and among tables whose reading is redundant, over all 36 tasks. A hypothesis that separates the two groups is a useful filter.

| Hypothesis | Claims falsifiable | Redundant falsifiable |
|---|---|---|
| Result is not empty | 41 of 137 (30%) | 10 of 163 (6%) |
| One column fixes another | 38 of 101 (38%) | 28 of 131 (21%) |
| Any feature at all | 130 of 140 (93%) | 121 of 171 (71%) |

Within the development set the ratio of the two rates is 8.0 for emptiness, 3.9 for "one row", 2.7 for distinct values, and 2.3 for bounding box features. Relations to the train output are falsifiable for nearly every table (94 to 97%), so they do not separate the groups. The separation by emptiness reproduced on both held-out batches (ratios 2.7 and 7.8).

Agreement of the full verdict with the readings, over all 36 tasks:

- Claims: 105 agree, 35 differ, 36 untested.
- Redundant tables: 79 agree, 92 differ, 28 untested.

By query shape on the development set, a proposer `DET` was informative in 6 of 6 cases, a `RULE` with `NOT` in 4 of 15, and an instance output in 1 of 48.

### Library growth

After the 36-task result, work shifted from separating claims from redundant tables to growing the library. Batches of features were added in order and each batch was measured against the previous library. The measure is the count of postconditions that some variant falsifies at a point where no earlier feature changes value. The first batch added cell sets in program-made frames, shape features (fills its box, symmetry count, enclosed regions, 4-connected components, distinct shapes per group), relations to the input grid, and features for direction, D4, offset and Ident columns. On a quarter sample of the variants, the families with the most postconditions broken only by new features were symmetry (58), enclosed regions (55), shapes per group (53) and 4-connected components (35). Most row changes that no feature shows were renamed object labels. Later batches added grid position, shape relations across frames, agreement of (cell, color) rows with the train output, periods, graph components, and constraint counts as static query features. A cache of each variant's tables lets a library change skip the engine.

## Findings

- A hypothesis can be falsified by editing task data only, while the inputs of its query stay correct. Entailed hypotheses are those that a clause or the inputs fix.
- Judging falsifiability from the clause text alone is unreliable. The "one line" case on `&beam` was misjudged. The test has to run.
- Contingency is necessary for information. It is not sufficient for relevance. Relevance needs a hypothesis that reads the base tables.
- The emptiness hypothesis separates claim tables from redundant tables on all three groups of tasks. The hypothesis may follow query shape, since the readings follow it too.
- The set of all features together separates the groups only weakly (93% against 71% falsifiable). The cause is credit to the first table that shows a fact. Of 31 redundant tables that came out informative in the development set, 16 were instance outputs, 7 were instance input ports, and 8 were selections such as "the cells of the background color". Of 15 claims that came out redundant, 7 were explained by features of the input grid.
- Disagreements split into library gaps (fixed by adding features) and limits of the test (arithmetic, stored values, small example counts).

## Limits

- One person wrote all readings, and the readings follow the person's knowledge of each concept.
- Three or four examples per task make graded ranges loose.
- A library grown on these tasks may fit them. The held-out batches were later folded into the growth corpus, so only the first analysis of each batch is a clean test.
- Stored values change only when a variant breaks their proposer. Testing them needs a variant that edits a whole train pair.
- Tables are computed at the one assignment that solves the train pairs. That choice reads the train outputs, which are unavailable at search time. The across-assignments level is empty.
- Only the first constraint model's rows of each example are used.
- Entailed and equivalent mean that no counterexample was found. They are not proofs.

## Open work

- Test the other hypotheses that a query makes by its shape, for example "every key has a row" for a keyed instance and "no key has two values" for a `Singleton`.
- Add features that inform the instrumental value of redundant tables. Live and dead labels from the corpus are the targets for that.
- Fill the across-assignments level.
- Replace the handwritten reading with a learned interpretation of the features.

## Files

- `README.md`: layout of the library and how to run the tests.
- `features/`, `guarantees/`, `dev/`: the three layers.
- `corpus/`: saved variants per task. `cache/`: saved tables per variant.
