"""Generate the three session-stop hook sounds.

Run: `uv run python .claude/hooks/sounds/gen_sounds.py`
Audit: `afplay .claude/hooks/sounds/<name>.wav`

Three semantic states from session-stop.py:
  continue.wav  — re-prompt fires, edits still pending under FIRE_CAP
                  (most frequent: up to FIRE_CAP-1 times/turn — keep quiet/short)
  resolved.wav  — fire_count > 0 and no pending edits (terminal success)
  gave_up.wav   — edits pending and fire_count >= FIRE_CAP (terminal cap-hit)
"""

import math
import struct
import wave
from pathlib import Path

SR = 44100
OUT = Path(__file__).parent


def tone(
    freq,
    duration_ms,
    amplitude=0.3,
    mod_ratio=1.4,
    mod_index=3.0,
    decay_ms=None,
):
    """2-op FM with exponential decay — gives a bell/chime timbre.

    mod_ratio non-integer → inharmonic partials (bell-like).
    mod_index controls brightness; it decays with the envelope so the attack
    is brighter than the tail (the classic struck-bell feel).
    """
    n = int(SR * duration_ms / 1000)
    tau = (decay_ms if decay_ms is not None else duration_ms * 1.2) / 1000
    tail_n = int(SR * 0.004)  # 4ms linear taper to zero (kills boundary click)
    out = []
    for i in range(n):
        t = i / SR
        env = math.exp(-t / tau)
        attack = min(1.0, t / 0.002)
        tail = min(1.0, (n - 1 - i) / tail_n) if tail_n else 1.0
        mod = math.sin(2 * math.pi * freq * mod_ratio * t) * mod_index * env
        s = math.sin(2 * math.pi * freq * t + mod) * env * attack * tail * amplitude
        out.append(s)
    return out


def concat(*chunks):
    out = []
    for c in chunks:
        out.extend(c)
    return out


def silence(duration_ms):
    return [0.0] * int(SR * duration_ms / 1000)


def write_wav(path, samples):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        data = b"".join(
            struct.pack("<h", max(-32767, min(32767, int(s * 32767))))
            for s in samples
        )
        w.writeframes(data)


# continue: staccato of two identical short blips
write_wav(
    OUT / "continue.wav",
    concat(
        tone(1000, 70, amplitude=0.08, mod_ratio=2.0, mod_index=1.3, decay_ms=30),
        tone(1000, 70, amplitude=0.08, mod_ratio=2.0, mod_index=1.3, decay_ms=30),
    ),
)

# resolved: rising bell-ding (C5 -> G5)
write_wav(
    OUT / "resolved.wav",
    concat(
        tone(523.25, 100, amplitude=0.08, mod_ratio=2.0, mod_index=1.5, decay_ms=60),
        tone(783.99, 100, amplitude=0.08, mod_ratio=2.0, mod_index=1.5, decay_ms=60),
    ),
)

# gave_up: descending mellow chime (E4 -> A3)
write_wav(
    OUT / "gave_up.wav",
    concat(
        tone(329.63, 140, amplitude=0.08, mod_ratio=2.0, mod_index=1.5, decay_ms=100),
        tone(220.00, 200, amplitude=0.08, mod_ratio=2.0, mod_index=1.5, decay_ms=100),
    ),
)

print(f"wrote: {OUT}/continue.wav resolved.wav gave_up.wav")
