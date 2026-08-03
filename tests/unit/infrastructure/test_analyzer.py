"""Tests for the numpy image analyzer (statistics and histograms)."""

from __future__ import annotations

import numpy as np

from dicomviewer.application.viewing import PixelArray
from dicomviewer.infrastructure.processing.analyzer import NumpyImageAnalyzer


def _frame() -> PixelArray:
    grid = np.array([[0, 1], [2, 3]], dtype=np.uint16)
    return PixelArray(pixels=grid, width=2, height=2)


def test_statistics_match_expected_values() -> None:
    analyzer = NumpyImageAnalyzer()
    stats = analyzer.statistics(_frame())
    assert stats.minimum == 0.0
    assert stats.maximum == 3.0
    assert stats.mean == 1.5
    assert stats.pixel_count == 4
    np.testing.assert_allclose(stats.standard_deviation, np.std([0, 1, 2, 3]))


def test_statistics_apply_rescale() -> None:
    pixels = PixelArray(
        pixels=np.array([[0, 1], [2, 3]], dtype=np.uint16),
        width=2,
        height=2,
        rescale_slope=2.0,
        rescale_intercept=-1.0,
    )
    stats = NumpyImageAnalyzer().statistics(pixels)
    assert stats.minimum == -1.0
    assert stats.maximum == 5.0
    assert stats.mean == 2.0


def test_histogram_counts_and_range() -> None:
    analyzer = NumpyImageAnalyzer()
    histogram = analyzer.histogram(_frame(), bins=4)
    assert histogram.bin_count == 4
    assert histogram.minimum == 0.0
    assert histogram.maximum == 3.0
    assert sum(histogram.counts) == 4
    assert len(histogram.edges) == 5


def test_histogram_counts_single_bin_for_constant_frame() -> None:
    pixels = PixelArray(pixels=np.full((2, 2), 7, dtype=np.uint16), width=2, height=2)
    histogram = NumpyImageAnalyzer().histogram(pixels, bins=8)
    assert sum(histogram.counts) == 4
    assert histogram.minimum <= 7.0 <= histogram.maximum


def test_histogram_bin_counts_distribution() -> None:
    values = np.array([0, 1, 2, 3, 4, 5, 6, 7], dtype=np.uint16).reshape(2, 4)
    pixels = PixelArray(pixels=values, width=4, height=2)
    histogram = NumpyImageAnalyzer().histogram(pixels, bins=8)
    assert histogram.counts == tuple(1 for _ in range(8))
