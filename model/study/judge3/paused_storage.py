"""Lossless file compression with original-byte SHA and exact restore on resume.

Never evaluates a program or regenerates a result. Existing receipts keep their
original byte hashes. Compression verifies the complete gzip stream before
removing its original. Restore verifies before publishing the original path.
"""
import argparse
import gzip
import hashlib
import io
import itertools
import json
import math
import os
from pathlib import Path
import stat
import tempfile

BLOCK = 1024 * 1024


def digest_stream(stream):
    h = hashlib.sha256(); size = 0
    for block in iter(lambda: stream.read(BLOCK), b''):
        h.update(block); size += len(block)
    return h.hexdigest(), size


def fsync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def sidecar(path):
    return path.with_name(path.name + '.sha256')


def publish_sha(path, digest, size):
    target = sidecar(path)
    value = {'schema': 'lossless-original-bytes-v1', 'sha256': digest,
             'uncompressed_bytes': size, 'original_name': path.name[:-3]}
    fd, temporary = tempfile.mkstemp(prefix='.' + target.name, dir=target.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, separators=(',', ':')); stream.write('\n')
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def verified(path):
    expected = json.loads(sidecar(path).read_text())
    if expected['schema'] != 'lossless-original-bytes-v1':
        raise ValueError('unsupported compressed checksum sidecar: ' + str(path))
    with gzip.open(path, 'rb') as stream: actual = digest_stream(stream)
    if actual != (expected['sha256'], expected['uncompressed_bytes']):
        raise ValueError('compressed original-byte checksum differs: ' + str(path))
    return expected


def compress_file(original):
    original = Path(original)
    if original.is_symlink(): raise ValueError('will not replace symlink: ' + str(original))
    before = original.stat(); archive = original.with_name(original.name + '.gz')
    if archive.exists():
        expected = verified(archive)
        with original.open('rb') as stream: actual = digest_stream(stream)
        if actual != (expected['sha256'], expected['uncompressed_bytes']):
            raise ValueError('existing compressed copy differs: ' + str(original))
    else:
        fd, temporary = tempfile.mkstemp(prefix='.' + archive.name, dir=archive.parent)
        h = hashlib.sha256(); size = 0
        try:
            with os.fdopen(fd, 'wb') as raw:
                with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0, compresslevel=6) as output:
                    with original.open('rb') as source:
                        for block in iter(lambda: source.read(BLOCK), b''):
                            output.write(block); h.update(block); size += len(block)
                raw.flush(); os.fsync(raw.fileno())
            with gzip.open(temporary, 'rb') as stream:
                if digest_stream(stream) != (h.hexdigest(), size):
                    raise ValueError('compression round-trip differs: ' + str(original))
            os.chmod(temporary, stat.S_IMODE(before.st_mode))
            os.utime(temporary, ns=(before.st_atime_ns, before.st_mtime_ns))
            # The original stays in place until gzip + original-SHA are durable.
            publish_sha(archive, h.hexdigest(), size)
            os.replace(temporary, archive); fsync_directory(archive.parent)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
    after = original.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError('original changed during compression; retained: ' + str(original))
    original.unlink(); fsync_directory(original.parent)
    return {'path': str(original), 'before': before.st_size,
            'after': archive.stat().st_size + sidecar(archive).stat().st_size}


def restore_file(archive):
    archive = Path(archive); original = archive.with_name(archive.name[:-3])
    metadata = json.loads(sidecar(archive).read_text()); before = archive.stat()
    expected = metadata['sha256'], metadata['uncompressed_bytes']
    if metadata['schema'] != 'lossless-original-bytes-v1': raise ValueError('unknown archive schema')
    if original.exists():
        with original.open('rb') as stream: actual = digest_stream(stream)
        if actual != expected: raise ValueError('restored path already differs: ' + str(original))
        verified(archive)
    else:
        fd, temporary = tempfile.mkstemp(prefix='.' + original.name, dir=original.parent)
        h = hashlib.sha256(); size = 0
        try:
            with os.fdopen(fd, 'wb') as output, gzip.open(archive, 'rb') as source:
                for block in iter(lambda: source.read(BLOCK), b''):
                    output.write(block); h.update(block); size += len(block)
                output.flush(); os.fsync(output.fileno())
            if (h.hexdigest(), size) != expected: raise ValueError('restore checksum differs')
            os.chmod(temporary, stat.S_IMODE(before.st_mode))
            os.utime(temporary, ns=(before.st_atime_ns, before.st_mtime_ns))
            os.replace(temporary, original); fsync_directory(original.parent)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)
    archive.unlink(); sidecar(archive).unlink(); fsync_directory(original.parent)
    return {'path': str(original), 'restored_bytes': expected[1], 'sha256': expected[0]}


