"""Tests for the thumbnail loader."""

from __future__ import annotations

from pathlib import Path

from tests.dicom_utils import FakeThumbnailService
from tests.qt_utils import pump_until

from dicomviewer.domain.studies import Image
from dicomviewer.presentation.workers.thumbnail_loader import ThumbnailLoader


def test_loader_emits_generated_thumbnail(qapp) -> None:
    service = FakeThumbnailService()
    loader = ThumbnailLoader(service, max_threads=1)
    image = Image(path=Path("slice.dcm"), instance_number=1)
    received: list = []
    loader.thumbnail_ready.connect(lambda *args: received.append(args))

    loader.request("s1", image, 16)

    assert pump_until(qapp, lambda: len(received) == 1)
    series_uid, path, thumbnail = received[0]
    assert series_uid == "s1"
    assert path == image.path
    assert thumbnail.width == 2 and thumbnail.height == 2


def test_loader_skips_failed_generations(qapp) -> None:
    class FailingService:
        def generate(self, image, size):
            raise RuntimeError("boom")

    loader = ThumbnailLoader(FailingService(), max_threads=1)
    image = Image(path=Path("slice.dcm"), instance_number=1)
    received: list = []
    loader.thumbnail_ready.connect(received.append)
    loader.request("s1", image, 16)
    assert not pump_until(qapp, lambda: len(received) > 0, timeout=1.0)
