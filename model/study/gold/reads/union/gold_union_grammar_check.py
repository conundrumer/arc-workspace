"""Which case programs of a union folder the grammar of an engine refuses. Each distinct program text of cases-SET.jsonl (the folder GOLD_UNION_DIR) is decoded as `gold_union_fits.sampler_decode` does for the fits stage: `StudyProgram.from_sexp` and then `Session.check_stream`, under the sampler's settings, with no table evaluated. A refusal that needs evaluation (DetAdmission, the decode having ended) is not found.

  PYTHONPATH=<site> ARCLOG_IDENT_SOURCE=value GOLD_UNION_DIR=<folder> python gold_union_grammar_check.py run OUT [SET ...] [--shard K N]
  python gold_union_grammar_check.py summary OUT [--expect TASK,TASK,...]

`run` writes OUT/grammar-SET[-K].jsonl (a zstd stream, study_zst.py), one line per task, as each task is checked: task, set, engine, and programs, a list of {text_sha, cases, decode}. `decode` is 'ok', 'refused: <reason> at token <i>', 'does not parse: <reason>', or 'error: <reason>'. SET is train, dev or held-out (default: all three). `--shard K N` takes the tasks at positions K, K + N, ... of the set and writes grammar-SET-K.jsonl. A restart skips the tasks that the file has (a Python with zstandard runs this file). With GRAMMAR_TASKS set (tasks separated by spaces), `run` takes only those tasks. It prints a progress line every 20 tasks with the rate in programs per second and the time left.
SAMPLER_LIVE_TRY names the live_try.py whose SETTINGS the check takes, as for gold_union_fits.py (default: gen-r69's live_try-08013c6cc.py, whose SETTINGS is a constant dict).
`summary` reads every OUT/grammar-*.jsonl.zst or .jsonl and prints the tasks and cases refused with each reason; with --expect, the tasks of that list that no refusal names and the refused tasks that the list lacks.
"""
import json, os, re, sys, time
from pathlib import Path

os.environ.setdefault('SAMPLER_LIVE_TRY', '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gen-r69/tools/live_try-08013c6cc.py')
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gold_union_fits as F  # noqa: E402
import study_zst as Z  # noqa: E402

SETS = ('train', 'dev', 'held-out')
EVERY = 20  # tasks between progress lines


def programs_by_task(set_name):
    """{task: {text: [case]}} of cases-SET.jsonl, in the order of the file."""
    got = {}
    for l in Z.open_text(F.OUT + 'cases-%s.jsonl' % set_name):
        r = json.loads(l)
        got.setdefault(r['task'], {}).setdefault(r['gold_sexp'], []).append(r['case'])
    return got


def decode_of(env, task_json, text):
    try:
        got = F.sampler_decode(env, task_json, text)
    except Exception as e:  # noqa: BLE001
        return 'error: %s: %s' % (type(e).__name__, str(e)[:150])
    return got if got else 'error: the engine has no Session.check_stream'


def done_tasks(path):
    """The tasks of the output file, after its torn last line is cut off."""
    if not Z.exists(path):
        return set()
    Z.trim_to_last_newline(path)
    return {json.loads(l)['task'] for l in Z.open_text(path)}


def run(out, sets, shard):
    k, n = shard or (0, 1)
    os.makedirs(out, exist_ok=True)
    env = F.engine()
    engine = F.engine_name(env)
    tasks_dir = F.ROOT / 'data/tasks'
    for s in sets:
        by = programs_by_task(s)
        mine = [t for i, t in enumerate(sorted(by)) if i % n == k]
        if os.environ.get('GRAMMAR_TASKS'):  # tasks separated by spaces, in place of every task
            mine = [t for t in mine if t in os.environ['GRAMMAR_TASKS'].split()]
        path = '%s/grammar-%s%s.jsonl' % (out, s, '-%d' % k if shard else '')
        done = done_tasks(path)
        left = [t for t in mine if t not in done]
        rest, seen, refused, start = sum(len(by[t]) for t in left), 0, 0, time.time()
        print('%s: %d tasks in this shard, %d done, %d programs to check, engine %s' % (s, len(mine), len(done), rest, engine), flush=True)
        with Z.open_text(path, 'a', line_buffering=True) as f:
            for i, t in enumerate(left, 1):
                task_json = json.load(open(tasks_dir / (t + '.json')))
                progs = [dict(text_sha=F.sha16(text), cases=cases, decode=decode_of(env, task_json, text)) for text, cases in by[t].items()]
                f.write(json.dumps(dict(task=t, set=s, engine=engine, programs=progs)) + '\n')
                seen += len(progs)
                refused += sum(p['decode'] != 'ok' for p in progs)
                if i % EVERY == 0 or i == len(left):
                    el = time.time() - start
                    print('%s %d/%d tasks  %d programs, %d not ok  %.1f programs/s  %.0fs  eta %.0fs' % (s, i, len(left), seen, refused, seen / el, el, el / seen * (rest - seen)), flush=True)


def reason(decode):
    return re.sub(r'`[^`]*`', '`_`', re.sub(r'Path\(NodePath\(\[[^\]]*\]\)\)', 'Path', re.sub(r' at token \d+', '', decode)))[:150]


def summary(out, expect):
    rows = [json.loads(l) for p in Z.glob(out + '/grammar-*.jsonl') for l in Z.open_text(p) if l.endswith('\n')]
    by_task = {}
    for r in rows:
        bad = [p for p in r['programs'] if p['decode'] != 'ok']
        if bad:
            by_task[r['task']] = (r['set'], bad)
    print('%d tasks read, %d programs; %d tasks have a refused program' % (len(rows), sum(len(r['programs']) for r in rows), len(by_task)))
    reasons = {}
    for t, (s, bad) in sorted(by_task.items()):
        ncases = sum(len(p['cases']) for p in bad)
        total = sum(len(p['cases']) for r in rows if r['task'] == t for p in r['programs'])
        print('%-9s %-8s %4d of %4d cases refused (%d programs)' % (t, s, ncases, total, len(bad)))
        for p in bad:
            reasons.setdefault(reason(p['decode']), {}).setdefault(t, 0)
            reasons[reason(p['decode'])][t] += len(p['cases'])
    print('\nreasons:')
    for why, ts in sorted(reasons.items(), key=lambda kv: -sum(kv[1].values())):
        print('%6d cases, %3d tasks  %s  [%s]' % (sum(ts.values()), len(ts), why, ' '.join('%s:%d' % kv for kv in sorted(ts.items()))))
    if expect is not None:
        read = {r['task'] for r in rows}
        print('\nexpected, no refusal: %s' % ' '.join(t for t in expect if t not in by_task and t in read))
        print('expected, not read: %s' % ' '.join(t for t in expect if t not in read))
        print('refused, not expected: %s' % ' '.join(t for t in sorted(by_task) if t not in expect))


if __name__ == '__main__':
    a = sys.argv[1:]
    if a[:1] == ['summary']:
        summary(a[1], a[a.index('--expect') + 1].split(',') if '--expect' in a else None)
    elif a[:1] == ['run']:
        shard = None
        if '--shard' in a:
            i = a.index('--shard')
            shard = (int(a[i + 1]), int(a[i + 2]))
            a = a[:i] + a[i + 3:]
        run(a[1], a[2:] or list(SETS), shard)
    else:
        print(__doc__)
