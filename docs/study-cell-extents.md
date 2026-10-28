# Native geometric cell extents

Fresh native CaseTables export `tables.extent_columns` for every scalar
Position, Box and Offset column, including columns whose global frame name is
empty. For each entry `e`, `entries.extent_status[e][r][k]` is a nested list
of u8 codes, with one metadata element per entry, one row per native sorted
value row, and `k` indexing `tables.extent_columns[table]`:

* 0: `no_grid`, positively proved by native semantics/provenance. Offset has
  no reference grid. Constants/proposer columns that explicitly give no frame,
  and copies of those proved columns, also carry this classification.
* 1: `resolved`; the native reference extent is determined for this cell.
* 2: `unresolved`; missing/ambiguous provenance is not proof of `no_grid`.

`entries.extent_offset` retains the existing layout: two int32 cells (height,
width) for each `r,k`, with `[-1,-1]` for no_grid/unresolved. A resolved pair is
positive. Empty/undefined/stopped entries have no row annotations; native
extent faults/stops remain explicit. The nested status list has no extra
buffer, offset or stride. Projection rows have the analogous
`projection_rows.extent_status`, indexed by the projection's geometric
columns in projection-column order.

Position's singleton semantics determine its reference extent from its exact
native margins. No-grid proof takes priority over that computation. Box
extents use native grid sizes, widened derivations and exact source-row
provenance. Source lookup is allowed to use per-row extents even when the
source has no single global frame name. This export does not convert margins
to coordinates in Python or invent a grid for a template/constant.

For full held choices, `study_component_tables` adds the report key
`full_choice_extents`, schema `arclog-study-choice-extents-v1`. It retains
`choices[].assignment` (the exact full kept index), then `dets[].source_name`
and `examples[]` with `example_kind`, `example_index`, `model`, and `rows[]`.
Each row has its exact original `packed_row` and `cells[]` with native scalar
`column`, string `extent_status` and `extent` (positive pair or null).
This is produced from native gold relation tables under the exact cached
held values, checked against the held relation. A missing materialization or
nonmatching value is explicitly unresolved. Task-wide rows stay task-wide;
no arbitrary training example is attached and extents are never collapsed
across examples/models. Body DET subsets can reuse this authoritative full
choice annotation by identity, without computing frames in the renderer.

Old v4/v5 buffers retain their old extent layout and contain no new status.
Use equal fresh native body/relation rows only after checking exact historical
kept values, schema, choice/example/model and row identities. Conflicting
resolved extents remain a mismatch. Do not reinterpret old missing metadata
as no_grid, or inject foreign-session Ident values to recreate an observation.
