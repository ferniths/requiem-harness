"""Themes package."""

from requiem.themes.emblem import emblem, emblem_ascii, emblem_line, header_block, supports_unicode, wordmark
from requiem.themes.manager import ThemeManager, default_theme
from requiem.themes.palettes import (
    ALL_THEMES,
    BLUE,
    CLASSIC,
    DEFAULT_THEME,
    GREY,
    MAGENTA,
    PURPLE,
    Palette,
    get_theme,
    list_theme_names,
)

__all__ = [
    "BLUE",
    "CLASSIC",
    "DEFAULT_THEME",
    "GREY",
    "MAGENTA",
    "PURPLE",
    "ALL_THEMES",
    "Palette",
    "ThemeManager",
    "default_theme",
    "emblem",
    "emblem_ascii",
    "emblem_line",
    "get_theme",
    "header_block",
    "list_theme_names",
    "supports_unicode",
    "wordmark",
]
