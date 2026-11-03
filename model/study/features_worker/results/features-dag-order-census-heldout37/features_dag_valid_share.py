#!/usr/bin/env python
"""The share of a form's `join` orders that the engine accepts, with no walk.

  SAMPLER_CODE=<sampler> <runtime python> -u features_dag_valid_share.py [--out DIR] [--tasks FILE] [--draws 256] [--shard K/N] [--task T] [--line I] [--seconds S] [--dry]

For each form (RULE, DET, INIT of the held tasks, as the census takes them), up to --draws distinct topological orders of its `join` DAG:
seeds 0, 1, 2, ... of FormDag.random_order, each order once, or every order where the form has no more than --draws. Each order is rendered, and the engine's check
(StudyProgram.from_sexp(...).decode_stream(), the first step of or_q.gold_rest) runs on the scope of the census arm `parents`, seed-s (the scope is the order of seed s
of ProgramDag.random_order over the form's ancestors), the rendered form, and the reader's OUT. A refusal is counted by its message with the path and its numbers left out.

Writes OUT/valid-share[-shardKofN].jsonl, one row per form as it is done: task, line, kind, n_orders (null past the cap), tried, accepted, refused (message -> count),
accepted_seeds (the seeds in 0..7 that the engine accepted, null where the form is enumerated), seconds, code. A rerun skips the forms in OUT/valid-share*.jsonl.
"""
import argparse
import collections
import glob
import itertools
import json
import os
import re
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-order-census-heldout37')  # the data folder
sys.path.insert(0, str(HERE))
import features_dag_census as C  # noqa: E402
import features_dag_order as D  # noqa: E402

PATH = re.compile(r'Path\(NodePath\(\[.*?\]\)\)|\bat Places\(\[.*?\]\)|\d+')


def refusal(e: Exception) -> str:
    """The message's first words: its kind and the start of its reason, with no path and no number."""
    text = str(e).replace('\n', ' ')
    head, _, reason = text.partition('): ')
    head = PATH.sub('', head + ')' if reason else head).replace('  ', ' ').strip()
    reason = PATH.sub('', reason or '')
    return ('%s: %s' % (head, ' '.join(reason.split()[:8]))) if reason else ' '.join(head.split()[:10])


def body_orders(dag: D.FormDag, path: str) -> list[list[str]]:
    """Every topological order of a body's items."""
    preds = dag.item_preds[path]
    out: list[list[str]] = []

    def go(done: list[str], left: set[str]):
        if not left:
            out.append(list(done))
            return
        for i in sorted(left):
            if preds[i] <= set(done):
                go(done + [i], left - {i})
    go([], set(preds))
    return out


def all_orders(dag: D.FormDag):
    """Every order of the form: the product over its bodies."""
    paths = [b.path for b in dag.all_bodies]
    for combo in itertools.product(*[body_orders(dag, p) for p in paths]):
        yield dict(zip(paths, combo))


