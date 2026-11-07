"""One row per task with gold: the size and shape of its gold program and of its grids, and its set. Writes task-facts.jsonl and task-facts.csv in this folder.

  python3 gold_task_facts.py

- Gold: gold-export/flat/<stem>.arclog. Forms are the non-OUT lines; equal tables appear once, since the equal-table step ran on this text. Depth is 0 for a form that reads no form, else one more than its deepest read. Counts are of forms; an INIT form makes one table per output relation.
- Ident columns: the head columns typed Ident by the typer of gold-ti-forms/ti_forms.py over the lib registry; forms it can't type are counted in `untyped`.
- Bits: the cheapest form at depths 0 to 3 in reread-kit/merged.jsonl (or_q.walk at b8e52e249), where that row's base_sha is the stem's text.
- Search depth: search-worker's search-effective-depth-ramp22-heldout37-training/tasks.jsonl, joined by task, as the `search_` columns (tables by merge key, depth from 0; empty where the task has no recorded run).
- Grids: data/tasks/<stem>.json; cells are height times width, medians over pairs.
- Union: the tables of gold-union per depth 0 to 7+, and their max depth, as the `union_` columns. Where graph-tables-<set>.jsonl exists, the tables are the merged union and the depth is by productions on its AND-OR graph (`union_level` merged); else they are the tables of union-identity-<set>.jsonl, one per identity, which is an upper bound on the count (`union_level` text). A merged table that no production makes from given tables has no depth: it counts in `union_tables` and in no depth column. `union_cases` is the count of non-excluded cases: `cases` of case-counts.jsonl, which leaves the excluded cases out.
"""
import collections, hashlib, json, os, statistics, sys

R = '/Users/davidlu/code/arc-workspace/'
sys.path.append(R + 'model/study')
import study_zst as Z  # the union files are zstd streams or plain files, whichever is on disk
D = R + 'work/lm/data-study/'
HERE = os.path.dirname(os.path.abspath(__file__))
FLAT = D + 'gold/gold-export/flat/'
sys.path.insert(0, D + 'gold/gold-ti-forms')
sys.argv = sys.argv[:1]
import ti_forms as T  # noqa: E402

SETS = [('37', D + 'sampler/sampler-worker/held/tasks.txt'), ('62', D + 'features-worker/arm/eval-tasks.txt'), ('22 ramp', D + 'sampler/sampler-worker/held/ramp-fold.txt')]


def set_of():
    got = {}
    for name, p in SETS:
        for t in open(p).read().split():
            got.setdefault(t, name)
    return got


def union():
    """{task: union columns}."""
    U = D + 'gold/gold-union/'
    got = {}
    for name in ('ramp', '37', 'training', '62'):
        if Z.exists(U + 'graph-tables-%s.jsonl' % name):
            depths = collections.defaultdict(list)
            for r in map(json.loads, Z.open_text(U + 'graph-tables-%s.jsonl' % name)):
                depths[r['task']].append(r['depth'])
            level = 'merged'
        else:
            depths = {r['task']: [x['depth'] for x in r['tables']] for r in map(json.loads, Z.open_text(U + 'union-identity-%s.jsonl' % name))}
            level = 'text'
        for t, ds in depths.items():
            made = [d for d in ds if d is not None]
            per = collections.Counter(min(d, 7) for d in made)
            got[t] = dict(union_level=level, union_tables=len(ds), union_max_depth=max(made, default=None), **{'union_depth_%s' % (d if d < 7 else '7+'): per[d] for d in range(0, 8)})
    for r in map(json.loads, open(U + 'case-counts.jsonl')):
        if r.get('cases') is not None:
            got.setdefault(r['task'], {})['union_cases'] = int(r['cases'])
    return got


def cells(g):
    return len(g) * len(g[0]) if g and g[0] else 0


