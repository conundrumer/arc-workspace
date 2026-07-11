# Backlog

User-owned list of queued ideas. Sessions append on ask; one line per item.

1. Mutation lint over `.dl` solvers: delete each negated body atom (and each rule), re-run all pairs; a surviving mutant marks structure the data doesn't instantiate. Informational report; candidate home `run_dl.py --lint`.
2. Program similarity analysis over `programs/solvers/` to find representative programs for reference. Candidate signals: Consts-shape signatures, body relation graphs.
