"""The ticket dashboard's usage rows, with a used share and elapsed tick,
and adapters for Claude windows and weekly Codex observations."""

from html import escape as esc

from dashboard_reads import DAY, CodexWindow
from operations.pacing import Usage, WindowName
from usage_window import elapsed_pct


def usage_row(label: str, shares: tuple[float, float] | None) -> str:
    """A usage row; absent shares give an unavailable reading."""
    if shares is None:
        return (f'<div class="ub"><span class="ul">{esc(label)}</span><div class="bar"></div>'
                '<span class="uv">–</span></div>')
    used, elapsed = shares
    hot = used > elapsed
    return (f'<div class="ub"><span class="ul">{esc(label)}</span>'
            f'<div class="bar"><i{' class="hot"' if hot else ""} style="width:{min(100, used):.0f}%"></i>'
            f'<b style="left:{min(100, elapsed):.0f}%"></b></div>'
            f'<span class="uv{" w" if hot else ""}">{used:.0f}%</span></div>')



def usage_bar(usage: Usage, name: WindowName, label: str) -> str:
    win = usage.windows.get(name)
    return usage_row(label, None if win is None else (win.used_pct, win.elapsed_pct))


def codex_bar(window: CodexWindow | None, now: float) -> str:
    if window is None or window.resets_at <= now:
        return usage_row("Codex", None)
    elapsed = elapsed_pct(window.resets_at, 7 * DAY, now)
    return usage_row("Codex", (window.used_pct, elapsed))
