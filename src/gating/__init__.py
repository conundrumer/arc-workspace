"""The gate, which `scripts/gate.py` runs, and the test of whether an edit
of a Python file changes what a check runs (`edits`), which the merge
checks also take. The hunks of a change (`hunks`) import `edits`, and
the dependency record (`deps`, `deps_record`) imports both. Whether a
change can affect a command (`affects`) imports `deps` and `hunks`, and
`deps_record` imports it."""
