#!/usr/bin/env python
"""Teacher-forced walks of RULE forms that write one line per relation pick: the steer's row, the steered proposal's weights, and the content features of each option.

  <runtime python> -u features_rel_walk.py --forms FORMS.json --out OUT.jsonl.zst [--golds POINTS.json] [--priors-fold TEMPLATE] [--shard i/n] [--budget S] [--scope parents|before]

FORMS is a list of rows with the task at [4] and the form's line at [5]. --golds gives gold's programs; without it, the corpus's first gold program. The scope of a form is its ancestors by reads (parents) or every form before it (before).
With --priors-fold, a form walks under the priors of its task's fold. A shard writes one zstd frame per form, and a restart skips the forms it holds. Each form ends with a 'form' line. Prints a rate and an ETA.
Env: SEARCH_MODELS (the models directory), SAMPLER_CORPUS, STEER_COVER=init,branch, SAMPLER_CODE, and the runtime on PYTHONPATH.
"""
import argparse
import collections
import gzip
import io
import json
import os
import pickle
import sys
import time

import zstandard

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-per-relation-pool-scope-heldout37'  # the data folder
sys.path.insert(0, os.environ['SAMPLER_CODE'])
import live  # noqa: E402
import or_q  # noqa: E402
import sample2_col as S  # noqa: E402
import sampler_paths as P  # noqa: E402
import search_gold as G  # noqa: E402
import live_rows  # noqa: E402
sys.path.insert(0, HERE)
import features_rel_content as C  # noqa: E402

M = live.M
LIMIT = 6000  # a table of more rows than this over the train examples is read by its row counts alone
NAME_LIMIT = 1500  # no further column is named once the table has more rows than this: a further column can multiply the rows
CTX = {}
PEND = []
LIB = {}  # task -> {relation: Table or Sized or None}, which holds for all of a task's forms


def read(dr, fr, n0, o):
    """The option's table with every column it can name, at the clause's start. The last count of named columns that gives a table stands."""
    c = fr.child(n0, o)
    if c is None:
        return None
    best = None
    for _ in range(12):
        tb, _e = S.body_table(fr, *live.TABLES, c.dec, dr.pg.before)
        if tb is not None:
            best = tb
            if sum(len(rows) for _ex, _a, rows, *_ in tb['entries']) > NAME_LIMIT:
                break
        cols = [t for t in fr.admitted(c) if fr.KIND[t] == 'column' and fr.colpos[t] > c.last]
        if not cols:
            break
        v = fr.child(c, cols[0])
        s = None if v is None else fr.child(v, M.STAR)
        if s is None:
            break
        c = s
    return best


def load(tb):
    if tb is None:
        return None
    if sum(len(rows) for ex, _a, rows, *_ in tb['entries'] if ex[0] == 1) > LIMIT:
        return C.Sized(tb)
    return C.Table(S.full(tb))


def option_tables(dr, fr, opts):
    n0 = S.FNode((), CTX['dec0'], 'root', -1, 0, '', False, 0, None)
    lib = LIB.setdefault(CTX['task'], {})
    tabs, der = {}, {}
    for o in opts:
        if o in M.CMP or o == M.NOT:
            continue
        kd = fr.KIND[o]
        name = dr.V.name(o)
        try:
            if kd == 'relation':
                der[name] = tabs[name] = load(read(dr, fr, n0, o))
            else:
                if name not in lib:
                    lib[name] = load(read(dr, fr, n0, o))
                tabs[name] = lib[name]
        except Exception as e:  # noqa: BLE001
            tabs[name] = None
            CTX['errs'][type(e).__name__] += 1
    rows = {}
    for name, t in tabs.items():
        f = C.table_row(t, CTX['grids'])
        f.update(C.scope_row(t, der, name if name in der else None))
        rows[name] = [round(f[k], 4) for k in C.OPTION]
    return tabs, rows


