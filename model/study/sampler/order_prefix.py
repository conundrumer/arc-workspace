#!/usr/bin/env python
"""The `ordered` plan's order rule (order.py) in prefix form: at a writing point, the next tokens that no `ordered` path continues with.

    rule = rule_of(run)              # one per Run
    keep = rule.keep(pt, ids)        # bool over ids: False where the rule removes the id
    fl = rule.floors(pt)             # [Floor] of the open sets of pt, [] where no set is open, None where the query has no sets; rule.floors(pt, t): of the point after token t
    rule.below(bound, t)             # whether first token t is below a Floor's bound, so that the bound bars it

The `ordered` rule writes the items of a set (the atoms of a body, the branches of an OR, the atoms of a branch, the two lists of an ALL) one at a time: at each step, the item of least key
among the items that the decoder accepts at that step. The key of an item at a state is its model tokens under the state's naming: a label made before the state is its label token; a label
made after it is `*` (or `^`) where the item first names it, and then the label token of the state's next fresh index. So a written order is the rule's where, for each two items p and x of
one set, p written first, x is refused at the state before p or x's key at that state is not below p's key. Equal keys are a tie, and both orders stay.

The rule tests that condition as the tokens come, at the innermost open set:
  - A token that starts an item is removed where it is below the first token of an earlier item of the set, and the item is accepted at the state before that earlier item.
  - A token that goes on with an open atom is removed where it makes the atom's key at the state before an earlier item fall below that item's key, and the atom is accepted there.
  - A token that closes an atom is removed where the atom fails the condition against an earlier item (order.render at the earlier state).
  - The END of an OR or an ALL is removed where the written item is not one of the ways that order.render writes it from its first state, or it fails the condition against an earlier
    item of its set. The END of a body is removed where the written body is not one of the ways that order.walk_set writes it from the body's first state.
Where a label was made between the earlier item and the open one, the open item can be refused at the earlier state by tokens still to come (a NOT, a comparison or a compound that reads
that label, an input site of a lib relation, a site that takes a `^` label): the first two tests keep the token there, and the tests at the close decide.

A DEMONSTRATED query, a proposer body and the group tokens of an INIT or a RIGID_DET have no sets: the rule keeps every id there. A test that passes SECONDS keeps the token.
"""
import bisect
import collections
import dataclasses
import time

import numpy as np

import live
import order
import writer
from live import ALSO_TOK, M, arclog
from writer import Phase, core_of

STAR, CARET, END, NOT, OR_TOK, ZERO = M.STAR, M.CARET, M.END, M.NOT, M.OR, M.ZERO
EQ = M.CMP[0]
CMP = frozenset(M.CMP)
SYMMETRIC = (M.CMP[0], M.CMP[1])
SECONDS = 2.0  # the budget of one test at a close


class _List:
    """An open set of items: kind 'body', 'branch', 'dom' (an ALL's first list), 'allbody', 'if0', 'if1' or 'if2'. items: [(start, end, kind)] of its closed items, token indexes
    (end excluded), kind 'atom', 'not', 'cmp', 'one', 'or', 'all' or 'if'. cur: the start of the open item, and cur_kind its kind."""
    __slots__ = ('kind', 'start', 'items', 'cur', 'cur_kind')

    def __init__(self, kind, start):
        self.kind, self.start, self.items, self.cur, self.cur_kind = kind, start, [], None, None


class _Or:
    """An open OR: branches [(start, end)] of its closed branches, cur the start of the open branch."""
    __slots__ = ('start', 'branches', 'cur')

    def __init__(self, start):
        self.start, self.branches, self.cur = start, [], start


