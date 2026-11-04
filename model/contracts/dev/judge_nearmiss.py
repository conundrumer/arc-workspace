"""Dev labeling layer: the near-miss output worlds of a task, which relevance.py reads. Not model input.

    <runtime python> -I -B judge_nearmiss.py OUT_DIR TASK [TASK ...]

A task's near misses are the outputs of the wrong readings of its rule in ../nearmiss/<task>.py, a handwritten module whose ALTERNATIVES
lists (description, function) pairs; a function takes a train pair's input and output grids and gives a wrong output, or None. Each near miss
stands as its pair's train output against the pair's own input. Each world holds every table's features at the pair's example, computed
against that output (the tables are the task's own run, since a near miss changes no table that does not read the train outputs), and the
base tables' features against it. A grid that is not rectangular, holds a value outside 0-9, or equals the true output is dropped, and equal
grids of one pair are one.

Writes OUT_DIR/<task>.nearmiss.jsonl: a base record with the train examples and the forms that read the train outputs (directly, through a
task parameter whose proposer reads them, or through other forms that do), one record per near miss, and an end record.
"""
import copy
import importlib.util
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'features'))
import engine as E  # noqa: E402
import features as F  # noqa: E402
import jsonl as J  # noqa: E402
import query as Q  # noqa: E402
import run as R  # noqa: E402
import tablecache as C  # noqa: E402
from judge_worlds import base_of  # noqa: E402

NEARMISS = Path(__file__).parent.parent / 'nearmiss'
# the proposers whose values the lib defines from the train outputs
OUTPUT_PROPOSERS = {'AnyOutNewColor', 'VanishedColor', 'ChangedColor', 'UnchangedColor', 'ScaleRatio', 'DivisorRatio', 'ConstOutDim',
                    'ConstOutDimAxis', 'TileD4', 'PanelCombine'}


def output_readers(text):
    """The forms whose tables read the train outputs, as the module's docstring gives."""
    qf, rd = Q.query_features(text), E.table_reads(text)
    out = {f for f, used in rd.items() if 'ex_output' in used} | {f for f, q in qf.items() if q.get('proposer') in OUTPUT_PROPOSERS}
    while True:
        more = {f for f, used in rd.items() if f not in out and any(u.split('.')[0] in out for u in used)}
        if not more:
            return out
        out |= more


def valid(g):
    return isinstance(g, list) and bool(g) and all(isinstance(r, list) and r and len(r) == len(g[0]) for r in g) and \
        all(isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= 9 for r in g for x in r)


def main(out_dir, tasks):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        t0 = time.time()
        spec = importlib.util.spec_from_file_location('nearmiss_' + task, NEARMISS / (task + '.py'))
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception as e:  # noqa: BLE001
            print('%s: the near-miss module does not load: %s' % (task, e), flush=True)
            continue
        eng = C.Engine(task)
        s, bj, T0 = eng.s, eng.bj, eng.T0
        graph, rd = E.reads(s.text), E.table_reads(s.text)
        up = lambda g, name: E.upstream(g, name)
        fcache = F.FeatureCache()
        dst = out_dir / (task + '.nearmiss.jsonl')
        for p in (dst, Path(str(dst) + '.zst')):
            if p.exists():
                p.unlink()
        n = dropped = 0
        with J.Appender(dst) as fo:
            worlds = {'train/%d' % j: dict(features=R.enc(F.all_features(T0, 'train/%d' % j, bj, graph, up, R.grids_of, fcache, reads=rd,
                                                                       prov=s.provenance)), base=base_of(bj, 'train/%d' % j))
                      for j in range(len(bj['train']))}
            fo.write(dict(id='base', task=task, examples=worlds, output_readers=sorted(output_readers(s.text))))
            for j, p in enumerate(bj['train']):
                ex, true, seen = 'train/%d' % j, p['output'], set()
                for k, (why, fn) in enumerate(mod.ALTERNATIVES):
                    try:
                        g = fn(copy.deepcopy(p['input']), copy.deepcopy(true))
                    except Exception:  # noqa: BLE001
                        g = None
                    if g is None:
                        continue
                    if not valid(g) or g == true or json.dumps(g) in seen:
                        dropped += 1
                        continue
                    seen.add(json.dumps(g))
                    tj = copy.deepcopy(bj)
                    tj['train'][j]['output'] = g
                    try:
                        rec = dict(id='nearmiss.%d.%d' % (j, k), ex=ex, why=why,
                                   features=R.enc(F.all_features(T0, ex, tj, graph, up, R.grids_of, fcache, reads=rd, prov=s.provenance)),
                                   base=base_of(tj, ex))
                    except Exception as e:  # noqa: BLE001
                        rec = dict(id='nearmiss.%d.%d' % (j, k), error='%s: %s' % (type(e).__name__, str(e)[:200]))
                    fo.write(rec)
                    n += 1
            fo.write(dict(id='end', n=n))
        print('%s done: %d near misses, %d dropped, %.0f s' % (task, n, dropped, time.time() - t0), flush=True)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
