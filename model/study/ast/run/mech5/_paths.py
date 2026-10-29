"""Tracked study imports; persistent files live under DATA_ROOT."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
CODE_ROOT = HERE.parents[2]
sys.path.insert(0, str(CODE_ROOT))
from study_paths import DATA_ROOT

MECH = CODE_ROOT / 'ast/run/mech'
sys.path[:0] = [str(MECH), str(CODE_ROOT/'ast/run'), str(CODE_ROOT/'judgetool'),
                str(CODE_ROOT/'judge3')]
DATA = DATA_ROOT / 'ast/run/mech5'
