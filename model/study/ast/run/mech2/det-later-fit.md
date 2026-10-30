# Derived DET fit measure

`det_later_fit.py` measures mutant OUT after deriving DET relations from the mutant tables through `ReplayEvaluator.det_later_fit`. It does not alter the mechanical labels or grades. It uses the canonical evaluator and native FITS; it has no alternate evaluator, grid comparator or gold-held fallback.

The executor supplies native TRAIN FITS and TEST outcomes for the same train-fitting assignments, a first later empty/different relation when available, operation receipts and explicit unknown reasons. TRAIN uses native FITS: one common derived assignment must fit every train example. TEST results belong to those same TRAIN-fitting assignments; assignments are never selected by TEST outputs. Limits apply to each recorded native operation; multiple operations can be necessary for one pair. Gold baseline acquisition is cached by the shared evaluator.

The store is `DATA_ROOT/ast/run/mech/det-later-fit/results.sqlite3`:

```sql
pairs(pair_id PRIMARY KEY, input_sha256, source_sha256, result_sha256, result_json)
metadata(key PRIMARY KEY, value)
```

`result_json` is the canonical `evaluator-det-later-fit-v1` result. It stores this measure's train/test outcomes, per-assignment evidence, later-difference facts and receipt references. No base record, grade or derived summary is copied. Source hashes provide provenance. Input keys bind the original source record consumed by the evaluator, task evidence and measure version; changes to code files do not force reruns. Every completed pair commits with synchronous FULL. `--retry-unknown` retries unresolved results; `--remeasure` reruns the selected scope; `--remeasure-pair` limits explicit repair to named pairs.

The smoke scope checks a failing product mutant and an equivalent mutant at task `6e02f1e3`, case `$Figure $Fixed`, point `[6,0]`. The failure must report TRAIN nonfit and later `fig_diag` empty; the equivalent mutant must fit TRAIN. The figure scope checks all stored pairs there and requires legacy fits pairs to fail TRAIN, including pairs study excludes for normal form. The points scope consumes the supplied `feat-exp/study/round-6/det-points.json`; the all scope covers every stored DET pair.

Progress reports done/total, elapsed, rate and ETA. Individual native calls may have separate limits; the evaluator's operation ledger records them. The command logs report wall seconds per newly evaluated pair. The full scope is launched only after pilot outcomes and measured cost are reviewed.

The driver groups work by task, case and point, following source case order. It prefetches bounded batches in gzip line order and hashes each task once. The native evaluator is constructed only when a pair needs new work. It checks resume before opening original sources or constructing new task sessions; unchanged done pairs require no source scan or evaluation. No stored status depends on current code hashes. Command files and execution logs live under the shared data root.

The pilot commands run this unmerged consumer with `--evaluator-code-root` selecting one qualified shared evaluator checkout. `codex-adm/n-mech2-det-fit/backend.json` under DATA_ROOT binds that code root to its compatible immutable runtime executable. It is published after n-eval's READY receipt; absent deployment metadata stops the commands before evaluation. No held-mode fallback is used.

`--parity-baseline` selects saved sample IDs and checks outcome/axis facts against an existing receipt without rerunning the baseline. `--pair-id` can select explicit points for qualification. Wall time, native phases and diagnostic-work counters are printed; `/usr/bin/time -l` in the run commands captures resource use. Full-run commands check saved candidate parity before launching and resume the same fact journal. Source and deadline/work/session bounds stay unchanged by batching.
