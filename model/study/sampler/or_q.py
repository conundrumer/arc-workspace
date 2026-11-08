#!/usr/bin/env python
"""Gold's clause through the live walk (live.py) with every choice taken to be gold's: its q by part, in bits, over the orders of the clause.

  <runtime python> or_q.py STEMS OUT.json [--steers struct,tilt,rel,choice] [--set NAME=value ...] [--order-cap N] [--order-budget N]

STEMS is a stems file of search_gold.py. A point's record in OUT.json has `total`, -log2 of the sum of the chances of the clause's valid orders; `parts` (bits by part: the OR
taken or not, the branch count, the relation and the rest of each atom by place, the stops, the link coins), the mean of each part over the orders, weighted by each order's chance,
with the part ORDER_PART that makes the parts sum to `total`; `atoms` (place in the form, text with no label marks, bits), one row per atom, each the same mean, sorted by place and
text; `detail`, likewise; `bad` (a choice to which the walk gives gold chance 0) and `dead` (a gate or a refusal that ends gold's path), of the written order where no order is valid;
`orders`, how the orders were taken (see form_orders.sum_orders, and `walk`); and `fell_back` (what the priors lack and the walk went on without, see Guide).
Gold's atoms are forced through Drawer.atom with the steers and the join coin on, as S.gold_q does, and each rng call of the walk takes gold's side. Each order's bits are those of the
first try of each choice, as the search counts a path. With UNREAD_BETA, a relation pick raises the forms that no form of the scope reads (live.unread_forms).
A coin is told from the line of live.py that makes it, so a change to those lines needs a change
here. `--set` replaces a number in live.py before the run (for example MIRROR_NOT=0.8).

The kind of the clause is that of gold's form, RULE or INIT. An INIT has the parts of Run.init: the component, the keyed coin, the key's count of
labels and which labels, then for each port its skip coin, its head columns (bound, names a key label, reads no key, count of labels, which labels)
and its body, whose atoms and stops are in the parts `key ...` and `port ...` (`outside ...` for a port that comes again after the key group).
The head columns follow the body in gold's tokens, and the walk draws them before the body, so Guide.look reads a port's head from gold ahead of
the walk. Where the walk collects rows (Guide.rows), a key pick adds a row `keypick`, the type sets of the labels offered and of those taken (key_type_counts.py counts them). Where the walk cannot take gold's side, `bad` says so and the chance is left out: a walk that cannot go on ends with `bad` and no `dead`.
"""
import argparse
import collections
import itertools
import json
import linecache
import math
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import body_order  # noqa: E402
import form_orders as O  # noqa: E402
import live  # noqa: E402
import live_try  # noqa: E402
import sampler_paths as P  # noqa: E402
import search  # noqa: E402
import search_gold as G  # noqa: E402
from live import ALSO_TOK, M, arclog  # noqa: E402

FORMS = 'INIT', 'RIGID_DET'  # the kinds of a form that has ports or a key group, and ends at its last body

