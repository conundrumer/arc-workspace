"""The checks over the lib's sources, on fixtures."""

from pathlib import Path

from dl.libcheck import check, doc_adjacency, input_marks, module_order


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


def test_doc_adjacency_flags_a_block_over_nothing_and_a_file_doc_below_an_item():
    findings = doc_adjacency(Path("sets.dl"), """\
//! The file.
/// Over a decl.
.decl a(x: number)
/// Over a rule.
a(1).
/// Over a blank line.

.comp Tally<Key> {
    /// Over an inner decl.
    .decl item(key: Key)  // @input
}
//! Too low.
""")
    assert findings == [
        "sets.dl:4: a `///` block stands over no declaration",
        "sets.dl:6: a `///` block stands over no declaration",
        "sets.dl:12: a `//!` block is not at the file's top",
    ]


def test_check_runs_every_check_over_the_root_and_its_modules(tmp_path: Path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib.dl").write_text(
        '//! The root.\n.decl in(p: number)  // @input\n#include "lib/a.dl"\n#include "lib/b.dl"\n')
    (tmp_path / "lib" / "a.dl").write_text(".decl a(x: number)\na(X) :- b(X).\n")
    (tmp_path / "lib" / "b.dl").write_text(".decl b(x: number)\nb(X) :- in(X).\n")
    assert check(tmp_path / "lib.dl") == [
        "`a.dl` reads `b`, defined in `b.dl`, which is included later",
    ]
