"""Tests for image processing result types and the processing pipeline."""

from __future__ import annotations

import numpy as np

from dicomviewer.application.processing import Histogram, ProcessingPipeline


class _OffsetStage:
    """A minimal processing stage that adds a constant to each value."""

    name = "offset"

    def __init__(self, amount: float) -> None:
        self.amount = amount
        self.calls = 0

    def apply(self, frame: np.ndarray) -> np.ndarray:
        self.calls += 1
        return frame + self.amount


def test_histogram_bin_width_and_edges() -> None:
    histogram = Histogram(bin_count=4, minimum=0.0, maximum=8.0, counts=(1, 1, 1, 1))
    assert histogram.bin_width == 2.0
    assert histogram.edges == (0.0, 2.0, 4.0, 6.0, 8.0)


def test_histogram_single_bin_covers_the_full_range() -> None:
    histogram = Histogram(bin_count=1, minimum=0.0, maximum=8.0, counts=(9,))
    assert histogram.bin_width == 8.0
    assert histogram.edges == (0.0, 8.0)


def test_pipeline_with_no_stages_is_identity() -> None:
    frame = np.arange(6, dtype=np.float32).reshape(2, 3)
    result = ProcessingPipeline(()).apply(frame)
    np.testing.assert_array_equal(result, frame)


def test_pipeline_applies_stages_in_order() -> None:
    first = _OffsetStage(1.0)
    second = _OffsetStage(10.0)
    pipeline = ProcessingPipeline((first, second))
    frame = np.zeros((2, 2), dtype=np.float32)
    result = pipeline.apply(frame)
    np.testing.assert_allclose(result, 11.0)
    assert first.calls == 1
    assert second.calls == 1


def test_pipeline_does_not_mutate_the_input() -> None:
    pipeline = ProcessingPipeline((_OffsetStage(5.0),))
    frame = np.arange(9, dtype=np.float32).reshape(3, 3)
    original = frame.copy()
    pipeline.apply(frame)
    np.testing.assert_array_equal(frame, original)


def test_pipeline_exposes_its_stages() -> None:
    stage = _OffsetStage(1.0)
    pipeline = ProcessingPipeline((stage,))
    assert pipeline.stages == (stage,)
