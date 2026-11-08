"""Union gold: the one-case programs of each task's solver and the pinned program, with the union of their tables. design.md in this folder gives the definitions. Rows in union-SET-K.jsonl.

The union stages write their large files as zstd streams, `union-SET-K.jsonl.zst`, and read them through model/study/study_zst.py, which reads a plain `union-SET-K.jsonl` and a `union-SET-K.jsonl.zst` alike. Names in this file are the logical names, without `.zst`. A frame is flushed as each row is written, so a reader can read a file that is still being written.

A program is kept when its text has a row in fits-SET.jsonl (gold_union_fits.py, on the current engine) with fit and test_ok true: some assignment of its DETs gives every train output, and the fitting assignments give, on each test example, at most two distinct grids and one is the expected output. Queries of equal QueryHash make one union table (query_hash.py, on the engine of gold_union_env.sh; the row keeps `query_hash_version`). A query that the engine refuses keeps its own union table and is listed in the row's `unhashed`. gold_union_graph.py joins union tables by equal maps.

  model/study/gold/cover_forms/gold_union_env.sh gold_union.py run [K N [SET]]    SET is train, dev or held-out; the rows go to union-SET-K.jsonl
  model/study/gold/cover_forms/gold_union_env.sh gold_union.py child TASK...
  model/study/gold/cover_forms/gold_union_env.sh gold_union.py merge [SET]    writes union-SET.jsonl and union-SET.jsonl.sha256 from the union-SET-K.jsonl files; with no SET, union.jsonl from all of them. A task listed in out-of-scope.jsonl gets the line {task, set, error, set_aside}, with its reason in both and no tables, so that the consumers set it aside; its lines in the union-SET-K.jsonl files stay. It also updates union-SET.manifest.json (made where missing): `sha256`, where the manifest has it, and `code`, {"sha", "dirty"} of the code that merged (gold_union_code.py); its other fields stay.
  model/study/gold/cover_forms/gold_union_env.sh gold_union.py search    writes search-programs.jsonl from the search outputs in SEARCH
"""
import glob, hashlib, json, os, re, sys, time
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[3]))  # model/study
import study_zst as Z  # the large files of OUT are zstd streams or plain files, whichever is on disk
SAMPLES = '/Users/davidlu/code/arc-workspace/model/study/samples'  # query_hash.py
import gold_case_counts as G
import gold_final_dedup as F
import gold_cheapest_case as C
import gold_union_code
from gold_union_fits import rows_of, set_of, sha16, shard_files
from gold_cheapest_common import Bar, ROOT, D, program_lines, sha
from gold_cheapest_prune import dead_lines
C.GIB = 4  # a task past 4 GiB is set aside; 6 shards share the machine

OUT = os.environ.get('GOLD_UNION_DIR', D + 'gold/gold-union') + '/'  # GOLD_UNION_DIR: the folder of the inputs and outputs
HEAD, NAME = G.HEAD, G.NAME
OUT_OF_SCOPE = OUT + 'out-of-scope.jsonl'  # one line per task, {task, set, reason}: a task the union sets aside


def out_of_scope():
    """{task: reason} of out-of-scope.jsonl."""
    return {r['task']: r['reason'] for r in map(json.loads, open(OUT_OF_SCOPE))} if os.path.exists(OUT_OF_SCOPE) else {}


SETS =['train', 'dev', 'held-out']  # the splits, in the order that they run
SEARCH = [  # glob patterns of search outputs: one JSON line per program, the file named TASK.*.jsonl
    ROOT / 'work/synth-kaggle' / ('kernel-soak-%s-linux-ramp59-2400s/work-logs/74dd1130.search.out.jsonl' % k) for k in ('8ed4fe634', '0eec50f18', '2d21a0079', 'e8ded5733', 'ec15d12f0')
] + [
    ROOT / 'work/synth-kaggle/kernel-soak-a1a88cc17-linux-23eval-23training-1800s/work-logs/239be575.search.out.jsonl',
    ROOT / 'work/lm/data-study/sampler/sampler-worker/sampler-pool-dag-both-final-600s/out/dagbf_s1/c35c1b4c/work/c35c1b4c.out.jsonl',
    ROOT / 'work/lm/data-study/sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out/bundle_s0/*/work/*.out.jsonl',
]