L2 = math.log(2)
COIN_ALT = os.environ.get('COIN_ALT', '1') == '1'  # gold's chance under a must_join coin that is true takes the weights that coin gives; 0 reads them as the free coin's
SEP = (ALSO_TOK, M.END)
SKIP = live.SKIP_TOK
ORDER_PART = 'orders: entropy credit'  # the part of a record by which -log2 of the sum over orders is under the mean of the orders' bits: minus the entropy of the orders' chances
ORDER_CAP, ORDER_BUDGET, ORDER_SECONDS = 256, 256, 300.0  # a clause with at most ORDER_CAP orders has all of them walked; another, ORDER_BUDGET walks of a guided draw; a clause's seconds


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
        self.total = len(rest)
        self.parts, self.counts, self.bad, self.atoms, self.detail = collections.Counter(), collections.Counter(), [], [], []
        self.hash, self.or_next, self.ctx = 0, False, 'top'
        self.levels = []  # one count of the branches so far, for each OR being drawn
        self.neg_idx = self.neg_toks = None
        self.cur = collections.Counter()
        self.where = ''  # in an INIT, the body that the walk is in ('key ', 'port ' or 'outside '), in front of the names of its parts
        self.carets = set()  # in an INIT, the numbers of the key's labels that gold marks with a caret
        self.port = None  # in an INIT, gold's port that the walk is in: see look
        self.rows = None  # with a list here, the rows that the steers score on gold's path: (kind, row) per consult, in walk order (see emit)
        self.stop = None  # the stop row that waits for the coin of its atom
        self.in_all = 0  # the ALLs being drawn
        self.marks = []  # the running bits after each atom of the walk
        self.fell_back = set()  # what the priors lack and the walk went on without: 'rigid' (a RIGID_DET's coins take 1/2), 'RIGID_DET atoms' (its parts take INIT's), 'empty_ports' (gold's empty port has no coin), 'empty_keyed' (the same in a key group)
        self.order_rng = None  # with a random.Random here, each body takes a random valid order as the walk comes to it (see shuffle)
        self.bodies = []  # the bodies of the form's text that no shuffle has taken
        self.star_total = sum(1 for t in rest if t in (M.STAR, M.CARET))
        self.order_key, self.order_many, self.no_order = [], False, None  # the bodies' tokens as walked, whether a body has other orders, why a body has no order

    def start(self, path):
        pass

    def shuffle(self, end):
        """The body at the front of rest, its first end tokens, takes a random valid order, and the tokens after it take the new label numbers. A body that body_order does not order
        stays as gold wrote it, and no_order says why."""
        if self.order_rng is None or self.no_order:
            return
        toks = list(self.rest)
        base = self.star_total - sum(1 for t in toks if t in (M.STAR, M.CARET))
        try:
            span, after, many = body_order.shuffle(self.run.V, toks[:end], toks[end:], base, self.run.ff0.label_tok, self.order_rng, self.bodies)
        except body_order.NoOrder as e:
            self.no_order = str(e)
            return
        self.rest.clear()
        self.rest.extend(span + after)
        self.order_key.append(tuple(span))
        self.order_many = self.order_many or many

    def stuck(self, why):
        self.bad.append(why)
        raise Stuck(why)

    def more(self):
        """Whether the body that the walk is in goes on in gold: an INIT body ends at its END."""
        return bool(self.rest) and not (self.kind in FORMS and self.rest[0] == M.END)

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
        self.shuffle(end)
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

    def emit(self, dr, kind, row, gold):
        """The sink of a Drawer: the row that a steer scores here, with gold's pick and where in the clause it is. A stop row waits for its coin."""
        row.update(gold=gold, place=dr.place, where='ALL' if self.in_all else ('body', 'branch', 'nested')[min(len(self.levels), 2)])
        if kind == 'stop':
            self.stop = row
        else:
            self.rows.append((kind, row))

    def stopped(self, gold):
        """The coin of the stop after an atom: its row takes gold's side. A stop that a gate bars has no coin, and its row is dropped."""
        if self.stop is not None:
            self.rows.append(('choice', dict(self.stop, gold='STOP' if gold else 'GO')))
            self.stop = None

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
        elif 'p_all' in line:
            r = bool(self.rest) and self.rest[0] == self.run.V.id('ALL')
            name, pop = 'top:no ALL', True
        elif 'stop_guard' in line:
            r = bool(self.rest) and self.rest[0] == M.END
            name, pop = 'all:guard stops', True
        elif "orc['after']" in line or 'all_after(' in line:  # the code reads `random() >= after`, which is a stop where the coin is False
            r = self.more()
            name = 'or:after'
        elif "['proposer']" in line:
            r = bool(self.rest) and self.run.V.name(self.rest[0]) in self.run.pri['proposers']
            name = 'proposer or atoms'
        elif 'random() < chance' in line:
            r = not self.more()
            name = 'top:stop'
            if self.rows is not None:
                self.stopped(r)
        elif 'ELSE_NEG' in line:
            self.neg_idx = None
            for i, a in enumerate(loc['first']):
                got = self.run.negated(loc['d'], a, loc['local'])
                if got is not None and list(got[1]) == list(self.rest)[:len(got[1])]:
                    self.neg_idx, self.neg_toks = i, len(got[1])
                    break
            r = self.neg_idx is not None
            name = 'br:else-NOT coin'
        elif 'nest_first' in line:
            r = bool(self.rest) and self.rest[0] == M.OR
            name = 'br:nest first coin'
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
        elif "rg['keyed']" in line or "rg['instance']" in line:  # a RIGID_DET's key group or instance clause
            r = bool(self.rest) and self.rest[0] != SKIP
            pre, name, pop = '', 'rigid: key group' if "rg['keyed']" in line else 'rigid: instance', False
            if not self.run.pri.get('rigid'):
                self.fell_back.add('rigid')
        elif 'f.admits([SKIP_TOK])' in line:  # a port's coin: taken or skipped
            r = not (self.rest and self.rest[0] == SKIP)
            pre, name, pop = '', 'outside: taken or skipped' if self.outside_loop(fr) else 'port: taken or skipped', False
        elif 'empties.get(' in line:  # a port of no atoms
            r = bool(self.rest) and self.rest[0] == M.END
            pre, name = '', 'port: empty'
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
                if self.kind in FORMS:
                    raise Stuck(name)
            r = p >= 1
        else:
            self.add(name, p if r else 1 - p)
        if pop is r and self.rest:
            self.rest.popleft()
        return r

    def choices(self, population, weights=None, k=1):
        """The count of an OR's branches; in a RULE or a DET the proposer; in an INIT also the component, the key's count of labels and a head column's count of labels."""
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
        elif who == 'proposed':
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
        elif who == 'key_body' and 'key_labels' in line:
            self.carets = self.key_group()
            n = len(self.carets)
            name = 'key: count of labels'
            if n not in population:
                self.stuck('key: %d labels are not among the counts that the priors have' % n)
        elif who == 'key_pick':
            return self.gold_key_pick(population, weights, sys._getframe(3))
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
        """The else negation's pick among the first branch's atoms, which takes the atom with no call of Drawer.atom."""
        for _ in range(self.neg_toks):
            self.rest.popleft()
        self.add(self.where + 'br:else-NOT pick', 1.0 / n)
        self.atoms.append((self.ctx, 'else-NOT', round(bits(1.0 / n), 2)))
        self.detail.append(dict(k=None, joined=True, lj=None, lf=None, cur={'else-NOT pick': round(bits(1.0 / n), 3)}))
        self.marks.append(sum(self.parts.values()))
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

    def key_gold(self, fr, population, k):
        """(gold's key labels among the population, the name of the part, the frame of the place) for Run.key_pick's caller fr, the place of the pick: the labels of a key group (in key_body), or the labels
        that an OR's first branch makes (in or_form). The population is label numbers."""
        who = fr.f_code.co_name
        if who == 'key_body':
            nlab = fr.f_locals['nlab']
            gold, name = sorted(nlab + c for c in self.carets), 'key: which labels'
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
            raise RuntimeError('a key pick that or_q.py does not know: ' + who)
        self.keypick(fr.f_locals['dr'], population, gold)
        return gold, name

    def keypick(self, dr, population, gold):
        """The row `keypick` of a key pick: the type sets of the labels offered, in the order of the labels, and of those taken. key_type_counts.py counts them."""
        if self.rows is not None:
            sets = self.run.label_type_sets(dr, (*dr.drawn, *dr.or_done))
            types = lambda n: sorted(sets['L%d' % n])  # noqa: E731
            self.emit(dr, 'keypick', dict(offered=[types(n) for n in population], taken=[types(n) for n in gold], k=len(gold)), gold)

    def sample(self, population, k):
        """The key's labels among the labels of a key group (in init), or among the labels that an OR's first branch makes (in or_form), as Run.key_pick draws them with every set at one chance."""
        fr = sys._getframe(1)
        population = list(population)
        gold, name = self.key_gold(fr.f_back, population, k)
        combos = math.comb(len(population), k)
        if combos > 1:
            self.add(name, 1.0 / combos)
        return gold

    def gold_key_pick(self, sets, weights, fr):
        """Run.key_pick's pick of a set of key labels with the weights of ORDER_FREE key: gold's set, with its share of the weights in the part."""
        labels = sorted({n for c in sets for n in c})
        gold, name = self.key_gold(fr, labels, len(sets[0]))
        gold = tuple(gold)
        if gold not in sets:
            self.bad.append('%s: gold\'s set %s is not among the sets' % (name, gold))
            return [sets[0]]
        if len(sets) > 1:
            self.add(name, weights[sets.index(gold)] / sum(weights))
        return [gold]

    def begin_port(self, cols, keys, outside):
        self.where = 'outside ' if outside else 'port '
        end = self.extent(list(self.rest))
        if end is not None:
            self.shuffle(end)
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
        if g.kind in FORMS and g.rest and g.rest[0] == M.END:  # gold's body has no atom, and the walk draws one: Run.port draws an empty port only with priors that count them
            g.stuck('%sbody: gold has no atom here, and the walk draws one' % g.where)
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
            g.parts['%s atom: join mix' % g.ctx] += total - sum(g.cur.values())
        g.atoms.append((g.ctx, res[3], None if total == math.inf else round(total, 2)))
        g.marks.append(sum(g.parts.values()))
        d = self.deltas.get(id(res))  # the join coin: log q given must_join, and given not
        g.detail.append(dict(k=self.p_k, joined=bool(res[4]), lj=None if d is None else round(d[1] / math.log(2), 3), lf=None if d is None else round(d[2] / math.log(2), 3),
                             cur={ph: round(b, 3) for ph, b in g.cur.items()}))
        if g.kind in FORMS and any(ph.startswith('relation') for ph in zero):  # the atom's tokens are not the walk's, so the tokens after it are out of step
            raise Stuck(g.bad[-1])
        return res, why

    def pick_complete(self, n, opts, weights, key, alt=None):
        """SearchDrawer's, with the share of gold's start among the weights of the other coin value, which the atom's coin mixture reads."""
        o, q = super().pick_complete(n, opts, weights, key, alt)
        if alt is not None and COIN_ALT:
            self.alt_q = self.alt_share(alt, opts.index(o)) if o in opts else 0.0
        return o, q

    def pick_reach(self, n, opts, weights, alt=None):
        """SearchDrawer's, with the share of gold's value among the weights of the other coin value."""
        o, q = super().pick_reach(n, opts, weights, alt)
        if alt is not None and COIN_ALT:
            self.alt_q = self.alt_share(alt, opts.index(o)) if o in opts else 0.0
        return o, q

    def steer_choice(self, fr, n, popts, opts, k, rel, joined, leaf, stop, key):
        """S's, and at a column pick where the atom may stop, the bits of gold's side of the stop: the stop's chance if gold's next token is no column, else its complement."""
        fm, stq = super().steer_choice(fr, n, popts, opts, k, rel, joined, leaf, stop, key)
        if n.phase == 'cols' and leaf and opts:
            stopped = not self.force or fr.KIND[self.force[0]] != 'column'
            self.rng.cur['column stop'] += bits(stq if stopped else 1 - stq)
        return fm, stq

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

    def all_form(self, *args):
        """The ALL's second END is not taken by any call, so it goes here."""
        g = self.rng
        g.in_all += 1
        try:
            got = super().all_form(*args)
        finally:
            g.in_all -= 1
        if got is not None:
            if g.rest and g.rest[0] == M.END:
                g.rest.popleft()
            else:
                g.bad.append('ALL end: gold has %s' % (g.rest[0] if g.rest else None))
        return got

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

    def drawer(self, pg, kind, dec, place=None, prior=None):
        """In an INIT, the parts of a body's atoms are those of its place. The hash that names the path to a body, for the caches that the Drawers of
        one path share, is the count of gold's tokens taken so far: each body of the walk has its own path, as in a search."""
        self.rng.hash = self.rng.total - len(self.rng.rest)
        dr, g = super().drawer(pg, kind, dec, place, prior), self.rng
        if g.rows is not None:
            dr.sink = lambda k, row, gold: g.emit(dr, k, row, gold)
        if kind == 'INIT':
            if place == 'key':
                g.where = 'key '
            g.ctx = g.where.strip()
        return dr

    def port(self, pg, f, comp, name, cols, params, nlab, keys, fields, outside=False):
        g = self.rng
        if comp == 'RIGID_DET' and 'RIGID_DET' not in self.pri['atoms']:
            g.fell_back.add('RIGID_DET atoms')
        counted = 'empty_keyed' if keys else 'empty_ports'
        if counted not in self.pri and not outside and comp != 'RIGID_DET' and g.extent(list(g.rest)) == 0:
            g.fell_back.add(counted)
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
    if kind in FORMS:  # the form ends at its last port, with no END of its own
        return collections.deque(t for t, _ in toks[1:])
    assert toks[-1][0] == M.END and len(toks[-1][1]) == 1
    return collections.deque(t for t, _ in toks[1:-1])


