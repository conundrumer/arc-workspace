"""Ships the concept case of aba27056 to Kaggle and fetches its run.

Assembles a private dataset of the arclog wheel, the case program's token
stream and the task file with each test output removed; versions the dataset
(creating it where the account holds none); pushes the notebook as a private
kernel with no internet; polls the kernel's status; and fetches its output.

    ship.py <wheel> <stream.json> <task.json> <work dir>

The work directory gets `dataset/`, `kernel/` and `out/`. Each `kaggle` call
runs under a 60 s timeout; the poll of the kernel ends after `WAIT_SECONDS`.
"""

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
TASK_ID = "aba27056"
CALL_SECONDS = 60
WAIT_SECONDS = 1500
POLL_SECONDS = 15
KAGGLE = "/Users/davidlu/.local/bin/kaggle"


def kaggle(*args: str) -> str:
    """The output of one `kaggle` call, which fails the script where the call fails."""
    result = subprocess.run([KAGGLE, *args], capture_output=True, text=True, timeout=CALL_SECONDS)
    output = result.stdout + result.stderr
    print(f"$ kaggle {' '.join(args)}\n{output}", flush=True)
    if result.returncode != 0:
        raise SystemExit(f"kaggle {args[0]} {args[1]} exited {result.returncode}")
    return output


def held_out(task_text: str) -> str:
    """The task file with the `output` of each test pair removed."""
    task = json.loads(task_text)
    task["test"] = [{key: value for key, value in pair.items() if key != "output"} for pair in task["test"]]
    return json.dumps(task)


def assemble(wheel: Path, stream: Path, task: Path, work: Path) -> tuple[Path, Path]:
    """The dataset and kernel directories under `work`."""
    dataset, kernel = work / "dataset", work / "kernel"
    for directory in (dataset, kernel):
        shutil.rmtree(directory, ignore_errors=True)
        directory.mkdir(parents=True)
    shutil.copy(wheel, dataset / wheel.name)
    shutil.copy(stream, dataset / f"{TASK_ID}.stream.json")
    (dataset / f"{TASK_ID}.json").write_text(held_out(task.read_text()))
    shutil.copy(HERE / "dataset-metadata.json", dataset / "dataset-metadata.json")
    shutil.copy(HERE / "kernel-metadata.json", kernel / "kernel-metadata.json")
    shutil.copy(HERE / "notebook.ipynb", kernel / "notebook.ipynb")
    return dataset, kernel


def version_dataset(dataset: Path) -> None:
    """Creates the dataset where the account holds none, and otherwise versions it, then waits until it is ready."""
    ref = json.loads((dataset / "dataset-metadata.json").read_text())["id"]
    slug = ref.split("/")[1]
    if ref in kaggle("datasets", "list", "--mine", "-s", slug, "--csv"):
        kaggle("datasets", "version", "-p", str(dataset), "-m", f"{TASK_ID} {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", "-r", "skip")
    else:
        kaggle("datasets", "create", "-p", str(dataset), "-r", "skip")
    deadline = time.monotonic() + WAIT_SECONDS
    names = [path.name for path in dataset.iterdir() if path.name != "dataset-metadata.json"]
    while not all(name in kaggle("datasets", "files", ref) for name in names):
        if time.monotonic() > deadline:
            raise SystemExit("the dataset is not ready")
        time.sleep(POLL_SECONDS)


def run_kernel(kernel: Path, out: Path) -> str:
    """Pushes the kernel, waits for its run to end, fetches its output, and gives its final status."""
    ref = json.loads((kernel / "kernel-metadata.json").read_text())["id"]
    kaggle("kernels", "push", "-p", str(kernel))
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        time.sleep(POLL_SECONDS)
        status = kaggle("kernels", "status", ref)
        match = re.search(r"(COMPLETE|ERROR|CANCEL\w*)", status)
        if match:
            break
        if time.monotonic() > deadline:
            raise SystemExit("the kernel did not end in time")
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    kaggle("kernels", "output", ref, "-p", str(out))
    return match.group(1)


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(__doc__, file=sys.stderr)
        return 2
    wheel, stream, task, work = (Path(arg) for arg in argv[1:])
    dataset, kernel = assemble(wheel, stream, task, work)
    version_dataset(dataset)
    status = run_kernel(kernel, work / "out")
    print(f"kernel status: {status}; output in {work / 'out'}")
    return 0 if status == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
