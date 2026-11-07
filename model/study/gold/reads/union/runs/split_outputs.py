"""Write the union outputs of each split (train, dev, held-out) from the outputs of the old sets (ramp, 37, training, 62) in GOLD_UNION_DIR, by task. Every output is per task (cases, fits, union rows, keys and graph lines), so a split's file is the lines of its tasks, with `set` changed to the split's name. gold_union_walks.py SPLIT then gives the walks of a split.

  GOLD_UNION_DIR=<folder> .venv/bin/python split_outputs.py

- The split of a task is its `split` column in model/study/samples/split_design/split2.tsv, where 'held' and 'held-out' both name held-out.
- Each output records the code stamps of its sources: the one stamp they share, else "code" null and "mixed" listing them (gold_union_code.py).
- It prints, per split, the tasks of the split, and the tasks that have cases, fits, a union row and a graph line.
"""
import hashlib, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../..'))  # model/study
import study_zst as Z  # the outputs are zstd streams or plain files, whichever is on disk

ROOT = '/Users/davidlu/code/arc-workspace/'
G = os.environ['GOLD_UNION_DIR'] + '/'
OLD = ['ramp', '37', 'training', '62']
SPLITS = ['train', 'dev', 'held-out']
split = {}
for l in open(ROOT + 'model/study/samples/split_design/split2.tsv'):
    f = l.rstrip('\n').split('\t')
    if f[0] != 'task':
        split[f[0]] = 'held-out' if f[3] in ('held', 'held-out') else f[3]


def joined(codes):
    """The code record of an output made from sources with these stamps."""
    out = []
    for c in codes:
        if c not in out:
            out.append(c)
    return dict(code=out[0]) if len(out) == 1 else dict(code=None, mixed=out)


def sidecar(old_paths):
    """The code record of an output made from these source files, from their .code.json files."""
    return joined([json.load(open(p + '.code.json'))['code'] for p in old_paths if os.path.exists(p + '.code.json')])


def lines(kind):
    """{split: [line]} of G + kind % old set, over the old sets, and the source paths."""
    got, paths = {s: [] for s in SPLITS}, [G + kind % o for o in OLD if Z.exists(G + kind % o)]
    for p in paths:
        for l in Z.open_text(p):
            r = json.loads(l)
            if r.get('t') == 'header':
                continue
            if 'set' in r:
                r['set'] = split[r['task']]
            got[split[r['task']]].append((r['task'], json.dumps(r) + '\n'))
    return got, paths


def write(path, text):
    open(path, 'w').write(text)
    return hashlib.sha256(text.encode()).hexdigest()


def main():
    cases, _ = lines('cases-%s.jsonl')
    fits, fits_paths = lines('fits-%s.jsonl')
    unions, union_paths = lines('union-%s.jsonl')
    keys, keys_paths = lines('union-keys-%s.jsonl')
    graph = {f: lines('graph-' + f + '-%s.jsonl') for f in ('tables', 'prods', 'tasks')}
    fits_code = joined([json.loads(Z.open_text(p).readline())['code'] for p in fits_paths])
    union_code = joined([json.load(open(p.replace('.jsonl', '.manifest.json')))['code'] for p in union_paths])
    for s in SPLITS:
        sha = write(G + 'cases-%s.jsonl' % s, ''.join(l for _, l in cases[s]))
        open(G + 'cases-%s.jsonl.sha256' % s, 'w').write('%s  cases-%s.jsonl\n' % (sha, s))
        write(G + 'fits-%s.jsonl' % s, json.dumps(dict(t='header', **fits_code)) + '\n' + ''.join(l for _, l in sorted(fits[s])))
        sha = write(G + 'union-%s.jsonl' % s, ''.join(l for _, l in sorted(unions[s])))
        open(G + 'union-%s.jsonl.sha256' % s, 'w').write(sha + '\n')
        json.dump(dict(file='union-%s.jsonl' % s, sha256=sha, **union_code), open(G + 'union-%s.manifest.json' % s, 'w'), indent=1)
        order = {}
        for t, l in cases[s]:
            r = json.loads(l)
            order.setdefault((t, r['case']), len(order))
        write(G + 'union-keys-%s.jsonl' % s, ''.join(l for _, l in sorted(keys[s], key=lambda x: order.get((x[0], json.loads(x[1])['case']), len(order)))))
        json.dump(sidecar(keys_paths), open(G + 'union-keys-%s.jsonl.code.json' % s, 'w'))
        for f, (got, paths) in graph.items():
            write(G + 'graph-%s-%s.jsonl' % (f, s), ''.join(l for _, l in got[s]))
            json.dump(sidecar(paths), open(G + 'graph-%s-%s.jsonl.code.json' % (f, s), 'w'))
        tasks = [t for t in split if split[t] == s]
        print(s, 'tasks', len(tasks), 'cases', len({t for t, _ in cases[s]}), 'fits', len(fits[s]), 'union', len(unions[s]), 'graph', len(graph['tasks'][0][s]), flush=True)


if __name__ == '__main__':
    main()
