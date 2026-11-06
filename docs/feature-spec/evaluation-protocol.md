# Evaluation of the features: protocol

What the encoder can do at each size, before any model. No person reviews anything. The results set the size to run. No feature is dropped because of a result.

## Common rules

- **Population:** every eligible task, in the seeded order of its list, so a run that stops early reads a random sample. The eligible list is the train-split tasks with at least 3 train pairs and a near-miss module in `model/contracts/nearmiss/`, in `work/feature-spec/eval-tasks.txt`. Candidate recognition also reads the dev split, in `work/feature-spec/eval-tasks-dev.txt`. A comparison that selects nothing from results covers all its tasks together. A comparison that selects anything from results selects on one split and reports on the other. Expressibility covers every train-split solver.
- **Unit:** the task. Each statistic is a mean over tasks, with a bootstrap over tasks for its interval.
- **Size:** each statistic is a curve over the size d, from 1 to D, the largest size the encoder finishes on at least two thirds of the tasks. A curve reads the tasks finished at D, and lists the others as left out, so its tasks stay fixed along it. Those tasks tend to have smaller grids, which limits what a result says about large ones.
- **Roots:** a test reads a root's value at one example, since a vector entry combines over the examples and would read a left-out pair.
    - A **closed root** is a shape, as the specification's section on vectors defines one, so it has one name for every table. Closed roots are primary, since a model's vector entries combine them. Ground expressions are reported beside them, as the most that a size can see.
    - All roots here are invariant. An equivariant root moves under a symmetry, so its value is not compared across a pair.
    - A closed root's value at an example is the multiset of its values over its bindings and models, so equality is exact. No value counts as a value of its own.
- **Classes:** two roots are one class in a task where they have an equal value vector over that task's instances. Statistics count classes, so a root counts once however many expressions write it. The same statistic over roots is reported beside it.
- **Active claims:** a claim of absence, a root at its default on every other pair, says little and grows with the family, and an empty table meets all of them. So statistics read active claims, whose one value is not the default. The same statistic over claims of absence is reported apart.
- **Left-out rule:** a task-wide root reads the left-out pair, so every leave-one-pair-out test leaves out task-wide roots.
- **Solver fit:** a solver was fitted to all train pairs, and its parameters can read the test inputs. So a result on solver tables favors the true side. Base tables have no such fit, so leave-one-pair-out tests take them as primary and report solver tables apart.
- **Hard items:** the items that size 1 leaves tied. Each recognition test reports its statistic on all items and on hard items, since easy items, such as an empty table or a changed palette, hold an AUC near 1 at every size. A task with no hard items leaves that statistic.
- **Count curve:** a statistic can rise with the number of roots alone. So each recognition test also runs on random subsets of the roots up to size D, at the counts of sizes 1 to D-1, with 20 draws at each count, and reports real minus subset. This is a description, and the rule for the size does not read it.
- **Nulls:** each null runs 20 times with a fixed seed, and a statistic's null is the mean.
- **Baseline:** the first version of the features runs on the same items.
- **Negatives:** Separation and Scene recognition read random mutations alone: records of `model/contracts/corpus/` of kind `in`, with a grid that equals no train input. Base tables read all of them. Solver tables read those with `stored` equal to `same` and no error, since a record's solver tables exist only there. Variants from `search.py` are selected by the first version's claims, so they would favor it.
- **Running:** each test writes its result per (task, d) as it ends, and a restart skips those written. So a test runs as soon as the encoder reaches size 1, and adds each larger size.

## Checks

Each is pass or fail, and a failure is a fault to fix.

- **Transformation law:** apply an element of D4 and a color permutation to a table's rows and to the grids, and read the result as stored rows. A solver can't run on a transformed task as it stands, since its stored values hold orientations and colors. An invariant feature keeps its value, and an equivariant feature moves by the group's action.
- **Reorder:** reorder the train pairs and the test inputs. A per-input value moves with its example, and a task-wide value with no `Example` column keeps its value.
- **Symmetric pairs:** on two row sets that a symmetry relates, no invariant feature whose leaves are the table and lib relations differs.
- **Equal rows:** on equal rows with equal grids, no feature differs.

## Expressibility

How large a next step is. A ground expression of size d shows the model what a query of that size would compute.

- **Items:** each query of the concept case of each train-split solver.
- **Measure:** the size of the feature expression that translates the query's body, with the relations it reads as leaves. Each language form takes the operators of its relational-algebra form. A `DET` that names a proposer has size 0.
- **Statistic:** the cumulative share of queries of size at most d, per solver and over solvers, and the size of each solver's largest query.
- **Gap list:** the forms that the grammar does not write, counted by kind. They are reported as a share beside the statistic.
- **Limit:** a closed root shows an aggregate of a query's rows, and not the rows. So this gives the size at which a feature expression can state a next step, and not what a model learns from it.

