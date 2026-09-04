"""After a green run over changed tests, a note to cut the useless ones once
the work is done."""

import subprocess

import pytest

NOTE = "Note: When you are done, cut the useless tests among the ones you added."


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
