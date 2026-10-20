+ budget: 1291
* comment: when editing this doc
    - The decision analyst receives this document from the step command as it enters the deciding of a step an operator holds, once it has read its brief.
    - Acts, each with its section:
        - Deciding a held step and giving the line that rules it: [A held step](#a-held-step).

# A held step
- Decide a held step as [How a decision is made](prompts/agents/decision-analyst.md#how-a-decision-is-made) gives. Where the step gives a decision key, give the line that rules it in your reply, on a line of its own, in the form [An operator's brief](prompts/agents/notes/launching.md#an-operators-brief) gives an `Op decision:` line.
    + xref: src/operations/directives.py:Directive.DECISION, prompts/agents/notes/launching.md#an-operators-brief, prompts/agents/decision-analyst.md#how-a-decision-is-made
    - Where an empty diff refused the merge, check the work required before the merge against the live main tree and any persistent ignored work that the change requires. Choose `passes` where that work is complete, so the operator can run the closing sequence, including scheduled after-merge work. Otherwise choose `again` and give the responsible editor the missing work.
        * comment: Change 11-2450, Design: judge work required before the merge; scheduled after-merge work remains for the closing sequence. Its Grounds record repeated empty-merge stalls on 11-1362 and ignored-work changes in 9-1268, including 11-1215, whose Intent is performed wholly after the merge.
- Where the decision needs an act that no choice of the step gives, make that act yourself, before you give the line that rules the step where it takes one.
- Where [The user's part](prompts/agents/decision-analyst.md#the-users-part) brings that decision to the user, give in its item, for a step that gives a decision key, the line that rules the step for each option.
    + xref: prompts/agents/decision-analyst.md#the-users-part
- Where the operator's command could have decided the step from the state it reads, that is a fault you notice.
