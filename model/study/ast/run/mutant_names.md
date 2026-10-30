# Stable mutant names and unique text

A decoded mutant inherits the source program's per-form native LabelId display
namespace. Surviving IDs keep their gold spellings; only IDs absent from that
namespace allocate a new name. Unused gold names remain reserved. Authored
programs keep their existing layout. This metadata never changes the checked
AST, edit identity, stream tokens, frame identity or held assignments.

`StudyProgram::label_names` is the shared presentation accessor for program
text, original-path node text, BODY views, typed sites and correspondence.
`render_sites::export_with_names` accepts an exact checked prefix and one names
map per retained form. Its inference still runs only on that checked prefix;
callers select scoped native IDs, never pair names or label ordinals. The
unseeded checker export delegates to the same inference implementation.
Packed table labels remain their actual wire metadata. A physical column is
linked to a display label by native correspondence, not spelling equality.

Gold names may make an edited join unrepresentable because an unchanged local
maker shadows its outer label. Authored sources keep their existing binding
guard. Decoded mutants with colliding live spellings are checked through the
ordinary native reader/binder and exact stream round trip, in both drawing and
identity rehydration. This preserves legitimate OR/IF branch-local scopes;
an unrepresentable edit is excluded rather than renaming an untouched label.

The completion domain admits each exact resulting mutant text once. Distinct
edit paths are not distinct output candidates when they print the same text.
A duplicate does not fill the requested count, so traversal continues for a
new candidate. The caller's point guard covers K/operation buckets as well.
The policy receipt is `complete-domain-unique-text-gold-names-v7`.

## Measurement and qualification

`mutant_names.py` scans stored pair text without evaluating a task. It uses
native gold AST paths to mask the selected atoms and compares the remaining
printed tokens. It reports exact duplicate full text per source/point and
writes pair IDs and source locators. It reads only leading JSON identity/text
fields; large unused evaluation and native payloads are not decoded. Gold
metadata is cached and duplicate memory is bounded to one point. A targeted
`--only-ids` pass reads only requested rows from their source files.

An unmodified record field can lose its explicit wrapper when its label takes
the field's name. The comparator therefore checks each unchanged prefix before
advancing to the next edit; it never assumes that prefix kept its old width.
An unavailable comparison is reported separately, not counted as unaffected.

`qualify_mutant_names.py` reconstructs only supplied native edit identities.
It requires unchanged historical stream ids/model flags/paths, a source-text
round trip to the same stream, and unchanged text at preserved native leaf
paths. It writes new program objects and source-bound repair receipts, never
rewrites corpus records or labels. Named fixture exports include gold/mutant
text and native structured metadata. `--draw-fixtures` also checks exact-text
uniqueness and deterministic draw prefixes at the duplicate example point.
Run the named fixture checks alongside the full repair export and report any
failures as they occur; they do not gate merging or starting that export.
