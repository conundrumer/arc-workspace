# Bounded native materialization

A compact native relation can hold the Cartesian product of several small row
sets. Evaluating its parts does not allocate or charge a flat row for every
combination. Previously `completed_rows` treated that compact value as an already
materialized table, expanded it without budget checks, and retained a boxed
extent vector for every combination. The same condition occurred in direct
relation/body annotations, fallback completion, and recursive input ports.
Packing and projection annotation could expand or copy that product again.

The saved `5dbc8537` body has products of 8,503,056 and 226,759,808 rows; its body
query alone completed in 184 ms. The separate `7b3084d4` INIT-key reproduction
has 48,640,000 rows on each of four examples and completed its body query in
49 ms. Native stacks locate both failures in the same `completed_rows` path,
rather than in CHOOSE option construction. These are baseline observations,
not measurements of a rebuilt candidate.

## One admission and traversal policy

`join::Materializer` borrows the native task session and the current operation's
`Limits`. It delegates to `Budget`, using the existing product, held-row,
TableWork, SessionBytes, deadline and cancellation checks. Admission precedes
vector reservation or product traversal. Flat input rows do not pay their
binding work twice; new output buffers pay for newly held rows. Periodic
zero-work budget checks interrupt traversals without inventing binding work.
`try_each_row` owns the one fallible product walker; legacy `each_row` delegates
to it and preserves its row order and empty-product semantics.

`completed_rows` returns an admitted Arc-owned matrix or the exact native stop.
All four callers propagate that result. The same operation policy serves
annotation formatting, lookup and key-evidence maps, internal-port copies,
value sorting/packing, projection maps and fallback walks. A stopped full
annotation is never retried as an unrestricted flat walk. Projected evidence
uses admitted projected rows; it does not reconstruct a stopped full matrix.
Physical table metadata and count-only entries are admitted before their output
headers, independently of logical product cardinality.

A packing stop leaves an explicit partial prefix and an unavailable suffix.
It does not turn missing buffers into completed empty relations. Native study
reports carry stopped packing evidence; stream/corpus adapters report the exact
packing stop, and `CaseTables.materialization_stop` exposes it to direct callers.
A stopped packed prefix cannot become a reusable prefix-cache result.

## Allocation ownership

The task session owns one atomic reservation ledger. Checked CAS admission
includes outstanding reservations alongside native intern/cache usage; dropping
a `SessionAllocation` releases its exact reservation once. Arc clones share
both retained data and the reservation. A genuine matrix, map, prefix or packed
buffer copy reserves its own ownership before allocation. Estimates saturate on
overflow; the stored reservation counter never saturates and later subtracts an
inexact value.

The common row estimate includes allocator/vector/hash slack. Packed values
allow eight cell-buffer widths during simultaneous sorting, native output,
conversion and owned Python buffer creation, plus per-row container overhead.
Each normal or projected annotation output reserves its own simultaneous
scratch/status/extent-copy allowance, including repeated interned value-run
cache hits. That retained lease covers the fallback scratch matrix too; a
periodic walk check alone is never its allocation admission.
Metadata admission separately covers physical entry/DET/projection headers,
nested strings/lists, dtype dictionaries and owner-class creation. These are
conservative admission estimates, not a promise that RSS equals the ledger:
interpreter infrastructure, allocator retention and consumer-created copies have
separate lifetimes. The fixed-size empty API envelope remains bounded even if
there is insufficient room for another table header.

Returned Python bytes/list subclasses retain the native capsule lease on each
actual escaped buffer/container. Scalars remain ordinary integers; bytes,
dtypes, list contents and serialized mapping keys are unchanged. A read-only
owner property prevents ordinary assignment/deletion from detaching ownership.
A private holder counts actual owned instances and drops its capsule at the
last instance, independently of heap-type garbage collection. Memoryviews keep
the original exporter alive. Copies subsequently made by consumers are the
consumers' ownership, rather than aliases of the producer's allocation.

## Operation lifetime and held queries

A study request creates one operation clock. Gold/mutant decoders, nested Reads
and final packing inherit that clock, cancellation and shared table-work count.
No nested query or packing adapter restarts the deadline. Retained caches and
Contents store allocation/assignment identity only, never a past operation's
limits. Stream replay records retain a stable task-session handle whose clones
share every intern/cache/fact/metric/reservation owner. A subsequent explicit
packing request starts its own operation, without changing the earlier replay.

The held-assignment context remains independent of allocation policy. Its full
receipt, selectors, exact native values and assignment/example/model axes are
preserved through bounded cache and error paths. No assignment re-search, row
substitution, frame guess, new stop kind or increased cap is introduced.

## Validation boundary

Source checks include the tables Python crate and the combined performance
patch. A real retained payload from `1efba499` remains 69,190 byte-identical bytes
with SHA256 `be7e91fd946483e7a4a6dcb1ceb1ce690e920cf53020e434076ad17f784bf5cd`.
The extracted owner implementation preserves escaped views and releases the
last owner without a cyclic-GC pass. This qualifies the wrapper implementation;
it is not a rebuilt native runtime pass.

After coordinator merge and immutable runtime build, replay both exact saved
mutants and run isolated `corpus.py --only 5dbc8537 7b3084d4` under an external
memory/watchdog limit. Do not use the live corpus directory. Runtime memory,
stop receipts and full corpus behavior remain pending until that check runs.
