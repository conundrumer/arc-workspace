"""Checks the jobs of a node score run: the log lines, the node score policy's counters in each bank, the cost, and the uses of the picks.

  <python> -I search_node_score_parity.py OUT [mac|pod]

OUT is the folder of the jobs, OUT/<arm>/<task>/ as run3600.sh writes it (OUT/out is used where it exists). The arm decides what a job must show:
  parity*  the node score of the hand model through the new path, with NODE_SCORE_CHECK=1: name ship, fold 0, check 1
  mt*      name mt, check 0
  depth*   name depth, check 0
  other    no node score line is required (a bundle job)
A job passes where all of these hold:
  Marker      the log has a `node score:` line of the arm's name, and every such line is the same
  Fallbacks   the log has no `uniform policy`, `steers off`, `bank not written` or `search failed` line
  Nodes       (parity) ns_check nodes at least 500 and differ 0
  Picks       (parity) ns_check openings at least 50 and open_differ 0
  Errors      ns_errors 0
  Cost        (pod only) the mean of ns_ms at most 24 and its q99 at most 60
  Proc        every line of the picks file and of the cover file has proc, and every cover line has node
  Uses        over the picks file, the picks that the bank's lineage keeps give each node the uses that the bank holds
The mean and q99 of ns_ms are printed for every job. The exit status is 1 where a job fails.
"""
import collections
import glob
import json
import os
import pickle
import re
import sys

import numpy as np

MIN_NODES, MIN_OPENINGS = 500, 50
COST_MEAN_MS, COST_Q99_MS = 24, 60
FALLBACKS = ('uniform policy', 'steers off', 'bank not written', 'search failed')  # `search failed` is in the worker's line `pool clauses: draws, search failed:`
ARM_NAME = (('parity', 'ship'), ('mt', 'mt'), ('depth', 'depth'))
SAFE_MODULES = {'builtins', 'collections', 'copyreg', '_codecs', 'numpy', 'datetime'}


class Stub:
    """Stands for a class of the engine or the sampler, so that a bank file loads with no engine."""

    def __init__(self, *args, **kwargs):
        pass

    def __setstate__(self, state):
        if isinstance(state, dict):
            self.__dict__.update(state)
        else:
            self.__dict__['state'] = state


class BankLoader(pickle.Unpickler):
    def find_class(self, module, name):
        if module.split('.')[0] in SAFE_MODULES:
            return super().find_class(module, name)
        return Stub


def load_bank(path):
    with open(path, 'rb') as f:
        return BankLoader(f).load()


def job_folders(out):
    """[(arm, task, folder)] of the jobs under out, sorted."""
    if os.path.isdir(out + '/out'):
        out += '/out'
    return sorted((d.split('/')[-2], d.split('/')[-1], d) for d in glob.glob(out + '/*/*') if os.path.isdir(d + '/work'))


def read_lines(path):
    """The JSON lines of a file, [] where it is missing. A line that does not parse is left out."""
    got = []
    if os.path.exists(path):
        for line in open(path, errors='replace'):
            try:
                got.append(json.loads(line))
            except ValueError:
                pass
    return got


def kept_picks(lineage, lines):
    """The picks lines that the bank holds: for each lineage entry in order, the lines of its process with seq below its picks1, in seq order."""
    by_proc = collections.defaultdict(list)
    for x in lines:
        by_proc[x['proc']].append(x)
    kept = []
    for entry in lineage:
        kept += sorted((x for x in by_proc.get(entry['proc'], ()) if x['seq'] < entry['picks1']), key=lambda x: x['seq'])
    return kept


def uses_check(bank, picks_lines):
    """(kept picks, nodes whose count of picks differs from the bank's uses)."""
    kept = kept_picks(bank.get('lineage', []), picks_lines)
    count = collections.Counter(n for x in kept for n in x['picks'])
    uses = bank['policy']['uses']
    return kept, sum(count.get(n, 0) != u for n, u in uses.items()) + sum(n not in uses for n in count)


def expected_name(arm):
    return next((name for prefix, name in ARM_NAME if arm.startswith(prefix)), None)


