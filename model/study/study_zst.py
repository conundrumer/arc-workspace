"""One opener for large data files that are zstd streams, plain files, or both over time. Every reader and writer of a large study file goes through here, so a file can change between plain and zstd with no reader changing.

A path names a file by its logical name, `X.jsonl`. On disk the file is `X.jsonl.zst` or `X.jsonl`; a path that ends in `.zst` names the same file. Where both exist, the one modified last is the file (a tie takes the `.zst`). Sidecars of a file (`X.jsonl.sha256`, `X.jsonl.code.json`) keep the logical name, and a `.sha256` holds the hash of the text, not of the bytes on disk.

Reading (`zstandard` 0.23 is the only dependency, and only where a `.zst` is read or written):
  exists(path) -> bool
  resolve(path) -> Path | None             the file on disk
  open_text(path)                          lines as text, as `open(path)`; a `.zst` file is read across its frames, and a last frame that a writer has not finished is not read
  open_bytes(path)                         the same in bytes, as `open(path, 'rb')`
  read_text(path) -> str
  sha256(path) -> hex                      of the text
  glob(pattern) -> [logical name]          the files that `pattern` or `pattern + '.zst'` matches, sorted
  listdir(folder) -> [logical name]
  LineStore(path)                          random access to lines (see the class)
Writing:
  open_text(path, 'w')                     writes `X.jsonl.zst`, a new file, as the stream of frames of whole writes; `.write(str)`, `.flush()`, `.close()`
  open_text(path, 'a')                     appends frames to `X.jsonl.zst`; a torn last frame is cut off first, and a file that is plain on disk is first made `X.jsonl.zst`, the plain file left as it is
  open_text(path, 'w', atomic=True)        writes `X.jsonl.zst.part` and renames it onto `X.jsonl.zst` at a clean close
  open_part(path, suffix=''), commit(path, suffix='')   `X.jsonl.zst.part<suffix>` with no rename at close, and the rename, for outputs that must appear together
  trim_to_last_newline(path)               cuts the file after its last complete line
  rewrite(path)                            a context manager: replaces a file by the text written to it, in the form that the file has
  write_sidecar_sha256(path)               `X.jsonl.sha256`: `<sha256 of the text>  <name>`
  `line_buffering=True` makes every write that holds a newline a frame, as `buffering=1` does for a plain file.

A reader can read a `.zst` while its writer writes it: the file is a sequence of independent frames, each of whole writes, and a frame is flushed when `flush()` is called, when `line_buffering` sees a line, and when 1 MiB is pending. A reader sees only complete frames.

  python3 study_zst.py compress [--aside FOLDER] [--min-bytes N] FILE...   makes FILE.zst from each plain FILE of N bytes or more (default 1 MiB), checks that its text has the plain file's sha256, gives it the plain file's modification time, and moves the plain file into FOLDER (default: next to it, in plain-aside/), keeping its path under FOLDER's root as given by --root; a file that changes while it is read is left alone
  python3 study_zst.py check FILE...                                       reads each file and prints its lines and sha256 of its text
  python3 study_zst.py concat OUT SHARD...                                 writes OUT.zst from the text of the shards, in the order given, each plain or `.zst`, through OUT.zst.part
"""
import contextlib
import glob as _glob
import hashlib
import io
import os
import sys
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

SUFFIX = '.zst'
FRAME_BYTES = 1 << 20  # pending bytes that make a frame, at the last newline
LEVEL = 3
CHUNK_BYTES = 1 << 20  # LineStore chunk, before compression


def _zstd():
    try:
        import zstandard
    except ImportError as e:
        raise ImportError('study_zst needs `zstandard` (uv run python, or the study runtime): %s runs without it' % sys.executable) from e
    return zstandard


def logical(path) -> str:
    """The logical name of a path: without a `.zst` suffix."""
    p = os.fspath(path)
    return p[:-len(SUFFIX)] if p.endswith(SUFFIX) else p


def resolve(path) -> Path | None:
    """The file on disk that the path names, or None. Of `X` and `X.zst` the one modified last; a tie takes the `.zst`."""
    base = logical(path)
    found = []
    for p in (base + SUFFIX, base):
        try:
            found.append((os.stat(p).st_mtime_ns, p.endswith(SUFFIX), p))
        except FileNotFoundError:
            pass
    return Path(max(found)[2]) if found else None


def exists(path) -> bool:
    return resolve(path) is not None


