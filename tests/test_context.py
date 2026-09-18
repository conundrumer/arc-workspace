"""The solver docs and the lib as a session reads them."""

from pathlib import Path

from dl.context import DOCS, lib_doc, render


def test_lib_doc_renders_docs_as_prose_and_the_interface_in_code():
    out = lib_doc("""\
//! The file's own doc.
//!
//! A second paragraph.

/// Opposite Dir on the same axis.
.decl opposite(d: Dir, opp: Dir)
opposite(DIR_T, DIR_B).

// A note for the maintainer.
.functor dist_proj(d: Dir, t: number): number

/// The task input grid.
.decl in(p: Position, col: Color)  // @input

/// Connected components.
///
/// - one point
/// - another
.comp Components<Key> {
    /// The node set.
    .decl node(key: Key, p: Position)  // @input

    /// The steps that join nodes.
    .decl step(delta: Offset)  // @input
    step([-1, 1, 0, 0]). step([1, -1, 0, 0]).

    /// A private helper and its doc.
    .decl _seen(key: Key)
    _seen(Ky) :- node(Ky, _).
    .init _ax = AxisFrame<Key>

    /// The id of the component p belongs to.
    .decl label(key: Key, p: Position, id: Ident)
    label(Ky, P, Min) :-
        node(Ky, P), Min = min ord(Q) : { conn(Ky, P, Q) }.
    .decl conn(key: Key, p: Position, q: Position)
    conn(Ky, P, Q) :- node(Ky, P), node(Ky, Q).
}

/// A private comp and its doc.
.comp _Room<Key> {
    .decl cand(key: Key)  // @input
}
""")
    assert out.startswith("The file's own doc.\n\nA second paragraph.\n\n")
    assert "Opposite Dir on the same axis.\n\n```\n.decl opposite(d: Dir, opp: Dir)\n```" in out
    assert "opposite(DIR_T, DIR_B)." not in out            # a top-level fill goes
    assert "maintainer" not in out and "functor" not in out
    assert "```\n.decl in(p: Position, col: Color)  // @input\n```" in out
    assert ("Connected components.\n\n- one point\n- another\n\n```\n"
            ".comp Components<Key> {\n"
            "    // The node set.\n"
            "    .decl node(key: Key, p: Position)  // @input\n"
            "\n"
            "    // The steps that join nodes.\n"
            "    .decl step(delta: Offset)  // @input\n"
            "    step([-1, 1, 0, 0]). step([1, -1, 0, 0]).\n"     # an input's default stays
            "\n"
            "    // The id of the component p belongs to.\n"
            "    .decl label(key: Key, p: Position, id: Ident)\n"
            "\n"
            "    .decl conn(key: Key, p: Position, q: Position)\n"
            "}\n```\n") in out
    assert "_seen" not in out and "_ax" not in out and "_Room" not in out
    assert "private" not in out                          # a hidden item's doc goes with it
    assert "min ord(Q)" not in out


def test_render_reads_the_listed_docs_in_order(tmp_path: Path):
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in DOCS:
        (docs / name).write_text(f"# {name}\n")
    (docs / "backlog.md").write_text("# Backlog\n\n2. a queued idea\n")
    (docs / "patterns.md").write_text("# Patterns\n\n## A pattern\n\nIts claim.\n")
    (docs / "style.md").write_text(
        "<!-- for the editor -->\n\n# Style\n\nEvery word <!-- aka all --> of it.\n"
        "\n- **word** — a unit.\n    + w ∈ W\n"
        "\n## Terms <!-- deferred -->\n\n- **term** — a name.\n\n## Rules\n\nOne rule.\n"
    )
    lib = tmp_path / "lib.dl"
    lib.write_text('//! The root.\n#include "lib/sets.dl"\n'
                   "/// The output.\n.decl out(p: Position)\nout(P) :- in(P, _).\n")
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "sets.dl").write_text("//! The sets.\n.decl s(x: number)\n")

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
            "# Style\n\nEvery word of it.\n\n- **word** — a unit.\n    + w ∈ W\n"
            "\n## Rules\n\nOne rule.\n") in out
    assert "a name" not in out
    assert "# docs/wf-solver/procedure.md\n\n# procedure.md\n" in out   # no note without notes
    assert ("\n---\n\n# programs/lib.dl\n\nThe root.\n\nThe output.\n\n"
            "```\n.decl out(p: Position)\n```\n"
            "\n---\n\n# programs/lib/sets.dl\n\nThe sets.\n\n"
            "```\n.decl s(x: number)\n```\n") in out
    assert "out(P) :- in(P, _)." not in out and "#include" not in out

    index = render(docs, lib, lib_index=True)
    assert index.endswith(
        "\n---\n\n# programs/lib.dl — index\n\n"
        "A module's interface file, its path with `.md` for `.dl`, holds each component's"
        " signature and the rest of its doc.\n\n"
        "The root.\n\n"
        "- **out** — The output.\n"
        "\n---\n\n# programs/lib/sets.dl — index\n\nThe sets.\n\n"
        "- **s**(x: number)\n")
    assert ".decl out" not in index


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
    assert text == agent_definition(render(docs, lib, lib_index=True))
    front, _, body = text.removeprefix("---\n").partition("\n---\n")
    assert front.splitlines() == [f"{k}: {v}" for k, v in AGENT_META.items()]
    assert body == ROLE_NOTE + render(docs, lib, lib_index=True)
    assert not list((tmp_path / "agents").glob("*.tmp"))
    stamp = path.stat().st_mtime_ns
    assert write_agent(path, docs, lib) == path
    assert path.stat().st_mtime_ns == stamp             # the same definition is left alone
    lib.write_text("/// The output.\n.decl out(p: Position, col: Color)\n")
    write_agent(path, docs, lib)
    assert "- **out** — The output." in path.read_text()


