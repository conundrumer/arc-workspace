# Change spec: a search over states

Status: specification, not built. The objects (ColumnValue, Row, TableRows, Type, Table, parameterized table, constraint model, Assignment, TableHash, Query, Reference, Name, QueryHash, Program, solves, State, Model, union graph, applicable, target query, the acceptance test of a written query, state sequence, sample) are those of `work/redesign-proposal.md`, "The objects and the signature", and this spec doesn't restate them. It adds one term: a dependent query of a query takes one of that query's parameterized tables as an input. The inputs that the state search takes out of the pool search are listed in [state-features.md](state-features.md). The contract comes first; the file-level detail is under "Files and functions".

## Contract

The state search is a best-first search over states. It has two choices: the score of a state, and the Model's distribution over query bodies. Everything else is fixed by the types below. Each type gives the fields the state search keeps, and its invariants.

### Query, as the state search keeps it

- Fields:
  - QueryHash;
  - body;
  - kind;
  - inputs: Reference → Parameterized table, each given as (QueryHash, Name) of the query that computes it, or by a base table's name. The same notation writes each input inside the body for the QueryHash;
  - outputs: Name → Parameterized table;
  - bits: the Model's bits for the body;
  - vector: its QueryVector, computed from its input and output tables, and optionally from its body (the type is Features-worker's);
  - depth;
  - seconds and expansion: when it was first written, as wall seconds from the job's start and as the expansion count.
- Invariants:
  - One record per QueryHash. A query written again at another state is the same query.
  - depth is 1 + the greatest depth of the queries it takes inputs from. The base tables have depth 0.

### Parameterized table, as the state search keeps it

A parameterized table is named by (QueryHash, Name) of the query that computes it. The one output of a RULE or a DET is stored with Name as the empty string.

- Fields:
  - its name, and its Type;
  - its tables: Assignment → Table, the Assignment over its parameters (the DETs it depends on), the first 256 assignments in the engine's order;
  - per table: its TableHash, and a summary of its Set of TableRows grouped on the Example column: per example, the count of its TableRows, the largest TableRows, and the hash of that example's TableRows;
  - per table: its TableVector, a function of that table.
- Invariants:
  - A table has no assignment columns. A table is the value of its parameterized table at an assignment, and the DETs the parameterized table depends on are its parameters.
  - Constraint models are inside the Set of TableRows, never in the key.
  - A parameterized table is a function of its query, so one parameterized table serves every state that holds its query.
  - A DET's values are each a TableRows of the DET's Type. A DET depends on itself, so its own parameterized table has one key per value.
  - Two queries whose parameterized tables have tables with equal TableHash give two parameterized tables. The TableHash is a measurement. It serves reach against the union graph, the table features, the acceptance test of a written query, and a prune where a score states one.
  - Each TableVector is computed once, when that table is first made. Rows are not kept after that.
  - A parameterized table whose assignments pass 256 is unreachable by the search, and its tables are the first 256.
  - The build checks one point first: that a table's TableRows depend only on the DETs among its parameterized table's parameters, so that DETs outside them change nothing.

### State, as the state search keeps it

- Fields:
  - id;
  - queries: a Set of Query, as QueryHashes;
  - parent: a state id, and the QueryHash that led here;
  - depth: the greatest query depth;
  - bits: the sum of the bits of the queries on the way from the root;
  - expansions and children: counts.
- Invariants:
  - The query set is the whole identity. Two states are equal exactly when their sets are equal.
  - Closed under inputs: each query of the state takes inputs only from base tables or from other queries of the state.
  - The root state is the empty set. The base tables are in every state, and the lib is in no state.
  - Every parameterized table of the state's queries, with its tables, and the state's program in dependency order, are computed from the set and not stored.
  - child queries = parent queries ∪ {the written query}.

### State view

What the score sees of one state. It is read-only.

- Fields:
  - the state's queries: each with its QueryVector, kind, bits and depth, and the input edges between them;
  - their parameterized tables: each with the TableVector and TableHash of each of its tables;
  - two flags on each table, as measurements: its TableHash equals that of another table of the state, and its TableHash was seen earlier in the state search;
  - the state's depth, bits, expansions and children;
  - the task's base tables.
- Invariants:
  - The score's input is the set of QueryVectors with the input edges. The other fields are there for a score that states a use of them.
  - It shows nothing else of other states. A score that wants more keeps it itself.

### Score

A function from a state view to a number, or to none.

- A higher number goes first. None closes the state.
- The state search scores a state when the state is made, and again after each expansion of it.
- It is pluggable by setting, as one module. The same module may give the TableVector function.
- Any prune by equal TableHash is the score's, stated as its policy. The state search itself prunes nothing by table equality.
- A default ships for a control arm: −bits − expansions.

### Frontier

The open states, ordered by score.

- Fields:
  - heap items of (score, state id, version);
  - the open set;
  - the map from query set to state id.
- Invariants:
  - Each open state has one live heap item. A new score raises the state's version, and a heap item whose version is old is skipped when it comes up. The heap is never rebuilt.
  - On equal scores, the lower state id goes first.
  - A closed state has no live heap item.
  - The frontier is bounded by memory. The time limit and the query cap end the state search.

### Writer

The Model, called once per expansion. It writes one query body at a state, never an assignment.

- Takes:
  - the decoder at the end of the state's program, and the program's names and parameterized tables;
  - the state view;
  - a random source, seeded by task, seed and expansion count;
  - a deadline.
- Gives: the decoder at the body's end, the body, its kind and its bits; or nothing, where it writes no query.
- Invariants:
  - Every token it writes is in the decoder's mask. The mask holds one token per parameterized table of the state, whatever the assignments, so the query's inputs are parameterized tables of the state, and two parameterized tables whose tables have equal TableHash are two tokens.
  - The kind token is the writer's own choice.
  - The same inputs and the same random state give the same body.
- A writing point is a state plus the tokens of the open body. The distribution over tokens at a writing point is the writer's pluggable part (the token-level writer spec).

### Expansion

One step of the state search.

- Order:
  1. Pop the state with the highest score.
  2. Get its decoder. Where the last expansion was of the same state, fork the kept decoder; else replay the state's program in the engine.
  3. Call the writer.
  4. Evaluate the query under the state, give it its QueryHash, and record its parameterized tables, each with its tables and their TableHashes.
  5. Make the child state, score it and push it.
  6. Run the OUT test once for a query not seen before, over the programs that end in its tables.
  7. Score the parent again, and push it back unless the score is none.
- Record fields:
  - the expansion count and seconds;
  - the state id and its score;
  - the QueryHash or none, with its kind and bits;
  - the outcome;
  - the child state id;
  - the measurement flags of the query's tables.
- The outcome takes one of four values:
  - new state: the child's query set is new;
  - known state: the child's query set exists already, as where two orders of the same queries meet;
  - no table: the query computes no parameterized table;
  - failed: the engine fails.
- Invariants:
  - An expansion writes one record.
  - Equal tables give no outcome of their own. They are the two measurement flags.
  - A state's re-expansion is the score's choice. The state search has no patience, resume, slot or visit.

### Visited set

The states that the state search has computed, kept on disk with what rebuilds them.

- Fields:
  - queries by QueryHash;
  - parameterized tables by (QueryHash, Name), with the keys of their assignments, and the TableHash and TableVector of each table. A key is stored as the Assignment written as a sorted tuple of (DET QueryHash, value hash), a value hash being the engine's hash of the value's TableRows with the DET's columns named, so two values that differ only by the order of their columns have two value hashes;
  - states, as parent plus one QueryHash each;
  - the frontier;
  - the expansion count;
  - the candidates found;
  - the generation, and the lineage of processes.
- Streams beside it: the expansion records (one line each), the cover events and the OUT candidates.
- Invariants:
  - Renewal resets nothing. A process that starts from the visited set has the same queries, parameterized tables, states and frontier. A query it writes again has its known QueryHash.
  - The expansion records rebuild every state: a state's queries are its parent's plus the record's QueryHash.

### Where assignments appear

- State: a state holds queries. Its parameterized tables are computed from them, each keyed by Assignment over its parameters, the DETs it depends on.
- Parameterized table: it maps Assignment to Table, a Set of TableRows. A DET's own parameterized table has one key per value. Constraint models are inside the Set of TableRows.
- Acceptance test of a written query: at every assignment at which both parameterized tables are defined, each output's two TableHashes are equal; for a written DET, the sets of its values' TableHashes are equal, so a DET whose columns differ from the target's only in order passes. Credit is per parameterized table: a target parameterized table of g counts once, and f matches it when some output of f has its Type and an equal TableHash at every assignment the test covers. Names are not compared across queries, and a parameterized table that matches at only some assignments gets no credit. A target parameterized table whose own walk stopped at the 256 cap is left out and counted.
- Target query: its tables are those of its parameterized tables at the state's assignments.
- Union graph: a parameterized table of one query stands for a parameterized table of another where their maps assignment → TableHash are equal, DETs of different QueryHash paired by equal sets of their values' TableHashes.
- Reach per depth: a union graph table is reached when a table of the state search has its TableHash. The denominators are per depth, over union graph tables.
- The build check: a table's TableRows depend only on the DETs among its parameterized table's parameters.

## Principles

- One identity per query (QueryHash) serves query dedupe, state equality and the visited set. One name per parameterized table, (QueryHash, Name), serves sharing across states. The parameters are the dedupe of assignments: two assignments that agree on the DETs a parameterized table depends on give one key. One measurement of values (TableHash) serves reach, features, the acceptance test and any stated prune. One evaluation path serves the state search and the gold seeding. One TableVector per table, made once.
- No wasted work:
  - A parameterized table is computed once and shared by every state that holds its query. A state holds only QueryHashes.
  - The program is replayed only when the popped state changes; else the kept decoder is forked.
  - The OUT test runs once per query, not once per state.
  - The frontier skips stale heap items and never rebuilds the heap.
  - Rows are dropped once the TableVectors exist.
  - The visited set stores each state as parent plus one QueryHash.
- Extension points are the score, the TableVector function and the writer, each one module behind its type. The state search changes for none of them. The expansion record carries a schema version, so fields can be added.

## Where Rust could take a part

The engine is Rust behind Python bindings. Each part below could move into it.

- The TableHash, and the TableVector over rows:
  - Now a table goes out to Python as rows (step_tables, 4 to 6 ms on the Mac) and is hashed there. The hash's worst case at its cell bound is 0.21 s.
  - In the engine, the hash and the vector would be made where the rows are, and no rows would cross to Python.
  - This also lifts the vector's limit at tables the engine exports as counts (over 10,000 rows in one TableRows).
  - It changes the binding interface, and the vector function then has to be written in Rust or given to the engine as a fixed set.
- A state's decoder:
  - Now a state is replayed from its bodies when it is popped, and the session cache makes known queries cheap.
  - In the engine, a state could hold a decoder snapshot by state id, and a pop would be a fork with no replay.
  - This costs memory per kept snapshot, so it needs a bound and an eviction rule, and the visited set can't store snapshots.
- The writer's token loop:
  - Each token now costs a Python-to-engine call: admits about 0.31 ms, step 0.14 to 0.26 ms.
  - A loop in the engine with the distribution as a callback, or with the Model run by the engine, would cut the per-token crossings.
  - A learned distribution in Python would then be called from Rust per token. A batch of tokens per call is the way to keep the crossings low.
- The frontier and the state set: they are small in Python and cheap per expansion. Rust gives nothing here until expansions per second rise by a large factor.

## Files and functions

File and line refer to `model/study/sampler/` of round 1's kit (`kits/search-refit-r1-kit-0729e4943`) unless named. In the code, a query is a `Form` and a computed table is a `Node` object. A `Node` becomes a parameterized table, named by (QueryHash, Name) in place of its TableHash, with a table per assignment. The QueryHash, the parameterized table, the state and the expansion record are new.

`superdag.py` (444 lines):

- Stay: `rss_mib`, `OneTable`, `relation_tables`, `table_key` (60 to 115); `Run` (159 to 188); `session_of`, `gold_keys` (361 to 389); `Pool.seed` (293 to 315); `Pool.test` (321 to 333).
- Change:
  - `Form` and `Node` (117 to 143): `Form` gets the QueryHash, `bits`, `seconds`, `expansion` and the QueryVector; `Node` gets its name, the keys of its assignments and a TableVector per table; `age`, `n_clauses` and `n_readers` go.
  - `Pool.__init__` (190 to 198): the policy and `kinds` go; `states`, `frontier` and the score module come in.
  - `Pool.take` (239 to 264): it records each parameterized table with its tables and their TableHashes, and drops no query. Today it drops a query whose tables all match known hashes, and that drop goes. `Pool.keys` becomes a measurement map from TableHash to the tables that have it.
  - `Pool.add_form` (266 to 291): the `policy.add` calls and the `n_readers` count go; the TableVector comes in.
  - `one_task`, `main` (390 to 444): no policy.
  - About 60 lines change.
- Go: `Pool.merge` (316 to 319), which today carries a dropped query's depth and count onto the `Node` of its TableHash; `UniformPolicy` (145 to 157), `Pool.scope` (199 to 213), `Pool.kind` (215 to 217), `Pool.draw` (219 to 237), `Pool.grow` (334 to 350) and `make_policy` (352 to 359). About 90 lines.

`superdag_search.py` (748 lines):

- Stay, moved to the new module: `table_key` and `prefix_key` (224 to 260), as the TableHash, `is_panic` and the panic guard (286 to 298), and the take-and-test core of `try_clause` (439 to 476). About 90 lines.
- Go: everything else. That is `patch_search_run` with its stop gates (106 to 195), `shift_bound`, `reads_pick` and `table_known` (197 to 283), `guard_saves` (300 to 322), `Slot`, `add_delta` and `pool_init` (325 to 359), `kind_of`, `picked_scope`, `oracle_targets` and `next_slot` (361 to 436), `visit`, `grow_search`, `first_pass` and `grow_first` (478 to 625), and `attach`, `after_bank`, `read_slots`, `install`, `load_rule` and `main` (635 to 748). About 650 lines. With them goes the search manager's role in the pool search (`live.Sampler.search`, `live.py` 603; `search.py`). `search.py` stays in the kit for other users, off this path.

`kaggle_worker.py` (347 lines):

- Stay: `rss_mib`, `mac_footprint`, `compression`, `recorder`, `renew`, `store_of`, the heartbeat, the RSS stop and the save cycle.
- Change:
  - `write_bank` and `read_bank` (62 to 93): the visited set (queries, parameterized tables, `states`, `frontier`) in, `policy` out; `read_bank` restores it.
  - `source` (160 to 175): it installs the state search.
  - `main` (182 to 347): the policy, `--k` and `--draws-per-scope` go; the `.picks` and `.visits` writers become the states log writer; the `picks1` lineage count goes.
  - About 45 lines change.

New: `state_search.py`, about 250 to 350 lines: the QueryHash from the engine's canonical hash; the parameterized table; `State`; the frontier; `expand`; the state view; the score module loader and the default score; the TableVector call; the expansion records; the visited-set hooks on the bank file; `install`, so that `kaggle_worker.source` keeps its shape.

Engine: the table export writes each parameterized table, one export row per table, holding that Set of TableRows, with Example a column of each Row and no assignment columns (`arclog-tables` `columns.rs` 1439 to 1463, `assignment_context.rs` 71 to 90). Evaluation is per joint assignment already, so evaluation is unchanged. The union graph's tables, the ramp and 37 maps, the outmap and the graph are exported and built again once, after that change.

`policy/` leaves the search path. Its feature functions stay as the starting table vectors.

The writer is a new module on sampler-worker's side. The search's interface to it is `write(dec, pg, view, rng, deadline) -> (decoder at the body's end, bits) or None`. Until it exists, an adapter over `live.Run.form` (`live.py` 819) can serve, with the kind drawn uniformly from the kinds `dec.admits` allows, so that the loop can be tested end to end.

## What breaks

The kit has no unit tests for the search path. What breaks is its run checks, its run lines, and the scripts that read its output files.

- The refit check (`refit-check.json`): the parity jobs (`NODE_SCORE_CHECK`, which compares picks) and the refit check job have no policy to check.
- The run lines (`run3600.sh`, the jobs files): `POOL_CLAUSES=search`, `ARC_POLICY`, `POLICY_MODEL`, `NODE_SCORE*`, `SEARCH_*`, `--k` and `--draws-per-scope` go, and `SEARCH_STATE_SCORE` and the writer's settings come in.
- The sixty-pass gate keeps working: it counts gold tables covered from the `.cover` events, which stay.
- Scripts that read `.picks` (the draw-to-time mapping in the reach rows, `P.kept_picks`, the scope-loss replay, the pick-value replay), of `.visits` (miss rate per head depth, context members) and of `.slots`: none of these files exists. The reach rows take time from the nodes' `seconds` instead. The miss-rate measure becomes a count over the expansion records: graph queries whose input tables were all in one state, by expansions of that state.
- Scripts that read `bank['policy']` (scores, uses): it's gone.
- Scripts that import `superdag_search` (`search-worker/search_prefix_*.py`, `seed_bank.py`, `search_refit_build.py`, `search_two_stage_job.py`, among others), and the features-worker builds over pool runs (`poolrun.py`, `features_node_rebuild.py`, `flat_common.py`): they run against an old kit or are rebuilt.
- Node and query counts per job change meaning: a query whose tables equal known ones is kept, as its own query with its own parameterized tables, and a `Node` holds one parameterized table. So counts by `Node` no longer count distinct values. A count of distinct values goes by TableHash.
- The node-score, M-T and M-H fits take a pool node, a class of equal TableHashes, as their unit. That unit doesn't carry into this contract, where the unit is a table.
