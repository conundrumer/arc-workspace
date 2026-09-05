"""The page, the modules, and the stylesheet the server serves."""

import re

from .conftest import ROOT, get

UI_IMPORT = re.compile(r'(?:from |src=)"(/ui/[^"]+)"')
STYLESHEET = re.compile(r'<link rel="stylesheet" href="(/ui/[^"]+)"')


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


def test_the_stylesheet_the_page_links_is_served(srv):
    href, = STYLESHEET.findall(get(srv, "/")["body"].decode())
    sheet = get(srv, href)
    assert (sheet["status"], sheet["ctype"]) == (200, "text/css")
    assert "#topbar" in sheet["body"].decode()


def test_the_ui_route_serves_only_modules_and_the_stylesheet_under_ui(srv):
    assert get(srv, "/ui/../server.py")["status"] == 404
    assert get(srv, "/ui/../console.html")["status"] == 404
    assert get(srv, "/ui/missing.js")["status"] == 404
    assert get(srv, "/ui/missing.css")["status"] == 404
    assert get(srv, "/ui/")["status"] == 404


STYLESHEET_FILE = ROOT / "tools" / "console" / "ui" / "console.css"
CSS_SECTION = re.compile(r"/\* -{10} (.+?) -{10} \*/")


def css_rules(css: str) -> list[tuple[str, str]]:
    """Each (section, selector) in the page's stylesheet, the selectors inside
    an @media block included; comments, at-rule preambles and rule bodies are
    left out."""
    css = re.sub(r"/\*(?!\s-{10} ).*?\*/", "", css, flags=re.S)
    out, section, i = [], "", 0
    while i < len(css):
        if css[i].isspace():
            i += 1
            continue
        if css.startswith("/*", i):
            j = css.index("*/", i) + 2
            section = CSS_SECTION.match(css[i:j]).group(1)
            i = j
            continue
        k = css.index("{", i)
        head = css[i:k].strip()
        if head.startswith("@media"):
            i = k + 1
            continue
        depth, j = 0, k
        while True:
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            j += 1
            if depth == 0:
                break
        if not head.startswith("@"):
            out += [(section, sel.strip()) for sel in head.split(",")]
        i = j
        if css[i:].lstrip().startswith("}"):   # the close of an @media block
            i = css.index("}", i) + 1
    return out


def test_a_component_section_of_the_stylesheet_scopes_every_rule_under_an_id():
    """A bare class selector matches wherever the class name recurs, so one
    component's row styling reached another component's rows. Outside the
    shared section, every selector begins at an element id."""
    rules = css_rules(STYLESHEET_FILE.read_text())
    runs = [s for i, (s, _) in enumerate(rules) if i == 0 or rules[i - 1][0] != s]
    assert runs[0] == "shared" and runs.count("shared") == 1, runs
    loose = [(section, sel) for section, sel in rules
             if section != "shared" and not re.match(r"(body\.[\w-]+ )?#", sel)]
    assert loose == [], loose