def draws(dag: D.FormDag, n: int, cap_seeds: int):
    """(seed or None, order) pairs: every order once where the count is at most n, else the first n distinct random orders."""
    if dag.n_orders is not None and dag.n_orders <= n:
        for k, o in enumerate(all_orders(dag)):
            yield None, o
        return
    seen, got = set(), 0
    for s in range(cap_seeds):
        o = dag.random_order(s)
        key = json.dumps(o, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        got += 1
        yield s, o
        if got >= n:
            return


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--points', default=str(C.BASE / 'points-base.json'))
    ap.add_argument('--corpus', default=str(C.ROOT / 'work/lm/data-study/gold/gold-v3-helper-forms-a036da074/corpus-view'))
    ap.add_argument('--out', default=str(HERE))
    ap.add_argument('--tasks', default=str(C.WORKER / 'held/tasks.txt'))
    ap.add_argument('--draws', type=int, default=256)
    ap.add_argument('--mode', default='join', choices=['binder', 'join'])
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--task', default=None)
    ap.add_argument('--line', type=int, default=None)
    ap.add_argument('--seconds', type=float, default=None)
    ap.add_argument('--dry', action='store_true')
    ap.add_argument('--file', default=None, help='output file name in OUT (default valid-share[-shardKofN].jsonl)')
    a = ap.parse_args()
    shard, shards = map(int, a.shard.split('/'))
    if C.so_hash() != C.WHEEL_SO:
        sys.exit('arclog in %s is not the wheel %s' % (C.ENGINE_PATH, C.WHEEL_SO))
    code = C.code_hash()
    want = json.load(open(Path(a.out) / 'manifest.json')).get('sampler_code', {}).get('hash') if (Path(a.out) / 'manifest.json').exists() else None
    if want and want != code:
        sys.exit('the sampler code hash is %s and the manifest has %s' % (code, want))
    os.environ.update(STEER_COVER='init,branch', SAMPLER_CORPUS=a.corpus.rstrip('/') + '/', SEARCH_MODELS=str(C.BASE / 'models-base'), RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    sys.path[:0] = [str(C.ENGINE_PATH), str(C.SAMPLER_CODE)]
    tasks = [t for t in open(a.tasks).read().split() if a.task in (None, t)]
    gold = C.golds(None, a.points, tasks)
    out_path = os.path.join(a.out, a.file or ('valid-share%s.jsonl' % ('' if shards == 1 else '-shard%dof%d' % (shard, shards))))
    done = set()
    for p in glob.glob(os.path.join(a.out, 'valid-share*.jsonl')):
        for line in open(p):
            r = json.loads(line)
            done.add((r['task'], r['line']))
    forms, todo = 0, []
    import live  # noqa: E402  # pyright: ignore[reportMissingImports]
    import live_try  # noqa: E402  # pyright: ignore[reportMissingImports]
    arclog = live.arclog
    for t in tasks:
        for i, text in enumerate(gold[t]):
            kind = text.split()[0].lstrip('(')
            if kind not in ('RULE', 'DET', 'INIT') or kind not in live.KIND_TOK:
                continue
            forms += 1
            if (forms - 1) % shards != shard or (a.line is not None and i != a.line):
                continue
            if (t, i) not in done:
                todo.append((t, i, kind))
    print('%d forms over all shards, %d to do on shard %d/%d, %d done, code %s' % (forms, len(todo), shard, shards, len(done), code), flush=True)
    if a.dry:
        return
    t0, n_done, n_checks = time.time(), 0, 0
    session = (None, None)
    with open(out_path, 'a') as f:
        for w, (t, i, kind) in enumerate(todo, 1):
            if a.seconds and time.time() - t0 > a.seconds:
                print('budget of %.0f s spent' % a.seconds, flush=True)
                break
            t1 = time.time()
            lines = gold[t]
            if session[0] != t:
                session = (t, live_try.session_of(t)[0])
            sess = session[1]
            dag = D.FormDag(lines[i], a.mode)
            dag.n_orders = dag.count_orders()
            prog = D.ProgramDag(lines)
            key = 'OUT' if lines[i].startswith('(OUT') else D.parse(lines[i])[1]
            parents = prog.ancestors(key)
            head = {('OUT' if x.startswith('(OUT') else D.parse(x)[1]): j for j, x in enumerate(lines)}
            scopes: dict[int, list[str]] = {}
            tried, accepted, refused, seeds_ok = 0, 0, collections.Counter(), []
            for k, (seed, order) in enumerate(draws(dag, a.draws, 4 * a.draws)):
                s = k if seed is None else seed
                if s not in scopes:
                    scopes[s] = prog.texts(prog.random_order(s, parents))
                target = dag.render(order)
                tried += 1
                try:
                    arclog.StudyProgram.from_sexp('\n'.join((*scopes[s], target, live.READER_OUT)), sess.settings).decode_stream()
                    accepted += 1
                    if seed is not None and seed < 8:
                        seeds_ok.append(seed)
                except Exception as e:  # noqa: BLE001
                    refused[refusal(e)] += 1
            n_checks += tried
            sec = round(time.time() - t1, 2)
            f.write(json.dumps(dict(task=t, line=i, kind=kind, n_orders=dag.n_orders, tried=tried, accepted=accepted, refused=dict(refused.most_common()),
                                    accepted_seeds=seeds_ok if dag.n_orders is None or dag.n_orders > a.draws else None, seconds=sec, code=code)) + '\n')
            f.flush()
            n_done += 1
            el = time.time() - t0
            print('[%d/%d %ds %.2f forms/s %.0f checks/s eta %ds] %s:%d %s n_orders %s tried %d accepted %d %.1fs' % (
                w, len(todo), el, n_done / el, n_checks / el, el / n_done * (len(todo) - w), t, i, kind, dag.n_orders, tried, accepted, sec), flush=True)
    print('done: %d forms, %d checks in %.0f s' % (n_done, n_checks, time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
