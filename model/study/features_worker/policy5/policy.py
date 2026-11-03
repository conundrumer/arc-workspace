"""The scored pool policy: Policy(task), add(node), scope(k, rng). No gold reaches it.

A node is scored once, when it is new. A scope takes three quarters of its picks by score, drawn without replacement with weights e^score, where
each earlier use of a node takes 1 off its score. The rest are the oldest nodes among the least used. The model is the fold that did not train on
the task.
"""
import hashlib
import json
import math
import os
import pickle
import sys

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/policy5'  # the data folder
sys.path.insert(0, HERE)
import numpy as np  # noqa: E402
from nodefeat import Pair, features  # noqa: E402
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/model/study/policy')
from outfeat import link_one, out_features  # noqa: E402

USES = float(os.environ.get('POLICY_USES', 1))  # score taken off per earlier use of a node
MODEL = os.environ.get('POLICY_MODEL', HERE + '/policy_model.pkl')
BUNDLE = None


def task_key(task):
    return hashlib.sha1(json.dumps(task['train'], sort_keys=True).encode()).hexdigest()


def bundle():
    global BUNDLE
    if BUNDLE is None:
        BUNDLE = pickle.load(open(MODEL, 'rb'))
    return BUNDLE


class Policy:
    def __init__(self, task):
        b = bundle()
        self.names, self.ix = b['names'], {n: i for i, n in enumerate(b['names'])}
        key = task_key(task)
        self.model = next((m for trained, m in b['folds'] if key not in trained), b['folds'][0][1])
        self.pairs = [Pair(p['input'], p['output']) for p in task['train']]
        self.nodes, self.score, self.uses, self.ids = {}, {}, {}, []

    def row(self, node):
        return dict(types=node.types, table_types=node.table_types, arity=node.arity, depth=node.depth, parents=node.parents, clause=node.clause,
                    n_clauses=1, x_rows=node.rows, examples=node.examples)

    def feats(self, node):
        r = self.row(node)
        d = features(r, self.pairs)
        o, s = out_features(r, self.pairs)
        d.update(o)
        link_one(node.parents, d, s, self.nodes)
        self.nodes[node.id] = (node.parents, d, s)
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

    def scope(self, k, rng):
        if not self.ids:
            return []
        keys = {i: self.score[i] - USES * self.uses[i] - math.log(-math.log(rng.random() or 1e-12)) for i in self.ids}
        best = sorted(self.ids, key=lambda i: -keys[i])[:max(1, k - k // 4)]
        rest = sorted((i for i in self.ids if i not in best), key=lambda i: (self.uses[i], i))[:k - len(best)]
        for i in best + rest:
            self.uses[i] += 1
        return best + rest
