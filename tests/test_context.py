"""The solver docs and the lib as a session reads them."""

import subprocess

from handbook.agents import write_agent
from handbook.generated import (Kept, Left, Regenerated, Rendering,
                                manifest_path, regenerate)


def test_the_agent_file_is_written_whole_and_left_alone_when_unchanged(tmp_path):
    lib = tmp_path / "lib.dl"
    lib.write_text(".decl out(p: Position)\n")
    wrappers = tmp_path / "components.py"
    out = tmp_path / "agents"
    path = write_agent(out, lib=lib, wrappers=wrappers)
    assert not list((tmp_path / "agents").glob("*.tmp"))
    stamp = path.stat().st_mtime_ns
    assert write_agent(out, lib=lib, wrappers=wrappers) == path
    assert path.stat().st_mtime_ns == stamp    # the same definition is left alone
    lib.write_text("/// The output.\n.decl out(p: Position, col: Color)\n")
    write_agent(out, lib=lib, wrappers=wrappers)
    assert "- **out** — The output." in path.read_text()


def test_only_a_listed_ignored_unchanged_file_no_source_renders_is_removed(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text(".claude/agents/\n/gen/\n")
    kept = Rendering(tmp_path / "gen" / "kept.md", "kept\n")
    names = ("gone", "edited", "shown")
    regenerate([kept, *(Rendering(tmp_path / "gen" / f"{n}.md", f"{n}\n")
                        for n in names)], tmp_path)
    shown = tmp_path / "shown.md"
    shown.write_text("shown\n")
    manifest = manifest_path(tmp_path)
    manifest.write_text(manifest.read_text().replace("gen/shown.md", "shown.md"))
    (tmp_path / "gen" / "edited.md").write_text("by hand\n")
    done = regenerate([kept], tmp_path)
    assert done == Regenerated(
        [tmp_path / "gen" / "gone.md"],
        [Left(tmp_path / "gen" / "edited.md", Kept.EDITED),
         Left(shown, Kept.NOT_IGNORED)])
    assert kept.path.exists() and shown.exists()
    assert [line.split(" ", 1)[1]
            for line in manifest.read_text().splitlines()[1:]] == ["gen/kept.md"]
