"""The expansions of the order components onto `Order`, `Tally` and
`Canon`, as `instances.Spec` shapes: the score form of `Order` for
`Ordinal`, `Extremes`, `ArgExtremes`, `IndexCycle` and `Mode`, the `before`
form for `OrderFrame`, `Canon` over the identity for `IdentOf`, and a `Tally`
for `KeyedSetCompare.pattern_size`.

`LexOrder` has both forms. Where a clause reads its `before`, the `before`
form states each ordered pair of cells. Otherwise the score form gives each
cell two rows, `score` the first of its two distances from the corner and
`secondary_score` the second, so the order is the lexicographic order of the
two.
"""
from __future__ import annotations

from arclog_convert.libmap.instances import Spec


def ordinal(inst, ex):
    return Spec(".init {x} = Order<{Key}, number>",
                {"idx_set(Ky, K)": ["{x}.elem(Ky, K)", "{x}.score(Ky, K, K)"]},
                {"rank(Ky, K, R)": "{x}.rank(Ky, K, R)", "rank_desc(Ky, K, R)": "{x}.rank_desc(Ky, K, R)",
                 "idx_set(Ky, K)": "{x}.elem(Ky, K)"})


def extremes(inst, ex):
    return Spec(".init {x} = Order<{Key}, number>",
                {"cand(Ky, S)": ["{x}.elem(Ky, S)", "{x}.score(Ky, S, S)"]},
                {"high(Ky, S)": "{x}.last(Ky, S)", "low(Ky, S)": "{x}.first(Ky, S)", "cand(Ky, S)": "{x}.elem(Ky, S)"})


def index_cycle(inst, ex):
    return Spec(".init {x} = Order<{Key}, number>",
                {"idx(Ky, K)": ["{x}.elem(Ky, K)", "{x}.score(Ky, K, K)"]},
                {"succ(Ky, K, K2)": "{x}.cyclic_successor(Ky, K, K2)", "idx(Ky, K)": "{x}.elem(Ky, K)"})


def arg_extremes(inst, ex):
    return Spec(".type {x}_cand = [v: {Val}, s: number]\n.init {x} = Order<{Key}, {x}_cand>",
                {"cand(Ky, V, S)": ["{x}.elem(Ky, [V, S])", "{x}.score(Ky, [V, S], S)"]},
                {"high(Ky, V, S)": "{x}.last(Ky, [V, S])", "low(Ky, V, S)": "{x}.first(Ky, [V, S])",
                 "cand(Ky, V, S)": "{x}.elem(Ky, [V, S])"})


def mode(inst, ex):
    ky, m, n = ex.names(inst, "item", ["Ky", "M", "N"])
    if inst.type_args[0].name == "Unit":
        k, decls = m, ".init {x}_count = Tally<{Member}, {Token}>\n"
        head = "$U()"
    else:
        k, decls = f"[{ky}, {m}]", ".type {x}_key = [key: {Key}, m: {Member}]\n.init {x}_count = Tally<{x}_key, {Token}>\n"
        head = ky
    c = "N" if n != "N" and "N" not in (ky, m) else "Count"
    return Spec(decls + ".init {x} = Order<{Key}, {Member}>",
                {f"item({ky}, {m}, {n})": [f"{{x}}_count.item({k}, {n})"]},
                {f"mode({ky}, {m})": f"{{x}}.last({ky}, {m})", f"tally({ky}, {m}, {c})": f"{{x}}_count.tally({k}, {c})",
                 f"item({ky}, {m}, {n})": f"{{x}}_count.item({k}, {n})"},
                f"{{x}}.elem({head}, {m}) :- {{x}}_count.tally({k}, _).\n"
                f"{{x}}.score({head}, {m}, {c}) :- {{x}}_count.tally({k}, {c}).")


def ident_of(inst, ex):
    return Spec(".init {x} = Canon<{T}>",
                {"value(V)": ["{x}.equiv(V, V)"]},
                {"id(V, I)": "{x}.id(V, I)", "value(V)": "{x}.equiv(V, V)"})


def keyed_set_compare(inst, ex):
    if "pattern_size" not in ex.reads_of(inst):
        return None
    return Spec(".init {x} = KeyedSetCompare<{Key}, {Pat}, {Member}>\n.init {x}_size = Tally<{Pat}, {Member}>",
                {"pattern_member(P, M)": ["{x}.pattern_member(P, M)", "{x}_size.item(P, M)"],
                 "observed_member(O, M)": ["{x}.observed_member(O, M)"]},
                {"pattern_size(P, N)": "{x}_size.tally(P, N)", "covers(O, P)": "{x}.covers(O, P)",
                 "equals(O, P)": "{x}.equals(O, P)", "pattern_member(P, M)": "{x}.pattern_member(P, M)",
                 "observed_member(O, M)": "{x}.observed_member(O, M)"})


ORDER_READS = {f"{r}(Ky, A, B)": f"{{x}}.{r}(Ky, A, B)" for r in ("before", "next")} | \
    {f"{r}(Ky, T, R)": f"{{x}}.{r}(Ky, T, R)" for r in ("rank", "rank_desc")} | \
    {f"{r}(Ky, T)": f"{{x}}.{r}(Ky, T)" for r in ("first", "last", "elem")}


