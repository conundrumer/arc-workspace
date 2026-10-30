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
