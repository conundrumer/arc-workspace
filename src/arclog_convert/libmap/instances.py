"""The expansion of a lib instance into the instances, types, relations and
clauses of its shape, as a pass over a parsed Souffle solver.

A `Spec` gives the shape in Souffle text, each part formatted with `{x}`,
the instance's name, and each type parameter of the present component by
its name, `{Key}`, `{T}`, as the instance's type arguments:

- `decls`: the types, relations and instances that stand in place of the
  instance, in the instance's scope.
- `inputs`: each input relation of the present component, as a pattern
  atom, with the heads its clauses take in its place. An input with no
  entry keeps its clauses only as a source of `in_<input>` atoms.
- `reads`: each relation of the present component a site reads, as a
  pattern atom, with the atom the site reads in its place.
- `clauses`: further clauses of the shape. An atom `in_<input>(..)` in
  their bodies stands for the input's clauses: where the input has one
  clause, and that clause's body is one atom or the shape reads the input
  once, the atom is that body, unified with the clause's head; otherwise it
  reads `{x}_<input>`, a relation derived from the input's clauses, as
  the rules of `work/arclog/lib-map.md` give for a body repeated.

A pattern's variables are distinct, so a site always matches it, and the
replacement takes each pattern variable's term at the site. A read of a
relation the spec does not map is left in place, with the reason.
"""
from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass, replace
from pathlib import Path
from typing import Any, Callable

from souffle.layout import SouffleProgram

from engine.program import (AliasType, AdtType, Atom, AtomLiteral, Comparison, ComparisonOperator,
                            ConstructorTerm, DeclId, Disjunction, Instance, RecordTerm, RecordType,
                            RelationDecl, RelationName, Scope, SubtypeType, TypeName, Unit, UnitId,
                            Variable, Wildcard)

ROOT = Path(__file__).resolve().parents[3]


@dataclass
class Spec:
    decls: str = ""
    inputs: dict[str, list[str]] = field(default_factory=dict)
    reads: dict[str, str] = field(default_factory=dict)
    clauses: str = ""
    derive: frozenset[str] = frozenset()   # inputs the shape reads through `{x}_<input>` even where one atom would do
    moved: dict[str, str] = field(default_factory=dict)   # each relation of the instance, by the shape's relation


def _parse(text: str) -> SouffleProgram:
    from souffle.parser import parse
    prog = parse(text, ROOT / "programs")
    if not isinstance(prog, SouffleProgram):
        raise ValueError(f"spec parse failed: {prog}\n{text}")
    return prog


def _atom(text: str) -> Atom:
    return _parse(f"{text} :- true.").units[0].head


# ---- terms


def term_vars(t, out: list[str]) -> list[str]:
    if isinstance(t, Variable):
        if t.name not in out:
            out.append(t.name)
    elif isinstance(t, tuple):
        for x in t:
            term_vars(x, out)
    elif is_dataclass(t) and not isinstance(t, type):
        for f in fields(t):
            if f.name not in ("relation", "line", "span", "op"):
                term_vars(getattr(t, f.name), out)
    return out


def subst(x, m: dict, deep: bool = True) -> Any:
    """x with each variable m names replaced by its term: a unifier's
    terms again in turn where `deep`, a match's terms once where not."""
    if isinstance(x, Variable):
        if x.name not in m:
            return x
        return subst(m[x.name], m) if deep else m[x.name]
    if isinstance(x, tuple):
        return tuple(subst(y, m, deep) for y in x)
    if is_dataclass(x) and not isinstance(x, type) and not isinstance(x, (RelationName, TypeName)):
        ch = {f.name: subst(getattr(x, f.name), m, deep) for f in fields(x)
              if f.name not in ("relation", "line", "span", "op", "id", "scope")}
        return replace(x, **ch) if ch else x
    return x


def unify(a, b, m: dict) -> bool:
    """Extend m so that a and b agree under it; False where they cannot."""
    a, b = subst(a, m), subst(b, m)
    if a == b:
        return True
    if isinstance(a, Wildcard) or isinstance(b, Wildcard):
        return True
    if isinstance(a, Variable) and isinstance(b, Variable):
        # a template's name gives way to a clause's, and a later clause's to an earlier one's
        if a.name.startswith("T__"):
            m[a.name] = b
        else:
            m[b.name] = a
        return True
    if isinstance(a, Variable):
        m[a.name] = b
        return True
    if isinstance(b, Variable):
        m[b.name] = a
        return True
    if isinstance(a, RecordTerm) and isinstance(b, RecordTerm) and len(a.args) == len(b.args):
        return all(unify(x, y, m) for x, y in zip(a.args, b.args))
    if isinstance(a, ConstructorTerm) and isinstance(b, ConstructorTerm) and a.name == b.name \
            and len(a.args) == len(b.args):
        return all(unify(x, y, m) for x, y in zip(a.args, b.args))
    return False


