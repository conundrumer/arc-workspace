#!/usr/bin/env python
"""Gold's clause through the live walk (live.py) with every choice taken to be gold's: its q by part, in bits.

  <runtime python> or_q.py STEMS OUT.json [--steers struct,tilt,rel,choice] [--set NAME=value ...]

STEMS is a stems file of search_gold.py. A point's record in OUT.json has `parts` (bits by part: the OR taken or not, the branch count, the
relation and the rest of each atom by place, the stops, the link coins), `total`, `atoms` (place, text, bits), `bad` (a choice to which the walk
gives gold chance 0) and `dead` (a gate or a refusal that ends gold's path). Gold's atoms are forced through Drawer.atom with the steers and the
join coin on, as S.gold_q does, and each rng call of the walk takes gold's side. The bits are those of gold's written atom order and of the first
try of each choice, as the search counts a path. A coin is told from the line of live.py that makes it, so a change to those lines needs a change
here. `--set` replaces a number in live.py before the run (for example MIRROR_NOT=0.8).

The kind of the clause is that of gold's form, RULE or INIT. An INIT has the parts of Run.init: the component, the keyed coin, the key's count of
labels and which labels, then for each port its skip coin, its head columns (bound, names a key label, reads no key, count of labels, which labels)
and its body, whose atoms and stops are in the parts `key ...` and `port ...` (`outside ...` for a port that comes again after the key group).
The head columns follow the body in gold's tokens, and the walk draws them before the body, so Guide.look reads a port's head from gold ahead of
the walk. Where the walk cannot take gold's side, `bad` says so and the chance is left out: a walk that cannot go on ends with `bad` and no `dead`.
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
SKIP = live.SKIP_TOK


def bits(p):
    return -math.log(p) / L2 if p > 0 else math.inf


class Stuck(Exception):
    """The walk cannot take gold's side at a choice, and cannot go on: `bad` says why."""


