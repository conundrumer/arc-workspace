"""Writes out-of-scope.jsonl in GOLD_UNION_DIR: the tasks the union sets aside, one line each, {task, set, reason}.

  python3 gold_union_scope.py

- A task is out of scope when every program the union keeps for it (its row in the union-SET-K.jsonl files, less left_out) has a DEMONSTRATED form in its text in cases-SET.jsonl.
- A task where some kept programs have a DEMONSTRATED form and others don't would need its tables reached only through such a form marked. The script lists those tasks and exits with status 1, and writes nothing.
"""
import collections, json, os, sys
from gold_union import OUT, OUT_OF_SCOPE, SETS, shards

REASON = 'out of scope: DEMONSTRATED (user ruling)'


def demonstrated(s):
    """{task: {case: whether its text has a DEMONSTRATED form}} of the cases of the set that are not excluded."""
    got = collections.defaultdict(dict)
    for l in open(OUT + 'cases-%s.jsonl' % s):
        c = json.loads(l)
        if c['excluded'] not in (True, 'True'):
            got[c['task']][c['case']] = '(DEMONSTRATED' in c['gold_sexp']
    return got


def main():
    out, mixed = [], []
    for s in SETS:
        last = {}
        for p in shards(s):
            for l in open(p):
                if l.endswith('\n'):
                    r = json.loads(l)
                    last[r['task']] = r
        demo = demonstrated(s)
        for t, u in sorted(last.items()):
            kept = [c for c, h in (u.get('cases') or {}).items() if h not in (u.get('left_out') or {})]
            has = [demo[t].get(c, False) for c in kept]
            if kept and all(has):
                out.append(dict(task=t, set=s, reason=REASON))
            elif any(has):
                mixed.append((s, t, sum(has), len(has)))
        print(s, sum(r['set'] == s for r in out), 'tasks out of scope', flush=True)
    if mixed:
        print('tasks with DEMONSTRATED in some kept programs only (set, task, with it, kept):', mixed)
        sys.exit(1)
    with open(OUT_OF_SCOPE + '.part', 'w') as f:
        f.writelines(json.dumps(r) + '\n' for r in out)
    os.replace(OUT_OF_SCOPE + '.part', OUT_OF_SCOPE)


if __name__ == '__main__':
    main()
