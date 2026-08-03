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

    def statistics(self, pixels: PixelArray) -> PixelStatistics:
        """Return summary statistics of the rescaled pixel values."""
        rescaled = pipeline.rescale(pixels.pixels, pixels.rescale_slope, pixels.rescale_intercept)
        return PixelStatistics(
            minimum=float(np.min(rescaled)),
            maximum=float(np.max(rescaled)),
            mean=float(np.mean(rescaled)),
            standard_deviation=float(np.std(rescaled)),
            pixel_count=int(rescaled.size),
        )

    def histogram(self, pixels: PixelArray, bins: int = 256) -> Histogram:
        """Return a histogram of the rescaled pixel values using ``bins`` bins."""
        rescaled = pipeline.rescale(pixels.pixels, pixels.rescale_slope, pixels.rescale_intercept)
        counts, edges = np.histogram(rescaled, bins=bins)
        return Histogram(
            bin_count=bins,
            minimum=float(edges[0]),
            maximum=float(edges[-1]),
            counts=tuple(int(value) for value in counts),
        )
