"""The checks over the lib's sources, on fixtures."""

from pathlib import Path

from dl.libcheck import input_marks, module_order


def test_input_marks_agree_with_the_rules_inside_a_comp():
    findings = input_marks(Path("cells.dl"), """\
.decl in(p: Position)  // @input
.decl top(p: Position)  // @input
top(P) :- in(P).
.decl table(d: Dir)
table(DIR_T).
.comp Ray<Key> {
    .decl dir(key: Key, d: Dir8)  // @input
    .decl mark(key: Key, p: Position)
    .decl step(delta: Offset)  // @input
    step([-1, 1, 0, 0]).
    .decl cast(key: Key, p: Position)  // @input
    cast(Ky, P) :- mark(Ky, P).
    .decl ray(key: Key, p: Position)
    ray(Ky, P) :- cast(Ky, P), dir(Ky, _).
    .init _in = _Inner<Key>
    _in.cand(Ky) :- dir(Ky, _).         // feeds the nested instance, derives nothing here
    .comp _Inner<K> {
        .decl cand(key: K)
    }
}
""")
    assert findings == [
        "cells.dl: `top` has a rule and an `@input` mark",
        "cells.dl: `Ray.mark` has no rule and no `@input` mark",
        "cells.dl: `Ray.cast` has a rule and an `@input` mark",
        "cells.dl: `_Inner.cand` has no rule and no `@input` mark",
    ]


def test_module_order_names_the_forward_reference():
    findings = module_order([
        (Path("lib.dl"), '.type Dir <: number\n#include "lib/orders.dl"\n'),
        (Path("orders.dl"), ".decl rank(d: Dir, k: number)\nrank(D, K) :- dist(D, K), DIR_T = 10.\n"),
        (Path("box.dl"), "#define DIR_T 10\n.decl dist(d: Dir, k: number) inline\n"
                         "dist(D, K) :- rank(D, K).\n"),   # a read of an earlier file is fine
    ])
    assert findings == [
        "`orders.dl` reads `DIR_T`, defined in `box.dl`, which is included later",
        "`orders.dl` reads `dist`, defined in `box.dl`, which is included later",
    ]


