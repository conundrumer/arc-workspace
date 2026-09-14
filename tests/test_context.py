"""The solver docs and the lib as a session reads them."""

from pathlib import Path

from dl.context import (DOCS, NOTES_DROPPED, entry_index, lib_doc, lib_entries,
                        lib_sources, render, role_agent)


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


def test_lib_doc_folds_define_groups_and_subtype_runs():
    out = lib_doc("""\
.type Color <: number
.type Dir <: number
.type Axis <: number

/// The rotation subgroup of D4.
.type C4 <: D4
.type Dir8 = Dir | DiagDir

/// The edges.
#define DIR_T 10
#define DIR_B 11

#define AXIS_V 20
#define AXIS_H 21

/// The zero box.
#define ZERO [0, 0, 0, 0]

/// Divide.
.decl divide(p: Position, a: Axis, n: number,
             p_outer: Position) inline
divide(P, A, N, P_outer) :- true.
""")
    assert "```\n.type Color, Dir, Axis <: number\n```" in out
    assert "The rotation subgroup of D4.\n\n```\n.type C4 <: D4\n\n.type Dir8 = Dir | DiagDir\n```" in out
    assert "The edges.\n\n```\nDIR_T DIR_B\n\nAXIS_V AXIS_H\n```" in out   # a blank line ends a group
    assert "The zero box.\n\n```\n#define ZERO [0, 0, 0, 0]\n```" in out
    assert "             p_outer: Position) inline\n```" in out          # a wrapped decl stays whole
    assert ":- true" not in out


def test_lib_doc_renders_a_block_over_no_item_where_it_stands():
    out = lib_doc("""\
/// Over nothing.

.decl a(x: number)
""")
    assert out == "```\n.decl a(x: number)\n```\n\nOver nothing.\n"


