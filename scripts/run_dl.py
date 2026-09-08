"""Run Souffle solvers against their tasks' train+test pairs.

Run with --help for the per-solver tooling.

For a single stem, encodes each example's input grid as fact lines on stdin,
invokes `souffle` on it (linking the functor library; see build_functors),
reads the output relation from stdout, compares to expected output grid.

Both CLI paths also lint each solver program (see dl.lint) and print style
findings, and determination-check each solver carrying a `Determine` comp
(see run_determine).
"""

import sys

from dl.cli import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
