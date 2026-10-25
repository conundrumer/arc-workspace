# Table rows and the information they carry

What the rows of the feature encoder's tables are, how many a table holds at each cut the encoder and the engine have taken, and how much information a row carries. The reader is a session that works on table size: in the encoder, in the lib, or in a solver. [encoder-large-tables.md](encoder-large-tables.md) gives the table cap this work serves and why it exists; [feature-encoder.md](feature-encoder.md) gives the encoder.

## Basis

Every number below is from the tables export `work/tables/full-7ae65ed2/`, all cases: 930 tasks, 6,652 cases, 293,724 derived tables. The export has the `connected` cut (C20-60) and the engine's projection cap of 10,000 rows per entry. Evidence tables, faulted tables and tables whose projection search stopped are left out.

A table's rows are what the encoder counts: an entry under the projection cap counts its rows, and an entry over it counts the rows of its maximal projections. Attention cost is the square of a table's rows, and the table cap is 4,000 rows.

The reads of each relation come from each case's token stream, through `arclog.corpus_streams`: a model-written relation token is a read, and the column tokens of its sites are the columns read. In an `INIT`, `CHOOSE` or `RIGID_DET` form, a read of a per-input relation puts the Example column at position 0, and a read of an instance relation whose key was skipped puts the key at the first position, so those positions are dropped. 2,398 tables, 0.8%, still had a read position outside their columns, and that position was ignored.

The scripts are under [table-information/](../work/table-information/): `pertable.py` builds the per-table rows at each stage and writes `pertable_split.parquet` and `pertable_whole.parquet`; `tail.py`, `snr.py`, `factor.py` and `ports.py` read them. They run with `work/lm/.venv/bin/python`.

## Rows per table at each stage

Each stage includes the ones before it. Stage 2 is in the encoder (`lm/encoder.py`, one table per assignment). Stage 3 is the engine's one-atom input cut, C20-73, which keeps an input whose atom reads a lib relation. Stages 4 and 5 assume knowledge of every later read, which a live decode does not have, so they are ceilings.

| stage | tables | median | p90 | p99 | max | >1k | >2k | >4k | >8k | >16k | cases with a table >4k |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1. one table per relation | 293,724 | 30 | 950 | 12,467 | 903,024 | 9.7% | 5.5% | 3.25% | 1.57% | 0.72% | 48.5% |
| 2. one table per assignment | 820,021 | 8 | 462 | 4,694 | 139,105 | 5.7% | 3.1% | 1.25% | 0.54% | 0.17% | 34.4% |
| 3. minus one-atom inputs | 734,721 | 8 | 480 | 5,010 | 139,105 | 6.0% | 3.3% | 1.27% | 0.58% | 0.18% | 33.5% |
| 4. clause tables projected onto read columns | 734,721 | 6 | 394 | 4,088 | 128,092 | 5.3% | 2.9% | 1.03% | 0.43% | 0.11% | 32.4% |
| 5. instance outputs projected too | 734,721 | 6 | 388 | 3,986 | 128,092 | 5.2% | 2.8% | 0.99% | 0.41% | 0.09% | 31.3% |

The split per assignment is the move that changes the tail: a relation with several assignments becomes several tables, each under its own cap. The count of tables over 4,000 barely moves between stages 1 and 2 because each large relation splits into several large tables.

Tables over 4,000 by what the table is:

| kind | stage 1 | stage 2 | stage 3 | stage 4 | stage 5 |
| --- | --- | --- | --- | --- | --- |
| RULE clause | 3,429 | 4,667 | 4,667 | 3,016 | 3,016 |
| instance input, two or more conjuncts | 1,372 | 2,360 | 2,360 | 2,360 | 2,360 |
| instance output | 1,975 | 1,777 | 1,777 | 1,777 | 1,532 |
| instance input, one atom | 1,114 | 932 | 0 | 0 | 0 |
| `&output` | 1,368 | 286 | 286 | 286 | 286 |
| DET clause | 260 | 229 | 229 | 78 | 78 |

The RULE tables still over 4,000 after projection lose nothing to it: their readers read every column.

Rows and attention cost at each stage, under the 4,000 cap and without it:

| stage | rows | rows seen | attention cost, seen tables | attention cost, no cap | tables unseen |
| --- | --- | --- | --- | --- | --- |
| 1 | 240.8 M | 26.5% | 9.3e10 | 2.6e13 | 9,537 |
| 2 | 240.8 M | 51.9% | 1.7e11 | 3.3e12 | 10,270 |
| 3 | 223.2 M | 51.4% | 1.6e11 | 3.1e12 | 9,338 |
| 4 | 180.9 M | 58.2% | 1.5e11 | 1.8e12 | 7,536 |
| 5 | 175.5 M | 59.6% | 1.5e11 | 1.6e12 | 7,291 |

