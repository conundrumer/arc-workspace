"""The scored pool policy: Policy(task), add(node), scope(k, rng). No gold reaches it.

A pick chooses a depth first, by SHARE, then the best node of that depth. A node is scored once, when it is new, from base table features and the families link.carry, link.join and out.code, where `available` is the node's own ancestors. A scope takes three quarters
of its picks by score, drawn without replacement with weights e^score, where each earlier use of a node takes 1 off its score. The rest are the oldest nodes among the least used. The model is
the fold that did not train on the task.
"""
import hashlib
import json
import math
import os
import pickle
import sys

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/policy4'  # the data folder
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
import families  # noqa: E402
from nodefeat import Pair, features  # noqa: E402

MODEL = os.environ.get('POLICY_MODEL', HERE + '/policy_model.pkl')
SHARE = {int(k): v for k, v in json.load(open(HERE + '/levels.json')).items()}  # share of picks per depth, from the depth of the node each gold form reads
USE = {('output_coding', 'ha'), ('link_columns', 'hc_carry'), ('link_structure', 'hd')}
BUNDLE = FNS = None


def task_key(task):
    return hashlib.sha1(json.dumps(task['train'], sort_keys=True).encode()).hexdigest()


def bundle():
    global BUNDLE, FNS
    if BUNDLE is None:
        BUNDLE = pickle.load(open(MODEL, 'rb'))
        FNS = {k: v for k, v in families.load().items() if k in USE}
    return BUNDLE


def ancestors(parents, by):
    seen, todo = {}, list(parents)
    while todo:
        p = todo.pop()
        if p in by and p not in seen:
            seen[p] = by[p]
            todo += by[p]['parents']
    return seen


class Policy:
    def __init__(self, task):
        b = bundle()
        self.names, self.ix = b['names'], {n: i for i, n in enumerate(b['names'])}
        key = task_key(task)
        self.model = next((m for trained, m in b['folds'] if key not in trained), b['folds'][0][1])
        self.train, self.test = task['train'], [p['input'] for p in task['test']]
        self.pairs = [Pair(p['input'], p['output']) for p in task['train']]
        self.by, self.score, self.uses, self.ids, self.level = {}, {}, {}, [], {}

    def feats(self, node):
        n = dict(token=str(node.id), types=node.types, table_types=node.table_types, arity=node.arity, examples=node.examples, parents=[str(p) for p in node.parents], x_rows=node.rows)
        self.by[n['token']] = n
        d = features(dict(n, depth=0, clause='', n_clauses=1), self.pairs)
        a = ancestors(n['parents'], self.by)
        c = dict(train=self.train, test=self.test, available=list(a.values()), by_token={**a, n['token']: n})
        for (mod, name), fn in FNS.items():
            d.update(families.rename(mod, name, fn(n, c)))
        return d

    def add(self, node):
        if node.id in self.score:
            return
        d = self.feats(node)
        x = np.full((1, len(self.names)), np.nan, np.float32)
        for k, v in d.items():
            if k in self.ix:
                x[0, self.ix[k]] = v
        self.score[node.id] = float(self.model.decision_function(x)[0])
        self.uses[node.id] = 0
        self.ids.append(node.id)
        self.level.setdefault(node.depth, []).append(node.id)

    def scope(self, k, rng):
        if not self.ids:
            return []
        keys = {i: self.score[i] - self.uses[i] - math.log(-math.log(rng.random() or 1e-12)) for i in self.ids}
        best = []
        for _ in range(max(1, k - k // 4)):
            left = [d for d, ids in self.level.items() if any(i not in best for i in ids)]
            if not left:
                break
            d = rng.choices(left, weights=[SHARE.get(d, min(SHARE.values())) for d in left])[0]
            best.append(max((i for i in self.level[d] if i not in best), key=lambda i: keys[i]))
        rest = sorted((i for i in self.ids if i not in best), key=lambda i: (self.uses[i], i))[:k - len(best)]
        for i in best + rest:
            self.uses[i] += 1
        return best + rest
