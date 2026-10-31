"""Per-option features for the relation pick: where an option lies in the read graph of the program so far, and how its
column types fit the labels in scope.

`option_features` is not a feature: it scores one option of a relation-choice row (`relrows`). A row of a file that
predates the read graph has no `prefix_bases`, `prefix_depth` or option `dag`; its DAG features are 0.0. Relation and
column names that a program's author wrote are compared only for equality within a row, never read as words.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r14b import _sub   # noqa: E402


def _dag(option):
    return option.get('dag') or {}


def option_features(row, option):
    """Features of one option of a relation-choice row (`scope`, `prefix_bases`, `prefix_depth`, `options`), the same keys
    for every option. `derived`: the option has `dag`; `reached`: its `path` is not None; `path`: 1/(1+path), 0.0 when
    None; `depth_step`: `dag.depth` less `prefix_depth`, and `deeper`: it is > 0; `sibling` and `method`: `dag.sibling` and
    `dag.method` as 0.0 or 1.0; `prefix_base`: `dag.base` is a base the prefix reads; `typed`: the option lists column
    types; `join_types`: the column types that equal or are subtypes of a type in scope, `join_share`: that count over the
    column count, and `new_type`: a column type not in scope."""
    dag = _dag(option)
    bases = set(row.get('prefix_bases') or [])
    scope = row.get('scope') or []
    types = option.get('types') or []
    path = dag.get('path')
    step = dag['depth'] - (row.get('prefix_depth') or 0) if dag.get('depth') is not None else 0
    joined = sum(1 for t in types if any(_sub(t, s) for s in scope))
    return {'derived': float(bool(dag)),
            'reached': float(path is not None),
            'path': 1 / (1 + path) if path is not None else 0.0,
            'depth_step': float(step),
            'deeper': float(step > 0),
            'sibling': float(bool(dag.get('sibling'))),
            'method': float(bool(dag.get('method'))),
            'prefix_base': float(bool(dag) and dag.get('base') in bases),
            'typed': float(bool(types)),
            'join_types': float(joined),
            'join_share': joined / len(types) if types else 0.0,
            'new_type': float(any(t not in scope for t in types))}


FEATURE_FUNCS = {'dag': option_features}  # the table that relcheap.py --plugin reads
