# Backlog

User-owned list of queued ideas. Sessions append on ask; one line per item.

1. Remove "single-set sites key on Unit" from every comp doc (`lib.dl`, `proposals.md`, solver-local comps); instantiation sites already show the keying.
2. `6cf79266` needs a patch to simplify the train 2 overlap, and the solver needs to be updated to remove the overlap handling
3. Mutation lint over `.dl` solvers: delete each negated body atom (and each rule), re-run all pairs; a surviving mutant marks structure the data doesn't instantiate. Informational report; candidate home `run_dl.py --lint`.
4. Program similarity analysis over `programs/solvers/` to find representative programs for reference. Candidate signals: Consts-shape signatures, body relation graphs.