def one(sampler, task, case, point, kind=None):
    """The record of the point's walk. kind is that of gold's clause, from its text where None."""
    d, lines = G.gold_of(task, case, point)
    scope, target = lines[:point[0]], lines[point[0]]
    sess, task_json, _ = live_try.session_of(task)
    return walk(sampler, task, case, point, scope, target, sess, task_json, kind)


def walk_order(sampler, task, case, point, scope, target, sess, task_json, kind=None, rows=None, atoms=None, scoped=None, seconds=120, order_rng=None, seen=()):
    """The record of the walk of one order, the target text as written, over the scope forms on the session. With a list as rows, the rows that the
    steers score on gold's path, (kind, row) for each consult, are added to it (the Drawers' sink; STEER_COVER decides where INIT bodies and later
    branches count). atoms are the token lists of the target's atoms in another order, in place of the written one. scoped is a list of one item, the `Run.scoped` of these
    forms on this session, which saves the replay of the scope; the walk puts its own there. With it, the record has `marks`, the running bits after each atom. With order_rng, each
    body takes a random valid order; rec['order_key'] is its tokens, rec['order_many'] says whether the form has other orders and rec['no_order'] why a body has none. seen
    holds the order_keys that a caller has: a RULE or a DET whose key is there has no walk, and its record has order_key alone."""
    kind = kind or target.split()[0].lstrip('(')
    run = GuidedRun(sampler.pri, sess, time.monotonic() + seconds, task_json, live.Limits(form_tries=1))
    run.scoped = scoped[0] if scoped else None
    dec, pg = run.scope(scope)
    if scoped is not None:
        scoped[0] = run.scoped
    g = run.rng = Guide(run, collections.deque(t for a in atoms for t in a) if atoms else gold_rest(sess, scope, target, kind), kind)
    g.rows = rows
    dead = match = None
    if order_rng is not None:
        g.order_rng, g.bodies = order_rng, body_order.bodies_of(target)
        if kind not in FORMS:
            g.shuffle(len(g.rest))
            if g.no_order or tuple(g.order_key) in seen:
                return dict(order_key=tuple(g.order_key), order_many=g.order_many, no_order=g.no_order)
    try:
        f = run.form(pg, dec, kind)
        if kind in FORMS:  # the walk steps the SKIP of each port that is left, and takes no call for it
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
               total=round(sum(g.parts.values()), 2), bad=g.bad, dead=dead, left=len(g.rest), atoms=g.atoms, detail=g.detail, fell_back=sorted(g.fell_back),
               order_key=tuple(g.order_key), order_many=g.order_many, no_order=g.no_order)
    if scoped is not None:
        rec['marks'] = g.marks
    if kind in FORMS:
        rec['match'] = match
    return rec


