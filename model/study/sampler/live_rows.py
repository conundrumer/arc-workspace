#!/usr/bin/env python
"""Rows for the rel steer and the choice steer from gold's walk through live.py, in the files that relcheap.py and choicecheap.py read.

  <runtime python> live_rows.py run --out DIR [--part train|test|all] [--models DIR | --models-fold TEMPLATE --folds N] [--orders N] [--jobs N]
                                    [--scope parents|before] [--tasks FILE] [--limit N] [--leave-out FILE]
  <runtime python> live_rows.py folds --out DIR [--folds N] [--leave-out FILE]

A row is the row that a steer scores at that pick of a draw, built by the Drawer's own function (sample2_col's rel_row, choice_consult_row and
stop_consult_row), with gold's pick as `gold`. Gold's clause is walked as or_q.py walks it, with each choice taken to be gold's, so a row exists
wherever the walk consults a steer: the atoms of a RULE's or a DET's body, of an INIT's key and ports, of the branches of an OR (nested ones
too) and of an ALL, with the stops after the atoms of a body. A row has `where` ('body', 'branch', 'nested', 'ALL'), `place` ('RULE', 'DET', 'key',
'port'), `kind` (the form's), `order` and `point` ([form index, 0]). STEER_COVER is 'init,branch' here, so that the rows of an INIT body and of a
later branch's first atom exist; a draw consults them only under the same setting. Rows go to DIR/relrows.jsonl.zst and DIR/choices.jsonl.zst, and
a task's status line to DIR/tasks.jsonl, which a restart reads to skip the tasks it holds.

The scope of a form is its ancestors by reads (parents) or every gold form before it (before). A form's walk uses the priors of its task's fold, fit
without that fold's tasks and the leave-out tasks (`folds` writes the lists), so that P at a row is not fit on the row's own task. Order 0 is
gold's written atom order. With --orders n, a RULE or a DET body of plain atoms (no OR, IF or ALL) also gives the rows of up to n - 1 random valid
orders, each a walk that ends cleanly; the live draw's atoms have no order, as ROW_ORDERS rows have.

  scripts/run_heavy.py --cpus N --need soon <runtime python> -u live_rows.py run --out DIR --jobs N
"""
import os

os.environ['STEER_COVER'] = 'init,branch'  # sample2_col reads this when it is imported

import argparse
import collections
import concurrent.futures as cf
import json
import random
import re
import resource
import subprocess
import sys
import time
import traceback
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live  # noqa: E402
import live_try  # noqa: E402
import or_q  # noqa: E402
import sample2_col as S  # noqa: E402
import sampler_paths as P  # noqa: E402
from live import M  # noqa: E402

sys.path.append(P.CODE)
from judge3.framed_jsonl import JsonlWriter  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LEAVE_OUT = P.SAMPLER_DATA + '/sampler-worker/held/leave_out.txt'
NAME = re.compile(r'&[A-Za-z_0-9]+')
FOLDS = 6
GOLD_REVISION = 'gold-v3-drift-regold-ba59a0ab1'  # the gold of corpus-v3mix (symlinks to gen-v3 ast-corpus) that the rows read
TEST_SHARE = 6  # one task in this many is a test task
ORDER_ATOMS = 12  # a body of more atoms than this gives its written order alone


def fold_of(task, n):
    return zlib.crc32(('fold' + task).encode()) % n


def is_test(task):
    return zlib.crc32(('test' + task).encode()) % TEST_SHARE == 0


def task_list(a):
    """The tasks of the run: the corpus tasks with gold, less the leave-out tasks and those of the other part."""
    leave = set(open(a.leave_out).read().split())
    if a.tasks:
        tasks = open(a.tasks).read().split()
    else:
        tasks = sorted(t for t in os.listdir(S.CORPUS) if t not in leave and S.corpus_forms(t))
    tasks = [t for t in tasks if t not in leave and (a.part == 'all' or is_test(t) == (a.part == 'test'))]
    return tasks[:a.limit] if a.limit else tasks


def gold_lines(task):
    """The lines of the first gold program of the task in the corpus, less its OUT."""
    import gzip
    with gzip.open(S.CORPUS + task + '/pairs.jsonl.gz', 'rt') as f:
        sexp = json.loads(f.readline())['gold_sexp']
    return [x for x in sexp.splitlines() if x.strip()]


def parents(lines, i):
    """The indexes before i of the forms that line i reads, directly or not, in order."""
    head = {NAME.search(x)[0]: j for j, x in enumerate(lines) if NAME.search(x)}
    got, todo = set(), [i]
    while todo:
        for n in NAME.findall(lines[todo.pop()]):
            j = head.get(n)
            if j is not None and j < i and j not in got:
                got.add(j)
                todo.append(j)
    return sorted(got)


