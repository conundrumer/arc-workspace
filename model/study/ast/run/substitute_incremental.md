# Incremental substitute populations

Part 2 adds only native typed-interface proposals. It leaves the historical and
part-1 draw APIs unchanged. `draw_added_substitutes_at` excludes baseline primitive
ASTs before any certification, using the original canonical proposer to identify
that set. It then uses the same whole-program, binding, held-interface, stream,
writer and static-prune checks as the existing completion domain.

The additions use native inferred scalar types and native row paths, including
record-field paths. Column spelling is no longer a type compatibility condition.
Fresh/key source arguments must survive the mapping; already-bound reads may be
omitted. Other sites use in-scope typed labels, legal zero or omitted existential
columns. Equality provides functional aliases without requiring a library peer
with identical column names. Mode/frame legality is decided by the full native
checker. Program relations and component ports come from the resolved graph and
native ProgramTypes, with earlier-declaration/no-cycle/scope checks, not an
inventory of earlier read atoms. Unknown compound-output schemas and nonfixed
library interfaces are counted explicitly rather than guessed.

Mapping enumeration is bounded to eight proposals and 512 traversal nodes per
target interface. Required makers are tried first. `domain_proposal_stopped`
records these shortfalls. No finite proposal miss is a proof about all possible
mutants or a label. Static exclusions retain the shared rule receipts.

`substitute_incremental.py` reads an immutable predecessor population as a
read-only View. Filled occurrences are inherited with no native call. Only empty
atomic source occurrences are routed to part 2. Source programs are recovered
from stored stream objects once per touched case; this reconstructs a native
handle, without task replay, source rescanning or target acquisition. Part-1
alternative checks are never repeated. Existing negative primitives are excluded
before certification, not retried after a checker failure.

The delta SQLite journal stores only its own objects/candidates and occurrence
facts plus one parent-store locator. Parent row integrity and exact parent result
bindings are validated on read; parent facts are not copied. Each occurrence
commits durably. Resume happens before native program setup and binds parent
facts plus actual profile/seed/deadline settings. Code hashes are provenance,
not current-file invalidators. Use a new delta for a deliberately new proposal
policy. The writer lock does not block read-only reports.

`View.rows()` derives the combined population. `--counts` writes an explicit
report, not an authoritative result store. It gives source gold uses, requested,
reused_selected, new_selected, selected_total, added proposals/attempts/pruning,
bounds and unavailable facts. `--report-only` uses read-only SQLite connections.
No grades or labels are written. Predecessor objects remain necessary to read the
new population; retain both databases.

## Part 3: whole-block delta

`--profile blocks-v3` routes only unfilled OR/IF/ALL/NOT-form occurrences from
its predecessor. It calls `draw_block_substitutes_at`; no atomic proposal or
previously completed draw is repeated. Use v2 as the parent and a separate v3
output. The same read-only View joins all three journals for pre-label counts.

OR proposals select one branch or omit one branch. IF proposals select the
successful then path or the guarded else path, swap branches, or replace the
conditional with a union. ALL proposals complement the universal, require an
existential match, require no match, or negate the body. These are candidate AST
transformations; native checks decide which are valid at each original scope.
No test rows, output labels or fitted result influence their construction.

A selected path must retain exactly the original block's exported labels.
Exports come from the canonical native `read::columns::made_labels` policy.
The constructor uses two alpha-distinct copies to keep private path variables
existential under OR's native export intersection. Required first-branch makers
are promoted at positive sites; the second copy joins shared exports and gives
private variables new native IDs. The ordinary checker authenticates binding
modes, scopes, types, frames and clause interface. No Python scope policy or
second evaluator is introduced. OR enumeration is bounded to the first 64
source branches; a proposal-bound receipt records larger cases.

The native identity JSON now recursively encodes bodies/blocks while keeping
historical atomic payloads byte-compatible. Public rehydration authenticates
both new block choices and already-stored typed-interface/equality choices.
No old draw needs to run again. Unit/empty-record sites inside blocks are checked
by the canonical native schema/checker. The editor preserves enclosing heads,
rejects overlapping edit paths, and refreshes display layout for compound
replacements using gold's namespace. The audit counts one selected whole
conjunct as one edit, excludes its descendants from untouched-leaf claims,
and retains exact checks for all leaves outside that subtree. Source-path
correspondence marks the replaced subtree without guessing descendant matches.
