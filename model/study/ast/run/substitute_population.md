# Source-occurrence substitute population

This additive generator draws one-edit substitutes independently at each direct
conjunct of each top-level RULE in the base population's gold programs. With
`--per-occurrence 1`, a relation with N source occurrences receives N requested
substitutes, regardless of its argument count. Historical `draw_specs`, records,
labels and pass stores are unchanged.

`StudyProgram.substitution_occurrences_json(point)` inventories direct native
conjunct paths, including unsupported blocks. `draw_substitutes_at` restricts the
existing native completion search to one occurrence. It shares native proposal,
binding, interface, whole-program checker, held-interface, stream, writer and
static-pruning rules. These are semantic validity rules, not deployment gates.

Run `substitute_population.py --output NEW_DB --counts REPORT.csv` with the
committed runtime. This is a full native dry draw, not task evaluation or labeling.
No inputs/outputs or target tables are acquired. The default program scope is
read-only distinct task/case identities from the base store; streams come from
the canonical task-local export via the shared inventory reader.

The WAL journal stores objects once (gold programs, mutant text, native identities,
producer provenance), each occurrence's own search receipt, and unique candidate
references. Every occurrence commits immediately with synchronous FULL. Resume
compares its actual source stream, occurrence and requested settings plus result
integrity; current code hashes are provenance only. Interrupted sites restart;
completed bounded/unavailable sites remain completed. Use a new output population
when changing the intended grammar. The single writer holds a file lock; reports
can read the live database through `--report-only` without write access.

Counts are derived at request time. The CSV separates requested, certified drawn,
selected distinct text, unsupported blocks, no primitive alternatives, exhausted
shortfalls, native bounds, unvisited alternatives, check/interface/held/stream
rejections, static-pruned candidates and pruning-unavailable calls. Candidate
failures may have multiple rule matches; the added native candidate exclusion
counter counts a statically rejected candidate once. Detailed native receipts
retain rule/diagnostic counts. Case acquisition failures stay explicit in failures.

The expected *requested* count is N times per-occurrence; the actual pre-label
substitute count is selected_unique from the dry draw. The generator does not
claim these two counts coincide. Whole-block proposals and wider native typed
interface mappings are subsequent population versions; this first part records
those gaps instead of silently omitting them. No outcome label influences drawing.

A corpus consumer reconstructs gold from objects[gold_ref], the candidate identity
from objects[identity_ref], and uses the existing native evaluator/filter pipeline
in a new output root. This generator does not copy that pipeline or claim label
results. Objects and references are content addressed; no prose/specification
hash invalidates completed work.
