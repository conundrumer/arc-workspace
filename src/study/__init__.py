"""Study tooling over the corpus and the theory, apart from the runner.
It holds no calibration card, since that card reads a peer file that no
`solver.load` gives.

`study.card_spec` holds what a card spec may state, `study.card_runs` the
card's solver run on each witness input and the checks of the card
against those runs, and `study.cards` the HTML page of a card and the page
that bundles several.
`study.corpus_scan` holds a scan of the solver corpus, and
`study.theta_card` one card defined in code, whose table is that scan."""
