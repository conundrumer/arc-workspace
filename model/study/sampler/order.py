#!/usr/bin/env python
"""The order of the free choices of a query, for the two writer plans.

A query is written token by token. Many orders give one QueryHash: the atoms of a body, the branches of an OR, the atoms of a branch, the parts of an ALL,
and the bodies of a key group and of the ports. This module reads a query (its model tokens) as a tree of sets, and writes it in an order.

    env = Env(sess)                                       # per session (one task)
    q = read_query(env, base_dec, kind, tokens)           # base_dec: the decoder after the scope's tokens; tokens: [(token id, model flag)] of the query's form, the kind token first
    res = ordered(env, q)                                 # the `ordered` plan: the canonical paths of q
    res.paths                                             # the distinct token streams (model tokens, kind token left out) that the greedy rule allows
    res.stuck                                             # None, or what blocked the rule
    cnt = unordered_count(env, q)                         # the `unordered` plan: the count of distinct write paths

The `ordered` rule is greedy and binding-aware. At a set, the allowed item is the least by key among the items that the decoder accepts now (an item whose inputs are
bound), the key being the item's model tokens under the current naming: a label that is bound is its label token, a new label is the token `*` (or `^`) and takes the next
fresh index. An OR's branches, the atoms of a branch and the two parts of an ALL follow the same rule, each by itself. Items with equal keys are a tie, and every tie
choice is followed: the number of distinct streams is the number of paths.

A site's order inside an atom is not an order that the QueryHash ignores in the engine wheel of the study (site-exp18): a permutation of the sites changes the QueryHash.
The sites stay as the query has them. The operands of `=` stand so that a new label is first.

The `unordered` count is the number of distinct token streams, over every order that the decoder accepts. It is a dynamic program over the sets of items taken, with the streams
merged by their tokens (a determinised walk), and each compound item (OR, ALL) is expanded to all its inner orders.
"""
import collections
import dataclasses
import itertools
import math
import time
import types

import numpy as np

import live
import writer
from live import M, SKIP_TOK, ALSO_TOK

END, NOT, STAR, CARET, ZERO, OR_TOK = M.END, M.NOT, M.STAR, M.CARET, M.ZERO, M.OR
EQ = M.CMP[0]
CMP = tuple(M.CMP)
SYMMETRIC_CMP = (EQ, M.CMP[1])


class Stuck(Exception):
    """No item of a set can be written next. .why: [(item description, refusal)]."""

    def __init__(self, why, written=0, total=0):
        super().__init__('stuck after %d of %d' % (written, total))
        self.why, self.written, self.total = why, written, total


class Overflow(Exception):
    pass


# ---------------------------------------------------------------- the tree of a query

@dataclasses.dataclass
class Atom:
    toks: tuple  # model tokens; a label is -(label token id + 1)


@dataclasses.dataclass
class Or:
    branches: list  # of Set


@dataclasses.dataclass
class All:
    dom: 'Set'
    body: 'Set'
    needs: frozenset = frozenset()  # the labels that the ALL shares with the rest of the query: bound before it


@dataclasses.dataclass
class If:
    test: 'Set'
    then: 'Set'
    els: 'Set'


@dataclasses.dataclass
class Set:
    items: list
    kind: str


@dataclasses.dataclass
class Fixed:
    toks: tuple


@dataclasses.dataclass
class Body:
    set: Set


@dataclasses.dataclass
class Query:
    kind: str
    plan: list  # of Fixed and Body
    marks: dict  # gold label token id -> STAR or CARET
    base: object  # the decoder after the kind token
    gold: list  # the model tokens of the query after the kind token, as written
    gold_hash: int
    unsupported: str = ''
    total: object = None  # Counter: the mentions of each label in the whole query


class Env:
    """The vocabulary's classes and a stub Run for writer.Core, for one session."""

    def __init__(self, sess):
        V = sess.vocabulary
        n = len(V)
        self.V = V
        self.kind = [V.kind(i) for i in range(n)]
        self.ALL = V.id('ALL')
        colpos = {i: int(V.name(i)[1:]) for i in range(n) if self.kind[i] == 'column' and V.name(i)[1:].isdigit()}
        label_tok = {int(V.name(i)[1:]): i for i in range(n) if self.kind[i] == 'label'}
        self.run = types.SimpleNamespace(V=V, ff0=types.SimpleNamespace(colpos=colpos, label_tok=label_tok), pri={'regtypes': {}})
        self.pg = types.SimpleNamespace(colmaps=collections.defaultdict(dict))
        self.rel = {i for i in range(n) if self.kind[i] in live.S.RELATION_KINDS}
        self.col = set(colpos)
        self.colpos = colpos
        self.tie_log = []
        self.total = None  # the label mentions of the query that ordered() walks
        self.lookahead = False  # ordered() sets it for the second try of a query that the plain rule cannot write
        self.look = 0  # above 0 inside completable: the walk asks whether a rest can be written, and does not probe each atom for a dead end
        self.rcache = {}  # render of atoms, for one query (ordered clears it)
        self.label = {i for i in range(n) if self.kind[i] == 'label'}
        self.stats = collections.Counter()
        self.deadline = None  # a time.monotonic() value past which a walk raises Overflow
        self.sess = sess
        self.IF = V.id('IF')
        self.ONE = V.id('ONE')
        env_ONE[0] = self.ONE
        self.probe = [END, OR_TOK, NOT, self.ALL, EQ, CMP[1], V.id('input')]  # tokens that close an atom: some is in the mask unless the atom is a dead end
        self.open = np.array([k in ('column', 'label') or i in (STAR, CARET, ZERO) for i, k in enumerate(self.kind)])  # tokens that go on with an open atom


def sym(t):
    return -(t + 1)


def is_sym(s):
    return s < 0


# ---------------------------------------------------------------- reading a query

def segments(env, dec_kind, kind, full):
    """full: [(token id, model flag)] after the kind token. Returns [('fixed', [model tokens]) | ('body', body kind, [tokens: model tokens and the labels after `*` and `^`])]."""
    pt = writer.start_point(env.run, env.pg, dec_kind, kind)
    segs, cur = [], None
    for t, m in full:
        if not m:
            if cur is not None and cur[0] == 'body' and cur[2] and cur[2][-1] in (STAR, CARET) and env.kind[t] == 'label':
                cur[2].append(t)
            continue
        T = pt.track
        is_body = T.where == 'body' or (T.where == 'group' and t not in (SKIP_TOK, END))
        pt = writer.step_point(pt, t)
        if is_body:
            bid = pt.track.body
            if cur is not None and cur[0] == 'body' and cur[3] == bid:
                cur[2].append(t)
            else:
                bkind = 'body' if kind in ('RULE', 'DET') else ('key' if pt.track.inkey else 'port') if kind == 'INIT' else ('rigid key' if pt.track.inkey else 'part')
                cur = ['body', bkind, [t], bid]
                segs.append(cur)
        else:
            if cur is None or cur[0] != 'fixed':
                cur = ['fixed', None, [], None]
                segs.append(cur)
            cur[2].append(t)
    return [(s[0], s[1], s[2]) for s in segs]


