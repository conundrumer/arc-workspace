"""The model of a solver as the handbook defines it, with no Datalog in it,
and solving over an engine.

Each type of the model holds, through `engine.quotes`, the handbook words
that define it, quoted as written. The package has no private module:
every module that `checker` reads is public, with a docstring, and no
module is kept only to re-export another.

The modules that read a solver's program as the model stand in an order,
and each imports only those before it at its top level: `solver.graph`, the
relations of the program at each instance; `solver.model`, the model's
values, its case type, branches and cases; `solver.aggregate`, the
aggregate `Solver` and what `load` reads into it; `solver.columns`, the
column types of the program's relations and the reading of an `assign`
argument;
`solver.case_types`, where the program holds a case value;
`solver.case_columns`, what a base holds at a case column;
`solver.dependence`, which parts of the solver's own text each base's
derivation of `out` depends on; and `solver.cases`, the solver's cases.
`solver.form_checks` holds the checks of the solver's form that `load`
runs, and imports the modules they read at its top level. A function of
`solver.aggregate` that reads a later module imports it inside the
function."""