def clean(rec):
    """Whether a record of one order is valid."""
    return not rec['bad'] and rec['dead'] is None and not rec['left']


PATH = re.compile(r'PathStep\((\d+)\)')
RULE_REASONS = O.RULE_REASONS
CANON_TRIES = 3000  # the orders of a form that canonical_lines tries


def decoder_check(sess, scope, kind):
    """form_orders' check of an order's text: the decoder takes the text over the scope. gold_rest decodes the whole program, and the tokens of the
    scope and then the text's are stepped through the session's decoder, which refuses more (for example "static prune") than the decode of a
    program does."""
    base = []

    def check(text):
        try:
            gold_rest(sess, scope, text, kind)
            ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*scope, text, live.READER_OUT)), sess.settings).decode_stream()
            if not base:
                dec = sess.decoder()
                for t, m, p in zip(ids, model, paths):
                    if m and p[0] < len(scope):
                        dec.step(t)
                base.append(dec)
            dec = base[0].fork()
            for t, m, p in zip(ids, model, paths):
                if m and p[0] == len(scope):
                    dec.step(t)
            return None
        except Exception as e:  # noqa: BLE001
            line = str(e).split('\n')[0]
            return line.split('): ')[-1], [int(x) for x in PATH.findall(line)][1:]
    return check


