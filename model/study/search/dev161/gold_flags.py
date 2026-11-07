"""gold_flags.py OUT.json: per dev task and graph table: depth, kind, has_ident (an entry of the table's (QueryHash, Name) has an Ident column type), dep_ident (a DET in its assignments has one).
Run: PY -I gold_flags.py OUT.json   (PY = the study runtime python, for zstandard)"""
import sys, json, gzip, collections
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/model/study')
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/model/study/search/dev161')
import reach as R, study_zst as Z
skip = {json.loads(l)['task'] for l in open(R.OUT_OF_SCOPE)}
G = collections.defaultdict(dict)
for r in map(json.loads, Z.open_text(R.GRAPH)):
    if r['table'].startswith('t') and r.get('kind') != 'DEMONSTRATED':
        G[r['task']][r['table']] = dict(depth=r['depth'], kind=r['kind'])
out, stat = {}, collections.Counter()
for t, g in sorted(G.items()):
    if t in skip:
        stat['skipped_out_of_scope_tasks'] += 1; continue
    p = R.ROWS / (t + '.jsonl.gz')
    if not p.exists():
        stat['no_rowstore_tasks'] += 1; continue
    recs = [json.loads(l) for l in gzip.open(p, 'rt')]
    fn_types = {}
    for r in recs:
        if r['t'] == 'function':
            for o in r['outputs']:
                fn_types[r['id'], o['name']] = o['types']
    entries = [r for r in recs if r['t'] == 'entry']
    outputs, ents = R.row_store(R.ROWS, t)
    names = R.graph_names(outputs, ents)
    ent_types = collections.defaultdict(set)   # (f,n) -> Ident present in some entry
    has = collections.defaultdict(bool)
    for e in entries:
        k = (e['function'], e['name'])
        has[k] = has[k] or ('Ident' in e['types'])
    for k, ty in fn_types.items():
        has[k] = has[k] or ('Ident' in ty)
    det_ident = {f for (f, n), v in has.items() if v}  # functions with an Ident output
    dets_of = collections.defaultdict(set)
    for e in entries:
        for d, v in e['assignment']:
            dets_of[e['function'], e['name']].add(d)
    by_g = collections.defaultdict(list)
    for k, gname in names.items():
        by_g[gname].append(k)
    rows = {}
    for gname, info in g.items():
        ks = by_g.get(gname)
        if not ks:
            stat['graph_table_not_in_rowstore'] += 1
            rows[gname] = dict(info, has_ident=None, dep_ident=None); continue
        hi = any(has[k] for k in ks)
        di = any(d in det_ident for k in ks for d in dets_of[k])
        rows[gname] = dict(info, has_ident=hi, dep_ident=di)
    out[t] = rows
    stat['tasks'] += 1
json.dump(out, open(sys.argv[1], 'w'))
tot = collections.Counter()
for t, rows in out.items():
    for r in rows.values():
        tot['tables'] += 1; tot['has_ident=%s' % r['has_ident']] += 1; tot['dep_ident=%s' % r['dep_ident']] += 1
print(dict(stat), dict(tot))