def symbolise(env, toks, marks):
    """Tokens with labels as symbols; `*` and `^` leave the token list and go to marks."""
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if t in (STAR, CARET):
            g = toks[i + 1]
            marks.setdefault(g, t)
            out.append(sym(g))
            i += 2
            continue
        out.append(sym(t) if env.kind[t] == 'label' else t)
        i += 1
    return out


class ParseError(Exception):
    pass


def parse_atom(env, s, i):
    """The atom that starts at s[i] (a relation): (Atom tokens, next index)."""
    j = i + 1
    due = rec = False
    while j < len(s):
        t = s[j]
        if due:
            if t in env.col:
                rec = True
            else:
                due = False
            j += 1
        elif rec:
            if t in env.col:
                due = True
                j += 1
            elif t == END:
                rec = False
                j += 1
            else:
                break
        elif t in env.col:
            due = True
            j += 1
        elif is_sym(t) or t == ZERO:
            j += 1
        else:
            break
    return tuple(s[i:j]), j


def parse_item(env, s, i):
    t = s[i]
    if t == NOT:
        a, j = parse_atom(env, s, i + 1)
        return Atom((NOT,) + a), j
    if t in env.rel:
        a, j = parse_atom(env, s, i)
        return Atom(a), j
    if t in CMP:
        return Atom(tuple(s[i:i + 3])), i + 3
    if t == OR_TOK:
        j, branches = i + 1, []
        while True:
            items, j = parse_items(env, s, j, (ALSO_TOK, END))
            branches.append(Set(items, 'branch'))
            j += 1
            if s[j - 1] == END:
                break
        return Or(branches), j
    if t == env.ONE:  # a ONE mark: the labels it names, then its END
        j = i + 1
        while s[j] != END:
            j += 1
        return Atom(tuple(s[i:j + 1])), j + 1
    if t == env.IF:
        test, j = parse_items(env, s, i + 1, (END,))
        then, j = parse_items(env, s, j + 1, (END,))
        els, j = parse_items(env, s, j + 1, (END,))
        return If(Set(test, 'if test'), Set(then, 'if then'), Set(els, 'if else')), j + 1
    if t == env.ALL:
        dom, j = parse_items(env, s, i + 1, (END,))
        body, j = parse_items(env, s, j + 1, (END,))
        return All(Set(dom, 'all domain'), Set(body, 'all body')), j + 1
    raise ParseError('item starts with token %s' % env.V.name(t))


def parse_items(env, s, i, stop):
    items = []
    while s[i] not in stop:
        item, i = parse_item(env, s, i)
        items.append(item)
    return items, i


def read_query(env, base, kind, full, gold_hash=None):
    """base: the decoder after the scope. full: [(token id, model flag)] of the query's form, the kind token first."""
    dec = base.fork()
    dec.step(full[0][0])
    full = list(full[1:])
    marks = {}
    gold = [t for t, m in full if m]
    if gold_hash is None:
        d = dec.fork()
        for t in gold:
            d.step(t)
        gold_hash = d.query_hash(-1)
    q = Query(kind, [], marks, dec, gold, gold_hash)
    if kind == 'DEMONSTRATED':  # its rules hold forms, which the tree of sets does not hold: the query is written in its own order
        q.unsupported = 'DEMONSTRATED: no tree of sets of its rules'
        return q
    try:
        for tag, bkind, toks in segments(env, dec.fork(), kind, full):
            s = symbolise(env, toks, marks)
            if tag == 'fixed':
                q.plan.append(Fixed(tuple(s)))
            elif env.kind[s[0]] == 'proposer':
                q.plan.append(Fixed(tuple(s)))
            else:
                items, j = parse_items(env, s, 0, (END,))
                if j != len(s) - 1:
                    raise ParseError('body ends early')
                q.plan.append(Body(Set(items, bkind)))
        set_needs(q)
    except (ParseError, IndexError) as e:
        q.unsupported = '%s: %s' % (type(e).__name__, e)
    return q


def labels_of(item):
    """Counter of the labels in the atoms of an item."""
    c = collections.Counter()
    if isinstance(item, Atom):
        c.update(-x - 1 for x in item.toks if x < 0)
    elif isinstance(item, Or):
        for b in item.branches:
            for it in b.items:
                c += labels_of(it)
    elif isinstance(item, All):
        for it in item.dom.items + item.body.items:
            c += labels_of(it)
    elif isinstance(item, If):
        for it in item.test.items + item.then.items + item.els.items:
            c += labels_of(it)
    return c


def set_needs(q):
    total, alls = collections.Counter(), []

    def walk(items):
        for it in items:
            total.update(labels_of(it)) if isinstance(it, Atom) else None
            if isinstance(it, Or):
                for b in it.branches:
                    walk(b.items)
            elif isinstance(it, All):
                alls.append(it)
                walk(it.dom.items + it.body.items)
            elif isinstance(it, If):
                walk(it.test.items + it.then.items + it.els.items)
    for seg in q.plan:
        if isinstance(seg, Body):
            walk(seg.set.items)
        else:
            total.update(-x - 1 for x in seg.toks if x < 0)
    q.total = total
    for a in alls:
        inside = labels_of(a)
        a.needs = frozenset(g for g in inside if total[g] > inside[g])


def sets_of(q):
    """[(kind, item count)] of every set in the query, nested ones too."""
    out = []

    def walk(st):
        out.append((st.kind, len(st.items)))
        for it in st.items:
            if isinstance(it, Or):
                out.append(('or', len(it.branches)))
                for b in it.branches:
                    walk(b)
            elif isinstance(it, All):
                walk(it.dom)
                walk(it.body)
            elif isinstance(it, If):
                walk(it.test)
                walk(it.then)
                walk(it.els)
    for seg in q.plan:
        if isinstance(seg, Body):
            walk(seg.set)
    return out


def upper_orders(q):
    """The product of the factorials of the sizes of all sets: a bound on the orders (not on the distinct streams)."""
    return math.prod(math.factorial(n) for k, n in sets_of(q))


# ---------------------------------------------------------------- stepping

def nm_key(nm):
    return tuple(sorted(nm.items()))


def variants(s, nm, mode):
    """The token tuples that write an item. An item is written as it stands, except a symmetric comparison of two labels (`=`, `!=`), whose operands have no order of their own
    (the QueryHash ignores it): a new label stands first; two bound labels stand in the order of their label tokens under the rule ('min'), and in both orders otherwise ('all')."""
    if s[0] == env_ONE[0]:  # a ONE mark names a set of bound labels: in the order of their label tokens under the rule, in every order otherwise
        labs = s[1:-1]
        if all(x < 0 and (-x - 1) in nm for x in labs):
            if mode == 'min':
                return [(s[0],) + tuple(sorted(labs, key=lambda x: nm[-x - 1])) + (s[-1],)]
            return [(s[0],) + p + (s[-1],) for p in sorted(set(itertools.permutations(labs)))]
        return [s]
    if len(s) == 3 and s[0] in SYMMETRIC_CMP and s[1] < 0 and s[2] < 0:
        a_new, b_new = (-s[1] - 1) not in nm, (-s[2] - 1) not in nm
        if a_new != b_new:
            return [(s[0], s[1], s[2]) if a_new else (s[0], s[2], s[1])]
        if not a_new and s[1] != s[2]:
            x, y = nm[-s[1] - 1], nm[-s[2] - 1]
            if mode == 'min':
                return [(s[0], s[1], s[2]) if x < y else (s[0], s[2], s[1])]
            return [(s[0], s[1], s[2]), (s[0], s[2], s[1])]
    return [s]


