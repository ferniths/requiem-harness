"""Theme palette definitions for REQUIEM.

All five themes share the same base surface colors (Obsidian, Dark Iron,
Ash White, Muted Ash, Iron Border, Elevated Iron) and spacing system.
Only the accent colors differ.  Each theme is a Pydantic model so the
TUI can access them by name and Rich can consume the hex values directly.
"""

from __future__ import annotations

from pydantic import BaseModel


class Palette(BaseModel):
    """A single named theme palette."""

    name: str
    description: str

    # Base surfaces — identical across all themes
    obsidian: str = "#0C0A0B"
    dark_iron: str = "#171316"
    elevated_iron: str = "#1B171F"
    ash_white: str = "#E8E1E5"
    muted_ash: str = "#82777D"
    iron_border: str = "#2A242D"

    # Accent colors — differ per theme
    primary_accent: str
    deep_accent: str
    secondary_accent: str  # rare brand emphasis (gold in classic)

    # Derived state colors
    @property
    def selected_bg(self) -> str:
        """Slightly crimson-tinted background for selected items."""
        return self._tint(self.elevated_iron, self.primary_accent, strength=0.15)

    @property
    def hover_bg(self) -> str:
        return self._tint(self.dark_iron, self.ash_white, strength=0.05)

    @property
    def success(self) -> str:
        return "#5A9E6F"  # muted green, works with all themes

    @property
    def warning(self) -> str:
        return self.secondary_accent

    @property
    def error(self) -> str:
        return self.primary_accent

    @property
    def disabled_text(self) -> str:
        return self.muted_ash

    @property
    def focus_ring(self) -> str:
        return self.primary_accent

    @staticmethod
    def _tint(base: str, accent: str, strength: float) -> str:
        """Blend *strength* fraction of *accent* into *base*."""
        b = _hex_to_rgb(base)
        a = _hex_to_rgb(accent)
        r = int(b[0] + (a[0] - b[0]) * strength)
        g = int(b[1] + (a[1] - b[1]) * strength)
        bl = int(b[2] + (a[2] - b[2]) * strength)
        return f"#{r:02X}{g:02X}{bl:02X}"


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


# ---------------------------------------------------------------------------
# The five themes
# ---------------------------------------------------------------------------

CLASSIC = Palette(
    name="classic",
    description="Classic REQUIEM — Blood Crimson / Antique Gold",
    primary_accent="#C02645",
    deep_accent="#81172F",
    secondary_accent="#D4AF72",
)

BLUE = Palette(
    name="blue",
    description="Muted Steel Blue",
    primary_accent="#6C8FA8",
    deep_accent="#405D73",
    secondary_accent="#A8BBC7",
)

PURPLE = Palette(
    name="purple",
    description="Subdued Royal Purple",
    primary_accent="#8D78A8",
    deep_accent="#57476E",
    secondary_accent="#C0B0CE",
)

MAGENTA = Palette(
    name="magenta",
    description="Restrained Dusty Magenta",
    primary_accent="#B16B89",
    deep_accent="#704459",
    secondary_accent="#D0A0B1",
)

GREY = Palette(
    name="grey",
    description="Metallic Graphite & Silver",
    primary_accent="#A7A0A5",
    deep_accent="#655F65",
    secondary_accent="#C2BABE",
)


ALL_THEMES: dict[str, Palette] = {
    t.name: t for t in [CLASSIC, BLUE, PURPLE, MAGENTA, GREY]
}

DEFAULT_THEME = CLASSIC


def get_theme(name: str) -> Palette:
    """Return a theme by name. Falls back to Classic."""
    return ALL_THEMES.get(name, CLASSIC)


def list_theme_names() -> list[str]:
    return sorted(ALL_THEMES.keys())
