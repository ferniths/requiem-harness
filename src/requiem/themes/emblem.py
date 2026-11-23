"""The REQUIEM terminal emblem — broken-halo + R.

The emblem is rendered as a multi-line block of Unicode box-drawing and
geometric characters.  It is intentionally compact so it can appear in
headers, onboarding, and empty states without consuming the screen.

The mark is readable in monochrome (iron border + muted ash).
"""

from __future__ import annotations


def emblem(lines: int = 6) -> list[str]:
    """Return the REQUIEM emblem as *lines* of text.

    The full emblem is 6 lines.  Fewer lines crop the top.
    """
    _emblem = [
        "   ┌─────────┐",
        "   │  ╭───╮  │",
        "   │  │ R │  │",
        "   │  ╰─╮╭─╯  │",
        "   │     ╰╯    │",
        "   └─────────┘",
    ]
    if lines >= 6:
        return _emblem
    return _emblem[-lines:]


def emblem_line(width: int = 40) -> str:
    """A single-line horizontal rule with the R motif centered."""
    side = max(0, (width - 7) // 2)
    return "─" * side + "  ╭─╮  " + "─" * max(0, width - side - 7)


def wordmark(spaced: bool = True) -> str:
    """Return 'REQUIEM' with optional letter-spacing."""
    letters = "REQUIEM"
    if spaced:
        return "  ".join(letters)
    return letters


def header_block() -> list[str]:
    """A compact header: emblem + wordmark + rule."""
    out: list[str] = []
    out.append("")
    out.extend(emblem(4))
    out.append("")
    out.append(wordmark(spaced=True))
    out.append(emblem_line(52))
    out.append("")
    return out


# ASCII fallback for terminals without Unicode
_EMBLEM_ASCII = [
    "  +---------+",
    "  | (  R  ) |",
    "  |   ___   |",
    "  |  |___|  |",
    "  +---------+",
]


def emblem_ascii(lines: int = 5) -> list[str]:
    if lines >= 5:
        return _EMBLEM_ASCII
    return _EMBLEM_ASCII[-lines:]


def supports_unicode() -> bool:
    """Best-effort check for terminal Unicode support."""
    import sys
    try:
        return bool(sys.stdout.encoding and sys.stdout.encoding.lower().startswith("utf"))
    except Exception:
        return True