def check_job(arm, task, folder, where):
    """(list of (item, ok, text)) for one job."""
    work = '%s/work/%s' % (folder, task)
    items = []

    def item(name, ok, text=''):
        items.append((name, bool(ok), text))
    log = open(work + '.log', errors='replace').read() if os.path.exists(work + '.log') else ''
    markers = sorted(set(re.findall(r'^node score: .*$', log, re.M)))
    want = expected_name(arm)
    if want is None:
        item('Marker', not markers, 'no node score line' if not markers else markers[0])
    else:
        fields = [dict(kv.split('=', 1) for kv in m[len('node score: '):].split()) for m in markers]
        parity = want == 'ship'
        ok = len(markers) == 1 and fields[0].get('name') == want and fields[0].get('fold') == '0' and fields[0].get('check') == ('1' if parity else '0')
        item('Marker', ok, markers[0] if len(markers) == 1 else '%d distinct lines: %s' % (len(markers), markers[:2]))
    found = [f for f in FALLBACKS if f in log]
    item('Fallbacks', not found, ', '.join(found) if found else 'none')
    if not os.path.exists(work + '.out.jsonl.bank'):
        item('Bank', False, 'no bank file')
        return items
    bank = load_bank(work + '.out.jsonl.bank')
    policy = bank['policy']
    if want is not None:
        errors, ms = policy.get('ns_errors'), policy.get('ns_ms') or [float('nan')]
        mean, q99 = float(np.mean(ms)), float(np.quantile(ms, .99))
        if want == 'ship':
            c = policy.get('ns_check') or {}
            item('Nodes', c.get('nodes', 0) >= MIN_NODES and c.get('differ', 1) == 0, 'nodes %s differ %s max_abs %s' % (c.get('nodes'), c.get('differ'), c.get('max_abs')))
            item('Picks', c.get('openings', 0) >= MIN_OPENINGS and c.get('open_differ', 1) == 0, 'openings %s open_differ %s' % (c.get('openings'), c.get('open_differ')))
            if c.get('differ') or c.get('open_differ'):
                first = next((n for n in policy['ids'] if policy['ns_alt'][n] != policy['score'][n]), None)
                if first is not None:
                    print('  first differing node %s: hand %r, node score %r' % (first, policy['ns_alt'][first], policy['score'][first]))
                if c.get('first_open_diff'):
                    print('  first differing opening: %s' % c['first_open_diff'])
        item('Errors', errors == 0, 'ns_errors %s' % errors)
        item('Cost', where != 'pod' or (mean <= COST_MEAN_MS and q99 <= COST_Q99_MS), 'ns_ms mean %.2f q99 %.2f over %d nodes%s' % (
            mean, q99, len(ms), '' if where == 'pod' else ' (budget applies on the pod)'))
    picks, cover = read_lines(work + '.out.jsonl.picks'), read_lines(work + '.out.jsonl.cover')
    item('Proc', all('proc' in x for x in picks + cover) and all('node' in x for x in cover), '%d picks lines, %d cover lines with proc' % (len(picks), len(cover)))
    kept, differ = uses_check(bank, picks)
    item('Uses', differ == 0, '%d picks kept, %d of %d nodes differ' % (len(kept), differ, len(policy['uses'])))
    lineage = bank.get('lineage', [])
    item('Lineage', bool(lineage) and all('proc' in e for e in lineage), '%d processes' % len(lineage))
    return items


def main():
    out = sys.argv[1]
    where = sys.argv[2] if len(sys.argv) > 2 else 'mac'
    failed = 0
    jobs = job_folders(out)
    for arm, task, folder in jobs:
        items = check_job(arm, task, folder, where)
        bad = [n for n, ok, _ in items if not ok]
        failed += bool(bad)
        print('%s/%s: %s' % (arm, task, 'PASS' if not bad else 'FAIL ' + ' '.join(bad)))
        for n, ok, text in items:
            print('  %-9s %s %s' % (n, 'ok  ' if ok else 'FAIL', text))
    print('jobs %d, failed %d' % (len(jobs), failed))
    sys.exit(1 if failed or not jobs else 0)


if __name__ == '__main__':
    main()
