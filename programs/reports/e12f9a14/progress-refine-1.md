# e12f9a14 refine-1 progress

- interference: [waiting-on-commands](prompts/agents/notes/commands.md#waiting-on-commands), "have its until-loop give up just under that timeout". The PreToolUse hook refused both a `while` loop and an `until` loop led by `: 'unattended-wait: …';`, with "unsupported executable construct". A plain `sleep` was accepted, and then the user moved it to the background and wrote "no waiting". Cost: three refused calls and one stopped wait. The doc line and the hook still disagree.
