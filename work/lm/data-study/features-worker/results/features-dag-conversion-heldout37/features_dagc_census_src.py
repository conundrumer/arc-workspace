#!/usr/bin/env python
"""The census of gold's forms on DAG order: or_q.walk on each form with its body in topological orders and its scope from the program DAG, on the sampler code of the main checkout, with no edit to that code.

  <runtime python> -u features_dag_census.py [--view VIEW --revision NAME] [--out DIR] [--tasks FILE] [--models DIR] [--seeds 8] [--mode binder] [--shard K/N] [--task T] [--seconds S]

VIEW is a corpus view: <view>/<task>/pairs.jsonl.gz, whose first row's gold_sexp is the task's gold. It also sets SAMPLER_CORPUS. With no view, gold is --points, the base gold of the census. Each row names --revision. A form's arms:
  before / written: gold's text, the census row `before`.
  parents / written: the forms that it reads, directly or not, in gold's text, and the written body. The census row `parents`.
  nondesc / written: its non-descendants in gold's text, and the written body.
  parents or nondesc / canonical: the scope and the body in the canonical topological order.
  parents or nondesc / seed-N: the scope and the body in a random topological order.
  parents / body-seed-N: the scope in gold's text, and the body in a random topological order. It splits what the body order moves from what the scope order moves.

Arms with equal scope text and form text are one walk. Each walk has a session of its own, as frontier_q.py has. Writes OUT/census-dag[-shardKofN].jsonl, one row per form and arm, in the census row's fields and these:
  revision, order, scope, scope_order, gold_target (`target` is the rendered text), mode, n_orders (the form's topological orders, null past the cap), written_topological, same_clause, atom_ids and atom_depths (beside `atoms`), else_negations (ids of atoms that the walk takes with no pick), aligned, seconds, code.
and OUT/per-pick-dag[-shardKofN].tsv, one row per relation pick. A NOT has two picks on one atom. Columns are in COLUMNS. `downset` and `frontier` are short ids (features_dag_order.short of an atom's id), and `bits` is that pick's bits. A rerun skips finished rows.
"""
import argparse
import collections
import gc
import glob
import gzip
import hashlib
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path('/Users/davidlu/code/arc-workspace')
WORKER = ROOT / 'work/lm/data-study/sampler/sampler-worker'
BASE = WORKER / 'sampler-helper-forms/gold-v3-helper-forms-a036da074'
SAMPLER_CODE = Path(os.environ.get('SAMPLER_CODE', ROOT / 'model/study/sampler'))
ENGINE_PATH = ROOT / 'work/lm/data-study/ast/run/runtime-ba0754492/py313-path'
WHEEL_SO = '4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371'
CODE_FILES = 'live.py', 'or_q.py', 'search.py', 'search_gold.py', 'live_try.py', 'sample2_col.py', 'sample.py'
COLUMNS = ('revision', 'task', 'line', 'kind', 'scope', 'order', 'pick', 'phase', 'ctx', 'k', 'option', 'option_depth', 'option_kind', 'option_text', 'gold_relation', 'gold_kind', 'own', 'gold_alive',
           'n_options', 'prefix_size', 'downset', 'frontier', 'bits', 'form_ok')
REL_KINDS = ('lib relation', 'relation macro', 'fact relation', 'relation')

sys.path.insert(0, str(HERE))
import features_dag_order as D  # noqa: E402


def code_hash():
    h = hashlib.sha256()
    for name in CODE_FILES:
        h.update((SAMPLER_CODE / name).read_bytes())
    return h.hexdigest()[:12]


def so_hash():
    return hashlib.sha256((ENGINE_PATH / 'arclog/arclog.abi3.so').resolve().read_bytes()).hexdigest()


