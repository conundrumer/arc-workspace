# Streaming DET full BODY refresh

`det_full_body_run.py` owns orchestration/publication only. `det_full_body` and the existing exporter own native identity, raw BODY acquisition, schema, kept/TRAIN/model and geometry validation. No column inference or rowset reconstruction is added to the driver.

The operator freezes `codex-adm/n-featapi/det-full-body-design/selection-5460.json`: 5,460 DET pairs at 973 points. The driver invokes one shared `ReplayEvaluator` and `export_pairs` in task/point groups, with `det_full_body=True`, `include_det=True`, `current_native_names=True` and the original point root as `existing_points`. The provider inherits validated non-G files/Tn numbering without case acquisition and chooses full G from complete stored raw BODY, matching persisted full acquisition, then fresh original-scope native acquisition. Only the last route needs gold_kept/gold_body work. Other clause kinds are untouched.

A persistent source checkout is required: private receipt implementation references must stay resolvable. Run the data-root `codex-adm/n-featapi/det-full-body.cmd COMBINED_REVISION [RUNTIME_DIRECTORY]`. Its default interpreter is the existing recorded f89c4bd9 runtime. The driver compares native build inputs to the merged source, rejecting incompatible runtime reuse before acquisition. No new runtime is necessary for a Python-only merged change whose native inputs remain identical.

## Publication and discovery

Output root: `DATA_ROOT/feat-exp/det-full-body-v1`.

- `generations/<selection-digest>/<point-id>/pairs/<pair-id>/pair.json` and `points/<point-id>/point.json`: stable final paths from acquisition onward; not visible through the publication index until the entire selected point validates. Existing relative pair-to-point paths remain valid.
- `published-points/<point-id>.json`: atomic, authoritative discovery record. Schema `study-det-full-body-publication-v1`, contract `det-full-body-train-v1`, status `complete`, `point_json`, `pairs` mapping pair IDs to pair.json paths, `generation`, and `artifact_manifest`. All paths are relative to DATA_ROOT. No private receipts, reader names or test data are included in this index.
- `manifest.jsonl`: append-only publication notifications. Ignore a trailing incomplete line. Discovery files remain authoritative if a crash occurs after publishing an index but before appending its notification.
- Each immutable generation has `artifact-manifest.json` binding public relative filenames, byte sizes and raw SHA256 hashes.
- `operator/points/`, `operator/private/`, `operator/unavailable/`, `operator/progress.jsonl` and `operator/summary.json`: private acquisition states, failure reasons and run status. They are not feature input.

A feature consumer selects a listed pair and its point from the same published generation. A point without a discovery file is not yet available under the full-BODY contract: do not silently combine an old projected pair with a new full G or fall back to old DET fields. Base fstore stays unchanged and remains explicitly readable under its previous contract. Feature readers can consume completed points while later points run.

## Resumption and fixes

A single publisher lock prevents concurrent writers to this output; it fails promptly rather than waiting. Published points are reused after raw-file manifest validation. Staged successful pairs are reused through the source-owned validator; lost result lines recover deterministic saved private receipts without reevaluation. No table JSON reload is performed by the driver.

A terminal failure is not retried under the same source/runtime/deadline/driver attempt key. A new source attempt revisits only failed/missing pairs, retaining valid staged packets and existing completed G through provider receipts. A completed artifact with a bad receipt is preserved for diagnosis, not silently re-evaluated. Independent points continue; failed points remain unindexed. Interrupted `.building` trees are retained outside published generations.

The initial refresh rebuilds X for the 5,460 affected DET pairs and G/metadata at 973 source points. Existing projected JSON cannot supply discarded cells, so these public tables require new full-layout serialization. Native evaluation is avoided wherever a complete matching raw payload or full acquisition is already valid. Available tables, grids, library files and numbering are reused, not recomputed. No Rule/INIT/CHOOSE or full Group1 rerun occurs.
