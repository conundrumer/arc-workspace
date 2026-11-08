# Training instances for the trees

The training instances that the gradient-boosted trees fit on. The trees score the admitted ids at each writing point of the query writer. The training instances come from the writer's own feature code, so that training and serving compute features in one way.

- **Source.** The samples of the sample build: each sample is a state, in `samples/SET/skeleton/<task>.jsonl`. The scope of a sample is the union of its members' programs (`query.program`, without each query's own last line where it is a closure).
- **Targets.** The target queries of every state that the extractor writes, a skeleton sample or a state off the samples, are those of the rule of the [contract](contract.md#sample), from the `TableHash`es of the tables that the engine computes for the state's scope. The graph tables' maps and each graph query's reads and computed graph tables come from the union's graph files (`graph-prods-SET.jsonl`, `graph-tables-SET.jsonl`). The skeleton's `target_queries` are not read.
- **Extraction.** `model/study/samples/points_write.py SET --vectors` replays the target queries from the sample's scope through the writer's own writing-point code and its own `Features` (`train_rows.points_of_targets(..., vectors=True)`). No other code computes a training instance's features.
- **Training instance.** One training instance is one (sample, writing point, admitted id). Training instances are grouped by writing point. A writing point with fewer than two admitted ids gives no training instances.
- **Features.** `writer.Features(pt, ids).vectors()`: the writing-point vector of each admitted id, as serving gives it to the model. A point record holds the point-scope columns once (`vp`) and the matrix of the other columns, one row per id (`vo`), both as base64 float32. The table features of an id that names a parameterized table are the export's TableVector, aggregated over the parameterized table's assignments by the writer's aggregates.
- **Plans.** Two writer plans are tested, each with its own training instances and its own tree. The header of the training instances names the plan.
    - `ordered`: a greedy legality rule that knows the bindings fixes every free order, so a query has one path. A target is live at a writing point when the point's token prefix is a prefix of its path.
    - `unordered`: no order rule. A target is live at a writing point when the point's token prefix can start some order of its free choices.
- **Label.** An admitted id is 1 when it is the next token of some live target, under the plan. Every other admitted id is 0. The mask alone decides which ids are admitted. The extractor writes the labels.
- **Loss.** Per writing point, −log of the summed chance of the positive ids, with a softmax over the admitted ids.
- **Split.** The split comes from the [split design](split.md). Training instances of train tasks and dev tasks go to `samples/SET/points/<plan>/<task>.jsonl.zst`, and the header of each file carries its split. Training instances of held-out tasks go to `samples/SET/points_held-out/<plan>/<task>.jsonl.zst`. The fit uses train training instances, evaluation uses dev training instances, and no fit reads `points_held-out/`.
- **Header.** Each file's header carries the task, the set and the split, the plan, the sha256 of the skeleton file (`skeleton_sha`), of the extractor (`extractor_sha`), of `writer.py` (`writer_sha`) and of `points_write.py` (`code`), the engine wheel (`wheel`, the name of the site folder), the files of sampled-query records it read (`draws`), and the vector's column names in order (`vector_names`, with `vector_point_cols`, the indexes of the point-scope columns).
- **Writing-point vector.** The blocks and what the engine gives are in [The writing-point vector](../../work/lm/data-study/sampler/sampler-worker/proposer-inventory/writer-spec.md#the-writing-point-vector). The table columns of the candidate block are below.
- **Comparison of the plans.** The dev loss per writing point depends on the label scheme, so it does not compare the two plans. On dev samples, each plan's tree is measured by two values:
    - The chance of writing some target query, summed over every path that writes it under the plan.
    - The share of samples whose most probable completed query is a target query.

## Sampled queries of the search

The queries that the search samples on train tasks give negative training instances. A sampled query is never a target and never a feature, because serving has no record of earlier samples.

- **Source.** A recorded search over the train tasks writes one record per sampled query. Sampled queries of dev and held-out tasks are not used, and `points_write.py` refuses them.
- **Record.** Each sampled-query record has these fields:
    - The task, the search run, the sample's index, the seed, the writer plan, the writer code release, the model file's sha and the engine build.
    - For each query of the program, in the order the writer wrote it: its text as written, its `QueryHash` on the run's engine site, and the `QueryHash`es of the queries written before it. That set is the step's state.
    - The outcome: whether the program ran; for each train ARC example, whether the output equals the expected output; the first query that failed, with its reason (an engine error, a refusal, no table, the deadline); and whether the sampled program solves every train ARC example.
    - The count of identical samples that the record stands for.
- **Matching.** Only a sample's last step, the query that the sample wrote, gives negatives. Its other steps are queries of its scope, which earlier samples wrote. The last step matches a sample when its state equals the sample's state. A sample that solves every train ARC example gives no negatives.
- **Ids of failed samples.** At each writing point of a matched step, the sample's next token is an id of a failed sample when no live target has that token next. An id's `drawn` count is the number of failed samples that took it at that writing point. A positive id has no `drawn` count.
- **Loss.** In the fit only, each id's term in the softmax denominator has the weight 1 + α · `drawn`, with α a fit option. The trees' scores do not read the weight.
- **States off the samples.** A last step whose state equals no sample's state adds that state as a sample. A state with no target query is not added. The step state's queries outside the union are written into the scope from the steps of a sampled-query record, and the scope computes their tables at scope time, as it does the union's queries'. The ids of failed samples at its writing points are counted as above.
- **Header.** The header of each task's file counts the last steps that match a sample, the last steps that add a state, the states added, and the last steps that cannot add one, each by its reason. Each state is added once, whatever the count of records that reach it.
- **Check.** `model/study/samples/run/draw_targets.py` counts, for files of sampled-query records, the last steps whose state is a sample's state, and the distinct states and queries outside the union that the added samples need. With `--points` it compares those counts with the headers. It runs no engine, so it does not decide targets.

## Fit noise

The dev score of a fit varies with its seed (`fit_trees.py --seed`), which sets the trees' feature sampling and the choice of each task's writing points. Four seeds of one configuration were each scored on one set of dev writing points (`fit_trees.py --score` at seed 0). The configuration was the exp59 row stores, 854 train tasks, 161 dev tasks, 40 writing points per task, and the default tree settings. The scores were:

- dev loss: 1.1241 to 1.1287, standard deviation 0.0022;
- top-scored id is positive: 65.1% to 65.7%, standard deviation 0.3 percentage points.

A change counts as a gain only when its dev gain is outside this range. Fits are compared on one set of dev writing points: each fit is scored with `--score` at one seed.

## Table columns of the writing-point vector

`model/study/samples/point_tables.py` computes these columns. Its functions take tables in the layout that `step_tables` gives with `by_assignment` and `rows`, and the task's base tables in the same layout.

Terms used below:

- A body table is the parameterized table that a partial query's body computes: the current body table before the next token, the successor body table after it.
- A parameterized table's table rows at an ARC example are the union of its tables at that ARC example, over its constraint models.
- A column of the successor body table is kept from the current body table when the two have one label and one type.
- `cells(T, e)` is the set of distinct (Position, Color) pairs of the table rows of body table T at ARC example e. It is taken from one Position column and one Color column of T: the pair of columns with the highest recall against `ex_output`, ties going to the first pair in column order. `cells` is undefined when T has no Position column or no Color column.
- `O(e)` is `cells` of `ex_output` at ARC example e. `D(e)` is the part of `O(e)` that `input` does not hold: positions outside the input grid, or a color that differs from the input's color at that position.
- `recall(T, e) = |cells(T, e) ∩ O(e)| / |O(e)|`, and `precision(T, e) = |cells(T, e) ∩ O(e)| / |cells(T, e)|`.
- Only train ARC examples are used, since only they have an output.

### Candidate block

The writer leaves this block out of the vector unless `WRITER_VECTOR_OFF` is set without `cand`.

- `succ:<name>`, for each name of `assignment_vector_names()`: the successor body table's AssignmentVector.
- `delta:<name>:min`, `delta:<name>:mean` and `delta:<name>:max`: aggregates over pairs. A pair is one successor assignment and the current assignment it restricts to. Each value of a pair is a mean over train ARC examples. NaN values are left out of a mean, a min and a max.
- `delta:pairs`: the count of pairs.

The `<name>`s of a pair, with C the current body table and S the successor at ARC example e:

| `<name>` | Value |
|---|---|
| `rows_cur`, `rows_succ` | log(1 + table row count) of C and of S |
| `kept` | the share of C's table rows that some table row of S extends on the kept columns; NaN when C has no table row |
| `lost` | 1 − `kept` |
| `fanout` | S's table row count divided by the count of C's table rows kept, or by 1 when none is kept |
| `empty` | 1 when S has no table row |
| `cols_added` | the count of S's columns that are not kept from C |
| `cols_added:color`, `:position`, `:ident`, `:int`, `:other` | that count, by the column's type class |
| `out_recall`, `out_precision` | `recall(S, e)` and `precision(S, e)` |
| `out_recall_gain` | `recall(S, e) − recall(C, e)`, with `recall(C, e)` 0 when `cells(C, e)` is undefined |
| `out_precision_gain` | `precision(S, e) − precision(C, e)`; NaN when `cells(C, e)` is undefined |
| `changed_recall` | the share of D(e) that `cells(S, e)` holds; NaN when D(e) is empty |
| `pos_recall` | the share of the positions of `O(e)` that some Position column of S holds |
| `lost_cells` | the share of O(e) that `cells(C, e)` holds and `cells(S, e)` does not |

The output features are NaN where `cells(S, e)` is undefined. At `END` the successor is each output table of the query. Its pairs are taken with no current table, so C has no table row and no column, and the pairs of all output tables are aggregated together.
