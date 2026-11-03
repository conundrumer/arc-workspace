"""Checks of the kind rows (item 16), on the gold of the tasks in the column-types cache that build-gold-rows.py wrote.

  features_dagc_env.sh 1 kind/check-scope-facts.py [--out DIR] [--tasks N] [--seed S]

1. Scramble: for each scope of each rule, the facts of the scope equal the facts of the same scope with its forms shuffled and renumbered (a form's number means no order; its parents follow the renumbering).
2. Power: the same shuffle changes the facts `last`, `head` and `cols` of the earlier definition (scope_facts.py of features-kind-pick-given-scope-contents-heldout37) on some scopes.
3. Scope rules: each scope holds the ancestors of the forms that f reads, and no descendant of f and not f; a `cut` scope is topological and equals the prefix of its seed's order; `closure` is the ancestors of R(f) alone.
Appends to check-scope-facts.txt in the kind folder.
"""
import argparse
import importlib.util
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, HERE)
sys.path.insert(1, HERE.rsplit('/kind/', 1)[0] + '/')
import scope_facts as F  # noqa: E402


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


G = load(HERE + 'build-gold-rows.py', 'build_gold_rows')
OLD = load('/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-kind-pick-given-scope-contents-heldout37/scope_facts.py', 'old_scope_facts')


def scramble(S, rng):
    """The same forms in another list order, each with a new number; parents follow."""
    nums = rng.sample(range(1000, 1000 + 10 * max(len(S), 1)), len(S))
    new = {f['i']: n for f, n in zip(S, nums)}
    out = [dict(f, i=new[f['i']], parents=[new.get(p, 10 ** 6 + p) for p in f['parents']]) for f in S]
    rng.shuffle(out)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default=HERE)
    ap.add_argument('--tasks', type=int, default=60)
    ap.add_argument('--seed', type=int, default=1)
    a = ap.parse_args()
    cache = json.load(open(os.path.join(a.out, 'column-types-cache.json')))
    T = G.texts()
    keys = sorted(T)
    rng = random.Random(a.seed)
    pick = [k for k in rng.sample(keys, min(a.tasks, len(keys)))]
    held = [k for k in keys if k[0] == 'held'][:a.tasks // 4]
    pick = sorted(set(pick) | set(held))
    D = G.D
    tally = dict(scopes=0, scramble_fail=0, old_changed=0, old_scopes=0, rule_fail=0, cut_fail=0)
    fails = []
    pool_forms = {}
    for key in pick:
        text = T[key]
        ck = '%s %s %s' % (key[0], key[1], G.hash_of(text))
        if ck not in cache:
            continue
        forms = F.gold_forms(text, {int(k): set(v) for k, v in cache[ck].items()})
        pool_forms[key] = forms
    pool = sorted(k[1] for k in pool_forms if k[0] == 'nonheld')
    allf = {k: v for k, v in pool_forms.items()}
    for key, forms in pool_forms.items():
        split, t = key
        prog = D.ProgramDag(T[key].strip().split('\n'))
        by_name = {x['name']: x['i'] for x in forms}
        for f in forms:
            rules = (('picks6', 8), ('closure', 1), ('cut', 2), ('picks6-foreign', 2)) if split == 'nonheld' and len(pool) > 1 else (('picks6', 8),)
            nd = set(F.non_descendants(forms, f['i']))
            ds = F.descendants(forms, f['i'])
            for rule, reps in rules:
                for rep in range(reps):
                    r = random.Random('%d %s %d %s %d' % (G.SEED, t, f['i'], rule, rep))
                    S = G.scope_of(rule, rep, forms, f, prog, allf, pool, t, r)
                    tally['scopes'] += 1
                    ids = {x['i'] for x in S}
                    own = {x['i'] for x in S if x['i'] < len(forms)}
                    base = F.closure(forms, f['parents'])
                    ok = base <= ids and not (own & (ds | {f['i']}))
                    if rule == 'closure':
                        ok = ok and ids == base
                    if rule == 'cut':
                        keyname = f['name']
                        order = prog.random_order(rep, prog.non_descendants(keyname) | {keyname})
                        want = [by_name[k] for k in order[:order.index(keyname)]]
                        at = {x: j for j, x in enumerate(want)}
                        topo = all(at[p] < at[x] for x in want for p in forms[x]['parents'] if p in at)
                        ok = ok and [x['i'] for x in S] == want and topo
                        tally['cut_fail'] += not ok
                    if rule in ('picks6', 'picks6-foreign'):
                        ok = ok and own <= nd | base
                    tally['rule_fail'] += not ok
                    if not ok and len(fails) < 5:
                        fails.append((key, f['i'], rule, rep))
                    q = F.facts(S)
                    for _ in range(2):
                        S2 = scramble(S, rng)
                        if F.facts(S2) != q:
                            tally['scramble_fail'] += 1
                            if len(fails) < 5:
                                fails.append((key, f['i'], rule, rep, 'scramble'))
                    o = OLD.facts(S)
                    tally['old_scopes'] += 1
                    if any(OLD.facts(scramble(S, rng))[x] != o[x] for x in ('last', 'head', 'cols')):
                        tally['old_changed'] += 1
    line = '%s: %d tasks, %s, first failures %s' % (time.strftime('%H:%M:%S'), len(pool_forms), tally, fails)
    print(line)
    with open(HERE + 'check-scope-facts.txt', 'a') as f:
        f.write(line + '\n')


main()
