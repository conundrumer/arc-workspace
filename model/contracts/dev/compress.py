"""Dev labeling layer: moves plain JSON-lines files into their zstd form (jsonl.py), once each.

    python3 compress.py FILE [FILE ...]

A cache record that holds its tables as zlib and base64 (`z`) gets them as plain JSON (`tables`), so that zstd compresses across records.
Any other file goes through the zstd command as it is.
Each file's records are counted before and after; the plain file is removed only where the counts agree.
"""
import base64
import json
import subprocess
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import jsonl as J  # noqa: E402


def unpack(z):
    """The tables of a cache record written as zlib, then base64."""
    return json.loads(zlib.decompress(base64.b64decode(z)))


def plain_records(p):
    for r in J.records(p):
        if 'z' in r and 'tables' not in r:
            r = dict(r)
            r['tables'] = unpack(r.pop('z'))
        yield r


def main(paths):
    for p in map(Path, paths):
        if not p.exists() or p.suffix == '.zst':
            continue
        n = sum(1 for _ in J.lines(p))
        size = p.stat().st_size
        tmp_name = p.with_name(p.name + '.converting')  # write under another name, so that the plain file stays the one readers take
        z = J.zst(tmp_name)
        if p.name.endswith('.tables.jsonl'):
            J.write_all(tmp_name, plain_records(p))
        else:
            subprocess.run(['zstd', '-q', '-f', '-T%d' % J.THREADS, '-%d' % J.LEVEL, str(p), '-o', str(z)], check=True)
        m = sum(1 for _ in J.lines(z))
        if m != n:
            print('%s: %d records before, %d after; kept the plain file' % (p, n, m), flush=True)
            z.unlink()
            continue
        z.replace(J.zst(p))
        p.unlink()
        print('%s: %d records, %.1f MB -> %.1f MB' % (p, n, size / 1e6, J.zst(p).stat().st_size / 1e6), flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
