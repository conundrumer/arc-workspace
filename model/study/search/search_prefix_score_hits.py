#!/usr/bin/env python
"""tp_end.py with the prefix score of superdag_search.py in the search's order. Same command line. Run from a kit's top folder, with tp_end.py there, and
SEARCH_PREFIX_SCORE and SEARCH_PREFIX_BETA set for an arm with the score."""
import os
import sys
import types

sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), 'model', 'study', 'sampler'))
import live_try  # noqa: E402
import superdag_search as SS  # noqa: E402
import tp_end  # noqa: E402

SS.load_rule()
session_of = live_try.session_of


def session_of_(task):
    got = session_of(task)
    SS.POOL[:] = [types.SimpleNamespace(task=got[1])]
    SS.patch_search_run()  # after tp_end's hook on Run.clause_of, which this must wrap
    return got


live_try.session_of = session_of_
tp_end.main()
