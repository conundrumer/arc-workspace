"""Study source in this extract of the census commit; shared data in the main checkout."""
from pathlib import Path
import sys

CODE_ROOT = Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-kaggle-allocation-signal-heldout37-soak46')  # the data folder
REPO_ROOT = CODE_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / 'src'))
MAIN_ROOT = Path('/Users/davidlu/code/arc-workspace')
DATA_ROOT = MAIN_ROOT / 'work/lm/data-study'


def data_path(source: str | Path) -> Path:
    return DATA_ROOT / Path(source).resolve().relative_to(CODE_ROOT)
