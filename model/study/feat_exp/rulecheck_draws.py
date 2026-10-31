"""Run the hard rule keys over the sampler's draws and write the keys that fire on each draw.

Usage: /Users/davidlu/code/arc-workspace/work/lm/.venv/bin/python rulecheck_draws.py DRAWS.jsonl.zst OUT.jsonl.zst
           [--rules FILE] [--workers N] [--names NAMES.json] [--read-later-clauses]

At a DET point the stored G keeps only the body columns that later clauses name, so the stored G depends on the
program after the point and the features at a DET point see different columns in stored data and in draws. A
draw gives its columns as `x['read']` if it has one; otherwise X keeps every non-Example body column, which is all
that is known without later clauses. `--read-later-clauses` takes `read` from the program's lines after the point
(`rulecheck.reader_fields`). It reads later clauses, so use it only for the equality check of gold against stored
data, never for the candidates of a search.

Run it through scripts/run_heavy.py with --cpus N. It writes one JSON line per draw in the order of the draws file, as framed zstd JSONL (`judge3.framed_jsonl`), to
an OUT that does not exist yet:

    task, case, point, draw, gold, status, hard (keys of the rule set that fire), soft (other keys of the functions
    run that fire), unmapped (relation names of the clause that still have the sampler's spelling), and for a gold
    draw gold_diff: {key: [value from the draw, value from the on-disk gold view]} for each key of the functions run
    that differs, and gold_diff_hard: those of them that are keys of the rule set.

status is `ok`, `no clause` (the draw has no clause: it failed), `no point dir` (no exported point has that task,
case and point) or `error: ...`. A point is exported in `fstore/points/` only for some clauses of a case, so the
draws of a point without a directory cannot run.

The sampler names relations `&r0`, `&r1`, ... and the exported programs name them as written. `--names` is a JSON file
{"task|case|point": {"&r2": "&legend", ...}} (point as JSON text, e.g. "7d18a6fb|$Concat|[3, 0]"). Without an entry,
the names come from aligning gold's clause of the draws with the program's gold line, which covers only the relations
that gold's clause uses; the candidates of that point may read others, and `unmapped` lists them.

The on-disk gold view of a gold draw is `RuleCheck.values` on the point's G table and the program's gold line, the same
view as `featlib.Pair.gold` (tested equal). The gold line and G are read only for that comparison and for the name
alignment, never for a candidate.
"""
import argparse
import hashlib
import collections as C
import json
import multiprocessing as mp
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import featlib  # noqa: E402
from judge3.framed_jsonl import JsonlWriter, iter_lines  # noqa: E402
import rulecheck  # noqa: E402
from rulecheck import RuleCheck, names_from_gold, rename_relations  # noqa: E402

# FSTORE_POINTS: a points root other than the feature store's (for example a store built from another gold corpus)
POINTS = Path(os.environ['FSTORE_POINTS']) if os.environ.get('FSTORE_POINTS') else featlib.FSTORE / 'points'


DRAW_HEAD = re.compile(rb'^\{"task":\s*"([^"\\]*)",\s*"case":\s*"([^"\\]*)",\s*"point":\s*(\[[0-9,\s]*\]),\s*"draw":\s*(\d+)')


def read_draws(path, skip=(), parse=json.loads):
    """The draws of the file (framed zstd, gzip or plain JSONL), each line given to parse; a file that is still being
    written is read up to its last complete line. A draw whose `task|case|point|draw` is in skip is left out without
    parsing its line."""
    rows = []
    try:
        for line in iter_lines(path):
            if skip:
                m = DRAW_HEAD.match(line if isinstance(line, bytes) else line.encode())
                if m and (f'{m[1].decode()}|{m[2].decode()}|{json.dumps(json.loads(m[3]))}|{m[4].decode()}'
                          in skip):
                    continue
            try:
                rows.append(parse(line))
            except ValueError:
                break
    except EOFError:
        pass
    return rows


POINT_INDEX = featlib.DATA / 'point-index.json'
if os.environ.get('FSTORE_POINTS'):  # one index per points root
    POINT_INDEX = POINT_INDEX.with_name('point-index-%s.json' % hashlib.sha1(str(POINTS).encode()).hexdigest()[:10])


def point_dirs(tasks):
    """{(task, case, json point): directory name} of the exported points of those tasks. A point's `point.json` is read
    only where POINT_INDEX has no entry for it at the file's modification time; new entries are written back."""
    try:
        index = json.loads(POINT_INDEX.read_text())
    except (OSError, ValueError):
        index = {}
    out, changed = {}, False
    for d in sorted(os.listdir(POINTS)):
        if d.split('-')[0] not in tasks:
            continue
        path = POINTS / d / 'point.json'
        try:
            mtime = path.stat().st_mtime
        except OSError:
            continue
        hit = index.get(d)
        if hit is None or hit[0] != mtime:
            pj = featlib.load(path)
            hit = index[d] = [mtime, pj['task'], pj['case'], json.dumps(pj['point'])]
            changed = True
        out[tuple(hit[1:])] = d
    if changed:
        tmp = POINT_INDEX.with_suffix(f'.{os.getpid()}.tmp')
        tmp.write_text(json.dumps(index))
        tmp.replace(POINT_INDEX)
    return out


