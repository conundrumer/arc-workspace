# Redesign: what is measured, and what is open

Status: proposal. Nothing here is built. Each statement under "Measured" cites a worker's record. Each item under "Open" is a choice the measurements do not settle.

## Measured

Figures are on the union gold (every non-excluded case of each task, tables merged by content), ramp unless said otherwise. In this section, a table counted, reached or computed is a parameterized table. Sources: work/results.md, work/measures.md, work/lm/data-study/gold/gold-union/, work/lm/data-study/sampler/search-worker/kit-decisions.md, work/lm/data-study/sampler/sampler-worker/proposer-inventory/inventory.md, work/lm/data-study/sampler/sampler-worker/sampler-depth-tools/reach-arms-ramp/arm-table.md.

- Everything a query uses is a parameterized table. The task enters through the base tables input, ex_input and ex_output; a DET over them is a depth-0 parameterized table; the goal is a parameterized table an OUT uses.
- Reach by depth has one shape on every set. A 600 s job reaches 87 / 59 / 25 / 5 % of union tables at depths 0 to 3 on the ramp, 70 / 45 / 23 / 7 % on the 37, and 85 / 45 / 12 / 5 % on 989 training tasks under R120. Growth ends by 300 s.
- The cut is bits per query. Gold queries behind reached tables cost a median of 5 to 10 bits; behind never-reached tables, 16 to 18. The most expensive reached table per task has a median of 13.0 bits. A job makes about 6,000 tries. Rank under the proposer is about 2 to the (bits − 4.5).
- Half the bits of a hard query are the relation pick (51%), spread over atoms at 4 to 10 bits each.
- Inputs exist and do not meet. Of ramp graph queries whose used tables were all reached and whose head was not, 65% never had those tables together in one context of the right kind (M2 arms). Context members are 74% depth-0 tables and about half one-row constants.
- The pick's learned score was fit on 22 tasks and 68 gold tables. A node score fit on 884 tasks and 8,029 positives cut constants in contexts by 15 points and raised reach at no depth.
- Of 28 hand-set decisions in the search kit, 9 were never measured against their absence, 10 tied or fell within noise, 2 showed an effect (the pool over plain sampling; the least-used slot). Of 94 in the proposer, most were never measured; the tilt steer has empty weights; no steer is computed from table rows or the base tables; under the corpus prior every declared relation has the same weight.
- Re-judged by reach per depth, none of 25 saved ramp arms moves past the band at depth 2 or 3 in either direction. Controls reach 2 to 6 of 47 depth-3 tables per job.
- Every learned score so far (node rank, node score refit, M2) gained offline and not in reach live.
- Six policy-model trainings exist; the four larger ones were dropped for losing under queries covered. The union graph's queries have not been used as labels.
- The merged training graph (924 tasks with a graph): 23,817 tables, 64,381 queries, 8,072 tables computed by several queries (mean 2.74 queries per table, rising with depth from 1.18 at depth 0 to 7.0 at depth 10). 348 tables are unreachable by the search (166 count-exported, 51 at the work cap, 131 grammar-refused). Cheapest path median 16 queries; goal depth median 6.
- A computed parameterized table is a function of its computing query and the queries it depends on. The engine evaluates every query under one joint DET assignment at a time. Today the export writes that assignment into a dependent query's table as extra columns; nothing joins on them. Decided: assignments are not columns. A parameterized table is a map from the assignments over the DETs it depends on to its tables, and the engine already evaluates per such assignment; the export changes to write one record per table, that is per parameterized table and assignment, holding its Set of TableRows, Example a column of each Row, and no assignment columns. The language is unchanged.
- A query's identity (query id) is the engine's name-free content hash: the canonical text with each used parameterized table written as the identity of the query that computes it, down to the base tables; invariant under relabelling and atom order, and under OR branch order once the engine sorts branches as it sorts conjuncts (decided). A computed table is identified by its computing query's identity, its restricted assignment and, for an INIT, the output. A state's identity is its set of query ids.
- Target identity is order-invariant: a query is a set of atoms, and the loss is on the table it computes, so any written order the engine accepts is one target. Identity for deduplication comes from the engine's canonical hash (from refinement and individualization, invariant under reordering and renaming); a canonical string is not needed. Counts from the Python canonical rule, as an upper bound: training's 64,381 queries become 26,682 identities within tasks and 15,554 across tasks; median 34 tokens and 2 atoms per query. Vocabulary: 66 lib relations, 3 base tables, 64 components, 42 ports, 124 field labels, 12 operators, 1 constant, table references by position.
- The union graph as labels: ramp 445 tables and 1,282 queries; the 37 (36 tasks) 3,270 queries; training estimated at 110k to 200k states with their enabled queries on 989 tasks. The corpus has no re-arc and no generators; witnesses exist for 321 tasks.
- The engine exports a table with more than 10,000 rows in one TableRows as counts, not rows.