def test_lib_sources_follow_the_root_includes_in_order(tmp_path: Path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib.dl").write_text('#include "lib/b.dl"\n#include "lib/a.dl"\n')
    (tmp_path / "lib" / "a.dl").write_text(".decl a(x: number)\n")
    (tmp_path / "lib" / "b.dl").write_text(".decl b(x: number)\n")
    assert [(p.name, t) for p, t in lib_sources(tmp_path / "lib.dl")] == [
        ("lib.dl", '#include "lib/b.dl"\n#include "lib/a.dl"\n'),
        ("b.dl", ".decl b(x: number)\n"),
        ("a.dl", ".decl a(x: number)\n"),
    ]


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


def test_lib_entries_gives_one_line_per_public_top_level_item():
    out = lib_entries("""\
//! The file's own doc.

/// Opposite Dir on the same axis. A second sentence.
///
/// A second paragraph.
.decl opposite(d: Dir, opp: Dir)

.functor dist_proj(d: Dir, t: number): number

/// Connected components.
.comp Components<Key> {
    /// The node set.
    .decl node(key: Key, p: Position)  // @input
    .decl label(key: Key, p: Position, id: Ident)
}

.type Color <: number
.type Dir <: number

/// The edges.
#define DIR_T 10
#define DIR_B 11

.decl plain(x: number)

/// A private comp.
.comp _Room<Key> {
    .decl cand(key: Key)  // @input
}
""")
    assert out == (
        "The file's own doc.\n\n"
        "- **opposite** — Opposite Dir on the same axis.\n"
        "- **Components** — Connected components.\n"
        "- **Color**, **Dir**\n"
        "- **DIR_T**, **DIR_B** — The edges.\n"
        "- **plain**(x: number)\n")


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
    cut = "\n---\n\n# programs/lib.dl"
    assert index[:index.index(cut)] == out[:out.index(cut)]      # the docs render the same
    assert index.endswith(
        "\n---\n\n# programs/lib.dl — index\n\n"
        "A module's interface file, its path with `.md` for `.dl`, holds each unit's"
        " signature and the rest of its doc.\n\n"
        "The root.\n\n"
        "- **out** — The output.\n"
        "\n---\n\n# programs/lib/sets.dl — index\n\nThe sets.\n\n"
        "- **s**(x: number)\n")
    assert ".decl out" not in index


def _docs(tmp_path: Path) -> tuple[Path, Path]:
    """A docs directory holding each listed doc, and a lib file."""
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in DOCS:
        (docs / name).write_text(f"# {name}\n")
    lib = tmp_path / "lib.dl"
    lib.write_text(".decl out(p: Position)\n")
    return docs, lib


def test_every_render_keeps_the_plus_lines_and_strips_the_glosses(tmp_path: Path):
    docs, lib = _docs(tmp_path)
    (docs / "principles.md").write_text(
        "<!-- for the editor -->\n\n# Principles\n\n"
        "- A rule. 00576224 <!-- the grid tiles under a flip -->\n    + fam(M) = T\n")

    for out in (render(docs, lib), render(docs, lib, lib_index=True)):
        heading = out.index("# docs/wf-solver/principles.md")
        section = out[heading:out.index("\n---\n", heading)]
        assert "- A rule. 00576224\n    + fam(M) = T\n" in section
        assert "the grid tiles under a flip" not in section and "for the editor" not in section
        assert NOTES_DROPPED.format(rel="docs/wf-solver/principles.md") in section


def test_role_agent_reads_the_first_line():
    assert role_agent("Agent: handbook-expanded\n\nYou run Simplify.\n") == (
        "handbook-expanded", "You run Simplify.\n")
    assert role_agent("You survey.\n\nAgent: not-a-header\n") == (
        "handbook", "You survey.\n\nAgent: not-a-header\n")


def test_write_agent_writes_both_agents_and_the_interface_files(tmp_path: Path):
    from dl.context import (EXPANDED_AGENT_META, agent_definition, expanded_agent_path,
                            write_agent)
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in DOCS:
        (docs / name).write_text(f"# {name}\n")
    lib = tmp_path / "lib.dl"
    lib.write_text('#include "lib/sets.dl"\n/// The output.\n.decl out(p: Position)\n')
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "sets.dl").write_text("//! The sets.\n.decl s(x: number)\n")

    path = write_agent(tmp_path / "agents" / "handbook.md", docs, lib)
    expanded = expanded_agent_path(path)
    assert expanded.name == "handbook-expanded.md"
    assert expanded.read_text() == agent_definition(render(docs, lib), EXPANDED_AGENT_META)
    assert (tmp_path / "lib.md").read_text() == (
        "<!-- Generated from lib.dl by scripts/context.py. -->\n\n" + lib_doc(lib.read_text()))
    assert (tmp_path / "lib" / "sets.md").read_text() == (
        "<!-- Generated from sets.dl by scripts/context.py. -->\n\n"
        "The sets.\n\n```\n.decl s(x: number)\n```\n")


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


def test_write_codex_writes_the_agents_doc_and_the_project_config(tmp_path: Path):
    from dl.context import CODEX_CONFIG, CODEX_STYLE, codex_config, uncommented, write_codex
    docs = tmp_path / "docs"
    docs.mkdir()
    for name in DOCS:
        (docs / name).write_text(f"# {name}\n")
    lib = tmp_path / "lib.dl"
    lib.write_text(".decl out(p: Position)\n")
    (tmp_path / "CLAUDE.md").write_text("# repo\n")

    agents, config = write_codex(tmp_path, docs, lib)
    assert agents == tmp_path / "AGENTS.md"
    assert agents.read_text() == render(docs, lib) + "\n---\n\n# CLAUDE.md\n\n# repo\n"
    assert config == tmp_path / CODEX_CONFIG
    assert config.read_text() == codex_config(None)
    assert "developer_instructions" not in config.read_text()   # no style file yet

    (tmp_path / CODEX_STYLE).write_text('# Style\n<!-- off -->\n- on "quoted" <!-- aside -->\n')
    write_codex(tmp_path, docs, lib)
    import tomllib
    loaded = tomllib.loads(config.read_text())
    assert loaded["developer_instructions"] == '# Style\n- on "quoted"\n'
    assert loaded["project_doc_max_bytes"] > 0 and loaded["sandbox_mode"] == "workspace-write"
    assert uncommented("a\n<!-- multi\nline -->\nb\n") == "a\nb\n"


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
