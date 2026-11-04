"""Dev labeling layer: JSON-lines files kept compressed with zstd, so that they stream.

    python3 jsonl.py count FILE    prints the number of records of FILE, in either form.

A file named `x.jsonl` is stored as `x.jsonl.zst`, one JSON record per line. A writer flushes a zstd block after each record, so a reader sees
every record written so far, and ends a zstd frame every few seconds and at its close. A reader takes the plain `x.jsonl` where it exists, so
files written before the compression read as they are; a writer removes the plain file once the compressed one holds its records.
"""
import json
import os
import time
from pathlib import Path

import zstandard

FRAME_SECONDS = 5
LEVEL = 3
THREADS = 4  # compression threads of a whole-file write


def zst(path):
    path = Path(path)
    return path if path.suffix == '.zst' else path.with_name(path.name + '.zst')


def plain(path):
    path = Path(path)
    return path.with_name(path.name[:-4]) if path.suffix == '.zst' else path


def exists(path):
    return plain(path).exists() or zst(path).exists()


def _decoded(z, state):
    """The decoded bytes of a compressed file, frame by frame. state['clean'] ends False where the last frame is cut short or still open, or
    where the data is corrupt; the bytes of every complete block before that point are given."""
    dctx = zstandard.ZstdDecompressor()
    dobj, fed = dctx.decompressobj(), False
    state['clean'] = False
    with open(z, 'rb') as f:
        while True:
            data = f.read(1 << 20)
            if not data:
                break
            while data:
                fed = True
                try:
                    out = dobj.decompress(data)
                except zstandard.ZstdError:
                    return
                if out:
                    yield out
                if dobj.eof:
                    data = dobj.unused_data
                    dobj, fed = dctx.decompressobj(), False
                else:
                    data = b''
    state['clean'] = not fed


def lines(path):
    """The complete lines of the file, as text, from the plain file or the compressed one. A last line still being written is left out."""
    p = plain(path)
    if p.exists():
        with open(p) as f:
            for l in f:
                if l.endswith('\n'):
                    yield l
        return
    z = zst(path)
    if not z.exists():
        return
    rest = b''
    for chunk in _decoded(z, {}):
        rest += chunk
        *done, rest = rest.split(b'\n')
        for l in done:
            yield l.decode() + '\n'


def records(path):
    """The records of the file, each parsed."""
    for l in lines(path):
        if l.strip():
            yield json.loads(l)


def _clean_end(z):
    """Whether the compressed file decodes to its end and its last frame is complete."""
    state = {}
    for _ in _decoded(z, state):
        pass
    return state['clean']


def write_all(path, recs):
    """Write the file anew with these records, then remove its plain twin."""
    z = zst(path)
    tmp = z.with_name(z.name + '.tmp')
    with open(tmp, 'wb') as f:
        with zstandard.ZstdCompressor(level=LEVEL, threads=THREADS).stream_writer(f, closefd=False) as w:
            for r in recs:
                w.write((json.dumps(r) + '\n').encode())
    os.replace(tmp, z)
    if plain(path).exists():
        plain(path).unlink()


class Appender:
    """Appends records to the compressed file, as a context manager. A plain twin is first moved into the compressed file, and a compressed
    file whose last frame a stop cut short is first written anew from its complete records."""

    def __init__(self, path):
        self.path = Path(path)

    def __enter__(self):
        z = zst(self.path)
        if plain(self.path).exists() or (z.exists() and not _clean_end(z)):
            write_all(self.path, records(self.path))  # streamed: the new file is written under another name, and replaces the old one at its end
        self.f = open(z, 'ab')
        self.w = zstandard.ZstdCompressor(level=LEVEL).stream_writer(self.f, closefd=False)
        self.frame_start = time.time()
        return self

    def write(self, rec):
        self.w.write((json.dumps(rec) + '\n').encode())
        if time.time() - self.frame_start > FRAME_SECONDS:
            self.w.flush(zstandard.FLUSH_FRAME)
            self.frame_start = time.time()
        else:
            self.w.flush(zstandard.FLUSH_BLOCK)
        self.f.flush()

    def __exit__(self, *exc):
        self.w.flush(zstandard.FLUSH_FRAME)
        self.f.close()
        return False


if __name__ == '__main__':
    import sys
    if sys.argv[1:2] == ['count']:
        print(sum(1 for _ in lines(sys.argv[2])))
