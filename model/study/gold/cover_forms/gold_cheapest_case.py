"""The case choice step of revision gold-v3-cheapest-round50: each stem with more than one case in the gen-v3 store takes its cheapest case that holds. Cheapest: the lower worst form in the all-earlier-forms context, then the lower sum.

  <runtime python> gold_cheapest_case.py run [CASE-COUNTS.json]    reads the stems with no row in round-out/case-choice.jsonl
  <runtime python> gold_cheapest_case.py child STEM...

A stem can have thousands of cases, and a full census of each is past reach on one process, so a stem reads in two steps:
- Estimate. Each form that is not in every case is read once, in the context of the first case that holds it. A form that is a crossing clause with a census row counts at the row's `worst`, since it is cut. A case's estimate is its worst such form, raised to the worst form of the base outside those forms, then the sum of those forms. A form with no bits marks its case undrawable.
- Exact. Up to TOP cases that the estimate puts lowest, at a worst no higher than the base's plus WORST_MARGIN and a sum under the base's plus MARGIN where the worst ties, are read in full. Cuts and swaps go on through gold_cover_one.py, with the stem's crossing clauses and cover candidates moved by masked text. A case past 5 min stops there, with no retry.

The base is the stem's text before this step: its view text, or its taken hand rewrite. A case is taken where every form of its finished program is drawable, it ranks below the base, it ends Consistent on train, its normal form is a fixed point, and its attempts equal the base's on each test input. The lowest such case is taken. A stem stays on its base where none is.

A row has stem, cases (the count), distinct (programs after dedupe), varied (forms not in every case), base (the base's figures), sums (each case read exactly with raw and finished figures, then the lowest estimates), taken (a case or null), why, and program, cuts, swapped and crossing of the taken case.
"""
import collections, json, os, selectors, signal, subprocess, sys, time
import numpy as np
from gold_cheapest_common import *

OUT = HERE + 'round-out/case-choice.jsonl'
TOP, MARGIN, WORST_MARGIN = 3, 5.0, 2.0
PER_CHILD = 40
GIB = 8


class Past(Exception):
    pass


def base_of(t, hand):
    """The stem's text before this step, and its case."""
    if t in hand:
        return hand[t]['program'], hand[t]['case'] or hand[t]['view_case']
    r = view_row(t)
    if r:
        return r['gold_sexp'], r['case']
    p = {x['task']: x for x in json.load(open(HERE + 'points-eval.json'))}
    return p[t]['gold_sexp'], json.load(open(HERE + 'current-text.json'))[t]['case']


def hand_taken():
    p = HERE + 'round-out/hand-rewrites.jsonl'
    return {r['stem']: r for r in map(json.loads, open(p)) if r['taken']} if os.path.exists(p) else {}


def cases_of(bar, t):
    """[(case, concept, lines)] of the store, one per distinct program; the count before dedupe."""
    streams, _ = arclog.corpus_streams(GEN + 'corpus/gen', all_cases=True, task_ids=[t])
    sess = bar.session()
    seen, out = {}, []
    for s in streams:
        ids = np.frombuffer(s.ids, np.uint32).tolist()
        model = [int(m) for m in np.frombuffer(s.model, np.uint8).astype(bool).tolist()]
        text = arclog.StudyProgram.from_stream(sess, ids, model).sexp()
        if text not in seen:
            seen[text] = len(out)
            out.append((s.case, bool(s.concept), program_lines(text)))
        elif s.concept:
            out[seen[text]] = (out[seen[text]][0], True, out[seen[text]][2])
    return out, len(streams)


