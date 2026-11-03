"""Gold scope rows. One row per task, form, replicate and scope rule, flushed task by task; a rerun skips finished tasks. Runs on the engine's python: it reads column types from the engine's render of each program, with no task data.

Sources:
  split nonheld   work/lm/data-study/gold/gen-v3-11f6a212c/ast-corpus: the normal form (&rN names, first case) of corpus/gen/*.arclog, on tasks outside features-worker/arm/eval-tasks.txt
  split held      the kit's points-eval.json, the new text the base-cost record read, on the 37 tasks of held/tasks.txt

Scope rules, for gold form f with read forms R(f) among the forms before it, k = 6 as in Pool.scope and SEARCH_ORACLE_CONTEXT=2:
  picks6          R(f) with ancestors, and k - |R(f)| other earlier forms drawn at random, each with ancestors. The primary rule.
  closure         R(f) with ancestors
  prefix          all earlier forms
  picks6-foreign  as picks6, with the other picks drawn from the gold of one other non-held task, each with ancestors in that task: forms that mean nothing to this task, like a search's junk
Only picks6 runs on held tasks.
"""
import gzip
import json
import os
import random
import sys
import time

import arclog

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, HERE)
import scope_facts as F  # noqa: E402

ROOT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
GOLD = ROOT + 'gold/gen-v3-11f6a212c/ast-corpus/'
KIT = ROOT + 'sampler/sampler-worker/kits/sampler-pool-extended-text-pass1-8be414670/'
EVAL = set(open(ROOT + 'features-worker/arm/eval-tasks.txt').read().split())
HELD = open(ROOT + 'sampler/sampler-worker/held/tasks.txt').read().split()
K = 6
REPS = 8
SEED = 20261101
COLS = ['split', 'task', 'form', 'kind', 'nreads', 'rule', 'rep'] + list(F.FACTS)


def column_types(text):
    """{line number of a form: set of its relations' column types}, from the engine's render."""
    p = arclog.StudyProgram.from_sexp(text, arclog.DecodeSettings())
    got = {}
    for e in json.loads(p.render_json())['definitions']['native_relations']:
        for w in e.get('column_witnesses') or ():
            t = (w.get('physical_type') or {}).get('type') or w.get('type')
            if t:
                got.setdefault(e['definition_path'][0], set()).add(t)
    return got


def texts():
    out = {}
    for t in sorted(os.listdir(GOLD)):
        if t not in EVAL:
            with gzip.open(GOLD + t + '/pairs.jsonl.gz', 'rt') as f:
                out['nonheld', t] = json.loads(f.readline())['gold_sexp']
    held = {x['task']: x['gold_sexp'] for x in json.load(open(KIT + 'points-eval.json'))}
    for t in HELD:
        out['held', t] = held[t]
    return out


def main():
    path = HERE + 'gold-scope-rows.tsv'
    tpath = HERE + 'gold-form-rows.tsv'
    done = set()
    if os.path.exists(tpath):
        done = {(l.split('\t')[0], l.split('\t')[1]) for l in open(tpath) if not l.startswith('split\t')}
    new = not os.path.exists(path)
    out, tout = open(path, 'a'), open(tpath, 'a')
    if new:
        out.write('\t'.join(COLS) + '\n')
        tout.write('split\ttask\tform\tkind\tnreads\tdepth\thead\tkey\tcols\n')
    T = texts()
    # every form list is built first: the foreign rule reads other tasks' forms
    t0 = time.time()
    all_forms, bad = {}, []
    for n, (key, text) in enumerate(sorted(T.items())):
        try:
            all_forms[key] = F.gold_forms(text, column_types(text))
        except Exception as e:  # noqa: BLE001
            bad.append((key, repr(e)[:200]))
            all_forms[key] = None
        if n % 200 == 0:
            print('types %d of %d, %.1f s' % (n, len(T), time.time() - t0), flush=True)
    print('no forms for', bad, flush=True)
    pool = sorted(k[1] for k, v in all_forms.items() if v and k[0] == 'nonheld')
    t0, finished = time.time(), 0
    todo = [k for k in sorted(all_forms) if all_forms[k] and k not in done]
    for key in todo:
        split, t = key
        forms = all_forms[key]
        for f in forms:
            tout.write('\t'.join(map(str, (split, t, f['i'], f['kind'], len(f['parents']), f['depth'], f['head'], int(f['key']), ','.join(sorted(f['cols']))))) + '\n')
            before = forms[:f['i']]
            base = F.closure(forms, f['parents'])
            rules = ('picks6', 'closure', 'prefix', 'picks6-foreign') if split == 'nonheld' else ('picks6',)
            for rule in rules:
                for rep in range(REPS if rule in ('picks6', 'picks6-foreign') else 1):
                    rng = random.Random('%d %s %d %s %d' % (SEED, t, f['i'], rule, rep))
                    S = [forms[i] for i in base]
                    need = max(0, K - len(f['parents']))
                    if rule == 'picks6':
                        others = [x['i'] for x in before if x['i'] not in f['parents']]
                        got = set(base)
                        for i in rng.sample(others, min(need, len(others))):
                            got |= F.closure(forms, [i])
                        S = [forms[i] for i in got]
                    elif rule == 'prefix':
                        S = list(before)
                    elif rule == 'picks6-foreign':
                        u = rng.choice([x for x in pool if x != t])
                        other = all_forms['nonheld', u]
                        got = set()
                        for i in rng.sample(range(len(other)), min(need, len(other))):
                            got |= F.closure(other, [i])
                        # order numbers past this task's: a foreign form reads only foreign forms
                        off = len(forms)
                        S += [dict(other[i], i=off + i, parents=[off + p for p in other[i]['parents']]) for i in got]
                    q = F.facts(S)
                    out.write('\t'.join(map(str, [split, t, f['i'], f['kind'], len(f['parents']), rule, rep] + [q[x] for x in F.FACTS])) + '\n')
        out.flush()
        tout.flush()
        finished += 1
        if finished % 100 == 0 or finished == len(todo):
            rate = finished / max(time.time() - t0, 1e-9)
            print('%d of %d tasks, %.1f tasks per s, eta %.0f s' % (finished, len(todo), rate, (len(todo) - finished) / rate), flush=True)


main()
