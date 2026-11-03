"""The columns of each function's outputs as the dev row store records them (`OUTD/SET/rows/<task>.jsonl.gz`, `function` lines): for each function id (FunctionHash) and Name, the column types in the engine's order without Example, and the column labels.

Only the `function` lines are parsed, so a file's rows are never loaded.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
import gzip, json
from pathlib import Path

type Outputs = dict[str, dict[str, tuple[list[str], list[str], str]]]  # function id -> Name -> (types, labels, the name that a site gives the Example column, '' where there is none)

PREFIX = '{"t": "function"'
FOOTER = '{"t": "footer"'


def without_example(types: list[str], labels: list[str]) -> tuple[list[str], list[str], str]:
    """The column types without Example, their labels, and the name that a site gives the Example column. The store's labels have one for each column, or, where Example is the engine's own column (a pair's last), none for it: a site names that column `:E`."""
    if len(labels) == len(types):
        keep = [i for i, t in enumerate(types) if t != 'Example']
        example = next((':' + (labels[i] or 'E') for i, t in enumerate(types) if t == 'Example'), '')
        return [types[i] for i in keep], [labels[i] for i in keep], example
    return [t for t in types if t != 'Example'], labels, ':E' if 'Example' in types else ''


def load(path: Path) -> Outputs:
    """{} where the file is not there or not finished. Only the lines before the footer are read: supplement.py appends functions after it, and those would make
    the skeleton depend on whether supplement has run."""
    got: Outputs = {}
    try:
        with gzip.open(path, 'rt') as f:
            for line in f:
                if line.startswith(FOOTER):
                    break
                if line.startswith(PREFIX):
                    r = json.loads(line)
                    got[r['id']] = {o['name']: without_example(o['types'], o['labels']) for o in r['outputs']}
    except (OSError, EOFError, ValueError):
        return {}
    return got
