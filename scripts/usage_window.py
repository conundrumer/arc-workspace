"""Elapsed shares of fixed-length usage windows."""


def elapsed_pct(resets_at: float, seconds: float, now: float) -> float:
    """The elapsed percentage of the positive-length window ending at
    `resets_at`, bounded to 0–100, at `now`. Times and length are seconds."""
    return min(100.0, max(0.0, 100 * (now - (resets_at - seconds)) / seconds))
