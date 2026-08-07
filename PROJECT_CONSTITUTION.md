DICOMStudio
Project Constitution
Version

1.0

Status

Approved

1. Mission

The mission of this project is to build a professional-grade DICOM Viewer for Microsoft Windows that follows modern software engineering practices and provides a clean, fast, reliable, and extensible platform for medical image visualization.

The application is not intended to be a simple image viewer. It is the foundation of a future medical imaging platform that can evolve to support advanced capabilities such as PACS integration, 3D visualization, AI-assisted analysis, radiotherapy planning, and medical research workflows.

Every design and implementation decision must support this long-term vision.

2. Core Goals

The project must satisfy the following goals:

Professional software architecture.
High-performance desktop application.
Clean and intuitive user experience.
Accurate DICOM image visualization.
Lightweight memory footprint.
Maintainable source code.
Modular project structure.
Future-proof architecture.
Easy deployment on Windows.
Clear separation between UI, business logic, and infrastructure.
3. Design Philosophy

The software shall be developed according to the following principles:

Architecture before implementation.
Simplicity over unnecessary complexity.
Readability over cleverness.
Composition over inheritance.
Explicit dependencies.
Low coupling.
High cohesion.
Reusability.
Testability.
Long-term maintainability.

Every module must have one clearly defined responsibility.

4. Product Vision

The final product should feel like a commercial desktop application rather than a student project.

The application should:

Start quickly.
Open large studies efficiently.
Remain responsive at all times.
Provide a smooth user experience.
Behave predictably.
Look modern and professional.
5. Technical Vision

The software shall be implemented using a modular architecture that allows future features to be added without redesigning the core system.

Examples of future extensions include:

PACS
MPR
Volume Rendering
AI Integration
Segmentation
RT Structure
RT Dose
PET/CT Fusion
Plugin System

The current version does not implement these features, but the architecture must remain ready for them.

6. Quality Standards

Every feature added to the project must be:

Functional.
Readable.
Documented.
Testable.
Maintainable.
Consistent with the architecture.
Free of unnecessary duplication.

Code that works but violates these principles is considered incomplete.

7. Technology Stack
Language: Python 3.13+
GUI: PySide6 (Qt6)
DICOM: pydicom
Medical Imaging: SimpleITK
Image Processing: OpenCV
Scientific Computing: NumPy
3D (Future): VTK
Logging: Loguru
Configuration: TOML
Testing: pytest
Formatting: Black
Linting: Ruff
Type Checking: Pyright
Dependency Management: uv
Packaging: PyInstaller

No additional libraries should be introduced without a clear technical justification.

8. Non-Negotiable Rules

The following rules are mandatory:

Business logic must never exist inside UI classes.
UI components must remain lightweight.
Long-running operations must never block the UI thread.
Every module must have a single responsibility.
Public APIs must remain stable and documented.
Avoid global mutable state.
Prefer dependency injection over direct instantiation.
Avoid premature optimization.
Keep functions short and focused.
Design for extensibility from the beginning.
9. Definition of Success

The project will be considered successful when it delivers:

A stable Windows desktop application.
Accurate DICOM visualization.
Professional user experience.
Clean project architecture.
High-quality source code.
Easy installation.
Strong portfolio value.
A scalable foundation for future medical imaging features.
10. Development Workflow

Every new feature should follow this lifecycle:

Plan
    ↓
Design
    ↓
Implement
    ↓
Review
    ↓
Test
    ↓
Refactor
    ↓
Merge

No feature should bypass testing or architectural review.

11. AI Development Principles

When generating code, the AI Agent must always prioritize:

Architectural correctness.
Maintainability.
Readability.
Reliability.
Testability.
Performance.
Simplicity.

Implementation speed is never the primary objective.

12. Project Motto

"Build it as if it will be maintained by a professional engineering team for the next ten years."