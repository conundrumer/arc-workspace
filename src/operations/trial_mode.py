"""The trial switch shared by the launches of one command run."""

from operations.mode_switch import ModeSwitch

SWITCH = ModeSwitch("trial")
OVERRIDE = SWITCH.override
read = SWITCH.read
enabled = SWITCH.enabled
