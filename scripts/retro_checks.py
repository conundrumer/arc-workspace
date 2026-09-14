"""Run the tree's checks and print what each one reports, as JSON.

    uv run python scripts/retro_checks.py

The test suite, the handbook render, and a run of every solver. Each one runs
to completion, whatever an earlier one reported. The checks take minutes, and
nothing but stdout is written. dl.checks runs them.
"""

import sys

from dl.checks import main

if __name__ == "__main__":
    sys.exit(main())
