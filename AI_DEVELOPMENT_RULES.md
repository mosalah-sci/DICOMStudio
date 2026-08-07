AI DEVELOPMENT RULES



Project: DICOMStudio



Version: 1.0



Purpose: Mandatory implementation rules for any AI agent contributing to this repository.



1\. Mission



You are contributing to a professional-grade medical imaging application.



Your responsibility is not simply to generate code, but to build software that is maintainable, extensible, testable, and suitable for long-term development.



Every implementation decision must support the project's architecture and future evolution.



2\. Primary Objectives



Always prioritize the following, in order:



Architectural correctness

Maintainability

Readability

Reliability

Testability

Extensibility

Performance

Development speed



Never sacrifice long-term quality for short-term implementation speed.



3\. Architectural Compliance



You must always respect the approved project architecture.



Never violate layer boundaries.

Never introduce circular dependencies.

Never bypass established abstractions.

Never mix responsibilities between modules.

Never place business logic inside UI components.



When uncertain, choose the solution that preserves architectural consistency.



4\. Before Writing Code



Before implementing any feature:



Understand the requested scope.

Identify the affected modules.

Reuse existing components whenever possible.

Minimize the number of new files and classes.

Avoid introducing unnecessary dependencies.



Do not implement functionality outside the requested scope.



5\. Code Generation Principles



Generated code must be:



Clear

Predictable

Self-explanatory

Modular

Easy to review

Easy to extend



Favor explicit implementations over clever shortcuts.



6\. Project Structure



Respect the existing directory structure.



Do not reorganize folders unless explicitly requested.



Create new modules only when they provide a clear architectural benefit.



7\. Layer Responsibilities

Presentation Layer



Responsible only for:



Windows

Widgets

User interaction

ViewModels

Visual state



Must not contain business logic.



Application Layer



Responsible for:



Use cases

Workflows

Coordination

Commands



Must not directly manipulate UI widgets.



Domain Layer



Responsible for:



Business rules

Core entities

Validation

Calculations



Must remain independent of frameworks.



Infrastructure Layer



Responsible for:



File system

DICOM libraries

Configuration

Logging

External integrations



Framework-specific code belongs here.



8\. Dependency Rules



Prefer dependency injection.



Avoid direct instantiation of services inside business logic.



Reuse shared services rather than creating duplicate implementations.



9\. Feature Development Workflow



For every feature:



Understand the requirement.

Design the solution.

Implement the minimum complete functionality.

Add error handling.

Add logging where appropriate.

Update tests if behavior changes.

Verify compatibility with existing modules.



Do not leave partially implemented features.



10\. Error Handling



Never ignore exceptions.



Use meaningful exception types.



Provide user-friendly error messages in the UI.



Record technical details in logs.



The application should fail gracefully whenever possible.



11\. Logging



Log only meaningful events.



Typical examples:



Application startup

Study loading

Export operations

Configuration changes

Recoverable errors



Avoid excessive or noisy logging.



12\. Performance



Assume that users may open very large DICOM studies.



Prefer:



Lazy loading

Incremental processing

Background workers

Intelligent caching



Avoid blocking the UI thread.



Do not optimize prematurely; optimize based on measured bottlenecks.



13\. UI Guidelines



The interface should:



Feel responsive.

Remain uncluttered.

Keep the image as the primary focus.

Provide consistent interactions.



Do not add controls that are not required by the current scope.



14\. Documentation



Document:



Public classes

Public functions

Public interfaces



Use concise Google-style docstrings.



Do not document obvious implementation details.



15\. Testing



Design code to be testable.



When introducing business logic:



Add or update unit tests where appropriate.

Keep tests deterministic.

Avoid reliance on global state.

16\. Refactoring



When modifying existing code:



Preserve external behavior unless changes are requested.

Reduce duplication.

Improve readability.

Avoid unnecessary rewrites.



Refactor only when it provides clear value.



17\. External Libraries



Before introducing a new dependency:



Confirm it provides significant value.

Prefer mature, well-maintained libraries.

Avoid overlapping functionality with existing dependencies.



Do not replace existing libraries without explicit justification.



18\. Security \& Privacy



Treat medical data with care.



Do not transmit patient data externally.

Do not expose sensitive information in logs.

Avoid storing unnecessary personal information.



Respect privacy even in development builds.



19\. Backward Compatibility



Changes should not break existing functionality unless explicitly requested.



Preserve public interfaces whenever possible.



When change is necessary, update all affected components consistently.



20\. Git \& Commit Expectations



Each implementation should represent a single logical change.



Keep changes focused.



Avoid unrelated modifications in the same commit.



21\. Decision-Making Rules



When multiple solutions are technically valid:



Choose the one that is:



Easier to maintain.

Easier to understand.

Better aligned with the project architecture.

More extensible.

Less coupled.

More testable.



Only consider performance as the deciding factor when the alternatives are otherwise equivalent.



22\. What to Avoid



Do not:



Introduce unnecessary abstractions.

Create oversized classes.

Mix UI and business logic.

Duplicate functionality.

Ignore linting or type-checking issues.

Add TODOs as placeholders for incomplete work.

Implement speculative features that are outside the current milestone.



Keep the codebase focused and intentional.



23\. Definition of Completion



A task is complete only when:



The requested functionality is fully implemented.

The solution follows the project architecture.

Error handling is included.

Documentation is updated if required.

Code passes formatting, linting, and type checking.

Tests pass (and new tests are added when appropriate).

No unnecessary technical debt has been introduced.

24\. Final Directive



You are expected to contribute as a senior software engineer working on a long-term commercial application.



Every design choice should improve the codebase rather than simply solving the immediate task.



If a requested implementation conflicts with the project's architecture or long-term maintainability, propose the safer approach before proceeding.