def read_gzip_json(path, *, expected_sha256=None):
    expected = json.loads(sidecar(Path(path)).read_text())
    if expected['schema'] != 'lossless-original-bytes-v1': raise ValueError('unknown cache SHA schema')
    h = hashlib.sha256(); size = 0
    with gzip.open(path, 'rb') as source:
        class Recording(io.RawIOBase):
            def readable(self): return True
            def readinto(self, buffer):
                nonlocal size
                data = source.read(len(buffer)); buffer[:len(data)] = data
                h.update(data); size += len(data); return len(data)
        with io.TextIOWrapper(io.BufferedReader(Recording()), encoding='utf-8') as text:
            value = json.load(text)
    if (h.hexdigest(), size) != (expected['sha256'], expected['uncompressed_bytes']):
        raise ValueError('compressed cache SHA differs: ' + str(path))
    if expected_sha256 is not None and h.hexdigest()!=expected_sha256:
        raise ValueError('referenced JSON SHA differs: '+str(path))
    return value


def _write_gzip_chunks(path, chunks, *, compresslevel=6):
    """The one atomic streaming gzip/original-SHA codec for text and JSON."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    h = hashlib.sha256(); size = 0
    try:
        with os.fdopen(fd, 'wb') as raw:
            with gzip.GzipFile(filename='', fileobj=raw, mode='wb', mtime=0, compresslevel=compresslevel) as output:
                pending = []; length = 0
                def flush():
                    nonlocal length, size
                    data = ''.join(pending).encode('utf-8'); output.write(data)
                    h.update(data); size += len(data); pending.clear(); length = 0
                for chunk in chunks:
                    pending.append(chunk); length += len(chunk)
                    if length >= 65536: flush()
                if pending: flush()
            raw.flush(); os.fsync(raw.fileno())
        with gzip.open(temporary, 'rb') as stream:
            if digest_stream(stream) != (h.hexdigest(), size): raise ValueError('new cache gzip differs')
        publish_sha(path, h.hexdigest(), size)
        os.replace(temporary, path); fsync_directory(path.parent)
        return h.hexdigest()
    finally:
        if os.path.exists(temporary): os.unlink(temporary)



def write_gzip_json(path, value, *, json_options=None, compresslevel=6, return_sha=False):
    """Stream JSON directly; existing callers keep compact level-6 bytes/None.

    Options permit exact legacy JSON formatting without a second codec. The
    optional digest describes the uncompressed UTF-8 bytes including newline.
    """
    options=dict(ensure_ascii=False,allow_nan=False,separators=(',',':'))
    if json_options is not None:options.update(json_options)
    chunks=itertools.chain(json.JSONEncoder(**options).iterencode(value), ('\n',))
    digest=_write_gzip_chunks(path,chunks,compresslevel=compresslevel)
    if return_sha:return digest


def write_gzip_text(path, text, *, compresslevel=6):
    """Write exact UTF-8 text through the same verified atomic gzip codec."""
    return _write_gzip_chunks(path,(text,),compresslevel=compresslevel)


def read_json(path, *, expected_sha256=None):
    """Plain/legacy gzip or missing logical path's verified gzip sibling."""
    path=Path(path);missing=not path.exists()
    actual=path.with_name(path.name+'.gz') if missing else path
    if actual.suffix=='.gz':
        if missing or sidecar(actual).exists() or expected_sha256 is not None:
            return read_gzip_json(actual,expected_sha256=expected_sha256)
        with gzip.open(actual,'rt',encoding='utf-8') as stream:return json.load(stream)
    data=actual.read_bytes()
    if expected_sha256 is not None and hashlib.sha256(data).hexdigest()!=expected_sha256:
        raise ValueError('referenced JSON SHA differs: '+str(path))
    return json.loads(data)


def files(root):
    root = Path(root)
    if not root.exists(): return []
    return sorted(p for p in root.rglob('*') if p.is_file() and not p.is_symlink()) if root.is_dir() else [root]


def estimate(root):
    candidates = [p for p in files(root) if not p.name.endswith(('.gz', '.sha256'))]
    total = sum(p.stat().st_size for p in candidates)
    # Bounded sample only; conversion does the full per-file verification once.
    sample = sorted(candidates, key=lambda p: p.stat().st_size, reverse=True)[:8]
    read = compressed = 0
    for path in sample:
        with path.open('rb') as stream: value = stream.read(BLOCK)
        read += len(value); compressed += len(gzip.compress(value, compresslevel=6, mtime=0))
    ratio = compressed / read if read else 1
    estimated = sum(max(4096, math.ceil(p.stat().st_size * ratio / 4096) * 4096) + 4096
                    for p in candidates)
    return dict(root=str(root), files=len(candidates), original_bytes=total,
                sample_bytes=read, estimated_allocated_after=estimated,
                estimate_only=True, estimated_ratio=ratio)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['compress', 'restore', 'estimate'])
    parser.add_argument('roots', nargs='+', type=Path)
    args = parser.parse_args()
    count = 0; before = after = 0
    for root in args.roots:
        if args.operation == 'estimate': print(json.dumps(estimate(root)), flush=True); continue
        for path in files(root):
            if args.operation == 'compress':
                if path.name.endswith(('.gz', '.sha256')) or path.name.startswith('.'): continue
                result = compress_file(path); before += result['before']; after += result['after']
            else:
                if not path.name.endswith('.gz') or not sidecar(path).is_file(): continue
                result = restore_file(path)
            count += 1; print(json.dumps(result), flush=True)
    print(json.dumps(dict(operation=args.operation, files=count, before=before, after=after)), flush=True)


if __name__ == '__main__': main()
