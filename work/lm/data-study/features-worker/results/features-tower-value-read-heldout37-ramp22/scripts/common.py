"""Shared paths and readers of the tower value read. Run with the engine venv python (numpy, sklearn)."""
import collections
import json
import os
import pickle

REC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
R1 = DS + 'sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/'
N600 = DS + 'sampler/sampler-worker/sampler-pool-dag-nodes-train50-600s/out/nodes_s0/'
FEAT = DS + 'features-worker/results/features-node-score-refit-loop/'
N600_ROWS = FEAT + 'n600-rows/'
HELD37 = DS + 'sampler/sampler-worker/held/tasks.txt'
RAMP = DS + 'sampler/sampler-worker/held/ramp-fold.txt'
E99 = DS + 'features-worker/arm/eval-tasks.txt'
SAFE_MODULES = {'builtins', 'collections', 'copyreg', '_codecs', 'numpy', 'datetime'}


class Stub:
    def __init__(self, *a, **k):
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


def read_lines(path):
    got = []
    if os.path.exists(path):
        for line in open(path, errors='replace'):
            try:
                got.append(json.loads(line))
            except ValueError:
                pass
    return got


def words(path):
    return open(path).read().split()


def held_union():
    return set(words(HELD37)) | set(words(RAMP)) | set(words(E99))


def read_runs():
    """[(group, seed, task, base)]: base is the path stem of the job's files. group is '37' or 'ramp'."""
    m = json.load(open(R1 + 'manifest.json'))
    out = []
    for group, key in (('37', 'heldout37'), ('ramp', 'ramp22')):
        for seed in ('s0', 's1'):
            for t in m['task_set'][key]:
                out.append((group, seed, t, R1 + 'out/bundle_%s/%s/work/%s.out.jsonl' % (seed, t, t)))
    return out


PASS_R1 = DS + 'sampler/search-worker/runs/search-pass-r1-heldout37-ramp22-2seeds-600s-0729e4943/'


def pass_runs():
    """[(group, seed, task, base, arm)] of the ramp tasks in the arms bundle and pass of search-pass-r1 (88 runs). Stem of a run's rows: ARM_TASK_SEED."""
    m = json.load(open(R1 + 'manifest.json'))
    out = []
    for arm in ('bundle', 'pass'):
        for seed in ('s0', 's1'):
            for t in m['task_set']['ramp22']:
                out.append(('ramp', seed, t, PASS_R1 + 'out/%s_%s/%s/work/%s.out.jsonl' % (arm, seed, t, t), arm))
    return out


def fit_runs():
    held = held_union()
    ts = words(FEAT + 'n600-tasks.txt')
    assert not (set(ts) & held), 'a fit task is held'
    return [('fit', 's0', t, N600 + '%s/work/%s.out.jsonl' % (t, t)) for t in ts]


def tower(bank):
    """Facts from parents only. Returns ids (sorted), anc {id: frozenset of ancestor ids}, facts {name: {id: value}}."""
    nodes, forms = bank['nodes'], bank['forms']
    ids = sorted(nodes)
    anc = {}
    depth = {}
    kinds = {}
    ident = {}
    for n in ids:
        nd = nodes[n]
        a = set()
        d = 1
        for p in nd.parents:
            a.add(p)
            a |= anc[p]
            d = max(d, depth[p] + 1)
        anc[n] = frozenset(a)
        depth[n] = d
        kinds[n] = len({forms[nodes[x].form].kind for x in a})
        ident[n] = int(any('Ident' in nodes[x].table_types for x in a))
    facts = {
        't_depth': depth,
        't_n_parents': {n: len(nodes[n].parents) for n in ids},
        't_n_anc': {n: len(anc[n]) for n in ids},
        't_kinds_below': kinds,
        't_anc_ident': ident,
    }
    return ids, anc, facts


TOWER_NAMES = ['t_depth', 't_n_parents', 't_n_anc', 't_kinds_below', 't_anc_ident']
