"""After a green run over changed tests, a note to queue the cut of useless
tests."""

import subprocess

import pytest

NOTE = "Note: If you added tests, add a TaskCreate task to cut useless tests."


def _tests_changed(rootdir) -> bool:
    """Whether git sees a modified or untracked file under tests/."""
    run = subprocess.run(["git", "status", "--porcelain", "--", "tests/"],
                         cwd=rootdir, capture_output=True, text=True)
    return run.returncode == 0 and bool(run.stdout.strip())


@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    """Wraps outside the terminal reporter's own wrapper, so the note follows
    the stats line and a tail of the output keeps it."""
    yield
    if exitstatus != 0:
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None and _tests_changed(session.config.rootpath):
        reporter.write_line(NOTE)
