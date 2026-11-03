from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = CODE_ROOT.parents[1]
MAIN_ROOT = REPO_ROOT
DATA_ROOT = REPO_ROOT / 'data-study'


def data_path(source):
    return DATA_ROOT / Path(source).resolve().relative_to(CODE_ROOT)
