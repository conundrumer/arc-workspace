#!/usr/bin/env python
"""Runs live.Sampler on tasks of data/tasks with their test outputs held out, as a Kaggle worker would, and prints each result
as it comes and a line per task: draws per second, peak RSS, counts. The test outputs score the attempts here, after draws.

  RAYON_NUM_THREADS=1 <runtime python> -u live_try.py TASK ... [--seconds 20] [--seed 0] [--models DIR] [--steers struct,tilt,rel,choice]

With --clause N, each task gets Sampler.clause in place of draws: N RULEs from an empty scope, then N clauses of each kind over a
scope of the first SCOPE of them, each checked by replaying its text, then N RULEs over that scope and one of those clauses. A line
gives ms per call, where calls after the first over a scope reuse its replay, and the ms of one replay.

With --one N, each task's gold clauses with their ONE marks removed are the scope, and the OUT search at their end runs with the ONE repair off and on (N seconds
a candidate). A line gives the candidates and the right ones of both runs, and the last line gives (right off, right on) per task.

With --choose N, each task's gold clauses with each CHOOSE replaced by the RULE that holds its candidates (plain_rule) are the scope, and the OUT search at their end runs
with the CHOOSE lift off and on (N seconds a candidate). A line gives the candidates and the right ones of both runs, and the last line gives (right off, right on) per task.
With CHOOSE_LIFT=N in the environment, --one runs both of its runs with the lift on, and its line gives a digest of the candidates, which the lift must leave as they were.

With --gold, every gold program of each task in the corpus is stepped on the same session in place of draws. A line gives whether
it ended, whether its attempts are right, the gate's rules that it breaks and its leave-one-out outcomes, and the last line counts
them.
"""
import argparse
import collections
import gzip
import hashlib
import json
import os
import re
import resource
import time

import live
import sampler_paths as P

SCOPE = 3  # the first clauses that make the scope of --clause
SETTINGS = dict(rule_tests=False, table_work_cap=1 << 21, static_pruning=True)  # the engine reads no clock, so no row depends on the machine's load


def session_of(task):
    """An open-world session of the task with no test output, the task with no test output, and the test outputs."""
    d = json.load(open('%s/data/tasks/%s.json' % (P.REPO, task)))
    outs = [t.pop('output', None) for t in d['test']]
    sess = live.arclog.Session(live.arclog.Task.from_json(json.dumps(d), live.arclog.World.Open), live.arclog.DecodeSettings(**SETTINGS), session_bytes=2 << 30)
    return sess, d, outs


def gold_lines(task, tally):
    """Yields a line per gold program of the task, stepped on its open-world session, and adds what it found to tally."""
    sess, d, outs = session_of(task)
    gate = live.Gate(d, sess.settings)
    path = live.S.CORPUS + task + '/pairs.jsonl.gz'
    if not os.path.exists(path):
        tally['tasks with no gold'] += 1
        return
    with gzip.open(path, 'rt') as f:
        sexps = [json.loads(x)['gold_sexp'] for x in f]
    for sexp in sexps:
        tally['programs'] += 1
        ids, model, _ = live.arclog.StudyProgram.from_sexp(sexp, sess.settings).decode_stream()
        dec = sess.decoder()
        try:
            for t, m in zip(ids, model):
                if m:
                    dec.step(t)
        except (live.arclog.Refusal, live.arclog.Fault) as e:
            tally['the decoder refused'] += 1
            yield '%s the decoder refused: %s' % (task, str(e)[:100])
            continue
        if not dec.ended:
            tally['not ended'] += 1
            yield '%s not ended' % task
            continue
        att = dec.attempts()
        broken = gate.refused(att)
        right = all(o in a for o, a in zip(outs, att))
        tally['ended right' if right else 'ended wrong'] += 1
        tally.update('refused:' + r for r in broken)
        loo = gate.leave_one_out(sexp)
        tally.update('loo fold:' + r for r in loo)
        tally['loo program:%s' % ('one pair' if not loo else 'all pass' if all(r == 'pass' for r in loo) else 'none pass' if 'pass' not in loo else 'some pass')] += 1
        yield '%s right=%s refused=%s loo=%s' % (task, right, broken, loo)


MARK = re.compile(r'\s*\(ONE(?: [^()]*)?\)')


def gold_sexp(task, points):
    """Gold's program for task: from the corpus, else from points, a JSON file of {task, gold_sexp}."""
    path = live.S.CORPUS + task + '/pairs.jsonl.gz'
    if os.path.exists(path):
        with gzip.open(path, 'rt') as f:
            return json.loads(f.readline())['gold_sexp']
    return next(r['gold_sexp'] for r in json.load(open(points)) if r['task'] == task)


