"""The one `engine.Engine`: Souffle programs parsed into units,
declarations and comments, rewritten as programs, rendered with the line
each rendered line comes from, and run under the Souffle binary, linked
with the functor library (`functors`), with a content-hash cache. A run's
key names each path from the checkout's root where it stands under it, so
that every checkout of the repository reads the runs the others stored."""

from souffle.engine import SouffleEngine

__all__ = ["SouffleEngine"]
