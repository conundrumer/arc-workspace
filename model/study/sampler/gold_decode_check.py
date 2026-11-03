#!/usr/bin/env python
"""Decodes whole gold programs through a session's decoder and writes one line per program: accepted, or the refusal.

    gold_decode_check.py ramp   OUT.jsonl [--tasks T,T...] [--shard i/n] [--limit N]    # each program of each task of the ramp (prep.jsonl)
    gold_decode_check.py train  OUT.jsonl [--tasks T,T...] [--shard i/n] [--limit N]    # training: each program of a query record of each task, less those that
                                                                                         # are the start of another program of the task (order_count.py's queries)

Run it with the runtime python of the engine to check (its `arclog` module), and compare two OUT files by (set, task, pid).

A task runs in a process of its own (this script, run again with the mode `one`), so a session and its memory are freed with the process. The lines are
appended and flushed as the programs finish, and a program with a line in OUT is skipped on a restart: run the same command again. --shard i/n takes the
tasks at places i, i+n, ... of the task list, so n commands with different i, on the same OUT or on different ones, split the work.

A line: set, task, pid (a hash of the program's text), case (ramp only), forms (the number of the program's forms), status, seconds, and for a status other
than accepted: phase, form, error (the type of the exception) and refusal (its first line).
    accepted    the reader took the program's text, with its checks, and every token the model writes in the forms of the program was stepped through the
                decoder; the closing OUT of the reader is not stepped
    refused     phase read: the reader refused the text or a check of the program (the type check among them), and form is null; the path is in the refusal.
                phase decode: the decoder refused or faulted at a token of the form with the index form
    process_failed  (pid "process") the process of the task ended with an exit code, and the programs after the last line of the task have no line
"""
import argparse
import gc
import hashlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PREP = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b9773fdd-d09f-4bd5-b2d0-ebeaa83d8c6d/scratchpad/canon-count/prep.jsonl'
TRAIN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/samples/training/skeleton'


def pid_of(lines):
    return hashlib.sha1('\n'.join(lines).encode()).hexdigest()[:16]


def ramp_programs(task):
    """[(case, lines)] of the task's programs in prep.jsonl, each distinct text once."""
    seen, out = set(), []
    for r in (json.loads(l) for l in open(PREP)):
        if r['task'] != task:
            continue
        for p in r['programs']:
            key = pid_of(p['lines'])
            if key not in seen:
                seen.add(key)
                out.append((p.get('case'), list(p['lines'])))
    return out


def train_programs(task):
    """[(None, lines)]: the program of each query record of the task, once, less each that is the start of another."""
    progs = set()
    for l in open('%s/%s.jsonl' % (TRAIN, task)):
        r = json.loads(l)
        if r['record'] == 'query':
            progs.add(tuple(r['program']))
    longest = [p for p in progs if not any(len(q) > len(p) and q[:len(p)] == p for q in progs)]
    return [(None, list(p)) for p in sorted(longest)]


PROGRAMS = dict(ramp=ramp_programs, train=train_programs)


def tasks_of(mode, wanted):
    if wanted:
        return wanted.split(',')
    if mode == 'ramp':
        return [json.loads(l)['task'] for l in open(PREP)]
    return sorted(f[:-6] for f in os.listdir(TRAIN))


def done_of(out):
    """{(set, task, pid)} written in out."""
    done = set()
    if os.path.exists(out):
        for l in open(out):
            try:
                r = json.loads(l)
                done.add((r['set'], r['task'], r['pid']))
            except (ValueError, KeyError):
                pass
    return done


def decode(live, sess, lines):
    """(status, phase, form, error, refusal) of the program's text: read by the reader, which runs the checks, then stepped through a decoder of the session."""
    try:
        ids, model, paths = live.arclog.StudyProgram.from_sexp('\n'.join((*lines, live.READER_OUT)), sess.settings).decode_stream()
    except Exception as e:  # noqa: BLE001
        return 'refused', 'read', None, type(e).__name__, str(e).split('\n')[0][:300]
    dec = sess.decoder()
    form = None
    try:
        for t, m, p in zip(ids, model, paths):
            if m and p[0] < len(lines):
                form = int(p[0])
                dec.step(t)
    except BaseException as e:  # noqa: BLE001  (a panic of the engine is a BaseException)
        if isinstance(e, (KeyboardInterrupt, SystemExit)):
            raise
        return 'refused', 'decode', form, type(e).__name__, str(e).split('\n')[0][:300]
    return 'accepted', None, None, None, None


def one(mode, out, task, limit):
    os.environ.setdefault('RAYON_NUM_THREADS', '1')
    import live
    import live_try
    live_try.P.REPO = os.environ.get('ARC_ROOT', '/Users/davidlu/code/arc-workspace')
    done = done_of(out)
    todo = [(case, lines) for case, lines in PROGRAMS[mode](task) if (mode, task, pid_of(lines)) not in done]
    if limit:
        todo = todo[:limit]
    if not todo:
        return
    sess, _, _ = live_try.session_of(task)
    with open(out, 'a') as fo:
        for case, lines in todo:
            t0 = time.time()
            status, phase, form, error, refusal = decode(live, sess, lines)
            row = dict(set=mode, task=task, pid=pid_of(lines), forms=len(lines), status=status, seconds=round(time.time() - t0, 2))
            if case is not None:
                row['case'] = case
            if status != 'accepted':
                row.update(phase=phase, form=form, error=error, refusal=refusal)
            fo.write(json.dumps(row) + '\n')
            fo.flush()
    del sess
    gc.collect()


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=('ramp', 'train', 'one'))
    ap.add_argument('out')
    ap.add_argument('task_or_mode', nargs='?', help='with the mode one: the set (ramp or train), then the task')
    ap.add_argument('task', nargs='?')
    ap.add_argument('--tasks', default='')
    ap.add_argument('--shard', default='0/1', help='i/n: the tasks at places i, i+n, ... of the task list')
    ap.add_argument('--limit', type=int, default=0, help='the most programs per task (0: all)')
    a = ap.parse_args(argv)
    if a.mode == 'one':
        one(a.task_or_mode, a.out, a.task, a.limit)
        return
    i, n = map(int, a.shard.split('/'))
    for task in tasks_of(a.mode, a.tasks)[i::n]:
        done = done_of(a.out)
        if all((a.mode, task, pid_of(lines)) in done for _, lines in PROGRAMS[a.mode](task)):
            continue
        cmd = [sys.executable, os.path.abspath(__file__), 'one', a.out, a.mode, task, '--limit', str(a.limit)]
        got = subprocess.run(cmd)
        if got.returncode:
            print('%s: the process ended with %d' % (task, got.returncode), file=sys.stderr, flush=True)
            with open(a.out, 'a') as fo:
                fo.write(json.dumps(dict(set=a.mode, task=task, pid='process', status='process_failed', refusal='exit %d' % got.returncode)) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
