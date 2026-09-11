"""The solver docs and lib.dl as a session reads them."""

from pathlib import Path

from dl.context import DOCS, entry_index, lib_signatures, render


def test_lib_signatures_keep_the_interface_and_drop_the_bodies():
    out = lib_signatures("""\
// Opposite Dir on the same axis.
.decl opposite(d: Dir, opp: Dir)
opposite(DIR_T, DIR_B).

// Dispatch functors (C++).
.functor dist_proj(d: Dir, t: number): number

.comp Components<Key> {
    .decl node(key: Key, p: Position)

    .decl edge(key: Key, d: Dir)  // input

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
    assert "functor" not in out                          # a functor is implementation
    assert ".decl node(key: Key, p: Position)  // input" in out
    assert ".decl edge(key: Key, d: Dir)  // input\n" in out   # the mark is written once
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


def test_lib_signatures_drop_a_comment_that_documents_a_dropped_body():
    out = lib_signatures("""\
// What the comp is for.

.comp Walk<Key> {
    // The cells to walk.
    .decl cell(key: Key, p: Position)

    // How the walk closes the cycle, which the rule below holds.

    .decl seen(key: Key, p: Position)
    seen(Ky, P) :- cell(Ky, P).
}
""")
    assert "// What the comp is for." in out            # a top-level comment stands
    assert "// The cells to walk." in out               # so does one over a kept line
    assert "closes the cycle" not in out


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


def test_render_reads_the_listed_docs_in_order(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in DOCS:
        (docs / name).write_text(f"# {name}\n")
    (docs / "backlog.md").write_text("# Backlog\n\n2. a queued idea\n")
    (docs / "patterns.md").write_text("# Patterns\n\n## A pattern\n\nIts claim.\n")
    (docs / "style.md").write_text(
        "<!-- for the editor -->\n\n# Style\n\nEvery word <!-- aka all --> of it.\n"
        "\n+ notation\n    + w — a word\n- **word** — a unit.\n    + w ∈ W\n"
        "\n## Terms <!-- deferred -->\n\n- **term** — a name.\n\n## Rules\n\nOne rule.\n    + ∀r\n"
    )
    lib = tmp_path / "lib.dl"
    lib.write_text(".decl out(p: Position)\nout(P) :- in(P, _).\n")

    out = render(docs, lib)
    assert out.startswith("# Handbook\n")
    assert "a queued idea" not in out
    assert out.index("# docs/wf-solver/style.md") < out.index("# docs/wf-solver/patterns.md")
    assert "# docs/wf-solver/patterns.md — index\n" in out
    assert "- **A pattern** — Its claim.\n" in out
    assert ("# docs/wf-solver/style.md\n\n"
            "Cited tasks carry worked applications of the principle they"
            " sit under. Grep the task id in docs/wf-solver/style.md to"
            " read one.\n\n"
            "The Terms section is in the source: read it in"
            " docs/wf-solver/style.md when a term is unclear.\n\n"
            "# Style\n\nEvery word of it.\n\n- **word** — a unit.\n\n## Rules\n\nOne rule.\n") in out
    assert "a name" not in out
    assert "notation" not in out and "∀r" not in out
    assert "# docs/wf-solver/procedure.md\n\n# procedure.md\n" in out   # no note without notes
    assert "# programs/lib.dl — signatures\n" in out
    assert "out(P) :- in(P, _)." not in out


def test_the_handbook_agent_is_the_handbook_under_its_frontmatter(tmp_path):
    from dl.context import AGENT_META, ROLE_NOTE, agent_definition, write_agent
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in DOCS:
        (docs / name).write_text(f"# {name}\n")
    lib = tmp_path / "lib.dl"
    lib.write_text(".decl out(p: Position)\n")
    path = write_agent(tmp_path / "agents" / "handbook.md", docs, lib)
    text = path.read_text()
    assert text == agent_definition(render(docs, lib))
    front, _, body = text.removeprefix("---\n").partition("\n---\n")
    assert front.splitlines() == [f"{k}: {v}" for k, v in AGENT_META.items()]
    assert body == ROLE_NOTE + render(docs, lib)
    assert not list((tmp_path / "agents").glob("*.tmp"))
    stamp = path.stat().st_mtime_ns
    assert write_agent(path, docs, lib) == path
    assert path.stat().st_mtime_ns == stamp             # the same definition is left alone
    lib.write_text(".decl out(p: Position, col: Color)\n")
    write_agent(path, handbook=render(docs, lib))       # a caller's own render
    assert path.read_text() == agent_definition(render(docs, lib))


def test_a_sweep_takes_the_digest_files_no_caller_has_taken_lately(tmp_path):
    import os
    import time

    from dl.context import DIGEST_TTL, sweep_digests

    now = time.time()

    def digest(name: str, age: float) -> Path:
        path = tmp_path / name
        path.write_text(name)
        os.utime(path, (now - age, now - age))
        return path

    current = digest("appendix-aaaaaaaaaa.md", DIGEST_TTL * 2)
    stale = digest("appendix-bbbbbbbbbb.md", DIGEST_TTL + 60)
    taken = digest("appendix-cccccccccc.md", DIGEST_TTL - 60)
    other = digest("handbook-dddddddddd.md", DIGEST_TTL + 60)

    sweep_digests(current, now)
    assert not stale.exists()
    # the file the caller holds, one a caller took within the window, and a
    # file of another family
    assert current.exists() and taken.exists() and other.exists()
