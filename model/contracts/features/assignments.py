"""Model input layer: how a table at one assignment stands to the same table at the task's other retained assignments. A table holds the rows of its
query under one choice of the task's parameters, and these features say what that choice changes: whether the rows depend on it, whether the query
gives rows at one choice alone, and how many of the table's features depend on it. They read no name and no value of a parameter.
"""
LIMIT = 16  # the retained assignments up to which a feature compares tables
MAX_ROWS = 5000  # the rows of a table at an example up to which a feature compares them

ACROSS = (' across assignments', ' at every assignment', ' at some assignment', ' at this assignment alone', ' with these rows, proportion', ' vs the other assignments')  # the features of this module

_memo = {}


def claims(name, tab, ex, others, sizes, gi):
    """{feature: value} of the table `name` at example ex. tab: the table at this assignment, with its columns under the features' tokens. others: the
    same program's tables at each other retained assignment, under their given names."""
    import features as F
    rows = F.rows_at(tab, ex)
    if rows is None or len(rows) > MAX_ROWS or not others:
        return {}
    types = [c[1] for c in tab['columns']]
    theirs = [t[name] for t in others if name in t]
    tables = [t for t in theirs if F.rows_at(t, ex) is not None]
    if len(tables) != len(theirs) or not tables or any(len(F.rows_at(t, ex)) > MAX_ROWS for t in tables):
        return {}
    key = (id(rows), ex, len(tables))
    held = _memo.get(key)
    if held is not None and held[0] is rows:
        return dict(held[1])
    mine = F.row_set(rows, types, tab.get('ident_values'))
    sets = [F.row_set(F.rows_at(t, ex), types, t.get('ident_values')) for t in tables]
    every = [mine] + sets
    distinct = {frozenset(s) for s in every}
    counts = [len(s) for s in every]
    f = {'rows distinct across assignments': len(distinct), 'same rows at every assignment': len(distinct) == 1, 'empty at some assignment': min(counts) == 0,
         'rows at this assignment alone': bool(mine) and not any(sets), 'assignments with these rows, proportion': round(sum(s == mine for s in every) / len(every), 3)}
    f['rows vs the other assignments'] = 'equal' if len(set(counts)) == 1 else 'most' if len(mine) == max(counts) else 'fewest' if len(mine) == min(counts) else 'between'
    if len(distinct) > 1:
        plain = dict(tab, columns=[(n, ty, fr) for n, ty, fr in tab['columns']])
        plain.pop('views', None), plain.pop('counts', None)
        own = F.table_features('', plain, ex, dict(sizes), {}, (gi, None))
        differ = set()
        seen = {frozenset(mine)}
        for t, s in zip(tables, sets):
            if frozenset(s) in seen:
                continue
            seen.add(frozenset(s))
            other = F.table_features('', dict(plain, rows=t['rows'], ident_values=t.get('ident_values', {})), ex, dict(sizes), {}, (gi, None))
            differ |= {k for k in set(own) | set(other) if own.get(k, 'ABSENT') != other.get(k, 'ABSENT')}
        f['features that differ across assignments, proportion'] = round(len(differ) / len(own), 3) if own else 0.0
    if len(_memo) > 4000:
        _memo.clear()
    _memo[key] = (rows, dict(f))
    return f