def union_rows(name):
    """The rows of union-NAME.jsonl, then of union-NAME-addendum.jsonl where it exists, a later row for a task in place of an earlier one, in task order."""
    got = {}
    for p in (OUT + 'union-%s.jsonl' % name, OUT + 'union-%s-addendum.jsonl' % name):
        if Z.exists(p):
            for l in Z.open_text(p):
                r = json.loads(l)
                got[r['task']] = r
    return [got[t] for t in sorted(got)]


def forms_of(lines):
    """([form], {label: identity}) of the non-OUT forms of the lines. A form is a dict of label, line, kind, component, identity, depth and the identities it reads. An identity is the form's text with each read replaced by the identity of the form it reads, labels dropped."""
    ident, depth, out = {}, {}, []
    for x in lines:
        m = HEAD.match(x)
        if not m:
            continue
        body = x[m.end():]
        reads = list(dict.fromkeys(ident[n[1]] for n in NAME.finditer(body) if n[1] in ident))
        text = m[1] + NAME.sub(lambda n: '{%s}%s' % (ident[n[1]], n[2]) if n[1] in ident else '&_' + n[2], body)
        ident[m[2]] = sha(' '.join(text.split()))
        depth[ident[m[2]]] = 1 + max((depth[r] for r in reads), default=-1)
        out.append(dict(label=m[2], line=x, kind=m[1], component=x.split()[2] if m[1] == 'INIT' else None, ident=ident[m[2]], depth=depth[ident[m[2]]], reads=reads))
    return out, ident


_FITS = {}


def fits_of(set_name):
    """{task: {text_sha: program}} of fits-SET.jsonl (gold_union_fits.py), or of its shard files where it is missing. Read once for each set."""
    if set_name not in _FITS:
        path = OUT + 'fits-%s.jsonl' % set_name
        files = [path] if Z.exists(path) else shard_files(set_name)
        got = {}
        for p in files:
            for r in rows_of(p):
                got[r['task']] = {x['text_sha']: x for x in r['programs']}
        _FITS[set_name] = got
    return _FITS[set_name]


def verdict(fits, text):
    """(program, reason): the fits entry of the text, and None where the program is kept, else why it is left out."""
    x = fits.get(sha16(text))
    if x is None:
        return None, 'no fits row'
    if x['why']:
        return x, x['why']
    for f in ('decode', 'sampler'):  # gold the sampler's decoder can't write; a timeout or 'not ended' (the 10 s deadline under load) is no outcome
        if (x.get(f) or 'ok').startswith(('refused', 'does not parse')):
            return x, '%s: %s' % (f, x[f])
    if not x['fit']:
        return x, 'no assignment fits'
    return x, None if x['test_ok'] else 'test output not given'


class QueryHashConflict(Exception):
    pass


def query_of(got, f, lines, program):
    """Sets got[identity] = [QueryHash or None, program, checked] for the form f (a form of forms_of) of `program`, whose non-OUT lines are `lines`. The first program with the identity gives the QueryHash (None where the engine refuses it). One other program with the identity is hashed too, and raises QueryHashConflict where its QueryHash differs."""
    if SAMPLES not in sys.path:
        sys.path.insert(0, SAMPLES)
    import query_hash as Q  # needs the engine on the path: gold_union_env.sh; the other readers of this file don't need it
    g = got.get(f['ident'])
    if g is not None and (g[2] or g[0] is None or g[1] == program):
        return
    i = lines.index(f['line'])
    try:
        h = Q.query_hash(lines[:i], lines[i])
    except ValueError:
        h = None
    if g is None:
        got[f['ident']] = [h, program, False]
    elif h is not None:
        if h != g[0]:
            raise QueryHashConflict('identity %s: QueryHash %s in program %s, %s in program %s' % (f['ident'], g[0], g[1], h, program))
        g[2] = True


