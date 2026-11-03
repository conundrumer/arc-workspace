"""The slot partition (lookahead_legal.ReadsScopeFirst) against the gold queries of a split, with no search. Streams one line per task to OUT.jsonl; a restart skips the tasks it has.

    SAMPLER_CODE=<kit>/model/study/sampler PYTHONPATH=<site>:<kit>/model/study/sampler <runtime python> partition_check.py OUT.jsonl [--split dev] [--tasks T,...]
    partition_check.py --summary OUT.jsonl

For each gold RULE or DET of the split's skeleton whose body reads a query of its scope: its canonical stream (order.canonical_stream, the
stream of the `ordered` plan's targets) is stepped through the writer from its scope. At the point of the body's first atom, the check
counts whether the stream's token is one that ReadsScopeFirst bars (the first atom reads no query of the scope), and, where it is, whether
the legal plan's options there (writer.options with the `legal` lookahead) hold a token that ReadsScopeFirst keeps, so that the writer can
start the body with an atom that reads the scope. Each barred query also gives the relation its stream starts with.
"""
import argparse
import collections
import gc
import json
import os
import re
import sys
import time

DATA = '/Users/davidlu/code/arc-workspace/work/lm/data-study/samples/%s/skeleton'


def queries(split, task):
    """[(scope, kind, text)] of the task's gold RULEs and DETs that read a query of their scope, each once."""
    out, seen = [], set()
    for l in open('%s/%s.jsonl' % (DATA % split, task)):
        r = json.loads(l)
        if r.get('record') != 'query' or r['kind'] not in ('RULE', 'DET'):
            continue
        scope, text = tuple(r['program'][:-1]), r['program'][-1]
        names = {m for s in scope for m in re.findall(r'^\(\w+ (&r\d+)', s)}
        body = text.split(' ', 2)[2] if text.count(' ') >= 2 else ''
        if set(re.findall(r'&r\d+', body)) & names and (scope, text) not in seen:
            seen.add((scope, text))
            out.append((scope, r['kind'], text))
    return out


def check_task(run, env, sess, split, task):
    import live
    import lookahead_legal as LL
    import order
    import writer
    from live import arclog
    c, starts = collections.Counter(), collections.Counter()
    rule = LL.ReadsScopeFirst()
    plan = writer.default_plan(run, None, ('legal',))
    for scope, kind, text in queries(split, task):
        c['queries'] += 1
        try:
            ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*scope, text, live.READER_OUT)), sess.settings).decode_stream()
            stream = [int(t) for t, m, q in zip(ids, model, paths) if m and q[0] == len(scope)]
            dec, pg = run.scope(scope)
            s2, how, why = order.canonical_stream(env, dec, kind, stream)
            c['order ' + how + (' ' + why.split(':')[0] if why else '')] += 1
            pg.new = []
            pt = writer.start_point(run, pg, run.open_form(pg, dec, kind), kind)
            if not getattr(pt.pg, 'written', None):
                c['scope has no written names'] += 1
                continue
            for t in s2:
                if pt.track.where == 'done' or t not in pt.ids_:
                    c['stream left the mask before the first atom'] += 1
                    break
                f = rule.factors(pt, [t])
                if f[0] == -float('inf'):
                    c['barred: first atom reads no scope query'] += 1
                    starts[run.V.name(t)] += 1
                    opts, fac, reason = writer.options(pt, plan)
                    keep = rule.factors(pt, list(opts)) if opts is not None and len(opts) else []
                    c['barred, and the legal options hold a scope-reading first atom' if len(keep) and (keep == 0).any() else 'barred, and no scope-reading first atom is an option'] += 1
                    break
                if pt.track.firsts:
                    c['first atom reads a scope query'] += 1
                    break
                pt = writer.step_point(pt, t)
            else:
                c['stream ended before its first atom'] += 1
        except Exception as e:  # noqa: BLE001
            c['error %s: %s' % (type(e).__name__, str(e)[:60])] += 1
    return c, starts


def summary(path):
    c, starts = collections.Counter(), collections.Counter()
    n = 0
    for l in open(path):
        r = json.loads(l)
        n += 1
        c.update(r['counts'])
        starts.update(r['starts'])
    print('%d tasks' % n)
    for k, v in sorted(c.items()):
        print('  %-70s %6d' % (k, v))
    print('  first relations of the barred streams:', starts.most_common(12))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--split', default='dev')
    ap.add_argument('--tasks', default='')
    ap.add_argument('--summary', action='store_true')
    a = ap.parse_args()
    if a.summary:
        return summary(a.out)
    import live
    import live_try
    import train_rows as tr
    live_try.P.REPO = os.environ.get('ARC_ROOT', '/Users/davidlu/code/arc-workspace')
    tasks = a.tasks.split(',') if a.tasks else sorted(f[:-6] for f in os.listdir(DATA % a.split))
    done = set()
    if os.path.exists(a.out):
        done = {json.loads(l)['task'] for l in open(a.out)}
    smp = live.Sampler(os.environ['SAMPLER_CODE'] + '/../../../models-current', steers=())
    t0, n = time.time(), 0
    with open(a.out, 'a') as f:
        for task in tasks:
            if task in done:
                continue
            sess, d, _ = live_try.session_of(task)
            run = live.Run(smp.pri, sess, 0, time.monotonic() + 3600, d, live.Limits())
            env = tr.order_env(run)
            c, starts = check_task(run, env, sess, a.split, task)
            f.write(json.dumps(dict(task=task, counts=c, starts=starts)) + '\n')
            f.flush()
            n += 1
            left = len(tasks) - len(done) - n
            print('%s %s | %d done, ETA %.0f min' % (task, dict(c), n, left * (time.time() - t0) / n / 60), flush=True)
            del sess, run, env
            gc.collect()


if __name__ == '__main__':
    sys.exit(main())
