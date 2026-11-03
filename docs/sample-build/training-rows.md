# Training rows for the trees

The rows that the gradient-boosted trees fit on. The trees score the admitted ids at each writing point of the query writer. The rows come from the writer's own feature code, so that training and serving compute features in one way.

- **Source.** The samples of the sample build: each sample is a state and its target queries, in `samples/SET/skeleton/<task>.jsonl`. The scope of a sample is the union of its members' programs (`query.program`, without each query's own last line where it is a closure).
- **Extraction.** The writer kit's extractor replays the target queries from the sample's scope through its own writing-point code (`start_point`, `step_point`) and its own `Features`. No other code computes a row's features.
- **Row.** One row is one (sample, writing point, admitted id). Rows are grouped by writing point. A writing point with fewer than two admitted ids gives no rows.
- **Features.** `Features.option(uses)` for the id and `Features.point(uses)` for the writing point, as `Distribution.logits` takes them. The table features of an id that names a parameterized table are the export's TableVector, aggregated over the parameterized table's assignments by the writer's aggregates.
- **Plans.** Two writer plans are tested, each with its own rows and its own tree. The rows' header names the plan.
    - `ordered`: a greedy legality rule that knows the bindings fixes every free order, so a query has one path. A target is live at a writing point when the point's token prefix is a prefix of its path.
    - `unordered`: no order rule. A target is live at a writing point when the point's token prefix can start some order of its free choices.
