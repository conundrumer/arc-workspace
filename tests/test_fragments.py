"""The extractor's own errors, which a run over a correct repo never shows.

`check` reads every `mctx` literal in the repo. While the repo is correct none
of these three fires, so a regression that stopped reporting one would pass the
check in silence. Each fixture here breaks one rule, and each is written where
the repo's own check does not reach it.
"""

import pytest

from controlled_markdown import ControlledMarkdownError, check_file_fragments

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
