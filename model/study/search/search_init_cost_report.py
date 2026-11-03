#!/usr/bin/env python
"""What holds the cost of a gold INIT: report on saved records, with the read steps kept in this folder.

    work/lm/.venv/bin/python search_init_cost_report.py            # all reads, each from saved files, about 3 minutes, one process
    work/lm/.venv/bin/python search_init_cost_report.py outcomes   # one read

Records read:
- Runs: arms base_s0 and base_s1 of sampler-pool-extended-text-pass1-600s/out-all37, 37 held-out tasks, 600 s wall, worker path, EPYC 9654, code c87cf482a, gold gold-v3-extended-cut/view-pass1, priors models-base.
- Rows: form-rows.tsv, cover-rows.tsv, kind-rows.tsv of sampler-base-cost-read-heldout37.
- Trace logs: search-repeat-trace-6tasks-600s-c87cf482a, 6 held-out tasks, seed 1, 600 s, EPYC 9B45, SEARCH_TRACE=2.
- Corpus gold: gold-v3-extended-cut/lines-all-stems.json. Fit rows leave out the 121 stems of the refit's leave-out list and the 37.

Files made once on the Mac runtime ba0754492 (one process each) and read here. Remake them with:
- parts-base.jsonl: parts_run.py SECONDS, walk bits by part of each form at its census and parents scope (35 of 37 tasks: f560132c and one more ran out of time).
- slots.jsonl: scopes_extract2.py, the right cell slots of each INIT, RULE and DET form with exposure to the first cover.
- slot-walks.jsonl: run_walks.sh slot_walks.py SECONDS, gold text walked over each slot's scope, 4,487 slots, 2 minutes.
- slot-var-LABEL.jsonl: all_var.sh, the INIT slots under other settings, under a minute each, gold's written atom order.
- slot-ord-LABEL.jsonl: run_ord.sh, the same walks over up to 6 atom orders per INIT and 4 per RULE or DET (orders.py), at slot, parents and census scopes. Don't rerun run_ord.sh or run_ord2.sh as they are: one reordered walk took the process to 33 GiB. Each run needs a hard memory cap in the process first. RULE and DET have no parents or census walks over orders.

A step whose name says written order reads one written atom order, and census bits also follow written form order: those are upper bounds for the form. Step `over orders` is the read to quote. Nothing here uses an atom index as a feature or a split. Parts by key, port and head are places the grammar fixes.

Steps: each is a script of this folder, run in order, and prints its table.
"""
import collections
import glob
import json
import math
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/'
ARMS = W + 'sampler-pool-extended-text-pass1-600s/out-all37/'
KIND_ROWS = W + 'sampler-base-cost-read-heldout37/kind-rows.tsv'


def outcomes():
    """Tries by outcome per kind, and INIT visits by scope size."""
    import csv
    t = collections.defaultdict(collections.Counter)
    for r in csv.DictReader(open(KIND_ROWS), delimiter='\t'):
        if r['arm'].startswith('base'):
            for k in ('tries', 'log_kept', 'log_equal', 'log_drop', 'visits'):
                t[r['kind']][k] += int(r[k])
    for k, c in t.items():
        n = c['log_kept'] + c['log_equal'] + c['log_drop']
        if n:
            print('%-10s tries %7d kept %.3f equal %.3f table failure %.3f; bits to no failure %.2f; tries per visit %.1f' % (k, n, c['log_kept'] / n, c['log_equal'] / n, c['log_drop'] / n, -math.log2(1 - c['log_drop'] / n), c['tries'] / c['visits']))
    tasks = open(W + 'held/tasks.txt').read().split()
    runs, withe, tries = 0, 0, 0
    size = collections.Counter()
    for arm in ('base_s0', 'base_s1'):
        for tk in tasks:
            e = 0
            for p in glob.glob('%s%s/%s/work/*.visits' % (ARMS, arm, tk)):
                for l in open(p):
                    try:
                        v = json.loads(l)
                    except ValueError:
                        continue
                    if v['kind'] == 'INIT':
                        size[min(len(v['fids']), 13)] += v['tries']
                        if not v['fids']:
                            e += v['tries']
            runs += 1
            withe += e > 0
            tries += e
    print('runs', runs, 'with an empty scope INIT visit', withe, 'tries there', tries)
    print('INIT tries by scope size (13 = 13 or more):', sorted(size.items()))


STEPS = [('outcomes', outcomes), ('components', 'trace1.py'), ('over orders', 'fit_orders.py'), ('slot scope over orders, each kind', 'fit_slot_only.py'), ('orders seen', 'order_counts.py'),('parts, written order', 'parts_table.py'), ('fit, written order', 'fit_steps.py'), ('form or slot', 'fit_live2.py'), ('rate by scope, written order', 'empty_rate.py'), ('place in slot', 'depth.py'),
         ('no reads', 'reads0.py'), ('near misses', 'nearmiss.py'), ('order', 'port_mi2.py'), ('text rule', 'none_rule.py'), ('variants', 'var_read.py')]


def main():
    want = sys.argv[1:]
    for name, step in STEPS:
        if want and name not in want:
            continue
        print('\n=====', name)
        if callable(step):
            step()
        else:
            sys.argv = [step]
            runpy.run_path(HERE + step, run_name='__main__')


if __name__ == '__main__':
    main()
