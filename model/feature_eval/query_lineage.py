"""What a program says of each of its tables with no row: where each column comes from, what its query does with it, and its place among the
program's reads. These are QueryVector entries, since two tables of equal rows can have different queries.

Each number stands under a name in the form of a shape: a column by its type, its greatest over the columns of that type, and for a word, whether some
column gives that word. The first version's `provenance`, `dependence` and `progress` modules define the numbers.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
for place in ('model/contracts/features', 'model/contracts/dev'):
    if str(REPO / place) not in sys.path:
        sys.path.insert(0, str(REPO / place))


def numbers_of(name, entry, types, steps, before):
    out = {'steps from the input grid': steps, 'tables before it': before}
    for feature, value in entry['table'].items():
        if isinstance(value, (bool, int, float)):
            out[feature] = float(value)
    for at, column in enumerate(entry['columns']):
        ty = types[at] if at < len(types) else ''
        for feature, value in column.items():
            key = f'?{ty} {feature}'
            if isinstance(value, (bool, int, float)):
                out[key] = max(out.get(key, 0.0), float(value))
            else:
                out[f'{key} :{value}'] = 1.0
    for first, second, feature, value in entry.get('pairs', ()):
        ty_first, ty_second = types[first], types[second]
        key = f'?{ty_first} {feature} ?{ty_second}'
        if isinstance(value, (bool, int, float)):
            out[key] = max(out.get(key, 0.0), float(value))
    return out


def flow_tables(arclog, np, program, tables, task_json):
    """The engine's tables with the flows of every column, which `query_numbers` reads."""
    import engine as E
    return E.FlowTables(arclog, np, program, tables, task_json)


def query_numbers(tb, text):
    """{table: {name: number}} of a program's tables, or no table where the first version cannot read the program."""
    import engine as E
    import progress as PR
    import provenance as PV
    try:
        prov = PV.provenance(tb, text)
    except Exception:
        return {}
    graph = E.reads(text)
    memo = {}
    out = {}
    for name, entry in prov.items():
        at = tb.names.index(name)
        types = list(tb.T['column_types'][at])
        upstream = E.upstream(graph, name)
        before = {node.split('.')[0] for node in upstream if node.split('.')[0] != name.split('.')[0] and node not in ('ex_input', 'ex_output', 'input')}
        out[name] = numbers_of(name, entry, types, PR.steps(graph, name.split('.')[0], memo), len(before))
    return out