The tables over 4,000 hold 57% of the rows of the tables over 1,000, 87% of their uncapped attention cost, and about 60% of their information by the measure below. Information grows with rows and cost with rows squared, which is why the cap pays and why cuts that keep every bit and shrink rows are free.

### The export at f8dd701d

`work/tables/full-f8dd701d/` has every landed cut: `connected` out of the lib (C20-62), the one-atom input cut (C20-73), `adjacent` and `predecessor` out of the tables (C20-76), and the table work cap of 2²⁰ bindings (C20-63), which may stop a table short. 961 tasks, 6,756 cases, 257,585 derived tables with rows. Reads come from the streams export at the same master, `work/lm/data-full-f8dd701d`. Tables of cases with no stream there count in the distribution with no kind. Stage 2 equals stage 1 here, since the engine has the cut.

| stage | tables | median | p90 | p99 | max | >1k | >2k | >4k | >8k | >16k | cases with a table >4k |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1. one table per relation | 257,585 | 25 | 876 | 12,744 | 555,684 | 9.0% | 5.2% | 3.09% | 1.61% | 0.70% | 47.3% |
| 2. one table per assignment, as the encoder reads | 818,167 | 6 | 384 | 3,600 | 86,308 | 4.9% | 2.5% | 0.82% | 0.29% | 0.08% | 33.8% |
| 4. clause tables projected, a ceiling | 818,167 | 5 | 334 | 3,422 | 86,308 | 4.5% | 2.3% | 0.69% | 0.24% | 0.05% | 31.5% |
| 5. instance outputs projected too, a ceiling | 818,167 | 5 | 332 | 3,422 | 86,308 | 4.4% | 2.3% | 0.67% | 0.23% | 0.05% | 30.5% |

The tables over 4,000 as the encoder reads them: RULE clauses 3,196, instance outputs 1,554, instance inputs 1,298, `&output` 214, DET clauses 171, and 268 with no stream.

## Information per row

For each per-assignment table over 1,000 rows at stage 5, on its largest entry that holds rows (15,240 tables, which hold 74% of all rows): the key is the fewest columns that determine a row, and the key's domain is the product of the distinct values each key column holds. Two bounds per row:

- lower: log₂(domain ÷ rows), the bits to say which key tuples are present given the value sets;
- upper: the lower bound plus log₂ of the distinct count of each non-key column, as if nothing determined those values.

A table is a cross product when its rows are at least 90% of the key's domain, a function when its key is one column of several, sparse when its rows are under 10% of the domain, and dense otherwise.

| class | share of rows | share of attention cost | bits per row, lower / upper | share of bits (upper) |
| --- | --- | --- | --- | --- |
| cross product of its key columns | 39% | 43% | 0.0 / 0.1 | 26% |
| function of one column | 15% | 7% | 0.0 / 2.8 | 10% |
| dense relation on its key | 23% | 23% | 1.1 / 5.8 | 33% |
| sparse relation on its key | 24% | 27% | 5.3 / 6.9 | 32% |

Rows-weighted, a row carries 1.6 bits by the lower bound and 5.7 by the upper, in 3.5 columns. Two thirds of the rows sit in tables under 1 bit per row by the lower bound, a quarter by the upper.

The measure has a blind spot: it rates a table against its own value sets, not against the grid and the program. A set of cells keyed by one column scores 0 bits though which cells it holds is information relative to the grid, and a table that repeats another table scores whatever that table scores. The cross-product class is overstated for the same reason: tables that are exactly a product of their factors, where the factors replace the rows, cut only 10% of the rows of the tables over 1,000 (52.0 M to 46.7 M, `factor.py`); most of the class is sets of cells with attributes.

## What the large tables are

By kind, among the tables over 4,000 at stage 5:

- RULE clauses, 3,016. Two columns, almost always a cell pair, determine the row in 85% of them, and each cell pairs with about 4 others. The other columns are functions of the pair, computed by lib relations in the body: `axis_of` in 885 bodies, `margin` 480, `compose` 333, `same_line` 276. The information is the pair set.
- Instance inputs of two or more conjuncts, 2,360. Propagation.edge 892, Ray.node 355, Distance.edge 325, Agreement.correspondence 126, Order.before 120. No later atom reads an input.
- Instance outputs, 1,532. Flood.reached 315, Connectivity.adjacent 291, Ray.ray 225. Flood.reached is read in 58% of these tables, Ray.ray in 69%, Connectivity.adjacent in none.

