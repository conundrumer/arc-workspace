#!/usr/bin/env python
"""Replays gold programs through the walk of live.py's body: each clause's atoms go through the same frontier and the same gates as a
draw's, and the lines say which gate refuses the program. A pass says that a draw can reach the program, with no word on how likely
that is; the check reads gold, so no draw calls it.

  RAYON_NUM_THREADS=1 <runtime python> -u live_replay.py TASK[:PAIR] ... [--seconds 180] [--models DIR]

PAIR is the index of the gold program in the task's corpus pairs, 0 where left out. A line per program gives hard gates, which no draw
passes, and soft gates, which a draw passes with a small chance (an unjoined atom, a later branch's label left unread). The last line
counts them over programs. A gate's name is the count's name in live.py where it has one.
"""
import argparse
import collections
import gzip
import json
import re
import time

import live
import live_try
from live import ALSO_TOK, KIND_TOK, OUT_TOK, S, SKIP_TOK, TABLES, M, arclog

HEADS = {3: 'ONE', 4: 'SET', 5: 'CHOOSE', 6: 'RIGID_DET', 9: 'IF', 10: 'ALL'}  # the control tokens that live.py has no draw of


class AnyFieldOrder(live.LiveFrontier):
    """A frontier that also walks a record's fields out of position order: a draw writes them in order, and the other order is the same
    program."""

    def candidates(self, n):
        c = super().candidates(n)
        if n.phase == 'fcol':
            opened = n.text[[m.start() for m in re.finditer(r'\(:\d+ \(:', n.text)][-1] + 1:]
            named = {int(x) for x in re.findall(r'\(:(\d+) [^(]', opened)}
            c = c + [self.col_by_pos[p] for p in range(n.need) if p in self.col_by_pos and p not in named]
        return c


class Refused(Exception):
    """A form that the walk can't go through; the message is the shape."""


