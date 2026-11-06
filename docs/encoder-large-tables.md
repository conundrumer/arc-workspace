# Large tables in the feature encoder

Status: record, for the neural encoder of [feature-encoder.md](feature-encoder.md). [Features map](features-map.md) gives the current sources.

A question of [feature-encoder.md](feature-encoder.md): what the encoder does with a table whose rows
are more than its attention can afford. The question is settled ([Decision](#decision)). This document
gives the question, the constraints on an answer, the data in hand, what was to be measured on the full
corpus, the measurements and the decision. The sections from The question to What to measure on the
full corpus are the record of what was weighed before the decision. The reader is a session that
changes the table cap.

## The question

The encoder's main branch was full attention among a table's rows ([Scale](feature-encoder.md#scale)).
Its cost is the square of the row count. The engine's projection cap bounds the rows of one entry, one
example at one assignment and model, and a table's rows are the sum over its entries, so a table can
hold many times the cap. The question was how the encoder reads such a table.

## Constraints

- One architecture for every table. A second path that only large tables take has to be learned from
  the rarest tables, and those are the heavy joins where a wrong reading costs the most. So an answer
  adds no learned component that only large tables use.
- A table over the table cap is an unseen table: the encoder gives its seeds, the relation's
  identifier and the constant unseen marker, and the case stays in training. The count of unseen tables
  is printed with the table statistics of each run.
- The answer comes from the data: which tables are large, why, and whether the program reads them.

## Answers that fit the constraints

- Full attention everywhere, with the score matrix never stored. Fused scaled-dot-product attention has
  memory linear in rows, and compute of about 2 × rows² × channels per layer: at 66,000 rows and 672
  channels, about 6 × 10¹² multiply-adds, which is under a tenth of a second on an A100. The risk is
  that the framework falls back to the plain kernel, which stores the matrix: 66,000² scores in bf16 is
  8.7 GB per head. Mitigations that change no mathematics: run a table alone where its size would need a
  padding mask, or chunk the query rows.
- A lower projection cap in the engine. A relation over the cap arrives as projections, which every
  table can do and the encoder reads already. The cap is a decode setting (`projection_cap` of the
  Python package's `Settings`, and of `arclog.corpus_tables` once change 20-9 lands). The design
  measured 10,000 rows as the cap at which 15 of 1,880 reads of the 57 largest solvers fall outside
  every projection, 7 of them candidate pairings inside a search. A lower cap puts more reads outside.
- Each part of a body as its own table, so a product of parts is never encoded: the first fallback of
  [Scale](feature-encoder.md#scale). It changes which tables exist, not the network. Bodies are not
  exported today (`engine/arclog-py/tables_export.py --bodies` gives the body points).
- Leave the table unseen. Costs the encoder its view of that clause's result, and nothing else.

Answers that do not fit: induced set attention, attention within an example with summaries across, or
value-sharing attention, taken only above a row count. Each is a learned path for the rare case.

## Data in hand

From the ten-task development export under `work/tables/dev/` (26 cases, 570 relation tables,
including the two evidence tables of each case):

| unit | median | p90 | max |
| --- | --- | --- | --- |
| rows per entry, or per projection at an entry | 4 | 170 | 6,568 |
| rows per table, summed over its entries | 32 | 1,470 | 66,144 |

No entry exceeds 10,000 rows. 13 tables exceed 10,000 rows in total, all in task 2b9ef948, cases
`$Core` and `$Corner`; the largest, relation 19 (DiagDir × Box) at token 301, has 30 entries, 6 per
example on 5 examples, of 1,200 to 3,600 rows each. The evidence tables' largest is 3,510 rows.

From the superseded full export of 2026-10-23 (21,165 relation tables of 956 tasks, before the fix
5f77b431, rows summed over examples and entries): median 48, p90 1,420, p99 13,453. So about 200
tables of the corpus are over 13,000 rows.

On the CPU of the development machine, a training batch that holds one 5,370-row table takes 23 to 29
seconds, against about 0.9 seconds for a batch without the encoder.

## What to measure on the full corpus

The full tables export, `work/lm/.venv/bin/python engine/arclog-py/tables_export.py <out dir> --all-cases`, gives
the current layout: `tables.parquet`, `index.parquet` (one row per entry), `projections.parquet`,
`projection_rows.parquet`, `values/`, with the layout in its docstring and the column meanings in
`engine/arclog-tables/src/columns.rs`. The export is slow on one solver's step until bug 20-14 lands.

1. The distribution of rows per table over the corpus, and the tables over 10,000, 20,000 and 50,000
   rows: their task, relation, column types, form, entry count and rows per entry.
2. What those tables are: which clause gives each, whether its rows are a product of its body's parts,
   and whether the relation is a join the program later projects. The stream and the solver under
   `work/arclog/gen/` and `programs/solvers/` give the clause.
3. Whether a later clause reads each large table: the reads of the program on that relation, and
   whether the columns read lie inside a projection the engine would give at a lower cap.
4. The share of model-written steps, and of the loss, that follows a large table within the program,
   so the cost of leaving it unseen is known.
5. The projection cap at which no table exceeds a chosen total, and the reads that then fall outside
   every projection, by the design's own measure.
6. On the GPU, whether fused attention runs at the largest table's size with the encoder's mask and
   head width (168 channels per head plus the equality dimensions), and the time and memory it takes.
   [Measured](#measured) gives it.

The answer was to be the one of the fits above that the measurements favoured, with the numbers that
favoured it, and the row count at which a table is unseen if any remained so.

[Measured](#measured) gives item 6. The distribution in [Decision](#decision) supersedes items 1 to 5.

## Measured

Fused attention at the encoder's shapes, on one A100 SXM 80 GB, torch 2.8: `scaled_dot_product_attention`
on random bf16 tensors, batch 1, 8 heads, query and key of 168 + D channels per head (D the equality
channels), value of 168, forward and backward of `output.sum()`. Each time is the median of 3 runs after a
warm-up; each peak is `torch.cuda.max_memory_allocated`. The mask is a boolean key mask of shape
[1, 1, 1, N], 95% True. Each backend was forced in turn with `sdpa_kernel`; "default" is the run with
none forced, and the backend whose time it matches.

| N | D | mask | flash ms | efficient ms | math ms | default | peak GB, efficient |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10,000 | 0 | no | 17.7 | 69.1 | 144.2 | flash | 0.31 |
| 10,000 | 0 | yes | refused | 70.0 | 149.3 | efficient | 0.33 |
| 10,000 | 64 | no | refused | 75.7 | 149.9 | efficient | 0.38 |
| 10,000 | 64 | yes | refused | 78.3 | 155.2 | efficient | 0.38 |
| 10,000 | 192 | no | refused | 97.8 | 183.4 | efficient | 0.50 |
| 10,000 | 192 | yes | refused | 100.1 | 188.6 | efficient | 0.50 |
| 20,000 | 0 | no | 57.4 | 241.1 | 583.2 | flash | 0.61 |
| 20,000 | 0 | yes | refused | 251.3 | 604.8 | efficient | 0.61 |
| 20,000 | 64 | no | refused | 275.8 | 605.3 | efficient | 0.72 |
| 20,000 | 64 | yes | refused | 283.8 | 627.8 | efficient | 0.72 |
| 20,000 | 192 | no | refused | 366.4 | 732.1 | efficient | 0.96 |
| 20,000 | 192 | yes | refused | 375.5 | 753.7 | efficient | 0.96 |
| 33,000 | 0 | no | 155.5 | 630.0 | out of memory | flash | 0.98 |
| 33,000 | 0 | yes | refused | 667.5 | out of memory | efficient | 0.98 |
| 33,000 | 64 | no | refused | 724.4 | out of memory | efficient | 1.17 |
| 33,000 | 64 | yes | refused | 742.1 | out of memory | efficient | 1.17 |
| 33,000 | 192 | no | refused | 981.7 | out of memory | efficient | 1.55 |
| 33,000 | 192 | yes | refused | 992.0 | out of memory | efficient | 1.55 |
| 66,000 | 0 | no | 615.9 | 2,465.9 | skipped | flash | 1.92 |
| 66,000 | 0 | yes | refused | 2,519.4 | skipped | efficient | 1.92 |
| 66,000 | 64 | no | refused | 2,868.3 | skipped | efficient | 2.29 |
| 66,000 | 64 | yes | refused | 2,885.4 | skipped | efficient | 2.29 |
| 66,000 | 192 | no | refused | 3,969.8 | skipped | efficient | 3.05 |
| 66,000 | 192 | yes | refused | 3,984.9 | skipped | efficient | 3.05 |

"refused" is the backend's `No available kernel` error. The math backend's peak was 12.2 GB at 10,000 rows
and 48.2 GB at 20,000; at 33,000 it ran out of memory on an allocation of 32.46 GiB, and at 66,000 it was
skipped, at an estimated 195 GB.

The efficient (memory-efficient) backend is the one that runs every configuration the encoder needs: at
66,000 rows, with the key mask and D = 192, one attention's forward and backward takes 3.98 s and peaks at
3.05 GB. Its memory is linear in rows, and its time grows about 4 times when the rows double. The flash
backend runs only where query, key and value have one width (D = 0) and no mask is given, and there it is
about 4 times faster than efficient; so the encoder's equality channels and its mask rule it out. The math
backend, which stores the score matrix, handles at most 20,000 rows on 80 GB. With no backend forced, the
framework picks flash where flash runs and efficient everywhere else, so it never falls back to the math
path at these shapes. The mask costs efficient at most 6%.

## Decision

The encoder sees a derived table only up to a table cap on its rows, summed over its entries: 4,000 rows
by default, `--enc-max-rows` of `train.py`. A derived table over the table cap is unseen, with a constant
marker that is not learned, and the encoder learns nothing for it. A decode whose table exceeds the
table cap runs with that table unseen from then on. The evidence tables are exempt. No architecture
exists that only large tables take. Full attention over all of a table's rows, across its entries,
stays in the code, and a higher table cap on the flag uses it.

The reasons:

- Attention costs the square of the row count, and the few large tables hold most of the rows, as the
  table below gives.
- Such tables are not what a solver holds in mind.
- The gold programs are written to avoid them.

The distribution of derived tables is from the index of the export `work/tables/full-32472165-skip60/`,
which counts a relation's rows before the engine's projection cap:

| rows per table | share of tables | share of rows |
| --- | --- | --- |
| at most 1,000 | 90% | 15% |
| over 2,000 | 5% | 84% |
| over 10,000 | 1.1% | 70% |

The median table has 42 rows, and the median entry 7. Tables over 10,000 rows occur in 221 of 865 tasks.

## Code

- `model/encoder.py`: the loader, `unseen_counts`, `mark_over_budget`, and the flags `--enc-budget`
  (the per-entry assertion, 10,000) and `--enc-max-rows` (the table cap, 4,000) in
  `model/train.py`.
- `model/README.md`, section Encoder: the flags and the development data.