def golds(view, points, tasks):
    """Task -> gold's lines: the first row of each task in a corpus view, or the entries of a list of task and gold_sexp where no view is given."""
    if view is None:
        got = {x['task']: x['gold_sexp'] for x in json.load(open(points))}
        return {t: [x for x in got[t].splitlines() if x.strip()] for t in tasks}
    out = {}
    for t in tasks:
        with gzip.open('%s/%s/pairs.jsonl.gz' % (view, t), 'rt') as f:
            out[t] = [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]
    return out


def arms_of(lines, i, mode, seeds):
    """(FormDag, {arm: (scope lines, target text, scope order name)}) of the form at line i."""
    text = lines[i]
    dag = D.FormDag(text, mode)
    prog = D.ProgramDag(lines)
    key = 'OUT' if text.startswith('(OUT') else D.parse(text)[1]
    head = {('OUT' if x.startswith('(OUT') else D.parse(x)[1]): j for j, x in enumerate(lines)}
    written = lambda keys: [lines[j] for j in sorted(head[k] for k in keys)]  # noqa: E731
    sets = dict(parents=prog.ancestors(key), nondesc=prog.non_descendants(key))
    arms = {('before', 'written'): (lines[:i], text, 'written'),
            ('parents', 'written'): (written(sets['parents']), text, 'written'),
            ('nondesc', 'written'): (written(sets['nondesc']), text, 'written')}
    canonical = dag.render(dag.canonical_order())
    for scope, keys in sets.items():
        arms[scope, 'canonical'] = prog.texts(prog.canonical_order(keys)), canonical, 'canonical'
        for s in range(seeds):
            arms[scope, 'seed-%d' % s] = prog.texts(prog.random_order(s, keys)), dag.render(dag.random_order(s)), 'seed-%d' % s
    for s in range(seeds):
        arms['parents', 'body-seed-%d' % s] = written(sets['parents']), dag.render(dag.random_order(s)), 'written'
    return dag, arms


