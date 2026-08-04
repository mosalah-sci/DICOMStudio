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


def test_analyze_combines_statistics_and_histogram() -> None:
    pixels = PixelArray(
        pixels=np.array([[0, 1], [2, 3]], dtype=np.uint16),
        width=2,
        height=2,
        rescale_slope=2.0,
        rescale_intercept=-1.0,
    )
    analyzer = NumpyImageAnalyzer()
    statistics, histogram = analyzer.analyze(pixels, bins=8)
    assert statistics == analyzer.statistics(pixels)
    assert histogram == analyzer.histogram(pixels, bins=8)


def test_analyze_preserves_pixel_count_with_rescale() -> None:
    pixels = PixelArray(
        pixels=np.arange(16, dtype=np.uint16).reshape(4, 4),
        width=4,
        height=4,
        rescale_slope=0.5,
        rescale_intercept=1.0,
    )
    statistics, _histogram = NumpyImageAnalyzer().analyze(pixels, bins=8)
    assert statistics.pixel_count == 16
    assert statistics.minimum == 1.0
    assert statistics.maximum == 8.5


def test_analyze_histogram_matches_numpy_reference() -> None:
    rng = np.random.default_rng(11)
    grid = rng.integers(0, 2048, (64, 64)).astype(np.uint16)
    pixels = PixelArray(
        pixels=grid,
        width=64,
        height=64,
        rescale_slope=2.0,
        rescale_intercept=-64.0,
    )
    _statistics, histogram = NumpyImageAnalyzer().analyze(pixels, bins=64)
    rescaled = grid.astype(np.float64) * 2.0 - 64.0
    counts, edges = np.histogram(rescaled, bins=64)
    assert sum(histogram.counts) == 64 * 64
    assert histogram.counts == tuple(int(value) for value in counts)
    np.testing.assert_allclose(histogram.edges, edges)
