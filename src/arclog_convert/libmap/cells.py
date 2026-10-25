"""The expansions of the cell components, as `instances.Spec` shapes:
`Components8` onto `Components` with the diagonal steps; a `Reach` that
reads its components, and a `Rim` that reads its depth, beside a
`Components` or a `CellDistance` instance; `Rim8` onto `Rim` with every
Dir8; `Ray`, `Between` and `Slide` onto the `Ray` of
`src/arclog_convert/lib-signature.dl`; `Diagonal` and `DiagPlacement` onto derived
relations; `Gravity` onto `Distance`; `D4Map` onto `Agreement`, one set
as source and target; and an `OffsetInvariance` that reads its candidates onto `Periods`.
"""
from __future__ import annotations

from engine.program import AtomLiteral, Variable
from souffle.printer import atom as atom_text, term as term_text

from arclog_convert.libmap.instances import Spec, term_vars


def components8(inst, ex):
    return Spec(".init {x} = Components<{Key}>",
                {"node(Ky, P)": ["{x}.node(Ky, P)"], "step(S)": ["{x}.step(S)"]},
                {"label(Ky, P, I)": "{x}.label(Ky, P, I)",
                 "node(Ky, P)": "{x}.node(Ky, P)", "step(S)": "{x}.step(S)"},
                "{x}.step(S) :- diag_dir_elem(D), step_offset(D, S).")


def reach(inst, ex):
    if "label" not in ex.reads_of(inst):
        return None
    return Spec(".init {x} = Reach<{Key}>\n.init {x}_label = Components<{Key}>",
                {"node(Ky, P)": ["{x}.node(Ky, P)", "{x}_label.node(Ky, P)"],
                 "step(S)": ["{x}.step(S)", "{x}_label.step(S)"], "seed(Ky, P)": ["{x}.seed(Ky, P)"]},
                {"label(Ky, P, I)": "{x}_label.label(Ky, P, I)",
                 "reach(Ky, P)": "{x}.reach(Ky, P)", "node(Ky, P)": "{x}.node(Ky, P)",
                 "seed(Ky, P)": "{x}.seed(Ky, P)", "step(S)": "{x}.step(S)"})


def rim(eight: bool):
    def spec(inst, ex):
        depth = "depth" in ex.reads_of(inst)
        if not depth and not eight:
            return None
        decls = ".init {x} = Rim<{Key}>" + ("\n.init {x}_depth = CellDistance<{Key}>" if depth else "")
        clauses = ["{x}.dir(D) :- dir8_elem(D)."] if eight else []
        if depth:
            clauses.append("{x}_depth.source(Ky, P) :- {x}.rim(Ky, P).")
            if eight:
                clauses.append("{x}_depth.step(S) :- dir8_elem(D), step_offset(D, S).")
        return Spec(decls, {"cell(Ky, P)": ["{x}.cell(Ky, P)"] + (["{x}_depth.node(Ky, P)"] if depth else [])},
                    {"depth(Ky, P, K)": "{x}_depth.distance(Ky, P, K)", "rim(Ky, P)": "{x}.rim(Ky, P)",
                     "rim_dir(Ky, P, D)": "{x}.rim_dir(Ky, P, D)", "cell(Ky, P)": "{x}.cell(Ky, P)"},
                    "\n".join(clauses))
    return spec


def _key_only(u, a) -> bool:
    """The atom holds a variable, and each variable it holds is one of the
    head's key column."""
    vs = term_vars(a.args, [])
    return bool(vs) and set(vs) <= set(term_vars(u.head.args[:1], []))


def _reads(u, a) -> bool:
    """The clause's body has a positive atom of the relation with the arguments of `a`."""
    return any(isinstance(l, AtomLiteral) and not l.negated and l.atom.relation == a.relation and l.atom.args == a.args
               for l in u.body or ())


def _frame_alone(ex, inst, name: str, frame_atom: str) -> bool:
    """Each clause of the input has for its body the frame atom, and atoms
    over the head's key variable alone that stand with the same arguments in
    every clause of the instance's `dir` input. `ray`, `end` and `stop` hold
    only for a key with a dir, so such an atom restricts no ray."""
    cs = ex.inputs(inst, name)
    if len(cs) != 1 or not cs[0].body or not all(isinstance(l, AtomLiteral) and not l.negated for l in cs[0].body):
        return False
    if not frame_atom.startswith("in("):
        return False
    p = cs[0].head.args[-1]
    atoms = [l.atom for l in cs[0].body]
    frame = [a for a in atoms if a.relation.name == "in" and not a.relation.instances and a.args[0] == p
             and isinstance(p, Variable)]
    if len(frame) != 1:
        return False
    dirs = ex.inputs(inst, "dir")
    return all(_key_only(cs[0], x) and dirs and all(_reads(d, x) for d in dirs) for x in atoms if x is not frame[0])


