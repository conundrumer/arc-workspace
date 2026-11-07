# Spec: a search over states

The state search is a best-first search over states, implemented in `model/study/sampler/state_search.py`. The objects are those of the [type contract](../sample-build/contract.md) and its [Terms](../sample-build/contract.md#terms), and this spec does not restate them. The contract comes first.

## Contract

The state search is a best-first search over states. It has two choices: the score of a state, and the writer's distribution over query bodies. Everything else is fixed by the types below. Each type gives the fields the state search keeps, and its invariants.

### Query, as the state search keeps it

- Fields:
  - QueryHash;
  - body;
  - kind;
  - inputs: Reference → Parameterized table, each given as (QueryHash, Name) of the query that computes it, or by a base table's name. The same notation writes each input inside the body for the QueryHash;
  - outputs: Name → Parameterized table;
  - bits: the writer's bits for the body;
  - vector: its QueryVector, computed from its input and output parameterized tables, and optionally from its body;
  - depth;
  - seconds and expansion: when it was first written, as wall seconds from the job's start and as the expansion count.
- Invariants:
  - One record per QueryHash. A query written again at another state is the same query.
  - depth is 1 + the greatest depth of the queries it takes inputs from. The base tables have depth 0.

### Parameterized table, as the state search keeps it

A parameterized table is named by (QueryHash, Name) of the query that computes it. The one output of a RULE or a DET is stored with Name as the empty string.

- Fields:
  - its name, and its Type;
  - its assignments: the Assignment over its parameters (the DETs it depends on), the first 256 in the engine's order;
  - per assignment: its TableHash, and a summary of its tables per ARC example: the count of tables, the largest table, and the hash of that ARC example's tables;
  - per assignment: its TableVector, a function of its tables there.
- Invariants:
  - A table has no assignment columns. The tables at an assignment are the value of the parameterized table there, and the DETs the parameterized table depends on are its parameters.
  - Constraint models are inside the set of tables at an assignment, never in the key.
  - A parameterized table is a function of its query, so one parameterized table serves every state that holds its query.
  - A DET's values are each a table of the DET's Type. A DET depends on itself, so its own parameterized table has one key per value.
  - Two queries whose parameterized tables have tables with equal TableHash give two parameterized tables. The TableHash is a measurement. It serves reach against the union graph, the table features, the acceptance test of a written query, and a prune where a score states one.
  - Each TableVector is computed once, when that parameterized table is first made at that assignment. Table rows are not kept after that.
  - A parameterized table whose assignments pass 256 is unreachable by the search, and its assignments are the first 256.
  - The build checks one point first: that a parameterized table's tables depend only on the DETs among its parameters, so that DETs outside them change nothing.

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
  - Every parameterized table of the state's queries, with its tables at each assignment, and the state's program in dependency order, are computed from the set and not stored.
  - child queries = parent queries ∪ {the written query}.

### State view

What the score sees of one state. It is read-only.

- Fields:
  - the state's queries: each with its QueryVector, kind, bits and depth, and the input edges between them;
  - their parameterized tables: each with the TableVector and TableHash at each of its assignments;
  - two flags on each parameterized table at an assignment, as measurements: its TableHash equals that of another parameterized table of the state, and its TableHash was seen earlier in the state search;
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

The writer, called once per expansion. It writes one query body at a state, never an assignment.

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
  4. Evaluate the query under the state, give it its QueryHash, and record its parameterized tables, each with its TableHash at each assignment.
  5. Make the child state, score it and push it.
  6. Run the OUT test once for a query not seen before, over the programs that end in its tables.
  7. Score the parent again, and push it back unless the score is none.
- Record fields:
  - the expansion count and seconds;
  - the state id and its score;
  - the QueryHash or none, with its kind and bits;
  - the outcome;
  - the child state id;
  - the measurement flags of the query's parameterized tables.
- The outcome takes one of four values:
  - new state: the child's query set is new;
  - known state: the child's query set exists already, as where two orders of the same queries meet;
  - no table: the query computes no parameterized table;
  - failed: the engine fails.
- Invariants:
  - An expansion writes one record.
  - Equal TableHashes give no outcome of their own. They are the two measurement flags.
  - A state's re-expansion is the score's choice. The state search has no patience, resume, slot or visit.

### Visited set

The states that the state search has computed, kept on disk with what rebuilds them.

- Fields:
  - queries by QueryHash;
  - parameterized tables by (QueryHash, Name), with the keys of their assignments, and the TableHash and TableVector at each assignment. A key is stored as the Assignment written as a sorted tuple of (DET QueryHash, value hash), a value hash being the engine's hash of the value's table with the DET's columns named, so two values that differ only by the order of their columns have two value hashes;
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
- Parameterized table: it maps Assignment to its set of tables. A DET's own parameterized table has one key per value. Constraint models are inside the set of tables.
- Acceptance test of a written query: at every assignment at which both parameterized tables are defined, each output's two TableHashes are equal; for a written DET, the sets of its values' TableHashes are equal, so a DET whose columns differ from the target's only in order passes. Credit is per parameterized table: a target parameterized table of g counts once, and f matches it when some output of f has its Type and an equal TableHash at every assignment the test covers. Names are not compared across queries, and a parameterized table that matches at only some assignments gets no credit. A target parameterized table whose own walk stopped at the 256 cap is left out and counted.
- Target query: its parameterized tables are taken at the state's assignments.
- Union graph: a parameterized table of one query stands for a parameterized table of another where their maps assignment → TableHash are equal, DETs of different QueryHash paired by equal sets of their values' TableHashes.
- Reach per depth: a union graph table is reached when a parameterized table of the state search has its TableHash. The denominators are per depth, over union graph tables.
- The build check: a parameterized table's tables depend only on the DETs among its parameters.

## Principles

- One identity per query (QueryHash) serves query dedupe, state equality and the visited set. One name per parameterized table, (QueryHash, Name), serves sharing across states. The parameters are the dedupe of assignments: two assignments that agree on the DETs a parameterized table depends on give one key. One measurement of values (TableHash) serves reach, features, the acceptance test and any stated prune. One evaluation path serves the state search and the gold seeding. One TableVector per table, made once.
- No wasted work:
  - A parameterized table is computed once and shared by every state that holds its query. A state holds only QueryHashes.
  - The program is replayed only when the popped state changes; else the kept decoder is forked.
  - The OUT test runs once per query, not once per state.
  - The frontier skips stale heap items and never rebuilds the heap.
  - Table rows are dropped once the TableVectors exist.
  - The visited set stores each state as parent plus one QueryHash.
- Extension points are the score, the TableVector function and the writer, each one module behind its type. The state search changes for none of them. The expansion record carries a schema version, so fields can be added.
