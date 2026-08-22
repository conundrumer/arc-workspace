"""The projection of the solver docs and lib.dl a session reads."""

from pathlib import Path

from dl.context import appendix, entry_index, lib_signatures


def test_lib_signatures_keep_the_interface_and_drop_the_bodies():
    out = lib_signatures("""\
// Opposite Dir on the same axis.
.decl opposite(d: Dir, opp: Dir)
opposite(DIR_T, DIR_B).

.comp Components<Key> {
    .decl node(key: Key, p: Position)

    .decl step(delta: Position)
    step([-1, 1, 0, 0]).

    .decl label(key: Key, p: Position, id: Ident)
    label(Ky, P, Min) :-
        node(Ky, P), Min = min ord(Q) : { conn(Ky, P, Q) }.
}
""")
    assert "// Opposite Dir on the same axis." in out
    assert ".decl opposite(d: Dir, opp: Dir)\n" in out   # a top-level fill goes
    assert "opposite(DIR_T, DIR_B)." not in out
    assert ".decl node(key: Key, p: Position)  // input" in out
    assert "step([-1, 1, 0, 0])." in out                 # a component's fill stays
    assert "min ord(Q)" not in out
    assert ".decl label(key: Key, p: Position, id: Ident)\n" in out


def test_lib_signatures_keep_a_wrapped_declaration_whole():
    out = lib_signatures("""\
.decl divide(p: Position, a: Axis, n: number,
             p_outer: Position) inline
divide(P, A, N, P_outer) :- true.
""")
    assert "p_outer: Position) inline  // input" not in out
    assert "             p_outer: Position) inline\n" in out


def test_entry_index_gives_the_preamble_and_one_line_per_entry():
    out = entry_index("""\
# Patterns

What the doc is.

## Boxes as margin Positions

A rectangular region is one Position: its four edge margins. `geq(P, M)`
expands a box to its cells. A third sentence.

```
geq(P, M)
```

## `cell_split`

Pairs an input cell with its axis split.
""", "docs/wf-solver/patterns.md")
    assert out == (
        "What the doc is.\n\n"
        "One line per entry. Read docs/wf-solver/patterns.md for the entries you need.\n\n"
        "- **Boxes as margin Positions** — A rectangular region is one Position:"
        " its four edge margins.\n"
        "- **`cell_split`** — Pairs an input cell with its axis split.\n")


def test_appendix_indexes_the_catalogs_and_drops_the_backlog(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "backlog.md").write_text("# Backlog\n\n2. a queued idea\n")
    (docs / "patterns.md").write_text("# Patterns\n\n## A pattern\n\nIts claim.\n")
    (docs / "style.md").write_text("# Style\n\nEvery word of it.\n")
    lib = tmp_path / "lib.dl"
    lib.write_text(".decl out(p: Position)\nout(P) :- in(P, _).\n")

    out = appendix(docs, lib)
    assert "a queued idea" not in out
    assert out.index("# docs/wf-solver/style.md") < out.index("# docs/wf-solver/patterns.md")
    assert "# docs/wf-solver/patterns.md — index\n" in out
    assert "- **A pattern** — Its claim.\n" in out
    assert "# docs/wf-solver/style.md\n\n# Style\n\nEvery word of it.\n" in out
    assert "# programs/lib.dl — signatures\n" in out
    assert "out(P) :- in(P, _)." not in out
