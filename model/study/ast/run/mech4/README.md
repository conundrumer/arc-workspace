# G-only lib recovery pass

This directory owns the bounded lib search over the stored base run's G-open queue hints. `prepare.py` reads the base records and current grade overlay. `run_lib.py` computes new library candidates through the shared `judgetool` evaluator. It writes only the mech4 data directory. The base labels and settled grades stay with their owners.

## Source prerequisites

Before execution, merge the shared `registry_atoms` and `available_atoms` additions supplied in `/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/mech4/patches/` into n-mech's `registry_plan.py`, the canonical `judge3.nonrender_metadata` producer, and n-eval's shared artifact-root, `retain_forms`, native slot/Ident matcher and exact cached-G context fixes. `run_lib.py` checks the callable interfaces before execution. These checks establish interface presence; runtime qualification is still required.

The canonical metadata producer currently reports changed DET and unsupported CHOOSE projections as unavailable. A qualified shared projection provider is needed to search those pairs. This pass records the limitation. It does not interpret judge admission exclusions as evidence about recovery.

No tests or native evaluations were run while building this source.

## Queue and new work

Labeling may process all pairs regardless of normal form. Study consumers apply the shared `mech2.read_normal` eligibility check when counting grades or fitting; non-normal and unavailable mutants are absent from those counts. This runner reports search attempts, not scientific grade counts.

The queue is a hint supplied by n-mech: base `overapproximation` without a train-verified witness, or a per-assignment `search_bound`, excluding base fit/error records and currently valid non-Unknown grades. Missing or stale grade evidence and a valid Unknown remain distinct in the queue receipt. This is not an authenticated containment or judge-admission certificate.

The pass reuses the base locator, source SHA, immutable base-result receipt, existing grade reader, native registry, canonical metadata/projector and graph policy. Fresh GOLD tables and supported point observers are acquired once per case/program/kept-context/input configuration and durably cached. This new work is required because the base does not store canonical lib candidate results or authoritative fresh target TEST rows. Saved target rows do not gate the fresh replay.

The initial grammar contains grounded typed registry predicates, fully-bound NOT, one computed lib relation, resolver-admitted available-table restrictions, and bounded conjunctions. The owner's registry helper supplies syntax and mode/type information. Candidate planning contains no Python lib evaluator. Source atoms preserve X as row supplier; available existential columns cannot supply target columns. The one-row-per-X rule is established only by the shared evaluator's independent native provenance proof.

Atomic candidates are screened together as named RULE tables in the original whole mutant program, preserving OUT. Each retained table is resolved by its exact inserted form. Failed batches split under the same total call/time budget; a failed batch alone never proves an individual clause refused. TRAIN comparisons require every expected kept assignment/input context. They produce an explicit ordered output projection. A TRAIN match receives a separate canonical TRAIN+TEST evaluation against fresh G, including its native one-row/provenance operations. Screening alone never establishes a recovery.

The bounded beams retain selectors and computations separately, then try conjunctions in the same evaluator. Candidate masks are never intersected or unioned in Python. Native family comparison does not zip model ordinals.

This finite grammar leaves structured/polymorphic groundings, deeper conjunctions, multiple computations, unions and other targets uncovered. A completed finite attempt with no recovery has `search_status=bound_unknown` and `full_space_covered=false`. It never supplies a negative proof or judge admission. Pairs step 3 later opens against other targets require a later pass.

## Durable journal and resume

The default database is `/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/mech4/lib.sqlite3`. SQLite uses WAL with `synchronous=FULL`. Every screened candidate, checked candidate and finished pair is committed as it completes. Native operations are reserved before execution, with an auditable ledger including split and provenance calls. A killed operation retains its declared deadline charge.

`queue` stores canonical JSON plus input/result SHA256. `records` has primary key `(kind,key)`, input/code/config/result SHA256 and zlib-compressed canonical JSON. Record kinds include `gold_case`, `registry`, `context`, `screen`, `batch`, `candidate` and `pair`. A pair key is the digest of `{pair: pair_id, target: "G"}`. References name the absolute database, table, kind, key and producer/result hashes. Native artifacts have directories scoped by code, runtime and run configuration.

A record resumes only when its input digest, full producer-code digest and configuration digest agree and its decompressed result digest verifies. Pair inputs bind source SHA, immutable base result and current grade availability. Candidate inputs additionally bind canonical metadata, fresh gold cache, task input data, native registry and runtime receipts. Legacy `spec_sha256` fields remain readable, and legacy prose-specification entries in code manifests are not read or checked. New runs record executable code and configuration provenance. Changed executable dependencies invalidate records; there is no unproved version-compatibility shortcut. Source changes during a pass stop it. A completed unavailable/bounded attempt is reusable for the same configuration; changing bounds or fixing a provider creates a new producer/configuration and retries it. Interrupted pair records remain resumable from committed inner work.

Native call count and time are bounded per pair across restarts for the same scope. A native operation already started can run to its own declared deadline; the ledger does not claim a shared native absolute deadline. Gold setup has its separate per-case limit. Disk reserve checks run before native calls and journal advancement. SIGINT/SIGTERM stop after durable work. Logs stream done/total, elapsed, rate, ETA and counters.

## Read-only reducer interface

With `model/study/ast/run` on `sys.path`:

```python
from mech4.read_results import load_result
result = load_result(database, pair_id,
                     source_sha256=current_source_sha,
                     base_result_sha256=immutable_base_result_sha)
```

`status="done", valid=true` means a completed attempt whose producer files and source/base/result bindings remain valid. It returns `search_status`, checked `mechanical_clauses`, `found_recovery` and the full durable record. A clause's receipt references the checked canonical evaluator result. `found_recovery` requires a normalized `recovery verified` clause with complete TRAIN+TEST and admitted X-row provenance. Partial-source outcomes are retained separately. The final grade and attributes are reduced by n-mech.

Missing, stale, interrupted or corrupt records return `status="open", valid=false` with a reason. A valid done `bound_unknown` or `unavailable` leaves other searches open. Every response has `final_grade=None` and `admission_authenticated=false` when valid; this API grants no admission.

## Coordinator commands after prerequisites merge

Run from the main checkout using the study's pinned interpreter. These commands are prospective until the prerequisite merges and source review are complete. Preparation uses stored data only. A limited queue produces an explicitly partial scope summary.

```sh
cd /Users/davidlu/code/arc-workspace
python3 scripts/run_heavy.py --cpus 1 --need soon work/lm/data-study/ast/run/runtime-5ee2f066/venv/bin/python -B model/study/ast/run/mech4/prepare.py --limit 20
python3 scripts/run_heavy.py --cpus 1 --need soon work/lm/data-study/ast/run/runtime-5ee2f066/venv/bin/python -B model/study/ast/run/mech4/run_lib.py
```

For the full queue, rerun preparation without `--limit`, then run the same pass command. Preparation rebuilds queue hints and preserves durable result records. All bounds are explicit CLI options; changing them changes the configuration. The default pair budget is 30 seconds and 24 native calls, with separate 2-second batch, 5-second verification and 30-second GOLD operation limits. The summary reports attempted scope completion, search outcomes and qualified candidate counts; scientific grade counts come from the reducer overlay.