class Instr(or_q.GuidedDrawer):
    def pick(self, opts, weights):
        f = sys._getframe(1)
        while f is not None and f.f_code.co_name != 'atom':
            f = f.f_back
        L = f.f_locals
        n = L['n']
        rec = None
        if n.phase in ('root', 'root2') and self.force:
            if n.phase == 'root':
                CTX['ord'] = CTX.get('ord', 0) + 1
            t0 = time.process_time()
            rec = self.snapshot(n, L, opts, weights)
            CTX['content_cpu'] += time.process_time() - t0
        o, q = super().pick(opts, weights)
        if rec is not None:
            rec['q_bits'] = round(or_q.bits(q), 4)
            PEND.append(rec)
        return o, q

    def snapshot(self, n, L, opts, weights):
        fr, V = self.fr, self.V
        k, key, scope = L['k'], L['key'], tuple(L['scope_types'])
        gold = self.force[0]
        if CTX['ord'] == 1 and n.phase == 'root':
            CTX['tabs'], CTX['optrows'] = option_tables(self, fr, opts)
        if n.phase == 'root':
            pre = None
            if k > 1:
                tb, _e = S.body_table(fr, *live.TABLES, n.dec, self.pg.before)
                pre = load(tb)
            CTX['pre'] = pre
        pre = CTX.get('pre')
        jset = None
        if k > 1:
            jset = L.get('jset')
            if jset is None:
                jset = self.joinable(n, opts, scope, key)
        gk = fr.KIND[gold] if gold not in M.CMP and gold != M.NOT else ('NOT' if gold == M.NOT else 'CMP')
        own = gold in key and gk in ('lib relation', 'relation macro', 'fact relation', 'relation')
        optl, cont, nop = [], [], [0.0] * (len(C.OPTION) + len(C.JOIN))
        for o, w in zip(opts, weights):
            kd = fr.KIND[o] if o not in M.CMP and o != M.NOT else ('NOT' if o == M.NOT else 'CMP')
            isrel = kd not in ('NOT', 'CMP')
            name = V.name(o)
            dj = bool(isrel and jset is not None and o not in jset)
            optl.append([name, kd, w, dj, o in key])
            if not isrel:
                cont.append(nop)
                continue
            base = CTX['optrows'].get(name)
            if base is None:  # a relation that the first pick did not offer
                t = None
                base = [0.0] * len(C.OPTION)
            else:
                t = CTX['tabs'].get(name)
            j = C.join_row(t, pre)
            cont.append(base + [round(j[x], 4) for x in C.JOIN])
        p = C.prefix_row(pre, CTX['grids'])
        return dict(rec='rel', task=CTX['task'], line=CTX['line'], orf=CTX['orf'], ord=CTX['ord'], phase=n.phase, k=k, ctx=self.rng.ctx, nscope=len(scope), scope=list(scope),
                    gold=V.name(gold), gold_kind=gk, own=own, gold_idx=opts.index(gold) if gold in opts else None, opts=optl, cont=cont, pre=[round(p[x], 4) for x in C.PREFIX])


Orig = or_q.GuidedRun


class RunX(Orig):
    drawer_class = Instr

    def drawer(self, pg, kind, dec, place=None, prior=None):
        dr = super().drawer(pg, kind, dec, place, prior)
        dr.pg = pg
        if kind == 'RULE' and 'dec0' not in CTX:
            CTX['dec0'] = dec
        return dr


or_q.GuidedRun = RunX


def gold_lines(task, golds):
    if golds is not None:
        return [x for x in golds[task].splitlines() if x.strip()]
    with gzip.open(S.CORPUS + task + '/pairs.jsonl.gz', 'rt') as f:
        return [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]


