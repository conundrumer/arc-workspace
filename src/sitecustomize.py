"""Starts the record of this process's call (`script_calls`), where the
process runs a script under `scripts/` of the main tree. The tree is the
parent of `src/`; the main tree's `.git` is a directory, and a linked
worktree's is a file, so a call that runs a worktree's changed code
writes no line. This module runs at the start of every `python` of the
venv, so it imports nothing for a process that writes no line."""

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


_start()