env_ONE = [None]  # the token id of ONE (set by Env)


class Unbound(Exception):
    pass


def check_bound(s, nm):
    """Raises Unbound where an atom with the tokens s reads a label that is not bound: a NOT and a comparison other than `=` read bound labels only, and `=` at most one unbound.
    The decoder refuses these late (at a later atom or at the end), so the rule is here."""
    if s[0] == env_ONE[0]:
        if any(x < 0 and (-x - 1) not in nm for x in s[1:-1]):
            raise Unbound('ONE names an unbound label')
    elif s[0] == NOT:
        if any(x < 0 and (-x - 1) not in nm for x in s):
            raise Unbound('NOT reads an unbound label')
    elif s[0] in CMP:
        new = [x < 0 and (-x - 1) not in nm for x in s[1:]]
        if s[0] == EQ:
            if all(new[:2]) and len(new) == 2 and all(x < 0 for x in s[1:]):
                raise Unbound('= has no bound operand')
        elif any(new):
            raise Unbound('comparison reads an unbound label')


def step_syms(env, marks, st, s):
    """(model tokens, new state) after the symbolic tokens s on a fork of the state's decoder; raises on a refusal."""
    dec, nm = st
    check_bound(s, nm)
    d = dec.fork()
    nm = dict(nm)
    out = []
    kind = env.kind
    for x in s:
        if x < 0:
            g = -x - 1
            if g in nm:
                t = nm[g]
                out.append(t)
                d.step(t)
            else:
                m = marks[g]
                out.append(m)
                forced = d.step(m)[0]
                nm[g] = next(f for f in forced if kind[f] == 'label')
        else:
            out.append(x)
            d.step(x)
    return tuple(out), (d, nm)


def step_one(env, st, t):
    d = st[0].fork()
    d.step(t)
    return (d, st[1])


def describe(env, item):
    if isinstance(item, Atom):
        return ' '.join(env.V.name(t) if t >= 0 else 'L%d' % (-t - 1) for t in item.toks)
    return type(item).__name__ + str(len(getattr(item, 'branches', ())) or '')


# ---------------------------------------------------------------- the walk of a set

def render(env, marks, item, st, mode, sep=None, k=None):
    """[(tokens, state)] of the ways to write the item at the state, and an error text where none: for an atom one way; a compound item, every way of its inner sets
    under the mode ('min': the ordered rule, 'all': every order). sep: a token written before the item (ALSO). k: in mode 'min', a function from the state after the item to whether
    the rest of the query can still be written; the ways returned are those that it accepts (see completable)."""
    if env.deadline is not None and time.monotonic() > env.deadline:
        raise Overflow()
    try:
        if sep is not None:
            st = step_one(env, st, sep)
        if isinstance(item, Atom):
            ckey = (id(item), mode, env.look, nm_key(st[1]), st[0].trace_form())  # the same atom at the same form so far gives the same ways
            hit = env.rcache.get(ckey)
            if hit is not None:
                return hit
            outs, err = [], ''
            for v in variants(item.toks, st[1], mode):
                try:
                    toks, st2 = step_syms(env, marks, st, v)
                except Overflow:
                    raise
                except Exception as e:  # noqa: BLE001 - a refusal
                    err = str(e).split('\n')[0][:160]
                    continue
                if mode == 'min' and not env.look and not any(st2[0].admits(env.probe)):  # the mask holds no token that closes the atom: it is a dead end (the 'all' walks find it at the next token)
                    err = 'the atom cannot close'
                    continue
                outs.append((toks, st2))
            env.rcache[ckey] = got = (outs, ('' if outs else err))
            return got
        if isinstance(item, Set):  # a branch
            outs = walk_set(env, marks, item, st, mode, k=k)
            return [(o[0], o[1]) for o in outs], ''
        if isinstance(item, Or):
            st = step_one(env, st, OR_TOK)
            k_or = None if k is None else (lambda s2: after(env, k, s2, END))
            outs = walk_set(env, marks, Set(item.branches, 'or'), st, mode, sep=ALSO_TOK, branches=True, k=k_or)
            res = []
            for toks, st2 in outs:
                res.append(((OR_TOK,) + toks + (END,), step_end(env, st2)))
            return res, ''
        if isinstance(item, If):
            st = step_one(env, st, env.IF)
            res = []
            k_else = None if k is None else (lambda s3: after(env, k, s3, END))

            def full(sub):
                return frozenset(range(len(sub.items)))

            def k_then(s2):
                try:
                    s2 = step_end(env, s2)
                except Exception:  # noqa: BLE001
                    return False
                return completable(env, marks, item.els.items, full(item.els), s2, frozenset(), None, k_else, {})

            def k_test(s1):
                try:
                    s1 = step_end(env, s1)
                except Exception:  # noqa: BLE001
                    return False
                return completable(env, marks, item.then.items, full(item.then), s1, frozenset(), None, k_then, {})
            for t1, s1 in walk_set(env, marks, item.test, st, mode, k=None if k is None else k_test):
                s1 = step_end(env, s1)
                for t2, s2 in walk_set(env, marks, item.then, s1, mode, k=None if k is None else k_then):
                    s2 = step_end(env, s2)
                    for t3, s3 in walk_set(env, marks, item.els, s2, mode, k=k_else):
                        res.append(((env.IF,) + t1 + (END,) + t2 + (END,) + t3 + (END,), step_end(env, s3)))
            return res, ''
        if isinstance(item, All):
            miss = [g for g in item.needs if g not in st[1]]
            if miss:
                raise Unbound('ALL shares an unbound label')
            st = step_one(env, st, env.ALL)
            res = []
            k_body = None if k is None else (lambda s2: after(env, k, s2, END))

            def k_dom(s1):
                try:
                    s1 = step_end(env, s1)
                except Exception:  # noqa: BLE001
                    return False
                return completable(env, marks, item.body.items, frozenset(range(len(item.body.items))), s1, frozenset(), None, k_body, {})
            for t1, s1 in walk_set(env, marks, item.dom, st, mode, k=None if k is None else k_dom):
                s1 = step_end(env, s1)
                for t2, s2 in walk_set(env, marks, item.body, s1, mode, k=k_body):
                    res.append(((env.ALL,) + t1 + (END,) + t2 + (END,), step_end(env, s2)))
            return res, ''
    except Stuck as e:
        return [], 'inner stuck: ' + ('; '.join('%s: %s' % w for w in e.why[:3]))
    except Overflow:
        raise
    except Exception as e:  # a refusal of the decoder
        return [], str(e).split('\n')[0][:160]
    raise ValueError(item)


CAP = 512


def kept_labels(st):
    """The labels that the items of a set keep: those of its atoms and ALLs, and, for an OR in it, those that its first branch keeps."""
    out = set()
    for it in st.items:
        if isinstance(it, Or):
            out |= kept_labels(it.branches[0])
        else:
            out |= set(labels_of(it))
    return out