## Separation

At which size a difference first shows. The specification's guarantee says that at unbounded size every difference other than a symmetry shows. This measures how soon.

- **Items:** (variant, table), at the train example that the variant changes, where the two row sets are not equal. Per task, they are all such pairs that the first version does not see, and 1% of the others, at least 20, with inverse-probability weights.
- **Grids:** a variant runs as a test input, so its grids are its input alone, and roots with an `output` leaf are left out.
- **Own-table level:** roots whose leaves are the table and lib relations.
- **Fixed-context level:** roots whose leaves are the table, the grids and lib relations. The variant's grids stay fixed, and only the table's rows are swapped for the source's.
- **Symmetric pairs:** those where a symmetry takes one database to the other at that level, as the specification's section on coverage defines one. An exact search decides this: each of the eight elements of D4, with the bijections found by backtracking over value signatures. They are counted apart, and the statistic reads the other pairs.
- **Statistic:** per level, the weighted share of the other pairs that show at size at most d. A task with no such pair leaves the statistic.
- **Meaning:** a necessary condition alone. It can only rise with size, and a digest of the rows would pass it. So the rule for the size does not read it.

## Candidate recognition

Whether the features of a candidate's table tell a solver's next query from a wrong one at the same state. This stands closest to what a model must do.

- **Items:** (task, query Q of the concept case, mutant Q'), with up to 5 mutants per query. A mutant is a valid one-edit mutation of Q's body from the engine, `draw_specs` with k=1 in a seeded order, whose table differs from Q's at some train example. They are stored under `results/mutants/`. A query with no such mutant leaves the test, and the share of such queries is reported.
- **Same structure:** a run can also draw argument edits whose query has the ground truth query's features with no table content, marked apart, for the result on pairs that those features leave tied.
- **Roots:** closed per-input roots with an `output` leaf, whose table holes take the candidate's table, the tables that Q reads, and the base tables.
- **Stable root:** a root with one value at every train pair, and that value is neither "no value" nor the root's default.
- **Contingent root:** a root that `input`, or some table Q reads, does not have as stable, with the candidate's table hole bound to that table. So Q and Q' have one set of contingent roots.
- **Score:** S(T) is the number of contingent classes that are stable on table T, over the number of contingent classes, and 0 where there are none.
- **Primary statistic:** AUC = P(S(Q) > S(Q')) + 0.5 P(S(Q) = S(Q')) over the items of a task, with the mean over tasks. A list with no contingent class on a pair ties it, so every list reads one fixed set of pairs. It reads the queries other than the one that `OUT` reads, which is reported apart, since it equals the output at the train pairs. It reads the pairs where Q' has rows at every train pair, since an empty table needs no feature to reject, and any stable active root beats it. The statistic over every pair is reported beside it.
- **Ties:** a list ties a pair where S(Q) and S(Q') are equal. A list of low-support roots ties most pairs, so its AUC stays near its null whatever its roots are worth. So each list also reports the share of pairs it does not tie, and how often it favors Q there, on the true outputs and on the permuted ones.
- **Graded score:** a stable root cannot show a value that varies over the pairs. So a `ratio` shape also reports the AUC with S as its greatest value over bindings, in the mean over the train pairs.
- **Null:** a permuted-output control: the same AUC with the train outputs under a derangement, a permutation that leaves no output at its own pair, and the contingent roots found again on them. So each example's table is compared with another pair's output. It shows how much of the AUC comes from what the tables look like, and not from how they relate to the output. A task whose train outputs are all equal leaves the null.
- **Known limits:** Q was fitted to every train pair, so this measures the recognition of a fitted query, which is what the search must find, and it says nothing about the test inputs. A mutant can compute something as good as Q, which lowers the AUC. S counts every class once, so many weak classes dilute a strong one, and this does not bound what a model can do with the same roots.

## Offline ranking evaluation

Alias: gate. A feature-set comparison (ablation study): gradient-boosted trees rank Q over Q', trained on train tasks and scored on dev tasks, per feature set, beside a baseline with no table content. This is the one test here that trains a model.

A fit moves with its seed, by as much as many differences between sets. So a set's result is the ensemble of several seeds, with the spread of its single fits beside it, and a difference between two sets is a paired difference over tasks.

A fit has a row at each example, a train pair or a test input. A shape that reads the output has no entry at a test input, and a shape that reads no output is read over every example.

## Rule recognition

Whether statements selected on some train pairs recognize the real output of a left-out pair.

- **Items:** (task, train pair h), for tasks with at least 3 train pairs and near misses for h.
- **Near misses:** every output of the task's module in `model/contracts/nearmiss/` that the module's `_valid` accepts and that differs from the true output, once per distinct grid per pair. The stored near-miss records hold features alone, so the outputs are rebuilt from the modules. The authors were asked for outputs that survive the first version's input claims, and the stored records keep those. So the primary statistic reads all outputs, and those that survive and those that do not are reported apart. On those that survive, the first version's claims on base tables are handicapped by selection.
- **Roots:** closed per-input roots with an `output` leaf, (a) on the base tables, which is primary, and (b) on solver tables that read no train output.
- **Claims C_h:** the roots with one active value at every train pair other than h.
- **Violation V(x):** the share of the classes of C_h whose value at output x differs from their claim. With no claim, V is 0 on both sides, so the item is a tie, and the share of such items is reported.
- **Primary statistic:** per pair, AUC = P(V(true) < V(m)) + 0.5 P(V(true) = V(m)) over the near misses m of h, with the mean over pairs per task and the mean over tasks.
- **Null:** the same AUC with C_h from another task, drawn at random. It shows how much of the AUC comes from what true outputs look like, and not from the task's claims.
- **Also reported:** the rate of false rule-outs (some claim fails at the true output) beside the rate of rule-outs (some claim fails at m), since an OR over claims rises with the number of claims.

## Scene recognition

Whether statements selected on some inputs recognize a real input against random mutations of it.

- **Items:** (task, input h), for each train and test input. A train input's mutations are the Negatives. A test input's mutations come from the same generator, `run.mutate`, with a fixed seed, and they have base tables alone.
- **Roots:** closed per-input roots with no `output` leaf, (a) on the base table `input`, which is primary, and (b) on solver tables that read no output, at train inputs.
- **Claims, violation, statistic and null:** as in Rule recognition, over inputs, with claims from the inputs other than h.
- **Known limit:** a mutation can keep the scene, such as moving an object in a task where any place is allowed. This label noise lowers the AUC.

## Coverage of the first version

Whether a model's row gives what the first version tells a model. [Purpose](feature-spec.md#purpose) requires that it does.

- **Items:** each distinct feature of `model/contracts/features`, on a sample of train tasks. Features with equal values on the sample's rows are one item. `guarantees/`, `nearmiss/` and `dev/` are no model input, so they stay out.
- **Rows:** a table of a ground truth program or of a mutant at one train pair. For what the first version states of the base tables, a row is one train pair. The first version's value and the column read a table at one assignment.
- **Form:** a feature that names a column by its place, or another table by its identity, is compared in the form a shape has: its greatest value over the bindings of one type signature, with the other table written as how it stands to the owner. A word is compared as whether some binding gives it.
- **Covered:** on the rows where the feature has a value, its value is a function of one column's value, and that function is monotone or changes few times along the column, so a few splits can read it.
- **Not judged:** a feature with under 5 rows off its commonest value (low support), a feature with one value on every row (zero variance), and text that describes a column or a table, which has no number.
- **Missing:** any other feature.
- **Statistic:** the counts of covered and missing items, by the first version's feature metadata: what a feature reads, its aggregation level, and the other tables it reads.
- **Limit:** a feature that only two columns together give counts as missing. Coverage shows that a model can read a value, and not that the value helps it.
- **Running:** `model/feature_eval/v1_dump.py` writes the first version's values, and `model/feature_eval/v1_cover.py` gives the result.

## Counts

A description, with no test. Per size, the number of ground expressions and of closed roots, by exact enumeration, and the number of classes of closed roots with an equal value vector over the sample's examples and variants. A size that adds no class adds no feature on this sample.

## The size to run

The rule is fixed before any result. It reads the primary AUC of Candidate, Rule and Scene recognition on hard items, less its null, on the primary tables and the fixed tasks of each curve. Intervals are 99% bootstrap intervals over tasks.

The **gain at d** of a statistic is the greatest of its means over the sizes above d, less its mean at d. So a size that a larger one does not beat has no gain, and a statistic that falls with size gets no credit for it. The **last step** is its mean at D less its mean at D-1.

The result is the first of these that holds:

1. **Unsaturated:** for some statistic, the last step is at least 0.01, and its interval lies above 0. No size is chosen, and D should grow.
2. **Chosen:** the size to run is the smallest d where, for each statistic, the upper bound of the gain at d is below 0.03. Expressibility at that d is reported beside it.
3. **Noise-limited:** no size is chosen.

A chosen d says nothing about sizes above D.

## Left out

- **Wrong assignments:** the cache holds no tables for them, 347 of 665 tasks have one assignment, and no stored record shows that a non-first assignment fails the train pairs. An output-reading feature is circular on them.
- **Program relations:** they read no row, so no test here scores them. A model can.
- **Task-wide roots and combined vector entries:** the tests read values at one example, under the left-out rule, so these enter no test. A model can test them.
- **The search's own candidates:** Candidate recognition draws random mutants. When the state search can draw candidates, the same test runs on its draws.
- **Concept cards:** they need a reader.
- **Program recovery:** it needs all 729 tasks and baselines on column types, since which features apply reveals the types.
