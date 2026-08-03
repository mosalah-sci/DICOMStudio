# DICOM Viewer Professional

A professional-grade DICOM medical image viewer for Microsoft Windows, built
with Python 3.13 and PySide6.

The project is developed incrementally against an approved roadmap
(`docs/`). Every milestone produces a stable, tagged, runnable application
built on a Clean Architecture foundation designed to evolve into a medical
imaging platform (PACS, MPR, 3D, AI-assisted analysis, and more).

## Status

Milestone 1 — Project Foundation (v0.1.0)

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
| Packaging   | uv / hatchling (PyInstaller at a later milestone)           |

## Quickstart

Prerequisites: [uv](https://docs.astral.sh/uv/) and Python 3.13.

```powershell
uv sync                              # create the environment and install deps
uv run python -m dicomviewer         # launch the application
```

Utility scripts (`scripts/`):

```powershell
.\scripts\dev.ps1        # sync the environment
.\scripts\run.ps1        # run the application
.\scripts\format.ps1     # format with Black
.\scripts\lint.ps1       # lint with Ruff
.\scripts\typecheck.ps1  # type check with Pyright
.\scripts\test.ps1       # run tests
.\scripts\build.ps1      # build distributions
```

Command line options:

```powershell
uv run python -m dicomviewer --version      # print version and exit
uv run python -m dicomviewer --smoke-test   # launch, auto-exit (CI smoke test)
```

## Repository Layout

```
src/dicomviewer/     application source (presentation / application / domain / infrastructure / shared)
tests/               unit, integration and smoke tests
docs/                project documentation and architecture decision records
config/              configuration reference material
resources/           runtime-bundled assets (icons, styles, application icon)
assets/              repository-only media (branding, screenshots)
scripts/             reproducible development workflows
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
