"""Dev labeling layer: the variants of out/<task>.variants.jsonl with every feature computed again by the current feature library, streamed to
<out dir>/<task>.variants.jsonl.

    <runtime python> -I -B refeature.py TASK OUT_DIR [SOURCE_FILE]

Each variant takes its tables from the table cache (tablecache.py) where the cache holds them, and the engine does not run for it. The base
record goes first, then the variants the cache holds, in the cache's order, then the others, in the source's order.

Each record keeps its id, kind, source, ops and grid. Every variant also gets its `stored` status and its `stored_changed`, as run.py gives them; an output variant runs the engine on the task with
the edited output, at the task's own proposer values (engine.proposer_relations), since an edit to a train output breaks the fit of every value. A restart skips the
records already written.
"""
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'features'))
import engine as E  # noqa: E402
import features as F  # noqa: E402
import run as R  # noqa: E402
import jsonl as J  # noqa: E402
import tablecache as C  # noqa: E402


MAX_LABELS = 1 << 27  # the bytes of Ident labels that a table's rows may hold; a row holds its Ident's whole label, so the total grows as the square of an Ident's rows


def canonical(tab, rows):
    """The rows as sorted strings, each Ident value in place of its name given as the rows it appears in with every Ident masked, so that a
    renaming of the Idents leaves the result unchanged. Where those names would take more than MAX_LABELS, each name is a digest of itself."""
    idc = {i for i, c in enumerate(tab['columns']) if c[1] == 'Ident'}
    if not idc:
        return sorted(json.dumps(x) for x in rows)
    masked = [json.dumps(['#' if i in idc else v for i, v in enumerate(r)]) for r in rows]
    sig = {}
    for r, m in zip(rows, masked):
        for i in idc:
            sig.setdefault(r[i], []).append([i, m])
    label = {v: json.dumps(sorted(x)) for v, x in sig.items()}
    if sum(len(label[r[i]]) for r in rows for i in idc) > MAX_LABELS:
        label = {v: hashlib.blake2b(x.encode(), digest_size=16).hexdigest() for v, x in label.items()}
    return sorted(json.dumps([label[v] if i in idc else v for i, v in enumerate(r)]) for r in rows)


def digests(T, ex):
    """{table: a short digest of its rows at example ex, blind to the renaming of Idents}: dev labeling only, to find the row changes that no
    feature shows."""
    out = {}
    for name, tab in T.items():
        if name in ('ex_input', 'ex_output', 'input'):
            continue
        rows = tab['rows'].get(ex, tab['rows'].get('task'))
        if rows is not None:
            out[name] = hashlib.blake2b(json.dumps(canonical(tab, rows)).encode(), digest_size=6).hexdigest()
    return out


def main(task, out_dir, src=None):
    src = Path(src) if src else Path(__file__).parent / 'out' / (task + '.variants.jsonl')
    dst = Path(out_dir) / (task + '.variants.jsonl')
    dst.parent.mkdir(parents=True, exist_ok=True)
    done = {r['id'] for r in J.records(dst)}
    eng = C.Engine(task)
    s, bj, T0 = eng.s, eng.bj, eng.T0
    graph = E.reads(s.text)
    rd = E.table_reads(s.text)
    up = lambda g, name: E.upstream(g, name)
    todo = [{k: v for k, v in r.items() if k not in ('features', 'error', 'digests', 'examples')} for r in J.records(src) if r['id'] not in done]  # the variant without the values this run computes again
    t0 = time.time()
    n = 0
    fcache = F.FeatureCache()  # the features of tables that a variant leaves as they were

    def write(rec):
        nonlocal n
        fo.write(rec)
        n += 1
        if n % 200 == 0 or n == len(todo):
            el = time.time() - t0
            print('%s %d/%d  %.1f/s  eta %.0fs' % (task, n, len(todo), n / el, (len(todo) - n) * el / n), flush=True)

    def featured(rec, T, tj, ex):
        rec['features'] = R.enc(F.all_features(T, ex, tj, graph, up, R.grids_of, fcache, reads=rd, prov=s.provenance))
        rec['digests'] = digests(T, ex)
        return rec

    want = {r['id']: r for r in todo if r['kind'] != 'base' and ('grid' in r or r['kind'] == 'out')}
    with J.Appender(dst) as fo, C.Cache(task, eng, hold=False) as cache:
        for r in todo:
            if r['kind'] == 'base':
                rec = dict(r)
                try:
                    exs = ['train/%d' % j for j in range(len(bj['train']))] + ['test/%d' % j for j in range(len(bj['test']))]
                    rec['examples'] = {ex: R.enc(F.all_features(T0, ex, bj, graph, up, R.grids_of, fcache, reads=rd, prov=s.provenance)) for ex in exs}
                    rec['tables'] = {name: [list(c) for c in t['columns']] for name, t in T0.items()}
                    rec['graph'] = {k: sorted(v) for k, v in graph.items()}
                    rec['reads_ports'] = {k: sorted(v) for k, v in E.reads_ports(s.text).items()}
                    rec['out'] = s.out
                    rec['digests'] = {ex: digests(T0, ex) for ex in exs}
                except Exception as e:  # noqa: BLE001
                    rec['error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
                write(rec)
        for r, T, tj, ex in cache.hits(want):
            rec = dict(r)  # the copy holds the features, so that todo holds none
            try:
                featured(rec, T, tj, ex)
            except Exception as e:  # noqa: BLE001
                rec['error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
            write(rec)
        for r in todo:
            if r['kind'] == 'base' or ('grid' in r or r['kind'] == 'out') and r['id'] not in want:
                continue
            rec = dict(r)
            try:
                if r['id'] in want:
                    write(featured(rec, *cache.tables(rec)))
                    continue
            except Exception as e:  # noqa: BLE001
                rec['error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
            write(rec)
    print('%s feature cache: %d tables from the cache, %d computed' % (task, fcache.hits, fcache.misses), flush=True)


if __name__ == '__main__':
    main(*sys.argv[1:4])
