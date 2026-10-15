"""The lint checks on a solver's form, one module for each part of the form:
`header`, the header and its keywords; `case_type`, the case type, its
glosses and markers; `witnesses`, the witnesses and claims; `components`,
the components a solver holds; `declared_types`, the types it may declare
and read; `open_value_fields`, the fields of `OpenValue`; and `sections`, the case sections. A module reads a helper of
another module of the package by its public name, and the package
re-exports nothing."""