def parse(core, kind, tokens):
    """The open sets of a query's model tokens (the kind token first), outermost first: a list of _List and _Or; [] where no set is open (between the bodies of an INIT or a RIGID_DET,
    after a body's END); None for a proposer body."""
    rel, col, lab = core.is_rel, core.is_column, core.is_label
    ALLT, IFT, ONET = core.ALL, core.IF, core.ONE
    starts = (NOT, OR_TOK, ALLT, IFT, ONET)
    stack = []
    if kind in ('RULE', 'DET'):
        if len(tokens) > 1 and core.kind[tokens[1]] == 'proposer':
            return None
        stack.append(_List('body', 1))
    atom = one = notwait = due = rec = False
    need = 0
    for i in range(1, len(tokens)):
        t = tokens[i]
        if not stack:
            if kind in ('RULE', 'DET'):
                return []
            if not (rel[t] or t in CMP or t in starts):  # a group token of an INIT or a RIGID_DET
                continue
            stack.append(_List('body', i))
        top = stack[-1]
        if one:  # a ONE mark: its labels, then its END
            if t == END:
                top.items.append((top.cur, i + 1, 'one'))
                top.cur, one = None, False
            continue
        if atom:
            if notwait:
                if rel[t]:
                    notwait = False
                    continue
            elif due:
                if col[t]:
                    rec = True
                else:
                    due = False
                continue
            elif need > 0:
                need -= 1
                continue
            elif rec:
                if col[t]:
                    due = True
                else:
                    rec = False
                continue
            elif col[t]:
                due = True
                continue
            elif t in (STAR, CARET, ZERO) or lab[t]:
                continue
            top.items.append((top.cur, i, top.cur_kind))
            top.cur, atom = None, False
        if rel[t]:
            top.cur, top.cur_kind, atom, due, rec, need = i, 'atom', True, False, False, 0
        elif t == NOT:
            top.cur, top.cur_kind, atom, notwait, due, rec, need = i, 'not', True, True, False, False, 0
        elif t in CMP:
            top.cur, top.cur_kind, atom, due, rec, need = i, 'cmp', True, False, False, 2
        elif t == OR_TOK:
            top.cur, top.cur_kind = i, 'or'
            stack.append(_Or(i + 1))
            stack.append(_List('branch', i + 1))
        elif t == ALLT:
            top.cur, top.cur_kind = i, 'all'
            stack.append(_List('dom', i + 1))
        elif t == IFT:
            top.cur, top.cur_kind = i, 'if'
            stack.append(_List('if0', i + 1))
        elif t == ONET:
            top.cur, top.cur_kind, one = i, 'one', True
        elif t == ALSO_TOK and top.kind == 'branch':
            stack.pop()
            o = stack[-1]
            o.branches.append((o.cur, i))
            o.cur = i + 1
            stack.append(_List('branch', i + 1))
        elif t == END:
            if top.kind == 'body':
                stack.pop()
            elif top.kind == 'branch':
                stack.pop()
                o = stack.pop()
                o.branches.append((o.cur, i))
                p = stack[-1]
                p.items.append((p.cur, i + 1, 'or'))
                p.cur = None
            elif top.kind in ('dom', 'if0', 'if1'):
                stack[-1] = _List({'dom': 'allbody', 'if0': 'if1', 'if1': 'if2'}[top.kind], i + 1)
            else:  # allbody, if2
                stack.pop()
                p = stack[-1]
                p.items.append((p.cur, i + 1, p.cur_kind))
                p.cur = None
    return stack


@dataclasses.dataclass(frozen=True, slots=True)
class Floor:
    """The bound that the order puts on the first token of the next item started in one open set. depth: the set's place among the open sets, 0 outermost. kind: the set's kind
    (_List.kind). rel: the bound for an atom of a relation whose sites all take a new label (not a lib relation), or None for no bound; it can fall only where a `^` label is made
    before that start. other: the bound for an atom of a lib relation, NOT, a comparison, OR and ALL, or None; it holds while no label is made before that start, and a label
    made in between can lower it. The rule removes a first token below the bound (unless the decoder refuses it at the state before the earlier item that sets the bound); a
    first token above it is free of the bound; at the bound, the item's later tokens decide, since a key is the item's whole token string."""
    depth: int
    kind: str
    rel: int | None
    other: int | None