def branch_labels(b):
    return set().union(*(labels_of(it) for it in b.items))


def first_branches(branches, bound, total=None):
    """The indexes of the branches of an OR that may be written first. The first branch is where the OR's labels are made: a later branch may name only the labels that the
    first branch keeps and the labels bound outside the OR (`bound`; the engine's check/labels.rs, "the label is read outside each list that keeps it"). So the first branch
    keeps every label that two branches name and that is not bound outside, and every label that the rest of the query (total: the mentions of each label in the query) names."""
    named = [branch_labels(b) for b in branches]
    shared = {g for g in set().union(*named) if sum(g in s for s in named) >= 2} - set(bound)
    if total is not None:
        inside = collections.Counter()
        for b in branches:
            for it in b.items:
                inside += labels_of(it)
        shared |= {g for g in inside if g not in bound and total[g] > inside[g]}
    return {i for i, b in enumerate(branches) if shared <= kept_labels(b)}


def is_one(item):
    return isinstance(item, Atom) and item.toks[0] == env_ONE[0]


def one_waits(items, rem, idx, strict=False):
    """True where the item idx is a ONE mark and an item that is no ONE mark is still to be written: a clause ends in its ONE marks. strict (the `ordered` rule): the ONE marks also
    stand in the order of the query, since the QueryHash of the engine depends on the order of the marks."""
    return is_one(items[idx]) and any(not is_one(items[r]) or (strict and r < idx) for r in rem)


def exports_ok(env, item, nm):
    """False where an OR, written at the naming nm, would make a label that the rest of the query names but that it does not export: an OR exports a label that its first branch
    makes and every other branch names."""
    if env.total is None:
        return True
    if isinstance(item, If):  # the then is the first list: it exports the labels that it makes and the else names
        inside = labels_of(item)
        then_l, else_l = branch_labels(item.then), branch_labels(item.els)
        return all(g in then_l and g in else_l for g in inside if g not in nm and env.total[g] > inside[g])
    if not isinstance(item, Or):
        return True
    inside = labels_of(item)
    named = [branch_labels(b) for b in item.branches]
    return all(all(g in n for n in named) for g in inside if g not in nm and env.total[g] > inside[g])


def step_end(env, st, tok=END):
    """The state after the closing token tok, raising where the decoder's mask does not hold tok: the decoder takes some closing tokens that the mask leaves out (the label checks run
    on the mask), and the writer writes only what the mask holds."""
    if not st[0].admits([tok])[0]:
        raise ValueError('the mask does not hold the closing token')
    return step_one(env, st, tok)


def after(env, k, st, tok):
    """Whether token tok is accepted at state st and, then, k accepts the state (k None: true)."""
    try:
        st = step_end(env, st, tok)
    except Exception:  # noqa: BLE001
        return False
    return k is None or k(st)


def completable(env, marks, items, rem, st, cr, sep, k, memo):
    """True where the items `rem` can be written, in some order, from the state st (cr: the items that made the labels), and k then accepts the state after them (k None: true).
    The decoder refuses some orders late (a label read outside each list that keeps it, a key label that is local to a form), so the greedy rule asks this before it takes an item.
    The search follows the same rule (the least keys that complete), which finds a completion where one exists."""
    key = (rem, nm_key(st[1]), cr, st[0].trace_form())  # the form so far: states of one naming can differ in what the atoms before them were
    got = memo.get(key)
    if got is not None:
        return got
    memo[key] = False
    res = False
    env.look += 1
    try:
        res = _completable(env, marks, items, rem, st, cr, sep, k, memo)
    finally:
        env.look -= 1
    memo[key] = res
    return res


def _completable(env, marks, items, rem, st, cr, sep, k, memo):
    res = False
    if not rem:
        res = k is None or bool(k(st))
    else:
        for idx in sorted(rem):
            if one_waits(items, rem, idx, True):
                continue
            def kk(s1, idx=idx, st=st, rem=rem, cr=cr):
                return completable(env, marks, items, rem - {idx}, s1, cr | frozenset((g, idx) for g in s1[1] if g not in st[1]), sep, k, memo)
            outs, _ = render(env, marks, items[idx], st, 'min', sep, kk)
            if any(kk(s1) for _, s1 in outs):
                res = True
                break
    return res


def walk_set(env, marks, node, st, mode, sep=None, branches=False, cap=None, k=None):
    """[(tokens, state)] of the complete writes of a set's items: mode 'min' follows the rule (the least key among the legal items from which the rest of the set can still be
    written, and then k accepts the state; every tie followed), 'all' every legal item. Branches follow each other with the token sep between them; the first one is a branch
    that first_branches allows. k: a function from the state after the set to whether the rest of the query can be written (None: no test). Raises Stuck where no item can follow."""
    cap = cap or CAP
    items = node.items
    n = len(items)
    first = first_branches(items, st[1], env.total) if branches else None
    memo = {}
    frontier = [((), st, tuple(range(n)), frozenset())]
    for step in range(n):
        new = {}
        dead = None
        for toks, s0, rem, cr in frontier:
            cands, why = [], []
            for idx in rem:
                if step == 0 and first is not None and idx not in first:
                    why.append((describe(env, items[idx]), 'the branch does not keep a label that another branch names'))
                    continue
                if one_waits(items, rem, idx, mode == 'min'):
                    why.append((describe(env, items[idx]), 'a ONE mark comes after the other items'))
                    continue
                if mode == 'min' and not exports_ok(env, items[idx], s0[1]):
                    why.append((describe(env, items[idx]), 'the OR would make a label that it does not export'))
                    continue
                kk = None
                if mode == 'min' and env.lookahead:
                    kk = (lambda s1, idx=idx, s0=s0, rem=rem, cr=cr: completable(
                        env, marks, items, frozenset(rem) - {idx}, s1, cr | frozenset((g, idx) for g in s1[1] if g not in s0[1]), sep, k, memo))
                outs, err = render(env, marks, items[idx], s0, mode, sep if (sep is not None and step > 0) else None, kk)
                if not outs:
                    why.append((describe(env, items[idx]), err))
                for o in outs:
                    cands.append((o[0], idx, o))
            if not cands:
                if dead is None:
                    dead = why
                continue
            if mode == 'min' and not env.lookahead:
                kmin = min(c[0] for c in cands)
                cands = [c for c in cands if c[0] == kmin]
                if len({c[1] for c in cands}) > 1:
                    env.stats['tie_choices'] += 1
                    env.tie_log.append(node.kind)
            elif mode == 'min':
                cands.sort(key=lambda c: c[0])
                kept, i = [], 0
                while i < len(cands) and not kept:
                    j = i
                    while j < len(cands) and cands[j][0] == cands[i][0]:
                        j += 1
                    for c in cands[i:j]:
                        rem2 = frozenset(r for r in rem if r != c[1])
                        made = frozenset((g, c[1]) for g in c[2][1][1] if g not in s0[1])
                        if completable(env, marks, items, rem2, c[2][1], cr | made, sep, k, memo):
                            kept.append(c)
                    i = j
                if not kept:
                    if dead is None:
                        dead = why + [('the rest of the set', 'no order of the items that are left can be written')]
                    continue
                cands = kept
                if len({c[1] for c in cands}) > 1:
                    env.stats['tie_choices'] += 1
                    env.tie_log.append(node.kind)
            for key, idx, o in cands:
                add = ((sep,) if sep is not None and step > 0 else ()) + o[0]
                rem2 = tuple(i for i in rem if i != idx)
                cr2 = cr | frozenset((g, idx) for g in o[1][1] if g not in s0[1])
                new[(toks + add, nm_key(o[1][1]), rem2)] = (toks + add, o[1], rem2, cr2)
        if not new:
            raise Stuck(dead or [], step, n)
        if len(new) > cap:
            raise Overflow()
        frontier = list(new.values())
    out = {}
    for toks, s0, rem, cr in frontier:
        out[(toks, nm_key(s0[1]))] = (toks, s0)
    return list(out.values())