def record(row, ids, progs, hashes):
    """The task's row with its tables, one for each QueryHash: ids are the identities in order (dicts of form, programs), progs {program: its cases}, hashes {identity: [QueryHash or None, ...]} from query_of. Identities of one QueryHash make one union table, keyed by the least of their indexes; one the engine refused keeps its own table and is listed in `unhashed`."""
    if SAMPLES not in sys.path:  # a row with every program left out runs no query_of
        sys.path.insert(0, SAMPLES)
    import query_hash as Q
    at = {x['form']['ident']: k for k, x in enumerate(ids)}
    group = {}
    for k, x in enumerate(ids):
        h = hashes[x['form']['ident']][0]
        group.setdefault(h if h is not None else k, []).append(k)
    new = {k: g[0] for g in group.values() for k in g}
    tables = []
    for g in sorted(group.values()):
        t = None
        for k in g:
            x = ids[k]
            f = x['form']
            made = {c for p in x['programs'] for c in progs[p]}
            part = dict(key=g[0], forms=[dict(ident=f['ident'], text=f['line'])], cases=sorted(made - {'pinned'}), pinned='pinned' in made,
                        kind=f['kind'], component=f['component'], reads={f['ident']: sorted({new[at[r]] for r in f['reads']})}, depth=f['depth'], depths=[f['depth']])
            if t is None:
                t = part
                continue
            assert (t['kind'], t['component']) == (part['kind'], part['component']), (g, t['forms'], part['forms'])
            t['forms'] += part['forms']
            t['cases'] = sorted(set(t['cases']) | set(part['cases']))
            t['pinned'] = t['pinned'] or part['pinned']
            t['reads'].update(part['reads'])
            t['depth'] = min(t['depth'], part['depth'])
            t['depths'] = sorted(set(t['depths']) | set(part['depths']))
        t['query'] = hashes[t['forms'][0]['ident']][0]
        tables.append(t)
    return dict(row, tables=tables, merged='query_hash', query_hash_version=Q.VERSION, unhashed=sorted(g[0] for g in group.values() if hashes[ids[g[0]]['form']['ident']][0] is None))


def one(t, pubs):
    print('stem', t, flush=True)
    bar = Bar(t)
    row = dict(stem=t, taken=None, task=t, set=set_of(t))
    fits = fits_of(set_of(t)).get(t)
    if fits is None:
        return dict(row, error='no fits row')
    progs, norms, cases, left_out, texts, kept = {}, {}, {}, {}, {}, {}
    if G.pinned(t) is not None:  # a solver written after gold-v3's view-final has no pinned program, and its cases alone make the row
        try:
            pin, _ = bar.normal(G.pinned(t))
        except Exception as e:  # noqa: BLE001
            return dict(row, error='pinned: does not parse: %s %s' % (type(e).__name__, str(e)[:100]))
        x, why = verdict(fits, G.pinned(t))
        if why == 'no fits row':
            return dict(row, error='pinned: ' + why)
        if why and not x['why']:
            return dict(row, error='pinned: no assignment fits')
        progs, norms, cases = {sha(pin): ['pinned']}, {sha(pin): pin}, {'pinned': sha(pin)}
        if why:  # the pinned program gives no tables (it stopped at the fits bound): it is left out, and the cases make the row
            left_out[sha(pin)] = why
        else:
            kept = {sha(pin): dict(test_differs=not x['test_ok'])}
    for c in (pubs[t][1]['cases'] if t in pubs else []):
        text = c.get('filtered_program') or c.get('original_program') or ''
        if text not in texts:
            try:
                norm, _ = bar.normal(text)
                x, why = verdict(fits, text)
            except Exception as e:  # noqa: BLE001
                norm, x, why = None, None, 'does not parse: %s %s' % (type(e).__name__, str(e)[:100])
            texts[text] = (sha(norm if norm is not None else text), norm, why, x)
        name, norm, why, x = texts[text]
        if not why:
            kept[name] = dict(test_differs=not x['test_ok'])
        cases[c['case']] = name
        progs.setdefault(name, []).append(c['case'])
        norms.setdefault(name, norm)
        if why:
            left_out[name] = why
    ids, seen, hashes = [], {}, {}
    try:
        for name in progs:
            if name in left_out:
                continue
            fs, _ = forms_of(program_lines(norms[name]))
            lines = [x for x in program_lines(norms[name]) if not x.startswith('(OUT')]
            for f in fs:
                query_of(hashes, f, lines, name)
                if f['ident'] not in seen:
                    seen[f['ident']] = len(ids)
                    ids.append(dict(form=f, programs=[]))
                if name not in ids[seen[f['ident']]]['programs']:
                    ids[seen[f['ident']]]['programs'].append(name)
    except QueryHashConflict as e:
        print('QUERYHASH CONFLICT', t, e, file=sys.stderr, flush=True)
        return dict(row, error='QueryHash conflict: %s' % e)
    return record(dict(row, cases=cases, programs=kept, left_out=left_out), ids, progs, hashes)


def child(stems):
    pubs = G.publications()
    for t in stems:
        print(json.dumps(one(t, pubs)), flush=True)