def _need(path) -> Path:
    p = resolve(path)
    if p is None:
        raise FileNotFoundError('no file %s, and no %s' % (logical(path), logical(path) + SUFFIX))
    return p


def _open_zst(p: Path):
    f = open(p, 'rb')
    try:
        return io.BufferedReader(_zstd().ZstdDecompressor().stream_reader(f, read_across_frames=True, closefd=True), buffer_size=1 << 20)  # type: ignore[arg-type]
    except BaseException:
        f.close()
        raise


def open_bytes(path):
    """The file's bytes as a buffered binary reader."""
    p = _need(path)
    return _open_zst(p) if p.suffix == SUFFIX else open(p, 'rb')


def open_text(path, mode: str = 'r', *, line_buffering: bool = False, atomic: bool = False, level: int = LEVEL, encoding: str = 'utf-8') -> Any:
    """The file's text. Mode r reads, w writes a new `.zst`, a appends to the `.zst`; see the module docstring."""
    if mode == 'r':
        p = _need(path)
        return io.TextIOWrapper(_open_zst(p), encoding=encoding) if p.suffix == SUFFIX else open(p, encoding=encoding)
    if mode not in ('w', 'a'):
        raise ValueError('mode must be r, w or a: %r' % mode)
    if atomic and mode == 'a':
        raise ValueError('atomic writes a new file')
    target = logical(path) + SUFFIX
    if mode == 'a':
        _prepare_append(target, level)
        return _Writer(target, target, 'ab', level, line_buffering, encoding, commit_on_close=False)
    if atomic:
        return _Writer(target, target + '.part', 'wb', level, line_buffering, encoding, commit_on_close=True)
    return _Writer(target, target, 'wb', level, line_buffering, encoding, commit_on_close=False)


def open_part(path, *, suffix: str = '', line_buffering: bool = False, level: int = LEVEL, encoding: str = 'utf-8'):
    """Writes `X.zst.part<suffix>`; `commit(path, suffix)` renames it onto `X.zst`. A suffix such as the process id keeps two writers of one file apart."""
    target = logical(path) + SUFFIX
    return _Writer(target, target + '.part' + suffix, 'wb', level, line_buffering, encoding, commit_on_close=False)


def commit(path, suffix: str = '') -> None:
    """Renames `X.zst.part<suffix>` onto `X.zst`."""
    target = logical(path) + SUFFIX
    os.replace(target + '.part' + suffix, target)


@contextlib.contextmanager
def rewrite(path):
    """Replaces an existing file by the text written to the yielded writer, in the form the file has now (`.zst` or plain), by a rename at a clean exit."""
    p = _need(path)
    if p.suffix == SUFFIX:
        with open_text(p, 'w', atomic=True) as f:
            yield f
        return
    part = str(p) + '.part'
    try:
        with open(part, 'w') as f:
            yield f
        os.replace(part, p)
    finally:
        if os.path.exists(part):
            os.unlink(part)


def read_text(path) -> str:
    with open_text(path) as f:
        return f.read()


def _sha256_of(f) -> str:
    h = hashlib.sha256()
    while chunk := f.read(1 << 20):
        h.update(chunk)
    return h.hexdigest()


def sha256(path) -> str:
    """The sha256 of the file's text."""
    with open_bytes(path) as f:
        return _sha256_of(f)


def write_sidecar_sha256(path) -> str:
    """Writes `X.sha256` as `<sha256 of the text>  <name of X>`; returns the hash."""
    digest = sha256(path)
    with open(logical(path) + '.sha256', 'w') as f:
        f.write('%s  %s\n' % (digest, os.path.basename(logical(path))))
    return digest


def glob(pattern) -> list[str]:
    """The logical names of the files that `pattern` or `pattern + '.zst'` matches, sorted."""
    pattern = logical(pattern)
    return sorted({logical(p) for p in _glob.glob(pattern) + _glob.glob(pattern + SUFFIX)})


def listdir(folder) -> list[str]:
    """The names in the folder, a `.zst` name by its logical name, once."""
    return sorted({logical(n) for n in os.listdir(folder)})


