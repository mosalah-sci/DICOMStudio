# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/), and
this project adheres to [Semantic Versioning](https://semver.org/).

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