def main():
    sets, reg, un = set_of(), T.Registry(), union()
    merged = {r['task']: r for r in map(json.loads, open(D + 'gold/gold-v3-dag-bits/reread-kit/merged.jsonl'))}
    man = json.load(open(D + 'gold/gold-export/manifest.json'))
    approx = {s for s, v in man['stems'].items() if 'approximated' in v}
    ED = D + 'sampler/search-worker/runs/search-effective-depth-ramp22-heldout37-training/tasks.jsonl'
    eff = {r['task']: r for r in map(json.loads, open(ED))} if os.path.exists(ED) else {}
    EK = ('gold_tables', 'gold_depth_max', 'covered', 'unknown', 'shallower', 'effective_depth', 'effective_from_unknown', 'effective_known')
    UK = ['union_level', 'union_cases', 'union_tables', 'union_max_depth'] + ['union_depth_%s' % (d if d < 7 else '7+') for d in range(0, 8)]
    rows = []
    for f in sorted(os.listdir(FLAT)):
        t = f[:-7]
        text = open(FLAT + f).read()
        lines, reads, depth = T.C.gold_forms(text)
        depth = [d - 1 for d in depth]
        trees = [T.parse_all(l)[0] for l in lines]
        kinds = collections.Counter(x[0] if x[0] in ('RULE', 'INIT', 'DET') else 'other' for x in trees)
        heads, unk, ident, untyped = {}, collections.Counter(), 0, 0
        for x in trees:
            try:
                hd, _ = T.type_form(reg, heads, T.canon_form(x), unk) if x[0] in ('RULE', 'INIT') else (None, None)
            except Exception:  # noqa: BLE001
                hd = None
            if hd is None:
                untyped += 1
                continue
            types = hd['head'] if isinstance(hd['head'], list) else [y for v in hd['head'].values() for y in v]
            untyped += '?' in types
            ident += types.count('Ident')
        per = collections.Counter(min(d, 7) for d in depth)
        sha = hashlib.sha256('\n'.join(text.strip().splitlines()).encode()).hexdigest()[:16]
        m = merged.get(t)
        bits = {}
        if m and m.get('base_sha') == sha:
            for d in (0, 1, 2, 3):
                b = [fm.get('bits') for fm in m['forms'] if fm['line'] < len(depth) and depth[fm['line']] == d and fm.get('bits') is not None]
                bits[d] = round(min(b), 2) if b else None
        task = json.load(open(R + 'data/tasks/%s.json' % t))
        tr, te = task['train'], task['test']
        ins = [cells(p['input']) for p in tr + te]
        outs = [cells(p['output']) for p in tr]
        same = all(len(p['input']) == len(p['output']) and len(p['input'][0]) == len(p['output'][0]) for p in tr)
        rows.append(dict(task=t, set=sets.get(t, 'training'), approximated=t in approx, forms=len(lines), max_depth=max(depth), **{'depth_%s' % (d if d < 7 else '7+'): per[d] for d in range(0, 8)},
                         rule=kinds['RULE'], init=kinds['INIT'], det=kinds['DET'], other=kinds['other'], ident_columns=ident, untyped_forms=untyped,
                         **{'bits_min_depth_%d' % d: bits.get(d) for d in (0, 1, 2, 3)}, bits_record='merged.jsonl b8e52e249' if bits else None,
                         train_pairs=len(tr), test_cases=len(te), input_cells_median=statistics.median(ins), output_cells_median=statistics.median(outs), output_size_equals_input=same, **{'search_' + k: eff.get(t, {}).get(k) for k in EK},
                         **{k: un.get(t, {}).get(k) for k in UK}))
    with open(HERE + '/task-facts.jsonl', 'w') as f:
        for r in rows:
            f.write(json.dumps(r) + '\n')
    with open(HERE + '/task-facts.csv', 'w') as f:
        f.write(','.join(rows[0]) + '\n')
        for r in rows:
            f.write(','.join('' if v is None else str(v) for v in r.values()) + '\n')
    print(len(rows), collections.Counter(r['set'] for r in rows), 'with bits', sum(r['bits_record'] is not None for r in rows), 'untyped forms', sum(r['untyped_forms'] for r in rows), 'of', sum(r['forms'] for r in rows))


if __name__ == '__main__':
    main()