## The objects and the signature

Terms agreed with the user. Only what the model and its state need; the rest is in docs/arclog/ and docs/engine/. A → B is a map.

- **ColumnValue**: a value of a column's type, such as a Color or a Position. **Row**: Column → ColumnValue. **TableRows**: Set of Row.
- **Type**: Set of Column. A Column is a field with a column type, with no name and no order. Example is a Column; an example is one pair of the task, an input and an output, the test example's output being the hidden answer.
- **Table**: a Type and a Set of TableRows, at one assignment. Each TableRows is at one example under one constraint model, equal TableRows being one; with no factor in use, one TableRows per example.
- **Parameterized table**: Assignment → Table. The Assignment ranges over its parameters, the DETs it depends on. It is a base table (input, ex_input, ex_output), which has one assignment, the empty one, or an output of a query. Its tables share one Type, fixed by its query. Its identity is (QueryHash, Name).
- **Constraint model**: one choice at each factor a parameterized table uses on one example, a factor being a ONE pick, the rows of a CHOOSE, an open parameter, a DEMONSTRATED key or an Unfold tie. It is local to the parameterized table and the example, with no identity across examples; at most 512 per case per input. Bare "model" never means this.
- **Assignment** over a set of DETs: DET → one of its values. A DET is a parameter; its values are each a TableRows of the DET's Type. The engine enumerates a parameterized table's assignments depth-first, DETs in dependency order and values in content order, and its walk stops after 256. An assignment names each DET by its own QueryHash and the TableHash of one of its full values; where the engine prunes a DET to the columns its readers use, the table at a pruned value is written at every full value that projects to it, so a parameterized table can have more than 256 assignments.
- **TableHash**: a hash of a table's Type and TableRows. A measurement only: two parameterized tables whose tables have equal TableHash are not one parameterized table.
- **TableVector**: the features of one table. **Assignment vector**: the features of one parameterized table over its assignments, such as their count, whether its tables differ, and aggregates of its TableVectors. **QueryVector**: the features of one query.
- **Query**: (body, inputs: Reference → Parameterized table, outputs: Name → Parameterized table).
    - A Reference is an atom that uses a parameterized table: in the body of a RULE, DET or OUT, in a clause at an input port of an INIT's component, or in a part of a RIGID_DET.
    - A Name is the one output of a RULE or DET, an output port of an INIT's component, or a part or the pose of a RIGID_DET. An OUT has none.
    - Identity (**QueryHash**): the body with each input written as its computing query, up to renaming and order. The engine realizes it as a canonical hash, with OR branches sorted.
    - The lib is part of the language: its relations with fixed rows, its relations computed from bound arguments and its components are operators in a body, and none is in the state. A proposer is part of a DET's body.
- **Program**: a set of queries closed under inputs, with one OUT. It holds at most one query per QueryHash, choice queries (DET, ONE, CHOOSE) included: two DETs with one body are one parameter. **Partial program**: without an OUT.
- A program **solves** a task when, over the assignments at which its train outputs equal the given ones, and within each over the constraint models of the OUT, the distinct test grids number at most two, one of them the answer.
- **State**: Set of Query, closed under inputs. That set is the whole identity: two states are equal when the sets are equal. Computed from it, not stored: every parameterized table of its queries, each holding the assignments its walk reached. If two queries compute parameterized tables whose tables have equal TableHash, neither is derived from both queries.
- **Model**: State → distribution over query bodies whose inputs are parameterized tables of the state. It writes a query, never an assignment.
- **Union graph** of a task: every case's queries, with a parameterized table of one query standing for one of another where their maps assignment → TableHash are equal, DETs of different QueryHash paired by equal sets of their values' TableHashes. A measurement.
- A graph query is **applicable** at a state when every parameterized table it uses is in the state. A **target query** at a state is an applicable graph query written over the state's own queries. **Acceptance test of a written query** f against a target g: at every assignment of the state over the DETs f and g depend on, each output's two TableHashes are equal; for a written DET, the sets of its values' TableHashes are equal. Credit is per parameterized table. A target parameterized table whose walk stopped at the cap is left out and counted.
- **State sequence**: starts at the base tables, adds one query per step, ends when the OUT's inputs are all computed. **Sample**: a state with the graph queries applicable at it, one per distinct state. States keyed by query set: ramp 1,816, the 37 7,155, training 109,610.
- A parameterized table is **unreachable by the search** when the kit can't compute it: the engine stops at the work cap, its walk stops at the 256 cap, or the kit's grammar refuses its query. Under the old export, a parameterized table over 10,000 rows in one TableRows was exported as counts and was unreachable too.

