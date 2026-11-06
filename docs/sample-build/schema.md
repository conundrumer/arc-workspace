# Training sample schema

On this page, "the 37" and "the ramp" are older sampler lists, and "held out" means left out of the sampler's fits. None of these is a part of the split. See [Held-out test set](../../work/measures.md#held-out-test-set).

Status: record. Nothing here is built. The schema serves the section "Settled with the user" of [the redesign proposal](../proposals/redesign-proposal.md). The model is a generator: it writes a query body given the state, under the grammar, the types and the state's mask.

Paths in this record are short where they repeat:

- `GU/` is `/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/`.
- `UN/` is `/Users/davidlu/code/arc-workspace/model/study/gold/reads/union/`.
- `KIT/` is `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943/model/study/sampler/`.
- `SW/` is `/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/`.
- `SF` is `SW/state-features.md`.
- `INV` is the [per-table feature inventory](inventory.md).

Terms:

- A **graph table** is one line of `GU/graph-tables-SET.jsonl`, named by its field `table`. On the ramp and the 37 that name is `m` followed by the `table_key` value (`UN/gold_union_graph.py` docstring, line 7). On training it is the union key (`GU/graph-tables-training.jsonl`, first line: `"table": "0"`).
- A **graph query** is one line of `GU/graph-prods-SET.jsonl` (the file calls it a production): `ident`, `kind`, `heads` (the graph tables it computes), `reads` (the graph tables it uses), `depth`.
- A **state** is the set of queries at one step of a state sequence of `UN/gold_union_walks.py` (lines 24 to 36), closed under inputs (the contract, `State`). The graph tables that its queries build are a measurement.
- `table_vec[?]` is the per-table feature vector. Its content is the section [What the features are computed from](inventory.md#what-the-features-are-computed-from) of `INV`, less what the settled calls below take out. The field list is not fixed, so each `[?]` is a placeholder for it.

Settled:

- The model is a generator. It writes a query body given the state. It does not rank candidates, and the proposer does not write candidates for it.
- Depth counts a root (a parameterized table whose query uses no built parameterized table) as 0. It is computed over the state's own edges.
- On training, a graph table's name is the union key.
- `table_vec` leaves out every feature that is computed from order or marks (the mark "order" of the section "Marks" in `INV`).
- The features that are computed from the query's body do not go into `table_vec`: its kind, its count of atoms that use a parameterized table, the count of Names it has, whether the parameterized table is an INIT output or a method, and the `Form shape` counts. Under a generator they are parts of the target body, not inputs.
- A parameterized table is written as (`QueryHash`, `Name`) of the query that computes it, and a base table by its name (the contract, `ParameterizedTable`). It maps each `Assignment` over the DETs it depends on to a table (its Type and a set of TableRows); the engine keeps the first 256 assignments of each parameterized table. There are no assignment columns. Two assignments that agree on the DETs the parameterized table depends on give its table one key. A DET with several values has one key for each value.
- At one assignment, a parameterized table gives a table, which is a Type and a set of TableRows. Each TableRows holds the Example column, with one TableRows per constraint model on each example (one choice at each factor that the parameterized table uses on that example: a ONE pick, the rows of a CHOOSE, an open parameter, a DEMONSTRATED key or an Unfold tie), with equal TableRows being one. With no factor in use, there is one TableRows per example. Constraint models are inside the table, never in a `ParameterizedTable`, an `Assignment` or a `QueryHash` (the contract, "The table at one assignment").
- Where an example has several TableRows, `table_vec` and the features over use edges follow the contract's rules (the contract, `TableVector`, "Several TableRows per example", and `QueryVector`).
- The `TableHash` is a stable hash of a table's column types and its set of TableRows at one assignment. The Example column is part of each row, so the hash covers it. It is a measurement, never an identity. It hashes the parts of one table that `table_key` hashes (`KIT/superdag.py` 83 to 114), at one assignment. The hashes of `table_key` are Python `hash` values, which compare only within one session (`KIT/superdag.py` 84). This is a record of the call. Nothing is built.

A sample is a state and its target queries.

## State

A state is a set of queries, closed under inputs, with the use edges of their tables. Each parameterized table of its queries enters at each of its first 256 assignments as a feature vector.

| Field | Content | Source |
|---|---|---|
| `tables` | one item per built parameterized table at each of its assignments, that is, per (`QueryHash`, `Name`, `Assignment`): `table_vec[?]`; at most 256 per parameterized table | `INV`, "What the features are computed from" |
| `edges` | for each built parameterized table, the built parameterized tables used by the query that computes it | `reads` and `heads` of `GU/graph-prods-SET.jsonl` |
| `given` | the base tables (input, ex_input, ex_output) | proposal, "The objects and the signature". These are not graph tables, so the empty state of a state sequence holds only them (`UN/gold_union_walks.py` line 5) |

The lib's relations are not part of the state.

Per-table fields over use edges, from `SF`, kept because they depend only on the built parameterized tables and their use edges (dependence T in `SF`). None of them is a whole-state aggregate: each is a value of one parameterized table, computed over its use edges or the queries that use it.

| Field | Content | `SF` row and source line | Notes |
|---|---|---|---|
| `depth` | 1 + the greatest depth of the parameterized tables its query uses; a root is 0 | depth; `KIT/superdag.py` 247 | Settled as above. The graph counts the same way (`UN/gold_union_graph.py` docstring line 9). The pool counts a root as 1 (`KIT/superdag.py` 247, `default=0`). |
| `n_parents` | the count of built parameterized tables its query uses | n_parents; `KIT/superdag.py` 271 | |
| `link_np` | the count of those parent parameterized tables the policy has scored | link_np; `outfeat.py` 135 | The pool scores each table when it is new (`SF` line 10), so on a state this equals `n_parents`. |
| `link_parent_gain`, `link_adds`, `link_better`, `link_new_cells`, `link_new_count`, `link_pair_union`, `link_filter`, `link_grow`, `link_disjoint` | the parents' paint state: gain, fixed cells, cell set | `outfeat.py` 131 to 151 | They are computed from the train outputs (task input, allowed). They need rows. |
| `link_row_ratio` | (rows + 1) / (greatest parent rows + 1) | `outfeat.py` 153 | needs row counts |
| `kid_n`, `kid_best`, `kid_best_adds` | the gains of the parameterized tables whose queries use this parameterized table | `outfeat.py` 156 to 170 | Not among the policy model's 87 names, and nothing calls them at run time (`SF` line 22). |
| `n_readers` | the count of built parameterized tables whose query uses this parameterized table | n_readers; `KIT/superdag.py` 288 to 290 | |
| `n_queries` | the count of queries whose table equals this table | `SF` row n_clauses; `KIT/superdag.py` 317 | In a state each parameterized table is computed by one query (the contract, "Settled calls"), so on a state this is 1. |
| `ancestors` | the closure of the parameterized table's use edges | Context membership, the closure part; `KIT/superdag.py` 199 to 213 | `SF` marks which tables enter a context as H and the closure as T. Only the closure is kept. |

`SF`'s `dp_form_reads` (`KIT/superdag.py` 262) is computed from the query's body, so it is not a state field (settled call above).

Dropped from `SF`, each with the reason:

| `SF` item | Reason |
|---|---|
| uses | count of earlier picks; depends on the pick (H) |
| node id order | creation order of the pool's ids; depends on the least-used slot (H). It is also an order of ids |
| Gumbel draw | the pool's rng per opening (H) |
| Mix coin | per opening, seeded by pool id and seed (H) |
| Context membership, which nodes | depends on the picks (H) |
| Kind weights | the decoder's admitted kinds after the context, weighted by global prior counts `kinds1` (H) |
| Slot, Resume, Patience, Visit and clause time, Best-first frontier | slot and visit structure (H) |
| "Merge keys, reset by renewal" (the `SF` item name) | the reset is H. The T part (whether a table equals a built table) is a measurement: it serves the acceptance test of a written query and the count of queries that make no progress |
| Renewal, Search manager, Draw seed | process and rng structure (H) |
| OUT test | depends on the context (H) |
| Counters | nothing in the search uses them (`SF` line 60) |
| Proposer steers (`scope`, `prefix`, `point_group`) | depend on the context and the visit kind (H). `prefix` is the atoms so far, which is a position in the body: it breaks the rule on marks and order |
| `SEARCH_READ_SCOPE`, `SEARCH_NEW_TABLE`, `SEARCH_READ_PICK` | use the picks (H); off in round 1 (`SF` line 68) |

Fields of `GU/graph-tables-SET.jsonl` that no state field may use, because they are computed from gold: `bits`, `cost_known`, `cost_low`, `goal`, `pinned`, `cases`, `productions`, `members`, `root_det`, `kit_unreachable`, `depth_cases`. The graph `depth` of a table is also gold's (least over its queries); a state field uses depth over the state's own use edges.

## Target queries

The target queries of a state are the graph queries enabled at it: every parameterized table the query uses is in the state, and some parameterized table it computes is not. A graph query whose tables all equal built tables of the state makes no progress, so it is not a target query and not a step of a state sequence; the count of such queries per state is a measurement (`redundant_forms`).

| Field | Content | Source |
|---|---|---|
| `body` | the query's body as canonical text | see "Canonical text" |
| `defines` | `table_vec[?]` of each parameterized table the query computes, at each of its first 256 assignments, where that parameterized table exists | a replay |
| `group` | the set of graph tables the query computes | `heads` of `GU/graph-prods-SET.jsonl` |

Queries with an equal `group` compute tables with equal TableHashes. Each stays its own target query. The loss counts each target parameterized table as one unit, whatever its count of assignments. The acceptance test of a written query matches a target parameterized table when some output of the written query has its Type and an equal TableHash at every assignment that the test covers, with no compare of Names; a parameterized table that matches at some assignments and not at others gets no credit (the contract, "Assignments"). A target parameterized table past the 256 cap is left out and counted. An INIT query can compute several parameterized tables (`UN/gold_union_graph.py` docstring line 6), so its `group` can hold more than one parameterized table. `GU/supervision-37.json` counts 487 graph tables with more than one query (`or_tables`); training has 6,506 (`GU/supervision-training.json`).

Applicable and enabled are different sets:

- An applicable query can compute a table that is already in the state.
- The state sequences record the enabled queries: every table the query uses is built, and some table it computes is not (`UN/gold_union_walks.py` lines 5 and 28).
- So the enabled set is a subset of the applicable set. The target queries are the enabled set. "Row counts" gives both.

Fields that break the rule on marks and order, so no target query or feature may use them. They may serve as row identifiers only:

- `ident` of a graph query: a hash of its text (`GU/design.md` line 15).
- a graph table's name: the union key is an index in order of first appearance in gold's text, with the pinned program first (`GU/design.md` line 20).
- `bits` of a graph query: a cost of gold's query (`UN/gold_union_graph.py` docstring line 10). It is computed from gold.

## Canonical text

### What the files hold of a query's text

| File and field | What it holds | Source |
|---|---|---|
| `GU/graph-prods-SET.jsonl` | no text: `ident` only | file head |
| `GU/union-SET.jsonl`, `tables[].forms[]` | `ident` and `text`, one per identity. The text is one case's line as written, with that case's labels, for example `(RULE &r2 (input (:P *P) (:Col *Col)) (NOT (&r0 (:C Col))))` | `GU/union-ramp.jsonl`, first line; `UN/gold_union.py` 115 |
| `GU/union-SET.jsonl`, `tables[].reads` | per identity, the union keys of the tables it uses | `GU/design.md` line 24 |
| `GU/union-keys-SET.jsonl` | per case: `text`, the case's program after `Bar.normal`, and `keys`, the union key of each non-OUT line in order | `UN/gold_union_keys.py` docstring line 1 |
| `GU/union-identity-SET.jsonl`, `tables[].form` | one text per identity, with labels as written | `GU/union-identity-ramp.jsonl`, first line |

`Bar.normal` is the engine's round trip of the program text (`model/study/gold/cover_forms/gold_cheapest_common.py` 105 to 109). Its output names the queries `&r0`, `&r1`, ... in the order of the queries in the case's text (`GU/union-keys-ramp.jsonl`, first line).

A query's identity is its text with each reference to a query replaced by the identity of the query it uses and its own label dropped (`UN/gold_union.py` 47 to 60). It keeps the variable names, the field names of computed tables, `*`, `^` and the order of atoms. So queries that are equal only under relabelling stay apart (`GU/design.md` line 17).

The map from a reference `&rN` in a case's text to a graph table is in `UN/gold_union_graph.py` 99 to 113: the case's labels with `keys` give (union key, kind), and a reference to an INIT output gives the output after the dot. On the ramp and the 37, the merge map then gives the graph table (docstring line 7).

### What in that text is a mark

| Part | Example | Why it is a mark |
|---|---|---|
| the query's own label | `&r2` in `(RULE &r2 ...)` | a label name; after `Bar.normal` it is the query's place in the case's text |
| a reference to another query | `&r0`, `&r2.tile` | a label name, as above. The part after the dot is an INIT output, a port name of the lib's registry (`UN/gold_union_graph.py` 66 to 88) |
| variable names | `P`, `Col`, `A`, `Across` | label names chosen by the author |
| the field names of a computed parameterized table | `:C` in `(&r0 (:C Col))` | a computed parameterized table's column names are the labels of its body as written (`INV`, `Form shape` section, citing `docs/arclog/arclog.md` line 31) |
| `*` and `^` | `(:P *P)`, `(OUT (&r11 ^P ^C))` | banned by the marks rule |
| atom order in a body | `(input ...) (NOT (&r0 ...))` | a position in a body |
| branch order in an OR | `(OR ((...)) ((...)))` | a position in the text |

The field names of a base table or a lib relation (`:P`, `:Col` of `input`) are its declared fields, which identify a column by the field it came from.

### The canonical text

- Drop the query's own label.
- Write each Reference as the parameterized table it uses: (`QueryHash`, `Name`) of the query that computes it, where the `Name` is the port's name in `engine/lib/registry.sexpr` for an INIT output, `slot <n>` for a RIGID_DET part, n the part's position in the form's canonical form (`slot <n>.<port>` for a part that reads an instance output), or `pose`, and the empty string for a RULE, DET or CHOOSE. Write a base table by its name. A body applies under every assignment, so a Reference holds no `Assignment`.
- Rename the variables by a labelling that depends only on the join structure of the body, not on the order of the atoms.
- Write a computed parameterized table's field as the field it came from in the query that computes the parameterized table, not by its label.
- Drop `*`. It follows from the join structure everywhere.
- In a key group, keep `^`. There it selects the key columns (`docs/arclog/arclog.md` line 61), so it changes the query's meaning.
- In an OUT, drop `^`. Every site of an OUT is `^`, so it follows from the query kind.
- These two rules on `*` and `^` are the director's call, not the user's word. The director takes the marks rule as barring marks that do not change a query's meaning.
- For identity, the atoms of a body and the branches of an OR are unordered. For writing, they take a fixed canonical order.
- In that order, each NOT and each ALL stands after the conjuncts that bind its labels. A query that still does not decode takes the first decodable order that the refusal search of `or_q.canonical_lines` finds. On the ramp, 1,091 of 1,282 queries decode in the plain sorted order; 178 of the 191 that fail have a NOT or an ALL before the conjuncts that bind its labels; the refusal search found a decodable order for every ramp query (Sampler-worker's count).

## Row counts

### Sets and their split

Each task's split (train, dev or held-out) comes from the rule in the [split design](split.md). Every data stage processes every set.

| Set | Tasks in the graph | Tasks with state sequences | Split | Source |
|---|---|---|---|---|
| ramp 22 | 22 | 22 | train or dev, by the split rule | `GU/graph-tasks-ramp.jsonl` (22 lines); `walks` 176 = 22 × 8 in `GU/walks-ramp.json` |
| the 37 | 36 | 29 | by the split rule | `GU/supervision-37.json` `tasks` 36, `tasks_without_path` 7; `walks` 232 = 29 × 8 in `GU/walks-37.json`; held list `sampler-worker/held/tasks.txt` (37 ids) |
| training | 988 | 924 | by the split rule | `GU/supervision-training.json` `tasks` 988, `tasks_without_path` 64; `walks` 7,392 = 924 × 8 in `GU/walks-training.json` |

The 988 training tasks share no id with the ramp 22, the 37 (`held/tasks.txt`) or the 99 (`held/leave_out.txt`). This is from a compare of the `task` ids of `GU/graph-tasks-SET.jsonl` with those lists: 0 shared ids for each.

A state sequence is made only for a task with goals and a path (`UN/gold_union_walks.py` line 48). There are 8 state sequences per task and state-sequence type, seeds 0 to 7 (line 13). The state-sequence type `union` picks among all enabled queries; `path` picks among the enabled queries of the cheapest path (line 6).

### Columns

- **States**: steps of state sequences, from `steps` of `GU/walks-SET.json`. Each step records one state. The same state can occur in several state sequences.
- **Distinct states**: distinct (task, built set) pairs. A state is counted at the depth where it first occurs.
- **Applicable queries**: graph queries whose used tables are all built, summed over states. This includes queries that make no progress.
- **Applicable tables**: distinct computed graph tables summed over states.
- **Enabled queries** and **Enabled tables**: as above for the enabled queries. For enabled, only the computed tables that are not built count.
- **Depth**: the frontier depth of the step, the least `depth` among its enabled queries (`UN/gold_union_walks.py` line 8). It is not the depth of a reached table.

The table columns count graph tables, one per parameterized table, which is the unit of loss. A parameterized table's vectors are per assignment, up to 256 per parameterized table; the count of assignments per parameterized table is not measured, and neither is the count of target parameterized tables past the 256 cap.

`steps`, and the enabled queries as `n` × `mean`, are in `GU/walks-SET.json`. The other columns come from a rerun of the state sequences of `UN/gold_union_walks.py` (same function, seeds and file order) in memory over `GU/graph-prods-SET.jsonl` and `GU/graph-tasks-SET.jsonl`. That rerun gave the same `steps` per depth as the file, so it gives the same states.

### Samples: one row per distinct state, state-sequence type `union`

A sample is one distinct (task, set of `QueryHash`) state, as the sample contract defines it. These rows are `union.distinct` of `GU/walks-SET.json`, and the distinct states are in `GU/walk-states-SET.jsonl` (task, forms, built, depth, redundant_forms; `built` is a measurement).

- **Target queries**: the graph queries enabled at the state (every table they use is built, and some table they compute is not), summed over distinct states. A graph query that uses a graph table which two members compute equally gives one target query per choice of member (the contract), so the count of target queries is at least this count.
- **Queries that make no progress**: graph queries not in the state whose tables all equal built tables of the state (`redundant_forms`). They are not target queries and not steps of a state sequence. The column is a measurement.
- **Applicable graph queries**: every graph query whose used tables are all built, including the queries already in the state.

Ramp 22 (`GU/walk-states-ramp.jsonl`, sha256 prefix 744e0a1e):

| Depth | Samples | Target queries (enabled graph queries) | Target tables (enabled graph tables) | Queries that make no progress | Applicable graph queries |
|---|---|---|---|---|---|
| 0 | 783 | 10,139 | 3,388 | 10,084 | 24,487 |
| 1 | 275 | 1,306 | 862 | 1,064 | 4,307 |
| 2 | 214 | 1,886 | 647 | 2,083 | 6,049 |
| 3 | 143 | 663 | 420 | 770 | 2,959 |
| 4 | 123 | 553 | 347 | 1,017 | 3,100 |
| 5 | 97 | 407 | 251 | 729 | 2,436 |
| 6 | 83 | 241 | 208 | 454 | 2,000 |
| 7 | 53 | 157 | 116 | 546 | 1,585 |
| 8 | 32 | 95 | 75 | 232 | 926 |
| 9 | 13 | 35 | 31 | 84 | 418 |
| all | 1,816 | 15,482 | 6,345 | 17,063 | 48,267 |

The 37, 29 tasks with state sequences (`GU/walk-states-37.jsonl`, sha256 prefix 24ed3081):

| Depth | Samples | Target queries (enabled graph queries) | Target tables (enabled graph tables) | Queries that make no progress | Applicable graph queries |
|---|---|---|---|---|---|
| 0 | 1,354 | 9,913 | 6,770 | 7,867 | 27,293 |
| 1 | 779 | 7,229 | 4,264 | 10,210 | 29,993 |
| 2 | 372 | 3,865 | 1,803 | 6,146 | 16,174 |
| 3 | 558 | 4,540 | 2,514 | 7,277 | 21,887 |
| 4 | 515 | 3,612 | 2,382 | 5,563 | 18,680 |
| 5 | 673 | 5,293 | 2,944 | 12,919 | 33,379 |
| 6 | 565 | 3,043 | 2,296 | 6,348 | 22,532 |
| 7 | 419 | 2,516 | 1,699 | 5,615 | 19,305 |
| 8 | 424 | 2,346 | 1,557 | 4,542 | 17,898 |
| 9 | 337 | 1,953 | 1,278 | 4,423 | 16,574 |
| 10 | 322 | 2,776 | 1,298 | 5,711 | 18,924 |
| 11 | 234 | 2,719 | 1,160 | 6,338 | 18,319 |
| 12 | 165 | 1,834 | 756 | 4,994 | 13,974 |
| 13 | 131 | 1,057 | 549 | 2,969 | 10,105 |
| 14 | 92 | 530 | 366 | 1,746 | 7,008 |
| 15 | 73 | 487 | 283 | 1,874 | 6,112 |
| 16 | 45 | 180 | 165 | 622 | 3,374 |
| 17 | 38 | 140 | 113 | 708 | 2,802 |
| 18 | 18 | 46 | 38 | 279 | 1,188 |
| 19 | 21 | 68 | 52 | 435 | 1,680 |
| 20 | 7 | 13 | 13 | 144 | 533 |
| 21 | 13 | 66 | 42 | 337 | 1,206 |
| all | 7,155 | 54,226 | 32,342 | 97,067 | 308,940 |

Training (`GU/walk-states-training.jsonl`, sha256 prefix 31387d9c, 109,610 lines; `GU/walk-seqs-training.jsonl`, sha256 prefix cd00bbc8), on the merged training graph `GU/graph-*-training.jsonl` of 10:57 (prods sha256 prefix 432f564b). 924 of the 988 tasks have state sequences: 7,392 state sequences, 7,376 of which reach the goal.

| Depth | Samples | Target queries (enabled graph queries) | Target tables (enabled graph tables) | Queries that make no progress | Applicable graph queries |
|---|---|---|---|---|---|
| 0 | 32,100 | 292,875 | 158,301 | 456,818 | 976,980 |
| 1 | 14,955 | 119,946 | 65,087 | 203,289 | 488,379 |
| 2 | 14,078 | 101,468 | 57,414 | 152,952 | 431,846 |
| 3 | 12,826 | 93,610 | 53,123 | 164,835 | 447,253 |
| 4 | 10,436 | 78,541 | 41,973 | 148,270 | 409,418 |
| 5 | 7,811 | 58,968 | 29,237 | 134,737 | 341,310 |
| 6 | 5,733 | 38,820 | 21,018 | 91,747 | 248,904 |
| 7 | 4,049 | 29,635 | 14,568 | 75,739 | 200,229 |
| 8 | 2,547 | 17,048 | 8,633 | 45,485 | 126,682 |
| 9 | 1,595 | 8,893 | 5,227 | 25,905 | 78,667 |
| 10 | 1,251 | 10,580 | 4,065 | 27,724 | 77,644 |
| 11 | 736 | 5,207 | 2,332 | 12,783 | 40,699 |
| 12 | 474 | 1,795 | 1,403 | 8,016 | 26,014 |
| 13 | 343 | 1,196 | 1,054 | 4,541 | 18,037 |
| 14 | 224 | 744 | 577 | 3,608 | 12,986 |
| 15 | 166 | 751 | 459 | 3,519 | 11,463 |
| 16 | 97 | 423 | 272 | 2,674 | 7,842 |
| 17 | 49 | 159 | 125 | 1,404 | 4,052 |
| 18 | 35 | 101 | 76 | 873 | 2,655 |
| 19 | 24 | 64 | 39 | 987 | 2,360 |
| 20 | 8 | 10 | 8 | 171 | 524 |
| 21 | 9 | 15 | 9 | 505 | 1,093 |
| 22 | 10 | 17 | 10 | 596 | 1,277 |
| 23 | 38 | 627 | 207 | 3,151 | 6,739 |
| 24 | 2 | 2 | 2 | 0 | 60 |
| 25 | 2 | 2 | 2 | 0 | 62 |
| 26 | 5 | 8 | 8 | 0 | 184 |
| 27 | 3 | 4 | 4 | 0 | 114 |
| 28 | 3 | 4 | 4 | 0 | 120 |
| 29 | 1 | 1 | 1 | 0 | 41 |
| all | 109,610 | 861,514 | 465,238 | 1,570,329 | 3,963,634 |

The tables below count states by sets of graph tables, before the re-key by query set, and sum the columns over every step of the state sequences, so a state that occurs in several state sequences counts once per occurrence. Their "applicable" columns include queries that make no progress.

### Ramp 22, state-sequence type `union` (176 state sequences, 176 reached the goal)

| Depth | States | Distinct states | Applicable queries | Applicable tables | Enabled queries | Enabled tables |
|---|---|---|---|---|---|---|
| 0 | 1,088 | 758 | 25,900 | 8,997 | 11,243 | 4,422 |
| 1 | 377 | 246 | 4,987 | 3,451 | 1,557 | 1,091 |
| 2 | 292 | 174 | 6,812 | 3,433 | 2,082 | 825 |
| 3 | 186 | 109 | 3,464 | 2,407 | 756 | 503 |
| 4 | 159 | 86 | 3,567 | 2,309 | 628 | 414 |
| 5 | 112 | 69 | 2,590 | 1,772 | 438 | 282 |
| 6 | 94 | 60 | 2,167 | 1,685 | 274 | 239 |
| 7 | 56 | 29 | 1,656 | 1,096 | 166 | 124 |
| 8 | 33 | 20 | 955 | 705 | 98 | 78 |
| 9 | 13 | 10 | 418 | 330 | 35 | 31 |
| all | 2,410 | 1,561 | 52,516 | 26,185 | 17,277 | 8,009 |

### Ramp 22, state-sequence type `path` (176 state sequences, 160 reached the goal)

| Depth | States | Distinct states | Applicable queries | Applicable tables | Enabled queries | Enabled tables |
|---|---|---|---|---|---|---|
| 0 | 1,175 | 328 | 16,612 | 9,864 | 8,590 | 4,911 |
| 1 | 178 | 50 | 1,955 | 1,731 | 679 | 601 |
| 2 | 87 | 12 | 1,223 | 939 | 283 | 240 |
| 3 | 8 | 1 | 72 | 64 | 24 | 24 |
| all | 1,448 | 391 | 19,862 | 12,598 | 9,576 | 5,776 |

### The 37 (29 tasks with state sequences), state-sequence type `union` (232 state sequences, 232 reached the goal)

| Depth | States | Distinct states | Applicable queries | Applicable tables | Enabled queries | Enabled tables |
|---|---|---|---|---|---|---|
| 0 | 1,780 | 1,327 | 29,494 | 18,425 | 11,625 | 8,378 |
| 1 | 865 | 743 | 30,600 | 17,526 | 7,406 | 4,416 |
| 2 | 468 | 337 | 16,938 | 8,785 | 4,046 | 1,958 |
| 3 | 649 | 492 | 22,805 | 13,528 | 4,788 | 2,686 |
| 4 | 565 | 420 | 19,286 | 12,464 | 3,720 | 2,462 |
| 5 | 733 | 580 | 34,256 | 18,982 | 5,454 | 3,091 |
| 6 | 592 | 485 | 22,965 | 15,911 | 3,107 | 2,347 |
| 7 | 449 | 362 | 19,864 | 13,482 | 2,574 | 1,755 |
| 8 | 448 | 351 | 18,348 | 13,044 | 2,388 | 1,599 |
| 9 | 366 | 293 | 17,109 | 12,044 | 2,012 | 1,337 |
| 10 | 338 | 283 | 19,288 | 12,103 | 2,815 | 1,337 |
| 11 | 245 | 213 | 18,559 | 10,669 | 2,733 | 1,174 |
| 12 | 174 | 156 | 14,211 | 8,137 | 1,843 | 765 |
| 13 | 146 | 109 | 10,496 | 7,011 | 1,072 | 564 |
| 14 | 109 | 87 | 7,474 | 5,554 | 547 | 383 |
| 15 | 91 | 68 | 6,629 | 4,540 | 505 | 301 |
| 16 | 64 | 43 | 3,944 | 3,295 | 199 | 184 |
| 17 | 65 | 33 | 3,700 | 2,945 | 178 | 151 |
| 18 | 42 | 17 | 1,925 | 1,628 | 79 | 71 |
| 19 | 39 | 19 | 2,303 | 1,839 | 86 | 70 |
| 20 | 14 | 4 | 736 | 592 | 20 | 20 |
| 21 | 13 | 12 | 1,206 | 845 | 66 | 42 |
| all | 8,255 | 6,434 | 322,136 | 203,349 | 57,263 | 35,091 |

### The 37 (29 tasks with state sequences), state-sequence type `path` (232 state sequences, 168 reached the goal)

| Depth | States | Distinct states | Applicable queries | Applicable tables | Enabled queries | Enabled tables |
|---|---|---|---|---|---|---|
| 0 | 3,448 | 1,367 | 94,490 | 59,474 | 33,780 | 22,928 |
| 1 | 266 | 94 | 4,896 | 4,644 | 930 | 702 |
| 2 | 112 | 28 | 1,819 | 1,631 | 411 | 384 |
| 3 | 260 | 55 | 6,178 | 5,690 | 675 | 647 |
| 4 | 20 | 3 | 179 | 163 | 28 | 20 |
| 5 | 230 | 116 | 5,791 | 5,775 | 705 | 705 |
| 6 | 72 | 16 | 1,805 | 1,089 | 480 | 273 |
| 7 | 8 | 1 | 96 | 96 | 8 | 8 |
| 8 | 8 | 1 | 104 | 104 | 8 | 8 |
| 9 | 27 | 8 | 439 | 439 | 52 | 52 |
| 10 | 13 | 6 | 237 | 237 | 21 | 21 |
| 11 | 12 | 4 | 234 | 234 | 17 | 17 |
| 12 | 4 | 1 | 80 | 80 | 4 | 4 |
| 13 | 8 | 1 | 168 | 168 | 8 | 8 |
| 14 | 8 | 1 | 176 | 176 | 8 | 8 |
| 15 | 8 | 1 | 184 | 184 | 8 | 8 |
| 16 | 8 | 1 | 192 | 192 | 8 | 8 |
| 17 | 8 | 1 | 200 | 200 | 8 | 8 |
| 18 | 18 | 4 | 491 | 491 | 29 | 29 |
| 19 | 6 | 1 | 168 | 168 | 6 | 6 |
| 20 | 8 | 1 | 232 | 232 | 8 | 8 |
| all | 4,552 | 1,711 | 118,159 | 81,467 | 37,202 | 25,852 |

## What needs a replay

A replay runs the queries of a case again in an engine session to get the rows and cells of their tables. `reach2.py` in `SW/runs/search-union-reach-ramp22-heldout37/` does one: a fresh session per case, the case's text from `GU/union-keys-SET.jsonl`, and `table_key` of each table (`key_tables`, line 42). It keeps only the per-example list of each table in memory and writes no rows.

No file in `GU/` holds rows or cells of a graph table. The engine exports a table at an assignment with more than 10,000 rows as counts, not rows (proposal, "Measured").

| Field | From files | Needs a replay | Source |
|---|---|---|---|
| state `edges` | yes | no | `reads` and `heads` of `GU/graph-prods-SET.jsonl` |
| state `depth`, `n_parents`, `n_readers`, `ancestors`, `n_queries` | yes | no | computed over `edges` |
| state `tables` (`table_vec[?]`) | no | yes | rows and cells of each built table |
| state `link_*`, `kid_*` | no | yes | they are computed from rows and cells (`outfeat.py` 131 to 170) |
| state `link_row_ratio` | no | yes | row counts per example |
| target query `group` | yes | no | `heads` of `GU/graph-prods-SET.jsonl` |
| target query `body` | yes, before the canonical form | no | `GU/union-SET.jsonl` `tables[].forms[].text`, joined to the graph query by `ident`; the reference map of `UN/gold_union_graph.py` 99 to 113 |
| target query `defines` (`table_vec[?]`) | no | yes | rows and cells of each computed table |

## Note: the search's draws as a held-out evaluation

The search's draws are not in the objective. They could serve as a held-out evaluation: a draw whose table equals a graph table is a query the model should give mass to.

- Saved pools on the ramp 22 and the 37: round 1, `SW/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out/<arm>/<task>/work/<task>.out.jsonl.bank`, 59 banks per arm (`bundle_s0`, `bundle_s1`, `refit_s0`, `refit_s1`). Training: r120 pool record files in `sampler-worker/sampler-cover-clauses-train-120s-c87cf482a/out/` (named in `gold-v3-combined-cut/cover-harvest/design.md` line 10).
- A bank (`KIT/kaggle_worker.py` 62 to 74) holds `forms` (text, kind, depth, parent query ids) and `nodes` (types, `examples`, `parents`, `age` = the draw that made it); the `nodes` of a bank hold no rows (`KIT/kaggle_worker.py` 265). A pool record file also holds `x_rows` and `scope` (`KIT/superdag.py` 281 to 283).
- A pool keeps a record only for a draw that makes a new table. Other draws add to a counter only (`KIT/superdag.py` 249 to 261).
- A draw does not match a state with the files that exist. The states of a state sequence are not saved (`UN/gold_union_walks.py` 57 to 65). No file names the graph table of each table of a pool: `reach2.py` matches a pool table to a union table by equal `examples` (lines 9 to 13, 182) in memory. A pool state also holds tables that are no graph table.

## Settled

- Canonical text: as in "The canonical text".
- Target queries: the enabled queries. A query whose tables all equal built tables of the state makes no progress: it is not a target query, and its count per state is a measurement.
- States come from the state sequences of type `union`.
- A state that occurs in several state sequences is one row per distinct (task, set of `QueryHash`).
- The state sequences for training are made on the graph only, with the distinct-state and applicable columns. No replay.
- The draw match for a held-out evaluation is not built.
