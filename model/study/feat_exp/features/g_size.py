"""G20 Size: how many rows the candidate table X holds.

Replaces `base.x_rows` and `base.x_empty_share` (K2). The counts of M2 and the cell count of N3 compare X with the
train grids and belong to other quantities.
"""
from featlib import feature


def _counts(p):
    """Row counts of the models of X, one per (assignment, example, model); the examples are the train inputs and, where X has test entries, the test inputs. A table without an Example column holds
    one entry per train input, so an entry with no row is a model with no row. A table with an Example column holds
    every example in each entry: an example of the task that has no row there is a model with no row."""
    x = p.x
    ex = x.examples(tests=True)  # the test inputs are examples of X too
    out = [len(rows) for models in ex.values() for rows in models]
    if any(c.type == 'Example' for c in x.columns()):
        assignments = {e['assignment'] for e in x.all_entries}
        have = {k for k, models in ex.items() if any(models)}
        out += [0] * sum(1 for a in assignments for e in p.examples() if (a, e.index) not in have)
        if x.has_test:
            out += [0] * sum(1 for a in assignments for u in range(len(p.test_inputs)) if (a, ('test', u)) not in have)
    else:
        seen = set()
        for e in x.all_entries:
            seen.add((e['assignment'], e['train'] if 'train' in e else ('test', e['test']), e['model']))
        have = {(a, t, m) for (a, t), models in ex.items() for m, rows in enumerate(models) if rows}
        out += [0] * len(seen - have)
    return out


@feature
def g20_size(p):
    """G20 Size: `rows`, the mean row count of X over its models (per example), and `empty`, the share of models with
    no row. None for a table with no model.

    Needs: partial. Monotone: partly (`empty` yes: an empty model stays empty; `rows` no: a new column can multiply rows).
    """
    n = _counts(p)
    if not n:
        return None
    return {'rows': sum(n) / len(n), 'empty': sum(k == 0 for k in n) / len(n)}
