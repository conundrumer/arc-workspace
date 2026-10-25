"""The directories the converter reads and writes. `main` of
`arclog_convert.convert` rebinds `OUT_DIR`, `MACROS_DIR`, `PLANS` and
`NAMES_DIR` under `--out`, so a module reads them as attributes of this module
(`paths.PLANS`) and never imports them by name."""

from __future__ import annotations

import sys
from pathlib import Path
from arclog_convert import out as arclog_out


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

SOLVERS = ROOT / "programs" / "solvers"
WITNESSES = ROOT / "programs" / "witnesses"


def out_dirs() -> tuple[Path, Path, Path, Path]:
    """`gen/`, `gen_macros/`, `plan/` and `names/` of `arclog_out`.
    `convert_one` writes each solver's name map (`name_map`) to `names/`,
    beside `gen/`, whose globs read only arclog and arcdata files."""
    root = arclog_out()
    return root / "gen", root / "gen_macros", root / "plan", root / "names"


OUT_DIR, MACROS_DIR, PLANS, NAMES_DIR = out_dirs()
MACROS_ENV = "ARCLOG_MACROS"
"""Set, the expansion config applies: the pool's workers read it."""
