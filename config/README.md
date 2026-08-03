# Configuration

The application configuration is TOML-based (ADR-006).

## Layout

- **Bundled defaults** ship inside the package as
  `src/dicomviewer/infrastructure/configuration/defaults.toml`. They are the
  single source of truth for default values and are loaded at runtime.
- **User overrides** are stored at
  `%APPDATA%\DicomViewer\config\settings.toml` and merged over the defaults.
  The file is created when the user saves settings.
- **`example_settings.toml`** in this directory documents the full schema for
  reference; it is not read by the application.

## Example

Copy the sections you want to override from `example_settings.toml` into the
user settings file, or edit the file from the application when the Settings
dialog exists (a later milestone).