### Terms not to use

Docs and code use the terms above. These other words for the same things are not used, in prose or in new identifiers:

- definition, function, form, clause, production, line (for one item of a program): **query**. "Function" stays only in its mathematical sense.
- DefinitionHash, form id, form identity, ident: **QueryHash**.
- given table: **base table**.
- Rows, RowSet (for a Set of Row): **TableRows**.
- walk (for a state sequence): **state sequence**. "Walk" stays only for the engine's walk over DET values.
- node, pool node (for a computed table): **parameterized table**, or a table.
- world, DET assignment: **assignment**.
- stable key, skey, table key, content key, merge key: **TableHash**.
- extension: **parameterized table**. entry, extension entry, table at an assignment: **table**. In the old export, an entry is **one TableRows**.
- model, for a constraint model: **constraint model**. Bare "model" is the learned writer.
- relation, for a table: **table** or **parameterized table**. "Relation" stays for the lib's relations.

## The question

Whether one learned model, given a partial program and its evaluation, can tell which query to add next on a known path to a program that solves the task, where the hand-set pick and proposer cannot.

## Settled with the user

- The model writes the query: given a state, it produces the text of one query under the grammar, the types and the state's mask (only tables in the state may be used). It does not rank candidates written by anything else, and the hand-set proposer is not its candidate writer.
- The loss is on the parameterized table the query computes: a written query is accepted at a state when the parameterized table it computes equals the one a target query computes. That is a judgement about outputs, not a claim that the parameterized table is derived from both queries.
- The model sits beside a search. The search is not decided now: it is abstracted as features over the whole state, so a choice of search is a choice of what the state exposes.
- Each table enters the state as a feature vector computed from its type and rows, and from the table together with the base tables: hand features now, an embedding later. Each query in the state carries a query vector, computed from its used tables' vectors and its computed tables' vectors and the relation between them, and optionally from the query's text (kind, component, atom count). The feature sets are not decided now. The function over the whole state (the set of query vectors with their use edges) may be learned entirely. The engine exports a table with more than 10,000 rows in one TableRows as counts, so features that need rows stop there without an engine change.
- Training targets: at every state on the union graph, every applicable graph query, every case. The search's own draws are not targets. Its draws on train tasks serve as negative examples; whether they serve as held-out evaluation is open.
- Held-out set: the 120 arc-agi-2 public evaluation tasks, for academic reasons. Train and dev are split over the other 1,027 by a hash of the task id, balanced over strata from stable facts (goal depth, output size equal to input size), no bits and nothing from our models: train 866, dev 161, held-out 120. Only 35 held-out tasks have a union graph, so reach on the held-out set covers 35 tasks; held-out tasks have larger inputs than training (86 of 120 with a median input of 226 cells or more, against 304 of 1,027). Judge of a live test: solves on the test example, with reach of union tables per depth as the diagnostic. From existing runs: the ramp has 0 to 2 solves of 22 per seed and the 37 has 0, so a change of 3 solves needs about 4 seeds per arm pooled on the ramp; training R120 (989 tasks, 8 solves on the test example at one seed, 10 with a candidate) shows a change of 10 at one seed, as a lower bound since training has no control pair. Reach per depth is measured at depths 0 and 2 and deeper; depth 1 has too wide a band on the ramp.
- Hand features continue to be made for the per-table and per-state representation, by AI agents, to keep reducing loss. The model is gradient-boosted trees over those features: at each writing point it scores the admitted tokens. It owns every token choice; the engine's mask is the only constraint. It is first trained on the existing features, and feature work goes on in parallel.
- At each writing point, each admitted token gets one feature vector of fixed length, in blocks: the token (class and id), the candidate, the partial query, the state, the task (the base tables), and the place (phase, nesting, atoms so far). A token is judged by the table its successor body computes, as a query is judged by its tables: the candidate block holds the successor body table's features, its change from the current body table paired by assignment and input, and its matches with the partial query by type, Ident source and frame. For END the successor is the query's output tables. Parameterized tables enter by fixed aggregates of their TableVectors over assignments for now.
- Performance work puts algorithmic improvements first. Caching is a last resort, used only when no algorithmic change is left.

