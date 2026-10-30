# Prefix-U feature publication

`prefix_feature_export.py` joins completed stored prefix packets without arclog,
replay, kept matching, model alignment or numeric Ident correspondence. It reads
both complete DEV packets and the full-run compact acquisition container,
authenticates explicit refs (including original-SHA gzip sidecars), adapter
source/runtime/atomic-query receipts, native column and entry-parent maps, local
family coverage, and same-context external available refs.

The public layout is `prefix-u-full-body-train-v1`, separate from the old fstore.
Actual physical columns, typed cells including extents, row multiplicity/order,
TRAIN filtering, TASK broadcasts, Undefined (`rows:null`), zero-model families
and zero-parent universes remain unchanged. Each parent and Ident namespace
belongs to its actual native context. Local models are never zipped.

* `inputs/points/POINT/CONTEXT/`: native independently checked prefix syntax,
  native available correspondence, Tn index, and available TRAIN table packets.
* `inputs/pairs/PAIR/KEY/`: X BODY table and native checked candidate-prefix
  syntax. No full original program, later forms, G, outcomes or private reports.
* `labels/POINT/CONTEXT/G.json.gz`: G only, or explicit unavailable G. This is a
  label tree, never a feature input. G-only failure does not hide valid X.
* `private/PAIR/KEY/receipt.json.gz`: authenticated acquisition refs and the
  explicit public/label file hashes. Does not authorize loading a live native
  payload or relabeling an old universe.
* `published-pairs/PAIR.json`: atomic discovery after publication. The input
  path and separate label path are explicit. Point/context paths are immutable;
  different source/native contexts cannot overwrite one another.

Tn IDs are **new context-local IDs**, assigned in the actual native packed
available inventory order. Each index entry carries the native table, selector,
form path, graph and physical-column correspondence. No legacy kept-only Tn is
inferred by name or ordinal. Consumers use this explicit index. No old fstore
row packet or feature-payload verdict is copied. The checked prefix/candidate
syntax and actual fields/frames are the metadata on this layout; no native
nf4f computation is fabricated from old kept packets.

Publication authenticates the explicit f6428307, 5f01bf6b and 530bf8e7e fixed runtimes
against their exact wheels/native binaries. Repeat `--runtime-ready` for the
ready receipts in a mixed store. Each X/G packet selects its own matching
binary/build; a default or first runtime is never grafted onto another context.
If equal binaries make a build ambiguous, only the packet's actual installed
native path can disambiguate it. All supplied ready refs participate in resume
keys. Existing exact f642 publications are retained through the pinned source
predecessor bridge: only the small discovery index advances, never the row
files, original private receipt, runtime, universe or Ident namespace.

A complete ee2431d7 packet is not a proof of this universe: it remains untouched
and is refused for real publication. Old DEV readbacks require `--preview`;
they write only below `preview-only/`, with
`recorded-prefix-universe-preview-v1` and explicit unproven coverage. Preview
output is not a production layout. The cancelled compile-only compatibility
request is not used. New native results are joined directly, without replay.

All large public packets use the canonical lossless `paused_storage` compact
JSON/gzip codec. Existing validated pair output is reused by exact acquisition,
G, context, runtime-ready and join-code keys plus public-file SHA. Unavailable
results are operator records keyed by the exact discovery/code/runtime, never
negative labels; changed discovery or code retries only the affected item.
The native status and exact `report.reason` are retained separately, including
held-interface and unfinished INIT schema faults hidden by generic adapter
messages. Nothing is deleted, and no acquisition process is controlled.

Run the data-root command `codex-adm/n-eval2-prefix-feature-join/publish.cmd`.
It serializes stored data only; it can be run incrementally and again when
acquisition ends. It does not reevaluate native rows. A loader must explicitly
select this row-universe layout and use only the `inputs` tree for features.

The final affected-only retry uses `runtime-body-replacement-530bf8e7e`.
`publish-retry.cmd` supplies that ready receipt alongside f642, with optional
5f01 when that build actually has stored contexts. Exact earlier multi-ready
publications reuse their original row/label/proof files through the pinned
e2d3a5c4 source predecessor. Adding runtime authority is not a native row replay
or a claim that old native scopes became equivalent.


## Publisher work reuse

The offline join orders tiny discovery records by point and actual context before
loading row packets. It retains only one context's read-only G/available data and
validated common-table results. Every shared source and output still has an
initial complete SHA check; dev/inode/size/mtime/ctime changes invalidate cached
hashes or decoded values. Common cell validation is reused only for the same
authenticated source packet/table with identical actual native physical schema,
column aliases, parent/entry/model maps, family coverage, U and Ident namespace.
Each unique X still receives full validation. No row or model alignment is
inferred. Context changes drop retained row trees before cyclic collection;
automatic cyclic GC is disabled during this acyclic JSON-only loop and restored
on exit. File-digest metadata caches are bounded separately.

Shared Tn, point metadata and G files are verified/written once per matching
context instead of repeatedly parsing, hashing and comparing their entire row
trees. G native/source proofs remain private and are checked once with their
source refs reauthenticated through file stamps on reuse. The canonical codec,
public packets and raw row order are unchanged. Existing publications and
unavailable operator records produced by the exact 6cb20226 predecessor are
retained with their original refs; matching runtime-ready lists need no index
rewrite. Changed discovery/source/context still retries only that changed item.

Switch by stopping the old publisher at a completed-pair boundary and restarting
the same command against patched source and the same output root. Do not run
two publishers against the same output. No native replay or acquisition occurs.
