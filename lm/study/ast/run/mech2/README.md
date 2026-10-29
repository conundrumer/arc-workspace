# Stored normal-form attributes

`classify_normal.py` reads the base mechanical database, its original corpus records, the exported case streams, and stored full gold replay buffers. It writes `normal.sqlite3` and `summary.json` in this directory. It performs no decoding, program evaluation, or base labeling.

The policy comes from `writer.py`: `CONSTRAINT_SETS['normal']`, `Shape`, `passes`, `normal_form`, and `CaseRows`. The adapter supplies native buffers through the existing `native_storage.load_native` reader. It retains the writer's column, flow, assignment, and distinct-row rules. Both forms use the unchanged gold prefix; their stored stream prefixes must agree. Each changed top-level form is checked in full, including the writer's segment and INIT-key rules. Gold point identities retain task, case, point, and clause.

`pairs.normal` is true, false, or null. A null result records unavailable evidence. `record_json.mutant.writer_pass` preserves the writer's exact conservative result. When missing row evidence caused a failure, the adapter asks the same structural policy whether granting those unavailable one-row claims would change it. A possible change yields null; a failure that persists yields false. It adds no row semantics. Structural decisions can remain available when a native pack is missing. Non-normal means false; unavailable is reported separately.

The output uses SQLite WAL and synchronous FULL, with a commit for every pair. Resume checks the base source and result hashes, the current code manifest, and each saved result hash. Code receipts bind the actual writer, storage reader, registry, encoder, transport adapter, and library versions. Original source records are checked against their base hashes; native compressed ranges are authenticated by the shared reader. Published source files are treated as immutable during a run. A changed producer requires a fresh run of the affected receipts.

`gold_points` stores one result per point. `pairs` retains base label, operation, and K. The summary reports normal, non-normal, and unavailable counts separately, marginal and joint breakdowns, and failing gold points. Counts cover the stored base population; runtime and load omissions from the corpus remain outside it.

Run from any directory:

```sh
/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 /Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python lm/study/ast/run/mech2/classify_normal.py
```

Progress includes the indexing phase, done/total, elapsed seconds, rate, and ETA. The same command resumes. No classification or tests were run while preparing this entry point.

Consumers use `read_normal.load_normal(database, pair_id, source_sha256=..., base_result_sha256=...)`. A missing or stale receipt has status `open`; a completed undecidable record has status `unavailable`. Valid records expose the normal attribute, gold-point attribute, and durable reference. Non-normal mutants are excluded from scientific fits and counts by the study consumer; this pass writes attributes only.
