"""The files that changed under a set of watched paths since the last
take, as the file event stream of macOS (FSEvents) gives them. An event
can come seconds after its write, or not at all, so a reader that must see
each change reads each path itself as well."""

import ctypes
import os
import sys
import threading
from collections.abc import Iterable
from pathlib import Path

LATENCY_SECONDS = 0.5
"""How long the stream holds an event to send it with the ones after it."""

SINCE_NOW = 0xFFFFFFFFFFFFFFFF
"""`kFSEventStreamEventIdSinceNow`."""

FILE_EVENTS = 0x10
"""`kFSEventStreamCreateFlagFileEvents`: an event gives the path of each
file, not only its directory."""

NO_DEFER = 0x02
"""`kFSEventStreamCreateFlagNoDefer`: the first event after a quiet time is
sent at once."""

ENTRY_FLAGS = 0x100 | 0x200 | 0x800
"""`kFSEventStreamEventFlagItemCreated`, `ItemRemoved` and `ItemRenamed`:
an event that changes the entries of the file's directory."""

UTF8 = 0x08000100
"""`kCFStringEncodingUTF8`."""

CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t,
                            ctypes.POINTER(ctypes.c_char_p), ctypes.POINTER(ctypes.c_uint32),
                            ctypes.POINTER(ctypes.c_uint64))


class Unwatched(OSError):
    """The stream cannot start on this system."""


def frameworks() -> tuple[ctypes.CDLL, ctypes.CDLL, ctypes.CDLL]:
    """CoreServices, CoreFoundation and libSystem, with the signatures of the
    calls `Changes` makes; `Unwatched` where they do not load."""
    if sys.platform != "darwin":
        raise Unwatched("file events are read on macOS only")
    try:
        cs = ctypes.CDLL("/System/Library/Frameworks/CoreServices.framework/CoreServices")
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
    except OSError as e:
        raise Unwatched(str(e)) from e
    vp = ctypes.c_void_p
    cf.CFStringCreateWithCString.restype = vp
    cf.CFStringCreateWithCString.argtypes = [vp, ctypes.c_char_p, ctypes.c_uint32]
    cf.CFArrayCreate.restype = vp
    cf.CFArrayCreate.argtypes = [vp, ctypes.POINTER(vp), ctypes.c_long, vp]
    cf.CFRelease.argtypes = [vp]
    cs.FSEventStreamCreate.restype = vp
    cs.FSEventStreamCreate.argtypes = [vp, CALLBACK, vp, vp, ctypes.c_uint64, ctypes.c_double,
                                       ctypes.c_uint32]
    cs.FSEventStreamSetDispatchQueue.argtypes = [vp, vp]
    cs.FSEventStreamStart.argtypes = [vp]
    cs.FSEventStreamStart.restype = ctypes.c_bool
    for name in ("FSEventStreamStop", "FSEventStreamInvalidate", "FSEventStreamRelease"):
        getattr(cs, name).argtypes = [vp]
    libc.dispatch_queue_create.restype = vp
    libc.dispatch_queue_create.argtypes = [ctypes.c_char_p, vp]
    return cs, cf, libc


def roots(dirs: Iterable[str]) -> list[str]:
    """The least set of `dirs` under which each of `dirs` lies."""
    out: list[str] = []
    for d in sorted(set(dirs)):
        if not under(d, out):
            out.append(d)
    return out


class Changes:
    """The watched paths that changed since the last `take`, each as the
    path it is watched by, from one stream over the directories they lie
    in. A watched path changes where an event names it, or where it is a
    directory and an event adds, removes or renames an entry of it. Events
    of other paths are dropped."""

    def __init__(self, paths: Iterable[Path]) -> None:
        self._cs, self._cf, self._libc = frameworks()
        self._real: dict[str, str] = {}
        self._watched: dict[str, str] = {}
        self._changed: set[str] = set()
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._callback = CALLBACK(self._given)
        self._stream: int | None = None
        self._roots: list[str] = []
        self.watch(paths)

    def watch(self, paths: Iterable[Path]) -> None:
        """Watch `paths` in place of the paths watched before, and start the
        stream again where they lie outside its directories."""
        watched: dict[str, str] = {}
        for p in paths:
            text = str(p)
            parent, name = os.path.split(text)
            real = self._real.get(parent)
            if real is None:
                real = self._real[parent] = os.path.realpath(parent)
            watched[os.path.join(real, name)] = text
        with self._lock:
            self._watched = watched
        wanted = roots(os.path.dirname(p) for p in watched)
        if self._stream is None or any(not under(d, self._roots) for d in wanted):
            self.close()
            self._start(wanted)

    def _start(self, dirs: list[str]) -> None:
        cs, cf, libc = self._cs, self._cf, self._libc
        strings = [cf.CFStringCreateWithCString(None, d.encode(), UTF8) for d in dirs]
        array = cf.CFArrayCreate(None, (ctypes.c_void_p * len(strings))(*strings), len(strings),
                                 ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeArrayCallBacks")))
        stream = cs.FSEventStreamCreate(None, self._callback, None, array, SINCE_NOW,
                                        LATENCY_SECONDS, FILE_EVENTS | NO_DEFER)
        cf.CFRelease(array)
        for s in strings:
            cf.CFRelease(s)
        if not stream:
            raise Unwatched(f"no stream over {len(dirs)} directories")
        cs.FSEventStreamSetDispatchQueue(stream, libc.dispatch_queue_create(b"file_events", None))
        if not cs.FSEventStreamStart(stream):
            cs.FSEventStreamInvalidate(stream)
            cs.FSEventStreamRelease(stream)
            raise Unwatched(f"the stream over {len(dirs)} directories did not start")
        self._stream, self._roots = stream, dirs

    def _given(self, _stream: int, _info: int, count: int,
               paths: "ctypes._Pointer[ctypes.c_char_p]",
               flags: "ctypes._Pointer[ctypes.c_uint32]", _ids: object) -> None:
        found: set[str] = set()
        with self._lock:
            for i in range(count):
                raw = paths[i]
                if raw is None:
                    continue
                path = os.fsdecode(raw)
                named = (path, os.path.dirname(path)) if flags[i] & ENTRY_FLAGS else (path,)
                found.update(w for p in named if (w := self._watched.get(p)) is not None)
            self._changed |= found
        if found:
            self._event.set()

    def wait(self, seconds: float) -> bool:
        """Wait up to `seconds` for a change, and give whether one is taken
        up yet."""
        return self._event.wait(max(seconds, 0.0))

    def take(self) -> set[str]:
        """The watched paths changed since the last take."""
        with self._lock:
            out, self._changed = self._changed, set()
            self._event.clear()
        return out

    def close(self) -> None:
        """Stop the stream."""
        if self._stream is not None:
            for call in (self._cs.FSEventStreamStop, self._cs.FSEventStreamInvalidate,
                         self._cs.FSEventStreamRelease):
                call(self._stream)
            self._stream = None


def under(path: str, dirs: list[str]) -> bool:
    """Whether `path` lies under one of `dirs`, or is one."""
    return any(path == d or path.startswith(d.rstrip(os.sep) + os.sep) for d in dirs)
