# Stored population consumption

`population_consume.py plan|materialize|label --output <root>/population.sqlite3
--tasks <task-directory>` consumes the joined substitute journal or the sampler's
`study-candidate-v1` JSONL. It never draws candidates. Use a new output root for a
new generation population. Historical corpus files, labels and pass stores remain
unchanged. All-target comparison is not part of this driver.

## Stores and resume

The WAL membership database has `members(pair_id,input_sha256,payload)`,
`observations(pair_id,source_sha256,locator)`, `scans(path,signature,line,complete)`,
`attempts(pair_id,input_sha256,payload)`, and `metadata(key,value)`. Members keep
identity facts and references into the immutable generation object chain; they do
not copy observations or labels. Sampler object refs point into its own object
store. Membership inputs include exact task bytes. Native/code/settings receipts
are provenance, never a current-code invalidator. A changed member input requires
a new output population; missing additions may be appended to an existing one.

`plan --population <v3-draws.sqlite3>` resolves v3/v2/v1 selected candidates and
canonical mechanical pair IDs. It first uses existing labels' indexed source
locators, reading each referenced gzip once in line order. For remaining legacy
edit kinds it scans only the relevant published task files, parsing the small
leading identity header before decoding a matching full row. Typed/block edits
cannot exist in the historical population and cause no historical scan. File
checkpoints bind immutable file signatures and the eligible membership set;
unchanged completed scans resume. Interrupted gzip scans decompress the prefix
to seek, but do not reconsider completed rows. An extended membership set needs
another scan for that task because the old scan did not search for those IDs.

Reuse requires exact Gold text, native edit identity, current task bytes at the
original producer's canonical task location, and an intact evaluated source with
native observations. Candidate text must match, or native reconstruction must
prove its complete ids/model/paths stream equals the stored mutant stream. This
last pure construction handles writer-only naming changes without replay. No
table-row equality is used to infer assignment or native identity. Historical
producers did not save a task-file byte digest: their original native observations
and held contexts remain the authority, and this reader does not manufacture a
historical byte-hash receipt. Sources with missing task files or unproved program
binding remain missing rather than being silently reused. Stored incomplete
observations are retained as facts, not automatically replayed.

`materialize` selects only members with no observation reference, before native
setup. It reconstructs stored Gold and ValidMutant identities, never calls a
drawer, and uses `corpus.observe_constructed`: the exact shared evaluator,
assignment expansion, native storage and corpus filters. The historical worker
uses that same function. Its old per-clause sampling quota is not reapplied to a
new selected population. Original Gold handles/observations and native blocks
are shared within a case; existing observed pairs are never replayed to recreate
handles. A new session must acquire the Gold side for its new X in the same native
Ident namespace, rather than combine unrelated saved native IDs.

New observations use canonical `<root>/observations/<pair>/<task>/pairs.jsonl.gz`
and `run.json` source layout. Immutable session packs live under `<root>/packs/`
with absolute range/hash refs and canonical NativeStore block deduplication.
Pack bytes and source files/directories are fsynced before the per-pair SQLite
commit. A session never reopens/truncates a previous pack. Completed rows survive
a stop. A source atomically published just before a crash but not yet referenced
by SQLite is adopted on restart rather than evaluated again. Construction/runtime failures are own durable attempts and resume;
`--retry-failures` explicitly retries those attempts after a relevant fix. Native
incomplete outcomes are observations, not failure retries. No grades are stored.

`label` reuses input-valid historical results by reference and input-valid own
results before reading their sources. Only unlabelled semantic survivors run
`mech.run.label_record`, the same one-record implementation as the base runner.
The old post-filter quota alone does not prevent reuse/labeling of an observation.
Filtered sources retain their canonical filter facts instead of running a
mechanical search. A recoverable_gold rejection alone is recovered evidence,
so it is included, just as the original runner includes recoverable.jsonl.gz. New mechanical results go to `<root>/labels.sqlite3`; old
labels and follow-up evidence stay where their owners wrote them. This phase
performs stored-row mechanical search, not program replay or all-target search.
The native evaluator budget and mechanical search budget are selected with
`--seconds` for their respective phases; defaults are 1 second.

## Analysis entry point

```python
from mech.read_grades import StudyReader
with StudyReader(paths={"population": "/absolute/root/population.sqlite3"}) as r:
    for pair in r.read_pairs():
        print(pair["pair_id"], pair.get("grade"), pair.get("facts"))
```

The population reader opens stores read-only while writers commit in WAL. It
routes reused labels through the historical StudyReader, and new labels through
a StudyReader with separate population follow-up store paths. Both use the same
pruning and pure read-time grading policy. `population_passes` in `paths` can
override those new follow-up paths. Missing observations/results remain explicit
open members. Filter-only members expose canonical filter classes and Unknown
rather than asserting test-verified equivalence from a train filter. No joined
records or derived grades are persisted. `rowids` refers to membership rowids.

## Whole-new-clause adapter

`plan --candidate-stream <sampler>/candidates.jsonl` accepts the content-addressed
`study-candidate-v1` envelope documented in the DATA-root interchange contract.
The native-edit identity route works with the same materializer. An opaque
`native_body_replacement` remains a readable member with an unavailable attempt
until its native owner provides reconstruction into ValidMutant; arbitrary body
JSON or a Python input adapter cannot certify that native binding. The stream can
be published/imported independently. Sampler passing checks are proposal facts,
not a negative grade. No sampler check is promoted to a label by this adapter.
