# Cases and judge

It builds the models of a case on an input, from its `ONE` and `CHOOSE` forms, its open values, its `DEMONSTRATED` forms and its `Unfold` walks, and the judge of the solves relation, the case conditions and the witnesses. It rests on [constraints](../../docs/arclog/constraints.md) and on the handbook's [Cases](../../docs/handbook/solver-file.md#cases). Here solves is the handbook's fit, and hypothesis the handbook's model, as [Requirements](overview.md#requirements) gives.

Two steps of the [build order](overview.md#build-order) build it, one before [Synthesis](synthesis.md) and one after it.

## One case

- The step before Synthesis builds what a synthesized program reads: one case, with no open parameter and no `DEMONSTRATED` form. It builds [Models](#models), and [Candidates](#candidates), [Solves](#solves) and [Grid columns](#grid-columns) of the judge.
- The step ends when each solver's concept case that reads no open parameter and no `DEMONSTRATED` form, at the stored `param` records, gives the solves outcome that Souffle gives, as [verification.md](verification.md) checks it, or the difference is reported as a fault, as the Principles requirement of [Requirements](overview.md#requirements) gives.

## Every case

- The step after Synthesis builds the rest of this doc, and checks the parameters that [Determination](determination.md) leaves unchecked.
- The step ends when the engine is at parity with Souffle on every solver outcome: each case's output on each pair, whether it solves the task, and the witness outcomes, as [verification.md](verification.md) checks them, or the difference is reported as a fault, as the Principles requirement of [Requirements](overview.md#requirements) gives.

## Cases

- A solver's cases are the product of its `ALTS` forms, restricted by the nesting of the blocks, less the combinations that the arcdata file's `exclude` forms leave out. A `DET_OR_RULE` or `RULE_OR_DET` line splits only the bases that read its relation. `cases()` of [Solvers](reader.md#solvers), built in [Reader and checker](reader.md), follows this rule, and gives a solver with a `representative` line the representative's cases, or the one case the line names.
- Each case is one program, with no `Choice` column. The [result cache](evaluator.md#the-result-cache) shares the entries that the cases' relations hold in common.
- The judge reports on the witnessed cases alone, as [Cases](../../docs/handbook/solver-file.md#cases) defines them. That set depends on each case's output on the pair inputs and the witness inputs, so the engine evaluates every included case on those inputs. The product reaches 9216 cases in one file, af24b4cc.
- The names of an `output` form expand to their cases as [Witness file](../../docs/handbook/solver-file.md#witness-file) gives.

## Models

A model of a case on an input is one choice at each of its picks, as [Semantics](../../docs/arclog/constraints.md#semantics) gives, one open value of each open parameter it reads, and one `Unfold` walk of each instance whose `score` ties, as [Lib](evaluator.md#lib) gives. The case's models are the product of these.

### The constraint module

- The constraint module is a finite-domain constraint solver over the picks. Its options are the rows of a clause with `ONE` marks and the `from` rows of each `for` row of a `CHOOSE`. Each option is kept or not. The constraints restate [Semantics](../../docs/arclog/constraints.md#semantics):
    - for each `ONE` mark and each value of its key that has rows, exactly one row with that value is kept, for all marks of the relation at once;
    - for each `for` row of a `CHOOSE` that has a `from` row, exactly one `from` row is kept;
    - no `never` pair is kept together.
- A `for` row with no `from` row is absent from every model. The options split into clusters, the connected components of the graph whose edges are the constraints above. A cluster with no model contributes no rows, and the product goes on over the other clusters. A program with no model gives no grid, and its output is undefined.
- On each cluster, the module runs propagation to a fixpoint, as the lib's `UnitPropagation` does, and then searches the options still open, depth first, under a cap of 10^4 nodes per cluster. The search visits options and values in a canonical order by content, with Idents ordered by their contents as a writer numbers them, as [Terms](reader.md#terms) gives, so a stop at a cap does not depend on an encoding order. The cap is provisional: the corpus gives no search size, as [Open values and constraint search](corpus-survey.md#open-values-and-constraint-search) gives. A search that reaches the cap is an alert, as [Bounds](overview.md#requirements) gives.
- The models of one case on one input run under a cap of 10^3. The cap is provisional: the largest count that the survey measured is 64, as [Open values and constraint search](corpus-survey.md#open-values-and-constraint-search) gives. A count that reaches the cap is an alert, as the node cap's is.
- The module gives the models one at a time.
- A cluster is enumerated where its chosen relation, as [One](../../docs/arclog/constraints.md#one) defines it, is an ancestor of `&output` in the case's [dependency graph](reader.md#the-dependency-graph), over every read edge, a negated read included. A chosen relation that is no ancestor of `&output` takes its first model in the search order, since no output reads it.
- A `DET` that reads a chosen relation runs over that relation's models. Where the models give the `DET` more than one value, the engine reports an error.

### Enumeration and its stops

- For each model, only the entries downstream of the chosen relation are computed again, as [The result cache](evaluator.md#the-result-cache) gives.
- On an input, enumeration stops as soon as the grids so far decide the comparison that the input serves, by [Solves](#solves):
    - a train pair under closed-world candidates: at a grid outside the pair's candidates, or once the grids lie in two different candidates;
    - a train pair under open-world candidates: at the third distinct grid, or at the second where neither grid is the given output;
    - a test pair: at the third distinct grid;
    - a witness input: at the first grid outside every grid that the witness's `output` forms record.
- An undefined grid stops each of these too, except on a witness input whose record holds `undefined`.
- A stopped enumeration gives the output `stopped`: three or more grids or undefined on a test input, and outside the candidates or the record on the others. Every comparison of the judge treats `stopped` as different from every output, itself included. Whether an enumeration stops does not depend on the order of the models, so no comparison does.
- Where a comparison needs the full set, as a witness group does on a witness input where the case's grids so far lie inside the record, enumeration goes on to the last model. A case that solves the task needs every model.

## Open values

- A parameter has open values under one of three readings:
    - A `DET` whose body ends in `(ONE)` is a chosen relation, task-wide as [Program](../../docs/arclog/arclog.md#program) gives, and the constraint module solves it. Its models are its open values.
    - A `DET` by a proposer or a domain with `(ONE)` keeps the values that the train pairs leave, as [`DET`](determination.md#det) gives, and those are its open values.
    - On the derived reading of a `DET_OR_RULE` line with `(ONE)`, each value the proposer gives on the input is a model, as [Open values](../../docs/arclog/arclog.md#open-values) gives, per input.
- The open values that M_open uses are those left after the intersection across cases of [`DET`](determination.md#det).
- M_open, as [Open parameters](../../docs/handbook/principles.md#open-parameters) gives, is used by the solves test alone, as [Cases](../../docs/handbook/principles.md#cases) gives. So the output is undefined where the case is undefined at some open value, in that test alone. Where a case condition or a witness check compares an output of a case with an open parameter, the judge reports the comparison `undecided`, as [Known gaps](#known-gaps) gives.

## `DEMONSTRATED`

- For each `DEMO_RULE`, the engine evaluates `&prediction` once per input, an entry that holds every key. At each key, a demonstration `(o, o2)` confirms the rule where the rule's prediction rows for `o` at that key, by `i` and `v`, equal the `value` rows of `o2`, as [Demonstrated](../../docs/arclog/arclog.md#demonstrated) gives. The cost per input is the rules' evaluations, then one comparison of row sets per rule, key and demonstration.
- A key with no confirmed rule holds no prediction.
- Each choice of one confirmed rule per key is one model, as [Demonstrated choice](../../docs/handbook/solver-file.md#demonstrated-choice) gives. Rules whose predictions at a key are equal give one model there, since the relation has no rule column.
- A rule with fields stands for one rule per value that its clauses bind for the field.

## Judge

### Candidates

- A run has closed-world or open-world candidates.
    - **Closed-world candidates:** a train pair's candidates come from its alts by their kind, as [Alt outputs](../../docs/handbook/solver-file.md#alt-outputs) gives: a `rule` alt gives a second candidate, a `tiebreak` alt adds a grid to the candidate, and a pair with no alt has one candidate, its output. A run on the task data of this repo is closed-world.
    - **Open-world candidates:** a pair with no alt may still have a tie that the data does not show, so its given output is one grid of an unknown candidate. A run on Kaggle task data is open-world.

### Solves

- A case solves some split task exactly when each pair has a candidate it solves, since a [split task](../../docs/handbook/principles.md#models-and-tasks) chooses a candidate per pair. So no split task is enumerated.
- Under closed-world candidates, solves is the handbook's fit: a train pair's output set equals one of its candidates, and a test pair's holds at most two grids, one of them in one of its candidates.
- Under open-world candidates, a train pair is solved where its output set holds at most two grids, one of them its given output, as a test pair is. The strict definition there would refuse each program that states a tie, and accept a program that breaks the tie by a hidden order only where that order matches the data. The determination's filter by the train pairs, in [`DET`](determination.md#det), reads a train pair this way on an open-world run.
- On Kaggle, a program is tested against a task with open-world candidates on the train pairs, and on each test input its output is defined and holds at most two grids, which needs no test output.

### Grid columns

- The [grid columns](../../docs/arclog/constraints.md#the-output-set) of a case are a pair of one Position column and one Color column of `&output` under which the grids, read model by model, solve every train pair, as [Solves](#solves) gives.
- The search runs once per content of `&output`'s entry and of the train candidates, and its result is cached with the entry, so the cases whose `&output` holds the same rows share it. Its cost is the Position columns times the Color columns, times the train pairs' models.
- Where no pair matches, the case has no grid columns, and it is undefined on every input.
- Where more than one pair matches, and two of them give different outputs on an input of the task or of the witnesses, the grid columns are undetermined. The engine reports it as an error, as it reports an undetermined `DET` in [`DET`](determination.md#det). At synthesis time a program has no witnesses, so the test reads the task's inputs alone.

### Witnesses

- A witness runs each case on the witness's input, with the witness's `assign` rows in place of the parameters they name.
- Where the verdict is not `other`, each `output` form is a group: the cases its names expand to, and a grid, several grids, or `undefined`. Over the included witnessed cases, the cases whose output on the input is a group's output are exactly that group's cases. A witnessed case in no group is a fault. A group's names are the fewest whose cases give its cases: the judge searches the names whose cases lie inside the group, in increasing count, and reports a group whose cases fewer names give. A disagreement with the record is a fault, as [Params](../../docs/arclog/arcdata.md#params) gives.
- A witness with the verdict `other` records the annotator's judged grid in one `output` form, as [verdict](../../docs/handbook/principles.md#witnesses) gives. No group is compared, and a case that gives the judged grid is a fault.
- A witness stands where [Witnesses](../../docs/handbook/principles.md#witnesses) gives. The hypothesis a witness is for is set by the form it stands under, whatever its verdict, `any` and `other` included: an `alt` form's witness is for that alt's hypothesis. Principles name none for a witness under an `approximated` form, so the judge reports its standing `undecided`.
- The judge reports an `assign` that the witness does not need. It tests the subsets of the `assign`'s relations in increasing size, the empty one, the stored assignment, first. Where a subset smaller than the `assign` makes the hypothesis defined and different, the `assign` changes more parameters than the fewest, and is reported. In `gen/`, 42 of the 1020 witnesses with a body hold an `assign`, 38 of one relation and 4 of two, so the test costs at most three more runs of the case on the input.
- A witness under an `approximated` form is not `foreign`, and each case that runs the approximation has a witness on which its output is not the verdict's, as [Header](../../docs/handbook/solver-file.md#header) gives.

### Case conditions

The judge checks the [case conditions](../../docs/handbook/principles.md#cases) where a pair or a witness can show them, and reports each failure:

- **Solves.** Each case solves a split task at its stored assignment, as [Solves](#solves) gives. Which split task the stored assignment is determined under is a gap, as [Known gaps](#known-gaps) gives.
- **Equivalence and Subsumption.** The other cases are the included cases. For each witnessed case other than the concept case, and each other case, some input of the task or of the witnesses shows the case defined and its output different from the other's. For the concept case and each other case, some such input shows the two differ. Where no input shows it, the judge reports the two cases: by [Cases](../../docs/handbook/principles.md#cases), of two equivalent cases the one with more non-concept branches fails, and of two with equal counts, Principles leave which, so the report names both. The check reads the stored assignments and the witnesses' `assign` rows alone, so it approximates the definition over every assignment of [Equivalence and subsumption](../../docs/handbook/principles.md#equivalence-and-subsumption): an input shows a difference, and no input shows equivalence.
- The judge interns each case's output on each input, with `stopped` and a bound's stop each as a fresh id, and groups the cases by their vectors of ids. Cases with one vector are compared once. For subsumption, for each set of inputs on which some vector is defined, the judge hashes each vector's projection onto that set. The cost is one pass over the cases times the inputs, then one hash per distinct vector and distinct set, where a pairwise test of af24b4cc's 9216 cases is about 4.2 × 10^7 pairs.
- **Excluded combinations.** An `exclude` form records a judgment and its reason, as [The `ALTS` form](../../docs/arclog/arclog.md#the-alts-form) gives, and the engine does not check it.
- **Relational form.** This is the annotator's judgment, and the engine does not check it.

### Reports

- A case stopped at a bound has no output on that input, and the judge reports the stop as a fault, as [Joins](evaluator.md#joins) gives. It is not the output `stopped` of an enumeration.
- A report names the case, the pair or the witness, and the cause, in the file's names.
- Per input, the judge's work past the evaluation of the cases is linear in the cases: one interned output per case, the enumeration up to its stop, and the comparisons over the distinct vectors. The Speed requirement of [Requirements](overview.md#requirements) is checked by the corpus run's time per solver against Souffle's, as in step 2.

## How each decision can fail

| Decision | Failure | What catches or bounds it |
| --- | --- | --- |
| Every case evaluated to find the witnessed cases | a product of 9216 cases on each pair and witness input | the entries the cases share, computed once by the result cache; a case differs from another only at the entries its alts rederive and those that read them |
| Models enumerated as a product | a pick with many models that reach the output | clusters solved one by one; clusters that no output reads fixed to one model; the stops; the model cap. In the corpus, the largest count measured is 64; the covers of the nine `CoverForcing` solvers are unique or absent, as [Evidence](../../docs/arclog/constraints.md#evidence) gives, and the other `CHOOSE` forms and the `DEMONSTRATED` forms are not measured |
| Open-world candidates on Kaggle | a train pair whose tie the data does not show refuses a program that states the tie | the relaxed reading of [Solves](#solves), in the judge and in determination |
| Grid columns found by the train pairs | several column pairs match, or none | an error where they disagree on an input; undefined where none matches; one search per content of `&output` |
| `DEMONSTRATED` confirmation | many rules, keys and demonstrations | one evaluation of each rule per input; equal predictions merged into one model |
| Equivalence and Subsumption over the included cases | pairwise tests over thousands of cases | cases grouped by their interned output vectors; projections hashed per set of defined inputs |
| The stop rule | two cases that both stop on an input count as different there, so an equivalence that only that input would show is missed | a stop happens only where the case fails the pair or the record, which is reported |

## Known gaps

| Gap | Where it shows |
| --- | --- |
| An open value that is a set of rows: a model of `(ONE)` keeps one row per value of its key, so a parameter whose open values are whole sets of rows, as [Params](../../docs/handbook/solver-file.md#params) allows, has no encoding | of the 42 parameters of [Open values and constraint search](corpus-survey.md#open-values-and-constraint-search), 40 hold 2 to 8 rows of single values; b7f8a4d8 `&draw_rank` and bc93ec48 `&precedence` hold 24 open values of 4 rows each, keyed by an Ident column that a bare `(ONE)` reads as one row |
| What Equivalence, Subsumption and the witness checks read for a case with an open parameter: Principles use M_open for the solves test alone | every solver with a `(ONE)` parameter; the judge reports `undecided` there |
