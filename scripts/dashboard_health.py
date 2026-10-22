"""The Health section of the ticket dashboard: rows the user can act on."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dashboard_reads import STALE_RECORD, hits_full, served_request
from dashboard_words import clock
from operations.pacing import Capped, Until, WindowName
from operations.state import NotComputed
from shown_state import ScriptAdmits
from ticketing.vocabulary import Kind

if TYPE_CHECKING:
    from dashboard_html import View


def health(v: View) -> str:
    from dashboard_html import ago, esc, per_session, session_name, tap

    out: list[str] = []
    for n, since in v.records.unwaited().items():
        if n not in v.all_:
            continue
        t = v.all_[n]
        request = served_request(t, v.all_) if t.kind is Kind.CHANGE else None
        if v.mine(t) or request is not None and v.mine(request):
            age = v.now - since
            minutes = ago(age) if 60 <= age < 3600 else f"{int(age // 60)} min"
            out.append(tap(n, f"⚠ {esc(v.phrase(t))} · {minutes}", "alert"))
    out += [f'<div class="alert">⚠ {"Main" if r.index is None else session_name(r.index)} · No operator · {clock(r.shown.at, v.now)}</div>'
            for r in v.records.records if v.now - r.shown.at > STALE_RECORD]
    if v.records.main_missing is not None:
        out.append('<div class="alert">⚠ No main session</div>')
    for _, h in per_session(v, lambda s: s.start_hold):
        if h is not None:
            match h:
                case Until():
                    value = f" · {clock(h.time, v.now)}"
                case Capped(cap):
                    value = f" · cap {cap}"
                case ScriptAdmits():
                    value = " · pace script"
                case NotComputed():
                    value = " · pace unknown"
            out.append(f'<div class="alert">⏸ Starts held{value}</div>')
    for window, label in ((WindowName.SEVEN_DAY, "Week full"), (WindowName.FIVE_HOUR, "5 h full")):
        full = hits_full(v.usage, window)
        if full is not None:
            out.append(f'<div class="alert">⚠ {label} · {clock(full, v.now)}</div>')
    return "".join(out) or '<div class="ok">✓ OK</div>'

