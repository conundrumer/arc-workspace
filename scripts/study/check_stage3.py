"""Compatibility entry point; the committed corpus checker owns execution."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_study_pair_corpus import (  # noqa: E402,F401
    checkpoints, column, dump_native, inspect_native, main,
)

if __name__ == "__main__":
    main()
