"""The page and the modules the server serves."""

import re

from .conftest import get

UI_IMPORT = re.compile(r'(?:from |src=)"(/ui/[^"]+)"')


def test_the_page_and_every_module_it_imports_are_served(srv):
    page = get(srv, "/")
    assert (page["status"], page["ctype"]) == (200, "text/html")
    todo = UI_IMPORT.findall(page["body"].decode())
    seen = set()
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        r = get(srv, path)
        assert (r["status"], r["ctype"]) == (200, "application/javascript"), path
        todo += UI_IMPORT.findall(r["body"].decode())
    assert {"/ui/shell.js", "/ui/prose.js"} <= seen


def test_the_ui_route_serves_only_modules_and_the_stylesheet_under_ui(srv):
    assert get(srv, "/ui/../server.py")["status"] == 404
    assert get(srv, "/ui/../console.html")["status"] == 404
    assert get(srv, "/ui/missing.js")["status"] == 404
    assert get(srv, "/ui/missing.css")["status"] == 404
    assert get(srv, "/ui/")["status"] == 404


