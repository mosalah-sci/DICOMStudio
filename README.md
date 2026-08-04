# DICOM Viewer Professional

A professional-grade DICOM medical image viewer for Microsoft Windows, built
with Python 3.13 and PySide6.

The project is developed incrementally against an approved roadmap
(`docs/`). Every milestone produces a stable, tagged, runnable application
built on a Clean Architecture foundation designed to evolve into a medical
imaging platform (PACS, MPR, 3D, AI-assisted analysis, and more).

## Status

Milestone 11 — Packaging and Distribution (v0.11.0)

## Technology Stack

| Concern     | Tooling                                                      |
| ----------- | ----------------------------------------------------------- |
| Language    | Python 3.13                                                  |
| GUI         | PySide6 (Qt 6)                                               |
| DICOM       | pydicom                                                     |
| Imaging     | NumPy (SimpleITK / OpenCV added when they add real value)   |
| Logging     | Loguru                                                      |
| Config      | TOML (tomlkit)                                              |
| Testing     | pytest                                                      |
| Formatting  | Black                                                       |
| Linting     | Ruff                                                        |
| Typing      | Pyright (strict)                                            |
| Packaging   | uv / hatchling, PyInstaller, Inno Setup                      |

## Quickstart

Prerequisites: [uv](https://docs.astral.sh/uv/) and Python 3.13.

```powershell
uv sync                              # create the environment and install deps
uv run python -m dicomviewer         # launch the application
```

Utility scripts (`scripts/`):

```powershell
.\scripts\dev.ps1            # sync the environment
.\scripts\run.ps1            # run the application
.\scripts\format.ps1         # format with Black
.\scripts\lint.ps1           # lint with Ruff
.\scripts\typecheck.ps1      # type check with Pyright
.\scripts\test.ps1           # run tests
.\scripts\build.ps1          # build Python distributions (wheel + sdist)
.\scripts\build_standalone.ps1  # build the standalone Windows application
.\scripts\build_portable.ps1    # build the portable zip archive
.\scripts\release.ps1        # full release: tests, standalone, installer, portable
```

Command line options:

```powershell
uv run python -m dicomviewer --version      # print version and exit
uv run python -m dicomviewer --smoke-test   # launch, auto-exit (CI smoke test)
uv run python -m dicomviewer <folder>       # open a folder of DICOM studies
uv run python -m dicomviewer <file.dcm>     # open a DICOM file's folder
```

## Distribution

Windows end users can install the app with the Inno Setup installer
(`dist/installer/DicomViewer-Professional-<version>-Setup.exe`), use it as a
portable app (extract
`dist/DicomViewer-Professional-<version>-Portable.zip`), or run the standalone
folder in `dist/DicomViewer/`. No Python is required. See
`docs/build.md` for the release process and `docs/user/README.md` for the
installation guide.

## Repository Layout

```
src/dicomviewer/     application source (presentation / application / domain / infrastructure / shared)
tests/               unit, integration and smoke tests
docs/                project documentation and architecture decision records
config/              configuration reference material
resources/           runtime-bundled assets (icons, styles, application icon)
assets/              repository-only media (branding, screenshots)
packaging/           Windows packaging (PyInstaller spec, Inno Setup script, icon)
scripts/             reproducible development and release workflows
```

## Architecture

Four-layer Clean Architecture with strict inward dependency direction:

```
Presentation → Application → Domain ← Infrastructure
```

- **Presentation** — Qt windows, widgets, dialogs and view models.
- **Application** — use cases, workflows and coordination (framework-free).
- **Domain** — business rules, entities and exceptions (framework-free).
- **Infrastructure** — adapters for pydicom, tomlkit, loguru, filesystem.

Dependencies are injected through a single composition root in
`src/dicomviewer/main.py`. No layer crosses architectural boundaries.

## Documentation

- `PROJECT_CONSTITUTION.md` — mission, goals and non-negotiable rules.
- `IMPLEMENTATION_ROADMAP.md` — the twelve milestones and release strategy.
- `CODING_STANDARDS.md` — mandatory coding conventions.
- `UI_BLUEPRINT.md` — user interface design specification.
- `AI_DEVELOPMENT_RULES.md` — implementation rules for AI contributors.
- `MILESTONE_PROMPT_FRAMEWORK.md` — milestone prompt structure.
- `docs/architecture/` — Architecture Decision Records (ADRs).

## License

MIT — see [LICENSE](LICENSE).
