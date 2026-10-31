# Clause sampler

S draws one clause at a point of a task, given the program before that point, under the decoder's token mask. The target is π ∝ P · exp(β · score) · 1[hard rules], where P is built from the corpus priors. The module docstring of `sample2_col.py` gives the draw, the gates and each environment setting.

`sample2_col.py` is S and `sample.py` holds its priors. `sampler_paths.py` says where code and data are read from. Models, the corpus view and run outputs stay in the shared data directory, under `sampler/` of `python3 model/study/study_paths.py`.

## Proposal

These settings steer the proposal. Each takes a file in `sampler/models/`:

- `TILT` with `TILT_STOP=lw`: the linear tilt.
- `STEER_REL`: the relation-pick ranker. `relcheap.py` fits it, `relsteer.py` loads it, and `relfeat.py` and `plugins/rk2/` give its features.
- `STEER_CHOICE`: the choice-pick ranker for columns, values, operators and the stop. `choicecheap.py` fits it, and `choicefeat.py` and `plugins/chplug/` give its features.

`REL_ROWS=1` and `CHOICE_ROWS=1` write the rows those fits read. `ROW_ORDERS=n` writes them for n random valid atom orders per clause, and each row has `order`.

## Measure

`GOLD_Q=1` gives gold's log q under the steered proposal, on gold's row in `draws.jsonl.zst`.

- `ANCESTOR_PREFIX=1` gives each point a prefix of its clause's ancestors by reads only, for the measure, the rows and the draws.
- `GOLD_ORDERS=all` also gives `logq_orders`, gold's log q summed over its valid atom orders. `ROW_ORDERS` and `GOLD_ORDERS` each turn on `ANCESTOR_PREFIX`.
- `gold_q_ab.sh`, `gold_q_d3.sh`, `gold_q_fresh.sh` and `gold_q_out.sh` run an arm into `sampler/runs/`. Each script's first lines give its point set and usage.
- `gq_pair.py A B` pairs two runs by point, `gq_parts.py A B` splits gold's bits by part, and `gold_q_report.py` gives the bits and the CPU-hours to hit gold.