# ---------------------------------------------------------------- the ordered plan

@dataclasses.dataclass
class Ordered:
    paths: list  # distinct model-token streams (after the kind token) that the rule writes
    hashes: list  # the QueryHash of each
    stuck: object  # None, or Stuck
    stuck_at: str  # the set kind where it stuck
    overflow: bool
    ties: int
    nms: list = dataclasses.field(default_factory=list)  # the final naming (query label -> label token) of each path
    tied: int = 0  # the streams that the tie choices gave, before the end-of-query rule kept the least


def ordered(env, q, cap=CAP):
    """The `ordered` plan's canonical path of q. The plain rule (the least key among the legal items) first; where it gets stuck, or its stream is refused at the end of a body, the rule is
    tried again with a lookahead: an item is taken only if the rest can still be written (completable)."""
    env.lookahead = False
    res = _ordered(env, q, cap)
    if res.paths or res.overflow or res.stuck is None:
        return res
    env.lookahead = True
    try:
        return _ordered(env, q, cap)
    finally:
        env.lookahead = False


def _ordered(env, q, cap=CAP):
    env.total = q.total
    env.rcache = {}
    env.stats.clear()
    env.tie_log = []
    states = {((), ()): ((), (q.base.fork(), {}))}
    stuck, where, overflow = None, '', False
    marks = q.marks
    # the base decoder has stepped the kind token
    try:
        for seg in q.plan:
            new = {}
            for toks, st in states.values():
                if isinstance(seg, Fixed):
                    t2, st2 = step_syms(env, marks, st, seg.toks)
                    new[(toks + t2, nm_key(st2[1]))] = (toks + t2, st2)
                else:
                    try:
                        outs = walk_set(env, marks, seg.set, st, 'min', cap=cap, k=lambda s2: after(env, None, s2, END))
                    except Stuck as e:
                        stuck, where = e, seg.set.kind
                        raise
                    refused = []
                    for t1, s1 in outs:
                        try:
                            s2 = step_end(env, s1)
                        except Exception as e:  # noqa: BLE001 - the end of the body refused
                            refused.append(('END', str(e).split('\n')[0][:160]))
                            continue
                        new[(toks + t1 + (END,), nm_key(s2[1]))] = (toks + t1 + (END,), s2)
                    if not new:
                        stuck, where = Stuck(refused, len(seg.set.items), len(seg.set.items)), seg.set.kind + ' end'
                        raise stuck
            if len(new) > cap:
                raise Overflow()
            states = new
    except Stuck:
        return Ordered([], [], stuck, where, False, env.stats['tie_choices'], [], 0)
    except Overflow:
        return Ordered([], [], None, '', True, env.stats['tie_choices'], [], 0)
    except Exception as e:  # noqa: BLE001 - a refusal in a fixed part
        return Ordered([], [], Stuck([('fixed part', str(e).split('\n')[0][:160])]), 'fixed', False, env.stats['tie_choices'], [], 0)
    paths, nms = {}, {}
    for toks, st in states.values():
        paths.setdefault(toks, st[0].query_hash(-1))
        nms.setdefault(toks, st[1])
    # the end-of-query rule: items with equal keys make different labels, so tie choices can give different streams; the least complete stream is the path
    tied = len(paths)
    best = min(paths)
    return Ordered([best], [paths[best]], None, '', False, env.stats['tie_choices'], [nms[best]], tied)


# ---------------------------------------------------------------- the unordered plan

def count_set(env, marks, node, st, limit=20000):
    """The number of distinct token streams over every order of the set that the decoder accepts, written as a body (the closing END checked). Raises Overflow past `limit` states.
    A state of the walk is the items taken, and which item made each label: the decoder's late refusals (a test that the atoms before it imply) depend on both."""
    items = node.items
    memo = {}
    nstates = [0]

    def cnt(cfgs):
        # cfgs: list of (rem frozenset, state, creators frozenset of (label, item index))
        if len(cfgs) == 1:
            key = (cfgs[0][0], cfgs[0][2])
        else:
            key = frozenset((c[0], c[2], nm_key(c[1][1])) for c in cfgs)
        if key in memo:
            return memo[key]
        nstates[0] += 1
        if nstates[0] > limit:
            raise Overflow()
        total = 0
        live_cfgs = []
        ended = False
        for c in cfgs:
            if c[0]:
                live_cfgs.append(c)
            elif not ended:
                try:
                    step_end(env, c[1])
                    total += 1
                    ended = True
                except Exception:  # noqa: BLE001
                    pass
        groups = collections.defaultdict(dict)
        for rem, s0, cr in live_cfgs:
            for idx in rem:
                if one_waits(items, rem, idx):
                    continue
                outs, _ = render(env, marks, items[idx], s0, 'all')
                for toks, s1 in outs:
                    r2 = rem - {idx}
                    cr2 = cr | {(g, idx) for g in s1[1] if g not in s0[1]}
                    groups[toks][(r2, cr2, nm_key(s1[1]))] = (r2, s1, cr2)
        for toks, d in groups.items():
            total += cnt(list(d.values()))
        memo[key] = total
        return total
    return cnt([(frozenset(range(len(items))), st, frozenset())]), nstates[0]


def gold_states(env, q):
    """The state (decoder, naming) at the start of each segment, along the query's own order."""
    st = (q.base.fork(), {})
    out = []
    for seg in q.plan:
        out.append(st)
        if isinstance(seg, Fixed):
            _, st = step_syms(env, q.marks, st, seg.toks)
        else:
            for it in seg.set.items:  # items in the written order
                st = gold_item(env, q.marks, it, st)
            st = step_one(env, st, END)
    return out


def gold_item(env, marks, item, st):
    if isinstance(item, Atom):
        return step_syms(env, marks, st, item.toks)[1]
    if isinstance(item, Or):
        st = step_one(env, st, OR_TOK)
        for k, b in enumerate(item.branches):
            if k:
                st = step_one(env, st, ALSO_TOK)
            for it in b.items:
                st = gold_item(env, marks, it, st)
        return step_one(env, st, END)
    if isinstance(item, If):
        st = step_one(env, st, env.IF)
        for sub in (item.test, item.then, item.els):
            for it in sub.items:
                st = gold_item(env, marks, it, st)
            st = step_one(env, st, END)
        return st
    st = step_one(env, st, env.ALL)
    for it in item.dom.items:
        st = gold_item(env, marks, it, st)
    st = step_one(env, st, END)
    for it in item.body.items:
        st = gold_item(env, marks, it, st)
    return step_one(env, st, END)


