#!/usr/bin/env python
"""Gold's clause through the live walk (live.py) with every choice taken to be gold's: its q by part, in bits.

  <runtime python> or_q.py STEMS OUT.json [--steers struct,tilt,rel,choice] [--set NAME=value ...]

STEMS is a stems file of search_gold.py. A point's record in OUT.json has `parts` (bits by part: the OR taken or not, the branch count, the
relation and the rest of each atom by place, the stops, the link coins), `total`, `atoms` (place, text, bits), `bad` (a choice to which the walk
gives gold chance 0) and `dead` (a gate or a refusal that ends gold's path). Gold's atoms are forced through Drawer.atom with the steers and the
join coin on, as S.gold_q does, and each rng call of the walk takes gold's side. The bits are those of gold's written atom order and of the first
try of each choice, as the search counts a path. A coin is told from the line of live.py that makes it, so a change to those lines needs a change
here. `--set` replaces a number in live.py before the run (for example MIRROR_NOT=0.8).
"""
import argparse
import collections
import json
import linecache
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import live  # noqa: E402
import live_try  # noqa: E402
import sampler_paths as P  # noqa: E402
import search  # noqa: E402
import search_gold as G  # noqa: E402
from live import ALSO_TOK, M, arclog  # noqa: E402

L2 = math.log(2)
SEP = (ALSO_TOK, M.END)


def bits(p):
    return -math.log(p) / L2 if p > 0 else math.inf


class Guide(search.Chooser):
    """The rng of a Run that takes gold's side at every choice and adds the bits of each to a part. rest holds gold's tokens that the walk
    has not taken: an atom takes its own from the front, and the OR, ALSO and END tokens go where the walk steps them."""

    def __init__(self, run, rest):
        self.run, self.rest = run, rest
        self.parts, self.counts, self.bad, self.atoms = collections.Counter(), collections.Counter(), [], []
        self.hash, self.or_next, self.ctx = 0, False, 'top'
        self.levels = []  # one count of the branches so far, for each OR being drawn
        self.neg_idx = self.neg_toks = None
        self.cur = collections.Counter()

    def start(self, path):
        pass

    def add(self, name, p):
        b = bits(p)
        if b == math.inf:
            self.bad.append(name)
            return
        self.parts[name] += b
        self.counts[name] += 1

    def scan(self):
        """Yields (token, depth) over rest up to the END that closes the construct that the walk is in. An END also closes a record site,
        which a column followed by a column opens."""
        V, stack, prev = self.run.V, [], None
        for t in self.rest:
            if t == M.OR:
                yield t, len(stack)
                stack.append('OR')
            elif t == M.END:
                if not stack:
                    return
                stack.pop()
                yield t, len(stack)
            else:
                if prev is not None and V.kind(t) == 'column' and V.kind(prev) == 'column':
                    stack.append('REC')
                yield t, len(stack)
            prev = t

    def coin(self, p):
        fr = sys._getframe(2)
        line = linecache.getline(fr.f_code.co_filename, fr.f_lineno).strip()
        loc = fr.f_locals
        if 'p_or(' in line:
            r = bool(self.rest) and self.rest[0] == M.OR
            name = 'or:take' if r else 'top:no OR'
        elif "orc['after']" in line:  # the code reads `random() >= after`, which is a stop where the coin is False
            r = bool(self.rest)
            name = 'or:after'
        elif 'random() < chance' in line:
            r = not self.rest
            name = 'top:stop'
        elif 'ELSE_NEG' in line:
            self.neg_idx = None
            for i, a in enumerate(loc['first']):
                got = self.run.negated(loc['d'], a, loc['local'])
                if got is not None and list(got[1]) == list(self.rest)[:len(got[1])]:
                    self.neg_idx, self.neg_toks = i, len(got[1])
                    break
            r = self.neg_idx is not None
            name = 'br:else-NOT coin'
        elif 'bool(nests)' in line:
            r = False
            for t, d in self.scan():
                if t == ALSO_TOK and d == 0:
                    break
                if t == M.OR and d == 0:
                    r = True
                    break
            name = 'br:nest coin'
        elif 'BIND_QUIT' in line:
            r = False
            name = 'br:bind quit'
        elif 'stop * soft' in line:
            nxt = self.rest[0] if self.rest else None
            r = nxt in SEP or (nxt == M.OR and bool(loc.get('opens')))
            name = 'br:stop' if r else 'br:go on'
        elif 'P_REEXPORT' in line:
            tok = self.run.ff0.label_tok[loc['x']]
            r = any(t == tok for t, d in self.scan())
            name = 'or:export coin'
        else:
            raise RuntimeError('a coin that or_q.py does not know: ' + line)
        if p >= 1 or p <= 0:
            if r != (p >= 1):
                self.bad.append('%s (chance %d, gold goes the other way)' % (name, p >= 1))
            return p >= 1
        self.add(name, p if r else 1 - p)
        return r

    def choices(self, population, weights=None, k=1):
        """The count of an OR's branches."""
        assert self.rest and self.rest[0] == M.OR, 'a branch count with no OR next: %s' % [self.run.V.name(t) for t in list(self.rest)[:6]]
        self.rest.popleft()
        n = 1 + sum(1 for t, d in self.scan() if t == ALSO_TOK and d == 0)
        if n not in population:
            self.bad.append('or:branches %d not in the shapes' % n)
            return [population[0]]
        self.add('or:branches', weights[list(population).index(n)] / sum(weights))
        self.levels.append(0)
        return [n]

    def randrange(self, n):
        """The else negation's pick among the first branch's atoms."""
        for _ in range(self.neg_toks):
            self.rest.popleft()
        self.add('br:else-NOT pick', 1.0 / n)
        return self.neg_idx

    def pick(self, opts, weights):
        raise RuntimeError('pick')

    def choice(self, seq):
        raise RuntimeError('choice')

    def sample(self, population, k):
        raise RuntimeError('sample')


