# Backlog

User-owned list of queued ideas. Sessions append on ask; one line per item.

## TODO

- Generalize `KeyedSetCompare<Key, Member>` to `KeyedSetCompare<Key, Pat, Member>`: pattern key as a type param removes the `ord` bridge (a87f7484 $Shape, `Occurrences`); stored-catalog callers instantiate `Pat = number` unchanged.
- Remove "single-set sites key on Unit" from every comp doc (`lib.dl`, `proposals.md`, solver-local comps); instantiation sites already show the keying.


## Pending

- `6cf79266` needs a patch to simplify the train 2 overlap.
- Mutation lint over `.dl` solvers: delete each negated body atom (and each rule), re-run all pairs; a surviving mutant marks structure the data doesn't instantiate. Informational report; candidate home `run_dl.py --lint`.
- Program similarity analysis over `programs/solvers/` to find representative programs for reference. Candidate signals: Consts-shape signatures, body relation graphs.
