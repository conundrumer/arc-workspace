"""The gate, which `scripts/gate.py` runs.

- `gating.commands`: the gate commands, the stems each runs on, and the
  fixed inputs under `tests/gate/` they read.
- `gating.lines`: the lines a run prints above its last line, and the
  comparison of two output files.
- `gating.cpu`: the CPU that processes outside the gate's process tree use
  over an interval.
- `gating.deps`: what a command depends on, from a traced run of it, and
  whether a change can affect it.
- `gating.records`: the gate's records of the machine under `.cache/gate/`.
- `gating.deps_record`: the dependency record: the commands it selects for
  a change, the record a traced run writes, and its adoption.
- `gating.run`: one gate run: its passes, the holds they take, and the
  comparison and acceptance of their outputs and times."""
