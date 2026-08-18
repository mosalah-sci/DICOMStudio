"""Tests for the icon provider."""

from __future__ import annotations

from dicomviewer.presentation.theme.icon_provider import IconProvider


def test_icon_returns_a_non_null_icon(icon_provider: IconProvider) -> None:
    assert not icon_provider.icon("folder").isNull()


def test_icon_results_are_cached(icon_provider: IconProvider) -> None:
    assert icon_provider.icon("folder") is icon_provider.icon("folder")


def test_color_change_invalidates_the_cache(icon_provider: IconProvider) -> None:
    before = icon_provider.icon("folder")
    icon_provider.set_color("#000000")
    after = icon_provider.icon("folder")
    assert after is not before


def test_missing_icon_degrades_gracefully(icon_provider: IconProvider) -> None:
    assert icon_provider.icon("does-not-exist").isNull()


def test_brand_icon_returns_a_non_null_multi_resolution_icon(
    icon_provider: IconProvider,
) -> None:
    icon = icon_provider.brand_icon()
    assert not icon.isNull()
    assert len(icon.availableSizes()) >= 5


def test_brand_icon_is_cached(icon_provider: IconProvider) -> None:
    assert icon_provider.brand_icon() is icon_provider.brand_icon()
