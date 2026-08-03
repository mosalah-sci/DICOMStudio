"""Application ports and state for measurements.

The presentation tool collects points and hands completed measurements to a
:class:`MeasurementCollection`, which stores them per slice and renders their
labels. Only the domain measurement model and plain data types are used here,
so both the state and the label text stay free of GUI logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dicomviewer.application.viewing import PixelArray
from dicomviewer.domain.measurement import (
    Measurement,
    MeasurementKind,
    distance_pixels,
    distance_with_spacing,
)


@dataclass
class MeasurementCollection:
    """Per-slice measurement storage with label rendering.

    ``pixel_array`` carries the pixel spacing used to compute physical
    distances; it is only needed for text, never for the point positions.
    """

    pixel_array: PixelArray | None = None
    _entries: dict[int, list[Measurement]] = field(default_factory=dict[int, list[Measurement]])

    def add(self, slice_index: int, measurement: Measurement) -> None:
        """Append a measurement to ``slice_index``."""
        self._entries.setdefault(slice_index, []).append(measurement)

    def remove(self, slice_index: int, measurement: Measurement) -> bool:
        """Remove an exact measurement; return whether it was found."""
        entries = self._entries.get(slice_index, [])
        try:
            entries.remove(measurement)
        except ValueError:
            return False
        return True

    def clear(self, slice_index: int) -> None:
        """Remove all measurements from ``slice_index``."""
        self._entries.pop(slice_index, None)

    def clear_all(self) -> None:
        """Remove every measurement from every slice."""
        self._entries.clear()

    def for_slice(self, slice_index: int) -> list[Measurement]:
        """Return the measurements stored for ``slice_index``."""
        return list(self._entries.get(slice_index, []))

    def has_any(self) -> bool:
        """Return whether any measurement exists on any slice."""
        return any(self._entries.values())

    def counts(self) -> dict[int, int]:
        """Return the number of measurements per slice index."""
        return {index: len(entries) for index, entries in self._entries.items()}


def measurement_label(
    measurement: Measurement,
    pixel_array: PixelArray | None,
) -> str:
    """Return the human-readable label for ``measurement``.

    Distances use the pixel spacing when the array provides one, otherwise
    they fall back to plain pixels. Angles are always reported in degrees.
    """
    if measurement.kind is MeasurementKind.DISTANCE:
        return _distance_label(measurement, pixel_array)
    return _angle_label(measurement)


def _distance_label(measurement: Measurement, pixel_array: PixelArray | None) -> str:
    pixels = distance_pixels(measurement)
    if pixel_array is not None:
        spacing = pixel_array.pixel_spacing
        millimetres = distance_with_spacing(measurement, spacing[0], spacing[1])
        return f"{millimetres:.2f} mm  ({pixels:.2f} px)"
    return f"{pixels:.2f} px"


def _angle_label(measurement: Measurement) -> str:
    from dicomviewer.domain.measurement import angle_degrees

    return f"{angle_degrees(measurement):.1f}°"