def one(t, bits, hand):
    print('stem', t, flush=True)
    tick = lambda: print('tick', flush=True)
    bar = Bar(t)
    base_text, base_case = base_of(t, hand)
    base_lines = program_lines(base_text)
    cases, count = cases_of(bar, t)
    row = dict(stem=t, cases=count, distinct=len(cases), base_case=base_case, concept=next((c for c, k, _ in cases if k), None), hand=t in hand)
    if len(cases) < 2:
        return dict(row, sums=[], taken=None, why='one program in the store')
    at = next((i for i, (c, _, _) in enumerate(cases) if c == base_case), None)
    if at is None:
        at = next(i for i, (_, k, _) in enumerate(cases) if k)
        row['base_case_not_in_store'] = True
    forms = [collections.Counter(map(masked, ls)) for _, _, ls in cases]
    shared = set(forms[0])
    for c in forms[1:]:
        shared &= set(c)
    cut = {masked(c['clause']): c['worst'] for c in crossing_read(t) if 'worst' in c}
    est = {}
    for i in [at] + [k for k in range(len(cases)) if k != at]:
        ls = cases[i][2]
        for k, x in enumerate(ls):
            m = masked(x)
            if m not in shared and m not in est and not x.startswith('(OUT'):
                tick()
                est[m] = bits.read(t, ls[:k + 1])['bits']
    row['varied'] = len(est)
    base = bits.whole(t, base_lines, tick)
    row['base'] = base
    floor = 0.0  # the worst form of the base outside the forms that vary
    for k, x in enumerate(base_lines):
        if masked(x) not in est and not x.startswith('(OUT'):
            floor = max(floor, bits.read(t, base_lines[:k + 1])['bits'] or 0.0)
    estimate = []
    for c in forms:
        got = [(est[m], cut.get(m, est[m])) for m in c if m in est for _ in range(c[m])]
        drawn = [g for g in got if g[0] is not None]
        estimate.append((len(drawn) < len(got), round(max([floor] + [g[1] for g in drawn]), 2), round(sum(g[0] for g in drawn), 2)))
    order = sorted(range(len(cases)), key=lambda i: estimate[i])
    b0 = estimate[at]
    near = lambda e: base['undrawable'] or e[1] < base['worst'] or (e[1] <= base['worst'] + WORST_MARGIN and e[2] < b0[2] + MARGIN)
    close = [i for i in order if i != at and not estimate[i][0] and near(estimate[i])][:TOP]
    show = lambda sums: sums + [dict(case=cases[i][0], est_worst=estimate[i][1], est_sum=estimate[i][2], est_undrawable=estimate[i][0]) for i in order[:20]]
    if not close:
        return dict(row, sums=show([]), taken=None, why='the estimate puts no case near the base: worst %.2f, sum of varied forms %.2f' % (base['worst'], b0[2]))
    ended, att = bar.direct(base_text)
    row['base_ended'] = ended
    sums, good = [], []
    for i in close:
        s = dict(case=cases[i][0])
        sums.append(s)
        t0 = time.time()

        def watch_case():
            tick()
            if time.time() - t0 > CAP:
                raise Past()

        try:
            s['raw'] = bits.whole(t, cases[i][2], watch_case)
        except Past:
            s['past_cap'] = True
            continue
        got = finish(t, cases[i][2], seconds=CAP - 20)
        tick()
        s.update(cuts=got.get('cuts'), swapped=got.get('swapped'), crossing=got['crossing'], error=got.get('error'), failed=got.get('failed'))
        for text in dict.fromkeys(x for x in (got.get('program'), '\n'.join(cases[i][2])) if x):
            norm, fixed = bar.normal(text)
            e2, a2 = bar.direct(norm)
            fin = bits.whole(t, program_lines(norm), tick)
            s.update(finished=fin, ended=e2, fixed_point=fixed, attempts_equal=a2 == att)
            if e2 and fixed and a2 == att and not fin['undrawable']:
                if text != got.get('program'):
                    s.update(cuts=[], swapped=[], fallback=True)
                s['program'] = norm
                break
    for s in sums:
        if 'program' in s and rank(s['finished']) < rank(base):
            good.append(s)
    why = '; '.join('%s: %s' % (s['case'], ('finished worst %.2f sum %.2f undrawable %d, ended %s, fixed %s, attempts %s' % (s['finished']['worst'], s['finished']['sum'], len(s['finished']['undrawable']), s['ended'], s['fixed_point'], s['attempts_equal'])) if 'finished' in s else 'past the cap') for s in sums)
    if not good:
        for s in sums:
            s.pop('program', None)
        return dict(row, sums=show(sums), taken=None, why='none holds below the base: ' + why)
    best = min(good, key=lambda s: rank(s['finished']))
    for s in sums:
        if s is not best:
            s.pop('program', None)
    prog = best.pop('program')
    return dict(row, sums=show(sums), taken=best['case'], why=why, program=prog, cuts=best['cuts'], swapped=best['swapped'], crossing=best['crossing'], finished=best['finished'])


