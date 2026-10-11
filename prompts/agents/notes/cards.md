# Card notes
- The statements on cards, that the coordinator reads before it launches or resumes an agent on cards.

## Cards
- When the user requests cards to help make a decision regarding a solver, launch one handbook agent for all the cards of that request, and tell it to make each based on [card_spec.py](src/study/card_spec.py), to bundle them with `uv run python scripts/cards.py bundle <name> <page> ...` where they are several, to publish the card or the bundle as a private artifact, and to report the artifact's link.
- Give the user the link that agent reports, in place of the path of the card or the bundle.
- When you launch or resume an agent to render again a card or a bundle whose link you gave the user, tell it to publish it to that link.
