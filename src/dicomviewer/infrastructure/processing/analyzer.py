"""NumPy image analyzer.

Computes pixel statistics and histograms from decoded frames using the same
pure-numpy pipeline stages as the renderer, so the analysis always reflects
the displayed (rescaled) values.
"""

from __future__ import annotations

import numpy as np

from dicomviewer.application.processing import Histogram, PixelStatistics
from dicomviewer.application.viewing import PixelArray
from dicomviewer.infrastructure.rendering import pipeline


class NumpyImageAnalyzer:
    """Computes statistics and histograms over rescaled pixel values."""

    def analyze(self, pixels: PixelArray, bins: int = 256) -> tuple[PixelStatistics, Histogram]:
        """Return statistics and a histogram computed from a single rescale.

        Rescaling the full frame once (instead of once per metric) roughly
        halves the per-slice analysis cost, which matters when scrolling a
        series with the statistics overlay visible.
        """
        rescaled = pipeline.rescale(pixels.pixels, pixels.rescale_slope, pixels.rescale_intercept)
        statistics = self._statistics_from(rescaled, pixels)
        histogram = self._histogram_from(rescaled, bins)
        return statistics, histogram

    def statistics(self, pixels: PixelArray) -> PixelStatistics:
        """Return summary statistics of the rescaled pixel values."""
        rescaled = pipeline.rescale(pixels.pixels, pixels.rescale_slope, pixels.rescale_intercept)
        return self._statistics_from(rescaled, pixels)

    def histogram(self, pixels: PixelArray, bins: int = 256) -> Histogram:
        """Return a histogram of the rescaled pixel values using ``bins`` bins."""
        rescaled = pipeline.rescale(pixels.pixels, pixels.rescale_slope, pixels.rescale_intercept)
        return self._histogram_from(rescaled, bins)

    def _statistics_from(self, rescaled: np.ndarray, pixels: PixelArray) -> PixelStatistics:
        """Compute summary statistics over an already-rescaled array."""
        return PixelStatistics(
            minimum=float(np.min(rescaled)),
            maximum=float(np.max(rescaled)),
            mean=float(np.mean(rescaled)),
            standard_deviation=float(np.std(rescaled)),
            pixel_count=int(pixels.width * pixels.height),
        )

    def _histogram_from(self, rescaled: np.ndarray, bins: int) -> Histogram:
        """Compute a histogram over an already-rescaled array.

        ``np.histogram`` sorts internally; binning via ``np.floor`` and
        ``np.bincount`` is linear and measurably faster for full-resolution
        frames while producing the same counts and edges for equal-width bins.
        """
        if bins <= 0:
            raise ValueError(f"Histogram bin count must be positive, got {bins}")
        minimum = float(np.min(rescaled))
        maximum = float(np.max(rescaled))
        span = maximum - minimum
        if span <= 0:
            counts = np.zeros(bins, dtype=np.int64)
            counts[0] = rescaled.size
        else:
            indices = np.floor((rescaled - minimum) * (bins / span)).astype(np.int64)
            np.clip(indices, 0, bins - 1, out=indices)
            counts = np.bincount(indices.ravel(), minlength=bins)
        edges = np.linspace(minimum, maximum, bins + 1)
        return Histogram(
            bin_count=bins,
            minimum=float(edges[0]),
            maximum=float(edges[-1]),
            counts=tuple(int(value) for value in counts),
        )