def atoms_of(run, sess, scope, target):
    """gold's atoms of a RULE or a DET target as token lists (its kind token and last END left out), or None where a token is not an atom's."""
    ids, model, paths = live.arclog.StudyProgram.from_sexp('\n'.join((*scope, target, live.READER_OUT)), sess.settings).decode_stream()
    toks = [(t, p) for t, m, p in zip(ids, model, paths) if m and p[0] == len(scope)]
    by = collections.defaultdict(list)
    for t, p in toks:
        if len(p) > 2:
            by[p[2]].append(t)  # the path is the point [form, 0] and then the atom; the form's own tokens (kind, END) have none
    atoms = list(by.values())
    V = run.V
    ok = all(a[0] == M.NOT or a[0] in M.CMP or V.kind(a[0]) in S.RELATION_KINDS for a in atoms)
    return atoms if ok and sum(map(len, atoms)) == len(toks) - 2 else None


def orders_of(run, sess, task, index, scope, target, n):
    """Up to n - 1 token deques of valid random orders of a plain body's atoms (S's reorder: a NOT or a comparison after the labels it reads)."""
    atoms = atoms_of(run, sess, scope, target)
    if atoms is None or not 1 < len(atoms) <= ORDER_ATOMS:
        return []
    sites = S.label_sites(run.V, atoms)
    seen, out = {tuple(map(tuple, atoms))}, []
    for o in S.random_orders(range(len(atoms)), random.Random(M.seed_of(task, index, 'orders'))):
        new = S.reorder(atoms, sites, o, run.ff0.label_tok)
        if new is None or tuple(map(tuple, new)) in seen:
            continue
        seen.add(tuple(map(tuple, new)))
        out.append((len(out) + 1, new))
        if len(out) >= n - 1:
            break
    return out


def form_rows(sampler, task, lines, i, sess, task_json, scope_mode, orders):
    """([(kind, row)], status) of the walks of form i: its written order and the extra orders."""
    kind = lines[i].split()[0].lstrip('(')
    keep = parents(lines, i) if scope_mode == 'parents' else list(range(i))
    scope, target = [lines[j] for j in keep], lines[i]
    t0 = time.time()
    out, status = [], dict(i=i, kind=kind, scope=len(scope), orders=0)
    walks = [(0, None)]
    if orders > 1 and kind in ('RULE', 'DET'):
        run0 = or_q.GuidedRun(sampler.pri, sess, time.monotonic() + 120, task_json, live.Limits(form_tries=1))
        walks += orders_of(run0, sess, task, i, scope, target, orders)
    for order, atoms in walks:
        rows = []
        rec = or_q.walk(sampler, task, 'live', [i, 0], scope, target, sess, task_json, kind, rows, atoms)
        clean = not rec['bad'] and rec['dead'] is None and not rec['left']
        if order == 0:
            status.update(bad=rec['bad'][:3], dead=rec['dead'], left=rec['left'], total=rec['total'], clean=clean)
        elif not clean:
            status['orders_refused'] = status.get('orders_refused', 0) + 1
            continue
        status['orders'] += 1
        for k, row in rows:
            row.update(task=task, case='live', point=[i, 0], kind=kind, order=order)
            out.append((k, row))
    status['seconds'] = round(time.time() - t0, 2)
    return out, status


SAMPLERS = {}


def sampler_of(models):
    if models not in SAMPLERS:
        SAMPLERS[models] = live.Sampler(models, ('struct',))  # P's structural logits, which the steers' rows were fit under; the steers themselves are off
    return SAMPLERS[models]


def task_rows(args):
    """(task, rows, statuses) for all the forms of a task."""
    task, models, scope_mode, orders = args
    t0 = time.time()
    sampler = sampler_of(models)
    lines = gold_lines(task)
    sess, task_json, _ = live_try.session_of(task)
    rows, statuses = [], []
    for i, line in enumerate(lines):
        kind = line.split()[0].lstrip('(')
        if kind not in live.KIND_TOK:
            continue
        if kind in ('RULE', 'DET') and re.match(r'\((RULE|DET) \S+ [A-Za-z]\S*\)$', line.strip()):  # a proposer form: its pick is a count, which no steer scores
            statuses.append(dict(i=i, kind=kind, proposer=True))
            continue
        try:
            got, status = form_rows(sampler, task, lines, i, sess, task_json, scope_mode, orders)
        except Exception as e:  # noqa: BLE001
            got, status = [], dict(i=i, kind=kind, error='%s: %s' % (type(e).__name__, str(e)[:200]), trace=traceback.format_exc()[-400:])
        rows += got
        status['rows'] = dict(collections.Counter(k for k, _ in got))
        statuses.append(status)
    return task, rows, statuses, round(time.time() - t0, 1), round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e9, 2)


