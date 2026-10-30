# Study FITS and accepted output sets

The fault class was loss of judged-task semantics between task loading and
study evaluation. Both Python evaluator entry points discarded the
`JudgedTask` returned by `read_task_files`. `study_pair::train` compared each
model only with `Task.train.output`; `fits` required all those equality flags
to be true. This is not the native judge's FITS rule when an example has an
alternative output. Continuation OUT repeated the single-grid comparison,
and component/continuation kept selection inherited the faulty cached FITS.

The standalone evaluator and task-session constructor now retain and pass
the mandatory judged task. The study entry points reject judge metadata
whose train count or given outputs disagree with the evaluation task. A
shared private helper in `study_judgement.rs` constructs native closed-world
`PairCandidates`, collects the distinct model grids, and calls native
`judge::solves::solves` on the complete output set. No separate study rule
implements alternative acceptance:

- No alt: the output set must equal the singleton given candidate.
- Rule alt: it must equal either singleton candidate, not their union.
- Tiebreak alt: it must equal the candidate containing both grids, not only
  produce one acceptable model.

Undefined/non-grid OUT cannot fit; native stops/faults propagate without a
partial FITS assertion. Different models producing the same grid contribute
one grid to the output set. The existing model records remain unchanged in
meaning: `equals`, `differing_cells`, and continuation `expected_grid` compare
with the given output, even when a different grid is accepted by the judge.
Each train result separately reports `fits`, `fit_comparison`,
`distinct_output_grids`, `output_set_defined`, and `accepted_candidate_sizes`.
The new `fits` fields, not the per-model equality flags, decide kept gold
assignments. Component tables and continuation consume that same cached
decision, with no assignment re-search or substitution. Continuation's
conditional mutant OUT uses the same helper and reports its judged result.

The observed 89565ca0 concept stream is consistent. Under assignment 1,
train examples 0 and 2 produce the given grid. Train example 1 produces two
grids: one equals the given and one equals its recorded tiebreak alternative.
Direct native table inspection on 6108dd6e confirms both exact grids, while
the old study report records differences 0 and 6 and rejects the assignment.
The error predates Unit removal and the subsequent extent changes.

This change covers both evaluator constructors, both OUT evidence paths,
and every consumer of cached FITS, for all native alternative kinds. It does
not change task facts, native candidate semantics, model enumeration, caps,
stored parameters, or the meaning of the given-grid diagnostic fields.
Validation uses real identity replay after an immutable runtime build.
