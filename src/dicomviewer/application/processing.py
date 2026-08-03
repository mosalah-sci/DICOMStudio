"""Application ports and data types for image processing.

Result types and the analyzer port keep the Presentation layer free of image
math. The processing pipeline is an ordered, non-destructive chain of stages;
future filters (for example AI-based ones) can be inserted at composition time
without modifying the renderers or the pipeline code.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from dicomviewer.application.viewing import PixelArray


@dataclass(frozen=True)
class PixelStatistics:
    """Summary statistics over the rescaled pixel values of a frame."""

    minimum: float
    maximum: float
    mean: float
    standard_deviation: float
    pixel_count: int


@dataclass(frozen=True)
class Histogram:
    """A fixed-bin histogram over the rescaled pixel values."""

    bin_count: int
    minimum: float
    maximum: float
    counts: tuple[int, ...]

    @property
    def bin_width(self) -> float:
        """Return the width of a single bin."""
        if self.bin_count <= 0:
            return 0.0
        return (self.maximum - self.minimum) / self.bin_count

    @property
    def edges(self) -> tuple[float, ...]:
        """Return the ``bin_count + 1`` boundary values of the bins."""
        return tuple(self.minimum + index * self.bin_width for index in range(self.bin_count + 1))


class ImageAnalyzer(Protocol):
    """Computes statistics and histograms from decoded frames."""

    def statistics(self, pixels: PixelArray) -> PixelStatistics:
        """Return summary statistics of the rescaled pixel values."""
        ...

    def histogram(self, pixels: PixelArray, bins: int = 256) -> Histogram:
        """Return a histogram of the rescaled pixel values using ``bins`` bins."""
        ...


class ProcessingStage(Protocol):
    """One transform in the non-destructive image processing chain."""

    name: str

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """Return a transformed copy of ``frame``; the input is never mutated."""
        ...


class ProcessingPipeline:
    """Applies an ordered sequence of processing stages.

    Each stage receives the previous stage's output and must return a new array.
    The pipeline never mutates its input, so the underlying pixels remain
    untouched (non-destructive image processing).
    """

    def __init__(self, stages: Sequence[ProcessingStage]) -> None:
        """Create a pipeline running ``stages`` in the given order."""
        self._stages = tuple(stages)

    @property
    def stages(self) -> tuple[ProcessingStage, ...]:
        """Return the configured stages in application order."""
        return self._stages

    def apply(self, frame: np.ndarray) -> np.ndarray:
        """Run every stage over ``frame`` and return the final result."""
        result = frame
        for stage in self._stages:
            result = stage.apply(result)
        return result
