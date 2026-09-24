"""Parameter value sweep: what its report tells the reader."""

from dl import sweep


def test_a_determined_param_says_its_determination_picks_the_stored_value(
        monkeypatch):
    """A refuted extra is already picked from train when the parameter's
    determination reproduces the stored value; without one, the line keeps
    the open clause."""
    monkeypatch.setattr(sweep, "_lib_defines", lambda: {})
    result = ("n", "swept", ([(1,), (2,)], [(1,)], ["number"], {(2,): False}))
    head = "n: stored (1); train also admits [(2)]; test refutes [(2)] — "
    assert sweep.render_sweep([result], {"n"}) == [
        head + "the determination picks the stored value"
    ]
    assert sweep.render_sweep([result]) == [
        head + "a determination from train alone could pick it"
    ]
