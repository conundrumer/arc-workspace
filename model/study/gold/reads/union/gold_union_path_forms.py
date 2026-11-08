"""RETIRED for graph files written after the graph dropped its bits: this script reads `path`, `minimax_path` and `bits` of graph-tasks-SET.jsonl / graph-prods-SET.jsonl, which gold_union_graph.py no longer writes. It runs only on graph files of earlier rounds. Where each production on a task's cheapest path and minimax path sits in the case texts. Writes path-forms-SET.jsonl in work/lm/data-study/gold/gold-union, one line per (task, path, production).

  <runtime python> gold_union_path_forms.py SET

- Paths: `path` and `minimax_path` of graph-tasks-SET.jsonl, by their `idents`.
- Fields: task, path (`cheapest` or `minimax`), ident, kind, bits, depth, heads and reads (graph table names, from graph-prods-SET.jsonl), `or_body` (the body holds OR), `goal_head` (a head is a goal table), and `at`: the first case of union-keys-SET.jsonl whose `text` has a form of that identity, with the form's index among the text's lines (OUT included) and its union key from `keys`.
- An OR body is one line of the text; its branches are the top-level lists of the OR.
"""
import collections, json, re, sys
from gold_union import OUT, forms_of, program_lines
import study_zst as Z  # on the path since gold_union is imported


def main():
    s = sys.argv[1]
    tasks = {json.loads(l)['task']: json.loads(l) for l in Z.open_text(OUT + 'graph-tasks-%s.jsonl' % s)}
    prods = {(p['task'], p['ident']): p for p in map(json.loads, Z.open_text(OUT + 'graph-prods-%s.jsonl' % s))}
    want = collections.defaultdict(set)
    for t, k in tasks.items():
        for which in ('path', 'minimax_path'):
            want[t] |= set((k.get(which) or {}).get('idents', []))
    at = {}
    for l in Z.open_text(OUT + 'union-keys-%s.jsonl' % s):
        c = json.loads(l)
        if not want.get(c['task']):
            continue
        ls = program_lines(c['text'])
        body = [i for i, x in enumerate(ls) if not x.startswith('(OUT')]
        fs, _ = forms_of([ls[i] for i in body])
        for i, f, key in zip(body, fs, c['keys']):
            if f['ident'] in want[c['task']]:
                at.setdefault((c['task'], f['ident']), dict(case=c['case'], line=i, key=key, text=ls[i]))
    n = 0
    with open(OUT + 'path-forms-%s.jsonl' % s, 'w') as out:
        for t, k in sorted(tasks.items()):
            goal = set(k.get('goal') or [])
            for which, name in (('path', 'cheapest'), ('minimax_path', 'minimax')):
                for i in (k.get(which) or {}).get('idents', []):
                    p, a = prods[t, i], at.get((t, i))
                    out.write(json.dumps(dict(task=t, path=name, ident=i, kind=p['kind'], bits=p['bits'], depth=p['depth'], heads=p['heads'], reads=p['reads'],
                                              or_body=bool(a and re.search(r'\(OR\b', a['text'])), goal_head=bool(set(p['heads']) & goal), at=a)) + '\n')
                    n += 1
    print(n, 'lines')


if __name__ == '__main__':
    main()