## Open

- The per-table feature set, starting from the inventory of per-table features that exist today.
- What the state exposes of the search (which abstracts the search choice).
- Whether the search's draws serve as held-out evaluation.

## Code changes in build

The user gave the go on 2026-11-02. Each is built by its owner, uncommitted, in the order below.

- The sample data build, specified: per-table feature function over (type, rows, base tables), about 164 features, to be computed in the engine at export where possible; a side output of the union run writing each table's feature vector and TableHash; the state-sequence generator over the union graph with targets identified by the engine's canonical hash; samples sharded by task. The held-out set is the 120 evaluation tasks; train and dev come from the hash rule over the rest. Sets are named only by this split (train, dev, held-out); a smaller set is a named fixed sample of one split. Pod-parallel stages are being marked. work/lm/data-study/features-worker/sample-build-spec/spec.md and contract.md.
- The query writer (the component that writes one query body from a state), specified: one query body from a state, each decision the next stream token under the engine's admissible mask, with the distribution over admitted tokens supplied by a pluggable function of the prefix, the decoder state, the state's table vectors and the task. It takes the place of the hand-set proposer in the search's execute step and replaces about 2,350 lines; 720 to 1,210 new. Budget, measured on 6 ramp tasks: the mask call costs 0.26 ms median, a step 0.02 ms, about 14 model tokens and 5 ms of engine time per query, 81 admitted tokens per state of 805; with body tables at each atom start the engine takes 21 to 37 ms per try, which leaves 2 to 5 ms per model call inside today's 89 ms; without body tables, 3 to 6 ms. With it, the table import fix (the sampler's Python code that turns an exported table into rows raises on a table exported as counts), Python only, 110 to 200 lines; today at most 1.5% of tries are dropped that way. work/lm/data-study/sampler/sampler-worker/proposer-inventory/writer-spec.md.
- A search over states driven by a score, specified: a best-first frontier of states; the two choices are a score module and the writer's distribution; about 650 of 748 search lines go, a new file of 250 to 350 lines, about 150 lines change elsewhere. work/lm/data-study/sampler/search-worker/state-search-spec.md.
- Engine side, decided: expose the engine's canonical hash as the query identity. The model takes features, never tables, so the export writes per table the TableVector computed in the engine from the full TableRows, with the TableHash and row counts, for every table with no count cap, and that is what the state search and the samples use. The 10,000-rows-per-TableRows count export survives only in the old format until the consumers switch. For feature development only, the export also writes every parameterized table in full, every assignment and every TableRows with no count cap, to a store once per run, each table once by TableHash, so a feature change never re-exports; Features-worker develops features in Python over that store, and a feature that settles moves into the engine's feature code. That code is one Rust crate, engine/arclog-features, called by the export and by a Python module over the store.

## Build order

Dependencies only.

- The Kaggle submission (on the user's word): after the trees are trained and in the writer, and the kit survives engine panics, memory kills and hangs, with every task still getting an answer.
- The table import fix for count-exported tables (Sampler-worker, Python only) depends on nothing and serves the sample build, the query writer and the state search.
- The sample data build (features-worker, Mac) depends on nothing else; its per-table vector is what the state search and the writer's pluggable function consume.
- The state search (search-worker) depends on nothing to build; it runs with an adapter over the current hand-set proposer until the writer exists, and takes the writer through one query.
- The writer (Sampler-worker) has its budget measured; its pluggable function takes hand features first and a learned model when one is trained on the samples.
- The trees depend on the samples and on training rows made by the writer's own feature code, so training and serving compute features one way.
- Engine-side items (Sampler-worker, after the table import fix): the export writes each parameterized table as one table per assignment, Example a column of each Row, with no assignment columns; QueryHash exposed; table summaries at export. The old format stays behind a flag until the state search and the sample build switch. They remove the Python canonical text and the table import fix when done. The union derivatives of each split are rebuilt once, after this lands.

