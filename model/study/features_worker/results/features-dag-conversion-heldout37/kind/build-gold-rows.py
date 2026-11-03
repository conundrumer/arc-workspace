"""Gold scope rows. One row per task, form, replicate and scope rule, flushed task by task; a rerun skips finished tasks. Runs on the engine's python: it reads column types from the engine's render of each program, with no task data.

  features_dagc_env.sh 1 kind/build-gold-rows.py [--seconds S] [--limit N] [--out DIR]

Sources (the pins of the conversion record):
  split nonheld   the first pair of each task of corpus-v3mix outside features-worker/arm/eval-tasks.txt and held/leave_out.txt (features_dagc_lib.fit_gold): 1,011 tasks
  split held      view-pass1 of gold-v3-extended-cut, the text that the visits and covers of the pool runs index (features_dagc_lib.pass1_gold), on the 37 tasks of held/tasks.txt

Scope rules, for gold form f with read forms R(f), k = 6 as in Pool.scope and SEARCH_ORACLE_CONTEXT=2. A form that f could read is a non-descendant of f: not f, not a form that reads f.
  picks6          R(f) with ancestors, and k - |R(f)| other non-descendants of f drawn at random, each with ancestors. The primary rule.
  closure         R(f) with ancestors
  cut             the forms before f in ProgramDag.random_order(s, non_descendants(f) | {f}), for seed s in 0 and 1 (rep = s): the scope of a search that has found those forms. This takes the place of `prefix`, all earlier forms.
  picks6-foreign  as picks6, with the other picks drawn from the gold of one other nonheld task, each with ancestors in that task: forms that mean nothing to this task, like a search's junk
Only picks6 runs on held tasks.
"""
import argparse
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, HERE)
sys.path.insert(1, HERE.rsplit('/kind/', 1)[0] + '/')  # the record folder: features_dag_order, features_dagc_lib
import arclog  # noqa: E402
import features_dag_order as D  # noqa: E402
import features_dagc_lib as L  # noqa: E402
import scope_facts as F  # noqa: E402

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


def hash_of(text):
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def texts():
    out = {}
    for t, lines in sorted(L.fit_gold().items()):
        out['nonheld', t] = '\n'.join(lines)
    for t, lines in L.pass1_gold().items():
        out['held', t] = '\n'.join(lines)
    return out


def cut_scope(prog, forms, f, seed):
    """The forms before f in the seed's random order of the non-descendants of f and f, as form numbers. prog is the ProgramDag of the whole text; form numbers go by head name."""
    by_name = {x['name']: x['i'] for x in forms}
    key = f['name']
    order = prog.random_order(seed, prog.non_descendants(key) | {key})
    return [by_name[k] for k in order[:order.index(key)]]


def scope_of(rule, rep, forms, f, prog, all_forms, pool, t, rng):
    base = F.closure(forms, f['parents'])
    need = max(0, K - len(f['parents']))
    if rule == 'closure':
        return [forms[i] for i in base]
    if rule == 'cut':
        return [forms[i] for i in cut_scope(prog, forms, f, rep)]
    if rule == 'picks6':
        others = [i for i in F.non_descendants(forms, f['i']) if i not in f['parents']]
        got = set(base)
        for i in rng.sample(others, min(need, len(others))):
            got |= F.closure(forms, [i])
        return [forms[i] for i in got]
    # picks6-foreign: order numbers past this task's; a foreign form reads only foreign forms
    u = rng.choice([x for x in pool if x != t])
    other = all_forms['nonheld', u]
    got = set()
    for i in rng.sample(range(len(other)), min(need, len(other))):
        got |= F.closure(other, [i])
    off = len(forms)
    return [forms[i] for i in base] + [dict(other[i], i=off + i, parents=[off + p for p in other[i]['parents']]) for i in got]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=HERE)
    ap.add_argument('--seconds', type=float, default=None)
    ap.add_argument('--limit', type=int, default=None, help='stop after this many tasks')
    a = ap.parse_args()
    path = os.path.join(a.out, 'gold-scope-rows.tsv')
    tpath = os.path.join(a.out, 'gold-form-rows.tsv')
    done = set()
    if os.path.exists(tpath):
        done = {(l.split('\t')[0], l.split('\t')[1]) for l in open(tpath) if not l.startswith('split\t')}
    new = not os.path.exists(path)
    out, tout = open(path, 'a'), open(tpath, 'a')
    if new:
        out.write('\t'.join(COLS) + '\n')
        tout.write('split\ttask\tform\tkind\tnreads\tdepth\thead\tkey\tcols\n')
    T = texts()
    t0 = time.time()
    all_forms, bad = {}, []
    cache_path = os.path.join(a.out, 'column-types-cache.json')  # the engine's render of each text, read once
    cache = json.load(open(cache_path)) if os.path.exists(cache_path) else {}
    fresh = 0
    for n, (key, text) in enumerate(sorted(T.items())):
        ck = '%s %s %s' % (key[0], key[1], hash_of(text))
        try:
            if ck not in cache:
                cache[ck] = {str(k): sorted(v) for k, v in column_types(text).items()}
                fresh += 1
            all_forms[key] = F.gold_forms(text, {int(k): set(v) for k, v in cache[ck].items()})
        except Exception as e:  # noqa: BLE001
            bad.append((key, repr(e)[:200]))
            all_forms[key] = None
        if n % 200 == 0:
            print('types %d of %d, %.1f s' % (n, len(T), time.time() - t0), flush=True)
    if fresh:
        json.dump(cache, open(cache_path, 'w'))
    print('no forms for', bad, flush=True)
    pool = sorted(k[1] for k, v in all_forms.items() if v and k[0] == 'nonheld')
    t0, finished = time.time(), 0
    todo = [k for k in sorted(all_forms) if all_forms[k] and k not in done]
    if a.limit:
        todo = todo[:a.limit]
    for key in todo:
        if a.seconds and time.time() - t0 > a.seconds:
            print('stopped: budget spent', flush=True)
            break
        split, t = key
        forms = all_forms[key]
        prog = D.ProgramDag([l for l in T[key].strip().split('\n')])
        for f in forms:
            tout.write('\t'.join(map(str, (split, t, f['i'], f['kind'], len(f['parents']), f['depth'], f['head'], int(f['key']), ','.join(sorted(f['cols']))))) + '\n')
            rules = (('picks6', 8), ('closure', 1), ('cut', 2), ('picks6-foreign', 8)) if split == 'nonheld' else (('picks6', 8),)
            for rule, reps in rules:
                for rep in range(reps):
                    rng = random.Random('%d %s %d %s %d' % (SEED, t, f['i'], rule, rep))
                    S = scope_of(rule, rep, forms, f, prog, all_forms, pool, t, rng)
                    q = F.facts(S)
                    out.write('\t'.join(map(str, [split, t, f['i'], f['kind'], len(f['parents']), rule, rep] + [q[x] for x in F.FACTS])) + '\n')
        out.flush()
        tout.flush()
        finished += 1
        if finished % 25 == 0 or finished == len(todo):
            rate = finished / max(time.time() - t0, 1e-9)
            print('%d of %d tasks, %.1f tasks per s, eta %.0f s' % (finished, len(todo), rate, (len(todo) - finished) / rate), flush=True)
    print('done: %d tasks in %.0f s' % (finished, time.time() - t0), flush=True)


if __name__ == '__main__':
    main()