def same(a, b):
    if a is None or b is None:
        return a is b
    if isinstance(a, float) or isinstance(b, float):
        return a == b or (a != a and b != b)
    return a == b


def run_point(job):
    key, dname, draws, rules, names_in, later = job
    out = []
    try:
        rc = RuleCheck(POINTS / dname, rules)
        gold_line = [l for l in (POINTS / dname / 'gold.arclog').read_text().splitlines() if l.strip()][rc.point[0]]
        named = None
        if later:
            program = [l for l in (POINTS / dname / 'gold.arclog').read_text().splitlines() if l.strip()]
            named = rulecheck.reader_fields(program[rc.point[0] + 1:], rulecheck.parse(gold_line)[0][1])
        golds = [d for d in draws if d.get('gold') and d.get('clause')]
        names = names_in or (names_from_gold(golds[0]['clause'], gold_line) if golds else {})
    except Exception as e:
        return [(d['_i'], dict(status=f'error: {type(e).__name__}: {str(e)[:80]}')) for d in draws]
    for d in draws:
        res = {}
        if d.get('fail') or not d.get('clause') or not d.get('x') or not d.get('x_rows'):
            res['status'] = 'no clause'
            out.append((d['_i'], res))
            continue
        try:
            clause = rename_relations(d['clause'], names)
            if named is not None and any(item[0][0] == 0 for item in d['x_rows']) and d['x'].get('read') is None:
                d['x']['read'] = [l for l in d['x']['labels'] if l in named]
            res['unmapped'] = sorted(set(re.findall(r'&r\d+', clause)))
            x = rc.draw_x(d, clause)
            vals = rc.values(clause, x, out_reads=rc.gold_out_reads(clause))
            fires = sorted(k for k, v in vals.items() if rulecheck._fires(v))
            res['hard'] = [k for k in fires if k in rc._rule_set]
            res['soft'] = [k for k in fires if k not in rc._rule_set]
            res['status'] = 'ok'
            if d.get('gold'):
                g = featlib.load(POINTS / dname / 'tables/G.json')
                disk = rc.values(gold_line, g, out_reads=rc.gold_out_reads(gold_line))
                res['gold_diff'] = {k: [vals.get(k), disk.get(k)] for k in vals.keys() | disk.keys()
                                    if not same(vals.get(k), disk.get(k))}
                res['gold_diff_hard'] = {k: v for k, v in res['gold_diff'].items() if k in rc._rule_set}
        except Exception as e:
            res['status'] = f'error: {type(e).__name__}: {str(e)[:80]}'
        out.append((d['_i'], res))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('draws')
    ap.add_argument('out')
    ap.add_argument('--rules', default=str(rulecheck.DEFAULT_RULES))
    ap.add_argument('--workers', type=int, default=int(os.environ.get('ARC_HEAVY_CPUS', 1)))
    ap.add_argument('--names')
    ap.add_argument('--read-later-clauses', dest='later', action='store_true',
                    help='choose a DET draw\'s columns from the clauses after the point (gold equality check only)')
    a = ap.parse_args()
    if Path(a.out).exists():
        sys.exit(f'{a.out} exists; give a new OUT')
    t0 = time.time()
    draws = read_draws(a.draws)
    for i, d in enumerate(draws):
        d['_i'] = i
    names_all = json.loads(Path(a.names).read_text()) if a.names else {}
    dirs = point_dirs({d['task'] for d in draws})
    by_point = C.OrderedDict()
    for d in draws:
        by_point.setdefault((d['task'], d['case'], json.dumps(d['point'])), []).append(d)
    jobs, results = [], {}
    for key, ds in by_point.items():
        if key in dirs:
            jobs.append((key, dirs[key], ds, a.rules, names_all.get('|'.join(key)), a.later))
        else:
            for d in ds:
                results[d['_i']] = dict(status='no point dir')
    print(f'{len(draws)} draws, {len(by_point)} points, {len(jobs)} with a point dir, {time.time() - t0:.0f}s', flush=True)
    if a.workers > 1:
        with mp.get_context('spawn').Pool(a.workers) as pool:
            for part in pool.imap_unordered(run_point, jobs):
                results.update(part)
    else:
        for j in jobs:
            results.update(run_point(j))
    status, gold_ok, gold_hard, gold_n = C.Counter(), 0, 0, 0
    with JsonlWriter(a.out) as f:
        for d in draws:
            r = results[d['_i']]
            status[r['status'].split(':')[0]] += 1
            if 'gold_diff' in r:
                gold_n += 1
                gold_ok += not r['gold_diff']
                gold_hard += not r['gold_diff_hard']
            f.write(dict(task=d['task'], case=d['case'], point=d['point'], draw=d['draw'], gold=d['gold'], **r))
    print(f'status {dict(status)}; gold draws of a point with a directory: {gold_n}, equal in every key {gold_ok}, equal in the rule keys {gold_hard}; wrote {a.out}; '
          f'{time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
