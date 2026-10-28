# CHOOSE extent derivation

CHOOSE retains a subset of its option relation; picking and never constraints
do not create new cells or frames. Its extent query compiles the original
checked `for` and `from` bodies with the native chosen-relation header.
Keyed candidates retain their for context; unkeyed candidates form the native
Cartesian option relation with the for rows. Negated exclusions are not
positive frame makers. The derivation walker then matches each selected
whole row against those options and uses the same source/provenance extent
analysis as clauses, retaining original lexical types and AST paths.

Runtime comparison for task b7cb93ac concept:
- pre-Unit runtime e02a0625: 24 relation tables, fault `the rows of a CHOOSE
  form are not derived`.
- runtime6108dd6e: the same 24-table fault.

The missing CHOOSE case in extent derivation predates Unit removal. This
change adds that derivation class, rather than suppressing its error or
assigning a guessed grid. Native work/model/time bounds and unresolved
source extents remain explicit.
