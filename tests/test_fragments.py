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
    check_closure,
    check_dl_comments,
    check_file_fragments,
    check_paths,
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