Instance outputs are 19.6% of all rows, and 11.4% are in outputs no later atom of the case reads. Each instance declares 2.3 ports with a table on average and reads 0.78 of them; 73% of instances read exactly one. Connectivity.adjacent and CellDistance.predecessor are read in no case (3.9% of rows), and are no longer tables as of C20-76.

Input ports by rows: Propagation.edge 4.8%, Ray.node 2.3%, Cardinality.member 1.3%, Distance.edge 1.3%, Agreement.correspondence 1.0%, Order.before 0.7%, Quotient.equivalent 0.6%.

Nine tasks hold half of the tables over 4,000 and 65% of the uncapped attention cost; twenty hold 70% of the tables. Their largest relations at the stored parameters of the concept case, rows summed over inputs:

| task | largest relations | what it is |
| --- | --- | --- |
| a32d8b75 | `&output` 2,702,700; `&region.connected` 50,976; `&panels_part_of` 14,100 | the output clause's body is a product; DividerTiles ports |
| c663677b | `&shift_vote` 227,484; `&shift_mode.cyclic_successor` 184,963; `&shift_place` 151,632 | shift candidates × cells, then Mode and Order over them |
| a09f6c25 | `&mirror.correspondence` 34,016; `&conn4.connected` 7,101 | Agreement's correspondence as cell pairs |
| b10624e5 | `&scaled` 17,568; `&lone_idx` 14,310; `&quad_part_idx` 8,424 | scaled cell pairs; DividerTiles ports |
| a47bf94d | `&walk.edge` 12,680 | the grid's adjacency inside a node set, as Distance's `edge` |
| ac0c5833 | `&side` 11,288; `&line.ray` 4,080 | cell pairs by side; Ray cells |
| c62e2108 | `&march.node` 5,948 = `&march_cell` 5,948 | a Ray node input restating a relation |
| b2862040 | `&own_open8.node` 4,326 = `&own4.cell` = `&off_wall` 4,326 | one cell set restated as three inputs |
| bae5c565 | `&same_column` 4,257 | cells in the same column, as pairs |

At the gold assignment of the concept case most of these are not large; they top the count because they have many cases and many assignments, each of which repeats the table. a32d8b75 and c663677b are large in any single assignment.

### Idioms with zero information per row

Ways a solver spells out a structure whose every row the grid or another table implies. Sites are counted once per form in `work/arclog/gen`, `ALTS` branches included.

| input | how the site writes it | sites | the form that carries the same information |
| --- | --- | --- | --- |
| Distance.edge, Propagation.edge | the grid's adjacency inside a node set: `occluder(Q), dir_elem(D), neighbor(Q, D, Q2), occluder(Q2)` | 41 | CellDistance and Flood, the lib's cell instances of Distance and Propagation: n rows of Box in place of 4n rows of Box×Box |
| Propagation.edge | every pair with `N2 < N`, then closed | 1 | Order's score form, which materializes no pairs |
| Propagation.edge | Distance's `predecessor` joined to a key | 3 | the composition as written; a one-atom `edge` has no table since 20-73, and a path output on Distance would name a composition, which [lib-spec.md](lib-spec.md) forbids |
| Ray.node | a guard with no variable, times `input` | 22 | `input` alone, which 20-73 cuts: when the guard fails, `dir` is empty and the ray casts nothing |
| Ray.node | one atom | 87 | no table, since 20-73 |
| Agreement.correspondence | `apply` of a D4 element over cell pairs | 42 | a `transform` input holding the D4 element, as Occurrences has; not in the lib |

The lib-spec principle that covers these: Order takes a score in place of the pairs it induces, Quotient takes a generating `edge` beside `equivalent`, and Flood and CellDistance are Propagation and Distance over the grid's own steps. In each, the construction takes the generator of a pair relation rather than its expansion, and the generator is the lower level, so the spec's rule against naming compositions holds. The generalization: a construction that takes a relation over pairs of its members offers a form that takes the generator, where the generator is a value the solver already has, a score, a step, or a transform. Agreement's `transform` is the one missing instance in the corpus. A frame default for Ray's `node` is not one: the spec's defaults are steps, directions and the D4 identity, and the default would hide a claim for 22 tables.

All but the Agreement row are sites not using a form the lib has, which the spec's lint rule already names: a site that writes out a cell instance the lib holds is a reimplementation.

## Derivability tests