class _Writer:
    """A text writer of independent zstd frames, one for each flush."""

    def __init__(self, final: str, path: str, mode: str, level: int, line_buffering: bool, encoding: str, commit_on_close: bool):
        self.name = path
        self._final, self._commit, self._line, self._encoding = final, commit_on_close, line_buffering, encoding
        self._comp = _zstd().ZstdCompressor(level=level)
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._f = open(path, mode)
        self._pending: list[bytes] = []
        self._size = 0
        self.closed = False

    def write(self, s: str | bytes) -> int:
        b = s if isinstance(s, bytes) else s.encode(self._encoding)
        self._pending.append(b)
        self._size += len(b)
        if self._line and b'\n' in b:
            self.flush()
        elif self._size >= FRAME_BYTES and b'\n' in b:
            self._frame(cut=True)
        return len(s)

    def writelines(self, lines) -> None:
        for l in lines:
            self.write(l)

    def _frame(self, cut: bool) -> None:
        data = b''.join(self._pending)
        keep = b''
        if cut:  # a frame ends at a newline where it can, so a live reader sees whole lines
            at = data.rfind(b'\n') + 1
            data, keep = data[:at], data[at:]
        if data:
            self._f.write(self._comp.compress(data))
            self._f.flush()
        self._pending = [keep] if keep else []
        self._size = len(keep)

    def flush(self) -> None:
        if not self.closed:
            self._frame(cut=False)

    def close(self) -> None:
        if self.closed:
            return
        self.flush()
        if self._f.tell() == 0:  # a file with no text is one empty frame, which `zstd -t` takes
            self._f.write(self._comp.compress(b''))
        self._f.close()
        self.closed = True
        if self._commit:
            os.replace(self.name, self._final)

    def abort(self) -> None:
        """Closes and removes a file that was to be renamed at close."""
        if not self.closed:
            self._pending, self._size = [], 0
            self._f.close()
            self.closed = True
            if self._commit and os.path.exists(self.name):
                os.unlink(self.name)

    def fileno(self) -> int:
        return self._f.fileno()

    def writable(self) -> bool:
        return True

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb) -> None:
        if et is not None and self._commit:
            self.abort()
        else:
            self.close()


def _frames_end(path: str) -> int:
    """The byte offset where the last complete frame of the file ends: 0 for an empty file, the size for a file that ends with a frame. A frame that is not complete does not count."""
    zstd = _zstd()
    end = 0
    with open(path, 'rb') as f:
        while True:
            dec = zstd.ZstdDecompressor().decompressobj()
            used = 0
            f.seek(end)
            while not dec.eof:
                block = f.read(1 << 20)
                if not block:
                    return end
                dec.decompress(block)
                used += len(block)
            end += used - len(dec.unused_data)


def _prepare_append(target: str, level: int) -> None:
    """Makes `target` a file that frames can be appended to: its torn last frame is cut off; a plain file of the same name, with no `.zst` yet or a newer plain one, becomes the `.zst`."""
    plain = target[:-len(SUFFIX)]
    if os.path.exists(plain) and (not os.path.exists(target) or os.stat(plain).st_mtime_ns > os.stat(target).st_mtime_ns):
        if os.path.exists(target):
            raise FileExistsError('%s is newer than %s; neither can be appended to without losing lines' % (plain, target))
        _compress_file(plain, target, level)
    if os.path.exists(target):
        end = _frames_end(target)
        if end < os.path.getsize(target):
            os.truncate(target, end)


def trim_to_last_newline(path) -> None:
    """Cuts the file after its last newline: the half line that a killed writer left goes. A file with no newline becomes empty."""
    p = resolve(path)
    if p is None:
        return
    good, torn = 0, False
    with open_bytes(p) as f:
        for line in f:
            if not line.endswith(b'\n'):
                torn = True
                break
            good += len(line)
    if p.suffix != SUFFIX:
        if torn:
            os.truncate(p, good)
        return
    if not torn:
        end = _frames_end(str(p))
        if end < os.path.getsize(p):
            os.truncate(p, end)
        return
    part = str(p) + '.part'
    with open_bytes(p) as f, open(part, 'wb') as out:
        comp, left = _zstd().ZstdCompressor(level=LEVEL), good
        while left:
            data = f.read(min(left, FRAME_BYTES))
            out.write(comp.compress(data))
            left -= len(data)
    os.replace(part, p)


