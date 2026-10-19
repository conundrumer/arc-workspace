"""The Tasks section: the sizes of the tasks under `data/tasks/`."""

from arc.task import TASKS_DIR, load
from study.corpus_survey.section import Section, body, ran, table


def tasks() -> str:
    ids = sorted(p.stem for p in TASKS_DIR.glob("*.json"))
    largest: tuple[int, str, str] = (0, "", "")
    train: tuple[int, str] = (0, "")
    test: tuple[int, str] = (0, "")
    for t in ids:
        task = load(t)
        for ex in [*task.train, *task.test]:
            for g in (ex.input, ex.output):
                cells = len(g) * len(g[0]) if g else 0
                if cells > largest[0]:
                    largest = (cells, t, f"{len(g)}×{len(g[0])}")
        if len(task.train) > train[0]:
            train = (len(task.train), t)
        if len(task.test) > test[0]:
            test = (len(task.test), t)
    return body(
        table(("measure", "value"), [
            ("tasks", len(ids)),
            ("largest grid", f"{largest[2]}, {largest[0]} cells ({largest[1]})"),
            ("most train pairs", f"{train[0]} ({train[1]})"),
            ("most test inputs", f"{test[0]} ({test[1]})"),
        ]),
        ran(f"the {len(ids)} task files of `data/tasks/`"))


TASKS = Section("Tasks", 2, False, tasks)