The lower and upper bounds above are deterministic and cheap, about rows × 2^columns with early exit. The quantity that matters is conditional: the information in a table given the tables already shown, the grid and the lib. In the limit that is the shortest clause that reproduces the table from what precedes it, which is program synthesis itself. A finite version is a fixed set of derivability tests, each cheap, each with a cost for the table it derives:

- the table equals another table, or a projection of one;
- the table is the product of its projections onto a partition of its columns;
- the table is the closure of a step relation inside a node set;
- the table is a rank or a class membership written as pairs.

A table's information is the cost of the cheapest test that derives it plus its exceptions. The tests are the same forms as the compact representations, so a test that passes names the rewrite.

Uses, beside the lint below: a feature for the encoder, key size, fill and bits per row per table, attached before the model attends over the rows; and a prior for synthesis, since the gold programs keep a table's information roughly proportional to its size, and a decode that produces a zero-bit table of 50,000 rows has taken a step a gold author would not.

### The lint

The lint runs the tests on a solver's relations and prints, for each relation over a row threshold, the test that derives it and the rewrite that test names. Its input is the solver's rows at the stored parameters of the concept case, which `arclog-cli row-counts --rows` dumps per relation and input, and the solver's source. Each line is a row count with a reason, and the reason is the instruction an agent acts on.

| test | what passes it | the rewrite it names |
| --- | --- | --- |
| restatement | the rows equal another relation's, or a projection of one; for an instance input, its body reads that relation | read the relation where the table was read; an input of one atom |
| cell instance | an `edge` of Distance or Propagation whose body is the grid's adjacency inside a node set | CellDistance or Flood |
| product | the rows are the product of the projections onto a partition of the columns; for an input, a guard with no variable times a domain | the factors; for a guard, the input it binds or nothing |
| closure | the rows are the closure of a step relation inside a node set | Flood or Connectivity |
| order or class as pairs | the key is a pair, and the rows are the pairs some column orders, or an equivalence's pairs | Order's score form; Quotient's `edge` |
| lib relation per pair | the rows are a lib relation, `same_line`, `neighbor`, `apply`, restricted to a cell set | the lib relation at the reading site; for Agreement, its `transform` form once the lib has it |
| none | | a residual: the rewrite is the solver's, and the line gives the rows, the key and the bits per row |

A line names the solver, the relation, its rows per input, the test and the rewrite. An agent's brief is the solver's lines; its acceptance is that the solver still passes its pairs, that each line's relation has fewer rows or no table, and that no new line over the threshold appears. The row counts before and after are the measure, from the same `row-counts` call.

The counts in hand, which are the first briefs: 41 sites for the cell-instance test, 1 for order as pairs, 22 guards on Ray's `node`, and the 42 Agreement sites once the `transform` form exists. The pair relations in the nine tasks of [What the large tables are](#what-the-large-tables-are) fall under the tests too: a32d8b75's output body is a product, c663677b's votes and a09f6c25's correspondence are lib relations per pair, bae5c565's `&same_column` and ac0c5833's `&side` are `same_line` and a side test per pair. Where no test passes, the line is the residual class, and the rewrite takes a reading of the task; those are the briefs that need a solver session rather than an editor.

The lint is not written. Its value tests exist in `snr.py` and `factor.py`, over the export's values rather than `row-counts` dumps, and the body tests in the survey that produced the idiom counts.

## Settled

- One table per assignment: in the encoder. Assignments are evaluated apart, since a join keeps only rows whose assignments agree, so attention across them carries nothing the program reads.
- No table per example for RULE relations: a `DET` can read a RULE's lifted form, which unions the examples, so examples cross.
- `connected` (C20-60, and out of the lib in C20-62), one-atom instance inputs (C20-73), Connectivity.adjacent and CellDistance.predecessor (C20-76): no longer tables.
- The engine's projection cap stays at 10,000: at 2,000, 66 of 123 large clause relations lose a read that fits in no projection.
- The assignment cap of 256 is not a lever: no table has more than 96 assignments.
- Factorized bodies are not a lever: 98% of large-body rows are in bodies with one connected part.
- Showing an instance output only when the model asks for it, or at its first read, is not pursued: it removes whole tables and leaves each table's rows as they are.
- Projection onto read columns as a step of the language is not pursued.

## Open

- The lint of [The lint](#the-lint), then agents on its lines, solver by solver.
- Agreement's `transform` form, the one lib addition the survey supports.
- Whether the work cap of C20-63 stops any of the large tables short, which would make the f8dd701d counts lower than the tables' true rows.
