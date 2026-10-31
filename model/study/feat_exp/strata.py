"""Point-group fields of a branch point, for gold and for a clause sampler's draws.

`point_fields(forms, i)` gives the fields of the point at line `i` of a program; the clause sampler calls it too, so that
gold and draws are grouped the same way. `forms` are the parsed lines of a program (`sexprs`).

    point_group  'DET', 'INIT', 'output', 'RULE depth 1', 'RULE depth 2' or 'RULE depth 3+'
    kind      the clause keyword (RULE, DET, INIT)
    output    whether `OUT` reads the clause's relation (`reads_of` its form), except at an INIT, whose X is a port table
    depth     the clause's longest path in the dependency DAG: 1 + the largest depth of the clauses it reads (a clause
              reads a relation as `&name` or `&name.port`) among the clauses before it, so 1 for a clause that reads
              only facts and library relations. A DET counts like any clause.
    d_out     hops from the clause to a clause that `OUT` reads, through the clauses that read it: 0 for a clause that
              `OUT` reads, None where no chain leads there. A REPORTING column: it reads later clauses, so no key may
              take it as input.

`depth` and `point_group` read the clause at the point in gold's program; they are labels of the point, the same for every
draw at it. `candidate_fields(forms, i, clause_text)` gives the same depth for a candidate clause, from its own reads
and the clauses before the point (`cand_depth`, `cand_facts_only`).

The scripts write these as columns `s_stratum`, `s_kind`, `s_output`, `s_depth`, `s_d_out`, `s_cand_depth` and
`s_cand_facts_only`.
"""
import re
from pathlib import Path

TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+')
COLUMNS = ['s_stratum', 's_kind', 's_output', 's_depth', 's_d_out', 's_cand_depth', 's_cand_facts_only']


def sexprs(text):
    out, stack = [], []
    for t in TOKEN.findall(text):
        if t == '(':
            stack.append([])
        elif t == ')':
            e = stack.pop()
            (stack[-1] if stack else out).append(e)
        else:
            (stack[-1] if stack else out).append(t)
    return out


def reads_of(x, out):
    """The relations (`&name`, port dropped) written anywhere in a parsed form."""
    if isinstance(x, str):
        if x.startswith('&'):
            out.add(x.split('.')[0])
    elif isinstance(x, list):
        for y in x:
            reads_of(y, out)
    return out


def _depths(forms):
    heads, body, kind = {}, {}, {}
    for j, f in enumerate(forms):
        if f and f[0] in ('RULE', 'DET', 'INIT') and len(f) > 1 and isinstance(f[1], str):
            heads[f[1]], kind[j] = j, f[0]
            body[j] = reads_of(f[2:], set()) - {f[1]}
    depth = {}

    def d(j):
        if j not in depth:
            depth[j] = 1 + max([d(heads[r]) for r in body[j] if r in heads and heads[r] < j], default=0)
        return depth[j]
    return heads, body, kind, d


def out_reads_of(forms):
    """The relations (`&name`, port dropped) that the program's last `OUT` form reads, or None without one."""
    outs = [f for f in forms if f and f[0] == 'OUT']
    return reads_of(outs[-1][1:], set()) if outs else None


def point_fields(forms, i):
    heads, body, kind, d = _depths(forms)
    reads = out_reads_of(forms) or set()
    dout = {j: 0 for j in body if forms[j][1] in reads}
    for _ in range(len(forms)):
        for j, rs in body.items():
            if j in dout:
                for r in rs:
                    if r in heads and dout.get(heads[r], 1 << 30) > dout[j] + 1:
                        dout[heads[r]] = dout[j] + 1
    k = kind[i]
    out = forms[i][1] in reads and k != 'INIT'
    st = k if k != 'RULE' else 'output' if out else 'RULE depth %s' % (d(i) if d(i) < 3 else '3+')
    return dict(point_group=st, kind=k, output=out, depth=d(i), d_out=dout.get(i))


def candidate_fields(forms, i, clause_text):
    """{cand_depth, cand_facts_only} of a candidate clause at line i, from the relations it writes (after the
    sampler's names are mapped to the program's) and the clauses before line i. A relation that no clause before the
    point declares (a sampler name left unmapped) is ignored."""
    heads, body, kind, d = _depths(forms)
    reads = reads_of(sexprs(clause_text)[0][2:], set())
    ds = [d(heads[r]) for r in reads if r in heads and heads[r] < i]
    k = sexprs(clause_text)[0][0]
    depth = 1 + max(ds, default=0)
    return dict(cand_depth=depth, cand_facts_only=max(ds, default=0) == 0)


def program_forms(point_dir):
    return sexprs((Path(point_dir) / 'gold.arclog').read_text())


def as_columns(pf, cf=None):
    """The row columns of point_fields' dict and candidate_fields' dict."""
    out = {'s_stratum': pf['point_group'] if 'point_group' in pf else pf['stratum'],'s_kind': pf['kind'], 's_output': pf['output'], 's_depth': pf['depth'],
           's_d_out': pf['d_out']}
    if cf is not None:
        out['s_cand_depth'] = cf['cand_depth']
        out['s_cand_facts_only'] = cf['cand_facts_only']
    return out
