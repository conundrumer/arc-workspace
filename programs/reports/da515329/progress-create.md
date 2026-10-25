# da515329 progress

- interference: `run_dl.py da515329` lint, recursion finding ("only the `skip`, `step`, `take` inputs of a `Take` instance may read its relations, through an atom whose every variable another atom of the clause grounds"). A `Take` state that holds the four arm tips cannot be grounded by a static atom, so the first draft, a lockstep walk over four-tip states, was rejected. Cost about 10 min of design. The draft was replaced by a walk of one arm whose other three arms are its C4 images about the center.
- delay: `run_dl.py deletions da515329` stopped at `timeout 120` (exit 124). Cost 2 min. The check stays open.
- delay: `run_dl.py da515329` reached the 20 s per-pair limit on train0 and test0 while the walk took its state atoms after the domain enumeration. Leading the `take` clause with the instance atom that binds the state brought the run to 7 s. Cost about 2 min.
