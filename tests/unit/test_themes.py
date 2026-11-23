"""Unit tests for the theme system."""

from __future__ import annotations

from requiem.themes.emblem import emblem, emblem_ascii, wordmark
from requiem.themes.manager import ThemeManager
from requiem.themes.palettes import ALL_THEMES, CLASSIC, get_theme, list_theme_names


class TestPalettes:
    def test_all_five_themes_present(self):
        assert len(ALL_THEMES) == 5
        names = set(ALL_THEMES.keys())
        assert names == {"classic", "blue", "purple", "magenta", "grey"}

    def test_classic_colors_exact(self):
        p = CLASSIC
        assert p.obsidian == "#0C0A0B"
        assert p.dark_iron == "#171316"
        assert p.primary_accent == "#C02645"
        assert p.deep_accent == "#81172F"
        assert p.secondary_accent == "#D4AF72"
        assert p.ash_white == "#E8E1E5"
        assert p.muted_ash == "#82777D"
        assert p.iron_border == "#2A242D"
        assert p.elevated_iron == "#1B171F"

    def test_alternative_themes_share_base(self):
        for name, palette in ALL_THEMES.items():
            assert palette.obsidian == CLASSIC.obsidian, f"{name}: obsidian mismatch"
            assert palette.dark_iron == CLASSIC.dark_iron, f"{name}: dark_iron mismatch"
            assert palette.ash_white == CLASSIC.ash_white, f"{name}: ash_white mismatch"
            assert palette.muted_ash == CLASSIC.muted_ash, f"{name}: muted_ash mismatch"
            assert palette.iron_border == CLASSIC.iron_border, f"{name}: iron_border mismatch"
            assert palette.elevated_iron == CLASSIC.elevated_iron, f"{name}: elevated_iron mismatch"

    def test_alternative_themes_differ_in_accent(self):
        accents = {name: p.primary_accent for name, p in ALL_THEMES.items()}
        assert len(set(accents.values())) == 5

    def test_get_theme_fallback(self):
        assert get_theme("nonexistent") is CLASSIC

    def test_list_theme_names_sorted(self):
        names = list_theme_names()
        assert names == sorted(names)
        assert len(names) == 5


class TestThemeManager:
    def test_default_theme_is_classic(self):
        tm = ThemeManager()
        assert tm.name == "classic"
        assert tm.palette is CLASSIC

    def test_switch_theme(self):
        tm = ThemeManager("classic")
        tm.set_theme("blue")
        assert tm.name == "blue"
        assert tm.palette.primary_accent == ALL_THEMES["blue"].primary_accent

    def test_cycle_theme(self):
        tm = ThemeManager("classic")
        tm.cycle_theme(1)
        names = list(ALL_THEMES.keys())
        idx = names.index("classic")
        assert tm.name == names[(idx + 1) % len(names)]

    def test_style_resolves_roles(self):
        tm = ThemeManager("classic")
        style = tm.style("accent")
        assert style is not None


class TestEmblem:
    def test_emblem_returns_six_lines(self):
        lines = emblem(6)
        assert len(lines) == 6
        assert any("R" in line for line in lines)

    def test_emblem_crops_top(self):
        lines = emblem(3)
        assert len(lines) == 3

    def test_emblem_ascii(self):
        lines = emblem_ascii(5)
        assert len(lines) == 5
        assert all(line.isascii() for line in lines)

    def test_wordmark(self):
        assert wordmark(spaced=True) == "R  E  Q  U  I  E  M"
