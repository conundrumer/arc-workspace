# v12 source binding

`move_v12.py` is the migration entry point. `source_bindings.py` is the shared
read-time adapter; its default journal is DATA_ROOT/ast/run/
corpus-v12-body-full/migration/bindings.sqlite3. No grades are stored.

The journal records each old source SHA, actual current SHA/locator, exact
backward JSON delta, input-footprint proof, and old/current base result identity.
Original hashes remain historical canonical-record identities, never aliases for different records.
A base row's source/provenance envelope is updated to the current locator. Its
old envelope and unchanged scientific facts are reconstructible through the
backward delta. Native compressed blocks resolve by their ORIGINAL content SHA:
borrow an exact v12 block, otherwise retain the original compressed block once
in the journal. Original manifests retain original physical native row indices,
schemas and selector maps. Every read still checks size/SHA. Physical v11 opens
are refused after activation when no binding exists.

`collect`, `scan`, `bind`, `apply` resume per source/pair. Source matching uses the
canonical pair identity and exact program/audit equality. Only requested task
files are scanned. Completed scans retain their file/request-set signatures;
framed sources seek past committed scan lines, legacy gzip keeps a sequential
cursor. The fast path compares authenticated G, X and full Gold manifests,
removing ONLY physical path/offset fields, together with exact held/maps and
inventory contract. The fallback compares canonical native model SET families
with one joint Ident mapping via the shared comparator. Available TRAIN+TEST
footprints use the shared kept reader, not a new decoder. Missing proof is not
an equality or a negative result.

When base search inputs match, `apply` reuses searches (including bounds) and
only reclassifies from v12's comparison/output/filter metadata. Otherwise it
binds the canonical algorithm to an input cache: unchanged main/sibling/redundant
search requests resume, changed positives get direct canonical verification,
and only remaining misses search. New or changed witness TEST applications are
owed to the existing full-Gold TEST checker. Compact Gold is not a substitute.
No lib search, all-target comparison, normal classification or judge is launched.
Their historical facts remain stored, accepted only for equal footprints, and
otherwise exposed as open. `owed` writes a framed, resumable changed-input report;
this report is not a second fact store or a command to rerun all those passes.

Genuine v11-only pairs are retained as legacy members INSIDE v12/migration/legacy,
with original canonical source records, exact program text and native content. Their new one-record
capsules use shared JsonlWriter, `.jsonl.zst`, and `committed_lines`. Existing
finished source files are not converted. SourceReader and direct consumers use
JsonlReader, indexed framed seeks, and persistent sequential legacy cursors.
Frozen judge source/answer/result files are not rewritten. Historical and new
post-cutover results both remain readable.

Reader integrations cover witness applications, normal status and DET fit keys,
fits split, lib source/receipt normalization, targets, host judge submissions,
static-pruning input identities, and population observation locators. Public
reader APIs stay unchanged. Normal/fit/lib/target policies are not copied.
Current production defaults use v12; the copied historical reference CLI is not
a production reader and is not invoked by these commands.

`audit` performs no evaluation/search. It prohibits physical v11 opens (including
caught attempts), checks source/delta/native closures once per content identity,
exercises the joined reader and frozen completed judge submissions, and checks
population locators. Its stamp binds base/source/native/metadata/population
state. `delete` rechecks that state under writer locks before removing the exact
v11 directory. This dependency check protects stored data; it is not a merge,
qualification or pilot gate. Old pinned writers must finish or be restarted on
the new source package before cutover/deletion. Paused jobs remain paused and
must use the new readers on any later restart; their result/artifact stores stay.

Commands, patches, logs and the migration report belong under DATA_ROOT/codex-adm/
n-mech-v12-move. The coordinator runs the long commands through run_heavy.

The public streaming source API is package-safe:

```python
from mech.source_read import SourceReader
reader = SourceReader(CODE_ROOT)
record = reader.record(base_row)
reader.close()
```

`base_row` supplies `task`, `source_sha256`, and
`source={"corpus": root, "file": relative_file, "line": one_based_line}`.
The path is `root/task/relative_file`. This supports population observations
and synthesized samples directly, with no migration entry. Framed `.jsonl.zst`,
plain `.jsonl` and historical gzip use the shared `JsonlReader`. A source must
be committed before publishing its locator. The hash is the canonical-record
digest used by the base label store. Constructor and `record(base_row)` remain
unchanged; callers own `close()` and can reuse one reader across samples.
