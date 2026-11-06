# Search kit: inputs beyond one table

Status: record of the features of one past kit. [Features map](../features-map.md) gives the current sources.

Each feature, pick input and search counter in round 1's kit (`kits/search-refit-r1-kit-0729e4943`, bundle and refit arms) whose input is more of the state than one table's own table and the task's pairs. `policy/` is the kit's policy folder; `sampler/` is `model/study/sampler/` of the kit.

The dependence column:

- T: its input is only the set of tables of the built queries and their dependencies (the use edges between queries).
- H: it depends on the pool's hand-set structure (openings, slots, visit kinds, renewal).

A table is scored once, when it is new. `Pool.merge` and a new query that uses the table call `policy.add` again (`sampler/superdag.py` 316 to 319 and 287 to 290), and `add` returns at once for a table it has scored (`policy/policy.py` 66, `policy/nodescore.py` 215). No later change to the state reaches a table's score.

## Score features: the policy model (`policy_model.pkl` 2ec93ed1)

| Feature | Input | Where | Dependence |
|---|---|---|---|
| depth | 1 + the greatest depth of the queries it takes inputs from, at creation. A merge lowers `node.depth` to the least depth (`superdag.py` 318); the score keeps the creation value | `superdag.py` 261, `nodefeat.py` 84 | T |
| n_parents | the count of the tables of the parent queries | `superdag.py` 279, `nodefeat.py` 84 | T |
| link_np | the count of those parent tables the policy has scored | `outfeat.py` 135 | T |
| link_parent_gain, link_adds, link_better, link_new_cells, link_new_count, link_pair_union, link_filter, link_grow, link_disjoint | the parents' paint state (gain, fixed cells, cell set), as kept when each parent was scored | `outfeat.py` 131 to 151, `policy.py` 61 to 62 | T |
| link_row_ratio | (rows + 1) / (greatest parent rows + 1) | `outfeat.py` 153 | T |

`kid_n`, `kid_best` and `kid_best_adds` (`outfeat.py` 156 to 170) are computed from the gains of the queries that use the table. They are not among the policy model's 87 names, and nothing calls them at run time.

## Score features: node-score-r1 (`node-score-r1.state.pkl` 975e4efb)

| Feature | Input | Where | Dependence |
|---|---|---|---|
| dp_form_depth | `form.depth`, as for depth above | `nodescore.py` 211 | T |
| dp_form_reads | `form.reads` = `len(run.reads)`, the count of atoms in the query's text that use a table or a lib relation | `nodescore.py` 31, `superdag.py` 271 | T |

`dp_kind` is the query's own kind. The other features are computed from the table's own table and the task's pairs (`FE.TaskCtx`, `nodescore.py` 169).

## Pick and context

| Item | Input | Where | Dependence |
|---|---|---|---|
| uses | the count of the table's earlier picks; the pick value is score − USES × uses | `policy.py` 45, 80, 86, 88, 90 | H |
| table id order | creation order: the least-used slot takes the least uses, then the oldest id. `Node.age` (the draw count) is stored, and the pick doesn't use it | `policy.py` 88, `superdag.py` 139 | H |
| Gumbel draw | the pool's rng, one draw per table per opening | `policy.py` 86 | H |
| Mix coin (refit arms) | per opening, a coin with chance `NODE_SCORE_MIX` picks the r1 score or the hand score; its rng is seeded by pool id and seed | `nodescore.py` 123 to 135, 198 | H |
| Context membership | the picks with all their ancestors by use edges, up to 96 queries, in depth order. Each new table's bank row stores the context it came from (`scope`); no score uses it | `superdag.py` 199 to 213, 283 | H for which tables, T for the closure |
| Kind weights | the kinds the decoder admits after the context's program, weighted by the global prior counts `kinds1` + 1 | `superdag.py` 196, 215 to 217; `superdag_search.py` 361 to 364 | H |
| n_readers | the count of later queries that use the table's query. Only `UniformPolicy` uses it (`superdag.py` 152) | `superdag.py` 141, 287 to 290 | T |
| n_clauses | the count of queries whose table merged into the table; the feature row fixes it at 1 (`policy.py` 54) | `superdag.py` 317 | T |

## Search state

| Item | Input | Where | Dependence |
|---|---|---|---|
| Slot | keyed by (context texts, kind); holds visits, tries, new tables, seconds, `last_rate` (new tables per second in the last visit) and `exhausted` | `superdag_search.py` 326 to 336 | H |
| Resume | with chance RESUME 0.3, the parked live slot with the most `last_rate` (ties: fewer visits); else a new pick | `superdag_search.py` 408 to 436 | H |
| Patience | misses in a row; 8 ends the visit. A miss is an equal, no-table or failed try | `superdag_search.py` 78, 488, 526 to 533 | H |
| Visit and query time | VISIT_SECONDS 4, CLAUSE_SECONDS 20 | `superdag_search.py` 79, 482, 491; `superdag.py` 55 | H |
| Best-first frontier | per slot, by the proposal's bits | `search.py`, through `superdag_search.py` 483 | H |
| TableHashes (pool membership) | whether a query's table is new or equal to a known one; this decides keep or drop, and an equal is a patience miss | `superdag.py` 194, 268 to 276 | T, reset by renewal (H) |
| Renewal | at RSS 0.6 of the limit the worker saves the bank and execs again. A renewal resets the TableHashes, so a known table can enter again as a new table | `kaggle_worker.py` 27, 151, 333 to 340 | H |
| Search manager | HOT 6, LIMIT_SHARE (0.65 in the run line), KEEP_COLD 2: which searches keep a run, by RSS | `superdag_search.py` 81 to 85 | H |
| Draw seed | sha1 of task, seed and the pool's draw count | `superdag.py` 225 | H |
| OUT test | programs that end in the new query's relations, over the context | `superdag.py` 321 to 333 | H through the context |
| Counters (`run.c`, visit events) | written to logs and events; nothing in the search uses them | throughout; the visit event at `superdag_search.py` 537 | none |

## Proposer steers

The rel and choice steers (on `models-tk`) are computed from the row fields `scope` (the context's column types), `prefix` (the atoms so far) and `point_group` (kind, depth, d_out). The rows are built at `sample2_col.py` 1935, 1957 and 2349; the hand weights `in_scope`, `in_scope_frac`, `none_in_scope` and `type_in_scope` are at `sample2_col.py` 217 to 224. Dependence: H, through the context and the visit kind.

## Off in round 1

`SEARCH_READ_SCOPE`, `SEARCH_NEW_TABLE` and `SEARCH_READ_PICK` are unset in the run line (`superdag_search.py` 96 to 98). Set, they use the pool's TableHashes and the picks (`superdag_search.py` 112 to 131, 217 to 221, 261 to 283). `FIRST_PASS_SECONDS` is 0.
