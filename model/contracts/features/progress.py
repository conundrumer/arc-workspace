"""Model input layer: what a table adds to the tables before it. A table may hold a claim about the train output or the input that no table it reads,
directly or through others, holds, and it may reach changed cells, or state their output colors, where none of those tables does. A table's relation or
instance is one step, so the tables of one instance do not count as before one another. Read at the task's own examples, with how many steps of reads
lead to the table.
"""
import re

MAX_ROWS = 5000
TOK = re.compile('(?:\\w+\\.)?⟨c:[^⟩]*⟩|⟨t:[^⟩]*⟩')
WITH_OUTPUT = ('output claims held', 'output claims that no earlier table holds', 'first table where a column determines the output color', 'first table where every cell agrees with the output colors')
WITH_BOTH = ('first table where a column determines which cells change', 'changed cells that no earlier table covers, proportion', 'changed cells whose output color no earlier table states, proportion')
WITH_INPUT = ('input claims held', 'input claims that no earlier table holds')
_FIX, _WHICH, _AGREE = 'C,C determines the output color', 'C,C determines which cells change', 'C,C agrees with the output colors, proportion'


def holds(k, v):
    return v is True or (v == 1 and not isinstance(v, bool) and k.endswith(', proportion'))


def template(k):
    return TOK.sub('C', k)


def steps(graph, node, memo):
    """The longest chain of relations and instances that node reads, down to one that reads none."""
    if node not in memo:
        memo[node] = 0  # a cycle through an instance's own inputs and outputs adds no step
        memo[node] = 1 + max((steps(graph, u, memo) for u in graph.get(node, ()) if u != node), default=-1)
    return memo[node]


def static_claims(name, graph, before, memo):
    """{feature: value} of a table from the program's reads."""
    return {'steps from the input grid': steps(graph, name.split('.')[0], memo), 'tables before it': len({u.split('.')[0] for u in before})}


def claims(out, T, ex, earlier, sizes, gi, go, output_suffixes, input_suffixes):
    """{(table, feature): value}. out: the features of every table at example ex. earlier: {table: the tables before it}."""
    import features as F
    outs, ins = {}, {}
    for (name, k), v in out.items():
        if holds(k, v):
            if k.endswith(output_suffixes):
                outs.setdefault(name, set()).add(template(k))
            elif k.endswith(input_suffixes):
                ins.setdefault(name, set()).add(template(k))
    train = go is not None
    same = train and (len(gi), len(gi[0])) == (len(go), len(go[0]))
    covers, states = {}, {}
    if same:
        changed = {(r, k) for r, row in enumerate(go) for k, x in enumerate(row) if gi[r][k] != x}
        for name, tab in T.items():
            rows = F.rows_at(tab, ex) if name not in ('ex_input', 'ex_output') else None
            if not rows or len(rows) > MAX_ROWS:
                continue
            frames = dict(sizes)
            cs = F.cellsets(tab, rows, frames)
            covers[name] = {c for fr, S in cs.values() if frames.get(fr) == (len(go), len(go[0])) for c in S & changed}
            cols = tab['columns']
            spots = [i for i, c in enumerate(cols) if c[1] == 'Position' and c[0] in cs and frames.get(cs[c[0]][0]) == (len(go), len(go[0]))]
            paints = [i for i, c in enumerate(cols) if c[1] == 'Color']
            states[name] = {(r[i][0], r[i][2]) for i in spots for j in paints for r in rows if (r[i][0], r[i][2]) in changed and go[r[i][0]][r[i][2]] == r[j]}
    f = {}
    for name, before in earlier.items():
        o_before = set().union(*(outs.get(u, set()) for u in before)) if before else set()
        i_before = set().union(*(ins.get(u, set()) for u in before)) if before else set()
        mine = outs.get(name, set())
        f[(name, 'input claims held')] = len(ins.get(name, set()))
        f[(name, 'input claims that no earlier table holds')] = len(ins.get(name, set()) - i_before)
        if train:
            f[(name, 'output claims held')] = len(mine)
            f[(name, 'output claims that no earlier table holds')] = len(mine - o_before)
            f[(name, 'first table where a column determines the output color')] = _FIX in mine and _FIX not in o_before
            f[(name, 'first table where every cell agrees with the output colors')] = _AGREE in mine and _AGREE not in o_before
        if same:
            f[(name, 'first table where a column determines which cells change')] = _WHICH in mine and _WHICH not in o_before
            if changed and name in covers:
                f[(name, 'changed cells that no earlier table covers, proportion')] = round(len(covers[name] - set().union(*(covers.get(u, set()) for u in before))) / len(changed), 3) if before else round(len(covers[name]) / len(changed), 3)
                f[(name, 'changed cells whose output color no earlier table states, proportion')] = round(len(states[name] - set().union(*(states.get(u, set()) for u in before))) / len(changed), 3) if before else round(len(states[name]) / len(changed), 3)
    return f