def git(*cmd):
    try:
        return subprocess.run(['git', *cmd], cwd=HERE, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def manifest(a, tasks, extra=None):
    m = dict(command=' '.join(sys.argv), commit=git('rev-parse', 'HEAD'), uncommitted=bool(git('status', '--porcelain', '--', HERE)),
             task_set='corpus-v3mix tasks with gold, less the %d leave-out tasks of %s; part %s: %d tasks' % (len(set(open(a.leave_out).read().split())), a.leave_out, a.part, len(tasks)),
             budget='no search budget: a teacher-forced walk of each gold form', measures=['rows for the rel steer and the choice steer'],
             corpus=S.CORPUS, gold_revision=GOLD_REVISION, scope=a.scope, orders=a.orders, models=a.models or a.models_fold, folds=a.folds, steer_cover=sorted(S.STEER_COVER),
             started=time.strftime('%Y-%m-%d %H:%M:%S'))
    return m | (extra or {})


def run(a):
    tasks = task_list(a)
    os.makedirs(a.out, exist_ok=True)
    done = set()
    sp = os.path.join(a.out, 'tasks.jsonl')
    if os.path.exists(sp):
        done = {json.loads(x)['task'] for x in open(sp) if x.strip()}
    todo = [t for t in tasks if t not in done]
    mp = os.path.join(a.out, 'manifest.json')
    if not os.path.exists(mp):
        json.dump(manifest(a, tasks), open(mp, 'w'), indent=1)
    print('%d tasks, %d done, %d to do, %d jobs' % (len(tasks), len(done), len(todo), a.jobs), flush=True)
    work = [(t, (a.models_fold.format(fold_of(t, a.folds)) if a.models_fold else a.models), a.scope, a.orders) for t in todo]
    t0, total = time.time(), collections.Counter()
    with (cf.ProcessPoolExecutor(a.jobs) as ex, JsonlWriter(os.path.join(a.out, 'relrows.jsonl.zst')) as rel, JsonlWriter(os.path.join(a.out, 'choices.jsonl.zst')) as ch,
          open(sp, 'a') as sf):
        futs = [ex.submit(task_rows, w) for w in work]
        for n, fu in enumerate(cf.as_completed(futs), 1):
            try:
                task, rows, statuses, secs, rss = fu.result()
            except Exception as e:  # noqa: BLE001
                print('FAILED %s' % e, flush=True)
                continue
            c = collections.Counter()
            for k, row in rows:
                (rel if k == 'rel' else ch).write(row)
                c[k, row.get('kind'), row['place'], row['where']] += 1
            rel.flush()
            ch.flush()
            sf.write(json.dumps(dict(task=task, seconds=secs, maxrss_gb=rss, forms=statuses, rows={'|'.join(map(str, k)): v for k, v in c.items()})) + '\n')
            sf.flush()
            total.update(c)
            el = time.time() - t0
            print('[%d/%d %.0fs %.2f tasks/s eta %.0fs] %s %d rows, %d forms, %.1fs, rss %.1f GB' % (
                n, len(todo), el, n / el, el / n * (len(todo) - n), task, len(rows), len(statuses), secs, rss), flush=True)
    m = json.load(open(mp))
    m.update(finished=time.strftime('%Y-%m-%d %H:%M:%S'), rows_this_run={'|'.join(map(str, k)): v for k, v in sorted(total.items())})
    json.dump(m, open(mp, 'w'), indent=1)
    print('TOTAL', dict(sorted(total.items())), flush=True)


def folds(a):
    """Writes DIR/fold<i>-leave_out.txt: the leave-out tasks and the corpus tasks of fold i."""
    leave = set(open(a.leave_out).read().split())
    tasks = sorted(t for t in os.listdir(S.CORPUS) if S.corpus_forms(t))
    os.makedirs(a.out, exist_ok=True)
    for i in range(a.folds):
        with open(os.path.join(a.out, 'fold%d-leave_out.txt' % i), 'w') as f:
            f.write('\n'.join(sorted(leave | {t for t in tasks if fold_of(t, a.folds) == i})) + '\n')
    print('%d folds written to %s' % (a.folds, a.out))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=('run', 'folds'))
    ap.add_argument('--out', required=True)
    ap.add_argument('--part', default='train', choices=('train', 'test', 'all'), help='test: one task in %d, by hash; train: the rest' % TEST_SHARE)
    ap.add_argument('--models', default='', help='a models directory (live_priors.pkl) for every task')
    ap.add_argument('--models-fold', default='', help='a models directory with {} for the task fold, as in DIR/fold{}')
    ap.add_argument('--folds', type=int, default=FOLDS)
    ap.add_argument('--scope', default='parents', choices=('parents', 'before'))
    ap.add_argument('--orders', type=int, default=1, help='orders of a plain RULE or DET body: its written order and up to this many less one random ones')
    ap.add_argument('--jobs', type=int, default=1)
    ap.add_argument('--tasks', default='', help='a file of tasks, one a line, in place of the corpus')
    ap.add_argument('--limit', type=int, default=0, help='the first n tasks')
    ap.add_argument('--leave-out', default=LEAVE_OUT)
    a = ap.parse_args()
    if a.cmd == 'folds':
        return folds(a)
    if bool(a.models) == bool(a.models_fold):
        ap.error('give --models or --models-fold')
    run(a)


if __name__ == '__main__':
    main()
