"""Performance benchmark for the image rendering, analysis and thumbnail paths.

Measures the wall-clock cost of the core per-frame operations on a
realistic 512x512 16-bit grayscale frame. Run with:

    uv run python scripts/benchmark.py

The numbers are used to verify that the milestone 10 optimizations keep
interactive rendering fast; there are no hard CI thresholds because timing
varies across machines, but the suite is useful before/after a change.
"""

from __future__ import annotations

import time

import numpy as np

from dicomviewer.application.viewing import PixelArray
from dicomviewer.domain.viewport import Viewport
from dicomviewer.infrastructure.processing.analyzer import NumpyImageAnalyzer
from dicomviewer.infrastructure.rendering.renderer import NumpyViewRenderer

_SIZE = 512
_PIXELS = np.random.default_rng(42).integers(0, 4096, (_SIZE, _SIZE)).astype(np.uint16)


def _pixel_array() -> PixelArray:
    return PixelArray(
        pixels=_PIXELS,
        width=_SIZE,
        height=_SIZE,
        rescale_slope=1.0,
        rescale_intercept=-1024.0,
    )


def _bench(label: str, fn, samples: int = 20) -> None:
    fn()
    start = time.perf_counter()
    for _ in range(samples):
        fn()
    elapsed = (time.perf_counter() - start) / samples * 1000.0
    print(f"  {label:<48} {elapsed:8.3f} ms")


def main() -> None:
    """Run the benchmark suite and print per-operation timings."""
    print(f"Benchmark on {_SIZE}x{_SIZE} uint16 grayscale:")
    renderer = NumpyViewRenderer()
    analyzer = NumpyImageAnalyzer()
    pixels = _pixel_array()

    _bench("render (auto window)", lambda: renderer.render(pixels, Viewport.initial()))
    _bench(
        "render (explicit window)",
        lambda: renderer.render(pixels, Viewport.initial().with_window(40.0, 400.0)),
    )
    _bench("analyzer statistics", lambda: analyzer.statistics(pixels))
    _bench("analyzer histogram (128 bins)", lambda: analyzer.histogram(pixels, bins=128))
    _bench("analyzer analyze (stats+histogram)", lambda: analyzer.analyze(pixels, bins=128))
    _bench(
        "thumbnail downscale 512->64",
        lambda: _thumbnail_downscale(_PIXELS, 64),
        samples=100,
    )


def _thumbnail_downscale(array: np.ndarray, size: int) -> np.ndarray:
    """Mirror the thumbnail service path: sample first, then normalize."""
    height, width = array.shape
    scale = size / max(height, width)
    new_height = max(1, round(height * scale))
    new_width = max(1, round(width * scale))
    row_indices = (np.arange(new_height) * height / new_height).astype(np.int64)
    col_indices = (np.arange(new_width) * width / new_width).astype(np.int64)
    sampled = array[row_indices][:, col_indices]
    rescaled = sampled.astype(np.float64) * 1.0 + -1024.0
    low, high = np.percentile(rescaled, (1.0, 99.0))
    normalized = np.clip((rescaled - low) / (high - low), 0.0, 1.0)
    return (normalized * 255.0).round().astype(np.uint8)


if __name__ == "__main__":
    main()
