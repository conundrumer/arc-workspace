"""Lightweight installed-package file inventory and content fingerprint."""
import glob
import hashlib
import os


def package_files(package: str) -> list[tuple[str, str]]:
    """(relative name, path), excluding bytecode caches, including extensions."""
    return [(os.path.relpath(f, package), f) for f in glob.glob(f"{package}/**", recursive=True)
            if os.path.isfile(f) and "__pycache__" not in f]


def digest_files(files) -> str:
    """Hash sorted name/NUL/bytes/NUL pairs; shared by all package consumers."""
    digest = hashlib.sha256()
    for name, path in sorted(files):
        digest.update(name.encode() + b"\0" + open(path, "rb").read() + b"\0")
    return digest.hexdigest()
