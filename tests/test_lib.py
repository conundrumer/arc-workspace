"""The lib's sources pass the checks in dl.libcheck."""

from dl.libcheck import check


def test_the_lib_passes_its_checks():
    assert check() == []
