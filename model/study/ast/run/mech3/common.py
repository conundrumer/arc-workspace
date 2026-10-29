"""Import shared source read-only; keep all mech3 outputs in shared data."""
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[2]))
from study_paths import CODE_ROOT,DATA_ROOT,MAIN_ROOT
OUTPUT_ROOT=DATA_ROOT/'ast/run/mech3'
for path in (CODE_ROOT/'ast/run/mech',CODE_ROOT/'ast/run',CODE_ROOT/'judgetool',CODE_ROOT/'judge3'):
    sys.path.append(str(path))

from mech.run import canonical,digest
