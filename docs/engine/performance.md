# Performance

The design decisions whose cost the engine pays on every candidate program of a synthesis loop and on every case of a solver, and the proposals that bound that cost. A decision here is part of the language or of the engine's semantics, and the scope docs build on it. How the scope docs implement a decision, such as the join algorithm, the form of an index, the hash and the thread pool, is provisional until the engine is written and a benchmark measures it.

Each entry gives its evidence, or says that it is provisional.

## Decisions with a cost

### Deferred projection

- A clause has no head: every variable of its body is a column of its relation, and a later read selects the columns it needs, as [Clause](../../docs/arclog/arclog.md#clause) gives.
- **Cost:** a relation keeps every binding of its body's variables, where a head would keep only the distinct rows of the columns its readers need. A relation can hold many more rows than any of its reads, and its width is the count of its labels.
- **Evidence:** most reads of a derived relation in `gen/` project, as [Columns](corpus-survey.md#columns) gives, so most relations carry columns that no reader reads. How many more rows that gives is not measured.
- **Proposal, provisional:** a relation is held in the factorized form of [Factorized bodies](synthesis.md#factorized-bodies), its parts each deduplicated, and a read projects the parts it reads. In a solver, every reader is known, so a relation also keeps only the columns some reader reads. In a decode, the readers are not known yet, so that projection waits until the relation is read.

### One program per case

- Each case is its own program, with no `Choice` column, as [Cases](cases.md#cases) gives.
- **Cost:** a solver costs its case count times one case, less what the result cache shares.
- **Evidence:** some solvers have many cases, as [Alts structure](corpus-survey.md#alts-structure) gives, and on one input of one solver the rows of a `parse.copy` relation hold far fewer distinct contents, as [Causes of the outliers](outliers.md#causes-of-the-outliers) gives, so the cases' relations often hold the same rows.
- **Proposal, provisional:** relations are hash-consed. Each relation gets the id of the hash of its rows when it is made, an entry's key is its clause with the ids of the relations it reads. So the cases whose relations hold the same rows on an input share every entry downstream of those relations, and a lookup costs no hash of rows.

### Sets, not bags

- A relation is a set of rows.
- **Cost:** each relation is deduplicated as it is made.
- **Evidence:** none measured. The language's semantics needs sets: `ONE`, `ALL` and the solves test read set membership.

### Canonical form per body

- Two bodies equal up to the order of their atoms and the names of their labels are one value, as [Programs as values](reader.md#programs-as-values) gives.
- **Cost:** a canonical labeling at each edit.
- **Evidence:** in `gen/`, refinement alone settles nearly every body, and the search stays small, as [Body symmetry](corpus-survey.md#body-symmetry) gives. Synthesized bodies are not measured.

### Checks on every prefix

- The token mask runs every check on each partial program, as [Checker](reader.md#checker) gives.
- **Cost:** a check per token for each token that may come next.
- **Evidence:** none measured. The check cache serves a form shared by cases or candidate programs once.

### The grid columns at each clause's end

- Where the rule tests of [Decode settings](synthesis.md#decode-settings) are on, the engine tests each `RULE` relation's pairs of a Position column and a Color column against the train outputs. With them off, the default, no `RULE` end runs it, and an `OUT` form reads its two columns with no search.
- **Cost:** with the rule tests on, one test per pair of such columns per clause, each over the relation's rows on every train example.
- **Evidence:** none measured.

### Models of `ONE`, `CHOOSE` and `DEMONSTRATED`, and determination by the train pairs

- A case's output is one grid per model, and a parameter whose `DET`'s domain holds several values is filtered by running the cases at each assignment, as [Models](cases.md#models) and [`DET`](determination.md#det) give.
- **Cost:** a product of models or of assignments, each a run of the entries downstream of the choice.
- **Evidence:** on the corpus, propagation alone solves every pick, and the products of the determination plans stay under the old tooling's limit, which shaped them, as [`DET` domains](corpus-survey.md#det-domains) gives.

### No recursion

- Closures come from lib components, and a program's relations form a DAG, as [Program](../../docs/arclog/arclog.md#program) gives.
- **Cost:** none past the components': each relation is evaluated once, with no fixpoint.

## Proposals for the synthesis loop

Each of these is provisional.

- **Target.** The engine's work per token stays below the language model's time per token, so a decode waits on the language model and not on the engine. The benchmark decodes every case program of `gen/` as a token stream and records the engine's time per token. The target is set when the language model and its decode rate are chosen.
- **Indexes of new relations.** Each candidate program's new relation is new, so a join's trie over it is built again at each step. An index over a relation that extends an indexed one by a semi-join can be built from the parent's.
- **The Python boundary.** The batch form, which steps many decodes in one call, is the main path, since a call per token per decode across pyo3 can cost more than the engine's work on that token.
- **Variants at once.** A search over the lattice of a clause's bodies, which removing atoms gives, can hold its variants at once, as the tagged form holds the assignments: each row of the most general body, the body without its optional atoms, carries in an added column the set of optional atoms it satisfies, and it holds under each variant whose optional atoms lie in that set. The rows carry the most general body's columns, which are the columns of each variant only where no optional atom binds a fresh label. The most general body must be safe, and its rows run under the row cap, as every body's do. It is built once a decode shows a need: no decode has measured whether asking for many variants at once finds a solution sooner than asking for each through the result cache.
