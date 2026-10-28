# Held assignment schemas

A held gold FITS relation remains an exact native relation in the original task
session. A mutation can change even an upstream DET's checked schema: removing
the last use of a label makes whole-program inference drop that column.
That relation cannot be consumed as a value of the differently shaped mutant
parameter. Evaluation returns a native fault; it does not truncate, project,
re-intern, or search for a replacement assignment.

`Driver::parameter` checks the native relation arity against the checked parameter
schema before returning determined rows. The body table constructor also checks
all attached DET assignments, including dependencies whose rows were not read,
before publishing the table. The packed writer retains its arity assertion.

Real-record diagnosis: runtime `6108dd6e`, task `0becf7df`, case `$Line`, body
`[6,0]`, one deletion at `[6,0,4]`. The source event log records exactly one spec
for that draw. Removing the `&r0` atom from `DET &r8` removes the final use of
`&r0.Col2`; its native schema shrinks from three columns to two. Replaying that
identity alone reproduces the historical packing assertion (3 versus 2) in
44 milliseconds. The last corpus heartbeat at `[5,0]` is not the identity.
Evidence and the isolated probe are in `ast/run/packing-0becf7df/`.