def columns_of(text, sess, scope):
    """The columns of the text's atoms that have ports, in the order of their paths: for each atom, {the steps from the atom to a port or a field: its column}."""
    ids, model, paths = arclog.StudyProgram.from_sexp('\n'.join((*scope, text, live.READER_OUT)), sess.settings).decode_stream()
    atoms, V = {}, sess.vocabulary
    for t, m, p in zip(ids, model, paths):
        if not m or p[0] != len(scope):
            continue
        p, kind = tuple(p), V.kind(t)
        if kind in live.S.RELATION_KINDS:
            atoms[p] = {}
        elif kind == 'column':
            at = next((p[:n] for n in range(len(p) - 1, 0, -1) if p[:n] in atoms), None)
            if at is not None:  # a head's record is in no atom
                atoms[at][p[len(at):]] = int(V.name(t)[1:])
    return [atoms[p] for p in sorted(atoms) if atoms[p]]


def sorted_fields(text, sess, scope):
    """The text with the ports of each atom, and the fields of each record, to any depth, in the column order of the relation or the record's key over the scope. The columns come from the decoder's tokens of the text.
    Fields of one column name keep their written order, since each stands for its own place in the key. Labels are marked again on their first occurrence. The text stays as written where the decoder refuses it or its atoms do not match the tokens."""
    def is_port(f):
        return isinstance(f, list) and bool(f) and isinstance(f[0], str) and f[0].startswith(':')

    def atoms(x, out):
        if isinstance(x, list) and x:
            if isinstance(x[0], str) and not x[0].startswith(':') and len(x) > 1 and all(is_port(f) for f in x[1:]):
                out.append(x)
            else:
                for y in x:
                    atoms(y, out)
        return out

    def order(port, at, cols):
        """The port with its fields in column order. A field that is a bare label is its own field name."""
        fields = [order(f, at + (i,), cols) if is_port(f) else f for i, f in enumerate(port[1:])]
        return [port[0], *[fields[i] for i in sorted(range(len(fields)), key=lambda i: cols.get(at + (i,), -1))]]

    try:
        tree = O.parse(text)[0]
        found, layout = atoms(tree, []), columns_of(text, sess, scope)
        if len(found) != len(layout):
            return text
        for x, cols in zip(found, layout):
            ports = [order(p, (i,), cols) for i, p in enumerate(x[1:])]
            x[1:] = [ports[i] for i in sorted(range(len(ports)), key=lambda i: cols[(i,)])]
        form = O.Form(O.unparse(tree))
    except (ValueError, KeyError):
        return text
    except Exception as e:  # noqa: BLE001
        if not isinstance(e, arclog.Refusal):
            raise
        return text
    return text if form.written is None else form.text(form.written)


