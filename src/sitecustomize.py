"""Starts the record of this process's call (`script_calls`), where the
process runs a script under `scripts/` of the main tree, and the count of
its instructions for the gate (`instructions`), where the gate asks for
one. The tree is the
parent of `src/`; the main tree's `.git` is a directory, and a linked
worktree's is a file, so a call that runs a worktree's changed code
writes no line. This module runs at the start of every `python` of the
venv, so it imports nothing for a process that writes no line and counts
nothing, and it names `instructions.COUNT_ENV` by its value."""

import os
import sys


def _start() -> None:
    tree = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    if not sys.argv or not sys.argv[0] or not os.path.isdir(os.path.join(tree, ".git")):
        return
    script = os.path.realpath(sys.argv[0])
    if os.path.dirname(script) != os.path.join(tree, "scripts"):
        return
    import atexit
    import script_calls
    script_calls.start(tree, script, sys.argv[1:])
    atexit.register(script_calls.record)


def _count() -> None:
    path = os.environ.pop("ARC_GATE_INSTRUCTIONS_FILE", None)
    if path is not None:
        import instructions
        instructions.count_to(path)


_start()
_count()
