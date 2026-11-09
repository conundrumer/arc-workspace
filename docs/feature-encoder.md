# Feature encoder

Status: the design of the neural encoder beside a language model that `model/encoder.py` implements. The project left this route ([Goal](../work/goal.md)). Here a table is a parameterized table at one assignment, over every ARC example and constraint model, and a row is one of its table rows; [Terms](sample-build/contract.md#terms) gives the other words.

An encoder turns the tables the engine computes during a decode into feature tokens that the program language model reads. It rests on one hypothesis: learned heuristics that read intermediate computations make program search efficient.

## Role

A decode is a search. At each step, the feature tokens carry the salient patterns in what has been computed so far: the evidence and every table the program has derived. They point at the clauses that ARC-AGI-2 priors make likely next. The engine verifies whatever the model writes, so the tokens only decide what is tried first.

Most tasks need several hops: a clause may compute something that relates to the output only through later clauses, as 68bc2e87's `&under` does. Each step's tables bring up the next clue. The tokens need not see the end of a plan.

The training signal is the gold streams: the next clause is the ground truth of what the tokens should point at.

## Shape

There are two models:

- The encoder takes one table at a time and returns K vectors. It is a pure function of the table's rows, the rows of the evidence tables `ex_input` and `ex_output`, and the K vectors of every earlier table of the decode: S_t = Enc(rows of table t, rows of the evidence tables, S_0, …, S_{t−1}). The evidence tables' rows stay in view for the whole decode, and every other table is kept afterwards as its K vectors alone. A solver keeps the grids in front of it and holds its intermediate results as summaries, so the comparison that a next clause rests on is made between the current table, the grids and summaries of what came before. The two evidence tables are encoded jointly: their rows attend to each other in both directions at every layer, since both are given before the first step and a solver reads the pairs side by side. Each still gives its own K vectors, and the causal order holds from the first derived table on. Seen from above, it is a causal transformer whose positions are tables. Its position encoding is a learned embedding of how many tables back an earlier table lies, clipped, which that table's vectors carry. The tables of one relation's assignments count as one there. It predicts nothing. The earlier vectors are cached, as a language model caches its keys and values, so a search branch shares its prefix's vectors.
- The program language model is a plain decoder over the engine's vocabulary, under the engine's token mask. Each table's K vectors pass through the crossing and enter its sequence after the token whose step produced the table, the way image vectors enter a vision-language model. It predicts none of them and takes no loss on them.
- Relations and labels are identity-only. Each one the engine declares takes a random identifier, drawn fresh for each decode, in place of a numbered token, and every read of it takes the same identifier. The language model writes a read through a pointer over the identifiers declared so far. Keywords, lib relations, components and column positions stay vocabulary tokens.

With `--enc-source-rows` of `train.py` and `pretrain.py`, a derived table's rows also attend, at each layer, to the rows of its source tables after that layer: the earlier derived tables that its columns' flows name, one level deep, which the export's column-level provenance gives. A source table's rows are kept with the state they reached at the source table's own step, so the rows that stay in view grow with the tables that are sources, and a source table over the table cap gives no rows. A computed field's value comes from a row of a source table, and with the flag that row is in view.

With `--enc-parent-bias B` of `train.py` and `pretrain.py`, a row's attention scores against an earlier table's pooled vectors gain a learned value by the provenance relation of that table to the row's table. The relation has three types. An earlier table is a direct source when the export's column-level provenance names it as a source table of a column of the row's table. It is an ancestor when it is a direct source of a direct source or of an ancestor, and not a direct source itself. Only earlier tables count as sources here, so a table that feeds only a later table of the row's export table is no ancestor. Every other earlier table is unrelated. A grid table that a column's flows name is a direct source, as a derived table is. The grid tables' columns have no sources, so no table is an ancestor through a grid table. In a program without the column-level provenance, every earlier table is unrelated. Each layer has its three values, which every head of the layer adds. They start at B, 0 and 0, and training may change them. The bias enters the scores as a channel of the queries and keys: 1 on every query, and on a key the bias of its pooled vector's type, or 0 for a key that is no pooled vector. The types are computed once per program, on the host. Each evaluation logs each layer's three values under `parent_bias`, and the attention probe of `--mask-remote-groups` measures the attention with the bias in it. The flag refuses `--enc-equality flex`. An encoder pretrained with the bias loads into `train.py --encoder-init` only with the flag.

The encoder sees one table per assignment. A relation whose entries hold several assignments gives one table for each, with that assignment's entries over every example and model, at the relation's step and with its identifier. Assignments are evaluated separately, so no clause relates rows of two assignments. The tables of one relation do not attend to each other's vectors.

A derived table's row tokens exist only while the encoder processes that table. Only its K vectors remain.

The evidence tables, `ex_input` and `ex_output`, are the first tables, and the encoder treats them like any other, except that their rows stay in view of every later table and the two are encoded jointly, as the encoder bullet above says. Each holds one row per cell, with the columns Example, Position and Color: `ex_input` holds every example's input, train and test, and `ex_output` each train example's output.

## Tables

The encoder reads a table at the end of each clause, and at the `END` of each `ONE` or `CHOOSE` form. It reads no body in progress: a body is where candidates are searched, and the clause's relation is what the search finds. A table carries its relation slot, its column slots and types, and its rows on every example, with the assignment as a column where the lifted evaluation gives one.

All of it goes in raw, as the lib exports it. The lib exports the compact form of a relation as the relation itself: a class id per member for an equivalence, a rank per member for an order, a ray's end. A program that needs the full form joins for it, and those rows exist only in that clause's body.

A clause has no head, so its relation holds every binding of its body ([Deferred projection](engine/performance.md#deferred-projection)), and the program commits to no projection. Where a relation holds more rows on an entry, one example at one assignment and model, than the row cap, the engine gives its maximal projections in its place: the projections, without repeated rows, onto the largest sets of its columns whose projection holds at most the cap. A smaller projection is a projection of one of these, so the encoder sees it by reading fewer columns. Since relations are sets, a later read whose columns lie inside one projection sees what it would see on the whole relation.

The encoder reads every projection the engine gives for a table, and each projection's rows enter as rows with the other columns absent. A table that the engine could not give, because its projection search stopped at a bound or its entry has no rows for another reason, enters as an empty table: the seeds, the relation's identifier and a constant unseen marker.

## Symmetry

The group is Γ = D4 × the color permutations × the example permutations. Ident renaming joins it if Idents are encoded.

A feature vector depends on a frame, as a pose of a `RIGID_DET` does: transforming the content by γ transforms every vector of the decode in the same fixed way. Relations between vectors do not depend on the frame. The program writes no frame-dependent value, since every such value is a `DET` that the engine determines, so what the language model needs is frame-free. Inside the encoder, vectors stay frame-dependent, so a comparison that needs relative orientation, such as an S in one table against a Z in another, can be made there. The crossing to the language model passes frame-free quantities alone.

The symmetry serves as a heuristic prior. Nothing requires it to hold exactly.

A pose is a frame: transforming the content by γ conjugates the pose set of an assembly. Where several instances are present, the instance that the engine picks as the frame can change under γ, which right-multiplies every pose by one fixed element. Equivariance is then exact only while the frame instance stays the same.

## Values

A row token has three parts:

- Invariant channels: an embedding of each number, and a random identifier for each value of an identity-only type, Color, Example, Ident and the assignment, and an indicator of the kind of the row's example: task, train or test. A random identifier is a vector drawn fresh for each decode and reused for that value in every table of the decode. The encoder can only test whether two identifiers are the same, so the color permutations act as a new draw.
- Edge channels, a 4 × c array with a row per edge: a Box, Position or Offset as the embedding of each margin on its edge, and a Dir, DiagDir, Dir8, Axis or Axis4 as an indicator on its edges. D4 acts by permuting the rows.
- Pairwise edge channels, a 4 × 4 × c array: a D4 element, a C4 or a Pose's D4 constant as its permutation matrix of the edges, a DiagAxis as the matrix of its reflection, and a Sense as the matrix of the quarter turn in that sense. A Sym, a subgroup of D4, takes two matrices: the sum of the permutation matrices of its rotations, and the same sum over its reflections. The mean over all its members is the projector onto their fixed space, which does not separate the subgroups. D4 acts on both sides, M ↦ P·M·Pᵀ, which is the conjugation of `docs/engine/equivariance.md`.

Each column's features, in each part, are bound to the column by a channel-wise product with the language model's embedding of its column slot, and the row token is their sum. The example kind's indicator is bound in the same way. The relation slot's embedding, which is added to the invariant channels, is the identifier that the language model gives the relation's declaration. The engine writes that declaration after the step that gives the table, and the table takes the first declaration of its slot after that step. In training, the identifier is read from the stream. In decoding, it is drawn when the table appears and reused when the engine declares the relation, so the table must determine that declaration.

A fallback gives each cell of a row its own token, with attention alternating within a row and across the rows of a column, as TabPFN (Hollmann et al., 2025) does. It costs the column count times more tokens. Whichever of row tokens and cell tokens is used, it is used for every table.

## Layer

Every part is a permutation representation of D4, so a standard transformer block carries over with its linear maps sharing weights by D4 orbit:

| map | weights per channel pair |
| --- | --- |
| edge → edge | 3: same, opposite, adjacent edge |
| invariant → edge, edge → invariant | 1 each |
| invariant ↔ pairwise | 3 each way |
| edge ↔ pairwise | 10 each way |
| pairwise → pairwise | 36 |

Pointwise nonlinearities and norms per entry keep the equivariance. An attention score is the sum of inner products over the invariant channels, the edges and the edge pairs, so it is invariant. The values are equivariant.

The score also holds an equality term: for each pair of columns of one type, whether the two rows hold the same value there, under a weight the encoder learns per head and column pair. It covers every type, since a join on a cell is as common as a join on a color, and Γ keeps equal values equal. Its current means is fixed query and key channels that hold each value's code per column, so an equality is an inner product and no row-by-row matrix is stored. A value of a type with few values has an exact code: a one-hot per margin for a Box, Position or Offset, and a one-hot for a color or a direction. Permuting colors permutes coordinates, which keeps inner products. A number, which can count up to the cells of a grid, and an Ident have random codes, so their equality is approximate.

The term acts within a table. With `--enc-source-rows`, it also acts between a derived row and the rows of its source tables: it compares each column with the source columns its flows name, under its own weight per head and column pair, so that a lookup by a shared Ident, Box or Example finds its source row. A join the program has written shows in the table the engine gives after it. A join not yet written is what the tokens point at, and it rests on the random identifiers that the earlier tables' vectors carry.

A table's K vectors come from K learned seeds that attend to its rows, as in the Set Transformer's pooling by multihead attention.

A directional scan gives each row, for each direction, the maximum of the features of the rows whose position lies in the same frame, on its line on that side, as CompressARC's directional cumulative max does on a grid. It goes into the edge channels, one row per direction, so it is equivariant, and a sort along each line makes it cost n log n. Two positions share a frame when their margins sum to the same amount on each axis. With it, the encoder reads a ray from its record and the cells it crosses. A plain scan sees past a blocker.

Some comparisons are cheap to build in. When an output is a D4 image of an input, the output's pooled vectors are the input's with their edge rows permuted, so the best match over the eight permutations of a pooled vector shows it.

## Crossing

Each of a table's K vectors is read out as frame-free quantities: its invariant channels, and sums and inner products over the edge and pairwise axes. A learned projection maps them to the language model's width.

The crossing runs one way. The encoder perceives the program through the tables the program computes.

The language model's sequence gains K vectors per table it reads, so its feature tokens number K times the tables: one per assignment of each clause's relation.

## Scale

Attention among a table's rows costs the square of the row count.

The row cap of [Decode settings](engine/synthesis.md#decode-settings) bounds the rows of one entry, since a larger relation gives its projections there ([Tables](#tables)). It is the bound of the export. A table's rows are the sum over its entries, so a table can hold far more rows than the row cap, and the main branch has large tables: one corpus table has 30 entries and 66,144 rows.

The encoder sees a derived table only up to a table cap on its rows, summed over its entries: 4,000 rows by default, `--enc-max-rows` of `train.py` and `pretrain.py`. The table cap applies to each assignment's table on its own. A derived table over the table cap is unseen: it enters with a constant marker, and the encoder learns nothing for it. A decode whose table exceeds the table cap runs with that table unseen from then on. The evidence tables are exempt. The table cap rests on these facts:

- 90% of derived tables hold at most 1,000 rows, and the median table holds 42. The 5% over 2,000 rows hold 84% of all rows, and attention costs the square of the row count.
- Such tables are not what a solver holds in mind.
- The gold programs are written to avoid them.

The row cap is the smallest row count at which the only reads of the gold solvers that fall outside every projection are the pairings inside a search over candidates, whose answer a later clause keeps, once each relation of the concept takes its concept's form. The table cap, not the row cap, bounds the encoder's attention. The value is provisional: 10,000 rows. On the 57 solvers with the largest tables, a cap of 10,000 rows leaves 15 of 1,880 reads outside every projection, in 9 cases. Seven are candidate pairings, and two are pairs where the concept has a class id. A relation over the cap gave at most 7 projections.

The row cap rests on engine work that does not exist: an instance that computes only the outputs some clause reads, and a `CHOOSE` that checks a `never` with one option bound and forms its clusters without listing pairs.

Fallbacks that keep large tables:

- Encode each part of a body as its own table, and combine the parts' vectors. A body's rows are the product of its parts' rows ([Decode interface](engine/synthesis.md#decode-interface)), so a product is never encoded.
- A lower row cap, so that more relations arrive as projections.

An architecture that only large tables take would be learned from the rarest tables, and is not used.

Each table adds K vectors to the language model's input, so the input length grows with the table count, and a relation with several assignments gives several tables. A sequence whose vectors would take it past twice `--max-len` drops its latest tables.

The encoder runs one level at a time: the t-th table of every program of a batch. The row tokens and equality codes of every table of a call are built together before the first level, and each level's tables are cut into a few batches, each padded to its largest table. The cut weighs the attention scores that padding adds against the fixed cost of one more batch, since a step of many small tables is bound by the count of operations it issues, not by its arithmetic.

## Training

The engine replays each gold stream of `programs/arclog/`, and later of re-arc and arcscene tasks, and records each table at its token index. The encoder and the language model train end to end on the next-token loss. Random identifiers are drawn fresh for each training example.

The encoder also takes a masked loss on every table: a field of a row is hidden, and the encoder predicts it from the table's other rows, the evidence tables' rows and the earlier tables' vectors. A number or a margin is predicted as a class, a Position or direction per edge from the edge channels, and an identity value as a pointer to a row that holds the same value, or as a value no row holds. Since a derived table follows from earlier tables, the loss also trains the cached vectors to keep what later tables need. Masked fields of `ex_output` are the task itself.

A hidden field must be computable from what the encoder sees. A computed field's value comes from a row of a source table, which, without `--enc-source-rows`, the hidden row sees only as that table's K vectors, so its pointer has no cue there. An inner product of learned maps does not compare random identifiers either, so the pointer gains equality terms with `--enc-ptr-equality`: a candidate row scores a learned weight where its value equals a visible field of the same type in the hidden row, and, with `--enc-source-rows`, it scores its value's code against the codes that the hidden row's last layer gathers from its source rows, the codes of each source row's Color, Example and Ident fields, weighted by the attention.

Each field has a label: computed, inferrable, remote or sole. The labels and the sources come from the export's column-level provenance: the flows of each column, the candidate keys and the depth of each table. In the evidence tables, Example and Position fields and the Color fields of `ex_input` are inferrable. A Color field of `ex_output` is computed when its value occurs among the same example's input colors or in another train example's output. Otherwise it is sole. A computed Color field is dependent when the output relation's Color column reaches a DET or `ex_output` through the flows, with the fields of the other train outputs that hold its value as its sources, and free otherwise. In a derived table, a field is inferrable when its column is in a candidate key, a key field whose target is a set, or when every flow of its column is a constant or a lib name. Otherwise it is computed. A sole field is never hidden. A computed field of a derived table whose column has sources, all in other derived tables, is remote, and a program step hides it only with `--mask-remote` or `--mask-remote-groups`, since its row sees those tables only as K vectors.

A hidden remote field is the only target of the loss whose answer must come from earlier tables' K vectors, so it is what trains those vectors to carry a table's contents. Hidden one field at a time, as `--mask-remote` hides it, it can often be answered without them: the rows of its table that joined the same source rows often hold the same value, and the encoder can read the value from one of them. Under `--mask-remote-groups`, a program step hides remote fields only in a column that has a source column in a derived table and whose source tables are all seen, and it hides them by key group: the rows of one entry that agree, in presence and value, on every other column that has a source table in common with the column. Each key group is hidden with probability `--mask-frac`, by one draw, in every row, so that a group's chance to be hidden does not grow with its size and no visible row of a hidden group shows its value. A remote column whose flows name no table is never hidden, since no earlier table's vectors carry its value. A hidden group counts its fields toward `--mask-cap`; where a table's computed candidates and hidden groups hold more fields than the cap, they are kept in a random order while they fit, and a group that does not fit stays visible whole. The flag does not combine with `--enc-source-rows`, under which the hidden row reads its source rows directly.

Each program's step is a program step, an output step or a prior step, by `--mask-kind`. A program step hides computed fields. An output step hides the computed fields of `ex_output` alone. A prior step hides inferrable fields. In a program step, a column hides no field when one of its sources hides fields, or when it is a source of a column that hides fields. A column's sources are the columns its flows name, one level deep. In a program step and in an output step, a hidden dependent field keeps one of its sources visible. An export without the provenance gives table-level rules: a derived table's sources are the evidence tables and the tables of its DETs' relations, a table hides no field when a source or a table it is a source of hides fields, a derived field is computed when its row differs from every other row outside its column, and a Color field of `ex_output` is dependent when its value occurs in another train output and not in its own input.

The loss is the program part, over the computed fields of the program and output steps, plus `--prior-weight` times the prior part. The prior part has a floor, the entropy of the target's distribution, so the log gives each part apart, by type, and the program part by the derived table's depth. Where remote fields are hidden, the log gives them apart from the computed fields of their type, leaves them out of the depth buckets, and gives them by the row count of the largest source table of their column and by type, with the per-field means of the loss and its chance level beside their means over key groups, so that a large group counts once. A pointer field is split by its target: a row that holds its value, a row of another entry that agrees with the hidden row on the group's key columns and holds its value, or "no row holds it". When a column is hidden in every row of its entry, its "no row" target follows from the mask pattern alone, and the row of another entry gives the value with no summary, so only the remaining row targets show that the vectors carry the table's contents. Under `--mask-remote-groups`, the evaluation also measures where a hidden remote field's row attends among the earlier tables' K vectors: the share of that attention on the vectors of its column's source tables, beside that share under equal scores, and, over the fields whose row attends to at least as many other earlier tables as source tables, the same share beside the share on as many of the latest other earlier tables, since the source tables are usually the latest ones and the recency embedding alone can draw attention to them. A hidden key field takes the single-value heads, and its loss estimates the distribution of its set. `--mask-frac` and `--mask-cap` set how many fields a step hides per table.

Programs are few and tables are many: running the corpus solvers on new inputs of their tasks, such as re-arc's, gives new tables under the same programs. The masked loss uses those tables; the next-token loss gains no new program from them.

The encoder also trains a value head, as a process reward model with the engine as its verifier. The value it estimates is the machine form of salience: a person's sense that an intermediate structure is on the way to the solution, which steers the person's search. A branch point is a rule boundary of a gold program. From each branch point, the baseline language model samples continuations of the gold prefix under the engine's mask, and the engine replays each one to give its tables. A table takes one of two labels, by `--value-label`. Under `solving`, the default, a table's label is its continuation's solving: a continuation whose replay does not fault, that ends consistent with the train pairs and solves the test pairs, is solving, and the gold continuation is one more solving continuation of its branch point, so every table of a solving continuation has label 1. The engine's verdict on a RULE clause is whether the relation that its END finishes, read as the output, solves every train pair. Under `consistent`, a table's label is the verdict on the rule whose evaluation gave it, 1 for Consistent, with the gold continuation's own verdicts, so the label marks the tables of a rule whose relation is the output. The head gives one logit per table, from the frame-free readout of its K vectors. Its loss is a listwise softmax cross-entropy over one branch point's continuations, which ranks the first table after the branch of each continuation of label 1 above those of label 0, so that the Monte Carlo rollout estimate of the process reward is its target. The continuations of one branch point share the prefix, so a ranking among them cancels what the prefix gives, its depth and its length. Empty, unseen and faulted tables take no target, since their form alone would tell a failure, and under `consistent` neither does a table of a last rule that has no verdict. Only the first tables after the branch take a target, since whether a later table exists, and at what depth, shows how far a continuation got. The gold continuation differs from the sampled ones in its author, so the pairwise ranking accuracy is also measured over the sampled continuations alone. A branch point is held out with its task, so a head that memorizes the training tasks' programs gains nothing on the held-out ones.

The first runs train the encoder on the masked loss as a stage before the next-token loss, and then with the two losses beside each other.

A comparison with and without the encoder evaluates the same cases, with the same batches in the same order for a seed, and bounds the step count by the length limit alone, so the targets are identical.

## Open

- Whether 4,000 rows is the right table cap, judged by how many tables of the gold programs it leaves unseen. The distribution of table sizes is measured ([Scale](#scale)).
- Two solvers whose reads fall outside every projection at 10,000 rows take their concept's class id: 0dfd9992 reads `&orbit.class` in place of `&wp.action` pairs, and 484b58aa reads a class per cell per axis in place of `&axis_agree` pairs.
- Tables during search, of clauses no gold program writes, are unmeasured.
- K, and the encoder's depth and widths.
- Whether a derived table's K vectors keep what later steps need, measured by the masked loss on derived tables and by the comparison with and without the encoder. The evidence tables are outside this question, since their rows stay in view.
- Whether prose per clause, or the clause itself, shapes the feature space as an auxiliary target.
- How much the encoder adds: the language model with and without it.
- Whether the masked loss runs before the next-token loss as a stage, or beside it. The first runs compare the two.
- How the language model avoids memorizing a program per task, with few programs.
- Whether cell tokens beat row tokens.
- How the equality term is computed. The one-hot codes add up to about 560 dimensions to each head's query and key. Measured at 66,000 rows, that is about 2.7 times the attention memory and 1.8 times its work. Under the table cap the width costs little, so the choice matters only with a higher table cap. The alternatives are a term that adds the per-column weight to exactly the pairs that hold the same value, with no extra width, and random codes of a fixed width, which are approximate. The means is a configuration of the encoder, with the one-hot codes as the default, and a sweep compares the one-hot codes, the same-value term and the random codes.
- Whether a row token's channels hold its columns' values, since the row token is the sum of its bound column features, measured by the masked loss's accuracy per value type at each channel width c. If they do not, cell tokens are the answer.
- Whether the encoder learns where a ray stops from a plain scan, or needs a scan that stops at a blocker.
- Whether a derived row attends to the cells of every example in `ex_input` and `ex_output`, as now, or to its own example's cells alone. The program relates a row to another example only through a DET, whose value also reaches the row through the jointly encoded grid tables, the other examples' rows of its own table and the DET's table, so the restriction loses nothing the program reads and divides that attention's work by the number of examples. It is adopted if the profiles show that attention as a large part of the step. At the default shape on the full afc44b43 data, all attention is 14% of the step's wall time and the step is host-bound, so it is not adopted yet.