def unordered_count(env, q, limit=20000):
    """(count or None, exact, states, per set [(kind, items, count or None)]). The count is the product of the counts of the bodies (each from the query's own state at its start)."""
    env.total = q.total
    env.rcache = {}
    starts = gold_states(env, q)
    total, exact, nst, per = 1, True, 0, []
    for seg, st in zip(q.plan, starts):
        if not isinstance(seg, Body):
            continue
        try:
            c, n = count_set(env, q.marks, seg.set, st, limit)
            nst += n
            per.append((seg.set.kind, len(seg.set.items), c))
            total *= c
        except Overflow:
            exact = False
            per.append((seg.set.kind, len(seg.set.items), None))
    return (total if exact else None), exact, nst, per


# ---------------------------------------------------------------- where the labels are made

def creation_sites(env, toks):
    """[(relation or operator, column, mark)] of each `*` and `^` of a stream of model tokens, in order: the k-th is the k-th label."""
    out, rel, col = [], None, None
    V = env.V
    for t in toks:
        if t in env.rel or t in CMP:
            rel, col = V.name(t), None
        elif t in env.col:
            col = V.name(t)
        elif t in (STAR, CARET):
            out.append((rel, col, V.name(t)))
    return out


def gold_naming(env, q):
    st = (q.base.fork(), {})
    for seg in q.plan:
        if isinstance(seg, Fixed):
            _, st = step_syms(env, q.marks, st, seg.toks)
        else:
            for it in seg.set.items:
                st = gold_item(env, q.marks, it, st)
            st = step_one(env, st, END)
    return st[1]


def site_diff(env, q, toks, nm):
    """The labels whose making site is not the query's own: [(mark, site as written, site in toks)]."""
    base = env.V.id('L0')
    gs, cs = creation_sites(env, q.gold), creation_sites(env, toks)
    out = []
    for g, tg in gold_naming(env, q).items():
        a, b = gs[tg - base], cs[nm[g] - base]
        if a != b:
            out.append((a[2], a[:2], b[:2]))
    return out


# ---------------------------------------------------------------- sites and operands

def atoms_of(q):
    out = []

    def walk(items):
        for it in items:
            if isinstance(it, Atom):
                out.append(it)
            elif isinstance(it, Or):
                for b in it.branches:
                    walk(b.items)
            elif isinstance(it, All):
                walk(it.dom.items + it.body.items)
            elif isinstance(it, If):
                walk(it.test.items + it.then.items + it.els.items)
    for seg in q.plan:
        if isinstance(seg, Body):
            walk(seg.set.items)
    return out


def site_stats(env, q):
    """(histogram {sites in an atom: atoms}, atoms whose sites are not in ascending column order, count of symmetric comparisons of two labels)."""
    hist, bad, sym2 = collections.Counter(), 0, 0
    for a in atoms_of(q):
        toks = a.toks
        if toks[0] in CMP:
            sym2 += toks[0] in SYMMETRIC_CMP and len(toks) == 3 and toks[1] < 0 and toks[2] < 0
            continue
        cols, due, rec = [], False, False
        for t in toks[2:] if toks[0] == NOT else toks[1:]:
            if due:
                if t in env.col:
                    rec = True
                else:
                    due = False
            elif rec:
                if t in env.col:
                    due = True
                else:
                    rec = False if t == END else rec
            elif t in env.col:
                due = True
                cols.append(env.colpos[t])
        hist[len(cols)] += 1
        bad += any(x >= y for x, y in zip(cols, cols[1:]))
    return dict(hist), bad, sym2


# ---------------------------------------------------------------- the set key of a writing point
#
#   set_key(pt)        a 16-byte hex digest: two writing points with the same key hold the same partial query as sets of items, up to a renaming of the labels, and the same open item
#   set_key_text(pt)   the text that the digest is of
#
# The partial query is read from pt.tokens alone. The atoms of a body, the branches of an OR, the atoms of a branch and the two lists of an ALL are sets; what has no free order
# (the component, SKIP, the heads of ports) stays in order. The open item is the open atom and the open containers (OR, ALL, body) around it. A label is named by a canonical
# numbering: colours by refinement over the atoms that read it, and the ties of that by the least text over their permutations (up to PERMS). With creators=True an atom that
# makes a label (`*`, `^`) differs from one that reads it, because the decoder's later refusals and the QueryHash of an OR depend on which atom made the label.

PERMS = 720


class _Open:
    """A container of a partial parse: kind 'body', 'or', 'all' or 'if' (stages: the lists of the test and the then, once closed)."""
    __slots__ = ('kind', 'items', 'branches', 'dom', 'stages')

    def __init__(self, kind):
        self.kind, self.items, self.branches, self.dom, self.stages = kind, [], [], None, []


def parse_prefix(core, kind, tokens, made):
    """The model tokens of a writing point (the kind token first) as a partial tree.

    Returns (segments, stack, atom). segments: ('F', tokens) for structure with no free order and ('B', items) for a closed body. stack: the open containers, outermost first.
    atom: the open atom (a list) or None. An item is ('A', tokens), ('OR', branches) or ('ALL', domain, body). In tokens a label read is ('L', token) and a label made by `*` or `^`
    is ('N', token, mark); the rest are ints. made: the label tokens in the order they were made."""
    rel, col, lab, ALLT = core.is_rel, core.is_column, core.is_label, core.ALL
    it = iter(made)
    segs, stack, atom, fixed = [], [], None, []
    one = None  # the open ONE mark
    due = rec = False
    need = 0
    toks = list(tokens[1:])
    if kind in ('RULE', 'DET'):
        if toks and core.kind[toks[0]] == 'proposer':
            return [('F', tuple(toks))], [], None
        stack.append(_Open('body'))

    def value(t):
        if t in (STAR, CARET):
            return ('N', next(it), t)
        return ('L', t) if lab[t] else t

    for t in toks:
        if not stack:  # the group level of an INIT or a RIGID_DET
            if not (rel[t] or t in CMP or t in (NOT, OR_TOK, ALLT, core.IF, core.ONE)):
                fixed.append(('L', t) if lab[t] else t)
                continue
            if fixed:
                segs.append(('F', tuple(fixed)))
                fixed = []
            stack.append(_Open('body'))
        if one is not None:  # inside a ONE mark: labels, then its END
            if t == END:
                one.append(END)
                stack[-1].items.append(('A', tuple(one)))
                one = None
            else:
                one.append(('L', t) if lab[t] else t)
            continue
        if atom is not None:
            if due:
                if col[t]:  # the first field of a record
                    rec = True
                    atom.append(t)
                else:
                    atom.append(value(t))
                    due = False
                continue
            if need > 0:
                atom.append(value(t))
                need -= 1
                continue
            if rec:
                atom.append(t)
                if col[t]:
                    due = True
                else:  # END of the record
                    rec = False
                continue
            if col[t]:
                atom.append(t)
                due = True
                continue
            if t in (STAR, CARET, ZERO) or lab[t]:
                atom.append(value(t))
                continue
            if atom == [NOT] and rel[t]:
                atom.append(t)
                continue
            stack[-1].items.append(('A', tuple(atom)))
            atom = None
        top = stack[-1]
        if rel[t] or t == NOT:
            atom, due, rec, need = [t], False, False, 0
        elif t in CMP:
            atom, due, rec, need = [t], False, False, 2
        elif t == OR_TOK:
            stack.append(_Open('or'))
        elif t == ALLT:
            stack.append(_Open('all'))
        elif t == core.IF:
            stack.append(_Open('if'))
        elif t == core.ONE:
            one = [t]
        elif t == ALSO_TOK:
            top.branches.append(tuple(top.items))
            top.items = []
        elif t == END:
            if top.kind == 'body':
                segs.append(('B', tuple(top.items)))
                stack.pop()
            elif top.kind == 'or':
                top.branches.append(tuple(top.items))
                stack.pop()
                stack[-1].items.append(('OR', tuple(top.branches)))
            elif top.kind == 'if':
                top.stages.append(tuple(top.items))
                top.items = []
                if len(top.stages) == 3:
                    stack.pop()
                    stack[-1].items.append(('IF',) + tuple(top.stages))
            elif top.dom is None:
                top.dom, top.items = tuple(top.items), []
            else:
                stack.pop()
                stack[-1].items.append(('ALL', top.dom, tuple(top.items)))
        else:
            raise ValueError('token %s at an item start' % core.names[t])
    if not stack and fixed:
        segs.append(('F', tuple(fixed)))
    if one is not None:
        atom = one
    return segs, stack, atom


