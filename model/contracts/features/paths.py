"""Where the library finds the repo and its untracked data.

The library reads the task files, the lib registry and the solvers of the main checkout, also when its code runs from a worktree, since a
worktree holds no untracked file. `CONTRACTS_GEN` and `CONTRACTS_DATA` override the solver folder and the folder of the library's data.
"""
import os
from pathlib import Path


def main_checkout(root):
    """The main checkout of the checkout at root: root itself, or, for a worktree, the checkout whose .git folder holds the worktree's."""
    git = root / '.git'
    if git.is_file():
        return Path(git.read_text().split('gitdir:', 1)[1].strip()).parents[2]
    return root


MAIN = main_checkout(Path(__file__).resolve().parents[3])
GEN = Path(os.environ.get('CONTRACTS_GEN', MAIN / 'programs/arclog'))  # the solvers, as .arclog and .arcdata files
DATA = Path(os.environ.get('CONTRACTS_DATA', MAIN / 'model/contracts'))  # holds cache/ and corpus/
REGISTRY = MAIN / 'engine/lib/registry.sexpr'


def read_gen(path):
    """The text of the file `path` of a gen/ directory, read through `arclog_convert.readback.read_checked` of the main checkout: it raises `Stale` where the file is not current."""
    import sys
    if str(MAIN / 'src') not in sys.path:
        sys.path.insert(0, str(MAIN / 'src'))
    from arclog_convert.readback import read_checked
    return read_checked(Path(path))
TASKS = MAIN / 'data/tasks'
