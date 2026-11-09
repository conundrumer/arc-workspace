"""The directories the converter reads and writes. `main` of
`arclog_convert.convert` rebinds `OUT_ROOT`, `OUT_DIR`, `PLANS`,
`NAMES_DIR`, `COLUMNS_DIR` and `CASE_RECORDS` under `--out`, so a module reads them as attributes of this module
(`paths.PLANS`) and never imports them by name."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from arclog_convert import corpus, out as arclog_out
from engine import checkout


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

SOLVERS_ENV = "ARCLOG_SOLVERS"
"""Set, the directory the converter reads solver files from, in place of `programs/solvers`."""
SOLVERS = Path(os.environ[SOLVERS_ENV]) if os.environ.get(SOLVERS_ENV) else ROOT / "programs" / "solvers"
WITNESSES = ROOT / "programs" / "witnesses"
CORPUS = "gen_check"
"""The directory of `OUT_ROOT` that `arclog_convert.convert` writes the copies of the converted programs for the row-parity check to
(`arclog_convert.row_parity`)."""


def out_dirs() -> tuple[Path, Path, Path, Path, Path, Path]:
    """`arclog_out`, the directory of the converted solvers that goes with it (`arclog_convert.corpus`: `programs/arclog/`
    by default, `gen/` of `arclog_out` under `--out`), and `plan/`, `names/`, `columns/` and `case_records/` of
    `arclog_out`. `convert_one` writes each solver's name map (`name_map`) to `names/` and
    its column map (`column_map`) to `columns/`, and `convert_into` and `convert_cases` write the
    record of each solver's files (`arclog_convert.readback`) to
    `case_records/`. The globs of the directory of the converted solvers read only arclog and arcdata
    files and its `cases/` directories hold only case files."""
    root = arclog_out()
    return root, corpus(root), root / "plan", root / "names", root / "columns", root / "case_records"


OUT_ROOT, OUT_DIR, PLANS, NAMES_DIR, COLUMNS_DIR, CASE_RECORDS = out_dirs()


def records_of(gen: Path) -> Path:
    """The `case_records/` directory of the directory `gen` of converted solvers: `CASE_RECORDS` for `OUT_DIR` and for
    the `programs/arclog/` of any checkout, and `case_records/` beside `gen` for any other directory, such as the
    `gen/` of a `--out` directory or a kept copy of an earlier conversion."""
    gen = gen.resolve()
    return CASE_RECORDS if gen == OUT_DIR.resolve() or gen.parts[-2:] == checkout.ARCLOG.parts else gen.parent / "case_records"