def match(pattern: Atom, site: Atom) -> dict | None:
    """The term at the site of each variable of the pattern; None where the
    pattern has `_` at a column the site reads."""
    if len(pattern.args) != len(site.args):
        return None
    if any(isinstance(p, Wildcard) and not isinstance(s, Wildcard) for p, s in zip(pattern.args, site.args)):
        return None
    return {p.name: s for p, s in zip(pattern.args, site.args) if isinstance(p, Variable)}


def apart(u: Unit, taken: set[str]) -> Unit:
    """u with each variable a name in `taken` renamed."""
    m = {}
    for v in term_vars((u.head, u.body), []):
        if v in taken:
            n = 2
            while f"{v}{n}" in taken:
                n += 1
            m[v] = Variable(f"{v}{n}")
            taken.add(f"{v}{n}")
        else:
            taken.add(v)
    return replace(u, head=subst(u.head, m), body=subst(u.body, m)) if m else u


# ---- the pass


class Expander:
    def __init__(self, prog, lib, specs: dict[str, Callable]) -> None:
        self.prog = prog
        self.lib = lib
        self.specs = specs
        self.next_decl = 1 + max((d.id.index for d in prog.declarations), default=0)
        self.next_unit = 1 + max((u.id.index for u in prog.units), default=0)
        self.insts = {(i.scope.components, i.name): i for i in prog.instances}
        self.comps = {c.name for c in prog.components}
        self.judgment: dict[Atom, str] = {}
        self.pending: list[Unit] = []   # the clauses of the relations derived from inputs
        self.made: dict[tuple, dict[str, str]] = {}   # an instance's relations derived from inputs, by input
        self.sig_top = set(getattr(lib, "sig_top", ()))   # the lib relations only the signature holds
        self.own: dict[UnitId, tuple] = {}   # a shape's clause: its instance, whose new relations it reads
        self.moved: dict[str, tuple[str, dict[str, str]]] = {}   # an heir instance: the name it stands for, and its moves
        self.from_input: set[UnitId] = set()   # a clause of a relation derived from an input: the solver's reads
        self.plans: dict = {}
        self.outputs_only = False

    def resolve(self, scope: tuple[str, ...], path: tuple[str, ...]) -> Instance | None:
        if not path:
            return None
        inst = next((self.insts[(scope[:i], path[0])] for i in range(len(scope), -1, -1)
                     if (scope[:i], path[0]) in self.insts), None)
        if inst is None or len(path) == 1:
            return inst
        if inst.component in self.comps:
            return self.resolve((inst.component,), path[1:])
        return None

    def read_sites(self, inst: Instance) -> list[Atom]:
        """Each atom of a clause's body that reads a relation of the instance."""
        return [a for u in self.prog.units for a in _atoms(u.body or ())
                if a.relation.instances and self.resolve(u.scope.components, a.relation.instances) is inst]

    def reads_of(self, inst: Instance) -> set[str]:
        """The relations of the instance that some clause's body reads."""
        return {a.relation.name for a in self.read_sites(inst)}

    def names(self, inst: Instance, input: str, defaults: list[str]) -> list[str]:
        """Names for a shape's variables: the variable at each column of the
        head of the input's first clause, where it is a variable that no
        other column there holds, and else the default."""
        u = next((u for u in self.prog.units if u.head.relation.name == input and u.head.relation.instances
                  and self.resolve(u.scope.components, u.head.relation.instances) is inst), None)
        if u is None or len(u.head.args) != len(defaults):
            return defaults
        vs = [a.name if isinstance(a, Variable) else None for a in u.head.args]
        out = [v if v and vs.count(v) == 1 and v not in defaults[:i] + defaults[i + 1:] else d
               for i, (v, d) in enumerate(zip(vs, defaults))]
        return out if len(set(out)) == len(out) else defaults

    def taken(self, name: str, scope: tuple[str, ...]) -> bool:
        """A relation or instance of the solver has the name, in the scope or
        one around it."""
        return any(d.name == name and d.scope.components == scope[:len(d.scope.components)]
                   and (d.span is None or d.span.file is None)   # the solver's own, not the lib's
                   for d in (*self.prog.relations, *self.prog.instances))

    def inputs(self, inst: Instance, name: str) -> list[Unit]:
        """The clauses of one input of the instance."""
        return [u for u in self.prog.units if u.head.relation.name == name and len(u.head.relation.instances) == 1
                and self.resolve(u.scope.components, u.head.relation.instances) is inst]

    def find_type(self, name: str, scope: tuple[str, ...]):
        types = {(t.scope.components, t.name): t for t in self.prog.types}
        return next((types[(scope[:i], name)] for i in range(len(scope), -1, -1) if (scope[:i], name) in types), None)

    def frame(self, inst: Instance) -> tuple[str, str] | None:
        """The frame of the instance's positions, as a key pattern over the
        instance's key and an atom over `P` and the pattern's variables: the
        input grid at the top level, the example's input under an Example
        field of the key, and Parse's `cell` under a field of Parse's key
        type; None where the key holds no such field. A Unit key at the top
        level is `$U()`, which a clause need not ground."""
        scope = inst.scope.components
        if inst.type_args[0].text == "Unit" and not scope:
            return "$U()", "in(P, _)"
        if not scope:
            return "Ky", "in(P, _)"
        want = {"Example": "ex_in({v}, P, _)"}
        if scope == ("Parse",):
            parse = next((c for c in self.prog.components if c.name == "Parse"), None)
            if parse is not None and parse.type_params and any(
                    r.name == "cell" and r.scope.components == ("Parse",) and len(r.columns) == 3
                    for r in self.prog.relations):
                want[parse.type_params[0]] = "cell({v}, P, _)"
        n = iter(range(1, 99))

        def walk(tname: str):
            if tname in want:
                v = f"Kf{next(n)}"
                return v, want[tname].format(v=v)
            t = self.find_type(tname, scope)
            if isinstance(t, RecordType):
                parts = [walk(f.type.text) for f in t.fields]
                found = next((a for _, a in parts if a), None)
                return "[" + ", ".join(p for p, _ in parts) + "]", found
            return f"Kx{next(n)}", None
        pat, atom = walk(inst.type_args[0].text)
        return (pat, atom) if atom else None

    def did(self) -> DeclId:
        self.next_decl += 1
        return DeclId(self.next_decl)

    def uid(self) -> UnitId:
        self.next_unit += 1
        return UnitId(self.next_unit)

    def fmt(self, text: str, inst: Instance) -> str:
        tparams = list(self.lib.comps[inst.component].type_params)
        sub = {p: a.text for p, a in zip(tparams, inst.type_args)}
        return text.format(x=inst.name, **sub)

    def run(self):
        prog = self.prog
        own = lambda x: x.span is None or x.span.file is None  # noqa: E731
        targets = [i for i in prog.instances if own(i) and i.component in self.specs]
        if not targets:
            return prog, {}
        types, rels, insts, units = list(prog.types), list(prog.relations), list(prog.instances), list(prog.units)
        plans = {}
        for inst in targets:
            spec = self.specs[inst.component](inst, self)
            if spec is None:
                continue
            plans[(inst.scope.components, inst.name)] = (inst, spec)
        if not plans:
            return prog, {}
        self.plans = plans
        new_units: list[Unit] = []
        inputs_of: dict[tuple, dict[str, list[Unit]]] = {k: {} for k in plans}
        for u in units:
            h = u.head.relation
            inst = self.resolve(u.scope.components, h.instances) if h.instances else None
            if inst is None:
                continue
            key = (inst.scope.components, inst.name)
            if key in plans and h.instances[-1] == inst.name and len(h.instances) == 1:
                inputs_of[key].setdefault(h.name, []).append(u)
        self.inputs_of, self.rels = inputs_of, rels
        for key, (inst, spec) in plans.items():
            d = _parse(self.fmt(spec.decls, inst)) if spec.decls.strip() else None
            insts.remove(inst)
            if d is not None:
                for x in (*d.types, *d.relations, *d.instances):
                    if x.name != inst.name and self.taken(x.name, inst.scope.components):
                        raise ValueError(f"{inst.name}: the shape's {x.name} clashes with the solver's")
                for t in d.types:
                    types.append(replace(t, id=self.did(), scope=inst.scope))
                for r in d.relations:
                    rels.append(replace(r, id=self.did(), scope=inst.scope, span=None))
                # the instance's span, and the directives above it, go to the one that takes its
                # name, or else to the first
                heir = next((i.name for i in d.instances if i.name == inst.name),
                            d.instances[0].name if d.instances else None)
                for i in d.instances:
                    insts.append(replace(i, id=self.did(), scope=inst.scope,
                                         span=inst.span if i.name == heir else None))
                if heir is not None:
                    # a directive's relation of the instance: the relation of the shape that stands for it
                    moves = {}
                    for p_, r_ in spec.reads.items():
                        rep = next(l.atom for l in _parse(f"x__(0) :- {self.fmt(r_, inst)}.").units[0].body or ()
                                   if isinstance(l, AtomLiteral)).relation
                        name = f"{inst.name}_{rep.name[3:]}" if rep.name.startswith("in_") and not rep.instances \
                            else ".".join((*rep.instances, rep.name))
                        moves[_atom(self.fmt(p_, inst)).relation.name] = name
                    moves |= {r: self.fmt(t, inst) for r, t in spec.moved.items()}
                    self.moved[heir] = (inst.name, moves)
            heads = {_atom(self.fmt(p, inst)).relation.name: (_atom(self.fmt(p, inst)),
                                                               [_atom(self.fmt(h, inst)) for h in hs])
                     for p, hs in spec.inputs.items()}
            ins = inputs_of[key]
            extra = _parse(self.fmt(spec.clauses, inst)).units if spec.clauses.strip() else ()
            self.derive_now = spec.derive
            for u in extra:
                for v in self.instantiate(u, inst, ins, extra, rels):
                    self.own[v.id] = key
                    new_units.append(v)
            for name, us in ins.items():
                if name not in heads:
                    continue
                pat, hs = heads[name]
                for u in us:
                    m = match(pat, u.head)
                    if m is None:
                        raise ValueError(f"{inst.name}.{name}: a clause's head does not match {pat}")
                    for h in hs:
                        new_units.append(replace(u, id=self.uid(), head=Atom(h.relation, subst(h.args, m, False), u.head.line)))
        # each input clause of a planned instance gives way to its new clauses
        gone = {id(u) for k in plans for us in inputs_of[k].values() for u in us}
        out_units = []
        for u in units:
            if id(u) in gone:
                continue
            out_units.append(self.reads(u, plans))
        out_units += [self.reads(u, plans) for u in new_units]
        done = 0
        while done < len(self.pending):   # a read may derive a relation, whose clauses read in turn
            u = self.pending[done]
            done += 1
            out_units.append(self.reads(u, plans))
        return replace(prog, types=tuple(types), relations=tuple(rels), instances=tuple(insts),
                       units=tuple(_unmarked(u) for u in out_units)), self.judgment

    def instantiate(self, u: Unit, inst: Instance, ins: dict[str, list[Unit]], extra, rels) -> list[Unit]:
        """A clause of the shape, its `in_<input>` atoms replaced."""
        count: dict[str, int] = {}
        for e in extra:
            for a in _atoms(e.body or ()):
                if a.relation.name.startswith("in_") and not a.relation.instances:
                    count[a.relation.name[3:]] = count.get(a.relation.name[3:], 0) + 1
        # the template's variables stand aside, so that a unified input clause keeps its own names
        u = replace(u, body=self.lib_names(u.body or (), inst))
        own_vars = term_vars((u.head, u.body), [])
        aside = {v: Variable(f"T__{v}") for v in own_vars}
        u = replace(u, head=subst(u.head, aside, False), body=subst(u.body, aside, False))
        taken = {f"T__{v}" for v in own_vars}
        m: dict = {}

        def lits(body) -> tuple:
            out = []
            for lit in body:
                if isinstance(lit, Disjunction):
                    out.append(Disjunction(tuple(lits(b) for b in lit.branches), lit.line))
                    continue
                if not (isinstance(lit, AtomLiteral) and lit.atom.relation.name.startswith("in_")
                        and not lit.atom.relation.instances):
                    out.append(lit)
                    continue
                name = lit.atom.relation.name[3:]
                cs = ins.get(name, [])
                one = len(cs) == 1 and cs[0].body is not None
                spec_derive = getattr(self, "derive_now", frozenset())
                hvars = [x.name for x in cs[0].head.args if isinstance(x, Variable)] if one else []
                plain = one and len(hvars) == len(cs[0].head.args) == len(set(hvars))
                # a head that repeats a variable or holds a term is unfolded, since a derived
                # relation's clause cannot repeat a head label
                if one and not lit.negated and name not in spec_derive and \
                        (len(cs[0].body or ()) == 1 or count.get(name, 0) == 1 or not plain):
                    c = apart(cs[0], taken)
                    if all(unify(y, x, m) for x, y in zip(c.head.args, lit.atom.args)):
                        out.extend(self.marked(self.output_reads(c).body or (), c))   # the input's reads, as the solver's
                        continue
                if lit.negated and name not in spec_derive and _one_atom(cs):
                    c = self.output_reads(apart(cs[0], taken))
                    if _one_atom([c]) and all(unify(y, x, m) for x, y in zip(c.head.args, lit.atom.args)):
                        # a column the read leaves unread is unread in the negated atom too
                        unread = {x.name: Wildcard() for x, y in zip(c.head.args, lit.atom.args)
                                  if isinstance(x, Variable) and isinstance(y, Wildcard) and x.name not in m}
                        out.append(AtomLiteral(self.marked(subst(_body_atom(c), unread, False), c), True))
                        continue
                occ = _vars_all(cs[0].head.args) if one else []
                if lit.negated and one and len(occ) != len(set(occ)):   # a head that repeats a variable
                    out.extend(self.negated_unplain(inst, name, cs[0], subst(lit.atom, m), rels))
                    continue
                out.append(AtomLiteral(Atom(RelationName((), self.derived(inst, name, cs, rels)),
                                            lit.atom.args, lit.atom.line), lit.negated))
            return tuple(out)

        body = _dedup(subst(lits(u.body or ()), m))
        head = subst(u.head, m)
        used = set(term_vars((head, body), []))
        back = {}
        for v in sorted(x for x in used if x.startswith("T__")):   # a template variable left free: its own name
            n, w = 2, v[3:]
            while w in used or Variable(w) in back.values():
                w, n = f"{v[3:]}{n}", n + 1
            back[v] = Variable(w)
        head, body = subst(head, back, False), subst(body, back, False)
        return [replace(u, id=self.uid(), scope=inst.scope, span=None, head=head, body=body)]

    def marked(self, x, c: Unit):
        """x with each atom's line marked, so that the pass maps none of them
        again, but a read of a planned instance's input, which the clause it
        is unfolded into reads through the relation derived from it."""
        from arclog_convert.libmap.box import mapped

        def fn(a: Atom) -> Atom:
            inst = self.resolve(c.scope.components, a.relation.instances) if a.relation.instances else None
            if inst is not None and (inst.scope.components, inst.name) in self.plans and \
                    a.relation.name in {r.name for r in self.lib.present(inst.component)[1] if r.is_input}:
                return a
            return replace(a, line=-a.line - 1) if a.line >= 0 else a
        return mapped(x, fn)

    def output_reads(self, c: Unit) -> Unit:
        """c with each read of a planned instance's output mapped, as a
        clause of the solver's; a read of an input stays for the clause it
        is unfolded into."""
        self.outputs_only = True
        try:
            return self.reads(c, self.plans)
        finally:
            self.outputs_only = False

    def negated_unplain(self, inst: Instance, name: str, c: Unit, read: Atom, rels) -> list:
        """A negated read of an input whose one clause's head repeats a
        variable: the read's arguments matched against the
        head, and either a test of the match failing or the clause's body,
        derived over the head's distinct variables, not holding. A derived
        clause then repeats no head label."""
        fresh = iter(range(1, 1 << 20))
        binds: list = []
        tests: list[tuple] = []
        m: dict = {}

        def match_(h, t):
            if isinstance(t, Wildcard):
                return
            if isinstance(h, Variable):
                if h.name in m:
                    if not (_unit(t) and _unit(m[h.name])):
                        tests.append((t, m[h.name]))
                else:
                    m[h.name] = t
            elif isinstance(h, RecordTerm):
                if isinstance(t, RecordTerm) and len(t.args) == len(h.args):
                    parts = t.args
                else:
                    parts = tuple(Variable(f"F_neg{next(fresh)}") for _ in h.args)
                    binds.append(Comparison(ComparisonOperator.EQ, t, RecordTerm(parts), read.line))
                for x, y in zip(h.args, parts):
                    match_(x, y)
            elif not (_unit(h) and _unit(t)):   # the Unit value equals itself
                tests.append((t, h))
        for h, t in zip(c.head.args, read.args):
            match_(h, t)
        hv = [v for v in term_vars(c.head.args, [])]
        rname = f"{inst.name}_{name}_held"
        if not any(r.name == rname and r.scope == inst.scope for r in rels):
            tparams, lrels = self.lib.present(inst.component)
            lr = next(r for r in lrels if r.name == name)
            types: dict[str, str] = {}
            sub = {p: a.text for p, a in zip(tparams, inst.type_args)}

            def type_of(h, ty):
                if isinstance(h, Variable):
                    types.setdefault(h.name, ty)
                elif isinstance(h, RecordTerm):
                    rt = self.find_type(ty, inst.scope.components)
                    if isinstance(rt, RecordType):
                        for x, f in zip(h.args, rt.fields):
                            type_of(x, f.type.text)
            for h, col in zip(c.head.args, lr.cols):
                type_of(h, sub.get(col.type, col.type))
            cols = ", ".join(f"{v.lower()}: {types.get(v, 'number')}" for v in hv)
            rels.append(replace(_parse(f".decl {rname}({cols})").relations[0], id=self.did(),
                                scope=inst.scope, span=None))
            v = replace(c, id=self.uid(), head=Atom(RelationName((), rname), tuple(Variable(x) for x in hv), c.head.line))
            self.own[v.id] = (inst.scope.components, inst.name)
            self.from_input.add(v.id)
            self.pending.append(v)
        held = AtomLiteral(Atom(RelationName((), rname), tuple(m.get(x, Wildcard()) for x in hv), read.line), True)
        if not tests:
            return [*binds, held]
        return [*binds, Disjunction(tuple((Comparison(ComparisonOperator.NE, t, h, read.line),) for t, h in tests)
                                    + ((held,),), read.line)]

    def lib_names(self, body, inst):
        """The body with each lib atom whose name a relation of the solver
        takes read at the path `@lib`, which `Converter.resolve` reads as
        the lib's."""
        from arclog_convert.libmap.box import mapped
        scope = inst.scope.components

        def fn(a: Atom) -> Atom:
            n = a.relation.name
            if not a.relation.instances and (n in self.lib.top or n in self.sig_top) and self.taken(n, scope):
                return Atom(RelationName(("@lib",), n), a.args, a.line)
            return a
        return mapped(body, fn)

    def derived(self, inst: Instance, name: str, cs: list[Unit], rels) -> str:
        """The relation derived from an input's clauses, declared once."""
        rname = f"{inst.name}_{name}"
        made = self.made.setdefault((inst.scope.components, inst.name), {})
        if name in made:
            return made[name]
        base = f"{inst.name}_{name}_{inst.component.lower()}"   # where the solver has a relation of that name
        rname = next(c for c in (rname, base, *(f"{base}{k}" for k in range(2, 99)))
                     if not self.taken(c, inst.scope.components)
                     and not any(r.name == c and r.scope == inst.scope for r in rels))
        made[name] = rname
        tparams, lrels = self.lib.present(inst.component)
        lr = next(r for r in lrels if r.name == name)
        sub = {p: a.text for p, a in zip(tparams, inst.type_args)}
        cols = ", ".join(f"{c.name.lower()}: {sub.get(c.type, c.type)}" for c in lr.cols)
        rels.append(replace(_parse(f".decl {rname}({cols})").relations[0], id=self.did(),
                            scope=inst.scope, span=None))
        for c in cs:
            v = replace(c, id=self.uid(), head=Atom(RelationName((), rname), c.head.args, c.head.line))
            self.own[v.id] = (inst.scope.components, inst.name)
            self.from_input.add(v.id)
            self.pending.append(v)
        return rname

    def target(self, u: Unit, a: Atom, plans):
        """The planned instance a read reaches and its spec, or None where
        the read is not one the pass maps."""
        path = a.relation.instances
        if not path or a.line < 0:   # no path, or a read the pass mapped already
            return None
        inst = self.resolve(u.scope.components, path)
        if inst is None or (inst.scope.components, inst.name) not in plans:
            return None
        if self.outputs_only and a.relation.name in {r.name for r in self.lib.present(inst.component)[1] if r.is_input}:
            return None
        if self.own.get(u.id) == (inst.scope.components, inst.name) and u.id not in self.from_input and \
                a.relation.name not in {r.name for r in self.lib.present(inst.component)[1] if r.is_input}:
            return None   # the shape's own read of an output of the new instance
        return inst, plans[(inst.scope.components, inst.name)][1]

    def replacement(self, u: Unit, a: Atom, inst, spec) -> tuple | None:
        """The literals a read takes, each at the read's instance path, its
        variables apart from the clause's; None where the spec maps no read
        of the relation. A clause of the shape, or of a relation derived
        from an input, reads an input through the relation derived from it,
        so that no input reads the new instance."""
        key = (inst.scope.components, inst.name)
        if self.own.get(u.id) == key and a.relation.name in {
                r.name for r in self.lib.present(inst.component)[1] if r.is_input}:
            name = self.derived(inst, a.relation.name, self.inputs_of[key].get(a.relation.name, []), self.rels)
            return (AtomLiteral(Atom(RelationName(a.relation.instances[:-1], name), a.args, a.line), False),)
        for p, r in spec.reads.items():
            pat = _atom(self.fmt(p, inst))
            if pat.relation.name != a.relation.name:
                continue
            m = match(pat, a)
            if m is None:
                continue
            body = self.lib_names(_parse(f"x__(0) :- {self.fmt(r, inst)}.").units[0].body or (), inst)
            taken = set(term_vars((u.head, u.body), []))
            for v in term_vars(body, []):
                if v not in m:
                    n, w = 2, v
                    while w in taken:
                        w, n = f"{v}_{n}", n + 1
                    taken.add(w)
                    m[v] = Variable(w)
            path = a.relation.instances
            uses: dict[str, int] = {}
            for v in term_vars(body, []):
                uses[v] = sum(1 for x in _vars_all(body) if x == v)
            for v, t in list(m.items()):
                if isinstance(t, Wildcard) and uses.get(v, 0) > 1 and len(body) > 1:
                    # one unread column the shape's literals join on
                    n, w = 2, v
                    while w in taken:
                        w, n = f"{v}_{n}", n + 1
                    taken.add(w)
                    m[v] = Variable(w)

            def fix(b: Atom) -> Atom:
                name = b.relation.name
                if name.startswith("in_") and not b.relation.instances:
                    cs = self.inputs_of[key].get(name[3:], [])
                    if _one_atom(cs):   # the input's one atom, at the read
                        c = cs[0]
                        mm = {x.name: subst(y, m, False) for x, y in zip(c.head.args, b.args)
                              if isinstance(x, Variable)}
                        inner = _body_atom(c)
                        rel = inner.relation
                        if path[:-1] and (rel.instances or not (rel.name in self.lib.top or rel.name in self.sig_top)):
                            rel = RelationName(path[:-1] + rel.instances, rel.name)   # read from outside its scope
                        return Atom(rel, subst(inner.args, mm, False), a.line)
                    name = self.derived(inst, name[3:], cs, self.rels)
                    return Atom(RelationName(path[:-1], name), subst(b.args, m, False), a.line)
                if b.relation.instances or name.startswith(f"{inst.name}_"):
                    return Atom(RelationName(path[:-1] + b.relation.instances, name), subst(b.args, m, False), a.line)
                return Atom(b.relation, subst(b.args, m, False), a.line)
            return tuple(subst(lit, m, False) if not isinstance(lit, AtomLiteral) else
                         AtomLiteral(fix(lit.atom), lit.negated) for lit in body)
        return None

    def output(self, inst, spec, a: Atom, u: Unit) -> Atom:
        """The atom of a relation derived in place of an output whose read
        takes several literals, for a read that cannot hold them."""
        tparams, lrels = self.lib.present(inst.component)
        lr = next(r for r in lrels if r.name == a.relation.name)
        rname = f"{inst.name}_{lr.name}"
        if not any(r.name == rname and r.scope == inst.scope for r in self.rels):
            sub = {p: t.text for p, t in zip(tparams, inst.type_args)}
            cols = ", ".join(f"{c.name.lower()}: {sub.get(c.type, c.type)}" for c in lr.cols)
            self.rels.append(replace(_parse(f".decl {rname}({cols})").relations[0], id=self.did(),
                                     scope=inst.scope, span=None))
            vs = [Variable(f"V{i}") for i in range(len(lr.cols))]
            head = Atom(RelationName((inst.name,), lr.name), tuple(vs), 0)
            probe = Unit(self.uid(), inst.scope, Atom(RelationName((), rname), tuple(vs), 0), (AtomLiteral(head, False),),
                         None, None)
            lits = self.replacement(probe, head, inst, spec)
            v = replace(probe, body=lits)
            self.own[v.id] = (inst.scope.components, inst.name)
            self.pending.append(v)
        return Atom(RelationName(a.relation.instances[:-1], rname), a.args, a.line)

    def reads(self, u: Unit, plans) -> Unit:
        from arclog_convert.libmap.box import mapped

        def lits(body: tuple) -> tuple:
            out = []
            for lit in body:
                if isinstance(lit, Disjunction):
                    out.append(Disjunction(tuple(lits(b) for b in lit.branches), lit.line))
                    continue
                if isinstance(lit, AtomLiteral):
                    t = self.target(u, lit.atom, plans)
                    if t is not None:
                        rep = self.replacement(u, lit.atom, *t)
                        if rep is not None and len(rep) > 1 and not lit.negated \
                                and set(term_vars(rep, [])) <= set(term_vars(lit.atom.args, [])):
                            out.extend(rep)   # the shape's literals, read as they stand, no label local to them
                            continue
                out.append(mapped(lit, fn))
            return tuple(out)

        def fn(a: Atom):
            t = self.target(u, a, plans)
            if t is None:
                return a
            rep = self.replacement(u, a, *t)
            if rep is None:
                self.judgment[a] = f"{t[0].component}.{a.relation.name}: a read the expansion does not map"
                return a
            if len(rep) == 1 and isinstance(rep[0], AtomLiteral) and not rep[0].negated:
                return rep[0].atom
            return self.output(t[0], t[1], a, u)
        return replace(u, body=lits(u.body)) if u.body else u