def done_forms(path):
    got = set()
    if os.path.exists(path):
        try:
            with open(path, 'rb') as f:
                for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
                    if line.startswith('{"rec": "form"'):
                        d = json.loads(line)
                        got.add((d['task'], d['line']))
        except zstandard.ZstdError:
            pass
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--forms', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--golds', default='')
    ap.add_argument('--priors-fold', default='')
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--budget', type=float, default=1e9)
    ap.add_argument('--scope', default='parents', choices=('parents', 'before'))
    a = ap.parse_args()
    forms = json.load(open(a.forms))
    i, n = map(int, a.shard.split('/'))
    tasks = sorted({r[4] for r in forms})
    keep = {t for j, t in enumerate(tasks) if j % n == i}
    forms = [r for r in forms if r[4] in keep]
    done = done_forms(a.out)
    todo = [r for r in forms if (r[4], r[5]) not in done]
    print('%d forms in the shard, %d done, %d to do' % (len(forms), len(done), len(todo)), flush=True)
    golds = {x['task']: x['gold_sexp'] for x in json.load(open(a.golds))} if a.golds else None
    sampler = live.Sampler(G.MODELS, tuple(live.STEERS))
    pri = {}
    t0 = time.time()
    cz = zstandard.ZstdCompressor(level=6)
    with open(a.out, 'ab') as out:
        for c, row in enumerate(todo, 1):
            task, line = row[4], row[5]
            if time.time() - t0 > a.budget:
                break
            if a.priors_fold:
                fold = live_rows.fold_of(task, live_rows.FOLDS)
                if fold not in pri:
                    with open(a.priors_fold.format(fold), 'rb') as f:
                        pri[fold] = pickle.load(f)
                sampler.pri = pri[fold]
            lines = gold_lines(task, golds)
            target = lines[line]
            keep_lines = live_rows.parents(lines, line) if a.scope == 'parents' else list(range(line))
            if task not in LIB:
                LIB.clear()
            G.gold_of = lambda t, c_, p, ls=[lines[j] for j in keep_lines] + [target]: (t, ls)
            CTX.clear()
            PEND.clear()
            CTX.update(task=task, line=line, orf='(OR ' in target, content_cpu=0.0, errs=collections.Counter(), grids=C.grids_of(json.load(open('%s/data/tasks/%s.json' % (P.REPO, task)))))
            t1 = time.process_time()
            rows = []
            try:
                q = or_q.one(sampler, task, 'RULE', [len(keep_lines), 0], 'RULE', rows)
            except Exception as e:  # noqa: BLE001
                q = dict(error=repr(e)[:200])
            rel = [r for k, r in rows if k == 'rel']
            aligned = len(rel) == len(PEND) and all(r['k'] == p['k'] and r['phase'] == p['phase'] and len(r['options']) == len(p['opts']) for r, p in zip(rel, PEND))
            buf = []
            for j, p in enumerate(PEND):
                if aligned:
                    r = rel[j]
                    p['prefix'] = r['prefix']
                    p['where'], p['place'] = r['where'], r['place']
                    p['prefix_bases'], p['prefix_depth'] = r.get('prefix_bases'), r.get('prefix_depth')
                    p['rowopts'] = [dict(tok=o['tok'], kind=o['kind'], p=o['p'], types=o.get('types'), cols=o.get('columns'), dag=o.get('dag')) for o in r['options']]
                buf.append(json.dumps(p))
            cpu = time.process_time() - t1
            buf.append(json.dumps(dict(rec='form', task=task, line=line, orf=CTX['orf'], natoms=len(q.get('atoms', [])), total=q.get('total'), parts=q.get('parts'), bad=q.get('bad'), dead=q.get('dead'),
                                       error=q.get('error'), cpu=round(cpu, 3), content_cpu=round(CTX['content_cpu'], 3), picks=len(PEND), aligned=aligned, errs=dict(CTX['errs']))))
            out.write(cz.compress(('\n'.join(buf) + '\n').encode()))
            out.flush()
            if cpu > 5:
                print('slow form', task, line, round(cpu, 1), flush=True)
            if c % 10 == 0 or c == len(todo):
                el = time.time() - t0
                print('[%d/%d %.0fs %.2f forms/s eta %.0fs] %s %s' % (c, len(todo), el, c / el, el / c * (len(todo) - c), task, line), flush=True)
    print('done', flush=True)


if __name__ == '__main__':
    main()
