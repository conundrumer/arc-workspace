"""Restore the paused target journal without expanding replay artifacts."""
import fcntl
from pathlib import Path
from ._paths import CODE_ROOT,DATA


def ensure_database(database):
    """Restore exact SQLite/WAL bytes; never create an empty replacement.

    Mech4 owns the shared streaming tar/zstd extractor and original-byte SHA
    verification. This wrapper serializes target read/resume restoration. No
    evaluator, task session, clause search or labeling is invoked.
    """
    database=Path(database).resolve()
    if database.exists() or database.name!='targets.sqlite3':return False
    archive=database.parent.with_name(database.parent.name+'.paused.tar.zst')
    if not archive.exists():return False
    with archive.with_name(archive.name+'.restore.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if database.exists():return False
        from mech4 import paused_archive
        if Path(paused_archive.__file__).resolve()!=CODE_ROOT/'ast/run/mech4/paused_archive.py':
            raise RuntimeError('paused archive extractor loaded outside this checkout')
        return paused_archive.restore_journal(database)


if __name__=='__main__':
    import argparse
    import json
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database',type=Path,nargs='?',default=DATA/'targets.sqlite3')
    args=parser.parse_args()
    print(json.dumps(dict(restored=ensure_database(args.database),database=str(args.database))))