def _unmarked(x):
    from arclog_convert.libmap.box import mapped
    return mapped(x, lambda a: replace(a, line=-a.line - 1) if a.line < 0 else a)


def _one_atom(cs: list[Unit]) -> bool:
    """One clause, its head distinct variables, its body one positive atom
    whose every variable the head holds."""
    if len(cs) != 1 or not cs[0].body or len(cs[0].body) != 1 or not isinstance(cs[0].body[0], AtomLiteral) \
            or cs[0].body[0].negated:
        return False
    head = [x.name for x in cs[0].head.args if isinstance(x, Variable)]
    if len(head) != sum(not _unit(x) for x in cs[0].head.args) or len(set(head)) != len(head):
        return False   # the Unit value holds no information
    args = _body_atom(cs[0]).args
    return set(term_vars(args, [])) <= set(head) and not any(isinstance(x, Wildcard) for x in args)


def _body_atom(u: Unit) -> Atom:
    """The atom of a clause whose body is one atom."""
    lit = u.body[0] if u.body else None
    assert isinstance(lit, AtomLiteral)
    return lit.atom


def _unit(t) -> bool:
    return isinstance(t, ConstructorTerm) and t.name == "U" and not t.args


def _vars_all(x) -> list[str]:
    """Each occurrence of a variable in x."""
    out: list[str] = []
    if isinstance(x, Variable):
        out.append(x.name)
    elif isinstance(x, tuple):
        for y in x:
            out += _vars_all(y)
    elif is_dataclass(x) and not isinstance(x, type):
        for f in fields(x):
            if f.name not in ("relation", "line", "span", "op"):
                out += _vars_all(getattr(x, f.name))
    return out


def _dedup(body: tuple) -> tuple:
    """The literals of each list, a repeat dropped."""
    out: list = []
    for lit in body:
        if isinstance(lit, Disjunction):
            lit = Disjunction(tuple(_dedup(b) for b in lit.branches), lit.line)
        if _bare(lit) not in map(_bare, out):
            out.append(lit)
    return tuple(out)


def _bare(lit):
    """A literal with its line numbers dropped, for comparison."""
    if isinstance(lit, AtomLiteral):
        return (lit.negated, lit.atom.relation, lit.atom.args)
    return replace(lit, line=0) if hasattr(lit, "line") else lit


def _atoms(x):
    from arclog_convert.libmap.box import atoms
    return atoms(x)


def expand(prog, lib, specs):
    """The program with each instance of a component `specs` maps expanded;
    each read left in place, with the reason; and each instance that stands
    for an expanded one under another name, with that name and the relation
    of the shape that stands for each relation of the expanded one."""
    e = Expander(prog, lib, specs)
    out, judgment = e.run()
    return out, judgment, e.moved
