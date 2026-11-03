"""Study source in this checkout; shared data in the main worktree."""
from pathlib import Path
import sys

CODE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = CODE_ROOT.parents[1]
sys.path.insert(0, str(REPO_ROOT / 'src'))
from engine.checkout import main_worktree

MAIN_ROOT = main_worktree(REPO_ROOT)
DATA_ROOT = MAIN_ROOT / 'work/lm/data-study'


def data_path(source: str | Path) -> Path:
    """The shared data directory corresponding to a study source directory."""
    return DATA_ROOT / Path(source).resolve().relative_to(CODE_ROOT)


if __name__ == '__main__':
    print(DATA_ROOT)