def child(stems):
    bits, hand = Bits(), hand_taken()
    for t in stems:
        print(json.dumps(one(t, bits, hand)), flush=True)


def run():
    done = {json.loads(l)['stem'] for l in open(OUT)} if os.path.exists(OUT) else set()
    text = json.load(open(HERE + 'current-text.json'))
    stems = set(os.listdir(HERE + 'corpus-view')) | {t for t in text if t in HELD or t in EVAL}
    counts = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else {}
    order = [t for t in HELD] + [t for t in EVAL if t not in HELD]
    order += sorted((t for t in stems if t not in order), key=lambda t: (len(counts.get(t, ())), t))
    left = [t for t in order if t not in done and (not counts or len(counts.get(t, 'xx')) > 1)]
    with open(OUT, 'a') as out:
        while left:
            part, left = left[:PER_CHILD], left[PER_CHILD:]
            while part:
                part = watch(part, out)
                out.flush()


def watch(part, out, script=__file__):
    """One child of script over part, under the caps. A stem whose read passes a cap has a row and keeps its text. Returns the stems not reached."""
    p = subprocess.Popen([sys.executable, os.path.abspath(script), 'child', *part], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, start_new_session=True, cwd=HERE)
    sel = selectors.DefaultSelector()
    sel.register(p.stdout, selectors.EVENT_READ, 'out')
    sel.register(p.stderr, selectors.EVENT_READ, 'err')
    now_t, last, err, seen, streams, checked = None, time.time(), [], set(), 2, 0

    def aside(why):
        out.write(json.dumps(dict(stem=now_t, set_aside=why, sums=[], taken=None, why=why)) + '\n')
        print(now_t, why, flush=True)
        seen.add(now_t)

    while streams:
        for k, _ in sel.select(5):
            l = k.fileobj.readline()
            if not l:
                sel.unregister(k.fileobj)
                streams -= 1
            elif k.data == 'err':
                err = (err + [l.rstrip()])[-6:]
            elif l.startswith('stem '):
                now_t, last = l.split()[1], time.time()
            elif l.startswith('tick'):
                last = time.time()
            elif l.startswith('{'):
                r = json.loads(l)
                out.write(l)
                seen.add(r['stem'])
                print(r['stem'], r.get('cases'), r.get('distinct'), r.get('varied'), r['taken'], str(r.get('why'))[:120], flush=True)
                now_t = None
        t = time.time()
        if now_t and t - last > CAP:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            aside('a read past %d s' % CAP)
            return [x for x in part if x not in seen]
        if t - checked > 5:
            checked = t
            if rss_gib(p.pid) > GIB:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
                if now_t:
                    aside('past %d GiB' % GIB)
                return [x for x in part if x not in seen]
    code = p.wait()
    if code != 0:
        if now_t is None:
            sys.exit('child failed outside a stem: %s %s' % (code, err))
        aside('process died: exit %s: %s' % (code, ' | '.join(err)[-300:]))
    return [x for x in part if x not in seen]


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'child':
        child(sys.argv[2:])
    elif cmd == 'run':
        run()
