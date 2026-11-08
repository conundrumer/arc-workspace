"""productions_check.py [--union DIR] [--skeleton DIR] [--tasks T,T] [--show N]

The productions of each gold table of the union graph from the union (break_points.py --productions union) against those from the skeleton (--productions skeleton), with no job and no engine.
For each task and graph table it counts the productions of each source by QueryHash; for the QueryHashes of both, whether the input graph tables (with their output names) and the text agree.
The text is compared with each input written as its producer's QueryHash and the output name: the skeleton's closure gives the producer of a label, the union's identity check gives it (Gold.producers).
A QueryHash that only one source has is listed by where it comes from. A source that cannot give a production (an input in no graph table, or a label with no producer) is counted by its reason.

Run with the study runtime python:  PY -I productions_check.py   (about 20 s for the dev set)
"""
import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import break_points as B  # noqa: E402


def skeleton_text(p):
    """The skeleton production's text with each label written as its producer's QueryHash, the output name kept."""
    closure = p.rec['closure']
    n = len(closure)

    def put(m):
        i = int(m[1])
        return '<%s>' % closure[i] if i < n else '<own>' if i == n else '<local>'
    return B.re.sub(r'&r(\d+)', put, p.rec['program'][-1])


def union_text(gold, task, p):
    """The union production's text with each label written as its producer's QueryHash."""
    u = gold.union[task]

    def put(m):
        if m[1] == p.own:
            return '<own>'
        return '<%s>%s' % (u[p.producers[m[1]]]['query'], m[2])
    return B.FORM_REF.sub(put, p.text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--union', default=str(B.R.UNION))
    ap.add_argument('--skeleton', default=str(B.SKELETON))
    ap.add_argument('--tasks')
    ap.add_argument('--show', type=int, default=3, help='how many examples of each difference to print')
    a = ap.parse_args()
    gold = B.Gold(Path(a.union), a.skeleton)
    want = set(a.tasks.split(',')) if a.tasks else None
    c, shown, why = collections.Counter(), collections.Counter(), collections.Counter()
    gp = collections.defaultdict(dict)  # task -> QueryHash -> graph-prods line: the graph's own list of the graph tables that each query reads
    for p in B.set_files(a.union, 'graph-prods', 'dev'):
        for l in B.Z.open_text(p):
            r = B.json.loads(l)
            if 'query' in r:
                gp[r['task']][r['query']] = r
    for task in sorted(gold.tables):
        if want and task not in want:
            continue
        key_of_query = {t['query']: k for k, t in gold.union.get(task, {}).items() if t.get('query')}
        for g in gold.tables[task]:
            c['graph tables'] += 1
            U = {p.query: p for p in B.productions(gold, task, g, 'union')}
            S = {p.query: p for p in B.productions(gold, task, g, 'skeleton')}
            c['union productions'] += len(U)
            c['skeleton productions'] += len(S)
            c['graph tables with a union production'] += bool(U)
            c['graph tables with productions, none usable (union)'] += bool(U) and all(p.ins is None for p in U.values())
            c['graph tables with productions, none usable (skeleton)'] += bool(S) and all(p.ins is None for p in S.values())
            c['graph tables with a usable production in the skeleton and none in the union'] += any(p.ins is not None for p in S.values()) and not any(p.ins is not None for p in U.values())
            c['graph tables with a usable production in the union and none in the skeleton'] += any(p.ins is not None for p in U.values()) and not any(p.ins is not None for p in S.values())
            c['graph tables with a skeleton production'] += bool(S)
            c['graph tables with no production in one source'] += bool(U) != bool(S)
            for src, ps in (('union', U), ('skeleton', S)):
                for h, p in ps.items():
                    line = gp[task].get(h)
                    if p.ins is not None and line is not None:
                        c['%s productions whose input graph tables %s the graph-prods line of the query' % (src, 'equal' if {x[0] for x in p.ins} == set(line['reads']) else 'differ from')] += 1
                for p in ps.values():
                    if p.ins is None:
                        why[src, p.why.split('(')[0]] += 1
            for h in sorted(set(U) | set(S)):
                where = 'both' if h in U and h in S else 'union only' if h in U else 'skeleton only'
                c['productions ' + where] += 1
                if where != 'both':
                    continue
                pu, ps = U[h], S[h]
                if (pu.ins is None) != (ps.ins is None):
                    what = 'inputs usable in one source only'
                elif pu.ins is None:
                    continue
                elif {x[:2] for x in pu.ins} != {x[:2] for x in ps.ins}:
                    what = 'input graph tables differ'
                else:
                    tu, ts = union_text(gold, task, pu), skeleton_text(ps)
                    if tu != ts:
                        what = 'text differs'
                        if sorted(tu.replace('(', ' ( ').replace(')', ' ) ').split()) == sorted(ts.replace('(', ' ( ').replace(')', ' ) ').split()):
                            what = 'text differs, same atoms and tokens in another order'
                        else:
                            what = 'text differs, other tokens'
                        if shown[what] < a.show:
                            shown[what] += 1
                            print('text differs', task, g, h, '\n  union   ', tu, '\n  skeleton', ts)
                    else:
                        what = 'agree'
                c['both: ' + what] += 1
                if what != 'agree' and not what.startswith('text differs') and shown[what] < a.show:
                    shown[what] += 1
                    print(what, task, g, h, '\n  union   ', pu.ins, '\n  skeleton', ps.ins)
    for k, v in sorted(c.items()):
        print('%8d  %s' % (v, k))
    for (src, w), v in why.most_common():
        print('%8d  %s production unusable: %s' % (v, src, w))


if __name__ == '__main__':
    main()
