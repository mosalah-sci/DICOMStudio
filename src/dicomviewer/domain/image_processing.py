"""Clinical window presets for diagnostic display.

Window presets are domain business rules: clinically standard (center, width)
combinations that radiologists apply to grayscale studies. Keeping them in the
Domain layer lets the values be unit-tested and reused without any GUI or DICOM
dependency.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WindowPreset:
    """A named (center, width) window used for diagnostic display."""

    name: str
    center: float
    width: float


WINDOW_PRESETS: tuple[WindowPreset, ...] = (
    WindowPreset("CT Brain", 40.0, 80.0),
    WindowPreset("CT Stroke", 40.0, 40.0),
    WindowPreset("CT Bone", 300.0, 1800.0),
    WindowPreset("CT Lung", -500.0, 1500.0),
    WindowPreset("CT Abdomen", 60.0, 400.0),
    WindowPreset("CT Mediastinum", 50.0, 350.0),
    WindowPreset("CT Soft Tissue", 40.0, 400.0),
    WindowPreset("CT Temporal Bones", 600.0, 3000.0),
)


def find_window_preset(name: str) -> WindowPreset | None:
    """Return the preset whose name matches ``name``, or ``None``."""
    for preset in WINDOW_PRESETS:
        if preset.name == name:
            return preset
    return None
