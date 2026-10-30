# Synthesized sample labels

`sample_label.py label` gives synthesized samples the labels that corpus pairs get. A sample is a task, a gold point and a candidate program, for example a mutant of a gold program. The driver writes one label line per sample as soon as that sample is done, and a restart skips the samples that already have a line. The producer can append samples while the driver runs; a later run labels the lines that a run did not reach.

```sh
scripts/run_heavy.py --cpus 1 <runtime python> -B model/study/ast/run/sample_label.py label \
  --samples DIR/samples.jsonl.zst --golds DIR/golds.jsonl.zst --root ROOT --tasks <task directory>
```

Use one `--root` per sample population. `--limit N` reads only the first N sample lines. `--retry-unavailable` processes again the samples whose last line has status `unavailable`, for example after a constructor for their candidate kind exists. `--no-reuse-base` evaluates a mutant again even where the historical base has an intact label for it. Progress with rate and ETA goes to stdout. Output of the stages goes to `ROOT/stages.log`.

`sample_label.py targets --root ROOT [--pair-seconds S] [--retry-unavailable]` runs the all-target comparison (`mech5.targets`) on the root's own labeled pairs, and adds a label line for each sample whose read changed. The comparison streams its own progress and resumes completed pairs.

`sample_label.py from-population --population DRAWS.sqlite3 --tasks DIR --out DIR --limit N` writes sample records for the first N candidates of a substitute population.

## Input

Samples and golds are framed zstd JSONL ([framed-jsonl.md](../../judge3/framed-jsonl.md)). The producer can append to both files while the driver runs. A gold line is `{task, case, text, stream: {ids, model}}`, and its `gold_ref` is `run.digest` of that line. A gold line must be in `golds.jsonl.zst` before the first sample that refers to it.

A sample line has schema `study-sample-v1`:

| Field | Value |
| --- | --- |
| `sample_id` | `run.digest` of `{task, task_sha256, case, gold_ref, point, candidate}` |
| `task`, `task_sha256` | task name, and the SHA-256 of the task file bytes that the producer read |
| `case`, `gold_ref` | the gold program's case, and its gold line |
| `point` | `{body_path, clause_path, kind}` of a point in `gold.points()` |
| `candidate` | see below |
| `proposal` | the producer's own facts. They are kept as provenance and never become labels. |

A candidate has one of these kinds:

- `native_edit_identity`: `{identity, operation, text[, stream]}`. `identity` is the native edit identity that `gold.construct_identity` takes, `text` is the whole mutant program, and `stream` is the whole mutant program's `{ids, model}`.
- `body_replacement`: `{text[, stream]}`. `text` is the whole program, with the body at `point.body_path` replaced. `stream` holds the replacement body's tokens in the decoder context of gold up to that point. These samples get status `unavailable` until a native constructor for this kind exists.

`sample_label.sample_record(...)` builds a sample line and computes `sample_id` and `gold_ref`.

## Stages

Each sample becomes a member of `ROOT/population.sqlite3`, the population store that [population_consume.md](population_consume.md) describes. The driver runs these stages on each sample, in order. Each stage resumes its own stored result, and a stage that fails is recorded in the label line.

| Stage | Entry point |
| --- | --- |
| `reuse` | binds the historical observation of a mutant whose historical base label is intact |
| `materialize` | `population_consume.materialize_one` |
| `label` | `population_consume.label_one` |
| `normal` | `mech2.classify_normal.label_pair` |
| `witness_tests` | `mech.step2_check.WitnessTestSession` |
| `fit_split` | `mech3.pair_api.PairLabeler` |

`normal`, `witness_tests` and `fit_split` run only on base results of this root; a reused mutant keeps the results of the historical passes. Samples of one gold share one evaluator session. The all-target comparison runs in the `targets` command. Lib search and the model judge stay in `missing_steps`. The all-target comparison does not observe DET targets, so in a task with a DET form the target catalog stays incomplete and a pair without a positive result stays Unknown.

The pass stores and replay artifacts are in `DATA_ROOT/population_passes/<root name>-<hash of the root path>`, because the evaluator writes artifacts only under `DATA_ROOT`. The all-target store is `DATA_ROOT/ast/run/mech5/population/<the same name>/targets.sqlite3`. `ROOT/evaluator.json` is the corpus-v12 evaluator configuration with this root's task directory.

The runtime must have the `arclog` wheel that the checkout's native code needs. The driver appends `work/lm/.venv` site-packages after the runtime's own, for the packages that study runtimes lack (zstandard in older runtimes, pandas and pyarrow).

## Output

`ROOT/labels.jsonl.zst` has one line per sample per run that processed it. The last line for a `sample_id` is the current one. A line has schema `study-sample-label-v1`, with `sample_id`, `pair_id` and the fields of the joined read: `status`, `valid`, `grade`, `grade_reason`, `filter_class`, `normal`, `judge_eligible`, `missing_steps`, `attributes`, `facts`, `reason`, `attempt`, `filters`, `source_sha256` and `base_result_sha256`. `base_label` is the base mechanical label. `results` gives the status of each pass result. `stages` gives the outcome of each stage that ran.

| `status` | Meaning |
| --- | --- |
| `done` | a base mechanical result exists |
| `filtered` | the corpus filters rejected the observation; `filters` gives the class |
| `pruned` | static pruning matched the pair |
| `open` | the observation exists, and the mechanical result is missing |
| `unavailable` | the observation could not be made; `attempt` gives the reason |
| `rejected` | the sample line failed validation; `reason` gives the cause |

The label lines are a copy for consumers that read as the driver writes. `sample_label.reader(ROOT)` gives the population reader with this root's pass stores; its `read_pair(pair_id)` and `read_pairs()` give the current joined result of members.
