"""RETIRED for graph files written after the graph dropped its bits: this script reads `path`, `minimax_path` and `bits` of graph-tasks-SET.jsonl / graph-prods-SET.jsonl, which gold_union_graph.py no longer writes. It runs only on graph files of earlier rounds. The shape of the expensive productions of one set's union graph. Writes expensive-productions-SET.json in work/lm/data-study/gold/gold-union and prints the summary.

  .venv/bin/python gold_union_expensive.py SET

- A production's text is its form in union-SET.jsonl (with union-SET-addendum.jsonl), joined to graph-prods-SET.jsonl by task and identity.
- Atoms: the relation atoms of the form, `(name (:` or `(&label (:`. Control: which of ALL, NOT, OR and IF the body holds. Ports: the top-level clauses of an INIT.
- Level: per-example where the form, or a form it reads at any distance, reads input, output, ex_input or ex_output; else task-level. A DET is task-level.
- Group, in this order:
  - INIT body: an INIT.
  - OR composition: a RULE whose body holds OR. `before_out` says whether a goal table of the task is one of its heads.
  - wide join: a RULE or DET without OR, of 6 or more atoms.
  - other.
- Expensive: over 20 bits. Each task's cheapest path and minimax path (graph-tasks-SET.jsonl) give the group of the production on it with the most bits.
"""
import collections, json, os, re, sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../..'))  # model/study
import study_zst as Z  # the union files are zstd streams or plain files, whichever is on disk

U = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'
EX = re.compile(r'\((input|output|ex_output|ex_input) ')
CUT = 20


def top(s):
    out, d, start = [], 0, None
    for i, c in enumerate(s):
        if c == '(':
            if d == 1:
                start = i
            d += 1
        elif c == ')':
            d -= 1
            if d == 1:
                out.append(s[start:i + 1])
    return out


def main():
    s = sys.argv[1]
    rows = {}
    for p in (U + 'union-%s.jsonl' % s, U + 'union-%s-addendum.jsonl' % s):
        if Z.exists(p):
            for l in Z.open_text(p):
                r = json.loads(l)
                rows[r['task']] = r
    text, reads, idents = {}, {}, {}
    for t, u in rows.items():
        for x in u.get('tables') or []:
            idents[t, x['key']] = [f['ident'] for f in x['forms']]
            for f in x['forms']:
                text[t, f['ident']] = f['text']
                reads[t, f['ident']] = x['reads'][f['ident']]
    memo = {}

    def per_example(t, i):
        if (t, i) not in memo:
            memo[t, i] = False
            x = text.get((t, i), '')
            memo[t, i] = not x.startswith('(DET') and (bool(EX.search(x)) or any(per_example(t, j) for k in reads.get((t, i), []) for j in idents.get((t, k), [])))
        return memo[t, i]

    goals = {}
    tasks = {}
    for l in Z.open_text(U + 'graph-tasks-%s.jsonl' % s):
        k = json.loads(l)
        tasks[k['task']] = k
        goals[k['task']] = set(k.get('goal') or [])

    def feats(p):
        t, x = p['task'], text.get((p['task'], p['ident']), '')
        ctl = sorted(set(re.findall(r'\((ALL|NOT|OR|IF)\b', x)))
        atoms = len(re.findall(r'\((?:&\w+(?:\.\w+)*|[a-z_]\w*) \(:', x))
        group = 'INIT body' if p['kind'] == 'INIT' else 'OR composition' if p['kind'] == 'RULE' and 'OR' in ctl else 'wide join' if atoms >= 6 else 'other'
        return dict(task=t, ident=p['ident'], bits=p['bits'], depth=p['depth'], kind=p['kind'], component=x.split()[2] if p['kind'] == 'INIT' else None, atoms=atoms, control=ctl,
                    ports=len(top(x)) if p['kind'] == 'INIT' else None, level='per-example' if per_example(t, p['ident']) else 'task', group=group, before_out=bool(set(p['heads']) & goals.get(t, set())), text=x)

    prods = [json.loads(l) for l in Z.open_text(U + 'graph-prods-%s.jsonl' % s)]
    byid = {(p['task'], p['ident']): p for p in prods}
    over = [feats(p) for p in prods if p['bits'] is not None and p['bits'] > CUT]
    under = [feats(p) for p in prods if p['bits'] is not None and p['bits'] <= CUT]
    path = {}
    for t, k in tasks.items():
        for which in ('path', 'minimax_path'):
            m = (k.get(which) or {}).get('max_production')
            if m and (t, m['ident']) in byid:
                path.setdefault(t, {})[which] = feats(byid[t, m['ident']])
    json.dump(dict(over=over, under=under, path=path), open(U + 'expensive-productions-%s.json' % s, 'w'))
    g = lambda rs: collections.Counter(r['group'] for r in rs)
    print('%s: %d productions over %d bits, %d at or under' % (s, len(over), CUT, len(under)))
    for name, n in g(over).most_common():
        print('  over: %s %d (%.0f%%)' % (name, n, 100 * n / len(over)))
    for name, n in g(under).most_common():
        print('  at or under: %s %d (%.0f%%)' % (name, n, 100 * n / max(len(under), 1)))
    print('  OR composition over %d bits whose head is a goal table: %d' % (CUT, sum(r['before_out'] for r in over if r['group'] == 'OR composition')))
    print('  tasks by group of the most expensive production on the cheapest path:', dict(g(x['path'] for x in path.values() if 'path' in x)))
    print('  tasks by group of the most expensive production on the minimax path:', dict(g(x['minimax_path'] for x in path.values() if 'minimax_path' in x)))
    for t in sorted(path):
        a, b = path[t].get('path'), path[t].get('minimax_path')
        if a and b:
            print('  %s cheapest %s %.1f, minimax %s %.1f%s' % (t, a['group'], a['bits'], b['group'], b['bits'], '' if a['group'] == b['group'] else '  differs'))


if __name__ == '__main__':
    main()
