# Cases and judge

It builds the models of a case on an input, from its `ONE` and `CHOOSE` forms, its open values, its `DEMONSTRATED` forms and its `Unfold` walks, and the judge of the solves relation, the case conditions and the witnesses. It rests on [constraints](../../docs/arclog/constraints.md) and on the handbook's [Cases](../../docs/handbook/solver-file.md#cases). Here solves is the handbook's fit, and hypothesis the handbook's model, as [Requirements](overview.md#requirements) gives.

Three steps of the [build order](overview.md#build-order) build it: one before [Synthesis](synthesis.md), and two after it.

## One case

- The step before Synthesis builds what a synthesized program reads: one case, with no `DEMONSTRATED` form. It builds [Models](#models), [Open values](#open-values) for the readings that [Open parameters](synthesis.md#open-parameters) gives, and [Candidates](#candidates), [Solves](#solves) and [The output of the `OUT` form](#the-output-of-the-out-form) of the judge. The open values of the derived reading of a `DET_OR_RULE` line are built with that reading.
- The step ends when each solver's concept case that reads no `DEMONSTRATED` form, and no open parameter on the derived reading, at the stored `param` records, gives on each pair the set of grids, or `undefined`, that the snapshot records, and the solves outcome that Souffle gives, as [verification.md](verification.md) checks them, or the difference is reported as a fault, as the Principles requirement of [Requirements](overview.md#requirements) gives. Every solves outcome of the snapshot is `fits`, so the grid sets carry the check. `arclog-cli compare` compares a pair's set of grids with the snapshot's, where step 2 compared one grid.
- The tests of the judge, of the kind that [Tests](../../prompts/agents/notes/tests.md#tests) keeps, refuse wrong input: a train pair under open-world candidates whose output set does not hold its given output, a pair that the case does not solve, and an `Unfold` instance whose tied walks give grids that the pair does not accept.

## Every case

- The step after Synthesis runs every solver in full. It builds every case of a solver's `ALTS` forms, as [Cases](#cases) and [Models](#models) give, [Open values](#open-values) of every reading, the [`DEMONSTRATED`](#demonstrated) forms, and [Reports](#reports). Each case runs at the values that [Determination with no stored value](determination.md#determination-with-no-stored-value) gives.
- The step ends when the engine is at parity with Souffle on each case's output on each pair and on whether it solves the task, as [verification.md](verification.md) checks them, or the difference is reported as a fault, as the Principles requirement of [Requirements](overview.md#requirements) gives. The check has these parts:
    - `arclog-cli determine`, as [End check](determination.md#end-check) gives, compares the determined values for each parameter that is not a pick and that no case with a `DEMONSTRATED` form reads. The parameters that a case with a `DEMONSTRATED` form reads, such as 351d6448's `&time_corner`, and the picks, such as b7f8a4d8's `&draw_rank`, are left to `arclog-cli compare`.
    - `arclog-cli compare`, run over every case, compares each case's output on each pair with the snapshot's record of the case, and its output on each witness input, at the `param` records and the witness's `assign` forms, with the record's on that witness. A case with an open parameter is compared by its output set, as [Open values](#open-values) gives. The snapshot keys a case by the name that `case_name` of `src/parity/__init__.py` gives it, and an engine case maps to that key by the same rule, from its `CaseName` of `engine/arclog/src/solver.rs`. The check reports each case that only one of the two sets holds, and the rerun of [Mismatch report](verification.md#mismatch-report) takes the snapshot's name.
    - A difference in a determined value is reported before the differences in output that it causes.
    - The run's time per solver is compared with Souffle's time in the snapshot, as the Speed requirement of [Requirements](overview.md#requirements) gives, and each solver that runs slower is reported.

## Refine step

- The step after the full run builds the rest of the judge: [Witnesses](#witnesses) and [Case conditions](#case-conditions), with the witnessed-case set that [Cases](#cases) gives. [Tooling](tooling.md) builds the rest of the step and gives its end check.

## Cases

- A solver's cases are the product of its `ALTS` forms, restricted by the nesting of the blocks, less the combinations that the arcdata file's `exclude` forms leave out. An `exclude` form that leaves out the concept case is a fault of its solver, and the engine reports it, since [Cases](../../docs/handbook/principles.md#cases) has the concept case as a case. A case's **base** is its choice at each `ALTS` form that the file writes: the concept case's answer or one of the form's alts. A `DET_OR_RULE` or `RULE_OR_DET` line splits only the bases whose `OUT` form reads its relation, through clauses, instances and `RIGID_DET` forms and through no `DET`'s body, so the cases of one base differ only in their readings at those lines. `cases()` of [Solvers](reader.md#solvers), built in [Reader and checker](reader.md), follows this rule, and gives a solver with a `representative` line the representative's cases, or the one case the line names.
- Each case is one program, with no `Choice` column. The [result cache](evaluator.md#the-result-cache) shares the entries that the cases' relations hold in common.
- The judge's checks of the [refine step](#refine-step) report on the witnessed cases alone, as [Cases](../../docs/handbook/solver-file.md#cases) defines them. That set depends on each case's output on the pair inputs and the witness inputs, so that step evaluates every included case on those inputs. [Alts structure](corpus-survey.md#alts-structure) gives the counts of cases per solver.
- In the refine step, the names of an `output` form expand to their cases as [Witness file](../../docs/handbook/solver-file.md#witness-file) gives.

## Models

A model of a case on an input is one choice at each of its picks, as [Semantics](../../docs/arclog/constraints.md#semantics) gives, one open value of each open parameter it reads, one confirmed rule at each key of each `DEMONSTRATED` form it reads, as [`DEMONSTRATED`](#demonstrated) gives, and one joint walk of each `Unfold` instance whose `score` ties, as [Lib](evaluator.md#lib) gives. A joint walk of an instance is one walk at each of its keys, and its outputs are the facts along those walks, so the instance's factor is the product over its keys of each key's walks. The case's models are the product of these factors.

- The picks and the `DEMONSTRATED` forms are solved in dependency order. A pick, a `DEMONSTRATED` form or an `Unfold` instance that reads a pick or a `DEMONSTRATED` form, as an ancestor in the case's [dependency graph](reader.md#the-dependency-graph), is built once per model of each one it reads, since each chosen relation, and the relation of each `DEMONSTRATED` form, holds the rows of one model of the program, as [Semantics](../../docs/arclog/constraints.md#semantics) gives. In b7cb93ac, `&ties` reads the `CHOOSE` `&pruning`, so the options of `&ties` are the rows of its clause at one model of `&pruning`.

### The constraint module

- The constraint module is a finite-domain constraint solver over the picks. Its options are the rows of a clause with `ONE` marks and the `from` rows of each `for` row of a `CHOOSE`. Each option is kept or not. A **group** is a set of options of which a model keeps exactly one: for each `ONE` mark of a relation and each value of its key that has rows, the rows with that value, and for each `for` row of a `CHOOSE` that has a `from` row, its `from` rows. No model keeps the two options of a `never` pair, as [Choose](../../docs/arclog/constraints.md#choose) gives the pair. A `never` pair of one option with itself constrains nothing. These constraints restate [Semantics](../../docs/arclog/constraints.md#semantics).
- A `for` row with no `from` row is absent from every model. The options split into clusters, the connected components of the graph whose edges join two options of one group or of one `never` pair. A cluster with no model contributes no rows, and the product goes on over the other clusters.
- On each cluster, the module runs propagation to a fixpoint, and then searches depth first, branching on the group with the fewest open options, the first such group where several tie, and visiting one node per open option of that group, with that option kept and propagated, in index order. The search runs under a cap of 2^10 = 1024 nodes per cluster, which is the default of the node cap of [Decode settings](synthesis.md#decode-settings). Propagation applies these rules:
    - a group with one option left forces that option;
    - a forced option excludes the other options of each of its groups, and each option that forms a `never` pair with it;
    - a group with no option left leaves the cluster with no model.
- The module visits clusters, options and values in a canonical order by content, with Idents ordered by their contents as a writer numbers them, as [Terms](reader.md#terms) gives, so a stop at a cap does not depend on an encoding order. The options of a pick compare column by column in the order of the canonical labeling of the pick's form, the labeling that the form's hash is made from, and not in the order the relation lists its columns. A file Ident compares by the rows that hold it: the Idents are ranked by color refinement over the options, and two Idents that the refinement does not tell apart compare by their written numbers, so the first model of a pick is a function of the options' content, up to the symmetries of the options. The node cap is a fixed count. On 2026-10-23, `arclog-cli row-counts` over the 18 solvers of `work/arclog/gen/` with a `CHOOSE` form searched at most 512 nodes in one cluster (b7cb93ac on train/2), and at most 12 nodes in a cluster of each of the other 17 solvers.
- The models of one case on one input, its `DEMONSTRATED` choices included, run under a cap of 2^9 = 512, which is the default of the model cap of [Decode settings](synthesis.md#decode-settings). The cap is a fixed count, and its evidence is in [Open values and constraint search](corpus-survey.md#open-values-and-constraint-search): the models per case per input that survey measures stay under it, for the forms it measures. The most models of one case on one input in `work/arclog/gen/` are 256, of `&pruning` of b7cb93ac on train/2, counted on 2026-10-23 by `arclog-cli row-counts` under a model cap of 2^24.
- Reaching the node cap is a stop at a bound, and so is reaching the model cap where [Enumeration and its stops](#enumeration-and-its-stops) gives no set at the cap: the case has no output on that input, the result cache does not store the stop, and the stop is an alert, as [Joins](evaluator.md#joins) and [Bounds](overview.md#requirements) give.
- The module gives the models one at a time.
- A cluster is enumerated where its chosen relation, as [One](../../docs/arclog/constraints.md#one) defines it, is an ancestor of `&output` in the case's dependency graph, over every read edge, a negated read included. A chosen relation, or the relation of a `DEMONSTRATED` form, that is no ancestor of `&output` takes its first model in the canonical order, as the options of a pick are ordered above, since no output reads it.
- A `DET` reads a chosen relation, or the relation of a `DEMONSTRATED` form, only where that relation has one model, on each example where the `DET` reads it lifted. Otherwise the engine reports an error that names the `DET` and the pick.

### Enumeration and its stops

- For each model, only the entries downstream of the chosen relation are computed again, as [The result cache](evaluator.md#the-result-cache) gives.
- On an input, enumeration stops as soon as the grids so far decide the comparison that the input serves, by [Solves](#solves):
    - a train pair under closed-world candidates: at a grid outside the pair's candidates, or once the grids lie in two different candidates;
    - a train pair under open-world candidates: at the third distinct grid, or at the second where neither grid is the given output;
    - a test pair: at the third distinct grid;
    - a witness input, in the refine step: at the first grid outside every grid that the witness's `output` forms record.
- An undefined grid stops each of these too, except on a witness input whose record holds `undefined`.
- The walks of an `Unfold` instance are enumerated lazily, as the other models are, under the same stops. A stop counts distinct grids, and not distinct sets of output facts, since two joint walks whose facts differ can give one grid.
- An enumeration that stops early gives the output `outside`: three or more grids or undefined on a test input, and outside the candidates or the record on the others. Every comparison of the judge treats `outside` as different from every output, itself included. Below the model cap, whether an enumeration stops early does not depend on the order of the models, so no comparison does. An early stop is not a stop at a bound, as [Reports](#reports) gives.
- In the consistency tests and the attempts of a decode, an enumeration that reaches the model cap before it stops early gives the set of the models up to the cap, the set it would give if the cap were its last model, in place of a stop at a bound. The judge counts each such set, and the trace of a decode records the count, as [Traces](synthesis.md#traces) gives. The admission of a `DET`, the determination and the judged run of a case on a pair give a stop at the model cap.
- Where a comparison needs the full set, as a witness group does on a witness input where the case's grids so far lie inside the record, enumeration goes on to the last model or, where the cap rule above applies, to the cap.
- A case that solves the task has, on each pair, a set of the models up to the last model or up to the model cap. At the cap the set depends on the order of the models: a model past the cap can give a grid that the set lacks, such as a third grid or a grid outside the candidates, and the set can solve a pair that the set of every model does not.

## Open values

- A parameter has open values under one of three readings:
    - A `DET` whose body ends in `ONE` marks is a chosen relation, task-wide as [Program](../../docs/arclog/arclog.md#program) gives, and the constraint module solves it. Its models are its open values.
    - Of the values that a `DET` by a proposer with `(ONE)` gives, those that the train pairs leave are its open values, as [`DET`](determination.md#det) gives.
    - On the derived reading of a `DET_OR_RULE` line with `(ONE)`, each value the proposer gives on the input is a model, as [Open values](../../docs/arclog/arclog.md#open-values) gives, per input.
- The open values that M_open uses are those left after the intersection across cases of [`DET`](determination.md#det).
- M_open, as [Open parameters](../../docs/handbook/principles.md#open-parameters) gives, is used by the solves test alone, as [Cases](../../docs/handbook/principles.md#cases) gives. So the output is undefined where the case is undefined at some open value, in that test alone.
- Outside the solves test, the output of a case with an open parameter is the set of grids over its models that [Models](#models) gives, which the snapshot records. [Every case](#every-case) compares that set, and the witnesses and the case conditions of the [refine step](#refine-step) read it.

## `DEMONSTRATED`

- For each `DEMO_RULE`, the engine evaluates `&prediction` once per input, an entry that holds every key. At each key, a demonstration `(o, o2)` confirms the rule where the rule's prediction rows for `o` at that key, by `i` and `v`, equal the `value` rows of `o2`, as [Demonstrated](../../docs/arclog/arclog.md#demonstrated) gives. The cost per input is the rules' evaluations, then one comparison of row sets per rule, key and demonstration.
- A key with no demonstration, or with no confirmed rule, holds no prediction, as [Demonstrated](../../docs/arclog/arclog.md#demonstrated) gives.
- Each choice of one confirmed rule per key is one model, as [Demonstrated choice](../../docs/handbook/solver-file.md#demonstrated-choice) gives. Rules whose predictions at a key are equal give one model there, since the relation has no rule column.
- A rule with fields stands for one rule per value that its clauses bind for the field.

## Judge

### Candidates

- A run has closed-world or open-world candidates.
    - **Closed-world candidates:** a train pair's candidates come from its alts by their kind, as [Alt outputs](../../docs/handbook/solver-file.md#alt-outputs) gives: a `rule` alt gives a second candidate, a `tiebreak` alt adds a grid to the candidate, and a pair with no alt has one candidate, its output. A run on the task data of this repo is closed-world.
    - **Open-world candidates:** a pair with no alt may still have a tie that the data does not show, so its given output is one grid of an unknown candidate. A run on Kaggle task data is open-world.
- The judge reads the candidates from a record of its own, `JudgedTask`, read from the task file beside `Task` of `engine/arclog/src/task.rs`: each pair's given output, the test pairs' included, and the pair's alt where the file gives one. The task file gives at most one alt per pair, `alt: {kind, grid}`. `Task` holds neither the test outputs nor the alts, since the evaluation reads neither.

### Solves

- A case solves some split task exactly when each pair has a candidate it solves, since a [split task](../../docs/handbook/principles.md#models-and-tasks) chooses a candidate per pair. So no split task is enumerated.
- Under closed-world candidates, solves is the handbook's fit: a train pair's output set equals one of its candidates, and a test pair's holds at most two grids, one of them in one of its candidates.
- Under open-world candidates, a train pair is solved where its output set holds at most two grids, one of them its given output, as a test pair is. The strict definition there would refuse each program that states a tie, and accept a program that breaks the tie by a hidden order only where that order matches the data. The determination's filter by the train pairs, in [`DET`](determination.md#det), reads a train pair this way on an open-world run.
- On Kaggle, a program is tested against a task with open-world candidates on the train pairs, and on each test input its output is defined and holds at most two grids, which needs no test output. An output of three or more grids on a test input, or an undefined one, is not consistent, and gives no attempt for that input.

### The output of the `OUT` form

- A case's grid on an input is read from the relation of its [`OUT` form](../../docs/arclog/arclog.md#the-out-form) at the form's two columns, Position then Color, model by model, as [The output set](../../docs/arclog/constraints.md#the-output-set) gives. No column of any relation is searched for.
- An `OUT` form holds where its output set solves every train pair, as [Solves](#solves) gives for the run's candidates, which `JudgedTask` holds, as [Candidates](#candidates) gives. On a pair with one candidate and a case with one model, that is where its rows equal `ex_output`'s at that example.
- The judge's solves condition, the determination's filter over assignments and the consistency test of a decode read the `OUT` form. The relation of the form is cached with its entry, so the cases whose `OUT` forms read the same rows share it.
- During a determination, the test runs at each assignment, as [Determination with no stored value](determination.md#determination-with-no-stored-value) gives. At an assignment where the `OUT` form does not solve the train pairs, the assignment does not solve them.

### Witnesses

- A witness runs each case on the witness's input, with the witness's `assign` rows in place of the parameters they name.
- Where the verdict is not `other`, each `output` form is a group: the cases its names expand to, and a grid, several grids, or `undefined`. Over the included witnessed cases, the cases whose output on the input is a group's output are exactly that group's cases. A witnessed case in no group is a fault. A group's names are the fewest whose cases give its cases: the judge searches the names whose cases lie inside the group, in increasing count, and reports a group whose cases fewer names give. A disagreement with the record is a fault, as [Params](../../docs/arclog/arcdata.md#params) gives.
- A witness with the verdict `other` records the annotator's judged grid in one `output` form, as [verdict](../../docs/handbook/principles.md#witnesses) gives. No group is compared, and a case that gives the judged grid is a fault.
- A witness stands where [Witnesses](../../docs/handbook/principles.md#witnesses) gives. The hypothesis a witness is for is set by the form it stands under, whatever its verdict, `any` and `other` included: an `alt` form's witness is for that alt's hypothesis. Principles name none for a witness under an `approximated` form, so the judge reports its standing `undecided`.
- The judge reports an `assign` that the witness does not need. It tests the subsets of the `assign`'s relations in increasing size, the empty one, the stored assignment, first. Where a subset smaller than the `assign` makes the hypothesis defined and different, the `assign` changes more parameters than the fewest, and is reported. An `assign` of n relations costs at most 2^n − 1 more runs of the case on the input.
- A witness under an `approximated` form is not `foreign`, and each case that runs the approximation has a witness on which its output is not the verdict's, as [Header](../../docs/handbook/solver-file.md#header) gives.

### Case conditions

The judge checks the [case conditions](../../docs/handbook/principles.md#cases) where a pair or a witness can show them, and reports each failure:

- **Solves.** Each case solves a split task at its stored assignment, as [Solves](#solves) gives.
- **Equivalence and Subsumption.** The other cases are the included cases. For each witnessed case other than the concept case, and each other case, some input of the task or of the witnesses shows the case defined and its output different from the other's. For the concept case and each other case, some such input shows the two differ. Where no input shows it, the judge reports the two cases: by [Cases](../../docs/handbook/principles.md#cases), of two equivalent cases the one with more non-concept branches fails, and of two with equal counts, Principles leave which, so the report names both. The check reads the stored assignments and the witnesses' `assign` rows alone, so it approximates the definition over every assignment of [Equivalence and subsumption](../../docs/handbook/principles.md#equivalence-and-subsumption): an input shows a difference, and no input shows equivalence.
- The judge interns each case's output on each input, with `outside` and a stop at a bound each as a fresh id, and groups the cases by their vectors of ids. Cases with one vector are compared once. For subsumption, for each set of inputs on which some vector is defined, the judge hashes each vector's projection onto that set. The cost is one pass over the cases times the inputs, then one hash per distinct vector and distinct set, where a pairwise test grows with the square of the cases.
- **Excluded combinations.** An `exclude` form records a judgment and its reason, as [The `ALTS` form](../../docs/arclog/arclog.md#the-alts-form) gives, and the engine does not check it.
- **Relational form.** This is the annotator's judgment, and the engine does not check it.

### Reports

- A case stopped at a bound at an assignment has no output on that input at that assignment. A determination or consistency walk continues with the other assignments, and a surviving assignment can establish a consistent verdict beside the recorded stop. In a judged run, the stopped case has no output on that input, and the judge reports the stop as a fault, as [Joins](evaluator.md#joins) gives. It is not the output `outside` of an enumeration that stops early.
- A report names the case, the pair or the witness, and the cause, in the file's names.
- A set that ended at the model cap is no stop at a bound, and the judge reports it as a count.
- Per input, the judge's work past the evaluation of the cases is linear in the cases: one interned output per case, the enumeration up to its stop, and, in the refine step, the comparisons over the distinct vectors.

## How each decision can fail

| Decision | Failure | What catches or bounds it |
| --- | --- | --- |
| Every case evaluated to find the witnessed cases | a product of many cases on each pair and witness input | the entries the cases share, computed once by the result cache; a case differs from another only at the entries its alts rederive and those that read them |
| Models enumerated as a product | a pick with many models that reach the output | clusters solved one by one; clusters that no output reads fixed to one model; the stops; the model cap. The counts measured are in [Open values and constraint search](corpus-survey.md#open-values-and-constraint-search); the covers of the `CoverForcing` solvers are unique or absent, as [Evidence](../../docs/engine/constraints.md#evidence) gives, and the other `CHOOSE` forms and the `DEMONSTRATED` forms are not measured |
| Open-world candidates on Kaggle | a train pair whose tie the data does not show refuses a program that states the tie | the relaxed reading of [Solves](#solves), in the judge and in determination |
| `DEMONSTRATED` confirmation | many rules, keys and demonstrations | one evaluation of each rule per input; equal predictions merged into one model |
| Equivalence and Subsumption over the included cases | pairwise tests over many cases | cases grouped by their interned output vectors; projections hashed per set of defined inputs |
| The stop rule | two cases that both stop on an input count as different there, so an equivalence that only that input would show is missed | a stop happens only where the case fails the pair or the record, which is reported |

## Known gaps

None.