class Rule:
    def __init__(self, run):
        self.run = run
        self.core = core_of(run)
        self.env = order.Env(run.session)
        self.label_tok = self.env.run.ff0.label_tok  # label index -> token
        self.label_idx = {t: k for k, t in self.label_tok.items()}
        self.stats = collections.Counter()
        self.free = self.core.is_rel & np.array([k not in writer.LIB_KINDS for k in self.core.kind])  # relations whose sites all take a new label (a lib relation's input sites take bound labels alone)

    # ---- the facts of a point

    def info(self, pt):
        got = pt.memo.get('order_prefix')
        if got is None:
            got = pt.memo['order_prefix'] = self._info(pt.kind, pt.tokens, pt.track)
        return got

    def _info(self, kind, tokens, T):
        if T.form or kind not in ('RULE', 'DET', 'INIT', 'RIGID_DET'):
            return None
        stack = parse(self.core, kind, tokens)
        if stack is None:
            return None
        mk = [i for i, t in enumerate(tokens) if t in (STAR, CARET)]
        return dict(stack=stack, mk=mk)

    @staticmethod
    def made_before(info, i):
        """The count of labels made before token index i."""
        return bisect.bisect_left(info['mk'], i)

    def late_caret(self, info, tokens, lo, hi):
        """Whether a label of index lo..hi-1 was made by `^`."""
        return any(tokens[info['mk'][k]] == CARET for k in range(lo, hi))

    def rendered(self, info, tokens, a, b, mj):
        """(tokens, assign) of tokens[a:b] at a state with mj labels made: labels of index mj or above are named anew (assign: label index -> new index)."""
        out, assign, nxt = [], {}, mj
        lab = self.core.is_label
        for p in range(a, b):
            t = tokens[p]
            if t in (STAR, CARET):
                assign[self.made_before(info, p)] = nxt
                nxt += 1
                out.append(t)
            elif lab[t]:
                k = self.label_idx[t]
                if k < mj:
                    out.append(t)
                elif k in assign:
                    out.append(self.label_tok[assign[k]])
                else:
                    assign[k] = nxt
                    nxt += 1
                    out.append(tokens[info['mk'][k]])
            else:
                out.append(t)
        return out, assign

    def render_tok(self, info, tokens, t, mj, assign):
        if self.core.is_label[t]:
            k = self.label_idx[t]
            if k < mj:
                return t
            if k in assign:
                return self.label_tok[assign[k]]
            return tokens[info['mk'][k]]
        return t

    # ---- the rule

    def keep(self, pt, ids):
        out = np.ones(len(ids), bool)
        T = pt.track
        if T.where != 'body' or not len(ids):
            return out
        info = self.info(pt)
        if not info or not info['stack']:
            return out
        L = info['stack'][-1]
        if not isinstance(L, _List):
            return out
        ph = pt.place.phase
        core = self.core
        if ph in (Phase.VALUE, Phase.OPERAND, Phase.FIELD):
            if L.cur is not None:
                out &= self.go_on(pt, info, L, ids)
                if ph == Phase.OPERAND:
                    out &= self.operands(pt, ids)
            return out
        if ph == Phase.ATOM_START and L.cur is not None and L.cur_kind == 'not':  # the relation of a NOT atom
            out &= self.go_on(pt, info, L, ids)
            return out
        if ph not in (Phase.COLUMN, Phase.ATOM_START):
            return out
        closing = np.ones(len(ids), bool)
        items = list(L.items)
        if ph == Phase.COLUMN and L.cur is not None:
            from lookahead import closers
            closing = closers(core, ids)
            if (~closing).any():
                sub = self.go_on(pt, info, L, ids[~closing])
                out[np.flatnonzero(~closing)[~sub]] = False
            if closing.any():
                x = (L.cur, len(pt.tokens), L.cur_kind)
                if not self.pair_ok(pt, info, L, x, pt.tokens):
                    out[closing] = False
                    return out
                items.append(x)
        from lookahead import starts
        st = starts(core, ids) & closing & out
        if st.any() and items:
            sub = self.new_ok(pt, info, items, ids[st])
            out[np.flatnonzero(st)[~sub]] = False
        e = closing & out & (ids == END)
        if e.any() and not self.end_ok(pt, info):
            out[e] = False
        return out

    def operands(self, pt, ids):
        """The second operand of `=` or `!=` after a label: the operands of a symmetric comparison of two labels stand in the order of their label tokens, and a new label stands first."""
        keep = np.ones(len(ids), bool)
        oa = pt.open_atom
        if pt.track.need == 1 and len(oa) == 2 and oa[0] in SYMMETRIC and self.core.is_label[oa[1]]:
            keep &= ~((ids == STAR) | (ids == CARET) | (self.core.is_label[ids] & (ids < oa[1])))
        return keep

    def go_on(self, pt, info, L, ids):
        """Which ids, as the next token of the open atom of set L, keep the atom's key from falling below an earlier item's key at the state before that item."""
        keep = np.ones(len(ids), bool)
        tokens = pt.tokens
        a, n = L.cur, len(tokens)
        ma = self.made_before(info, a)
        for s, e, kd in L.items:
            if kd == 'one' or L.cur_kind == 'one':
                continue
            K = tokens[s:e]
            mj = self.made_before(info, s)
            late = ma > mj
            r, assign = self.rendered(info, tokens, a, n, mj)
            d = next((i for i in range(min(len(r), len(K))) if r[i] != K[i]), None)
            if d is not None or len(r) >= len(K):
                continue  # above K, or decided below it before this token (the close decides)
            kn = K[len(r)]
            rt = np.array([self.render_tok(info, tokens, int(t), mj, assign) for t in ids], np.int64)
            low = rt < kn
            if not low.any():
                continue
            if late and (L.cur_kind != 'atom' or not self.free[tokens[a]] or self.late_caret(info, tokens, mj, ma)):
                continue
            dec = writer.dec_at(pt, s).fork()
            try:
                for x in r:
                    dec.step(x)
            except arclog.Refusal:
                continue  # the atom is refused at that state
            adm = np.array(dec.admits([int(x) for x in rt[low]]), bool)
            keep[np.flatnonzero(low)[adm]] = False
        return keep

    def new_ok(self, pt, info, items, ids):
        """Which ids, starting an item of a set whose earlier items are `items`, are not below an earlier item's first token where the item is accepted at the state before it."""
        keep = np.ones(len(ids), bool)
        tokens = pt.tokens
        n = len(tokens)
        mn = self.made_before(info, n)
        free = self.free[ids]
        for s, e, kd in items:
            if kd == 'one':
                continue
            low = (ids < tokens[s]) & (ids != self.core.ONE)
            if not low.any():
                continue
            mj = self.made_before(info, s)
            if mn > mj:  # labels were made since: only an atom of a relation that takes a new label at each site is decided at its first token, and not where a `^` label was made
                if self.late_caret(info, tokens, mj, mn):
                    continue
                low &= free
                if not low.any():
                    continue
            adm = np.array(writer.dec_at(pt, s).fork().admits([int(x) for x in ids[low]]), bool)
            keep[np.flatnonzero(low)[adm]] = False
        return keep

    # ---- the tests at a close

    def symbolic(self, info, tokens, a, b):
        """The tokens a..b-1 in order.py's form: a label as order.sym of its label token, `*` and `^` with the label they make."""
        out = []
        for p in range(a, b):
            t = tokens[p]
            if t in (STAR, CARET):
                out.append(order.sym(self.label_tok[self.made_before(info, p)]))
            elif self.core.is_label[t]:
                out.append(order.sym(t))
            else:
                out.append(t)
        return out

    def setup(self, info, tokens, b):
        """(marks, total) of the labels of tokens[:b], and the env ready for a test."""
        env = self.env
        marks = {self.label_tok[k]: tokens[i] for k, i in enumerate(info['mk']) if i < b}
        total = collections.Counter()
        for p in range(1, b):
            t = tokens[p]
            if t in (STAR, CARET):
                total[self.label_tok[self.made_before(info, p)]] += 1
            elif self.core.is_label[t]:
                total[t] += 1
        env.total = total
        env.rcache = {}
        env.lookahead = False
        env.deadline = time.monotonic() + SECONDS
        return marks, total

    def naming(self, info, i):
        return {self.label_tok[k]: self.label_tok[k] for k in range(self.made_before(info, i))}

    def set_needs(self, item, total):
        if isinstance(item, order.All):
            inside = order.labels_of(item)
            item.needs = frozenset(g for g in inside if total[g] > inside[g])
        for sub in self.subs(item):
            for it in sub.items:
                self.set_needs(it, total)

    @staticmethod
    def subs(item):
        if isinstance(item, order.Or):
            return item.branches
        if isinstance(item, order.All):
            return (item.dom, item.body)
        if isinstance(item, order.If):
            return (item.test, item.then, item.els)
        return ()

    def item_of(self, info, tokens, a, b, total):
        s = self.symbolic(info, tokens, a, b)
        item, j = order.parse_item(self.env, s, 0)
        if j != len(s):
            raise order.ParseError('the item ends early')
        self.set_needs(item, total)
        return item

    def pair_ok(self, pt, info, L, x, tokens):
        """Whether the closed item x = (start, end, kind) of set L passes the condition against each earlier item of L. tokens: pt's tokens, and the token after the point where
        x ends with it."""
        a, b, kd = x
        if kd == 'one':
            return True
        ma = self.made_before(info, a)
        item = marks = None
        for s, e, kj in L.items:
            if kj == 'one':
                continue
            K = tuple(tokens[s:e])
            mj = self.made_before(info, s)
            if ma == mj:  # no label made between: the item is written at that state as it stands, and the decoder takes it there as it took it here
                if tuple(tokens[a:b]) < K:
                    self.stats['pair below'] += 1
                    return False
                continue
            if tuple(self.rendered(info, tokens, a, b, mj)[0][:1]) > K[:1]:
                continue
            try:
                if item is None:
                    marks, total = self.setup(info, tokens, b)
                    item = self.item_of(info, tokens, a, b, total)
                outs, _ = order.render(self.env, marks, item, (writer.dec_at(pt, s), self.naming(info, s)), 'min')
            except order.Overflow:
                self.stats['pair overflow'] += 1
                continue
            except Exception:  # noqa: BLE001 - an item that order.py cannot read: no test
                self.stats['pair error'] += 1
                continue
            finally:
                self.env.deadline = None
            if outs and min(o[0] for o in outs) < K:
                self.stats['pair below (renamed)'] += 1
                return False
        return True

    def end_ok(self, pt, info):
        """Whether END may close the innermost open set: for a body, the written body is one of order.walk_set's; for an ALL or an OR, the item is one of order.render's from its
        first state, and it passes the condition against the earlier items of its set."""
        got = pt.memo.get('order_prefix_end')
        if got is None:
            got = pt.memo['order_prefix_end'] = self._end_ok(pt, info)
        return got

    def _end_ok(self, pt, info):
        stack, tokens = info['stack'], pt.tokens
        L, n = stack[-1], len(tokens)
        if L.kind in ('dom', 'if0', 'if1'):
            return True
        if L.kind == 'body':
            return self.body_ok(pt, info, L)
        P = stack[-3] if L.kind == 'branch' else stack[-2]
        a = P.cur
        written = tuple(tokens[a:n]) + (END,)
        toks = tokens + (END,)
        try:
            marks, total = self.setup(info, toks, n + 1)
            item = self.item_of(info, toks, a, n + 1, total)
            outs, _ = order.render(self.env, marks, item, (writer.dec_at(pt, a), self.naming(info, a)), 'min')
        except order.Overflow:
            self.stats['end overflow'] += 1
            return True
        except Exception:  # noqa: BLE001
            self.stats['end error'] += 1
            return True
        finally:
            self.env.deadline = None
        if outs and written not in {o[0] for o in outs}:
            self.stats['compound not canonical'] += 1
            return False
        return self.pair_ok(pt, info, P, (a, n + 1, P.cur_kind), toks)

    def body_ok(self, pt, info, L):
        tokens, n = pt.tokens, len(pt.tokens)
        a = L.start
        written = tuple(tokens[a:n])
        env = self.env
        try:
            marks, total = self.setup(info, tokens, n)
            s = self.symbolic(info, tokens, a, n) + [END]
            items, j = order.parse_items(env, s, 0, (END,))
            if j != len(s) - 1:
                return True
            for it in items:
                self.set_needs(it, total)
            st = (writer.dec_at(pt, a), self.naming(info, a))
            k = (lambda s2: order.after(env, None, s2, END))
            try:  # as order.ordered: the plain rule, and where it is stuck or no stream it gives can end the body, the rule with a lookahead
                outs = [o for o in order.walk_set(env, marks, order.Set(items, L.kind), st, 'min', k=k) if k(o[1])]
            except order.Stuck:
                outs = []
            if not outs:
                self.stats['body lookahead'] += 1
                env.lookahead = True
                env.rcache = {}
                outs = [o for o in order.walk_set(env, marks, order.Set(items, L.kind), st, 'min', k=k) if k(o[1])]
        except order.Overflow:
            self.stats['body overflow'] += 1
            return True
        except order.Stuck:
            self.stats['body stuck'] += 1
            return True
        except Exception:  # noqa: BLE001
            self.stats['body error'] += 1
            return True
        finally:
            env.deadline = None
            env.lookahead = False
        if written not in {o[0] for o in outs}:
            self.stats['body not canonical'] += 1
            return False
        return True

    # ---- floors

    def has_sets(self, pt):
        """Whether the query of pt has sets that the rule orders: False for a DEMONSTRATED query and a proposer body, where the rule keeps every id."""
        return self.info(pt) is not None

    @staticmethod
    def below(bound, t):
        """Whether first token t is below a Floor's bound (rel or other), so that the bound bars it. False where the bound is None, at the bound (the later tokens decide) and above it.
        The rule keeps a barred start where the decoder refuses it at the state before the earlier item that sets the bound; keep(pt, ids) gives that exact verdict."""
        return bound is not None and int(t) < bound

    def floors(self, pt, t=None):
        """[Floor] of the open sets of pt, outermost first; with t, of the point after token t (no step is made). [] where no set is open (after a body's END, between the bodies
        of an INIT or a RIGID_DET); None where the query has no sets (has_sets)."""
        if not self.has_sets(pt):
            return None
        tokens = pt.tokens if t is None else pt.tokens + (int(t),)
        info = self.info(pt) if t is None else self._info(pt.kind, tokens, pt.track)
        if info is None:
            return None
        n = len(tokens)
        mn = self.made_before(info, n)
        out = []
        lists = [f for f in info['stack'] if isinstance(f, _List)]
        for depth, L in enumerate(lists):
            items = list(L.items) + ([(L.cur, n, L.cur_kind)] if L.cur is not None else [])
            rel = other = None
            for s, e, kd in items:
                if kd == 'one':
                    continue
                mj = self.made_before(info, s)
                f = tokens[s]
                if mn == mj:  # no label made since that item
                    other = f if other is None else max(other, f)
                if mn == mj or not self.late_caret(info, tokens, mj, mn):
                    rel = f if rel is None else max(rel, f)
            out.append(Floor(depth, L.kind, rel, other))
        return out


def rule_of(run):
    got = run.__dict__.get('order_prefix_rule')
    if got is None:
        got = run.order_prefix_rule = Rule(run)
    return got