def _atoms(segs, stack, atom):
    """[(path, tokens)] of every atom of a partial tree, and the open atom last as (path + ('open',), tokens)."""
    out = []

    def items(its, path):
        for x in its:
            if x[0] == 'A':
                out.append((path, x[1]))
            elif x[0] == 'OR':
                for b in x[1]:
                    items(b, path + ('or',))
            elif x[0] == 'IF':
                for sub in x[1:]:
                    items(sub, path + ('if',))
            else:
                items(x[1], path + ('all',))
                items(x[2], path + ('all',))
    for i, (tag, body) in enumerate(segs):
        if tag == 'F':
            out.append((('F', i), body))
        else:
            items(body, ('B', i))
    path = ('O', len(segs))
    for c in stack:
        path = path + (c.kind,)
        items(c.items, path)
        for b in c.branches:
            items(b, path + ('or',))
        if c.dom is not None:
            items(c.dom, path + ('all',))
        for sub in c.stages:
            items(sub, path + ('if',))
    if atom is not None:
        out.append((path + ('open',), tuple(atom)))
    return out


def _tok_text(x, lab_text, creators):
    if isinstance(x, int):
        return 'i%d' % x
    if x[0] == 'N' and creators:
        return 'N%s%d' % (lab_text(x[1]), x[2])
    return 'L' + lab_text(x[1])


def _atom_text(toks, lab_text, creators):
    """The text of an atom's tokens. The two operands of a symmetric comparison of two read labels stand in no order."""
    parts = [_tok_text(x, lab_text, creators) for x in toks]
    if toks[0] == env_ONE[0]:  # a ONE mark names a set of labels
        e = -1 if toks[-1] == END else len(toks)
        parts[1:e] = sorted(parts[1:e])
    if len(toks) == 3 and toks[0] in SYMMETRIC_CMP and all(not isinstance(x, int) and (x[0] == 'L' or not creators) for x in toks[1:]):
        parts[1:] = sorted(parts[1:])
    return ' '.join(parts)


def set_key_text(pt, creators=True):
    core = writer.core_of(pt.run)
    segs, stack, atom = parse_prefix(core, pt.kind, pt.tokens, [L.tok for L in pt.labels.items])
    atoms = _atoms(segs, stack, atom)
    labels = sorted({x[1] for _, toks in atoms for x in toks if not isinstance(x, int)})
    # colours by refinement
    color = {g: 0 for g in labels}
    ncls = 1
    for _ in range(len(labels) + 1):
        sigs = {}
        for g in labels:
            sigs[g] = repr((color[g], sorted(repr((path, _atom_text(toks, lambda h: 'X' if h == g else str(color[h]), creators)))
                                              for path, toks in atoms if any(not isinstance(x, int) and x[1] == g for x in toks))))
        rank = {s: i for i, s in enumerate(sorted(set(sigs.values())))}
        color = {g: rank[sigs[g]] for g in labels}
        if len(rank) == ncls:
            break
        ncls = len(rank)
    classes = collections.defaultdict(list)
    for g in labels:
        classes[color[g]].append(g)
    order = [classes[c] for c in sorted(classes)]
    best = None
    if math.prod(math.factorial(len(c)) for c in order) <= PERMS:
        choices = itertools.product(*[itertools.permutations(c) for c in order])
    else:
        choices = [tuple(tuple(c) for c in order)]
    for choice in choices:
        num, n = {}, 0
        for c in choice:
            for g in c:
                num[g] = n
                n += 1
        text = _encode(segs, stack, atom, num, creators, pt.kind)
        if best is None or text < best:
            best = text
    return best


def _encode(segs, stack, atom, num, creators, kind):
    lab_text = lambda h: str(num[h])  # noqa: E731

    def at(toks):
        return _atom_text(toks, lab_text, creators)

    def its(items):
        return ','.join(sorted(item(x) for x in items))

    def item(x):
        if x[0] == 'A':
            return '(' + at(x[1]) + ')'
        if x[0] == 'OR':
            return 'OR[' + '|'.join(sorted(its(b) for b in x[1])) + ']'
        if x[0] == 'IF':
            return 'IF[' + '|'.join(its(sub) for sub in x[1:]) + ']'
        return 'ALL[' + its(x[1]) + '|' + its(x[2]) + ']'
    parts = [kind]
    for tag, body in segs:
        parts.append('F:' + at(body) if tag == 'F' else 'B:{' + its(body) + '}')

    def open_part(k):
        if k == len(stack):
            return ('A?(' + at(atom) + ')') if atom is not None else '-'
        c = stack[k]
        head = c.kind + '{' + its(c.items) + '}'
        if c.kind == 'or':
            head = 'or{' + '|'.join(sorted(its(b) for b in c.branches)) + '}cur{' + its(c.items) + '}'
        elif c.kind == 'if':
            head = 'if{' + '|'.join(its(sub) for sub in c.stages) + '}cur{' + its(c.items) + '}'
        elif c.kind == 'all':
            head = 'all{' + ('-' if c.dom is None else its(c.dom)) + '}cur{' + its(c.items) + '}'
        return head + '>' + open_part(k + 1)
    parts.append('O:' + open_part(0))
    return ';'.join(parts)


def set_key(pt, creators=True):
    """A 16-byte digest (hex) of set_key_text: the state of a writing point as sets of items up to label renaming, with the open item."""
    import hashlib
    return hashlib.blake2b(set_key_text(pt, creators).encode(), digest_size=16).hexdigest()


