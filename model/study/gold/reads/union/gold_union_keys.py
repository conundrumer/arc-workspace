"""The union key of each form of each case. Writes union-keys-SET.jsonl in work/lm/data-study/gold/gold-union, one line per case: task, case, `text`, the case's program after `Bar.normal` (the text the union reads), and `keys`, the union key of each line of that text that isn't OUT, in order (null where no union table has the line's identity, as for a case that the union leaves out). A union table holds the identities of one QueryHash, so lines of equal QueryHash have one key.

  <runtime python> gold_union_keys.py SET
  <runtime python> gold_union_keys.py SET K N
  <runtime python> gold_union_keys.py SET merge

A case is a line of cases-SET.jsonl. The union is union-SET.jsonl with union-SET-addendum.jsonl. The case `pinned` is the pinned program.

- `SET K N` takes the tasks at positions K, K + N, ... of the union and appends to union-keys-SET-K.jsonl, all of a task's lines in one write, so a task in that file is complete. It skips the tasks in any union-keys-SET-<n>.jsonl. Where union-SET.jsonl doesn't exist yet, the union is the shard files of `gold_union.py run`, a later row for a task in place of an earlier one.
- `SET merge` writes union-keys-SET.jsonl from those files, in the order of cases-SET.jsonl.
- `SET` and `SET merge` also write union-keys-SET.jsonl.code.json, {"code": {"sha", "dirty"}}: the commit of the code that wrote the file (gold_union_code.py).
"""
import glob, json, os, re, sys
import gold_union_code
from gold_union import OUT, Bar, forms_of, program_lines, shards, union_rows


def union(s):
    if os.path.exists(OUT + 'union-%s.jsonl' % s):
        return list(union_rows(s))
    got = {}
    for p in shards(s):
        for l in open(p):
            if l.endswith('\n'):
                r = json.loads(l)
                got[r['task']] = r
    return [got[t] for t in sorted(got)]


def key_shards(s):
    return [p for p in glob.glob(OUT + 'union-keys-%s-*.jsonl' % s) if re.search(r'-\d+\.jsonl$', p)]


def merge(s):
    got = {}
    for p in key_shards(s):
        for l in open(p):
            if l.endswith('\n'):
                c = json.loads(l)
                got[c['task'], c['case']] = l
    with open(OUT + 'union-keys-%s.jsonl.part' % s, 'w') as out:
        for l in open(OUT + 'cases-%s.jsonl' % s):
            c = json.loads(l)
            if (c['task'], c['case']) in got:
                out.write(got.pop((c['task'], c['case'])))
    os.replace(OUT + 'union-keys-%s.jsonl.part' % s, OUT + 'union-keys-%s.jsonl' % s)
    gold_union_code.write_sidecar(OUT + 'union-keys-%s.jsonl' % s)
    print(len({json.loads(l)['task'] for l in open(OUT + 'union-keys-%s.jsonl' % s)}), 'tasks')


def stream(s, k, n):
    rows = union(s)
    done = {json.loads(l)['task'] for p in key_shards(s) for l in open(p) if l.endswith('\n')}
    keys = {u['task']: {f['ident']: x['key'] for x in u.get('tables') or [] for f in x['forms']} for i, u in enumerate(rows) if i % n == k and u['task'] not in done}
    print(len(keys), 'tasks', flush=True)
    cases = {}
    for l in open(OUT + 'cases-%s.jsonl' % s):
        c = json.loads(l)
        if c['task'] in keys and c['excluded'] != 'True':
            cases.setdefault(c['task'], []).append(c)
    with open(OUT + 'union-keys-%s-%d.jsonl' % (s, k), 'a') as out:
        for i, t in enumerate(keys):
            bar = Bar(t)
            lines = []
            for c in cases.get(t, []):
                try:
                    text = bar.normal(c['gold_sexp'])[0]
                except Exception:  # noqa: BLE001
                    text = c['gold_sexp']
                ls = [x for x in program_lines(text) if not x.startswith('(OUT')]
                fs, _ = forms_of(ls)
                got = [keys[t].get(f['ident']) for f in fs] if len(fs) == len(ls) else [None] * len(ls)
                lines.append(json.dumps(dict(task=t, case=c['case'], text=text, keys=got)) + '\n')
            out.write(''.join(lines))
            out.flush()
            print(i + 1, t, len(lines), flush=True)


def main():
    s = sys.argv[1]
    if sys.argv[2:3] == ['merge']:
        return merge(s)
    if len(sys.argv) > 3:
        return stream(s, int(sys.argv[2]), int(sys.argv[3]))
    keys = {}
    for u in union_rows(s):
        keys[u['task']] = {f['ident']: x['key'] for x in u.get('tables') or [] for f in x['forms']}
    n = miss = 0
    bar = None
    with open(OUT + 'union-keys-%s.jsonl.part' % s, 'w') as out:
        for l in open(OUT + 'cases-%s.jsonl' % s):
            c = json.loads(l)
            if c['task'] not in keys or c['excluded'] == 'True':
                continue
            if bar is None or bar.task != c['task']:
                bar = Bar(c['task'])
                bar.task = c['task']
            try:
                text = bar.normal(c['gold_sexp'])[0]
            except Exception:  # noqa: BLE001
                text = c['gold_sexp']
            lines = [x for x in program_lines(text) if not x.startswith('(OUT')]
            fs, _ = forms_of(lines)
            got = [keys[c['task']].get(f['ident']) for f in fs] if len(fs) == len(lines) else [None] * len(lines)
            n += len(got)
            miss += got.count(None)
            out.write(json.dumps(dict(task=c['task'], case=c['case'], text=text, keys=got)) + '\n')
    os.replace(OUT + 'union-keys-%s.jsonl.part' % s, OUT + 'union-keys-%s.jsonl' % s)
    gold_union_code.write_sidecar(OUT + 'union-keys-%s.jsonl' % s)
    print(n, 'lines', miss, 'without a key')


if __name__ == '__main__':
    main()
