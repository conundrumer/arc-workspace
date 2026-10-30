# Synthesized sample labels

`sample_label.py label` gives synthesized samples the labels that corpus pairs get. A sample is a task, a gold point and a candidate program, for example a mutant of a gold program. The driver writes one label line per sample as soon as that sample is done, and a restart skips the samples that already have a line.

```sh
scripts/run_heavy.py --cpus 1 <runtime python> -B model/study/ast/run/sample_label.py label \
  --samples DIR/samples.jsonl.zst --golds DIR/golds.jsonl.zst --root ROOT --tasks <task directory>
```

Use one `--root` per sample population. `--limit N` reads only the first N sample lines. `--retry-unavailable` processes again the samples whose last line has status `unavailable`, for example after a constructor for their candidate kind exists. Progress with rate and ETA goes to stdout. The progress of the population phases goes to `ROOT/stages.log`.

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

Each sample becomes a member of `ROOT/population.sqlite3`, the population store that [population_consume.md](population_consume.md) describes. Samples of one gold that come one after another, up to `--batch`, share one evaluator session. The driver runs the `materialize` and `label` phases of `population_consume.py` on them, and reads the joined result through `mech.population_read.PopulationReader`. That result includes read-time static pruning and the grade. Follow-up passes (witness tests, normal form, reader and TEST fits, lib search, all-target comparison, model judge) stay in `missing_steps` until they have written results for the population.

## Output

`ROOT/labels.jsonl.zst` has one line per sample per run that processed it. The last line for a `sample_id` is the current one. A line has schema `study-sample-label-v1`, with `sample_id`, `pair_id` and the fields of the joined read: `status`, `valid`, `grade`, `grade_reason`, `filter_class`, `normal`, `judge_eligible`, `missing_steps`, `attributes`, `facts`, `reason`, `attempt`, `filters`, `source_sha256` and `base_result_sha256`. `base_label` is the base mechanical label. `results` gives the status of each pass result.

| `status` | Meaning |
| --- | --- |
| `done` | a base mechanical result exists |
| `filtered` | the corpus filters rejected the observation; `filters` gives the class |
| `pruned` | static pruning matched the pair |
| `open` | the observation exists, and the mechanical result is missing |
| `unavailable` | the observation could not be made; `attempt` gives the reason |
| `rejected` | the sample line failed validation; `reason` gives the cause |

The label lines are a copy for consumers that read as the driver writes. `PopulationReader(paths={"population": "ROOT/population.sqlite3"})` reads the current joined result of any member.