class Rows:
    """The file the watchdog writes to: a task's row, or a set_aside line."""

    def __init__(self, out):
        self.out = out

    def write(self, line):
        r = json.loads(line)
        stem = r.pop('stem')
        r.pop('taken', None)
        if r.get('set_aside'):
            r = dict(task=stem, set=set_of(stem), set_aside=r['set_aside'])
        self.out.write(json.dumps(r) + '\n')

    def flush(self):
        self.out.flush()


def order():
    return sorted(F.order(), key=lambda t: SETS.index(set_of(t)))  # stable, so F.order() orders within a set


def run(args=()):
    """`run K N SET` takes the tasks of the set at positions K, K + N, ... of the order and writes union-SET-K.jsonl. With UNION_TASKS set (tasks separated by spaces), it takes those tasks instead, less the done ones."""
    k, n = (int(args[0]), int(args[1])) if args else (0, 1)
    sets = args[2] if len(args) > 2 else None
    done = {json.loads(l)['task'] for p in shards() for l in Z.open_text(p) if l.endswith('\n')}
    left = [t for i, t in enumerate(x for x in order() if sets in (None, set_of(x))) if i % n == k and t not in done]
    if os.environ.get('UNION_TASKS'):
        left = [t for t in os.environ['UNION_TASKS'].split() if t not in done]
    print(len(left), 'tasks', flush=True)
    with Z.open_text(OUT + 'union-%s-%d.jsonl' % (slug(sets), k), 'a', line_buffering=True) as f:
        out = Rows(f)
        while left:
            part, left = left[:C.PER_CHILD], left[C.PER_CHILD:]
            while part:
                part = C.watch(part, out, os.path.abspath(__file__))
                out.flush()


def shards(name=None):
    """The shard files of `run`, of one set or of all: union-<set>-<K>.jsonl, and not the union-identity files of gold_union_identity.py."""
    pat = re.compile(r'union-(%s)-\d+\.jsonl$' % (re.escape(name) if name else 'train|dev|held-out|all'))
    return sorted(p for p in Z.glob(OUT + 'union-*.jsonl') if pat.search(p))


def slug(sets):
    return sets.replace(' ', '-') if sets else 'all'


def merge(args=()):
    name = 'union-' + slug(args[0]) if args else 'union'
    got = {}
    for p in shards(slug(args[0]) if args else None):
        for l in Z.open_text(p):
            if l.endswith('\n'):
                r = json.loads(l)
                got[r['task']] = l
    for t, why in out_of_scope().items():
        if t in got:
            got[t] = json.dumps(dict(task=t, set=json.loads(got[t]).get('set'), error=why, set_aside=why)) + '\n'
    text = ''.join(got[t] for t in sorted(got))
    with Z.open_text(OUT + name + '.jsonl', 'w', atomic=True) as f:
        f.write(text)
    open(OUT + name + '.jsonl.sha256', 'w').write(hashlib.sha256(text.encode()).hexdigest() + '\n')
    manifest = OUT + name + '.manifest.json'
    info = json.load(open(manifest)) if os.path.exists(manifest) else dict(file=name + '.jsonl')
    if 'sha256' in info or not os.path.exists(manifest):
        info['sha256'] = hashlib.sha256(text.encode()).hexdigest()
    info['code'] = gold_union_code.stamp()
    with open(manifest, 'w') as f:
        json.dump(info, f, indent=1)
        f.write('\n')
    print(len(got), 'tasks')


def trim(text):
    """The program's lines without the forms that no later form reads, again and again."""
    ls = program_lines(text)
    while dead_lines(ls):
        ls.pop(dead_lines(ls)[-1])
    return '\n'.join(ls)


def search(args=()):
    """One line per program of the search outputs: task, file, line, the program pruned to the forms OUT reads, and per test the attempts that are right."""
    n = 0
    with open(OUT + 'search-programs.jsonl', 'w') as out:
        for pattern in SEARCH:
            for path in sorted(glob.glob(str(pattern))):
                task = os.path.basename(path).split('.')[0]
                tests = json.load(open(ROOT / 'data/tasks' / (task + '.json')))['test']
                for i, l in enumerate(open(path), 1):
                    r = json.loads(l)
                    if r.get('program'):
                        right = [[a == t['output'] for a in att] for t, att in zip(tests, r['attempts'])]
                        out.write(json.dumps(dict(task=task, file=path.replace(str(ROOT) + '/', ''), line=i, program=trim(r['program']), right=right)) + '\n')
                        n += 1
    print(n, 'programs')


if __name__ == '__main__':
    {'child': child, 'merge': merge, 'search': search}.get(sys.argv[1], run)(sys.argv[2:])
