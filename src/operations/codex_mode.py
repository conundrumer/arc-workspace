"""The Codex switch shared by the launches of one command run."""

from operations.mode_switch import ModeSwitch

SWITCH = ModeSwitch("codex")
OVERRIDE = SWITCH.override
read = SWITCH.read
enabled = SWITCH.enabled