def canonical_lines(lines, sess):
    """(lines with each drawable form in its first order, items sorted, that the decoder takes over its canonical ancestors, and with the fields of its atoms, and of their records, in the column order of the relations they read (sorted_fields); the count of forms that keep their written text). lines has no OUT form. A CHOOSE keeps its text."""
    out, kept = list(lines), 0
    forms = live.S.strata.sexprs('\n'.join(lines))
    for i in sorted(range(len(lines)), key=lambda i: len(live.S.ancestor_order(forms, i))):
        kind = lines[i].split()[0].lstrip('(')
        if kind not in live.DRAWN_KINDS:
            continue
        scope = canonical_scope(out, i)
        check, form = decoder_check(sess, scope, kind), O.Form(sorted_fields(lines[i], sess, scope))
        for order in itertools.islice(form.orders(), CANON_TRIES):
            got = check(form.text(order))
            if got is None:
                out[i] = form.text(order)
                break
            if got[0].startswith(O.RULE_REASONS):
                form.refuse(order, got[1])
        else:
            kept += 1
    return out, kept


def canonical_scope(lines, i):
    """The forms that form i of lines reads, directly or not, in ancestor_order: depth in the read graph, then form text."""
    return [lines[j] for j in live.S.ancestor_order(live.S.strata.sexprs('\n'.join(lines)), i)]


