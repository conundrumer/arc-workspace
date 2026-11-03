#!/usr/bin/env python3
"""Trace the source of each Ident column through arclog forms, from clause text alone.

A source is the form that makes an Ident value: a Connectivity, Enclosure or Quotient INIT, or a PanelCombine DET.
The tracer holds a set of sources per column only so that it can report a union of two sources (a column whose set has
more than one source), which the checker refuses. Two sites of one label meet, and a label whose sets don't meet is a
cross-source join.

The tracer reads the registry for the columns of type parameters. Forms it can't read (CHOOSE, RIGID_DET, DEMONSTRATED)
give their columns no set, so it undercounts where such forms pass Idents on.
"""
import os
import re

REPO = '/Users/davidlu/code/arc-workspace'
MAKERS = {('Connectivity', 'component'), ('Enclosure', 'enclosed'), ('Quotient', 'class')}


def sexprs(text):
    toks = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    out, stack = [], []
    for t in toks:
        if t == '(':
            stack.append([])
        elif t == ')':
            e = stack.pop()
            (stack[-1] if stack else out).append(e)
        else:
            (stack[-1] if stack else out).append(t)
    return out


def load_components(path=REPO + '/engine/lib/registry.sexpr'):
    text = '\n'.join(x for x in open(path) if not x.lstrip().startswith(';'))
    comps = {}
    for e in sexprs(text):
        if e and e[0] == 'component':
            c = dict(params=set(), inputs={}, outputs={})
            for part in e[3:]:
                if part[0] == 'type-parameters':
                    c['params'] = {p if isinstance(p, str) else p[0] for p in part[1:]}
                elif part[0] in ('inputs', 'outputs'):
                    for port in part[1:]:
                        cols = {}
                        for x in port[1:]:
                            if isinstance(x, list) and len(x) == 2 and isinstance(x[1], str) and x[0] not in ('copies', 'default'):
                                cols[x[0]] = x[1]
                        c[part[0]][port[0]] = cols
            comps[e[1]] = c
    return comps


COMPONENTS = load_components()


def strip(x):
    return x[1:] if x[0] in '*^' else x


class Form:
    __slots__ = ('kind', 'name', 'cols', 'comp', 'binds', 'keys', 'known', 'text', 'bad')

    def __init__(self, kind, name, text):
        self.kind, self.name, self.text = kind, name, text
        self.cols, self.comp, self.binds, self.keys, self.known, self.bad = {}, None, {}, {}, True, []