class Walk:
    """One gold program's walk: its model tokens toks, with the hard and soft gates so far."""

    def __init__(self, run, toks):
        self.run, self.t, self.i, self.hard, self.soft = run, toks, 0, collections.Counter(), collections.Counter()
        self.pg, self.V, self.why = live.Program(), run.V, []

    def kind(self, j):
        return self.V.kind(self.t[j])

    def atom_end(self, j):
        """The index after the atom at index j."""
        t = self.t
        if t[j] == M.NOT:
            j += 1
        if t[j] in M.CMP:
            return j + 3
        j += 1
        while j < len(t) and self.kind(j) == 'column':
            j += 1
            if self.kind(j) == 'column':
                while t[j] != M.END:
                    j += 2
                j += 1
            else:
                j += 1
        return j

    def atom(self, dr, cur, j, end, labs, key):
        """The atom at indices j to end, walked from decoder cur over Drawer dr's frontier: (decoder, text), text None where the grammar
        has no such atom. A key's ^ is walked as *, as a draw makes it."""
        fr, ok = dr.frontier(cur, labs), True
        n = fr.root
        for t in self.t[j:end]:
            t = M.STAR if t == M.CARET else t
            if t not in fr.options(n):
                self.hard['grammar:%s' % n.phase] += 1
                self.why.append('%s at %s%s' % (self.V.name(t), n.text, ' hidden' if t in fr.hidden else ''))
                ok = False
                break
            n = fr.child(n, t)
        if ok:
            return n.dec, fr.render(n)
        f = cur.fork()
        for t in self.t[j:end]:
            f.step(M.STAR if t == M.CARET else t)
        return f, None

    def flat(self, dr, cur, text, end, j, k, labs, prefix, scope, close, one, outer=()):
        """Gates of one atom at index j: (decoder, atom text). close(decoder) says whether the clause or branch can close there."""
        d, a = self.atom(dr, cur, j, end, labs, prefix + tuple(self.t[j:end]))
        if a is None:
            return d, a
        joined = re.search(r'(?<![*\w])L\d+', a) is not None or self.t[j] in M.CMP
        if k > 1 and not joined:
            self.soft[one + 'unjoined'] += 1
        if a in [*outer, *text] or live.opposite(a) in [*outer, *text] or live.clash(a, text, outer):
            self.hard[one + 'repeat'] += 1
            self.why.append('%s beside %s' % (a, text))
        if close is not None and not close(d):
            self.hard[one + 'unsafe'] += 1
        return d, a

    def compound(self, dr, cur, k, labs, text, pfx, scope, nested=False):
        """The OR at self.i: the decoder after its END, its label numbers that the OR keeps local (those of ORs inside it too), its atom
        texts, and (the labels it exports, those every branch reads, those some branch reads) of the labels the OR does not make. An OR
        inside a branch gives atom texts of its own atoms, and the branch has it as one atom."""
        run, t = self.run, self.t
        d = cur.fork()
        d.step(t[self.i])
        self.i += 1
        branches, loc, lost, inner, reads = [], labs, set(), [], []
        while True:
            btext, j = [], 0
            while t[self.i] not in (ALSO_TOK, M.END):
                if t[self.i] in HEADS or (t[self.i] == M.OR and nested):
                    raise Refused('compound inside a compound')
                if t[self.i] == M.OR:
                    j, start = j + 1, self.i
                    if j < 2 or not dr.orc.get('nest'):
                        self.hard['or:nested'] += 1
                    d, hide, atoms, (exp, rall, rany) = self.compound(dr, d, k + j - 1, loc, [*text, *btext], pfx, scope, True)
                    loc += sum(x in (M.STAR, M.CARET) for x in t[start:self.i])
                    lost |= hide
                    inner += atoms
                    dr.fr.hidden = dr.fr.hidden | frozenset(run.ff0.label_tok[i] for i in hide if i in run.ff0.label_tok)
                    btext.append('(OR %s)' % ' '.join(['*L%d' % x for x in exp] + ['L%d' % x for x in rany]))
                    continue
                end, j = self.atom_end(self.i), j + 1
                d, a = self.flat(dr, d, btext, end, self.i, k + j - 1, loc, pfx, scope, run.can_close, 'or:try:', text)
                loc += sum(x in (M.STAR, M.CARET) for x in t[self.i:end])
                self.i = end
                btext.append(a or '')
            if j > run.lim.branch_atoms:
                self.hard['or:branch atoms'] += 1
            branches.append(btext)
            sep = t[self.i]
            self.i += 1
            d = d.fork()
            d.step(sep)
            if sep == M.END:
                break
        if len(branches) not in [x for x, _ in dr.orc['shapes']]:
            self.hard['or:parts'] += 1
        made = [set(re.findall(r'\*L(\d+)', ' '.join(b))) for b in branches]
        read = [set(re.findall(r'(?<![*\w])L(\d+)', ' '.join(b))) for b in branches]
        exported = {x for x in made[0] if all(x in m | r for m, r in zip(made[1:], read[1:]))}
        for b, m, r in zip(branches[1:], made[1:], read[1:]):  # the atom that binds the last exported label
            left = {x for x in exported} - m
            for i, atom in enumerate(b):
                left -= set(re.findall(r'(?<![*\w])L(\d+)', atom)) | set(re.findall(r'\*L(\d+)', atom))
                if not left:
                    if i >= run.lim.bind_atoms:
                        self.soft['or:bound late'] += 1
                    break
        if made[0] - read[0] - exported and dr.place != 'key':
            self.hard['or:first branch keeps an unread label'] += 1
        if any(m - r for m, r in zip(made[1:], read[1:])) and dr.place != 'key':
            self.soft['or:later branch leaves a label unread'] += 1
        every = {int(x) for m in made for x in m}
        rd = [{int(x) for x in r} for r in read]
        atoms = [a for b in branches for a in b if not a.startswith('(OR ')] + inner
        return d, every - {int(x) for x in exported} | lost, atoms, ({int(x) for x in exported}, set.intersection(*rd) - every, set.union(*rd) - every)

    def body(self, pg, dr, kind, cur, nlab, keys=()):
        """The body at self.i through its END: gates as in Run.body. (decoder before the END, atom texts, types in scope)."""
        run, t, top = self.run, self.t, run_top(self.run, kind)
        text, scope, k, pfx, labs, tb = [], [], 0, (), nlab, None
        dr.want = set(keys)
        dr.drawn = []
        while t[self.i] != M.END:
            if t[self.i] in HEADS:
                raise Refused('%s in a %s' % (HEADS[t[self.i]], kind))
            k += 1
            if t[self.i] == M.OR:
                if dr.orc is None:
                    raise Refused('OR in a %s' % kind)
                cur, hide, atoms, _ = self.compound(dr, cur, k, labs, text, pfx, scope)
                labs = nlab + sum(x in (M.STAR, M.CARET) for x in self.t[self.start:self.i])
                dr.fr.hidden = dr.fr.hidden | frozenset(run.ff0.label_tok[i] for i in hide if i in run.ff0.label_tok)
                dr.drawn += atoms
                if kind == 'INIT':
                    seen = run.label_types(dr, atoms)
                    scope = list(scope) + [x for y, x in seen.items() if int(y[1:]) not in hide]
                    text.append('(OR)')
                    continue
                tb = run.table(dr.fr, cur, pg)[0]
                sm = S.summary(tb)
                if sm is not None and sm['empty_inputs']:
                    self.hard['or:empty'] += 1
                if not run.can_end(cur):
                    self.hard['or:unsafe'] += 1
                text.append('(OR)')
                scope = [str(x) for x in tb['types']] if tb is not None else scope
                continue
            end = self.atom_end(self.i)
            d, a = self.flat(dr, cur, text, end, self.i, k, labs, pfx, scope, run.can_end if kind != 'INIT' else None, 'try:')
            labs += sum(x in (M.STAR, M.CARET) for x in t[self.i:end])
            pfx += tuple(t[self.i:end])
            self.i, cur = end, d
            text.append(a or '')
            dr.drawn.append(a or '')
            if kind != 'INIT':
                fr = dr.frontier(cur, labs)
                tb = run.table(fr, cur, pg)[0]
                sm = S.summary(tb)
                if sm is not None and sm['empty_inputs']:
                    self.hard['try:empty'] += 1
                scope = [str(x) for x in tb['types']] if tb is not None else scope
            elif a:
                scope += list(run.label_types(dr, [a]).values())
        if k > top:
            self.hard['body: no stop in %d atoms' % top] += 1
        if k == 0:
            self.hard['empty body'] += 1
        if k == 1 and kind in S.MIN2_KINDS and text[0] != '(OR)' and not S.one_call(dr, text):
            self.hard['gate:one atom'] += 1
        return cur, text, scope

    def rule(self, kind, f):
        pg, run, t = self.pg, self.run, self.t
        if self.V.kind(t[self.i]) == 'proposer':
            if kind == 'RULE':
                raise Refused('RULE by a proposer')
            if self.V.name(t[self.i]) not in run.pri['proposers']:
                self.hard['no proposer'] += 1
            f = f.fork()
            f.step(t[self.i])
            self.i += 1
            if t[self.i] != M.END:
                raise Refused('%s in a DET' % HEADS.get(t[self.i], 'mark'))
            self.i += 1
            return run.end(pg, f)
        self.start = self.i
        cur = self.body(pg, run.drawer(pg, kind, f), kind, f, 0)[0]
        self.i += 1
        return run.end(pg, cur)

    def init(self, f):
        pg, run, t = self.pg, self.run, self.t
        name = self.V.name(t[self.i])
        if name not in run.pri['comps']:
            self.hard['no component'] += 1
        f = f.fork()
        forced = f.step(t[self.i])[0]
        self.i += 1
        run.declared(pg, forced)
        slots = [M.slot_no(self.V.name(x)) for x in forced if self.V.kind(x) == 'relation']
        pg.names = pg.names | {'&r%d' % s: '&r%d.%d' % (slots[0], i) for i, s in enumerate(slots)}
        params, ports = run.pri['comp_ports'][name]
        nlab, keys, fields = 0, {}, {}
        if t[self.i] == SKIP_TOK:
            f = f.fork()
            f.step(SKIP_TOK)
            self.i += 1
        else:  # the key
            self.start = self.i
            dr = run.drawer(pg, 'INIT', f, 'key')
            self.body(pg, dr, 'INIT', f, 0)
            carets = [x for x in t[self.start:self.i] if x in (M.STAR, M.CARET)]
            where = [i for i, x in enumerate(carets) if x == M.CARET]
            if not where:
                raise Refused('key of no ^ label')
            g = f.fork()
            for x in t[self.start:self.i]:
                g.step(x)
            g.step(M.END)
            self.i += 1
            f, nlab = g, len(carets)
            types = run.label_types(dr, dr.drawn)
            keys = {run.ff0.label_tok[n]: types.get('L%d' % n) for n in where}
        left = []
        for pname, cols in ports:
            if t[self.i] == SKIP_TOK:
                f = f.fork()
                f.step(SKIP_TOK)
                self.i += 1
                left.append((pname, cols))
                continue
            if t[self.i] in KIND_TOK.values() or t[self.i] == OUT_TOK:
                break
            f, nlab = self.port(f, name, pname, cols, params, nlab, keys, fields)
        for pname, cols in left if keys else ():  # the ports outside the key group
            if t[self.i] == SKIP_TOK:
                f = f.fork()
                f.step(SKIP_TOK)
                self.i += 1
            elif t[self.i] not in (*KIND_TOK.values(), OUT_TOK, *HEADS):
                f, nlab = self.port(f, name, pname, cols, params, nlab, {}, fields)
        while t[self.i] == SKIP_TOK:
            f = f.fork()
            f.step(SKIP_TOK)
            self.i += 1
        if t[self.i] not in (*KIND_TOK.values(), OUT_TOK, *HEADS):
            raise Refused('keyed INIT with a port outside the key')
        run.close(pg, f)
        return f

    def head_column(self, g):
        """The head column at self.i, walked from decoder g: (decoder, its labels). A record's fields go in order, each with its token."""
        t, labs, record = self.t, [], False
        while t[self.i] != M.END:
            if self.kind(self.i) == 'column':
                record = True
            else:
                labs.append(t[self.i])
            g = g.fork()
            g.step(t[self.i])
            self.i += 1
        for _ in range(1 + (record or len(labs) > 1)):
            g = g.fork()
            g.step(M.END)
            self.i += 1
        return g, labs

    def port(self, f, comp, pname, cols, params, nlab, keys, fields):
        pg, run, t = self.pg, self.run, self.t
        dr = run.drawer(pg, 'INIT', f, 'port')
        dr.want_types = frozenset(x for x in keys.values() if x)
        dr.fr.hidden = frozenset(run.ff0.label_tok[i] for i in range(nlab)) - set(keys)
        self.start = self.i
        cur, text, scope = self.body(pg, dr, 'INIT', f, nlab, keys)
        ptoks = t[self.start:self.i]
        if keys and not set(keys) & set(ptoks):
            raise Refused('keyed port reads no key label')
        g = cur.fork()
        g.step(M.END)
        self.i += 1
        made = list(range(nlab, nlab + ptoks.count(M.STAR)))
        nlab = made[-1] + 1 if made else nlab
        bound, types, before = [], run.label_types(dr, dr.drawn), dict(fields)
        for c, ty in cols:
            g, labs = self.head_column(g)
            if not labs:
                continue
            bound.append((c, ty))
            if not set(labs) <= {run.ff0.label_tok.get(i) for i in made}:
                raise Refused('head names a key label')
            if len(labs) > 1 and len(labs) not in run.pri.get('head_labels', {}).get((comp, pname, c), ()) and ty not in fields:
                self.hard['head: record size'] += 1
            if ty in params and ty not in fields:
                fields[ty] = [types.get(self.V.name(x), live.ANY_TYPE) for x in labs]
        need = run.head_need(bound, params, before)
        if need and live.ANY_TYPE not in scope and any(not x & set(scope) for x in need):
            self.hard['gate:port head'] += 1
            self.why.append('%s need %s scope %s %s' % (pname, need, scope, text))
        if not run.port_can_end(cur):
            self.hard['gate:unsafe'] += 1
        return g, nlab

    def out(self, dec):
        run, t = self.run, self.t
        rtok, p, c = t[self.i + 1], t[self.i + 2], t[self.i + 4]
        if t[self.i + 6] != M.END:
            raise Refused('OUT of two atoms')
        first = run.out_pairs(dec, rtok, run.lim.out_pairs)
        if (p, c) not in first:
            self.hard['out: pair past the cap'] += 1

    def go(self):
        run, pg, dec = self.run, self.pg, self.run.root.fork()
        while True:
            head = self.t[self.i]
            if head == OUT_TOK:
                self.out(dec)
                return
            if head in HEADS:
                raise Refused('form ' + HEADS[head])
            self.i += 1
            pg.forms = S.strata.sexprs(dec.program_form())
            pg.new = []
            kind = next(k for k, v in KIND_TOK.items() if v == head)
            f = run.open_form(pg, dec, kind)
            dec = self.init(f) if kind == 'INIT' else self.rule(kind, f)


