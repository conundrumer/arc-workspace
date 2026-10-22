"""The Health section of the ticket dashboard: rows the user can act on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dashboard_reads import STALE_RECORD, hits_full, served_request
from dashboard_words import clock
from operations.pacing import Until, WindowName
from ticketing.vocabulary import Kind

if TYPE_CHECKING:
    from dashboard_html import View


def health(v: View, waits: int) -> str:
    from dashboard_html import ago, esc, per_session, tap

    out: list[str] = []
    if waits:
        out.append(f'<a class="alert" href="#blocked">! Blocked · {waits}</a>')
    for n, since in v.records.unwaited().items():
        if n not in v.all_:
            continue
        t = v.all_[n]
        request = served_request(t, v.all_) if t.kind is Kind.CHANGE else None
        if v.mine(t) or request is not None and v.mine(request):
            age = v.now - since
            minutes = ago(age) if 60 <= age < 3600 else f"{int(age // 60)} min"
            out.append(tap(n, f"⚠ {esc(v.phrase(t))} · {minutes}", "alert"))
    out += [f'<div class="alert">⚠ No operator · {clock(at, v.now)}</div>'
            for _, at in per_session(v, lambda s: s.at if v.now - s.at > STALE_RECORD else None)
            if at is not None]
    if v.records.main_missing is not None:
        out.append('<div class="alert">⚠ No operator</div>')
    for _, h in per_session(v, lambda s: s.start_hold):
        if h is not None:
            value = f" · {clock(h.time, v.now)}" if isinstance(h, Until) else ""
            out.append(f'<div class="alert">⏸ Starts held{value}</div>')
    for window, label in ((WindowName.SEVEN_DAY, "Week full"), (WindowName.FIVE_HOUR, "5 h full")):
        full = hits_full(v.usage, window)
        if full is not None:
            out.append(f'<div class="alert">⚠ {label} · {clock(full, v.now)}</div>')
    return "".join(out) or '<div class="ok">✓ OK</div>'