class GuidedDrawer(search.SearchDrawer):
    def atom(self, fr, k, scope_types=(), key=()):
        g = self.rng
        self.force, self.gq, self.gq_rel = g.rest, True, []
        g.cur = collections.Counter()
        try:
            res, why = super().atom(fr, k, scope_types, key)
        finally:
            self.force, self.gq = None, False
        if res is None:
            g.bad.append('%s atom failed: %s' % (g.ctx, why))
            return res, why
        total = bits(math.exp(res[1])) if res[1] > -700 else math.inf
        for ph, b in g.cur.items():
            g.parts['%s atom: %s' % (g.ctx, ph)] += b
        g.parts['%s atom: column stops and join mix' % g.ctx] += total - sum(g.cur.values())
        g.atoms.append((g.ctx, res[3], round(total, 2)))
        return res, why

    def pick(self, opts, weights):
        o, q = super().pick(opts, weights)
        f = sys._getframe(1)
        while f is not None and f.f_code.co_name != 'atom':
            f = f.f_back
        ph = f.f_locals['n'].phase
        if ph in ('val', 'fval'):
            ph = 'value: label' if self.fr.KIND[o] == 'label' else 'value: other'
        elif ph in ('root', 'root2'):
            ph = 'relation' + (' (op)' if o == M.NOT or o in M.CMP else '')
        elif ph == 'cols':
            ph = 'column'
        self.rng.cur[ph] += bits(q)
        return o, q


class GuidedRun(search.SearchRun):
    drawer_class = GuidedDrawer

    def or_form(self, dr, dec, toks, text, scope, nlab, k, nested=False):
        g, saved = self.rng, self.rng.ctx
        try:
            return super().or_form(dr, dec, toks, text, scope, nlab, k, nested)
        finally:
            if g.levels:
                g.levels.pop()
            g.ctx = saved

    def branch(self, dr, d, labs, pkey, k, scope, outer, exported, first, local, want, want_types, nests=0.0):
        g = self.rng
        g.levels[-1] += 1
        g.ctx = 'br%d%s' % (min(g.levels[-1], 2), ' nested' if nests == 0.0 and len(g.levels) > 1 else '')
        got = super().branch(dr, d, labs, pkey, k, scope, outer, exported, first, local, want, want_types, nests)
        if got[0] is not None:  # or_form steps the separator next
            if g.rest and g.rest[0] in SEP:
                g.rest.popleft()
            else:
                g.bad.append('branch end: gold has %s' % (g.rest[0] if g.rest else None))
        return got


def gold_rest(sess, scope, target):
    """The model tokens of the RULE target, less its kind token and its last END."""
    ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*scope, target, live.READER_OUT)), sess.settings).decode_stream()
    toks = [(t, p) for t, m, p in zip(ids, model, paths) if m and p[0] == len(scope)]
    assert toks[0][0] == live.RULE_TOK and toks[-1][0] == M.END and len(toks[-1][1]) == 1
    return collections.deque(t for t, _ in toks[1:-1])


def one(sampler, task, case, point):
    d, lines = G.gold_of(task, case, point)
    scope, target = lines[:point[0]], lines[point[0]]
    sess, task_json, _ = live_try.session_of(task)
    run = GuidedRun(sampler.pri, sess, time.monotonic() + 120, task_json, live.Limits(form_tries=1))
    dec, pg = run.scope(scope)
    g = run.rng = Guide(run, gold_rest(sess, scope, target))
    dead = None
    try:
        run.form(pg, dec, 'RULE')
    except search.Dead as e:
        dead = 'Dead: %s' % e
    except Exception as e:  # noqa: BLE001
        dead = '%s: %s | %s' % (type(e).__name__, str(e)[:100], [k for k in run.c if k.startswith(('form:', 'try:', 'or:'))][:4])
    return dict(task=task, case=case, point=point, target=target, parts={k: round(v, 3) for k, v in sorted(g.parts.items())}, counts=dict(g.counts),
                total=round(sum(g.parts.values()), 2), bad=g.bad, dead=dead, left=len(g.rest), atoms=g.atoms)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stems')
    ap.add_argument('out')
    ap.add_argument('--steers', default=','.join(live.STEERS))
    ap.add_argument('--set', nargs='*', default=[], help='NAME=value: a number of live.py or search.py, replaced for the run')
    a = ap.parse_args()
    for kv in a.set:
        k, v = kv.split('=')
        setattr(search if hasattr(search, k) and not hasattr(live, k) else live, k, float(v))
    sampler = live.Sampler(P.SAMPLER_DATA + '/models', tuple(x for x in a.steers.split(',') if x))
    res = []
    for task, case, point in G.points(a.stems):
        t0 = time.time()
        try:
            r = one(sampler, task, case, point)
        except Exception as e:  # noqa: BLE001
            r = dict(task=task, case=case, point=point, error=repr(e))
        res.append(r)
        json.dump(res, open(a.out, 'w'))
        print('%s %s %s total %s bad %s dead %s (%.1fs, %d of ?)' % (task, case, point, r.get('total'), r.get('bad'), r.get('dead'), time.time() - t0, len(res)), flush=True)


if __name__ == '__main__':
    main()
