# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and
this project adheres to [Semantic Versioning](https://semver.org/).

## [0.7.0] - 2026-08-04

### Added

- Measurement Tools:
  - Distance measurements: click two points on the image to record the
    length; the label shows millimetres when DICOM Pixel Spacing is available
    and falls back to pixels otherwise.
  - Angle measurements: click three points (vertex and one point on each ray)
    to record the smaller angle in degrees.
  - Overlay rendering: completed measurements and the in-progress draft are
    drawn on the viewer in image pixel coordinates, so they stay synchronized
    with pan, zoom, fit mode and window/level changes.
  - Measurement editing: an active draft rubber-bands with the pointer and is
    cancelled with a right-click; a measurement can be removed from the
    current slice; Clear Measurements removes every measurement from every
    slice.
  - Per-slice measurement storage: measurements are tied to the slice on which
    they were drawn and survive navigating away and back.
  - The Tools > Measure action (and toolbar ruler button) toggles the
    measurement tool; a visible hint appears while measuring and Esc exits.
  - Pixel Spacing is read from each DICOM header and carried on the decoded
    pixel array, defaulting to identity spacing when absent or malformed.
  - Pure domain geometry (distance, angle, pixel-spacing scaling) and an
    application-level measurement collection keep all math out of the GUI.
  - Application version bumped to 0.7.0.

## [0.6.0] - 2026-08-04

### Added

- Metadata Explorer:
  - Metadata panel now inspects the DICOM metadata of the displayed image
    and updates automatically when the slice changes.
  - Grouped presentation: elements are classified into logical groups
    (Patient, Study, Series, Image, Acquisition, Image Pixel, Equipment,
    General, File Meta, Other) and ordered in a readable tree.
  - Live search box that filters elements by keyword, display name, group,
    tag or value, with an explicit no-matches state.
  - Bulk Expand all / Collapse all controls.
  - Context menu actions to copy the DICOM tag (for example `(0010,0010)`)
    or the element value to the system clipboard.
  - Bounded per-image metadata cache so browsing a large series reads each
    header at most once.
  - Header-only extraction (never loads pixel data) with private and empty
    elements omitted and binary values size-bounded for readability.
  - Metadata service wired behind an application port; the metadata panel
    resets when a new scan starts.
  - Application version bumped to 0.6.0.

## [0.5.0] - 2026-08-04

### Added

- Diagnostic Image Processing:
  - Clinical window presets (CT Brain, Stroke, Bone, Lung, Abdomen,
    Mediastinum, Soft Tissue, Temporal Bones) with a Window Presets submenu;
    presets apply instantly and are disabled until a series is loaded.
  - Pixel statistics (minimum, maximum, mean, standard deviation, count)
    computed over rescaled values and shown in the viewer overlay.
  - Fixed-bin histogram calculation with live mini histogram rendering in the
    viewer corner.
  - Non-destructive image processing pipeline abstraction: ordered, composable
    stages that never mutate the source pixels, designed so future filters
    (for example AI-based) plug in at composition time without renderer
    changes.
  - Numpy image analyzer service behind an application port (`ImageAnalyzer`)
    so the Presentation layer performs no image math.
  - Bounded per-slice render cache reusing RGBA frames for unchanged
    window/level state, reducing repeated work while interacting.
  - VOI LUT / window-level pipeline extended and formalized; rescale,
    MONOCHROME1/2 inversion and automatic window behaviour preserved from
    Milestone 4.
  - Application version bumped to 0.5.0.

## [0.4.0] - 2026-08-04

### Added

- Medical Image Viewer Core:
  - Full-resolution DICOM pixel decoding with metadata (rescale, window and
    photometric interpretation) behind an application port.
  - Modular numpy rendering pipeline: rescale slope/intercept, VOI LUT /
    window level, normalization, MONOCHROME1 inversion and RGBA conversion.
  - High-quality grayscale rendering with smooth, aspect-preserving scaling
    and an RGBA buffer that is reused across zoom and pan changes.
  - Color frame support (RGB) with automatic channel normalization; genuinely
    unsupported pixel formats are reported gracefully instead of crashing.
  - Window / Level interaction: right-mouse drag adjusts window width and
    level against a concrete baseline; window/level resets to automatic.
  - Fit to Window, Actual Size (100%), Zoom In / Out (toolbar, `+`/`-` keys
    and Ctrl/Shift + mouse wheel).
  - Pan by left-mouse drag with pixel-accurate image-space offsets.
  - Slice navigation via mouse wheel and keyboard (arrows, Page Up/Down,
    Home/End) with clamped bounds and a bounded decode cache.
  - Double-clicking a series or image in the Study Explorer opens it in the
    viewer; view actions enable only when content is loaded.
  - Viewport state model in the Domain layer with zoom, pan, window/level and
    slice clamping rules that are unit-tested without Qt.
  - Status bar feedback for zoom and window/level changes.
  - Application version bumped to 0.4.0.

## [0.3.0] - 2026-08-03

### Added

- DICOM Discovery & Loading:
  - Open Folder action (Ctrl+O) with a native folder picker.
  - Background study scanning on a worker thread so large folders do not
    freeze the interface; a newer scan cancels the previous one.
  - Recursive folder scanning with header-only DICOM parsing for speed.
  - DICOM validation: malformed, unreadable or unrelated files are ignored
    gracefully and counted in the status report.
  - Metadata parsing and grouping into the Patient / Study / Series / Image
    hierarchy (patient, study and series UIDs with sensible fallbacks).
  - Study tree in the Study Explorer with modality, image counts, study dates
    and descriptive tooltips.
  - Lazy thumbnail generation: thumbnails render in a bounded thread pool when
    a series is expanded, preserving responsiveness.
  - Busy, empty and no-results states for the Study Explorer.
  - Domain study-catalog model and application ports (`StudyScanner`,
    `ThumbnailService`) backed by pydicom and numpy in Infrastructure.
  - Application version bumped to 0.3.0.

## [0.2.0] - 2026-08-03

### Added

- Application Shell:
  - Main window with a three-panel dock workspace: Study Explorer, Image
    Viewer and Metadata panels around a central viewer area.
  - Menu bar (File, View, Tools, Window, Help) with menu entries, shortcuts
    and status tips.
  - Toolbar with a single consistent theme-aware icon set.
  - Status bar with contextual messages and permanent theme/version labels.
  - Dock system supporting dock, undock, resize, hide/show toggles,
    fullscreen mode and restore-default-layout.
  - Theme system (dark default and light) with tokenized palette, stylesheet
    and SVG icon tinting.
  - Theme switching: `--theme` command-line override and live switching from
    the Settings dialog.
  - Settings dialog (appearance settings with immediate apply) and About
    dialog.
  - Window state persistence: geometry and dock layout survive restarts;
    corrupt state files are handled safely.
  - SVG icon system: 17 bundled line icons shipped inside the package and
    tinted to the active theme.
  - Action catalog: declarative command/action registry that fails fast and
    communicates future capability through disabled actions.
  - Keyboard shortcuts for all primary actions (open, view, layout, theme,
    fullscreen, settings, exit, ...).
  - Empty-state UI for all panels and a user-facing error presentation
    framework.
  - Settings model relocated to the Domain layer; application ports
    (`SettingsStore`, `WindowStateStore`) introduced.

### Changed

- Settings model (`Settings`, `AppearanceSettings`, `LoggingSettings`) moved from
  Infrastructure to Domain so Presentation depends only on Application ports.
- Application version bumped to 0.2.0.

## [0.1.0] - 2026-08-03

### Added

- Project foundation:
  - Repository structure (src-layout, tests, docs, config, resources, assets, scripts).
  - Dependency management with `uv` and a committed lockfile.
  - `pyproject.toml` as the single configuration source (Black, Ruff, Pyright, pytest, hatchling).
  - Typed TOML-based configuration system with bundled defaults and user overrides.
  - Loguru-based logging to console and rotating files.
  - Composition root and application entry points (`dicomviewer`, `python -m dicomviewer`).
  - Minimal main window with an informative empty state.
  - Unit, integration and smoke tests.
  - CI-ready workflow for Windows.
  - Architecture Decision Records (docs/architecture).
