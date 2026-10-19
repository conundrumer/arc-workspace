"""The nesting of a text's lines under a list item of a text the command
prints."""


def nested(text: str) -> list[str]:
    """The lines of `text`, each one level deeper, nested under a list
    item."""
    return [f"    {ln}".rstrip() for ln in text.strip().splitlines()]
