"""Indexed independent zstd JSONL frames; legacy plain/gzip line reads.

Line locators are one-based. A writer commits whole frames (about 1 MiB or
2048 lines), data fsync before index fsync. Resume recovers complete orphan
frames and truncates only an incomplete final frame/index line. Single writer;
readers see complete frames only. No program evaluation or existing conversion.
"""
from bisect import bisect_right
import fcntl
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile

SCHEMA = 'study-jsonl-zstd-v1'
MAGIC = b'\x28\xb5\x2f\xfd'


def _zstd():
    import zstandard
    return zstandard


def index_path(path):
    return Path(str(path) + '.idx.jsonl')


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      separators=(',', ':')).encode('utf-8') + b'\n'


def _sync(stream):
    stream.flush(); os.fsync(stream.fileno())


def _directory_sync(path):
    fd = os.open(path, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def _index(path):
    """Load small metadata only; ignore a torn, unterminated last index row."""
    frames = []; good_end = 0
    with index_path(path).open('rb') as stream:
        line = stream.readline()
        if not line.endswith(b'\n') or json.loads(line).get('schema') != SCHEMA:
            raise ValueError('missing or invalid framed JSONL index header')
        good_end = stream.tell(); first = 1; offset = 0
        for line in stream:
            if not line.endswith(b'\n'): break
            row = json.loads(line)
            if (row['first_line'] != first or row['offset'] != offset
                    or any(type(row[key]) is not int or row[key] <= 0
                           for key in ('line_count', 'compressed_bytes', 'uncompressed_bytes'))
                    or not isinstance(row['sha256'], str) or len(row['sha256']) != 64):
                raise ValueError('noncontiguous or invalid frame index')
            frames.append(row)
            first += row['line_count']; offset += row['compressed_bytes']
            good_end = stream.tell()
    if offset > Path(path).stat().st_size:
        raise ValueError('index points beyond durable data')
    return frames, good_end


def _frame_info(data, offset, compressed_bytes, first_line):
    if not data or not data.endswith(b'\n'):
        raise ValueError('frame is not complete newline-terminated JSONL')
    return dict(first_line=first_line, offset=offset, compressed_bytes=compressed_bytes,
                uncompressed_bytes=len(data), line_count=data.count(b'\n'),
                sha256=hashlib.sha256(data).hexdigest())


def _decode(stream, row):
    stream.seek(row['offset']); compressed = stream.read(row['compressed_bytes'])
    if len(compressed) != row['compressed_bytes']: raise ValueError('truncated indexed frame')
    data = _zstd().ZstdDecompressor().decompress(compressed, allow_extra_data=False)
    if _frame_info(data, row['offset'], len(compressed), row['first_line']) != row:
        raise ValueError('frame checksum, byte size or line count differs from index')
    return data


def _tail(stream, offset, first_line):
    """Recover only the unindexed tail; never rescan committed data."""
    stream.seek(offset)
    while True:
        start = offset; decoder = _zstd().ZstdDecompressor().decompressobj()
        chunks = []; consumed = 0; saw_input = False
        while not decoder.eof:
            block = stream.read(65536)
            if not block: return
            if not saw_input and len(block) < len(MAGIC) and MAGIC.startswith(block): return
            saw_input = True
            chunks.append(decoder.decompress(block)); consumed += len(block)
        consumed -= len(decoder.unused_data)
        data = b''.join(chunks)
        row = _frame_info(data, start, consumed, first_line)
        yield row
        offset += consumed; first_line += row['line_count']; stream.seek(offset)


def _snapshot(stream, path):
    frames, good_index_end = _index(path)
    offset = frames[-1]['offset'] + frames[-1]['compressed_bytes'] if frames else 0
    first = frames[-1]['first_line'] + frames[-1]['line_count'] if frames else 1
    recovered = list(_tail(stream, offset, first))
    return frames, recovered, good_index_end


class JsonlWriter:
    """Single-writer append. Resume uses committed_lines, not input rescanning.

    close()/flush() commits pending lines. An exceptional context exit discards
    pending RAM lines; previously committed and complete orphan frames survive.
    A single oversized line remains intact in its own (larger) frame.
    """
    def __init__(self, path, *, frame_bytes=1024 * 1024, frame_lines=2048, level=3):
        self.path = Path(path)
        if self.path.suffix != '.zst': raise ValueError('writer requires a .jsonl.zst path')
        if frame_bytes < 1 or frame_lines < 1: raise ValueError('frame limits must be positive')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self.path.open('a+b'); self._index = None; self._closed = False
        try:
            fcntl.flock(self._data.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            idx = index_path(self.path)
            if not idx.exists():
                if self.path.stat().st_size: raise ValueError('nonempty zstd file lacks its index')
                fd, temporary = tempfile.mkstemp(prefix='.' + idx.name, dir=idx.parent)
                try:
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(_json(dict(schema=SCHEMA, line_base=1,
                            frame_bytes=frame_bytes, frame_lines=frame_lines)))
                        _sync(stream)
                    os.replace(temporary, idx)
                    _directory_sync(self.path.parent)
                finally:
                    if os.path.exists(temporary): os.unlink(temporary)
            frames, recovered, good_end = _snapshot(self._data, self.path)
            if frames: _decode(self._data, frames[-1])
            self._index = idx.open('r+b'); self._index.truncate(good_end); self._index.seek(good_end)
            # Data precedes index publication, including recovered orphan frames.
            end = ((recovered or frames)[-1]['offset'] + (recovered or frames)[-1]['compressed_bytes']
                   if recovered or frames else 0)
            self._data.truncate(end); self._data.seek(end); _sync(self._data)
            for row in recovered: self._index.write(_json(row))
            _sync(self._index)
            self.committed_lines = sum(row['line_count'] for row in frames + recovered)
            self.recovered_frames = len(recovered)
            self.frame_bytes = frame_bytes; self.frame_lines = frame_lines
            self._compressor = _zstd().ZstdCompressor(level=level, write_checksum=True)
            self._pending = []; self._size = 0
        except BaseException:
            if self._index is not None: self._index.close()
            self._data.close(); raise

    @property
    def next_line(self):
        return self.committed_lines + len(self._pending) + 1

    def write_line(self, line):
        if self._closed: raise ValueError('writer is closed')
        raw = line.encode('utf-8') if isinstance(line, str) else bytes(line)
        if not raw.endswith(b'\n') or raw.count(b'\n') != 1:
            raise ValueError('write_line requires exactly one newline-terminated UTF-8 line')
        raw.decode('utf-8')
        if self._pending and (self._size + len(raw) > self.frame_bytes
                              or len(self._pending) >= self.frame_lines): self.flush()
        self._pending.append(raw); self._size += len(raw)
        if self._size >= self.frame_bytes or len(self._pending) >= self.frame_lines: self.flush()

    def write(self, value):
        self.write_line(_json(value))

    def flush(self):
        if self._closed: raise ValueError('writer is closed')
        if not self._pending: return
        data = b''.join(self._pending); frame = self._compressor.compress(data)
        offset = self._data.tell()
        row = _frame_info(data, offset, len(frame), self.committed_lines + 1)
        self._data.write(frame); _sync(self._data)
        self._index.write(_json(row)); _sync(self._index)
        self.committed_lines += len(self._pending); self._pending.clear(); self._size = 0

    def close(self):
        if self._closed: return
        try: self.flush()
        finally:
            self._closed = True; self._index.close(); self._data.close()

    def __enter__(self): return self

    def __exit__(self, kind, value, traceback):
        if kind is None: self.close()
        else:
            self._closed = True; self._index.close(); self._data.close()


class JsonlReader:
    """Reusable metadata index and at most one cached decompressed zstd frame."""
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.exists() and self.path.suffix not in ('.gz', '.zst'):
            candidates = [Path(str(self.path) + suffix) for suffix in ('.gz', '.zst')]
            candidates = [p for p in candidates if p.exists()]
            if len(candidates) > 1: raise ValueError('ambiguous compressed JSONL siblings')
            if candidates: self.path = candidates[0]
        self._data = None; self._cached = None
        if self.path.suffix == '.zst':
            self._data = self.path.open('rb')
            try:
                frames, recovered, _ = _snapshot(self._data, self.path)
                self.frames = frames + recovered
                self._first = [row['first_line'] for row in self.frames]
            except BaseException: self._data.close(); raise

    def iter_lines(self, *, start_line=1, stop_line=None):
        if type(start_line) is not int or start_line < 1: raise ValueError('line numbers start at one')
        if stop_line is not None and (type(stop_line) is not int or stop_line < start_line):
            raise ValueError('stop_line must be at least start_line')
        if self._data is None:
            opener = gzip.open if self.path.suffix == '.gz' else open
            with opener(self.path, 'rb') as stream:
                for number, line in enumerate(stream, 1):
                    if stop_line is not None and number >= stop_line: break
                    if number >= start_line: yield line
            return
        position = max(0, bisect_right(self._first, start_line) - 1)
        for frame_number in range(position, len(self.frames)):
            row = self.frames[frame_number]
            if stop_line is not None and row['first_line'] >= stop_line: break
            if self._cached is None or self._cached[0] != row['offset']:
                self._cached = row['offset'], _decode(self._data, row)
            for number, line in enumerate(io.BytesIO(self._cached[1]), row['first_line']):
                if stop_line is not None and number >= stop_line: return
                if number >= start_line: yield line

    def read_line(self, number):
        try: return next(self.iter_lines(start_line=number, stop_line=number + 1))
        except StopIteration: raise IndexError(number) from None

    def close(self):
        if self._data is not None: self._data.close()
        self._cached = None

    def __enter__(self): return self
    def __exit__(self, *unused): self.close()


def iter_lines(path, *, start_line=1, stop_line=None):
    with JsonlReader(path) as reader:
        yield from reader.iter_lines(start_line=start_line, stop_line=stop_line)


def read_line(path, number):
    with JsonlReader(path) as reader: return reader.read_line(number)


def iter_json(path, *, start_line=1, stop_line=None):
    for line in iter_lines(path, start_line=start_line, stop_line=stop_line): yield json.loads(line)