_FRAME_DECL = ".init {x}_frame = Frame<{Key}>"
_FRAME_EXTENT = "{x}_frame.extent(Ky, A, N) :- in_mark(Ky, P), axis_elem(A), axis_dim(P, A, N)."


def ray(inst, ex):
    """A Ray's `node` is the frame of the instance's key (`Expander.frame`)
    where `Expander.places` places each mark in it, and the cells of a
    `Frame` keyed by the instance's key, whose extent is the frame extent of
    each mark, otherwise."""
    f = ex.frame(inst)
    if f is None:
        return None
    k, frame = f
    sites = ex.read_sites(inst)
    names = {a.relation.name for a in sites}
    stop_k = any(a.relation.name == "stop" and type(a.args[3]).__name__ != "Wildcard" for a in sites)
    clear = bool(names & {"clear", "clear_cast", "stop"})
    full_needed = bool(names & {"cast", "ray"}) or stop_k or not clear
    full = "{x}_full" if clear and full_needed else "{x}"
    blocked = bool(ex.inputs(inst, "blocked"))
    placed = ex.places(inst)
    cell = "" if placed and _frame_alone(ex, inst, "cell", frame) else ", in_cell(Ky, P)"
    decls = [".init {x} = Ray<{Key}>"] + ([".init {x}_full = Ray<{Key}>"] if clear and full_needed else [])
    clauses = []
    for i in (["{x}"] if not (clear and full_needed) else ["{x}", "{x}_full"]):
        clauses += [f"{i}.source(Ky, P) :- in_mark(Ky, P).", f"{i}.dir(Ky, D) :- in_dir(Ky, D)."]
    ground = "" if k == "$U()" else f"in_dir({k}, _), "
    if not placed:
        frame, ground = f"{{x}}_frame.cell({k}, P)", ""
        decls.append(_FRAME_DECL)
        clauses.append(_FRAME_EXTENT)
    if full_needed:
        clauses.append(f"{full}.node({k}, P) :- {ground}{frame}.")
    if clear:
        clauses.append(f"{{x}}.node({k}, P) :- {ground}{frame}" + (f", !in_blocked({k}, P)." if blocked else "."))
    reads = {"cast(Ky, P, D, N, S)": f"{full}.ray(Ky, P, D, N, S)",
             "ray(Ky, P, D, N, S)": f"{full}.ray(Ky, P, D, N, S){cell}",
             "clear_cast(Ky, P, D, N, S)": "{x}.ray(Ky, P, D, N, S)",
             "clear(Ky, P, D, N, S)": "{x}.ray(Ky, P, D, N, S)" + cell}
    if k in ("Ky", "$U()"):
        reads["stop(Ky, P, D, _, S)"] = f"{{x}}.end(Ky, E, D, _, S), neighbor(E, D, P), {frame}"
    reads |= {"stop(Ky, P, D, N, S)": f"{{x}}.end(Ky, E, D, _, S), neighbor(E, D, P), {full}.ray(Ky, P, D, N, S)",
              "dir(Ky, D)": "{x}.dir(Ky, D)", "mark(Ky, P)": "{x}.source(Ky, P)",
              "cell(Ky, P)": "in_cell(Ky, P)", "blocked(Ky, P)": "in_blocked(Ky, P)"}
    return Spec("\n".join(decls), {}, reads, "\n".join(clauses), grounded=frozenset({"node"}))


def between(inst, ex):
    f = ex.frame(inst)
    if f is None:
        return None
    k, frame = f
    placed = ex.places(inst)
    cell = "" if placed and _frame_alone(ex, inst, "cell", frame) else ", in_cell(Ky, P)"
    decls = ".init {x} = Ray<{Key}>\n.decl {x}_between(key: {Key}, p: Position)"
    extent = ""
    if placed:
        node = f"{{x}}.node({k}, P) :- " + ("" if k == "$U()" else f"in_axis({k}, _), ") + f"{frame}.\n"
    else:
        node = f"{{x}}.node({k}, P) :- {{x}}_frame.cell({k}, P).\n"
        decls += "\n" + _FRAME_DECL
        extent = _FRAME_EXTENT + "\n"
    return Spec(decls, {},
                {"between(Ky, P)": "{x}_between(Ky, P)", "ray(Ky, P, D, N, S)": "{x}.ray(Ky, P, D, N, S)" + cell,
                 "mark(Ky, P)": "{x}.source(Ky, P)", "axis(Ky, A)": "in_axis(Ky, A)", "cell(Ky, P)": "in_cell(Ky, P)"},
                "{x}.source(Ky, P) :- in_mark(Ky, P).\n"
                "{x}.dir(Ky, D) :- in_axis(Ky, A), axis4_of(D, A).\n" + node + extent +
                "{x}_between(Ky, P) :- in_cell(Ky, P), in_axis(Ky, A), axis4_of(D, A), dir8_opposite(D, O),"
                " {x}.ray(Ky, P, D, _, _), {x}.ray(Ky, P, O, _, _).", grounded=frozenset({"node"}))