def order_walker(sampler, task, case, point, scope, kind, sess, task_json, seconds=120):
    """form_orders' walk of an order's text, on a new session each time, with the scope replayed: the bits of an order on a session that earlier walks used differ
    (check_session.py: up to 18 bits), and so do the bits with a scope replay that an earlier walk saved. A walk that isn't valid has its marks up to where it stopped, so that the guided draw learns the choice that ended it."""
    def go(text):
        try:
            fresh, fresh_json, _ = live_try.session_of(task)
            rec = walk_order(sampler, task, case, point, scope, text, fresh, fresh_json, kind, scoped=[None], seconds=seconds)
        except Exception as e:  # noqa: BLE001
            refused = isinstance(e, live.arclog.Refusal)  # a mode, type or safety check of the engine
            return dict(bits=None, marks=None, why='decoder' if refused else 'error', detail='%s: %s' % (type(e).__name__, str(e)[:160]))
        if not clean(rec):
            return dict(bits=None, marks=rec['marks'], why='walk', detail=str((rec['bad'] or [rec['dead']] if (rec['bad'] or rec['dead']) else ['left %d' % rec['left']])[0])[:120], rec=rec)
        return dict(bits=sum(rec['parts'].values()), marks=rec['marks'], rec=rec)
    return go


def weighted(rows):
    """The mean of each key of the dicts of rows, a list of (weight, dict), with a key that a dict lacks at 0."""
    out = collections.Counter()
    for w, d in rows:
        for k, v in d.items():
            if v is not None:
                out[k] += w * v
    return out


def atom_means(form, valid):
    """The rows of `atoms` and `detail`: for each atom of the form, the mean of its row over the orders, weighted by each order's chance. valid is a list of (weight, order, record)."""
    rows = {leaf.leaf_id: [] for leaf in form.leaves}
    for w, order, rec in valid:
        emitted = form.emission(order)
        if len(emitted) != len(rec['atoms']):  # a form of one proposer has no atom rows
            continue
        for leaf, (_, _, b), det in zip(emitted, rec['atoms'], rec['detail']):
            rows[leaf.leaf_id].append((w, b, det))
    done = []
    for leaf in form.leaves:
        got = rows[leaf.leaf_id]
        if not got:
            continue
        total = sum(w for w, _, _ in got)
        mean = sum(w * b for w, b, _ in got) / total
        k = [x for x in got if x[2]['k'] is not None]
        lj, lf = [x for x in got if x[2]['lj'] is not None], [x for x in got if x[2]['lf'] is not None]
        det = dict(k=round(sum(w * d['k'] for w, _, d in k) / total, 3) if k else None, joined=round(sum(w * d['joined'] for w, _, d in got) / total, 3),
                   lj=round(sum(w * d['lj'] for w, _, d in lj) / sum(w for w, _, _ in lj), 3) if lj else None, lf=round(sum(w * d['lf'] for w, _, d in lf) / sum(w for w, _, _ in lf), 3) if lf else None,
                   cur={p: round(v / total, 3) for p, v in sorted(weighted([(w, d['cur']) for w, _, d in got]).items())})
        done.append((leaf.place, O.unparse(O.strip_marks(leaf.tree)), round(mean, 2), det))
    done.sort(key=lambda r: r[:2])
    return [r[:3] for r in done], [r[3] for r in done]