def run_top(run, kind):
    return run.lim.port_atoms if kind == 'INIT' else run.lim.max_atoms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tasks', nargs='+')
    ap.add_argument('--seconds', type=float, default=180)
    ap.add_argument('--models', default=live_try.P.SAMPLER_DATA + '/models')
    a = ap.parse_args()
    sampler = live.Sampler(a.models, ())
    live.LiveFrontier = AnyFieldOrder
    tally, end = collections.Counter(), time.monotonic() + a.seconds
    for item in a.tasks:
        if time.monotonic() >= end:
            tally['not reached'] += 1
            continue
        task, _, pair = item.partition(':')
        with gzip.open(live.S.CORPUS + task + '/pairs.jsonl.gz', 'rt') as f:
            sexp = json.loads(list(f)[int(pair or 0)])['gold_sexp']
        sess, d, _ = live_try.session_of(task)
        run = live.Run(sampler.pri, sess, 0, time.monotonic() + 3600, d, live.Limits())
        ids, model, _ = arclog.StudyProgram.from_sexp(sexp, sess.settings).decode_stream()
        walk = Walk(run, [t for t, m in zip(ids, model) if m])
        t0, shape = time.monotonic(), None
        try:
            walk.go()
        except Refused as e:
            shape = str(e)
        except (arclog.Refusal, arclog.Fault, live.Drop) as e:
            shape = 'the walk stopped: %s: %s' % (type(e).__name__, re.sub(r'\d+', 'N', str(e))[:90])
        tally['programs'] += 1
        tally['pass' if not (walk.hard or shape) else 'shape' if shape else 'gate'] += 1
        tally['pass with soft gates'] += not walk.hard and not shape and bool(walk.soft)
        tally.update('shape:' + x for x in [shape] if x)
        tally.update('hard:' + x for x in walk.hard)
        tally.update('soft:' + x for x in walk.soft)
        print('%s %.1fs shape=%s hard=%s soft=%s %s' % (item, time.monotonic() - t0, shape, dict(walk.hard), dict(walk.soft), walk.why[:3] if walk.why else ''), flush=True)
    print(dict(sorted(tally.items())), flush=True)


if __name__ == '__main__':
    main()
