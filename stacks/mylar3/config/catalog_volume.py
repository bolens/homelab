"""Respect explicit catalog volumes before applying optional defaults."""


def volume_label(value, default=False):
    """An explicit catalog volume takes precedence over optional defaulting."""
    text = str(value).strip() if value is not None else ""
    if text.isdecimal() and int(text) > 0:
        return "v" + str(int(text))
    return "v1" if default else None
