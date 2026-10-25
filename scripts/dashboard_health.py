"""The Health section of the ticket dashboard: rows the user can act on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dashboard_operators import STALE_RECORD
from dashboard_words import clock
from operations.labels import label, served_request
from ticketing.vocabulary import Kind

if TYPE_CHECKING:
    from dashboard_html import View


def health(v: View) -> str:
    from dashboard_html import ago, esc, session_name, tap

    out: list[str] = []
    for n, since in v.records.unwaited().items():
        if n not in v.all_:
            continue
        t = v.all_[n]
        request = served_request(t, v.all_) if t.kind is Kind.CHANGE else None
        if v.mine(t) or request is not None and v.mine(request):
            age = v.now - since
            minutes = ago(age) if 60 <= age < 3600 else f"{int(age // 60)} min"
            out.append(tap(n, f"⚠ {esc(label(t, v.all_))} · {minutes}", "alert"))
    out += [f'<div class="alert">⚠ {"Main" if r.index is None else session_name(r.index)} · No operator · {clock(r.shown.at, v.now)}</div>'
            for r in v.records.records if v.now - r.shown.at > STALE_RECORD]
    if v.records.main_missing is not None:
        out.append('<div class="alert">⚠ No main session</div>')
    return "".join(out) or '<div class="ok">✓ OK</div>'

