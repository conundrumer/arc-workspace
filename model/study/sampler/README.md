# Clause sampler

S draws one clause at a point of a task, given the program before that point, under the decoder's token mask. The target is π ∝ P · exp(β · score) · 1[hard rules], where P is built from the corpus priors. The module docstring of `sample2_col.py` gives the draw, the gates and each environment setting.

`sample2_col.py` is S and `sample.py` holds its priors. `sampler_paths.py` says where code and data are read from. Models, the corpus view and run outputs stay in the shared data directory, under `sampler/` of `python3 model/study/study_paths.py`.

## Proposal

These settings steer the proposal. Each takes a file in `sampler/models/`:

- `TILT` with `TILT_STOP=lw`: the linear tilt.
- `STEER_REL`: the relation-pick ranker. `relcheap.py` fits it, `relsteer.py` loads it, and `relfeat.py` and `plugins/rk2/` give its features.
- `STEER_CHOICE`: the choice-pick ranker for columns, values, operators and the stop. `choicecheap.py` fits it, and `choicefeat.py` and `plugins/chplug/` give its features.

`UNREAD_BETA` takes no file. It is in nats, with default 0, which is off. At an atom start, a derived option whose form no kept form reads has its log weight in q raised by that many nats. P and the steers' rows stay as they are. A pool gives `Sampler.search` the forms that none of its forms read, and a caller with no pool takes the forms of the scope as all the kept forms (`live.unread_forms`).

`ORDER_FREE=col,tie,key` takes no file and is off by default. Each name turns on one reading of a body as a DAG:

- `col`: a derived relation's columns get a coin each, by the body's place, the column's type and whether that type is in scope (`COL_TYPE`). `col_type_counts.py ROWS OUT.json` counts the table from the rows of `live_rows.py`.

`REL_ROWS=1` and `CHOICE_ROWS=1` write the rows those fits read. `ROW_ORDERS=n` writes them for n random valid atom orders per clause, and each row has `order`.

`live_rows.py` writes the same rows from gold's walk through `live.py`, so a row exists wherever a draw consults a steer: the atoms of a RULE's or a DET's body, of an INIT's key and ports, of the branches of an OR (nested ones too) and of an ALL, and the stops after a body's atoms. Each row is the row that the steer scores, built by the Drawer's own function, with gold's pick, and has `where` and `place`. `STEER_COVER=init,branch` makes a draw consult the steers at an INIT's bodies and at the first atom of a later branch of an OR, which they leave alone otherwise; the rows are written under it. `relcheap.py` and `choicecheap.py` take `--exclude FILE` for tasks that no fit may read.

## Measure

`GOLD_Q=1` gives gold's log q under the steered proposal, on gold's row in `draws.jsonl.zst`.

- `ANCESTOR_PREFIX=1` gives each point a prefix of its clause's ancestors by reads only, for the measure, the rows and the draws.
- `GOLD_ORDERS=all` also gives `logq_orders`, gold's log q summed over its valid atom orders. `ROW_ORDERS` and `GOLD_ORDERS` each turn on `ANCESTOR_PREFIX`.
- `gold_q_ab.sh`, `gold_q_d3.sh`, `gold_q_fresh.sh` and `gold_q_out.sh` run an arm into `sampler/runs/`. Each script's first lines give its point set and usage.
- `gq_pair.py A B` pairs two runs by point, `gq_parts.py A B` splits gold's bits by part, and `gold_q_report.py` gives the bits and the CPU-hours to hit gold.
- `or_q.py STEMS OUT.json` gives gold's bits under the walk of `live.py` (the walk that `search.py` explores), by part: the OR, its branches' atoms, the stops and the link coins. It runs gold's clause with each choice set to gold's, and the record reads the form's valid orders: `total` is -log2 of the sum of their chances. `or_q.walk_order` is the walk of the written order alone.
- `form_orders.py` reads a form as sets of atoms: the form's orders, the rules the decoder's refusals teach, and the sum of a chance over the orders.
- `dag_bits.py` writes a record of `or_q.walk` for each form of gold's text, in shards that resume; `dag_bits_read.py` reads those records, partial or whole.
- `scripts/arclog_bits.py PROGRAM.arclog TASK [--fast]` gives the bits of each form and atom of a program, in the walk of `or_q.py` over its valid orders and every earlier form (`--parents`: the forms it reads, in canonical atom order; `--written`: the written order only). `--help` has the columns and the options.
