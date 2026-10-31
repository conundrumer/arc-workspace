# ff805c23 create: progress notes

- delay: `uv run python scripts/run_dl.py witness ff805c23 --file programs/reports/ff805c23/witnesses.json` with `$FoundCenter` widened to non-square frames for SYM_BOX. Every case timed out after 20 s on the three 24×24 and 26×26 witnesses, because the candidate frames grew from about a thousand to about ten thousand per input. It cost about 2 minutes. The square-frame form was put back.
- interference: the PreToolUse hook blocked a Bash call that wrapped a `run_dl.py witness` run in `time ( ... | tail )`, with the message "executable input cannot be read: source: unsupported function or array syntax". It cost one call. The call went through again without the wrapper.
