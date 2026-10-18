"""An entry document's attribute whose value is one of a closed set of
forms, read with its absence as the set's default form."""

from __future__ import annotations

from enum import Enum

import controlled_markdown as nm


def attr_form[F: Enum](document: nm.Node, name: str, forms: type[F],
                       default: F) -> F:
    value = document.attr(name)
    if value is None:
        return default
    try:
        return forms(value.strip())
    except ValueError:
        raise SystemExit(nm.mctx(
            "`{name}: {value}` in {source} is no {name} form; the forms are "
            "{forms}").format(
                name=name, value=value.strip(), source=document.source,
                forms=", ".join(str(f.value) for f in forms))) from None
