"""Build one committed study runtime in a fresh directory; never reinstall it.

Run through run_heavy.py. The source archive, wheel, interpreter environment,
and checker copies belong exclusively to this build. Rebuild into a new path.

The Cargo target folder is scratch. About four fifths of it is incremental
state and workspace artifacts that are keyed by the build's source path, so no
other build can reuse them. The build removes it after the installed extension
matches the wheel, and before it writes ready.json.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args()
    if not os.environ.get("ARC_HEAVY_CPUS"):
        parser.error("run this build through scripts/run_heavy.py --cpus N")
    repo = Path(__file__).resolve().parents[1]
    revision = subprocess.check_output(
        ["git", "rev-parse", "--verify", args.revision + "^{commit}"], cwd=repo, text=True).strip()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    done = 0
    stages = 6

    def progress(label):
        elapsed = time.monotonic() - started
        rate = done / elapsed if elapsed else 0
        eta = f"{(stages-done)/rate:.0f}s" if rate else "pending"
        print(f"{done}/{stages} stages; elapsed={elapsed:.1f}s "
              f"rate={rate:.3f} stages/s ETA={eta}; {label}", flush=True)

    def run(command, label, **kwargs):
        nonlocal done
        progress(label)
        # Inherit stdout/stderr: build output is streamed, with heartbeats
        # even while a compiler step emits nothing.
        with subprocess.Popen([str(x) for x in command], **kwargs) as process:
            while True:
                try:
                    code = process.wait(timeout=2)
                    break
                except subprocess.TimeoutExpired:
                    progress(label)
            if code:
                raise subprocess.CalledProcessError(code, command)
        done += 1
        progress(label + " finished")

    source = destination / "source"
    source.mkdir()
    archive = destination / "source.tar"
    run(["git", "archive", "--format=tar", "-o", archive, revision,
         "engine", "scripts/study", "scripts/check_study_pair_corpus.py"], "archive " + revision, cwd=repo)
    run(["tar", "-xf", archive, "-C", source], "extract committed source")
    checks = destination / "checks"
    shutil.copytree(source / "scripts/study", checks)
    shutil.copy2(source / "scripts/check_study_pair_corpus.py", checks / "check_study_pair_corpus.py")
    wheels = destination / "wheels"
    env = dict(os.environ, CARGO_TARGET_DIR=str(destination / "target"),
               CARGO_BUILD_JOBS=os.environ["ARC_HEAVY_CPUS"], PYTHONDONTWRITEBYTECODE="1")
    run(["maturin", "build", "--offline", "--profile", "tool", "--manifest-path",
         source / "engine/arclog-py/Cargo.toml", "--interpreter", sys.executable,
         "--out", wheels], "build isolated wheel", env=env)
    venv = destination / "venv"
    run([sys.executable, "-B", "-m", "venv", venv], "create private environment")
    built = list(wheels.glob("arclog-*.whl"))
    if len(built) != 1:
        raise RuntimeError(f"expected exactly one wheel, got {built}")
    # The study's readers import numpy; pin the repository environment's version.
    numpy = "numpy==" + importlib.metadata.version("numpy")
    run(["uv", "pip", "install", "--python", venv / "bin/python", "--no-deps",
         built[0], numpy, "zstandard==0.23.0"], "install private wheel and study readers")
    verify = (
        "import hashlib, pathlib, sys, zipfile, arclog, zstandard\n"
        "assert zstandard.__version__ == '0.23.0', 'study zstandard version differs'\n"
        "package = pathlib.Path(arclog.__file__).resolve().parent\n"
        "with zipfile.ZipFile(sys.argv[1]) as wheel:\n"
        "    members = [n for n in wheel.namelist() if n.endswith(('.so', '.pyd'))]\n"
        "    assert members, 'wheel has no native extension'\n"
        "    for n in members:\n"
        "        installed = package / pathlib.Path(n).name\n"
        "        assert installed.is_file() and hashlib.sha256(installed.read_bytes()).hexdigest() "
        "== hashlib.sha256(wheel.read(n)).hexdigest(), 'installed extension differs from wheel: ' + str(installed)\n")
    run([venv / "bin/python", "-I", "-B", "-c", verify, built[0]], "verify installed extension",
        cwd=destination, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    shutil.rmtree(destination / "target")
    helper = checks / "execution_evidence.py"
    manifest = dict(revision=revision, wheel=str(built[0]), python=str(venv / "bin/python"),
                    checks=str(checks), seconds=time.monotonic()-started,
                    execution_evidence=dict(path=str(helper),
                        sha256=hashlib.sha256(helper.read_bytes()).hexdigest()))
    (destination / "ready.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest), flush=True)


if __name__ == "__main__":
    main()
