# Backlog

List of queued ideas. Sessions append on ask; one line per item.

1. Mutation lint over `.dl` solvers: delete each negated body atom (and each rule), then re-run all pairs. If a mutant survives, the data does not instantiate the deleted structure. Informational report; candidate home `run_dl.py --lint`.
2. Program similarity analysis over `programs/solvers/` to find representative programs for reference. Candidate signals: Consts-shape signatures, body relation graphs.
