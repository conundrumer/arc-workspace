"""Cross-worker disk reserve checks and a shared, resumable stop marker."""
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import shutil
import time


class DiskSpaceStop(BaseException):
    """Escape pair/case error handlers and close the incomplete task cleanly."""


class DiskGuard:
    def __init__(self,root,min_free_gb=30):
        self.root=Path(root);self.minimum=int(min_free_gb*1_000_000_000)
        self.marker=self.root/'.disk-stop.json';self.lock=self.root/'.disk-guard.lock'
    def _check(self,reserve=0):
        if self.marker.exists():raise DiskSpaceStop(self.marker.read_text())
        free=shutil.disk_usage(self.root).free
        if free-reserve<self.minimum:
            row=dict(event='disk_guard_stop',free_bytes=free,min_free_bytes=self.minimum,
                     pending_bytes=reserve,time=time.time())
            # The file is small and written while holding the common guard lock.
            self.marker.write_text(json.dumps(row)+'\n')
            raise DiskSpaceStop(json.dumps(row))
        return free
    @contextmanager
    def permit(self,reserve=0):
        with self.lock.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            self._check(reserve)
            yield
    def check(self):
        with self.permit():return shutil.disk_usage(self.root).free
    def resume(self):
        # A previous guard stop is resumable only after free space recovers.
        with self.lock.open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            free=shutil.disk_usage(self.root).free
            if free<self.minimum:raise DiskSpaceStop('free space remains below disk reserve')
            self.marker.unlink(missing_ok=True)


def directory_bytes(path):
    logical=allocated=files=0
    for p in Path(path).rglob('*'):
        if p.is_file():
            st=p.stat();logical+=st.st_size;allocated+=st.st_blocks*512;files+=1
    return dict(bytes=logical,allocated_bytes=allocated,files=files)
