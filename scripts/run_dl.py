"""Run Souffle solvers against their tasks' train+test pairs.

Run with --help for the per-solver tooling.

A sentence a tool prints stands in an `mctx` call where the tool prints it.
"""

import sys

from dl.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
