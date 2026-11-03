"""One run loaded for the read: arrays over nodes, forms with births and keys, reader edges by birth, clock, covers and gold labels.

  R = poolrun.Run(which, arm, task)
"""
import bisect, collections, json, os, sys
import numpy as np
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop')
import common2 as C2

C = C2.C
INF = 1 << 60


class Run:
    def __init__(self, which, arm, task, labels=True):
        S = C2.SETS[which]
        self.which, self.arm, self.task, self.S = which, arm, task, S
        self.dir = C.run_dir(S['root'], arm, task)
        st = self.st = C.bank(self.dir + 'work/' + task + '.out.jsonl.bank')
        self.forms, self.nodes, self.pol = st['forms'], st['nodes'], st['policy']
        forms, nodes = self.forms, self.nodes
        self.ids = sorted(nodes)
        assert self.ids == list(range(len(self.ids)))
        self.n = len(self.ids)
        self.age = np.array([nodes[i].age for i in self.ids], np.int64)
        assert (np.diff(self.age) >= 0).all()
        self.nform = np.array([nodes[i].form for i in self.ids], np.int64)
        self.score = np.array([self.pol['score'][i] for i in self.ids], np.float64)
        self.uses_end = np.array([self.pol['uses'].get(i, 0) for i in self.ids], np.int64)
        self.tid_of, self.pairs = C2.table_ids(nodes)
        self.tid = np.array([self.tid_of[i] for i in self.ids], np.int64)
        self.ntab = len(self.pairs)
        self.kind = {f: forms[f].kind for f in forms}
        self.fdepth = {f: forms[f].depth for f in forms}
        self.parents = {f: sorted(set(forms[f].parents)) for f in forms}
        self.fnodes = {f: list(forms[f].nodes) for f in forms}
        self.birth = {f: (min(nodes[n].age for n in forms[f].nodes) if forms[f].nodes else INF) for f in forms}
        self.fkey = {f: tuple(sorted({self.tid_of[n] for n in forms[f].nodes})) for f in forms}
        self.fkeyset = {f: set(k) for f, k in self.fkey.items()}
        self.edges = sorted((self.birth[g], g, p) for g in forms for p in self.parents[g] if self.birth[g] < INF)
        self.edge_births = [e[0] for e in self.edges]
        self.clk = C2.clock(S['root'], arm, task)
        self.draws = st['draws']
        vs = self.clk['visits']
        self.visits = vs
        self.vends = [v['d1'] for v in vs]
        self.opens = [v for v in vs if not v['resume'] and v['d0'] < self.draws]
        if labels:
            self.cs = C2.covers(which, arm, task, st)
            self.lab = C2.labels(which, task, self.cs)
            lab = self.lab
            self.q_of_pair = collections.defaultdict(list)
            for q, ts in lab['tables'].items():
                for s in ts:
                    self.q_of_pair[s].append(q)
            self.gold_form = {}
            for f in forms:
                self.gold_form[f] = any(self.pairs[t] in self.q_of_pair for t in self.fkey[f])

    # ---- cuts
    def cut_draw(self, seconds):
        """(draw, true second) of a cut: the last write for a cut at or past the last write's second, else the rebuilt draw."""
        end_d, end_t = C2.draw_at_end(self.clk, self.draws)
        if seconds >= end_t - 1e-9 or (self.which == 'base'):
            return end_d, end_t, 'last write'
        d, t = C2.draw_at(self.clk, seconds, self.draws)
        return d, t, 'rebuilt'

    def covered(self, h, d):
        f = self.lab['first'].get(h)
        return f is not None and f <= d

    def table_label(self, pair, d):
        """(any_read, open_read, ready_read, open_nondet, ready_nondet) of a table pair at draw d."""
        lab = self.lab
        qs = self.q_of_pair.get(pair)
        if not qs:
            return 0, 0, 0, 0, 0
        anyr = op = rd = opn = rdn = 0
        for q in qs:
            for h in lab['readers'].get(q, ()):
                anyr = 1
                if self.covered(h, d):
                    continue
                op = 1
                ready = all(self.covered(r, d) for r in lab['reads'][h])
                nd = lab['kinds'][h] != 'DET'
                rd |= ready
                opn |= nd
                rdn |= ready and nd
        return anyr, op, int(rd), opn, int(rdn)