def sexp(text):
    """The nested lists of an s-expression's text."""
    stack = [[]]
    for t in re.findall(r'\(|\)|[^\s()]+', text):
        if t == '(':
            stack.append([])
        elif t == ')':
            top = stack.pop()
            stack[-1].append(top)
        else:
            stack[-1].append(t)
    return stack[0][0]


def render(x):
    return x if isinstance(x, str) else '(%s)' % ' '.join(map(render, x))


def starred(x):
    """x, nested lists, with each (:Label Var) as (:Label *Var), and each bare label of a key record."""
    if isinstance(x, str):
        return x
    if len(x) == 2 and x[0].startswith(':') and isinstance(x[1], str) and re.match(r'[A-Z]\w*\Z', x[1]):
        return [x[0], '*' + x[1]]
    if x and x[0] == ':key':  # a key record: its bare labels are variables too
        return [x[0]] + [('*' + y if re.match(r'[A-Z]\w*\Z', y) else y) if isinstance(y, str) else starred(y) for y in x[1:]]
    return [starred(y) for y in x]


def plain_rule(form):
    """A CHOOSE form as the RULE that holds its candidates: the same head, and the atoms of its `from` with each label starred. Another form stays."""
    if not form.startswith('(CHOOSE'):
        return form
    _, head, *clauses = sexp(form)
    atoms = next(c[2][1:] for c in clauses if c[0] == 'for')
    return render(['RULE', head, *starred(atoms)])


def one_run(sampler, task, points, seconds, lift=None):
    """The candidates, (program, attempts, whether each test input has its output among them), of the OUT search at the end of task's gold clauses, and the Run's counts.
    With lift None the clauses have their ONE marks removed and seconds is the ONE repair's limit (0 is off); else each CHOOSE is a plain RULE, the ONE marks stay, and
    lift is the CHOOSE lift's limit (0 is off)."""
    sess, d, outs = session_of(task)
    lines = [x for x in gold_sexp(task, points).splitlines() if x.strip() and not x.startswith('(OUT')]
    forms = [MARK.sub('', x) for x in lines] if lift is None else [plain_rule(x) for x in lines]
    run = live.Run(sampler.pri, sess, 0, time.monotonic() + 120, d, live.Limits(one_repair=seconds, **({} if lift is None else {'choose_lift': lift})))
    dec, pg = run.scope(forms)
    t0 = time.monotonic()
    got = [(f.program_form(), f.attempts(), [o in a for o, a in zip(outs, f.attempts())]) for f in run.search(pg, dec)]
    return got, run.c, time.monotonic() - t0


def digest(cands):
    return hashlib.sha1(repr([(p, a) for p, a, _ in cands]).encode()).hexdigest()[:8]


def one_try(sampler, task, points, seconds):
    """--one on one task: the OUT search at the end of the gold clauses without ONE marks runs with the ONE repair off and on. With it on, the candidates
    of the repair-off run come first and unchanged, and none that was right is lost."""
    off, _, t_off = one_run(sampler, task, points, 0)
    on, c, t_on = one_run(sampler, task, points, seconds)
    assert on[:len(off)] == off or live.Limits().choose_lift, task  # with the lift on in both runs, its candidates follow the ONE repairs' in the second
    right = lambda cands: sum(all(r) for _, _, r in cands)  # noqa: E731
    print('%s candidates %d -> %d, right %d -> %d, search %.2f -> %.2f s, digest %s, %s' % (
        task, len(off), len(on), right(off), right(on), t_off, t_on, digest(on), {k: v for k, v in sorted(c.items()) if k.startswith(('one:', 'choose'))}), flush=True)
    return right(off), right(on)


def choose_try(sampler, task, points, seconds):
    """--choose on one task: the OUT search at the end of the gold clauses, each CHOOSE a plain RULE, runs with the CHOOSE lift off and on. With it on, the candidates
    of the lift-off run come first and unchanged."""
    off, _, t_off = one_run(sampler, task, points, 0, 0)
    on, c, t_on = one_run(sampler, task, points, 0, seconds)
    assert on[:len(off)] == off, task
    right = lambda cands: sum(all(r) for _, _, r in cands)  # noqa: E731
    print('%s candidates %d -> %d, right %d -> %d, search %.2f -> %.2f s, %s' % (
        task, len(off), len(on), right(off), right(on), t_off, t_on, {k: v for k, v in sorted(c.items()) if k.startswith('choose')}), flush=True)
    for p, a, r in on[len(off):]:
        print('  lift right=%s' % all(r), ' '.join(x[:400] for x in p.split('\n') if x.startswith('(CHOOSE')), flush=True)
    return right(off), right(on)


def clause_calls(sampler, sess, d, seeds, deadline, forms, kind):
    """The Clauses of a clause call per seed, and the line of those calls."""
    t0 = time.perf_counter()
    got = [sampler.clause(sess, s, deadline, d, forms, kind) for s in seeds]
    t1 = time.perf_counter()
    sampler.run.scoped = None
    sampler.run.scope(forms)
    print('  %s over %d forms: %d calls, %d clauses, %.1f ms a call; one replay of the scope %.1f ms' % (
        kind, len(forms), len(got), sum(c is not None for c in got), 1000 * (t1 - t0) / len(got), 1000 * (time.perf_counter() - t1)), flush=True)
    return [c for c in got if c]


