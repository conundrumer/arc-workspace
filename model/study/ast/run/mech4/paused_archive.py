"""Restore the paused lib journal without expanding historical replay artifacts."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import tempfile


def restore_journal(database):
    database = Path(database).resolve()
    archive = database.parent.with_name(database.parent.name + '.paused.tar.zst')
    if database.exists() or not archive.exists():
        return False
    names = {database.name, database.name + '-wal'}
    database.parent.mkdir(parents=True, exist_ok=True)
    before = archive.stat()
    signature = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    found = {}
    with tempfile.TemporaryDirectory(prefix='.restore-journal-', dir=database.parent) as temporary:
        stage = Path(temporary)
        # Stream the existing archive once. Only the journal and optional WAL
        # occupy disk; no native program or table is evaluated or regenerated.
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(['zstd', '-dc', '--', str(archive)],
                                       stdout=subprocess.PIPE, stderr=errors)
            try:
                with tarfile.open(fileobj=process.stdout, mode='r|') as stream:
                    for member in stream:
                        path = PurePosixPath(member.name)
                        parent = [p for p in path.parts[:-1] if p not in ('.', '/')]
                        if (path.name not in names or
                                (parent and parent[-1] != database.parent.name)):
                            continue
                        if not member.isfile() or path.name in found:
                            raise ValueError('ambiguous/nonregular archived journal: ' + member.name)
                        target = stage / path.name
                        digest = hashlib.sha256()
                        with stream.extractfile(member) as source, target.open('wb') as output:
                            while block := source.read(1024 * 1024):
                                output.write(block)
                                digest.update(block)
                            output.flush()
                            os.fsync(output.fileno())
                        if target.stat().st_size != member.size:
                            raise ValueError('archived journal length differs')
                        check = hashlib.sha256()
                        with target.open('rb') as source:
                            while block := source.read(1024 * 1024):
                                check.update(block)
                        if check.digest() != digest.digest():
                            raise ValueError('restored journal SHA differs')
                        found[path.name] = dict(member=member.name, bytes=member.size,
                                               sha256=digest.hexdigest())
                # Consume the zstd frame to its end so a truncated archive or
                # failed decoder cannot publish a partially restored journal.
                while process.stdout.read(1024 * 1024):
                    pass
                if process.wait() != 0:
                    errors.seek(0)
                    raise ValueError('archive decode failed: ' + errors.read().decode(errors='replace'))
            finally:
                process.stdout.close()
                if process.poll() is None:
                    process.terminate()
                    process.wait()
        after = archive.stat()
        if signature != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError('paused archive changed during restore')
        if database.name not in found:
            raise ValueError('journal missing from paused archive: ' + str(archive))
        # Publish the WAL before its main database. The caller holds lib.lock.
        for name in sorted(found, key=lambda name: name == database.name):
            sha = found[name]['sha256']
            (stage / (name + '.paused-original.sha256')).write_text(sha + '  ' + name + '\n')
            os.replace(stage / (name + '.paused-original.sha256'),
                       database.parent / (name + '.paused-original.sha256'))
            os.replace(stage / name, database.parent / name)
        receipt = dict(archive=str(archive), restored=found,
                       historical_artifacts='retained in archive; not expanded')
        (database.parent / 'paused-journal-restore.json').write_text(json.dumps(receipt) + '\n')
    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', type=Path)
    args = parser.parse_args()
    import fcntl
    args.database.parent.mkdir(parents=True, exist_ok=True)
    with args.database.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        print(json.dumps({'restored': restore_journal(args.database)}))