def priority(group):
    """Walks that a read of the relation pick needs come first, then the others, each in an order of forms that is fair across tasks."""
    t, i, kind, _, _, _, members = group
    parents = any(sc == 'parents' for (sc, _), _ in members)
    return (0 if kind == 'RULE' and parents else 1 if parents else 2), D.short('%s %d' % (t, i))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--view', default=None)
    ap.add_argument('--points', default=str(BASE / 'points-base.json'))
    ap.add_argument('--corpus', default=str(ROOT / 'work/lm/data-study/gold/gold-v3-helper-forms-a036da074/corpus-view'), help='SAMPLER_CORPUS where no view is given')
    ap.add_argument('--revision', default='gold-v3-helper-forms-a036da074-base')
    ap.add_argument('--out', default=str(HERE))
    ap.add_argument('--tasks', default=str(WORKER / 'held/tasks.txt'))
    ap.add_argument('--models', default=str(BASE / 'models-base'))
    ap.add_argument('--seeds', type=int, default=8)
    ap.add_argument('--mode', default='binder', choices=['binder', 'join'])
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--task', default=None, help='one task only')
    ap.add_argument('--seconds', type=float, default=None, help='start no walk past this budget')
    ap.add_argument('--kinds', default='RULE,DET,INIT')
    ap.add_argument('--commit', default='d1c0f40e661d91f62a3c6ecf872febb5c885edfb')
    ap.add_argument('--dry', action='store_true', help='count the walks, with no engine')
    ap.add_argument('--decode-only', action='store_true', help='ask the decoder for each walk\'s text, with no walk: decoder-check.jsonl')
    a = ap.parse_args()
    shard, shards = map(int, a.shard.split('/'))
    tail = '' if shards == 1 else '-shard%dof%d' % (shard, shards)
    tail = ('-join' if a.mode == 'join' else '') + tail
    if so_hash() != WHEEL_SO:
        sys.exit('arclog in %s is not the wheel %s' % (ENGINE_PATH, WHEEL_SO))
    code = code_hash()
    os.makedirs(a.out, exist_ok=True)
    manifest_path = Path(a.out) / 'manifest.json'
    if manifest_path.exists():
        want = json.load(open(manifest_path)).get('sampler_code', {}).get('hash')
        if want and want != code:
            sys.exit('the sampler code hash is %s and the manifest has %s: the main checkout moved, so these rows cannot go on from those' % (code, want))
    os.environ.update(STEER_COVER='init,branch', SAMPLER_CORPUS=(a.view or a.corpus).rstrip('/') + '/', SEARCH_MODELS=a.models, RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    sys.path[:0] = [str(ENGINE_PATH), str(SAMPLER_CODE)]
    import live  # noqa: E402  # pyright: ignore[reportMissingImports]
    import live_try  # noqa: E402  # pyright: ignore[reportMissingImports]
    import or_q  # noqa: E402  # pyright: ignore[reportMissingImports]
    import search  # noqa: E402  # pyright: ignore[reportMissingImports]
    import search_gold as G  # noqa: E402  # pyright: ignore[reportMissingImports]
    M = live.M
    CTX = {}

    class Instr(or_q.GuidedDrawer):
        """The drawer of or_q.py, with a record of each relation pick. The record reads the walk and changes nothing in it (as rel_read.py of the relation pick read)."""

        def atom(self, fr, k, scope_types=(), key=()):
            CTX['leaf'] = CTX['next']
            CTX['next'] += 1
            res = super().atom(fr, k, scope_types, key)
            if res[0] is not None:
                CTX['atom_leaf'].append(CTX['leaf'])
            return res

        def pick(self, opts, weights):
            f = sys._getframe(1)
            while f is not None and f.f_code.co_name != 'atom':
                f = f.f_back
            L = f.f_locals
            n = L['n']
            rec = self.snapshot(n, L, opts) if n.phase in ('root', 'root2') and self.force else None
            o, q = super().pick(opts, weights)
            if rec is not None:
                rec['bits'] = round(or_q.bits(q), 4)
                CTX['picks'].append(rec)
            return o, q

        def snapshot(self, n, L, opts):
            fr, V = self.fr, self.V
            k, key, scope = L['k'], L['key'], tuple(L['scope_types'])
            gold = self.force[0]
            jset = None
            if k > 1:
                jset = L.get('jset')
                if jset is None:
                    jset = self.joinable(n, opts, scope, key)
            kind = 'NOT' if gold == M.NOT else 'CMP' if gold in M.CMP else fr.KIND[gold]
            return dict(leaf=CTX['leaf'], phase=n.phase, ctx=self.rng.ctx, k=k, gold=V.name(gold), gold_kind=kind, own=gold in key and kind in REL_KINDS, n_options=len(opts),
                        alive=kind in ('NOT', 'CMP') or (gold in opts and (jset is None or gold in jset)))

    class Run(or_q.GuidedRun):
        drawer_class = Instr

    class Guide(or_q.Guide):
        def randrange(self, n):  # the else negation: an atom that the walk takes with no pick
            CTX['else'].append(CTX['next'])
            CTX['next'] += 1
            return super().randrange(n)

    or_q.GuidedRun, or_q.Guide = Run, Guide

    tasks = [t for t in open(a.tasks).read().split() if a.task in (None, t)]
    gold = golds(a.view, a.points, tasks)
    kinds = set(a.kinds.split(','))
    done = set()
    for p in glob.glob(os.path.join(a.out, 'census-dag%s*.jsonl' % ('-join' if a.mode == 'join' else ''))):
        if a.mode == 'binder' and '-join' in p:
            continue
        for line in open(p):
            r = json.loads(line)
            done.add((r['revision'], r['task'], r['line'], r['scope'], r['order']))

    todo, forms = [], 0
    t_plan = time.time()
    for t in tasks:
        lines = gold[t]
        for i, text in enumerate(lines):
            kind = text.split()[0].lstrip('(')
            if kind not in kinds or kind not in live.KIND_TOK:
                continue
            forms += 1
            if (forms - 1) % shards != shard:
                continue
            dag, arms = arms_of(lines, i, a.mode, a.seeds)
            dag.n_orders = dag.count_orders()
            groups = collections.defaultdict(list)
            for arm, (scope, target, scope_order) in arms.items():
                if (a.revision, t, i, *arm) not in done:
                    groups[tuple(scope), target].append((arm, scope_order))
            for (scope, target), members in groups.items():
                todo.append((t, i, kind, dag, scope, target, members))
    todo.sort(key=priority)
    print('%d forms over all shards, %d walks to do on shard %d/%d, %d rows done, planned in %.1f s, code %s' % (forms, len(todo), shard, shards, len(done), time.time() - t_plan, code), flush=True)
    print('walks by priority %s; sum of scope forms over walks %d' % (sorted(collections.Counter(priority(x)[0] for x in todo).items()), sum(len(x[4]) for x in todo)), flush=True)
    if a.dry:
        return
    if a.decode_only:
        path = os.path.join(a.out, 'decoder-check.jsonl')
        seen = {(r['task'], r['line'], r['target'], r['nscope'], r['scope_hash']) for r in map(json.loads, open(path))} if os.path.exists(path) else set()
        sessions, t0, n = {}, time.time(), 0
        with open(path, 'a') as f:
            for w, (t, i, kind, dag, scope, target, members) in enumerate(todo, 1):
                sh = D.short(''.join(scope))
                if (t, i, target, len(scope), sh) in seen:
                    continue
                if a.seconds and time.time() - t0 > a.seconds:
                    break
                if t not in sessions:
                    sessions.clear()
                    sessions[t] = live_try.session_of(t)[0]
                try:
                    or_q.gold_rest(sessions[t], list(scope), target, kind)
                    why = None
                except Exception as e:  # noqa: BLE001
                    why = '%s: %s' % (type(e).__name__, str(e)[:240])
                n += 1
                f.write(json.dumps(dict(task=t, line=i, kind=kind, nscope=len(scope), scope_hash=sh, target=target, gold_target=dag.text, ok=why is None, why=why, arms=[list(m[0]) for m in members])) + '\n')
                f.flush()
                if n % 100 == 0:
                    el = time.time() - t0
                    print('[%d/%d %ds %.1f texts/s eta %ds]' % (w, len(todo), el, n / el, el / n * (len(todo) - w)), flush=True)
        print('decoder check: %d texts in %.0f s' % (n, time.time() - t0), flush=True)
        return
    if not manifest_path.exists() and shard == 0:
        json.dump(dict(what='gold forms through or_q.walk with the body in topological orders of the atom DAG and the scope from the program DAG', command=' '.join(sys.argv), commit=a.commit,
                       task_set='37 held-out tasks of %s; forms RULE, DET, INIT' % a.tasks, gold_revision=a.revision, view=a.view or a.points, models=a.models, steer_cover='init,branch',
                       budget='teacher-forced walks, no search budget; %d random orders per form' % a.seeds,
                       measures=['surprisal of gold under the proposal distribution (or_q.py total) by order', 'bits per relation pick'],
                       started=time.strftime('%Y-%m-%dT%H:%M:%S%z'), sampler_code=dict(path=str(SAMPLER_CODE), hash=code, hash_of=list(CODE_FILES), edited=False),
                       wheel_engine=dict(commit='ba0754492', sha256='a3278497561b3fabbb5d90edb1f2c3845dbe54091d29d95f055fd299e64900d8', so_sha256=WHEEL_SO, machine='Mac')), open(manifest_path, 'w'), indent=1)
    t0 = time.time()
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    print('models loaded in %.1f s' % (time.time() - t0), flush=True)
    jsonl = open(os.path.join(a.out, 'census-dag%s.jsonl' % tail), 'a')
    tsv_path = os.path.join(a.out, 'per-pick-dag%s.tsv' % tail)
    fresh = not os.path.exists(tsv_path)
    tsv = open(tsv_path, 'a')
    if fresh:
        tsv.write('\t'.join(COLUMNS) + '\n')
    t0, walked, spent = time.time(), 0, 0.0
    last = None
    for w, (t, i, kind, dag, scope, target, members) in enumerate(todo, 1):
        if a.seconds and time.time() - t0 > a.seconds:
            print('budget of %.0f s spent' % a.seconds, flush=True)
            break
        if (t, i) != last:
            gc.collect()  # the last form's sessions and tables
            last = (t, i)
        t1 = time.time()
        CTX.update(next=0, leaf=None, atom_leaf=[], picks=[], **{'else': []})
        scope = list(scope)
        try:
            sess, task_json, _ = live_try.session_of(t)
            q = or_q.walk(sampler, t, kind, [len(scope), 0], scope, target, sess, task_json, kind)
        except Exception as e:  # noqa: BLE001
            q = dict(error='%s: %s' % (type(e).__name__, str(e)[:300]))
        sec = round(time.time() - t1, 2)
        spent += sec
        walked += 1
        order = D.FormDag(target, dag.mode).written_order()
        leaves = dag.leaves(order)
        ok = not (q.get('error') or q.get('bad') or q.get('dead') or q.get('left'))
        aligned = CTX['next'] == len(leaves)
        atom_ids = [leaves[k] for k in CTX['atom_leaf']] if aligned else None
        same = search.clause_key(target) == search.clause_key(dag.text)
        row = dict(q, revision=a.revision, line=i, kind=kind, gold_target=dag.text, target=target, mode=a.mode, n_orders=dag.n_orders, written_topological=dag.is_topological(dag.written_order()),
                   same_clause=same, atom_ids=[D.short(x) for x in atom_ids] if atom_ids is not None else None, atom_depths=[dag.depth(x) for x in atom_ids] if atom_ids is not None else None,
                   else_negations=[D.short(leaves[k]) for k in CTX['else']] if aligned else None, aligned=aligned, seconds=sec, code=code, nscope=len(scope), task=t)
        lines_out = []
        for (sc, name), scope_order in members:
            jsonl.write(json.dumps(dict(row, scope=sc, order=name, scope_order=scope_order, walk_of=list(members[0][0]))) + '\n')
            for n, p in enumerate(CTX['picks']):
                leaf = leaves[p['leaf']] if p['leaf'] < len(leaves) else None
                if leaf is None or not aligned:
                    pre = ['?']
                    cells = ('?', '', '?', '', '?')
                else:
                    a_ = dag.atoms[leaf]
                    pre = [x for x in leaves[:p['leaf']]]
                    cells = (D.short(leaf), dag.depth(leaf), a_.kind, a_.key, ','.join(D.short(x) for x in dag.frontier(pre)) or '-')
                lines_out.append('\t'.join(str(x) for x in (a.revision, t, i, kind, sc, name, n, p['phase'], p['ctx'], p['k'], cells[0], cells[1], cells[2], cells[3], p['gold'], p['gold_kind'], int(p['own']), int(p['alive']),
                                                            p['n_options'], len(pre), ','.join(D.short(x) for x in pre) or '-', cells[4], p['bits'], int(ok))) + '\n')
        tsv.write(''.join(lines_out))
        tsv.flush()
        jsonl.flush()
        el = time.time() - t0
        print('[%d/%d %ds %.2f walks/s eta %ds] %s:%d %s %s total %s %s %.1fs' % (w, len(todo), el, walked / el, el / walked * (len(todo) - w), t, i, kind, members[0][0], q.get('total'), (q.get('error') or (q.get('bad') or [''])[0] or q.get('dead') or '')[:120], sec), flush=True)
    print('done: %d walks in %.0f s' % (walked, time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
