"""Unit tests for the tiered series-image ordering policy (v1.4 M2).

These pin the exact documented policy in ``domain.studies.sort_series_images``:

1. geometry tier — all images positioned+oriented with parallel normals;
   ordered by physical projection onto the slice normal;
2. SliceLocation tier — every image carries (0020,1041);
3. InstanceNumber tier — legacy stable behavior.

Partially-geometried series deliberately fall through to a later tier.
"""

from __future__ import annotations

from pathlib import Path

from dicomviewer.domain.studies import Image, sort_series_images

_AXIAL = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0)  # normal = +z


def _image(
    name: str,
    *,
    number: int = 1,
    position: tuple[float, float, float] | None = None,
    orientation: tuple[float, ...] | None = None,
    location: float | None = None,
) -> Image:
    return Image(
        path=Path(f"{name}.dcm"),
        instance_number=number,
        position=position,
        orientation=orientation,
        slice_location=location,
    )


def _names(images: tuple[Image, ...]) -> list[str]:
    return [image.path.stem for image in images]


def test_single_image_series_is_returned_directly() -> None:
    only = _image("only", position=(0.0, 0.0, 5.0), orientation=_AXIAL)
    assert sort_series_images([only]) == (only,)


def test_geometry_tier_orders_by_projection_onto_normal() -> None:
    images = [
        _image("mid", number=2, position=(0.0, 0.0, 5.0), orientation=_AXIAL),
        _image("first", number=1, position=(0.0, 0.0, 1.0), orientation=_AXIAL),
        _image("last", number=3, position=(0.0, 0.0, 9.0), orientation=_AXIAL),
    ]
    assert _names(sort_series_images(images)) == ["first", "mid", "last"]


def test_geometry_tier_ignores_instance_number_for_position() -> None:
    # Shuffled instance numbers must not override physical position order.
    images = [
        _image("z9", number=1, position=(0.0, 0.0, 9.0), orientation=_AXIAL),
        _image("z1", number=2, position=(0.0, 0.0, 1.0), orientation=_AXIAL),
        _image("z5", number=3, position=(0.0, 0.0, 5.0), orientation=_AXIAL),
    ]
    assert _names(sort_series_images(images)) == ["z1", "z5", "z9"]


def test_sagittal_orientation_projects_on_x_axis() -> None:
    sagittal = (0.0, 1.0, 0.0, 0.0, 0.0, 1.0)  # normal = +x
    images = [
        _image("x30", number=1, position=(30.0, 0.0, 0.0), orientation=sagittal),
        _image("x10", number=2, position=(10.0, 0.0, 0.0), orientation=sagittal),
    ]
    assert _names(sort_series_images(images)) == ["x10", "x30"]


def test_duplicate_positions_break_ties_by_instance_number() -> None:
    images = [
        _image("dup_b", number=7, position=(0.0, 0.0, 4.0), orientation=_AXIAL),
        _image("dup_a", number=3, position=(0.0, 0.0, 4.0), orientation=_AXIAL),
        _image("solo", number=1, position=(0.0, 0.0, 2.0), orientation=_AXIAL),
    ]
    assert _names(sort_series_images(images)) == ["solo", "dup_a", "dup_b"]


def test_partial_geometry_falls_back_to_instance_number() -> None:
    # One slice lacks geometry: the whole series uses the legacy tier so
    # positioned and unpositioned content is never interleaved by guesswork.
    images = [
        _image("geo", number=2, position=(0.0, 0.0, 9.0), orientation=_AXIAL),
        _image("nogeom", number=1),
    ]
    assert _names(sort_series_images(images)) == ["nogeom", "geo"]


def test_inconsistent_normals_fall_back_to_instance_number() -> None:
    axial = _AXIAL
    coronal = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0)  # normal = +y
    images = [
        _image("axial", number=2, position=(0.0, 0.0, 9.0), orientation=axial),
        _image("coronal", number=1, position=(0.0, 5.0, 0.0), orientation=coronal),
    ]
    assert _names(sort_series_images(images)) == ["coronal", "axial"]


def test_degenerate_orientation_falls_back_to_instance_number() -> None:
    degenerate = (0.0, 0.0, 0.0, 0.0, 1.0, 0.0)
    images = [
        _image("bad", number=2, position=(0.0, 0.0, 9.0), orientation=degenerate),
        _image("good_num", number=1),
    ]
    assert _names(sort_series_images(images)) == ["good_num", "bad"]


def test_slice_location_tier_applies_when_geometry_absent() -> None:
    images = [
        _image("loc50", number=2, location=50.0),
        _image("loc10", number=1, location=10.0),
        _image("loc25", number=3, location=25.0),
    ]
    assert _names(sort_series_images(images)) == ["loc10", "loc25", "loc50"]


def test_missing_instance_number_does_not_break_location_ordering() -> None:
    # Instance numbers were assigned at scan time; equal fallback numbers
    # keep location as the deciding key.
    images = [
        _image("b", number=1, location=20.0),
        _image("a", number=1, location=10.0),
    ]
    assert _names(sort_series_images(images)) == ["a", "b"]


def test_legacy_instance_number_tier_matches_previous_behavior() -> None:
    images = [
        _image("third", number=3),
        _image("first", number=1),
        _image("second", number=2),
        _image("tied", number=2),
    ]
    # Stable sort: ties keep discovery order ("second" before "tied").
    assert _names(sort_series_images(images)) == ["first", "second", "tied", "third"]
