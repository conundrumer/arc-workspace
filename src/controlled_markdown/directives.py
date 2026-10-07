"""The directives of Controlled Markdown that a render acts on, and the
reference that an `include`, an `inline` or a link writes as
`<path>#<id>`, with the file its path names."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------- directives

# The directives the renderer acts on. `comment` heads an editing note, which
# no reader outside the source sees.
COMMENT = "comment"
INCLUDE = "include"
INLINE = "inline"
CODE_OF = "code"
QUOTE_OF = "quote"
TEXT_OF = "text"
# The directives that read a value, beyond the two that name text to fill.
READERS = (CODE_OF, QUOTE_OF, TEXT_OF, "if", "unless")


# ---------------------------------------------------------------- references


@dataclass(frozen=True)
class Reference:
    """A document's path, empty where the reference names the document that
    holds it, and a section's id, None where the reference holds no `#`."""

    path: str
    ident: str | None


def reference(value: str) -> Reference:
    path, hashed, ident = value.strip().partition("#")
    return Reference(path.strip(), ident.strip() if hashed else None)


def resolve_reference(path: str, base: Path) -> Path:
    """The file a reference's path names, where `base` is the file that
    holds the reference: the path resolves from that file's directory, and
    an empty path names that file."""
    return (base.parent / path).resolve() if path else base.resolve()