class Tracer:
    def __init__(self):
        self.forms = {}
        self.unknown_reads = 0
        self.unread_kinds = {}

    # ---- reading one atom

    def site_args(self, site):
        """(column, [args]) of a site list."""
        return site[0][1:], site[1:]

    def read(self, atom, sites, ctx):
        """Adds to sites {label: [set]} the sources of each label of the atom."""
        rel = atom[0]
        if not rel.startswith('&'):
            return
        name, _, port = rel.partition('.')
        f = self.forms.get(name)
        if f is None:
            self.unknown_reads += 1
            return
        for s in atom[1:]:
            if not (isinstance(s, list) and s and s[0].startswith(':')):
                continue
            col, args = self.site_args(s)
            for path, lab in self.flat(args):
                got = self.column(f, port, col, path)
                if got and lab != '0':
                    sites.setdefault(strip(lab), []).append(got)
                    ctx.setdefault('reads', []).append((strip(lab), name, port, col, tuple(path), self.key_text(atom), got))

    def key_text(self, atom):
        """The labels at the atom's key and Example sites, with no marks, which tell two reads of one maker at two keys apart."""
        def plain(x):
            return strip(x) if isinstance(x, str) else ' '.join(plain(y) for y in x)
        return tuple(sorted(plain(s) for s in atom[1:] if isinstance(s, list) and s[0] in (':key', ':E')))

    def flat(self, args, path=()):
        """[(field path, label)] of a site's args."""
        out = []
        for a in args:
            if isinstance(a, str):
                out.append((path + (strip(a),) if len(args) > 1 else path, a))
            elif a and a[0].startswith(':'):
                out += self.flat(a[1:], path + (a[0][1:],))
        return out

    def column(self, f, port, col, path):
        """The set of sources at column col, field path path, of output or input `port` of form f (the relation itself where port is empty)."""
        if f.kind in ('RULE', 'DET') or not port:
            return f.cols.get(col)
        if f.kind != 'INIT' or f.comp is None:
            return None
        c = COMPONENTS.get(f.comp)
        if c is None:
            return None
        if col == 'key':
            if not path:
                return None
            return f.keys.get(path[0])
        cols = c['outputs'].get(port) or c['inputs'].get(port) or {}
        ty = cols.get(col)
        if ty == 'Ident':
            return frozenset([f.name]) if (f.comp, port) in MAKERS else None
        if ty in c['params']:
            b = f.binds.get(ty)
            if b is None:
                return None
            if None in b:
                return b[None]
            return b.get(path[0]) if path else None
        return None

    # ---- bodies

    def meet(self, sites, label, sets, bad, neg=False, at=None, under_not=()):
        """The meet of sets, each with a flag in under_not for a site read under NOT. A failed meet with a site under NOT counts as negated."""
        cur = None
        order = sorted(range(len(sets)), key=lambda i: i in under_not)  # positive sites first
        for i in order:
            s = sets[i]
            if cur is None:
                cur = s
            elif cur & s:
                cur = cur & s
            else:
                bad.append(dict(label=label, a=sorted(cur), b=sorted(s), neg=neg or i in under_not, at=at))
        return cur

    def conj(self, items, ctx, bad, env=None, neg=False):
        """{label: set} of a conjunction, with its cross-source joins appended to bad. env holds labels of an enclosing scope (a key)."""
        sites = {k: [v] for k, v in (env or {}).items()}
        negated = {}
        eqs = []
        unions = []
        for it in items:
            if not isinstance(it, list) or not it:
                continue
            h = it[0]
            if isinstance(h, list):  # a list of atoms
                got = self.conj(it, ctx, bad, None, neg)
                for k, v in got.items():
                    sites.setdefault(k, []).append(v)
            elif h == 'NOT':
                got = self.conj(it[1:], ctx, bad, None, True)
                for k, v in got.items():
                    sites.setdefault(k, []).append(v)
                    negated.setdefault(k, set()).add(len(sites[k]) - 1)
            elif h == 'OR':
                unions.append(self.union(it[1:], ctx, bad, neg) + (self.fresh(it),))
            elif h == 'IF':
                unions.append(self.union([it[1] + it[2], it[3]] if len(it) > 3 else [it[1] + it[2]], ctx, bad, neg) + (self.fresh(it),))
            elif h == 'ALL':
                got = self.conj(sum((x for x in it[1:] if isinstance(x, list)), []), ctx, bad, None, neg)
                for k, v in got.items():
                    sites.setdefault(k, []).append(v)
            elif h in ('=', '!=') and len(it) == 3:
                eqs.append(it)
            elif h in ('<', '<=', '>', '>=', 'ONE', 'SET'):
                pass
            elif isinstance(h, str):
                sub = {}
                self.read(it, sub, ctx)
                for k, v in sub.items():
                    sites.setdefault(k, []).extend(v)
        for merged, branches, fresh in unions:
            for br in branches:  # the sites outside an OR bound each branch of a label that the OR does not make (the engine's Outside::admit)
                for k, v in br.items():
                    outer = None
                    for s in sites.get(k, ()):
                        outer = s if outer is None else (outer & s or outer)
                    if k not in fresh and outer is not None and not outer & v:
                        ctx.setdefault('branch_cross', []).append(k)
            for k, v in merged.items():
                sites.setdefault(k, []).append(v)
        out = {k: self.meet(sites, k, v, bad, neg, None, negated.get(k, ())) for k, v in sites.items()}
        for op, a, b in eqs:
            a, b = strip(a), strip(b)
            x, y = out.get(a), out.get(b)
            if op == '=':
                if x is not None and y is not None:
                    if x & y:
                        out[a] = out[b] = x & y
                    else:
                        bad.append(dict(label=a + '=' + b, a=sorted(x), b=sorted(y), neg=neg, at='='))
                elif x is not None:
                    out[b] = x
                elif y is not None:
                    out[a] = y
            elif x is not None and y is not None and not x & y:
                ctx.setdefault('ne', []).append((a, b))
        return out

    def fresh(self, x):
        """The labels that x makes."""
        if isinstance(x, str):
            return {x[1:]} if x.startswith('*') else set()
        return set().union(*(self.fresh(y) for y in x)) if x else set()

    def union(self, branches, ctx, bad, neg):
        merged, each = {}, []
        for br in branches:
            if not isinstance(br, list):
                continue
            got = self.conj(br, ctx, bad, None, neg)
            each.append(got)
            for k, v in got.items():
                merged[k] = merged[k] | v if k in merged else v
        if any(len(v) > 1 for v in merged.values()):
            ctx.setdefault('union_labels', []).extend(k for k, v in merged.items() if len(v) > 1)
        return merged, each

    # ---- forms

    def add(self, text):
        """Traces one form's text and returns its Form; a form seen before is returned as it was."""
        e = sexprs(text)[0]
        kind, name = e[0], e[1]
        if name in self.forms:
            return self.forms[name]
        f = Form(kind, name, text)
        ctx = {}
        if kind in ('RULE', 'DET'):
            if len(e) == 3 and isinstance(e[2], str):  # a proposer
                if e[2] == 'PanelCombine':
                    f.cols['Id'] = frozenset([name])
            else:
                f.cols = {k: v for k, v in self.conj(e[2:], ctx, f.bad).items() if v}
        elif kind == 'INIT':
            self.init(f, e, ctx)
        else:
            f.known = False
            self.unread_kinds[kind] = self.unread_kinds.get(kind, 0) + 1
        f_ctx = ctx
        f.__class__ = Form
        self.forms[name] = f
        self.last_ctx = f_ctx
        return f

    def init(self, f, e, ctx):
        f.comp = e[2]
        c = COMPONENTS.get(f.comp)
        if c is None:
            f.known = False
            return
        ports = e[3:]
        if ports and isinstance(ports[0], list) and ports[0][0] == 'key':
            key = ports[0]
            keyenv = self.conj(key[1], ctx, f.bad)
            carets = []
            self.carets(key[1], carets)
            f.keys = {k: keyenv.get(k) for k in carets}
            for p in key[2:] + ports[1:]:
                self.port(f, c, p, dict(keyenv), ctx)
        else:
            for p in ports:
                self.port(f, c, p, {}, ctx)

    def carets(self, x, out):
        if isinstance(x, list):
            for y in x:
                self.carets(y, out)
        elif isinstance(x, str) and x.startswith('^'):
            if x[1:] not in out:
                out.append(x[1:])

    def port(self, f, c, p, env, ctx):
        if not (isinstance(p, list) and p and isinstance(p[0], str)):
            return
        cols = c['inputs'].get(p[0])
        if cols is None or len(p) < 2:
            return
        head = p[1]
        labs = self.conj(p[2:], ctx, f.bad, {k: v for k, v in env.items() if v})
        for s in head:
            if not (isinstance(s, list) and s and s[0].startswith(':')):
                continue
            col, args = self.site_args(s)
            ty = cols.get(col)
            if ty not in c['params'] or ty == 'Key':
                continue
            flat = self.flat(args)
            b = f.binds.setdefault(ty, {})
            for path, lab in flat:
                v = labs.get(strip(lab))
                k = path[0] if path else None
                if v:
                    if b.get(k) and not b[k] & v:
                        ctx.setdefault('param_cross', []).append((ty, f.comp))
                    b[k] = b[k] | v if b.get(k) else v
                else:
                    b.setdefault(k, None)


def component_of(forms, name):
    f = forms.get(name)
    if f is None:
        return '?'
    return f.comp if f.kind == 'INIT' else 'PanelCombine' if f.kind == 'DET' else f.kind