def walk(sampler, task, case, point, scope, target, sess, task_json, kind=None, cap=None, budget=None, seconds=None, seed=None):
    """The record of the target clause over the scope forms on the session, read over its valid orders. `total` is -log2 of the sum of their chances,
    and `parts`, `counts`, `atoms` and `detail` are means weighted by each order's chance (see the head of this file). A clause with at most cap orders has
    each walked, and `orders.exact` is true. Another has budget walks of a guided draw, its `total` is an estimate and its means read the paths walked.
    `orders` has the order counts (`orders`, an estimate where `orders_exact` is false), `walked` and `valid` paths, `refused` by reason, `rules` learned from the decoder, `written`, the bits of the
    written order, which reads one order; `best`, those of the cheapest order walked; `tight`, -log2 of the sum over the paths walked and the written order; `only_written`, true where the clause has more orders than the cap, none of those walked is valid and the written order is; and for an estimate `walked_bits`, -log2 of the sum over the paths walked; `se_bits`; `ess`."""
    kind = kind or target.split()[0].lstrip('(')
    cap, budget, seconds = cap or ORDER_CAP, budget or ORDER_BUDGET, seconds or ORDER_SECONDS
    go = order_walker(sampler, task, case, point, scope, kind, sess, task_json)
    try:
        form = O.Form(target)
    except ValueError as e:
        rec = walk_order(sampler, task, case, point, scope, target, sess, task_json, kind)
        rec['orders'] = dict(orders=1, orders_exact=False, exact=False, walked=1, valid=int(clean(rec)), why=str(e))
        return rec
    got = O.sum_orders(form, go, decoder_check(sess, scope, kind), cap, budget, seconds, search.stable('%s %s' % (task, form.canonical_key())))
    valid = [(o, r) for o, r in got['walks'] if r['bits'] is not None]
    refused = collections.Counter(r['why'] for _, r in got['walks'] if r['bits'] is None)
    for reason, n in got['refused'].items():
        refused[reason] += n
    written = got['written']
    only_written = not valid and not got['orders_exact'] and written['bits'] is not None and form.written is not None
    if only_written:
        valid = [(form.written, written)]
        got = dict(got, bits=written['bits'])
    orders = dict(orders=got['orders'], orders_exact=got['orders_exact'], exact=got['exact'], walked=len(got['walks']), valid=len(valid), refused=dict(refused), rules=got['rules'], written=written['bits'], best=min((r['bits'] for _, r in valid), default=None),
                  tight=got['tight'] if got['tight'] != math.inf else None, only_written=only_written, stopped=got['stopped'], draws=got['draws'])
    orders['refused_examples'] = {w: sorted({r['detail'][:100] for _, r in got['walks'] if r.get('why') == w})[:2] for w in set(r['why'] for _, r in got['walks'] if r['bits'] is None)}
    if not valid:  # no order has a record to read: the written order's says why
        rec = written['rec'] if written.get('rec') else dict(task=task, case=case, point=point, target=target, parts={}, counts={}, total=0.0, bad=[written['detail']], dead=None, left=0, atoms=[], detail=[], fell_back=[])
        rec.pop('marks', None)
        rec['orders'] = orders
        return rec
    if not got['exact']:
        orders.update(walked_bits=None if got['walked_bits'] == math.inf else round(got['walked_bits'], 3), se_bits=round(got['se_bits'], 3), ess=None if got['ess'] is None else round(got['ess'], 1))
    low = min(r['bits'] for _, r in valid)
    shares = [2 ** (low - r['bits']) for _, r in valid]
    total = sum(shares)
    means = [(w / total, o, r['rec']) for w, (o, r) in zip(shares, valid)]
    parts = weighted([(w, r['parts']) for w, _, r in means])
    parts[ORDER_PART] = got['bits'] - sum(parts.values())
    atoms, detail = atom_means(form, means)
    rec = dict(task=task, case=case, point=point, target=target, parts={k: round(v, 3) for k, v in sorted(parts.items())}, counts={k: round(v, 3) for k, v in sorted(weighted([(w, r['counts']) for w, _, r in means]).items())},
               total=round(got['bits'], 2), bad=[], dead=None, left=0, atoms=atoms, detail=detail, fell_back=sorted({x for _, _, r in means for x in r['fell_back']}), orders=orders)
    if kind in FORMS:
        rec['match'] = any(r.get('match') for _, _, r in means)
        orders['text_differs'] = sum(r.get('match') is False for _, _, r in means)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stems')
    ap.add_argument('out')
    ap.add_argument('--steers', default=','.join(live.STEERS))
    ap.add_argument('--set', nargs='*', default=[], help='NAME=value: a number of live.py or search.py, replaced for the run')
    ap.add_argument('--order-cap', type=int, default=ORDER_CAP, help='a clause with at most this many orders has all of them walked')
    ap.add_argument('--order-budget', type=int, default=ORDER_BUDGET, help='the walks of a clause with more')
    a = ap.parse_args()
    globals().update(ORDER_CAP=a.order_cap, ORDER_BUDGET=a.order_budget)
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