def lex_order(inst, ex):
    cells = "{x}.elem(Ky, P) :- in_cell(Ky, P).\n"
    if "before" in ex.reads_of(inst):
        order = ("{x}.before(Ky, Q, P) :- in_cell(Ky, Q), in_cell(Ky, P), in_corner(Ky, Diag), in_axis(Ky, A),"
                 " (dir_of(Diag, A, D), nearer(D, Q, P) ;"
                 " diag_dirs(Diag, A, D, D2), same_dist(D, Q, P), nearer(D2, Q, P)).")
    else:
        dist = "in_cell(Ky, P), in_corner(Ky, Diag), in_axis(Ky, A), diag_dist(P, Diag, A, K1, K2)."
        order = f"{{x}}.score(Ky, P, K1) :- {dist}\n{{x}}.secondary_score(Ky, P, K2) :- {dist}"
    return Spec(".init {x} = Order<{Key}, Position>", {},
                ORDER_READS | {"cell(Ky, P)": "{x}.elem(Ky, P)"}, cells + order)


def order_frame(inst, ex):
    ky, m, p = ex.names(inst, "member", ["Ky", "M", "P"])
    v = dict(Ky=ky, M=m, P=p)
    return Spec(".type {x}_dir = [key: {Key}, a: Axis, d: Dir]\n.init {x} = Order<{x}_dir, {T}>\n"
                ".decl {x}_pos(key: {Key}, m: {T}, p_pos: Position)", {},
                {"pos(Ky, M, P)": "{x}_pos(Ky, M, P)", "axis(Ky, A)": "in_axis(Ky, A)",
                 "member(Ky, M, P)": "in_member(Ky, M, P)"},
                ("{x}.elem([{Ky}, A, D], {M}) :- in_member({Ky}, {M}, _), in_axis({Ky}, A), axis_of(D, A).\n"
                 "{x}.before([{Ky}, A, D], {M}, M_b) :- in_member({Ky}, {M}, {P}), in_member({Ky}, M_b, Q), {M} != M_b,"
                 " in_axis({Ky}, A), axis_of(D, A), dist({P}, D, K1), dist(Q, D, K2), K1 < K2.\n"
                 "{x}_pos({Ky}, {M}, P_pos) :- {x}.rank([{Ky}, A, D], {M}, R1), {x}.rank_desc([{Ky}, A, D], {M}, R2),"
                 " axis_inset(D, R1, R2, P_pos).").replace("{Ky}", ky).replace("{M}", m).replace("{P}", p))


def divider_tiles(inst, ex):
    rels = ("on_divider", "part_idx", "part_of", "tile_of")
    return Spec(".type {x}_dir = [key: {Key}, d: Dir]\n.init {x}_rank = Order<{x}_dir, number>\n"
                ".decl {x}_on_divider(key: {Key}, p: Position, a: Axis)\n"
                ".decl {x}_part_idx(key: {Key}, p: Position, d: Dir, n: number)\n"
                ".decl {x}_part_of(key: {Key}, p: Position, a: Axis, p_part: Position)\n"
                ".decl {x}_tile_of(key: {Key}, p: Position, p_tile: Position)", {},
                {"on_divider(Ky, P, A)": "{x}_on_divider(Ky, P, A)", "part_idx(Ky, P, D, N)": "{x}_part_idx(Ky, P, D, N)",
                 "part_of(Ky, P, A, Q)": "{x}_part_of(Ky, P, A, Q)", "tile_of(Ky, P, T)": "{x}_tile_of(Ky, P, T)",
                 "cell(Ky, P)": "in_cell(Ky, P)", "divider(Ky, A, L)": "in_divider(Ky, A, L)"},
                "{x}_rank.elem([Ky, D], K) :- in_divider(Ky, A, L), axis_of(D, A), dist(L, D, K).\n"
                "{x}_rank.score([Ky, D], K, K) :- in_divider(Ky, A, L), axis_of(D, A), dist(L, D, K).\n"
                "{x}_rank.score([Ky, D], K, K) :- in_cell(Ky, P), dir_elem(D), dist(P, D, K).\n"
                "{x}_rank.probe([Ky, D], K) :- in_cell(Ky, P), dir_elem(D), dist(P, D, K).\n"
                "{x}_on_divider(Ky, P, A) :- in_cell(Ky, P), in_divider(Ky, A, L), axis_of(D, A), same_dist(D, P, L).\n"
                "{x}_part_idx(Ky, P, D, N) :- in_cell(Ky, P), axis_of(D, A), !{x}_on_divider(Ky, P, A),"
                " dist(P, D, K), {x}_rank.rank([Ky, D], K, N).\n"
                "{x}_part_of(Ky, P, A, P_part) :- axis_of(D, A), opposite(D, D2), {x}_part_idx(Ky, P, D, N1),"
                " {x}_part_idx(Ky, P, D2, N2), axis_inset(D, N1, N2, P_part).\n"
                "{x}_tile_of(Ky, P, P_tile) :- {x}_part_of(Ky, P, A, P1), perp(A, A2), {x}_part_of(Ky, P, A2, P2),"
                " compose(P1, P2, P_tile).",
                derive=frozenset({"divider"}),
                moved={r: f"{{x}}_{r}" for r in (*rels, "divider", "cell")})


SPECS = {"Ordinal": ordinal, "Extremes": extremes, "IndexCycle": index_cycle, "ArgExtremes": arg_extremes,
         "Mode": mode, "IdentOf": ident_of, "KeyedSetCompare": keyed_set_compare,
         "LexOrder": lex_order, "OrderFrame": order_frame, "DividerTiles": divider_tiles}
"""Each component's spec, by the present component's name."""

RUNNABLE = {"IdentOf", "LexOrder", "OrderFrame"}
"""The components whose shape holds only present-lib names."""
