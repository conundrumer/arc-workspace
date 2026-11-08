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
TableWork, request and assignment byte budget and cancellation checks. Admission precedes
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
The packing names each table of the unavailable suffix (`CaseColumns::left_out`).
`step_tables`, `successor_tables` and `base_tables` raise `RuntimeError` where
the suffix holds a table: the message gives the bound and names each table left
out, by its relation and the path of its form. A stop inside a table's entries
keeps the table, with those entries stopped, and raises nothing.
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
Packing admission also forecasts physical metadata container growth before
allocation. At the end of a table, the local pointer memo releases its cloned
types, sorted row orders and native relation owners. Temporary annotation
matrices and projection maps have also dropped at that boundary. The new
packing reservations then settle to the measured growth in owned column, name
and content-run-index capacities, using the same simultaneous Python-owner
allowance as prefix-copy admission. Coverage assertions reject an insufficient
preflight instead of silently reducing the retained allowance. Shared native
matrix leases remain independent and unchanged.

The eight-times allowance covers the copies that coexist while packing runs.
A returned `CaseTables` does not keep it. `PyCaseTables::of` takes the
reservations out of the columns (`CaseColumns::take_allocations`) after it makes
the Python objects, and each unshared reservation shrinks so that together they
keep the bytes of those objects: `sys.getsizeof` of each column object and of
each object that its items reach, with None, bools and the ints from -5 to 256
counted as 0, plus the `__dict__` of each owned `bytes` column. The Rust columns
drop when `of` returns. A result of `step_tables` also keeps the tables of its
stream for the next call's `before`, and with them the reservations of their
native rows and extents. Those tables are shared by the later results of the
same stream, and two streams of one decode, such as a call with
`by_assignment` and one without, each hold their own.
`Session.ledger_stats()` gives the three parts that the bound counts: the intern
table's bytes, the result cache's bytes and the reserved bytes of live buffers.

A deep prefix copy owns its new copy reservation exclusively. It does not keep
the original prefix's reservations alive after cache eviction. The existing
single session ledger releases the exact unused phase allowance through mutable
`SessionAllocation::shrink_to`; shared Arc owners cannot be reduced this way.
Pointer reuse remains local to one table, while content-run interning spans
the whole packed result. A packing stop ends the fold before any later table
can create a gap in the available prefix.

Metadata admission separately covers physical entry/DET/projection headers,
nested strings/lists, dtype dictionaries and owner-class creation. These are
conservative admission estimates, not a promise that RSS equals the ledger:
interpreter infrastructure, allocator retention and consumer-created copies have
separate lifetimes. The fixed-size empty API envelope remains bounded even if
there is insufficient room for another table header.

DET header admission uses the same latest-relation lookup as header placement.
The current relation takes precedence over earlier tables in both paths. Its
source allowance sizes paths, frames, slots and both native and file label
spellings without constructing the header before admission. Earlier unrelated
tables remain a borrowed name index; charging that entire index per DET would
charge it repeatedly as the prefix grows and stop small exports at the session
bound.

The corpus checker validates the available packed prefix even when its selected
clause lies in the unavailable suffix. Only a native `materialization_stop`
permits that missing clause: inspection records `clause_available=false`,
`clause_rows=null` and the exact stop. A missing clause without a native packing
stop remains a fault. Native dumps and stream observations retain packing stops,
so a bounded prefix cannot be mistaken for a complete or empty clause.

Each column object of a result, a `bytes` or `list` subclass, retains the
native capsule lease. The items of a list column are plain objects: a `bytes`
subclass carries a `__dict__` for its owner, ten times the bytes of a short
row's status. Scalars remain ordinary integers; bytes, dtypes, list contents and
serialized mapping keys are unchanged. Each column object holds the capsule in
its `_owner` attribute, so the capsule drops when the last column object of the
result drops. Memoryviews keep
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
