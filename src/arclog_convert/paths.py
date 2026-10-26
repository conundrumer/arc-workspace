"""The directories the converter reads and writes. `main` of
`arclog_convert.convert` rebinds `OUT_DIR`, `MACROS_DIR`, `PLANS` and
`NAMES_DIR` and `COLUMNS_DIR` under `--out`, so a module reads them as attributes of this module
(`paths.PLANS`) and never imports them by name."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from arclog_convert import out as arclog_out


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

SOLVERS_ENV = "ARCLOG_SOLVERS"
"""Set, the directory the converter reads solver files from, in place of `programs/solvers`."""
SOLVERS = Path(os.environ[SOLVERS_ENV]) if os.environ.get(SOLVERS_ENV) else ROOT / "programs" / "solvers"
WITNESSES = ROOT / "programs" / "witnesses"


def out_dirs() -> tuple[Path, Path, Path, Path, Path]:
    """`gen/`, `gen_macros/`, `plan/`, `names/` and `columns/` of `arclog_out`.
    `convert_one` writes each solver's name map (`name_map`) to `names/` and
    its column map (`column_map`) to `columns/`, beside `gen/`, whose globs
    read only arclog and arcdata files."""
    root = arclog_out()
    return root / "gen", root / "gen_macros", root / "plan", root / "names", root / "columns"


OUT_DIR, MACROS_DIR, PLANS, NAMES_DIR, COLUMNS_DIR = out_dirs()
MACROS_ENV = "ARCLOG_MACROS"
"""Set, the expansion config applies: the pool's workers read it."""