- **Label.** An admitted id is 1 when it is the next token of some live target, under the plan. Every other admitted id is 0. The mask alone decides which ids are admitted. The extractor writes the labels.
- **Loss.** Per writing point, −log of the summed chance of the positive ids, with a softmax over the admitted ids.
- **Split.** The split comes from the [split design](split.md). Rows of train tasks and dev tasks go to `samples/SET/points/<plan>/<task>.jsonl.gz`, and the header of each file carries its split. Rows of held tasks go to `samples/SET/points_held/<plan>/<task>.jsonl.gz`. The fit uses train rows, evaluation uses dev rows, and no fit reads `points_held/`.
- **Header.** Each file's header carries the split, the writer plan's version, the feature names in order and the engine wheel.
- **Writing-point vector.** The blocks and what the engine gives are in [The writing-point vector](../../work/lm/data-study/sampler/sampler-worker/proposer-inventory/writer-spec.md#the-writing-point-vector). The table columns of the candidate and state blocks are below.
- **Comparison of the plans.** The dev loss per writing point depends on the label scheme, so it does not compare the two plans. On dev samples, each plan's tree is measured by two values:
    - The chance of writing some target query, summed over every path that writes it under the plan.
    - The share of samples whose most probable completed query is a target query.

## Search draws

The search's draws on train tasks are negative examples. A draw is never a target and never a feature, because serving has no draws.

- **Source.** A recorded search over the train tasks writes one record per draw. Draws of dev and held-out tasks are not used, and `points_write.py` refuses them.
- **Record.** Each draw record has these fields:
    - The task, the search run, the draw's index, the seed, the writer plan, the writer kit release, the model file's sha and the engine site.
    - For each query of the program, in the order the writer wrote it: its text as written, its `QueryHash` on the run's engine site, and the `QueryHash`es of the queries written before it. That set is the step's state.
    - The outcome: whether the program ran; for each train example, whether the output equals the expected output; the first query that failed, with its reason (an engine error, a refusal, no table, the deadline); and whether the draw solves every train example.
    - The count of identical draws that the record stands for.
- **Matching.** Only a draw's last step, the query the draw wrote, gives negatives. Its other steps are queries of its scope, which earlier draws wrote. The last step matches a sample when its state equals the sample's state. A draw that solves every train example gives no negatives.
- **Drawn ids.** At each writing point of a matched step, the draw's next token is a drawn id when no live target has that token next. An id's `drawn` count is the number of failed draws that took it at that writing point. A positive id has no `drawn` count.
- **Loss.** In the fit only, each id's term in the softmax denominator has the weight 1 + α · `drawn`, with α a fit option. The trees' scores do not read the weight.
- **Unmatched steps.** A step whose state equals no sample's state gives no rows. The header of each task's file counts the matched and unmatched steps.

## Table columns of the writing-point vector

`model/study/samples/point_tables.py` computes these columns. Its functions take tables in the layout that `step_tables` gives with `by_assignment` and `rows`, and the task's base tables in the same layout.

Terms used below:

- A table's rows at an example are the union of its TableRows at that example, over its constraint models.
- A column of the successor body table is kept from the current body table when the two have one label and one type.
- `cells(T, e)` is the set of distinct (Position, Color) pairs of table T at example e. It is taken from one Position column and one Color column of T: the pair of columns with the highest recall against `ex_output`, ties going to the first pair in column order. `cells` is undefined when T has no Position column or no Color column.
- `O(e)` is `cells` of `ex_output` at example e. `D(e)` is the part of `O(e)` that `input` does not hold: positions outside the input grid, or a color that differs from the input's color at that position.
- `recall(T, e) = |cells(T, e) ∩ O(e)| / |O(e)|`, and `precision(T, e) = |cells(T, e) ∩ O(e)| / |cells(T, e)|`.
- Only train examples are used, since only they have an output.

### Candidate block

The writer leaves this block out of the vector unless `WRITER_VECTOR_OFF` is set without `cand`.

- `succ:<name>`, for each name of `assignment_vector_names()`: the successor body table's AssignmentVector.
- `delta:<name>:min`, `delta:<name>:mean` and `delta:<name>:max`: aggregates over pairs. A pair is one successor assignment and the current assignment it restricts to. Each value of a pair is a mean over train examples. NaN values are left out of a mean, a min and a max.
- `delta:pairs`: the count of pairs.

The `<name>`s of a pair, with C the current body table and S the successor at example e:

| `<name>` | Value |
|---|---|
| `rows_cur`, `rows_succ` | log(1 + row count) of C and of S |
| `kept` | the share of C's rows that some row of S extends on the kept columns; NaN when C has no row |
| `lost` | 1 − `kept` |
| `fanout` | S's row count divided by the count of C's rows kept, or by 1 when none is kept |
| `empty` | 1 when S has no row |
| `cols_added` | the count of S's columns that are not kept from C |
| `cols_added:color`, `:position`, `:ident`, `:int`, `:other` | that count, by the column's type class |
| `out_recall`, `out_precision` | `recall(S, e)` and `precision(S, e)` |
| `out_recall_gain` | `recall(S, e) − recall(C, e)`, with `recall(C, e)` 0 when `cells(C, e)` is undefined |
| `out_precision_gain` | `precision(S, e) − precision(C, e)`; NaN when `cells(C, e)` is undefined |
| `changed_recall` | the share of D(e) that `cells(S, e)` holds; NaN when D(e) is empty |
| `pos_recall` | the share of the positions of `O(e)` that some Position column of S holds |
| `lost_cells` | the share of O(e) that `cells(C, e)` holds and `cells(S, e)` does not |

The output features are NaN where `cells(S, e)` is undefined. At `END` the successor is each output table of the query. Its pairs are taken with no current table, so C has no row and no column, and the pairs of all output tables are aggregated together.

### State block

Over the state's parameterized tables:

- `state:tables`, `state:dets`: the count of parameterized tables, and of those computed by a DET.
- `state:capped`: the count whose walk stopped at the cap.
- `state:differ`: the share whose `differ` is 1.
- `state:<f>:mean:mean` and `state:<f>:mean:max`, for each TableVector feature `<f>`: the mean and the max of the AssignmentVector's `<f>:mean` over the tables.
- `state:out_recall:max`, `state:out_precision:max`, `state:changed_recall:max`. Each table is valued at its best assignment, by the mean over train examples. These are the max over the tables, and `out_precision` is the precision of the table with the highest recall.
