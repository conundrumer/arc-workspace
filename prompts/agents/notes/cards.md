+ document-size-budget: 1537
* comment: when editing this doc
    - Reader: the coordinator, by a link, before it launches an agent on cards.
    - Acts: launching that agent, [Cards](#cards).

# Card notes
- The statements on cards, that the coordinator reads before it launches or resumes an agent on cards.

## Cards
- When the user requests cards to help make a decision regarding a solver, launch one handbook agent for all the cards of that request, and give it the instructions below.
    - Where the decision is which model is a task's concept, tell it to make one deck of the cards with `uv run python scripts/concept_deck.py <name> <spec>.json ...`, from one spec per task in the form [deck_spec.py](src/study/deck_spec.py) gives.
        + xref: src/study/deck_spec.py
    - For any other decision, tell it to make each card based on [card_spec.py](src/study/card_spec.py), and to bundle them with `uv run python scripts/cards.py bundle <name> <page> ...` where they are several.
        + xref: src/study/card_spec.py, scripts/cards.py:main
    - Tell it to write on the page, a spec's question and option texts included, only the handbook's words, the task's own terms and plain descriptions.
    - Tell it to publish the page as a private artifact, and to report the artifact's link.
- Give the user the link that agent reports, in place of the page's path.
- When you launch or resume an agent to render again a page whose link you gave the user, tell it to publish it to that link.