class Guide(search.Chooser):
    """The rng of a Run that takes gold's side at every choice and adds the bits of each to a part. rest holds gold's tokens that the walk
    has not taken: an atom takes its own from the front, and the OR, ALSO and END tokens go where the walk steps them. In an INIT, the
    SKIP tokens go at the skip coins, and the END and the head of a port go when the walk leaves the port."""

    def __init__(self, run, rest, kind='RULE'):
        self.run, self.rest, self.kind = run, rest, kind
        self.parts, self.counts, self.bad, self.atoms = collections.Counter(), collections.Counter(), [], []
        self.hash, self.or_next, self.ctx = 0, False, 'top'
        self.levels = []  # one count of the branches so far, for each OR being drawn
        self.neg_idx = self.neg_toks = None
        self.cur = collections.Counter()
        self.where = ''  # in an INIT, the body that the walk is in ('key ', 'port ' or 'outside '), in front of the names of its parts
        self.carets = set()  # in an INIT, the numbers of the key's labels that gold marks with a caret
        self.port = None  # in an INIT, gold's port that the walk is in: see look

    def start(self, path):
        pass

    def stuck(self, why):
        self.bad.append(why)
        raise Stuck(why)

    def more(self):
        """Whether the body that the walk is in goes on in gold: an INIT body ends at its END."""
        return bool(self.rest) and not (self.kind == 'INIT' and self.rest[0] == M.END)

    def extent(self, toks):
        """The index in toks of the END that closes the body at the front of toks, or None. An OR takes an END, an ALL takes two, and a
        column followed by a column opens a record site, which an END closes."""
        V, stack, prev = self.run.V, [], None
        all_tok = V.id('ALL')
        for i, t in enumerate(toks):
            if t == M.END:
                if not stack:
                    return i
                stack.pop()
            elif t == M.OR:
                stack.append('OR')
            elif t == all_tok:
                stack += ['ALL', 'ALL']
            elif prev is not None and V.kind(t) == 'column' and V.kind(prev) == 'column':
                stack.append('REC')
            prev = t
        return None

    def key_group(self):
        """The numbers of the labels that carry a caret in gold's key group, which is at the front of rest. The key body is drawn with stars
        and the walk marks the keys after it, so each caret in rest becomes a star."""
        end = self.extent(list(self.rest))
        if end is None:
            self.stuck('the key group has no END')
        n, carets = 0, set()
        for i in range(end):
            if self.rest[i] in (M.STAR, M.CARET):
                if self.rest[i] == M.CARET:
                    carets.add(n)
                    self.rest[i] = M.STAR
                n += 1
        return carets

    def look(self, cols, keys):
        """Gold's port at the front of rest, for the coins of Run.port that come before its body: its head, a label tokens list for each of cols
        (None for a column that gold leaves unbound), and whether its body reads a label of keys. left is the count of the tokens of rest
        after the port, so that the body's END and the head are the tokens of rest between the body's atoms and those."""
        toks, V = list(self.rest), self.run.V
        end = self.extent(toks)
        if end is None:
            self.stuck('the port has no END')
        pos, heads = end + 1, []
        try:
            for _ in cols:
                if toks[pos] == M.END:
                    heads.append(None)
                    pos += 1
                elif V.kind(toks[pos]) == 'column':  # a record: each field's column token, then its label, then two END
                    labs = []
                    while toks[pos] != M.END:
                        if toks[pos] != self.run.ff0.col_by_pos[len(labs)]:
                            self.bad.append('head record: the fields are not in the order of the columns')
                        labs.append(toks[pos + 1])
                        pos += 2
                    if len(labs) == 1 or toks[pos + 1] != M.END:
                        self.bad.append('head record of %d fields' % len(labs))
                    heads.append(labs)
                    pos += 2
                else:
                    heads.append([toks[pos]])
                    pos += 2
        except IndexError:
            self.stuck('the head of the port runs past the end of gold')
        return dict(cols=[c for c, _ in cols], heads=heads, hcols=[i for i, h in enumerate(heads) if h], hc=-1, gold=None, keys=keys,
                    reads=any(t in keys for t in toks[:end]), left=len(toks) - pos)

    def outside_loop(self, fr):
        """Whether the coin at frame fr is in the loop over the ports that the key group skipped."""
        n = fr.f_lineno
        while n > 0:
            s = linecache.getline(fr.f_code.co_filename, n).strip()
            if s.startswith('for name, cols in'):
                return ' left' in s
            n -= 1
        return False

    def add(self, name, p):
        b = bits(p)
        if b == math.inf:
            self.bad.append(name)
            return
        self.parts[name] += b
        self.counts[name] += 1

    def scan(self):
        """Yields (token, depth) over rest up to the END that closes the construct that the walk is in. An END also closes a record site,
        which a column followed by a column opens, and an ALL takes two."""
        V, stack, prev = self.run.V, [], None
        all_tok = V.id('ALL')
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
                if t == all_tok:
                    stack += ['ALL', 'ALL']
                elif prev is not None and V.kind(t) == 'column' and V.kind(prev) == 'column':
                    stack.append('REC')
                yield t, len(stack)
            prev = t

    def coin(self, p):
        fr = sys._getframe(2)
        line = linecache.getline(fr.f_code.co_filename, fr.f_lineno).strip()
        loc = fr.f_locals
        pre, pop = self.where, None  # pre goes in front of the name of a part; pop is the value of the coin at which the coin takes gold's SKIP
        if 'p_or(' in line:
            r = bool(self.rest) and self.rest[0] == M.OR
            name = 'or:take' if r else 'top:no OR'
        elif "orc['after']" in line:  # the code reads `random() >= after`, which is a stop where the coin is False
            r = self.more()
            name = 'or:after'
        elif "pri['det']['proposer']" in line:
            r = bool(self.rest) and self.run.V.name(self.rest[0]) in self.run.pri['proposers']
            name = 'proposer or atoms'
        elif 'random() < chance' in line:
            r = not self.more()
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
        elif 'PORT_LONG' in line:  # the body is at an atom past PORT_SHORT, so gold has one
            r = True
            name = 'long body'
        elif 'KEY_ALL' in line:  # gold stops with a key unread
            r = False
            name = 'key partly read'
        elif "pri['keyed'][comp]" in line:
            r = bool(self.rest) and self.rest[0] != SKIP
            pre, name, pop = '', 'keyed', False
        elif 'f.admits([SKIP_TOK])' in line:  # a port's coin: taken or skipped
            r = not (self.rest and self.rest[0] == SKIP)
            pre, name, pop = '', 'outside: taken or skipped' if self.outside_loop(fr) else 'port: taken or skipped', False
        elif 'heads.get(' in line:
            r = self.port['heads'][self.port['cols'].index(loc['c'])] is not None
            pre, name = '', 'head: bound'
        elif "hk['key'" in line:
            head = self.port['heads'][self.port['cols'].index(loc['c'])]
            r = head is not None and head[0] in self.port['keys']
            pre, name = '', 'head: names a key label'
        elif "hk['unread']" in line:
            r = not self.port['reads']
            pre, name = '', 'head: body reads no key'
        else:
            raise RuntimeError('a coin that or_q.py does not know: ' + line)
        name = pre + name
        if p >= 1 or p <= 0:
            if r != (p >= 1):
                self.bad.append('%s (chance %d, gold goes the other way)' % (name, p >= 1))
                if self.kind == 'INIT':
                    raise Stuck(name)
            r = p >= 1
        else:
            self.add(name, p if r else 1 - p)
        if pop is r and self.rest:
            self.rest.popleft()
        return r

    def choices(self, population, weights=None, k=1):
        """The count of an OR's branches; in a DET the proposer; in an INIT also the component, the key's count of labels and a head column's count of labels."""
        fr = sys._getframe(2)
        who, line = fr.f_code.co_name, linecache.getline(fr.f_code.co_filename, fr.f_lineno).strip()
        population = list(population)
        if who == 'or_form':
            assert self.rest and self.rest[0] == M.OR, 'a branch count with no OR next: %s' % [self.run.V.name(t) for t in list(self.rest)[:6]]
            self.rest.popleft()
            n = 1 + sum(1 for t, d in self.scan() if t == ALSO_TOK and d == 0)
            name = self.where + 'or:branches'
            if n not in population:
                self.bad.append('%s %d not in the shapes' % (name, n))
                return [population[0]]
            self.levels.append(0)
        elif who == 'det':
            n = self.run.V.name(self.rest[0]) if self.rest else None
            name = 'proposer'
            if n not in population:
                self.stuck('proposer %s is not among those that the walk draws' % n)
            self.rest.popleft()
        elif who == 'init' and 'comp = self.pick' in line:
            n = self.run.V.name(self.rest[0]) if self.rest else None
            name = 'component'
            if n not in population:
                self.stuck('component %s is not among those that the walk draws' % n)
            self.rest.popleft()
        elif who == 'init' and 'key_labels' in line:
            self.carets = self.key_group()
            n = len(self.carets)
            name = 'key: count of labels'
            if n not in population:
                self.stuck('key: %d labels are not among the counts that the priors have' % n)
        elif who == 'record_size':
            head = self.port['heads'][self.port['cols'].index(fr.f_locals['c'])]
            n = len(head) if head else None
            name = 'head: count of labels'
            if n not in population:
                self.bad.append('%s %s is not among the sizes that the priors have' % (name, n))
                return [population[0]]
        else:
            raise RuntimeError('a pick that or_q.py does not know: ' + line)
        self.add(name, weights[population.index(n)] / sum(weights))
        return [n]

    def randrange(self, n):
        """The else negation's pick among the first branch's atoms."""
        for _ in range(self.neg_toks):
            self.rest.popleft()
        self.add(self.where + 'br:else-NOT pick', 1.0 / n)
        return self.neg_idx

    def pick(self, opts, weights):
        raise RuntimeError('pick')

    def choice(self, seq):
        """A label of a head column: the walk takes one of the labels that the decoder admits, each with the same chance."""
        fr = sys._getframe(1)
        if fr.f_code.co_name != 'head_column':
            raise RuntimeError('a choice that or_q.py does not know: ' + linecache.getline(fr.f_code.co_filename, fr.f_lineno).strip())
        j, n, port = fr.f_locals['j'], fr.f_locals['n'], self.port
        if j == 0:  # the head column that the walk binds next is gold's next bound one
            port['hc'] += 1
            if port['hc'] >= len(port['hcols']):
                self.stuck('head: the walk binds a column that gold leaves unbound')
            port['gold'] = port['heads'][port['hcols'][port['hc']]]
            if n != len(port['gold']):
                self.bad.append('head: the walk takes %d labels for a column, gold %d' % (n, len(port['gold'])))
        if j >= len(port['gold']):
            self.stuck('head: gold has no label %d' % j)
        label = port['gold'][j]
        if label not in seq:
            self.bad.append('head: gold names label %s, which the walk cannot take' % self.run.V.name(label))
        elif len(seq) > 1:
            self.add('head: which label', 1.0 / len(seq))
        return label

    def sample(self, population, k):
        """The key's labels among the labels of a key group (in init), or among the labels that an OR's first branch makes (in or_form)."""
        who = sys._getframe(1).f_code.co_name
        population = list(population)
        if who == 'init':
            gold, name = sorted(self.carets), 'key: which labels'
            if len(gold) != k or not set(gold) <= set(population):
                self.stuck('key: the labels with a caret are %s, and the walk takes %d of %s' % (gold, k, population))
            if not self.rest or self.rest[0] != M.END:  # the walk steps the END of the key group next
                self.stuck('key: no END after the key group')
            self.rest.popleft()
        elif who == 'or_form':
            gold, name = [x for x in population if x in self.carets], self.where + 'key: which labels an OR exports'
            if len(gold) != k:
                self.bad.append('%s: the first branch makes %d keys, the walk takes %d' % (name, len(gold), k))
        else:
            raise RuntimeError('a sample that or_q.py does not know: ' + who)
        combos = math.comb(len(population), k)
        if combos > 1:
            self.add(name, 1.0 / combos)
        return gold

    def begin_port(self, cols, keys, outside):
        self.where = 'outside ' if outside else 'port '
        self.port = self.look(cols, keys)

    def end_port(self):
        """The walk is out of the port: the body's END and the head are not taken by any call, so they go here."""
        port = self.port
        extra = len(self.rest) - port['left']
        if extra < 0:
            self.stuck('port: the walk took more of gold than the port has')
        if port['hc'] + 1 != len(port['hcols']):
            self.bad.append('head: gold binds %d columns, the walk %d' % (len(port['hcols']), port['hc'] + 1))
        for _ in range(extra):
            self.rest.popleft()


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
        zero = [ph for ph, b in g.cur.items() if b == math.inf]
        if zero or total == math.inf:  # a pick that gives gold chance 0: the picks before it count, and the rest of the atom has no bits
            g.bad.append('%s atom has chance 0 at %s: %s' % (g.ctx, ', '.join(zero) or 'its mix', res[3]))
        for ph, b in g.cur.items():
            if b != math.inf:
                g.parts['%s atom: %s' % (g.ctx, ph)] += b
        if total != math.inf:
            g.parts['%s atom: column stops and join mix' % g.ctx] += total - sum(g.cur.values())
        g.atoms.append((g.ctx, res[3], None if total == math.inf else round(total, 2)))
        if g.kind == 'INIT' and any(ph.startswith('relation') for ph in zero):  # the atom's tokens are not the walk's, so the tokens after it are out of step
            raise Stuck(g.bad[-1])
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
        g.ctx = '%sbr%d%s' % (g.where, min(g.levels[-1], 2), ' nested' if nests == 0.0 and len(g.levels) > 1 else '')
        got = super().branch(dr, d, labs, pkey, k, scope, outer, exported, first, local, want, want_types, nests)
        if got[0] is not None:  # or_form steps the separator next
            if g.rest and g.rest[0] in SEP:
                g.rest.popleft()
            else:
                g.bad.append('branch end: gold has %s' % (g.rest[0] if g.rest else None))
        return got

    def drawer(self, pg, kind, dec, place=None):
        """In an INIT, the parts of a body's atoms are those of its place."""
        dr, g = super().drawer(pg, kind, dec, place), self.rng
        if kind == 'INIT':
            if place == 'key':
                g.where = 'key '
            g.ctx = g.where.strip()
        return dr

    def port(self, pg, f, comp, name, cols, params, nlab, keys, fields, outside=False):
        g = self.rng
        g.begin_port(cols, keys, outside)
        got = super().port(pg, f, comp, name, cols, params, nlab, keys, fields, outside)
        g.end_port()
        return got

    def stop_barred(self, dr, kind, k, top, nlab, toks, text, scope, need, keys):
        """A stop that a gate bars is no choice, so the body goes on; gold's body does not."""
        barred, g = super().stop_barred(dr, kind, k, top, nlab, toks, text, scope, need, keys), self.rng
        if barred and kind == 'INIT' and not g.more():
            why = [w for w, hit in (('a head column needs a type that no label of the body has', bool(need) and live.ANY_TYPE not in scope and any(not x & set(scope) for x in need)),
                                    ('the body has fewer labels than the head takes', nlab + toks.count(M.STAR) < dr.labs_wanted and k < top),
                                    ('the body reads no key', bool(keys) and not set(keys) & set(toks))) if hit]
            g.stuck('%sstop after atom %d is barred (%s), and gold stops' % (g.where, k, '; '.join(why)))
        return barred


