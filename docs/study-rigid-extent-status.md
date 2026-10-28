# Native rigid output frame evidence

The fault class was a valid native output being reported as an invalid program
because it has no clause-based frame-size derivation. The all-geometric-column
export introduced in `070178ae` exposed this condition: previously, only Box
columns with a named made frame entered extent derivation.

`eval/rigid.rs::Assembly::placements` materializes D4 images of an assembly's
canonical readings. These are not rows of the source clause. Accordingly,
`flows.rs::Flows::flows_visiting` explicitly replaces the frame provenance of
D4-moved part columns with `SourceFrame::Unknown`. Copying the source frame or
matching the output to untransformed source rows would fabricate evidence.

`extents.rs::derive` now handles this native-output contract explicitly. It
leaves slots without a native extent proof unset. Every original table, row,
geometric column, and assignment remains exported; unset slots have status
`2` (unresolved), not `0` (no grid), with absent extent cells `[-1, -1]`.
Independent Position or known grid-frame proofs retain their normal meaning.
Actual relation-evaluation faults and stops are unchanged. No expected output
dimensions, task names, or observed fault identities enter this decision.

The dispatch was audited against every decoded top-level form. Clause, CHOOSE,
and INIT already have derivation handlers; RIGID_DET was the missing native
case. OUT's interface is Position/Color and uses direct evidence. CLAIM, ALTS,
and DEMONSTRATED are rejected by the standalone study-program boundary.
Unexpected form/kind combinations still report a derivation fault. The fix
therefore covers all native rigid outputs, including future tasks and parts,
without weakening errors from malformed derivations.

Candidate-runtime reproduction on `968f0e95` showed the regression at task
`409aa875`, case `$Glyph`, native tables 31 and 32, form 22: a Box column with
empty global frame produced "the rows of a RIGID_DET form are not derived".
The supplied replay contains 24 records of this class across six gold cases;
the `6108dd6e` baseline has none. Post-fix runtime confirmation requires a
fresh immutable build and the same replay; a successful compile alone does
not establish that runtime result.
