"""Runs the held feasible walk, and skips a form whose walk writes no row for STALL seconds. One engine call can run for many minutes with no deadline. Each skipped form goes on skipped-forms.txt; rows of its earlier picks stay.

  features_feasible_resume.py STALL
"""
import json, os, signal, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
R = '/Users/davidlu/code/arc-workspace/'
FORMS = R + 'work/lm/data-study/sampler/sampler-worker/sampler-relation-pick-read-heldout431-census/forms_all.json'
GOLDS = R + 'work/lm/data-study/sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/points-base.json'
PY = R + 'work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python'
OUT, SKIP, LEFT = HERE + 'feasible-walk-held.jsonl', HERE + 'skipped-forms.txt', HERE + 'forms-left.json'
STALL = float(sys.argv[1])
forms = json.load(open(FORMS))


def skipped():
    if not os.path.exists(SKIP):
        return set()
    return {(a, int(b)) for a, b in (x.split() for x in open(SKIP) if x.strip())}


def done():
    d = set()
    for line in open(OUT):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get('rec') == 'form':
            d.add((r['task'], r['line']))
    return d


while True:
    left = [f for f in forms if (f[4], f[5]) not in skipped()]
    json.dump(left, open(LEFT + '.new', 'w')); os.replace(LEFT + '.new', LEFT)
    p = subprocess.Popen([PY, '-u', HERE + 'features_feasible_walk.py', '--forms', LEFT, '--golds', GOLDS, '--out', OUT], start_new_session=True)
    size, seen = os.path.getsize(OUT), time.time()
    while p.poll() is None:
        time.sleep(5)
        s = os.path.getsize(OUT)
        if s != size:
            size, seen = s, time.time()
        elif time.time() - seen > STALL:
            os.killpg(p.pid, signal.SIGKILL); p.wait()
            d = done()
            stuck = next(f for f in left if (f[4], f[5]) not in d)
            with open(SKIP, 'a') as w:
                w.write('%s %d\n' % (stuck[4], stuck[5]))
            print('skip', stuck[4], stuck[5], 'after', STALL, 's with no row', flush=True)
            break
    else:
        print('walk ended', p.returncode, flush=True)
        break