def _rim_dir(ex, inst) -> str:
    """The clauses of the rim's `dir`: one for each clause of the instance's
    `dir` input, with its atoms over the key column alone left out. Where a
    clause has no other literal, or a literal other than a positive atom, the
    rim's `dir` is the rows of the input."""
    lines = []
    for u in ex.inputs(inst, "dir"):
        body = [l for l in u.body or ()]
        if not body or not all(isinstance(l, AtomLiteral) and not l.negated for l in body):
            return "{x}_rim.dir(D) :- in_dir(_, D)."
        kept = [l.atom for l in body if not _key_only(u, l.atom)]
        if not kept or not set(term_vars(u.head.args[-1:], [])) <= set(term_vars(tuple(a.args for a in kept), [])):
            return "{x}_rim.dir(D) :- in_dir(_, D)."
        text = f"({term_text(u.head.args[-1])}) :- {', '.join(map(atom_text, kept))}."
        lines.append("{x}_rim.dir" + text.replace("{", "{{").replace("}", "}}"))
    return "\n".join(lines) or "{x}_rim.dir(D) :- in_dir(_, D)."


def slide(inst, ex):
    rim_dir = "rim_dir" in ex.reads_of(inst)
    return Spec(".init {x} = Ray<{Key}>" + ("\n.init {x}_rim = Rim<{Key}>" if rim_dir else ""), {},
                {"rest(Ky, P, D, Q)": "{x}.end(Ky, Q, D, _, P)", "run(Ky, P, D, Q)": "{x}.ray(Ky, Q, D, N, P), N > 0",
                 "halt(Ky, P, D, Q)": "{x}.end(Ky, Q, D, N, P), N > 0",
                 "rim_dir(Ky, P, D)": "{x}_rim.rim_dir(Ky, P, D), in_dir(Ky, D)",
                 "node(Ky, P)": "in_node(Ky, P)", "dir(Ky, D)": "in_dir(Ky, D)"},
                "{x}.source(Ky, P) :- in_node(Ky, P).\n{x}.node(Ky, P) :- in_node(Ky, P).\n"
                "{x}.dir(Ky, D) :- in_dir(Ky, D)."
                + ("\n{x}_rim.cell(Ky, P) :- in_node(Ky, P).\n" + _rim_dir(ex, inst) if rim_dir else ""))


def diagonal(inst, ex):
    return Spec(".decl {x}_diagonal(key: {Key}, p: Position, ring: number)", {},
                {"diagonal(Ky, P, K)": "{x}_diagonal(Ky, P, K)", "cell(Ky, P)": "in_cell(Ky, P)",
                 "corner(Ky, D)": "in_corner(Ky, D)"},
                "{x}_diagonal(Ky, P, K) :- in_cell(Ky, P), in_corner(Ky, D), diag_dist(P, D, _, K, K).")


def diag_placement(inst, ex):
    read = ex.reads_of(inst)
    need = {"nearer"} | ({"quadrant"} if read & {"quadrant", "diag_cell"} else set()) | (read & {"diag_cell"})
    decls = {"nearer": ".decl {x}_nearer(key: {Key}, p: Position, d: Dir)",
             "quadrant": ".decl {x}_quadrant(key: {Key}, p: Position, diag: DiagDir)",
             "diag_cell": ".decl {x}_diag_cell(key: {Key}, p: Position, diag: DiagDir, ring: number)"}
    clauses = {"nearer": "{x}_nearer(Ky, P, D) :- in_cell(Ky, P), dir_elem(D), dist_pair(P, D, K, K2), K < K2.",
               "quadrant": "{x}_quadrant(Ky, P, Diag) :- diag_dirs(Diag, _, D1, D2), {x}_nearer(Ky, P, D1),"
                           " {x}_nearer(Ky, P, D2).",
               "diag_cell": "{x}_diag_cell(Ky, P, Diag, K) :- {x}_quadrant(Ky, P, Diag), diag_dist(P, Diag, _, K, K)."}
    order = [n for n in ("nearer", "quadrant", "diag_cell") if n in need]
    return Spec("\n".join(decls[n] for n in order), {},
                {"nearer(Ky, P, D)": "{x}_nearer(Ky, P, D)", "quadrant(Ky, P, Diag)": "{x}_quadrant(Ky, P, Diag)",
                 "diag_cell(Ky, P, Diag, K)": "{x}_diag_cell(Ky, P, Diag, K)", "cell(Ky, P)": "in_cell(Ky, P)"},
                "\n".join(clauses[n] for n in order))


