"""The model of a solver as the handbook defines it, with no Datalog in it,
and solving over an engine.

Each type of the model carries, through `engine.quotes`, the handbook words
that define it, quoted as written. The package has no private module:
every module that `checker` reads is public, with a docstring, and no
module is kept only to re-export another."""