def _compress_file(src: str, dst: str, level: int = LEVEL) -> None:
    """Writes dst, a `.zst` of the text of src, through dst + '.part', with src's modification time. Raises where src changed while it was read."""
    before = os.stat(src)
    h = hashlib.sha256()
    part = dst + '.part'
    comp = _zstd().ZstdCompressor(level=level)
    with open(src, 'rb') as f, open(part, 'wb') as out:
        while chunk := f.read(FRAME_BYTES):
            h.update(chunk)
            out.write(comp.compress(chunk))
        if out.tell() == 0:  # an empty file is one empty frame, which `zstd -t` takes
            out.write(comp.compress(b''))
    after = os.stat(src)
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        os.unlink(part)
        raise RuntimeError('%s changed while it was read' % src)
    with _open_zst(Path(part)) as f:
        same = _sha256_of(f) == h.hexdigest()
    if not same:
        os.unlink(part)
        raise RuntimeError('%s: the text of its .zst differs' % src)
    os.utime(part, ns=(before.st_atime_ns, before.st_mtime_ns))
    os.replace(part, dst)


class LineStore:
    """Random access to the lines of a file, plain or `.zst`, in bytes. `for handle, line in store.scan()` reads the file once, in order; `store.get(handle)` gives the line again. A plain file stays open, so a handle stays valid when a writer replaces the file by a rename. A `.zst` file has no byte offsets of its text, so the scan keeps the lines in memory, as chunks of about 1 MiB compressed again, and `get` decompresses one chunk (the last one is cached)."""

    def __init__(self, path):
        self.path = _need(path)
        self.zst = self.path.suffix == SUFFIX
        self._chunks: list[bytes] = []
        self._cache: tuple[int, bytes] | None = None
        self._f = None if self.zst else open(self.path, 'rb')
        self._lock = threading.Lock()  # `get` may be called from several threads

    def scan(self) -> Iterator[tuple[tuple[int, int, int], bytes]]:
        if not self.zst:
            assert self._f is not None
            pos = 0
            self._f.seek(0)
            for line in self._f:
                yield (0, pos, len(line)), line
                pos += len(line)
            return
        zstd = _zstd()
        comp = zstd.ZstdCompressor(level=1)
        buf: list[bytes] = []
        size = 0
        with open_bytes(self.path) as f:
            for line in f:
                yield (len(self._chunks), size, len(line)), line
                buf.append(line)
                size += len(line)
                if size >= CHUNK_BYTES:
                    self._chunks.append(comp.compress(b''.join(buf)))
                    buf, size = [], 0
        if buf:
            self._chunks.append(comp.compress(b''.join(buf)))

    def get(self, handle: tuple[int, int, int]) -> bytes:
        chunk, pos, size = handle
        with self._lock:
            if not self.zst:
                assert self._f is not None
                self._f.seek(pos)
                return self._f.read(size)
            if self._cache is None or self._cache[0] != chunk:
                self._cache = (chunk, _zstd().ZstdDecompressor().decompress(self._chunks[chunk]))
            return self._cache[1][pos:pos + size]


def _main(argv: list[str]) -> int:
    if not argv or argv[0] not in ('compress', 'check', 'concat'):
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == 'concat':
        with open_text(args[0], 'w', atomic=True) as out:
            for p in args[1:]:
                with open_bytes(p) as f:
                    while chunk := f.read(1 << 20):
                        out.write(chunk)
        return 0
    if cmd == 'check':
        for p in args:
            n = 0
            with open_bytes(p) as f:
                for n, _ in enumerate(f, 1):
                    pass
            print('%s: %d lines, sha256 %s' % (resolve(p), n, sha256(p)))
        return 0
    aside, min_bytes, root, files = None, 1 << 20, None, []
    it = iter(args)
    for a in it:
        if a == '--aside':
            aside = next(it)
        elif a == '--min-bytes':
            min_bytes = int(next(it))
        elif a == '--root':
            root = next(it)
        else:
            files.append(a)
    bad = 0
    for p in files:
        if not os.path.isfile(p) or p.endswith(SUFFIX) or os.path.getsize(p) < min_bytes:
            continue
        dst = p + SUFFIX
        try:
            if os.path.exists(dst) and os.stat(dst).st_mtime_ns >= os.stat(p).st_mtime_ns:
                raise RuntimeError('%s exists and is not older than the plain file' % dst)
            _compress_file(p, dst)
        except RuntimeError as e:
            print('SKIPPED %s' % e, file=sys.stderr)
            bad += 1
            continue
        rel = os.path.relpath(p, root) if root else os.path.basename(p)
        away = os.path.join(aside or os.path.join(os.path.dirname(os.path.abspath(p)), 'plain-aside'), rel)
        os.makedirs(os.path.dirname(away), exist_ok=True)
        os.rename(p, away)
        print('%s -> %s (%d -> %d bytes), plain file moved to %s' % (p, dst, os.path.getsize(away), os.path.getsize(dst), away))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
