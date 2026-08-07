CODING STANDARDS

Project: DICOMStudio

Version: 1.0

Status: Approved

1. Purpose

This document defines the mandatory coding standards for the DICOMStudio project.

Every source file, class, function, and module must comply with these standards.

These rules are not recommendations. They are mandatory project conventions.

Whenever multiple valid implementation choices exist, the solution that best complies with these standards shall be selected.

2. General Principles

The codebase must always prioritize:

Readability
Maintainability
Simplicity
Correctness
Testability
Performance

Performance optimizations must never reduce code clarity unless they solve a demonstrated bottleneck.

3. Python Version
Python 3.13+ is required.
Use modern language features when they improve clarity.
Avoid deprecated syntax or legacy compatibility code.
4. Code Style
Formatting
Use Black as the single source of formatting.
Never manually format code to conflict with Black.
Keep formatting consistent across the repository.
Linting
Use Ruff.
Resolve all lint warnings before merging.
Do not silence warnings unless there is a documented reason.
Type Checking
Use Pyright.
Public APIs must be fully type-annotated.
Avoid Any unless absolutely necessary.
5. Naming Conventions
Variables

Use descriptive names.

Good:

patient_name
study_directory
window_width
pixel_spacing

Bad:

x
tmp
data1
foo
Functions

Function names must describe actions.

Examples:

load_study()
parse_metadata()
generate_thumbnail()
calculate_window_level()
Classes

Use PascalCase.

StudyLoader
DicomParser
ImageViewport
MeasurementTool
Constants
DEFAULT_WINDOW_WIDTH
MAX_CACHE_SIZE
SUPPORTED_MODALITIES
6. File Organization

Each file should have one primary responsibility.

Avoid files containing unrelated classes.

Prefer smaller, focused modules over large utility files.

As a guideline, a file should rarely exceed 500 lines. If it grows significantly beyond that, consider whether it contains more than one responsibility.

7. Class Design

Every class should have one responsibility.

Avoid "God Classes."

Good:

StudyLoader
MetadataParser
WindowingService

Bad:

MedicalImagingManager

that performs loading, rendering, exporting, logging, and configuration.

8. Function Design

Functions should:

Do one thing.
Have descriptive names.
Be easy to test.
Avoid hidden side effects.

As a guideline:

Aim for fewer than 40 lines.
If a function becomes difficult to understand, split it into smaller private helper methods.
9. Dependency Rules

Never instantiate infrastructure services directly inside business logic.

Prefer constructor injection.

Good:

StudyLoader(FileRepository)

Bad:

StudyLoader()
    creates FileRepository internally

This keeps components testable and replaceable.

10. Error Handling
Never ignore exceptions.
Never use bare except:.
Catch the most specific exception possible.
Log recoverable errors.
Re-raise only when appropriate.
User-facing messages should be clear and actionable.
Internal logs may contain technical details but should avoid exposing protected patient information.
11. Logging

Use structured logging.

Log:

Startup
Shutdown
Configuration loading
DICOM loading
Export operations
Exceptions
Performance-critical events

Avoid excessive logging inside tight rendering loops.

12. Documentation

Every public class must include a docstring.

Every public function must include:

Purpose
Parameters
Return value
Raised exceptions (when applicable)

Use Google Python Style for docstrings.

Complex algorithms should include brief implementation notes explaining why a particular approach was chosen.

13. Comments

Write comments that explain why, not what.

Avoid obvious comments.

Bad:

# Increment index
index += 1

Good:

# DICOM slices may arrive out of order, so sorting is performed
# before building the study hierarchy.
14. Imports
Group imports in the following order:
Python standard library
Third-party libraries
Project modules
Remove unused imports.
Avoid wildcard imports.
Minimize circular dependencies through clear module boundaries.
15. UI Rules

The Presentation layer must:

Never contain business logic.
Never perform DICOM parsing.
Never access the file system directly.
Never perform expensive processing on the UI thread.

UI components should focus on presentation and user interaction only.

16. Domain Rules

The Domain layer:

Must remain independent of UI frameworks.
Must not import Qt.
Must not import VTK.
Must not import OpenCV directly.
Must remain testable in isolation.
17. Performance Guidelines

Optimize only when necessary.

When optimization is required:

Measure the bottleneck.
Document the reason.
Implement the optimization.
Re-measure to confirm improvement.

Prefer lazy loading, caching, and asynchronous processing over premature micro-optimizations.

18. Threading Rules
The UI thread is reserved for user interaction and rendering coordination.
Long-running tasks must execute in worker threads.
Never update Qt widgets directly from worker threads.
Use Qt signals/slots or another thread-safe communication mechanism.
19. Testing Standards

Core business logic should include unit tests.

Tests should be:

Independent
Deterministic
Fast
Readable

Avoid tests that depend on external state or execution order.

20. Git Standards
One logical change per commit.
Use clear commit messages.
Keep commits focused and reviewable.
Do not commit generated files unless explicitly required.

Suggested commit format:

feat: add DICOM study loader
fix: handle invalid transfer syntax
refactor: simplify metadata parser
test: add study grouping tests
docs: update architecture guide
21. Forbidden Practices

The following practices are prohibited:

Business logic inside UI classes.
Circular dependencies.
Global mutable state.
Hard-coded file paths.
Magic numbers without explanation.
Duplicate business logic.
Wildcard imports.
Catch-all exception handlers without justification.
Mixing unrelated responsibilities in the same class.
Ignoring linting or type-checking errors.
22. Definition of Code Quality

Code is considered production-ready only if it is:

Correct
Readable
Maintainable
Tested
Documented
Type-safe
Consistent with the project architecture
Free of unnecessary duplication
Compliant with formatting and linting rules

Working code alone is not sufficient if it violates these standards.

23. AI Agent Coding Rules

When generating code, the AI Agent must:

Respect the project architecture.
Prefer simple solutions over clever ones.
Avoid introducing unnecessary abstractions.
Reuse existing components before creating new ones.
Keep public APIs stable.
Write code that is easy for humans to read and maintain.
Ensure new code integrates cleanly with the existing project structure.
Add or update tests when introducing new functionality.
Preserve backward compatibility within the current project scope whenever reasonable.
Treat maintainability as the highest long-term objective.
24. Final Principle

"Code is written for humans first and executed by machines second."

Every implementation decision should make the codebase easier to understand, easier to extend, and safer to evolve over time.