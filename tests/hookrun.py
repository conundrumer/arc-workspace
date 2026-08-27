"""Runs a console hook script in this process.

A hook is a script the harness calls with a JSON event on stdin; it answers
on stdout, or refuses on stderr with a non-zero exit. Each call loads the
script fresh, so the module-level environment reads land per call.
"""
import contextlib
import importlib.util
import io
import os
import sys


def run_hook(script, stdin_text, env=None):
    """The hook's exit code, stdout, and stderr for one event."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.ExitStack() as stack:
        stack.enter_context(_patched(sys, stdin=io.StringIO(stdin_text),
                                     stdout=out, stderr=err))
        if env is not None:
            stack.enter_context(_environ(env))
        spec = importlib.util.spec_from_file_location("hook_under_test", script)
        module = importlib.util.module_from_spec(spec)
        code = 0
        try:
            spec.loader.exec_module(module)
            module.main()
        except SystemExit as exit:
            code = exit.code or 0
    return code, out.getvalue(), err.getvalue()


@contextlib.contextmanager
def _patched(target, **names):
    before = {k: getattr(target, k) for k in names}
    for k, v in names.items():
        setattr(target, k, v)
    try:
        yield
    finally:
        for k, v in before.items():
            setattr(target, k, v)


@contextlib.contextmanager
def _environ(env):
    before = dict(os.environ)
    os.environ.clear()
    os.environ.update(env)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(before)