def clause_try(sampler, task, n, seed, seconds):
    """--clause on one task."""
    sess, d, _ = session_of(task)
    deadline = time.monotonic() + seconds
    print(task, flush=True)
    empty = clause_calls(sampler, sess, d, range(seed, seed + n), deadline, [], 'RULE')
    forms = [c.text.replace('&r0', '&drawn%d' % i, 1) for i, c in enumerate(empty[:SCOPE])]  # from an empty scope each has one head
    for f in forms:
        print('  scope:', f[:150], flush=True)
    run = sampler.run
    for kind in live.DRAWN_KINDS:
        got = clause_calls(sampler, sess, d, range(seed + n, seed + 2 * n), deadline, forms, kind)
        for c in got:  # a Clause's text, with the scope's forms in another order, is the same program
            assert run.scope(forms + [c.text])[0].program_form() == c.decoder.program_form(), c.text
            run.scope(forms[::-1] + [c.text])
        if got:
            print('  drew:', got[-1].text[:300], flush=True)
            longer = forms + [got[-1].text]
            for c in clause_calls(sampler, sess, d, range(seed + 2 * n, seed + 3 * n), deadline, longer, 'RULE')[:2]:
                print('  over it:', c.text[:300], flush=True)
                assert run.scope(longer + [c.text])[0].program_form() == c.decoder.program_form(), c.text
    print('  counts %s' % {k: v for k, v in sorted(run.c.items()) if k.startswith(('drop', 'error'))}, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tasks', nargs='+')
    ap.add_argument('--seconds', type=float, default=20)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--models', default=P.SAMPLER_DATA + '/models')
    ap.add_argument('--steers', default=','.join(live.STEERS), help='the steers that are on, by name; empty: none')
    ap.add_argument('--gold', action='store_true', help='check the gate on gold in place of draws')
    ap.add_argument('--clause', type=int, default=0, help='N: try Sampler.clause in place of draws')
    ap.add_argument('--one', type=float, default=0, help='N: the ONE repair check, with a limit of N seconds a candidate, in place of draws; see one_try')
    ap.add_argument('--choose', type=float, default=0, help='N: the CHOOSE lift check, with a limit of N seconds a candidate, in place of draws; see choose_try')
    ap.add_argument('--points', help='with --one: a JSON file of {task, gold_sexp} that has the gold of tasks the corpus lacks')
    a = ap.parse_args()
    if a.gold:
        tally = collections.Counter()
        for task in a.tasks:
            for line in gold_lines(task, tally):
                print(line, flush=True)
        print(dict(tally), flush=True)
        return
    t0 = time.time()
    sampler = live.Sampler(a.models, tuple(filter(None, a.steers.split(','))))
    print('loaded %.2fs' % (time.time() - t0), flush=True)
    if a.one:
        print(dict(zip(a.tasks, (one_try(sampler, task, a.points, a.one) for task in a.tasks))), flush=True)
        return
    if a.choose:
        print(dict(zip(a.tasks, (choose_try(sampler, task, a.points, a.choose) for task in a.tasks))), flush=True)
        return
    for task in a.tasks if a.clause else ():
        clause_try(sampler, task, a.clause, a.seed, a.seconds)
    for task in () if a.clause else a.tasks:
        sess, d, outs = session_of(task)
        last, solved, shown = None, 0, False
        c0 = time.process_time()
        for r in sampler.draws(sess, a.seed, time.monotonic() + a.seconds, d):
            last = r
            if r.decoder is None:
                break
            right = all(o in att for o, att in zip(outs, r.attempts))
            solved += right
            if not shown or right:  # the first fit, and each that passes the test
                print('%s %.2fs consistent draws=%d test=%s\n%s' % (task, r.seconds, r.counts['draws'], right, r.program), flush=True)
                shown = True
        c = last.counts
        print('%s %.1fs draws=%d forms=%d (%.1f draws/s, %.2f CPU s a draw, search %.1f ms a form) consistent=%d test_right=%d peak_rss=%.0fMiB\n  %s' % (
            task, last.seconds, c['draws'], c.get('forms', 0), c['draws'] / max(last.seconds, 1e-9), (time.process_time() - c0) / max(c['draws'], 1),
            1000 * c.get('search_seconds', 0) / max(c.get('forms', 0), 1),
            c.get('consistent', 0), solved,
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20,
            {k: v for k, v in sorted(c.items(), key=lambda x: str(x[0])) if k not in ('draws', 'limits')}), flush=True)


if __name__ == '__main__':
    main()
