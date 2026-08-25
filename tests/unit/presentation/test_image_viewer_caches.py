"""Focused characterization for ImageViewerWidget cache policies.

Complements the existing coverage in ``test_image_viewer.py`` (decode/analysis
bounds, per-slice analysis memoization, frame reuse across zoom, W/L-keyed
eviction, ``set_max_cache`` shrink). These two tests pin the remaining
policies examined during the R1.6 cache investigation:

- a failed decode is NOT cached: the widget retries on the next request, so
  a transient read failure never becomes permanently sticky;
- the frame cache evicts in pure FIFO order of insertion (oldest entry
  first, regardless of reuse), which is why revisiting the oldest
  window/slice state triggers exactly one re-render.
"""

from __future__ import annotations

from pathlib import Path

from tests.dicom_utils import FakeImageAnalyzer, FakeViewRenderer

from dicomviewer.application.viewing import PixelArray, UnsupportedPixelFormatError
from dicomviewer.domain.studies import Image
from dicomviewer.presentation.widgets.image_viewer import ImageViewerWidget


def _series(count: int) -> tuple[Image, ...]:
    return tuple(Image(Path(f"slice{i}.dcm"), i + 1) for i in range(count))


class _FlakyDecoder:
    """PixelDecoder double failing for a configured number of attempts."""

    def __init__(self, failures_remaining: int) -> None:
        self.failures_remaining = failures_remaining
        self.decoded: list[Image] = []
        self.error = UnsupportedPixelFormatError("transient read failure")

    def decode(self, image: Image) -> PixelArray:
        self.decoded.append(image)
        if self.failures_remaining > 0:
            self.failures_remaining -= 1
            raise self.error
        return PixelArray(pixels=None, width=8, height=6)  # type: ignore[arg-type]


def test_failed_decode_is_not_cached_and_retries(qapp) -> None:
    del qapp
    decoder = _FlakyDecoder(failures_remaining=1)
    viewer = ImageViewerWidget(
        None,
        decoder,
        FakeViewRenderer(),
        analyzer=FakeImageAnalyzer(),
    )
    viewer.load_series(_series(count=2))

    assert viewer._qimage is None
    assert viewer._last_error == "This image could not be decoded."

    # Navigating to the next slice decodes it successfully...
    viewer.set_slice(1)
    assert len(decoder.decoded) == 2
    assert viewer._last_error is None

    # ...and returning to the failed slice retries the decode (the failure
    # was not cached), now succeeding and caching the pixels.
    viewer.set_slice(0)
    assert len(decoder.decoded) == 3
    assert viewer._last_error is None
    assert viewer._qimage is not None
    assert 0 in viewer._cache


class _PassThroughDecoder:
    """Minimal PixelDecoder double handing out tiny placeholder frames."""

    def decode(self, image: Image) -> PixelArray:
        return PixelArray(pixels=None, width=8, height=6)  # type: ignore[arg-type]


def test_frame_cache_evicts_in_fifo_order(qapp) -> None:
    renderer = FakeViewRenderer()
    viewer = ImageViewerWidget(
        None,
        _PassThroughDecoder(),
        renderer,
        analyzer=FakeImageAnalyzer(),
    )
    viewer.load_series(_series(count=3))

    # Two slices rendered; returning to the first reuses its cached frame.
    viewer.set_slice(1)
    assert len(renderer.calls) == 2
    viewer.set_slice(0)
    assert len(renderer.calls) == 2

    # A third distinct frame arrives: capacity is 2, so the OLDEST entry
    # (slice 0) is dropped — even though it was reused most recently,
    # proving pure insertion-order eviction rather than LRU.
    viewer.set_slice(2)
    assert len(renderer.calls) == 3

    # Slice 0 was dropped, so returning to it re-renders (and evicts slice
    # 1); slice 1 therefore also misses on the next visit.
    viewer.set_slice(0)
    assert len(renderer.calls) == 4
    viewer.set_slice(1)
    assert len(renderer.calls) == 5
