"""Run Souffle solvers against their tasks' train+test pairs.

Run with --help for the per-solver tooling.

A sentence a tool prints stands in its module's `MESSAGES` table, so the next
check written puts its own there.
"""

import sys

from dl.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
