"""The lib's components called from Python. `lib_components.components`
holds one function per public top-level component of the lib, generated
from its `.comp` declaration by `scripts/context.py`. A call takes the type
arguments and the rows of each input relation, runs the component in
Souffle, and returns the rows of each output relation.

A value crosses as a Python value: a number as `int`, a symbol as `str`, and
a record as the `tuple` of its fields."""
