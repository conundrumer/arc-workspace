"""Packs the pass kit folder into a tar.gz that is the same for the same files: sorted entries, owner 0, a fixed time, no AppleDouble (._*) files, and a gzip header with time 0.

  <python> -I search_pass_pack.py KIT_FOLDER OUT_DIR

Writes OUT_DIR/<kit folder name>.tar.gz and prints its path and sha256.
"""
import datetime
import gzip
import hashlib
import os
import sys
import tarfile

sys.dont_write_bytecode = True


def main():
    kit, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    name = os.path.basename(kit)
    entries = []
    for root, dirs, fs in os.walk(kit):
        dirs[:] = sorted(d for d in dirs if not d.startswith('._'))
        entries.append(root)
        entries += [os.path.join(root, f) for f in sorted(fs) if not f.startswith('._')]
    mtime = int(datetime.datetime(2026, 11, 2).timestamp())
    path = '%s/%s.tar.gz' % (out, name)
    with open(path + '.tmp', 'wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0, compresslevel=6) as gz, tarfile.open(fileobj=gz, mode='w') as t:
        for p in entries:
            info = t.gettarinfo(p, arcname=os.path.join(name, os.path.relpath(p, kit)).rstrip('/.'))
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mtime = mtime
            if info.isfile():
                with open(p, 'rb') as f:
                    t.addfile(info, f)
            else:
                t.addfile(info)
    os.replace(path + '.tmp', path)
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    print('kit %s' % path)
    print('sha256 %s' % h.hexdigest())


main()
