"""Controlled Markdown: parser, formatter, and renderers.

A document is a tree of nodes. Every line is one node, and every line is valid
CommonMark. `parse` reads text into a tree, `write` puts a tree back as
canonical text, and the renderers project a tree down to ordinary Markdown for
an agent to read.

A node has attributes. `+ name: value` is an attribute of the node it is
nested under, and it describes that node. `* name: value` is a directive: a
node with no text of its own, holding that attribute, and the lines under it
are the lines it governs.

`Registry` holds the documents a render draws on, together with each document's
path and its sections, keyed by the slug of each heading's text. An `include`
directive names a file and brings that whole document; an `inline` directive
names a section by `#<id>` or `<path>#<id>` and brings the lines under its
heading. The registry reads a document the first time a directive names it.

A render takes the values its variables read. `{{name}}` in a node's text is
replaced by the value of that name, and `if` and `unless` read the values
too.

A document may open with a front matter block, `---` to `---`. `parse` keeps it
verbatim, `write` puts it back unchanged, and a render leaves it out.

The package holds Controlled Markdown as a whole: `nodes` holds the node
tree, `parser` the parser, `formatter` the formatter, `registry` the
registry, `directives` the directives a render acts on, `prose` the checks
of prose in code, `document_set` the checks of a document set with the
links a node's text holds, `renderers` the renderers, `round_trip` the
formatter's round trip, and `xrefs` the references from a document to
code. This module gives every name of the package.
`nodes`, `parser`, `formatter`, `registry` and `directives` import from
the modules that hold what they use; each other module imports from this
module, which gives their names once those five are imported.
"""

from __future__ import annotations

from controlled_markdown.nodes import (
    ControlledMarkdownError as ControlledMarkdownError,
    Rule as Rule,
    slug as slug,
    INDENT as INDENT,
    DOCUMENT as DOCUMENT,
    CONTENT as CONTENT,
    ATTRIBUTE as ATTRIBUTE,
    QUOTE as QUOTE,
    TABLE as TABLE,
    CODE as CODE,
    HEADING as HEADING,
    Node as Node,
)
from controlled_markdown.parser import (
    BLOCK_RE as BLOCK_RE,
    ESCAPE_RE as ESCAPE_RE,
    unescape as unescape,
    escape as escape,
    FRONT_FENCE as FRONT_FENCE,
    split_front as split_front,
    BLOCK_MARKER as BLOCK_MARKER,
    BLOCK_KIND as BLOCK_KIND,
    FENCE_RE as FENCE_RE,
    NUMBERED_RE as NUMBERED_RE,
    HEADING_RE as HEADING_RE,
    CLOSER_RE as CLOSER_RE,
    RESERVED as RESERVED,
    split_named as split_named,
    parse as parse,
    _closes as _closes,
)
from controlled_markdown.formatter import (
    write as write,
    check_order as check_order,
)
from controlled_markdown.registry import (
    Registry as Registry,
    _walk as _walk,
    relative as relative,
)
from controlled_markdown.directives import (
    COMMENT as COMMENT,
    INCLUDE as INCLUDE,
    INLINE as INLINE,
    CODE_OF as CODE_OF,
    QUOTE_OF as QUOTE_OF,
    TEXT_OF as TEXT_OF,
    READERS as READERS,
    Reference as Reference,
    reference as reference,
    resolve_reference as resolve_reference,
)
from controlled_markdown.document_set import (
    reached as reached,
    carried as carried,
    check_closure as check_closure,
    PARTIALS as PARTIALS,
    partials as partials,
    inline_sites as inline_sites,
    PARTIAL_SITES as PARTIAL_SITES,
    check_partial_sites as check_partial_sites,
    check_blocks as check_blocks,
    LINK_RE as LINK_RE,
    SPAN_RE as SPAN_RE,
    EXTERNAL_RE as EXTERNAL_RE,
    SCHEME_RE as SCHEME_RE,
    links as links,
    relative_link as relative_link,
    RelativeToNoFile as RelativeToNoFile,
    target_of as target_of,
    section as section,
    check_links as check_links,
)
from controlled_markdown.prose import (
    form as form,
    mctx as mctx,
    dedent as dedent,
    CARRY_RE as CARRY_RE,
    NOT_OWN_RE as NOT_OWN_RE,
    carry_words as carry_words,
    carry_errors as carry_errors,
    code_carry_errors as code_carry_errors,
    PY_HOLE_RE as PY_HOLE_RE,
    JS_HOLE_RE as JS_HOLE_RE,
    HOLE_NAME_RE as HOLE_NAME_RE,
    FILLED as FILLED,
    Fragment as Fragment,
    JS_TAG_RE as JS_TAG_RE,
    PY_WHOLE_RE as PY_WHOLE_RE,
    JS_WHOLE_RE as JS_WHOLE_RE,
    MARKER_RE as MARKER_RE,
    check_fragment as check_fragment,
    fragments as fragments,
    check_file_fragments as check_file_fragments,
    DOC_PATH_RE as DOC_PATH_RE,
    JS_STRING_RE as JS_STRING_RE,
    check_paths as check_paths,
    CITATION_RE as CITATION_RE,
    check_citations as check_citations,
    check_citation_anchors as check_citation_anchors,
    LINE_MARKER_RE as LINE_MARKER_RE,
    Quote as Quote,
    handbook_sections as handbook_sections,
    check_quotes as check_quotes,
    DL_DOC_RE as DL_DOC_RE,
    dl_fragments as dl_fragments,
    check_dl_comments as check_dl_comments,
)
from controlled_markdown.renderers import brief as brief
from controlled_markdown.renderers import entries as entries
from controlled_markdown.renderers import full as full
from controlled_markdown.renderers import gist as gist
from controlled_markdown.renderers import headings as headings
from controlled_markdown.renderers import markdown_heading_lines as markdown_heading_lines
from controlled_markdown.renderers import markdown_headings as markdown_headings
from controlled_markdown.renderers import outside_fences as outside_fences
from controlled_markdown.renderers import render as render
from controlled_markdown.renderers import render_linked as render_linked
from controlled_markdown.renderers import section_document as section_document
from controlled_markdown.renderers import variables as variables
from controlled_markdown.round_trip import round_trips as round_trips
from controlled_markdown.xrefs import (
    XREF as XREF,
    Xref as Xref,
    xrefs as xrefs,
    span as span,
    CodeReference as CodeReference,
    references as references,
    check_xrefs as check_xrefs,
    Touch as Touch,
    touched as touched,
)