def gravity(inst, ex):
    if not ex.inputs(inst, "cell") or not ex.inputs(inst, "dir"):
        return None
    blocked = bool(ex.inputs(inst, "blocked"))
    return Spec(".init {x} = GraphDistance<{Key}, {Body}>", {},
                {"travel(Ky, B, V)": "{x}.distance(Ky, B, K), in_dir(Ky, D), jump_offset(D, K, V)",
                 "cell(Ky, B, P)": "in_cell(Ky, B, P)", "dir(Ky, D)": "in_dir(Ky, D)",
                 "blocked(Ky, P)": "in_blocked(Ky, P)"},
                "{x}.source_distance(Ky, B, K) :- in_cell(Ky, B, P), in_dir(Ky, D), dist(P, D, K).\n"
                + ("{x}.source_distance(Ky, B, K) :- in_cell(Ky, B, P), in_dir(Ky, D), in_blocked(Ky, Q),"
                   " gap(D, P, Q, K).\n" if blocked else "")
                + ("" if inst.type_args[1].text == "Unit" else   # one body: no body ahead of another
                   "{x}.weight(Ky, B2, B, K) :- in_cell(Ky, B, P), in_dir(Ky, D), in_cell(Ky, B2, Q), B != B2,"
                   " gap(D, P, Q, K)."))


def d4_map(inst, ex):
    return Spec(".init {x} = Agreement<{Key}, {Val}>",
                {"src(Ky, P, V)": ["{x}.source(Ky, P, V)"], "dst(Ky, P, V)": ["{x}.target(Ky, P, V)"]},
                {"mismatch(Ky, D)": "{x}.mismatch(Ky, D)", "conflict(Ky, D)": "{x}.conflict(Ky, D)",
                 "map(Ky, D)": "in_src(Ky, _, _), d4_elem(D), !{x}.mismatch(Ky, D)",
                 "compatible(Ky, D)": "in_src(Ky, _, _), d4_elem(D), !{x}.conflict(Ky, D)",
                 "has_sym(Ky)": "in_src(Ky, _, _), d4_elem(D), !d4_identity(D), !{x}.mismatch(Ky, D)",
                 "src(Ky, P, V)": "in_src(Ky, P, V)", "dst(Ky, P, V)": "in_dst(Ky, P, V)"})


def offset_invariance(inst, ex):
    if not ex.reads_of(inst) & {"cand", "mismatch", "pair", "line_mismatch"}:
        return None
    return Spec(".init {x} = Periods<{Key}, {Val}>", {"cell(Ky, P, V)": ["{x}.cell(Ky, P, V)"]},
                {"min_period(Ky, A, K)": "{x}.fundamental_period(Ky, A, K)",
                 "period(Ky, A, K)": "{x}.approximate_period(Ky, A, K)",
                 "cand(Ky, A, K, V)": "in_cell(Ky, P, _), frame_offset(P, A, K, V)",
                 "mismatch(Ky, A, K)": "in_cell(Ky, P, _), frame_offset(P, A, K, _), !{x}.period(Ky, A, K)",
                 "pair(Ky, A, K, P, Q)": "in_cell(Ky, P, _), frame_offset(P, A, K, V), compose(P, V, Q),"
                                         " in_cell(Ky, Q, _)",
                 "cell(Ky, P, V)": "{x}.cell(Ky, P, V)"},
                pairs=(("cand(Ky, A, K, V)", "mismatch(Ky, A, K)",
                        "{x}.period(Ky, A, K), axis_of(D, A), jump_offset(D, K, V)"),))


SPECS = {"Components8": components8, "Reach": reach, "Rim": rim(False), "Rim8": rim(True), "Ray": ray,
         "Between": between, "Slide": slide, "Diagonal": diagonal, "DiagPlacement": diag_placement,
         "Gravity": gravity, "D4Map": d4_map, "OffsetInvariance": offset_invariance}
"""Each component's spec, by the present component's name."""

RUNNABLE = {"Components8", "Reach", "Diagonal", "DiagPlacement"}
"""The components whose shape holds only present-lib names."""
