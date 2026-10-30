# Framed JSONL storage

`framed_jsonl.py` is an opt-in shared storage API. No existing writer is switched
by this change. It does not evaluate, project or normalize records.

```python
from judge3.framed_jsonl import JsonlWriter, JsonlReader, iter_json

with JsonlWriter('pairs.jsonl.zst') as out:
    # On resume, complete frames (including complete unindexed tail frames)
    # are retained. Continue from out.committed_lines, not from line zero.
    for record in remaining_records:
        out.write(record)             # compact UTF-8 JSON plus LF
        # out.write_line(original_bytes) preserves an existing exact LF line

with JsonlReader('pairs.jsonl.zst') as source:
    row_bytes = source.read_line(123)  # one-based; seek to one frame
    for line in source.iter_lines(start_line=123):
        consume(line)                 # bytes; json.loads accepts them directly

for record in iter_json('old-pairs.jsonl.gz'):
    consume(record)                   # old plain/gzip also supported
```

## Disk format

Data is ordinary concatenated independent zstd frames, each with zstd content
checksum. Default level is 3. Frame targets are 1 MiB of UTF-8 data or 2048 lines,
whichever fills first. A line is never split between frames; an oversized line
is one larger frame. Raw lines require exactly one terminating LF and valid
UTF-8. `write()` emits compact JSON; `write_line()` preserves exact input bytes,
including CR whitespace. Plain/gzip readers preserve legacy line bytes and an
unterminated final line without modifying the original.

`pairs.jsonl.zst.idx.jsonl` is a small append-only index. Its header has
`schema: study-jsonl-zstd-v1`, `line_base: 1`, and advisory frame limits. Each
following entry has `first_line`, `offset` (compressed byte offset),
`compressed_bytes`, `uncompressed_bytes`, `line_count`, and `sha256` of the exact
uncompressed frame. Original line bytes, including all whitespace, are retained
and hash checked. Frame boundaries are storage details, not record identities.

`read_line()` is one-based; missing lines raise IndexError. `stop_line` is an
exclusive one-based bound. A reusable reader holds the small index and at most
one decompressed frame. Indexed reads seek directly; they do not replay the
compressed prefix. Old plain and gzip paths still work, with their existing
linear-seek cost. A missing logical plain path resolves to its sole `.gz` or
`.zst` sibling; ambiguous siblings fail instead of guessing.

## Append and crash recovery

There is one writer per file, enforced by a nonblocking OS file lock. A frame
commit writes and fsyncs compressed data, then appends and fsyncs its index row.
There is no per-line flush. Initial index publication is atomic and directory
synced. Explicit `flush()` and normal close commit a pending partial batch.
Exceptional context exit discards only uncommitted in-memory lines.

Resume loads index metadata and scans **only the unindexed tail**. Complete
orphan frames are indexed without reserializing or recomputing their records.
An unfinished final frame and unfinished final index row are truncated; completed
frames are retained. Corrupt complete/indexed data raises an error rather than
being treated as missing work. Reader snapshots expose complete tail frames
without mutating the files. A writer validates the last indexed frame before
append, and readers verify size, line count, zstd checksum and original SHA of
each frame they consume. Index loss/corruption is not silently a fresh run.

Writers resume their actual source input at `committed_lines`; calling code must
also retain its existing source/config identity. This storage module does not
invent resume policy or decide that an old native result is obsolete.

## Dependency and measurement

`zstandard==0.23.0` is a locked repo dependency and is installed by
`scripts/build_study_runtime.py`. Old plain/gzip readers import zstandard only
when using the new format. Existing immutable runtime builds are not rebuilt.

A bounded real corpus-prefix benchmark and direct append/crash checks are under
`DATA_ROOT/codex-adm/n-judgetool-framed-jsonl/`. They are not merge/run gates.
The index schema is versioned; independent frames require no dictionary or
external codec state. No current cache key or existing codec module is changed.