def gold_rest(sess, scope, target, kind='RULE'):
    """The model tokens of the target of the kind, less its kind token and, for a RULE, its last END."""
    ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*scope, target, live.READER_OUT)), sess.settings).decode_stream()
    toks = [(t, p) for t, m, p in zip(ids, model, paths) if m and p[0] == len(scope)]
    assert toks[0][0] == live.KIND_TOK[kind]
    if kind == 'INIT':  # the form ends at its last port, with no END of its own
        return collections.deque(t for t, _ in toks[1:])
    assert toks[-1][0] == M.END and len(toks[-1][1]) == 1
    return collections.deque(t for t, _ in toks[1:-1])


def one(sampler, task, case, point, kind=None):
    """The record of the point's walk. kind is that of gold's clause, from its text where None."""
    d, lines = G.gold_of(task, case, point)
    scope, target = lines[:point[0]], lines[point[0]]
    kind = kind or target.split()[0].lstrip('(')
    sess, task_json, _ = live_try.session_of(task)
    run = GuidedRun(sampler.pri, sess, time.monotonic() + 120, task_json, live.Limits(form_tries=1))
    dec, pg = run.scope(scope)
    g = run.rng = Guide(run, gold_rest(sess, scope, target, kind), kind)
    dead = match = None
    try:
        f = run.form(pg, dec, kind)
        if kind == 'INIT':  # the walk steps the SKIP of each port that is left, and takes no call for it
            if all(t == SKIP for t in g.rest):
                g.rest.clear()
            match = search.clause_key(run.clause_of(scope, pg, f).text) == search.clause_key(target)
    except Stuck:
        pass
    except search.Dead as e:
        dead = 'Dead: %s' % e
    except Exception as e:  # noqa: BLE001
        dead = '%s: %s | %s' % (type(e).__name__, str(e)[:100], [k for k in run.c if k.startswith(('form:', 'try:', 'or:'))][:4])
    rec = dict(task=task, case=case, point=point, target=target, parts={k: round(v, 3) for k, v in sorted(g.parts.items())}, counts=dict(g.counts),
               total=round(sum(g.parts.values()), 2), bad=g.bad, dead=dead, left=len(g.rest), atoms=g.atoms)
    if kind == 'INIT':
        rec['match'] = match
    return rec


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
