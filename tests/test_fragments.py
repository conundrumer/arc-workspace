"""The extractor's own errors, which a run over a correct repo never shows.

`check` reads every `mctx` literal in the repo. While the repo is correct none
of these rules fires, so a regression that stopped reporting one would pass the
check in silence. Each fixture here breaks one rule, and each is written where
the repo's own check does not reach it.
"""

from pathlib import Path

import pytest

from controlled_markdown import (
    ControlledMarkdownError,
    check_citation_anchors,
    check_citations,
    check_closure,
    check_dl_comments,
    check_file_fragments,
    check_paths,
    code_carry_errors,
)

MCTX_LITERAL = '''\
from controlled_markdown import mctx

WORDS = "a sentence the program computes"
MESSAGES = mctx({"a": WORDS})
'''

MCTX_NESTED = '''\
const mctx = (parts) => parts.join('')
const brief = (name) => mctx`- The name is ${`a ${name} nested literal`}.`
'''

HOLE_NAME = '''\
const mctx = (parts) => parts.join('')
const brief = (item) => mctx`- The findings are ${item.findings.join(', ')}.`
'''


@pytest.mark.parametrize(("name", "text", "rule"), [
    ("literal.py", MCTX_LITERAL, "mctx-literal"),
    ("nested.js", MCTX_NESTED, "mctx-nested"),
    ("hole.js", HOLE_NAME, "hole-name"),
])
def test_the_extractor_reports_what_it_cannot_read(tmp_path, name, text, rule):
    path = tmp_path / name
    path.write_text(text)
    with pytest.raises(ControlledMarkdownError) as err:
        check_file_fragments(path, name)
    assert err.value.rule == rule


BREAK_AFTER_NEWLINE = '''\
from controlled_markdown import mctx

TEXT = mctx("""
    one statement
    on two lines
    """)
'''


def test_a_finding_in_a_fragment_that_opens_with_a_newline_is_at_its_text(tmp_path):
    path = tmp_path / "f.py"
    path.write_text(BREAK_AFTER_NEWLINE)
    with pytest.raises(ControlledMarkdownError) as err:
        check_file_fragments(path, "f.py")
    assert (err.value.rule, err.value.line) == ("fragment-break", 4)


BAD_DOC_PATH_PY = '''\
DOC = "docs/handbook/no-such-doc.md"
'''

BAD_DOC_PATH_JS = """\
const DOC = 'docs/handbook/no-such-doc.md'
"""

@pytest.mark.parametrize(("name", "text"), [
    ("named.py", BAD_DOC_PATH_PY),
    ("named.js", BAD_DOC_PATH_JS),
])
def test_a_document_a_program_names_stands_in_the_tree(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    with pytest.raises(ControlledMarkdownError) as err:
        check_paths(path, name, Path.cwd())
    assert err.value.rule == "path-missing"


def write_cited_tree(tmp_path, citation):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/spec.md").write_text("# Spec\n\n## The pose\n")
    code = tmp_path / "code"
    code.write_text(f"// As `docs/spec.md#the-pose` gives.\n// As `{citation}` gives.\n")
    return code


@pytest.mark.parametrize(("citation", "rule"), [
    ("work/engine/reader.md", "path-missing"),
    ("docs/spec.md#no-such-heading", "citation-anchor"),
])
def test_a_citation_in_the_engine_names_a_present_heading(tmp_path, citation, rule):
    code = write_cited_tree(tmp_path, citation)
    errors = list(check_citations(code, "code", tmp_path, frozenset({"docs/spec.md"})))
    assert [(e.line, e.rule) for e in errors] == [(2, rule)]


@pytest.mark.parametrize(("citation", "rules"), [
    ("work/engine/reader.md#terms", []),
    ("docs/spec.md#no-such-heading", ["citation-anchor"]),
])
def test_an_anchor_cited_outside_the_engine_names_a_heading(tmp_path, citation, rules):
    code = write_cited_tree(tmp_path, citation)
    errors = list(check_citation_anchors(code, "code", tmp_path))
    assert [e.rule for e in errors] == rules


BAD_DL_LINK = """\
//! The module's doc, with a link to [Style](docs/handbook/no-such.md).
.decl a(x: number)
"""


def test_a_doc_comment_in_the_lib_takes_the_text_rules(tmp_path):
    path = tmp_path / "mod.dl"
    path.write_text(BAD_DL_LINK)
    with pytest.raises(ControlledMarkdownError) as err:
        check_dl_comments(path, "mod.dl", Path.cwd())
    assert err.value.rule == "link-missing"
    assert err.value.line == 1


CARRY_PY = '''\
from controlled_markdown import mctx

LINE = mctx("The line carries a word in a figurative sense.")
OTHER = mctx("Another line carries a word in a figurative sense.")
'''

CARRY_DL = """\
/// The relation carries a word in a figurative sense.
.decl a(x: number)
/// The relation carries a word in a figurative sense.
.decl b(x: number)
"""


@pytest.mark.parametrize(("name", "text", "lines"), [
    ("carry.py", CARRY_PY, [3, 4]),
    ("carry.dl", CARRY_DL, [1, 3]),
])
def test_prose_in_code_takes_the_literal_word_rule(tmp_path, name, text, lines):
    path = tmp_path / name
    path.write_text(text)
    errors = list(code_carry_errors(path, name))
    assert [(e.rule, e.line) for e in errors] == [("literal-word", n) for n in lines]


def test_the_handbook_links_only_where_its_reader_can_follow(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "one.md").write_text("# One\n- See [Two](docs/two.md).\n")
    (docs / "two.md").write_text("# Two\n- The other one.\n")
    entry = tmp_path / "entry.md"
    entry.write_text("# Entry\n- The lead.\n* include: docs/one.md\n")
    with pytest.raises(ControlledMarkdownError) as err:
        check_closure([entry], {(docs / "two.md").resolve()}, tmp_path)
    assert err.value.rule == "handbook-link"
