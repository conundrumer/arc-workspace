"""The one `engine.Engine`: Souffle programs parsed into units,
declarations and comments, rewritten as programs, rendered with the line
each rendered line comes from, and run under the Souffle binary with a
content-hash cache."""

from souffle.engine import SouffleEngine

__all__ = ["SouffleEngine"]
