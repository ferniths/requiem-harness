"""Theme manager — central accessor for the active theme palette.

All TUI widgets obtain their colors from the ThemeManager, never from
hardcoded hex values.  The theme can be switched at runtime without
restarting the application.
"""

from __future__ import annotations

from rich.style import Style
from rich.text import Text

from requiem.themes.palettes import Palette, get_theme

# Shared UI roles used throughout the TUI
UI_ROLE = [
    "bg", "bg_recessed", "bg_elevated", "text", "text_secondary", "border",
    "accent", "accent_deep", "accent_secondary", "selected_bg", "hover_bg",
    "success", "warning", "error", "disabled", "focus",
]


class ThemeManager:
    """Holds and exposes the active theme."""

    def __init__(self, name: str = "classic") -> None:
        self._palette: Palette = get_theme(name)
        self._name = self._palette.name

    @property
    def palette(self) -> Palette:
        return self._palette

    @property
    def name(self) -> str:
        return self._name

    def set_theme(self, name: str) -> None:
        """Switch to a named theme. No-op if already active."""
        self._palette = get_theme(name)
        self._name = self._palette.name

    def cycle_theme(self, direction: int = 1) -> None:
        """Cycle to the next/previous theme in the fixed list."""
        from requiem.themes.palettes import ALL_THEMES
        names = list(ALL_THEMES.keys())
        idx = names.index(self._name) if self._name in names else 0
        idx = (idx + direction) % len(names)
        self.set_theme(names[idx])

    # -- Rich helpers ------------------------------------------------------

    def style(self, role: str, **overrides: str) -> Style:
        """Build a Rich Style for the given UI role.

        Example:  theme.style("text", bold=True)
        """
        color = self._resolve(role)
        s = Style(color=color, **{k: v for k, v in overrides.items() if v})  # type: ignore[arg-type]
        return s

    def style_bg(self, role: str, **overrides: str) -> Style:
        color = self._resolve(role)
        s = Style(bgcolor=color, **{k: v for k, v in overrides.items() if v})  # type: ignore[arg-type]
        return s

    def styled_text(self, text: str, role: str = "text") -> Text:
        return Text(text, style=self.style(role))

    def _resolve(self, role: str) -> str:
        """Map a UI role to a hex color from the active palette."""
        p = self._palette
        mapping: dict[str, str] = {
            "bg": p.obsidian,
            "bg_recessed": p.dark_iron,
            "bg_elevated": p.elevated_iron,
            "text": p.ash_white,
            "text_secondary": p.muted_ash,
            "border": p.iron_border,
            "accent": p.primary_accent,
            "accent_deep": p.deep_accent,
            "accent_secondary": p.secondary_accent,
            "selected_bg": p.selected_bg,
            "hover_bg": p.hover_bg,
            "success": p.success,
            "warning": p.warning,
            "error": p.error,
            "disabled": p.disabled_text,
            "focus": p.focus_ring,
        }
        return mapping.get(role, p.ash_white)


# Module-level convenience: the default theme manager instance.
# The TUI app creates its own and passes it down; this exists so
# non-TUI code (tests, CLI) can use a theme without an app instance.
default_theme = ThemeManager()
