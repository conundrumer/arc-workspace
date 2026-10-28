# Extent queries under held assignments

The component export can evaluate a mutant under a cached gold assignment that
its own determination would not propose. The rows of that intervention are
native results under `ParameterValues::determined`. An extent query that searches
the mutant's determination domain instead can have no matching assignment, even
when the downstream row and its frame have a derivation under the intervention.
Matching projected assignments after that search does not recover the missing
query evaluation.

The tables assignment-context dispatcher now selects between two modes. Search
uses `Decoder::assigned`. Held mode evaluates every original full assignment in
its original order through the existing `Evaluation`, on the same task, session
and checked program. Only the query's exported DET assignment is projected. A
missing required DET is an error, not a request to search for another value.
The existing native parameter-schema checks still apply.

The relation and body exporters use this dispatcher. The extent derivation uses
it for widened bodies, recursive input ports and separate key evidence. Nested
queries use the parent operation's limits and work counter. A held root clones
the caller's absolute deadline and cancellation state; it does not start another
deadline. The dispatcher also replaces the two former fixed-assignment loops in
the body and component exporters.

## Assignment identity in proofs

Each native table records an assignment layout. A searched table has Search
layout. A held table retains a shared receipt with the original full ordered
assignments and the checked source owner. The receipt contains identity metadata
and native relation references, not an evaluator or operation limits. Receipt
bookkeeping is counted once per shared allocation in cache byte estimates;
referenced relation storage is not counted again.

One selector is used by widened-body gathering, input-port evidence, key evidence
and earlier-table frame lookup:

- Two tables with the same held receipt use the exact choice ordinal.
- Different held receipts do not authorize an ordinal or a projected-value join.
- A held query can use a searched table only when every DET required by that
  source matches the full held assignment, using native row equality. A missing
  required DET supplies no proof.
- Search queries retain the native compatible-assignment rule. All selected
  proof entries contribute to frame consensus.

The query context retains the full held assignment even when its table interface
exports only a subset. Cached ordinary relation prefixes remain Search tables.
They are not relabelled with a later held receipt. Model ordinals from separate
queries are not used as a join key. A missing or conflicting proof remains
unresolved.

## Observed case and limits

The saved 736a9ebc replay of task 14754a24, pair beginning `0007c7c2`, has identical
gold and mutant values for the held `r9` relation, its Connectivity output, its
BoundingBox output and the held `r16` relation. Their row counts are 89, 89, 18 and
5. The gold Box annotations resolve, while the mutant Box annotations do not;
the native collection and extent entries record no stop. The held `r9` value is
outside the mutant's proposed domain. The corrected projected-column metadata
already identifies the relative-frame maker on both sides.

The context fix makes downstream queries evaluate that actual held dependency.
It does not supply a mutant body witness for an arbitrary forced DET row, infer
a frame from the expected grid, or substitute gold annotations. Genuine missing
frame laws, conflicting proofs and native stops remain explicit. Verification
of the changed native behavior requires a committed runtime and exact-record
replay; compilation alone does not establish it.
