# Normal-form facts

`classify_normal.py` applies the writer's normal constraint set to stored streams and native prefix buffers. `normal_policy.py` supplies the adapter and the existing writer check. The pass performs no program replay. Labeling passes may process every pair; study uses the shared normal reader to exclude non-normal and unavailable mutants from its read-time counts and fits.

The authoritative store is `DATA_ROOT/ast/run/mech2/normal.sqlite3`. Its `metadata` entry `schema` identifies `normal-facts-v2`:

```sql
pairs(pair_id PRIMARY KEY, source_sha256, code_sha256, gold_point_id,
      normal, diagnostics_json, fact_sha256)
gold_points(point_id PRIMARY KEY, origin_pair_id, source_sha256, code_sha256,
            normal, diagnostics_json, fact_sha256)
producers(code_sha256 PRIMARY KEY, manifest_json)
metadata(key PRIMARY KEY, value)
```

`pairs.normal` is the mutant check's true/false/null fact. Gold checks occur once in `gold_points`; a pair holds their point key. The point key is the canonical JSON digest of task, case, point and clause, obtained from the upstream pair. `origin_pair_id` locates the source used for the gold check. Source hashes bind the original corpus records; no base label, source locator, operation, K or base-result copy is stored. Producer manifests bind the classification code, runtime and dependencies. Fact hashes bind their canonical payloads as implemented by `facts.payload`.

`diagnostics_json` retains reasons and failed one-row probe sites from this pass. Native snapshots, their row counts and layouts remain with their owning source. Status, eligibility, conservative writer result, grades and counts are derived at read time. The store contains no summaries, historical result copies or document hashes.

Consumers import `mech2.read_normal`. The boolean API is `is_normal(pair_id, *, source_sha256=None, base_result_sha256=None, database=None, reader=None)`. Only a valid classified normal mutant returns true. For bulk access, use `with NormalReader() as reader` and `reader.load_normal(pair_id, *, source_sha256=None, base_result_sha256=None)`. Its constructor accepts `database=None, *, base_database=None`. Defaults resolve from `study_paths.DATA_ROOT`.

Rich results contain `normal`, `status`, `eligible`, `absence_reason`, gold attributes and a durable reference. Classified false has `absence_reason="non_normal"`; missing/stale evidence has status `open`, while a completed unavailable classification has status `unavailable`. Both have `absence_reason="normal_unavailable"`. The legacy `load_normal(database, pair_id, *, source_sha256=None, base_result_sha256=None, reader=None)` remains supported. Its `record` is a read-time view, not a stored copy.

The reader joins source bindings against the canonical base database when hashes are omitted. A supplied legacy base-result hash is checked against the current base row; base-result changes alone do not invalidate normal facts. It uses short read transactions and caches source hashes while their filesystem signatures stay unchanged. Readers are worker-local and expose `close()` as well as the context-manager interface.

Compact an existing store after deploying the updated reader:

```sh
/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 /Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python /Users/davidlu/code/arc-workspace/model/study/ast/run/mech2/compact_normal.py
```

Compaction validates the old result hashes, producer compatibility, classification extraction and dependencies. It preserves all current mutant and gold classifications in one atomic transaction, removes the duplicated tables and legacy `summary.json`, and never opens the base database for writing. A failed validation leaves the database unchanged. Existing v1 records remain readable during deployment through a bounded compatibility check for this storage rewrite. The check binds the reviewed predecessor and the exact extracted policy source.

For new work or resume:

```sh
/Users/davidlu/code/arc-workspace/scripts/run_heavy.py --cpus 1 /Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python /Users/davidlu/code/arc-workspace/model/study/ast/run/mech2/classify_normal.py
```

The producer commits each pair durably and streams done/total, elapsed time, rate and ETA. It resumes every fact whose source record matches; producer manifests are provenance, and a code change does not invalidate a fact. `--reclassify` classifies every pair again and replaces the stored facts. `--retry-unavailable` retries null mutant classifications while preserving completed facts. Aggregation belongs to the read-time join.
