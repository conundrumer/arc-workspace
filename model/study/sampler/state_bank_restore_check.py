"""Checks that a truncated bank, an older visited-set schema and a visited set with an unknown query each leave the state search empty with no raise.

    PYTHONPATH=<kit sampler>:<site> python bank_restore_check.py BANK SCRATCH_DIR
"""
import collections
import copy
import os
import pickle
import sys
import types

bank, tmp = sys.argv[1:3]
os.environ.setdefault('POOL_CLAUSES', 'state')
import kaggle_worker as KW
import state_search as SS


class Pool:
    def __init__(self):
        self.forms, self.nodes, self.draws, self.lineage = {}, {}, 0, []
        self.policy = types.SimpleNamespace()
        self.states, self.state_ids, self.frontier, self.expanded = {}, {}, [], 0
        self.run = types.SimpleNamespace(c=collections.Counter())

    def rebuild_maps(self):
        pass

    bank_restore = SS.bank_restore


data = open(bank, 'rb').read()
cases = []

p = Pool()
cut = os.path.join(tmp, 'truncated.bank')
open(cut, 'wb').write(data[:len(data) // 2])
got = KW.read_bank(cut, p)
cases.append(('truncated bank', got == (0, 0) and not p.states and not p.forms))

state = pickle.loads(data)
p = Pool()
p.forms = state['forms']
p.bank_restore(state)
cases.append(('current schema restores', len(p.states) == len(state['state_search']['states']) and p.expanded == state['state_search']['expanded']))

old = copy.deepcopy(state)
old['state_search']['v'] = SS.SCHEMA - 1
p = Pool()
p.forms = old['forms']
p.bank_restore(old)
cases.append(('older schema starts empty', not p.states and p.expanded == 0 and p.run.c['state:visited set not read'] == 1))

bad = copy.deepcopy(state)
bad['state_search']['states'][-1][1] = [10 ** 9]
p = Pool()
p.forms = bad['forms']
p.bank_restore(bad)
cases.append(('unknown query starts empty', not p.states and p.run.c['state:visited set not read'] == 1))

short = copy.deepcopy(state)
short['state_search']['states'][0] = short['state_search']['states'][0][:3]
p = Pool()
p.forms = short['forms']
p.bank_restore(short)
cases.append(('short state row starts empty', not p.states and p.run.c['state:visited set not read'] == 1))

for name, ok in cases:
    print('PASS' if ok else 'FAIL', name)
print('summary: %d of %d cases pass' % (sum(ok for _, ok in cases), len(cases)))