# ---------------------------------------------------------------- a query from its model tokens, and its canonical stream
#
#   full_of(env, scope_dec, kind, stream)             [(token, model flag)] of a query's form: the labels that `*` and `^` force follow as tokens that are not model tokens
#   query_of(env, scope_dec, kind, stream)            the Query (read_query) of a stream of model tokens
#   canonical_stream(env, scope_dec, kind, stream)    (stream to write, 'canonical' | 'gold', why): the `ordered` plan's stream, else the stream as given
#
# scope_dec is the decoder after the scope's forms (the first result of Run.scope), before the kind token.

def full_of(env, scope_dec, kind, stream):
    stream = [int(t) for t in stream]
    kind_tok = live.KIND_TOK[kind]
    if stream and stream[0] == kind_tok:
        stream = stream[1:]
    d = scope_dec.fork()
    d.step(kind_tok)
    full = [(kind_tok, True)]
    for t in stream:
        forced = d.step(t)[0]
        full.append((t, True))
        if t in (STAR, CARET):
            full.extend((f, False) for f in forced if env.kind[f] == 'label')
    return full


def query_of(env, scope_dec, kind, stream):
    return read_query(env, scope_dec, kind, full_of(env, scope_dec, kind, stream))


def canonical_stream(env, scope_dec, kind, stream, seconds=10.0):
    """(the stream to write, order, why). order is 'canonical' when the `ordered` rule gives one stream whose QueryHash is the gold QueryHash, else 'gold' with the stream as
    given and why: unsupported, stuck, overflow, hash_mismatch or an error text. The streams do not hold the kind token."""
    stream = [int(t) for t in stream]
    if stream and stream[0] == live.KIND_TOK[kind]:
        stream = stream[1:]
    try:
        q = query_of(env, scope_dec, kind, stream)
        if q.unsupported:
            return stream, 'gold', 'unsupported'
        env.deadline = time.monotonic() + seconds
        try:
            res = ordered(env, q)
        finally:
            env.deadline = None
    except Exception as e:  # noqa: BLE001
        return stream, 'gold', 'error: %s: %s' % (type(e).__name__, str(e)[:100])
    if res.overflow:
        return stream, 'gold', 'overflow'
    if res.stuck is not None:
        return stream, 'gold', 'stuck'
    if len(res.paths) != 1 or res.hashes[0] != q.gold_hash:
        return stream, 'gold', 'hash_mismatch'
    return [int(t) for t in res.paths[0]], 'canonical', ''


# ---------------------------------------------------------------- the unordered language of a query as an automaton
#
#   w = Unordered(env, q)           explores every state of the query's items (like count_set), once; Overflow past `limit` states or `seconds`
#   w.ok                            False where no order of the items is accepted by the decoder
#   cfgs = w.start()                the configurations before the first token (after the kind token)
#   w.nexts(cfgs)                   the set of model tokens that continue some order of the items
#   w.step(cfgs, t)                 the configurations after token t (tokens are matched as they are, so a label is its label token; the labels are named by the order they are made)
#   w.done(cfgs)                    True where some configuration has written the whole query
#
# A configuration is (boundary, pending tokens): a boundary is the state between two chunks of tokens (the segment of the query's plan, the items of its body still to write, the
# decoder, the naming of the labels, which item made each label); a chunk is the tokens of one item (every inner order of an OR or ALL, as render gives them under mode 'all'), the
# END of a body, or a fixed part. Only the boundaries from which the whole query can be written are kept, so every positive token leads to a complete query.

class Boundary:
    __slots__ = ('seg', 'rem', 'st', 'cr', 'cs', 'key', 'chunks', 'viable')

    def __init__(self, seg, rem, st, cr, cs):
        self.seg, self.rem, self.st, self.cr, self.cs = seg, rem, st, cr, cs
        self.key = (seg, rem, nm_key(st[1]), cr, cs)  # cs: the tokens that each compound item (OR, ALL, IF) was written in; the decoder's late checks depend on them
        self.chunks = None  # [(tokens, next boundary)] of the viable chunks
        self.viable = None


class Unordered:
    def __init__(self, env, q, limit=20000, seconds=10.0):
        self.env, self.q, self.limit = env, q, limit
        self.nseg = len(q.plan)
        self.bounds = {}
        env.total = q.total
        env.rcache = {}
        env.deadline = time.monotonic() + seconds
        try:
            self.root = self.boundary(0, (q.base.fork(), {}), frozenset())
            self.expand(self.root)
        finally:
            env.deadline = None
        self.ok = bool(self.root.viable)
        self.states = len(self.bounds)

    def full(self, seg):
        if seg < self.nseg and isinstance(self.q.plan[seg], Body):
            return frozenset(range(len(self.q.plan[seg].set.items)))
        return frozenset()

    def boundary(self, seg, st, cr, rem=None, cs=frozenset()):
        b = Boundary(seg, self.full(seg) if rem is None else rem, st, cr, cs)
        got = self.bounds.get(b.key)
        if got is not None:
            return got
        if len(self.bounds) >= self.limit:
            raise Overflow()
        self.bounds[b.key] = b
        return b

    def expand(self, b):
        if b.viable is not None:
            return b.viable
        b.chunks = []
        env, q = self.env, self.q
        if b.seg == self.nseg:
            b.viable = True
            return True
        seg = q.plan[b.seg]
        found = []  # (tokens, next boundary)
        if isinstance(seg, Fixed):
            try:
                toks, st2 = step_syms(env, q.marks, b.st, seg.toks)
                found.append((toks, self.boundary(b.seg + 1, st2, frozenset())))
            except Overflow:
                raise
            except Exception:  # noqa: BLE001 - a refusal
                pass
        else:
            for idx in sorted(b.rem):
                if one_waits(seg.set.items, b.rem, idx):
                    continue
                outs, _ = render(env, q.marks, seg.set.items[idx], b.st, 'all')
                for toks, s1 in outs:
                    made = frozenset((g, idx) for g in s1[1] if g not in b.st[1])
                    cs = b.cs | {(idx, toks)} if isinstance(seg.set.items[idx], (Or, All, If)) else b.cs
                    found.append((toks, self.boundary(b.seg, s1, b.cr | made, b.rem - {idx}, cs)))
            if not b.rem:
                try:
                    found.append(((END,), self.boundary(b.seg + 1, step_end(env, b.st), frozenset())))
                except Overflow:
                    raise
                except Exception:  # noqa: BLE001
                    pass
        b.chunks = [(toks, nb) for toks, nb in found if self.expand(nb)]
        b.viable = bool(b.chunks)
        return b.viable

    def start(self):
        return [(self.root, ())] if self.ok else []

    def nexts(self, cfgs):
        out = set()
        for b, pend in cfgs:
            if pend:
                out.add(pend[0])
            else:
                out.update(toks[0] for toks, _ in b.chunks)
        return out

    def step(self, cfgs, t):
        out = {}
        for b, pend in cfgs:
            if pend:
                if pend[0] == t:
                    out[(b.key, pend[1:])] = (b, pend[1:])
            else:
                for toks, nb in b.chunks:
                    if toks[0] == t:
                        out[(nb.key, toks[1:])] = (nb, toks[1:])
        return list(out.values())

    def done(self, cfgs):
        return any(not pend and b.seg == self.nseg for b, pend in cfgs)
