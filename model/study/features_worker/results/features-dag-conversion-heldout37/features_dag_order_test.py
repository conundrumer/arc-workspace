#!/usr/bin/env python
"""Checks features_dag_order.py over corpus views: a form reads back as itself, the DAG has no cycle, written order is a topological order, and a permuted text gives equal outputs.

  python features_dag_order_test.py OUT.jsonl VIEW [VIEW ...]

A permuted text is a topological order by a seed, of a form's bodies and OR branches, or of a program's forms. Label names stay.
The tally also counts the forms with a NOT or an ALL that has a marked label which has a site outside it (`marked local with an outside site`): the forms whose parents the local-label pass changes against the rule that read marks. Each view adds one line to OUT.jsonl per finished stem and a rerun skips stems with a line. A line that a check fails holds the form's text and the check. Prints a rate and an ETA.
"""
import collections
import glob
import gzip
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import features_dag_order as D  # noqa: E402

KEEP = 20  # failing examples per check and stem
SEEDS = (0, 1, 2)
PERMUTED = (10, 11, 12)  # the seeds of the permuted texts


def marked_local_outside(text):
    """True where a NOT or an ALL has a marked label that has a site outside it. This reads marks, and only this check does."""
    tree = D.parse(text)
    total = collections.Counter(n for b in D.form_bodies(tree) for x in b.holder[b.low:b.high] for _, _, _, n in D.label_sites(x if isinstance(x, list) else [None, x]))

    def walk(x):
        if isinstance(x, list) and x:
            if x[0] in ('NOT', 'ALL'):
                sites = list(D.label_sites(x))
                inside = collections.Counter(n for _, _, _, n in sites)
                if any(m and inside[n] < total[n] for _, _, m, n in sites):
                    return True
            return any(walk(y) for y in x)
        return False
    return walk(tree)


def check_form(text, tally, fails, mode):
    def fail(why, extra=None):
        tally['fail: ' + why] += 1
        if len(fails) < KEEP:
            fails.append(dict(why=why, mode=mode, text=text, extra=extra))

    if D.unparse(D.parse(text)) != text:
        fail('does not read back')
        return
    try:
        dag = D.FormDag(text, mode)
    except ValueError as e:
        fail('cycle', str(e))
        return
    tally[mode + ': forms'] += 1
    tally[mode + ': forms with an OR'] += '(OR ' in text
    tally[mode + ': marked local with an outside site'] += marked_local_outside(text)
    tally[mode + ': atoms'] += len(dag.atoms)
    tally[mode + ': bodies'] += len(dag.all_bodies)
    if dag.is_topological(dag.written_order()):
        tally[mode + ': written is topological'] += 1
    else:
        tally[mode + ': written is not topological'] += 1
        if len(fails) < KEEP:
            fails.append(dict(why='written order is not topological', mode=mode, text=text))
    n = dag.count_orders()
    tally[mode + ': forms past the cap'] += n is None
    tally[mode + ': forms with one order'] += n == 1
    want = dag.summary(SEEDS)
    tally[mode + ': forms with no atom'] += not want['atoms']
    for seed in PERMUTED:
        order = dag.random_order(seed)
        if not dag.is_topological(order):
            fail('random order is not topological')
            continue
        leaves = dag.leaves(order)
        for i in range(len(leaves)):
            if not dag.is_downset(leaves[:i]):
                fail('a prefix is not a downset')
                break
        other_text = dag.render(order)
        if D.parse(other_text) == D.parse(text):
            tally[mode + ': permutations equal to written'] += 1
            continue
        tally[mode + ': permutations'] += 1
        got = D.FormDag(other_text, mode).summary(SEEDS)
        for k, v in want.items():
            if got[k] != v:
                fail('output differs: ' + k, other_text)


def check_program(lines, tally, fails):
    try:
        p = D.ProgramDag(lines)
    except ValueError as e:
        tally['fail: program cycle'] += 1
        fails.append(dict(why='program cycle', text=str(e)))
        return
    tally['programs'] += 1
    written = [D.parse(x)[1] if not x.startswith('(OUT') else 'OUT' for x in lines]
    at = {k: i for i, k in enumerate(written)}
    if all(at[q] < at[k] for k in written for q in p.parent_ids[k]):
        tally['programs written topological'] += 1
    else:
        tally['fail: program written order is not topological'] += 1
    want = p.summary(SEEDS)
    for seed in PERMUTED:
        order = p.random_order(seed)
        if p.summary(SEEDS) != want or D.ProgramDag(p.texts(order)).summary(SEEDS) != want:
            tally['fail: program output differs'] += 1
            if len(fails) < KEEP:
                fails.append(dict(why='program output differs', order=order))
        tally['program permutations'] += 1


def main():
    out, views = sys.argv[1], sys.argv[2:]
    done = {(r['view'], r['stem']) for r in map(json.loads, open(out))} if os.path.exists(out) else set()
    todo = [(v, Path(p).parent.name, p) for v in views for p in sorted(glob.glob(v.rstrip('/') + '/*/pairs.jsonl.gz')) if (v, Path(p).parent.name) not in done]
    print('%d stems to do, %d done' % (len(todo), len(done)), flush=True)
    t0, total = time.time(), collections.Counter()
    with open(out, 'a') as f:
        for n, (view, stem, path) in enumerate(todo, 1):
            tally, fails, seen = collections.Counter(), [], set()
            with gzip.open(path, 'rt') as g:
                for row in g:
                    sexp = json.loads(row)['gold_sexp']
                    if sexp in seen:
                        continue
                    seen.add(sexp)
                    lines = [x for x in sexp.splitlines() if x.strip()]
                    check_program(lines, tally, fails)
                    for text in lines:
                        if not text.startswith('(OUT'):
                            check_form(text, tally, fails, 'join')
            total.update(tally)
            f.write(json.dumps(dict(view=view, stem=stem, tally=tally, fails=fails)) + '\n')
            f.flush()
            if n % 50 == 0 or n == len(todo):
                el = time.time() - t0
                print('[%d/%d %.1f stems/s eta %ds] %s' % (n, len(todo), n / el, el / n * (len(todo) - n), dict(total)), flush=True)
    print(dict(total))


if __name__ == '__main__':
    main()
