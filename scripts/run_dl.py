"""Run Souffle solvers against their tasks' train+test pairs.

Usage:
    uv run python scripts/run_dl.py                    # run all .dl solvers
    uv run python scripts/run_dl.py <stem>             # run one
    uv run python scripts/run_dl.py --audit <stem>     # fill sweep + mutation report
    uv run python scripts/run_dl.py --sweep <stem> [cap]   # conditional fill sweep
    uv run python scripts/run_dl.py --mutate <stem>    # structural mutation report
    uv run python scripts/run_dl.py --propose <stem>   # proposers vs stored Color fills

For a single stem, encodes each example's input grid as fact lines on stdin,
invokes `souffle` on it (linking the functor library; see build_functors),
reads the output relation from stdout, compares to expected output grid.

Both CLI paths also lint each solver body (see dl.lint) and print style
findings, and fit-check each solver carrying a `Fit` comp (see run_fit).
"""

import sys

from dl.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
