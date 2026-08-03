"""Application entry point and composition root.

All object wiring happens here. Components are assembled through constructor
injection; the rest of the codebase never constructs infrastructure directly.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.resources import as_file, files
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from dicomviewer import __version__
from dicomviewer.application.processing import ProcessingPipeline
from dicomviewer.application.theme_manager import ThemeManager
from dicomviewer.domain.settings import SettingsError
from dicomviewer.infrastructure.configuration.settings_service import build_settings_service
from dicomviewer.infrastructure.dicom.pixel_reader import PydicomPixelDecoder
from dicomviewer.infrastructure.dicom.scanner import PydicomStudyScanner
from dicomviewer.infrastructure.dicom.thumbnail_service import PydicomThumbnailService
from dicomviewer.infrastructure.logging.setup import configure_logging
from dicomviewer.infrastructure.persistence.app_paths import AppPaths
from dicomviewer.infrastructure.persistence.window_state_store import JsonWindowStateStore
from dicomviewer.infrastructure.processing.analyzer import NumpyImageAnalyzer
from dicomviewer.infrastructure.rendering.renderer import NumpyViewRenderer
from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.presentation.theme.theme_controller import ThemeController
from dicomviewer.presentation.theme.theme_provider import ThemeProvider
from dicomviewer.presentation.windows.main_window import MainWindow
from dicomviewer.shared.constants import APP_DIR_NAME, APP_NAME, ORGANIZATION_NAME


@dataclass(frozen=True)
class CliOptions:
    """Parsed command-line options."""

    show_version: bool = False
    smoke_test: bool = False
    theme: str | None = None
    qt_arguments: tuple[str, ...] = ()


def main(argv: Sequence[str] | None = None) -> int:
    """Start the application and run its event loop until the user exits.

    Returns the process exit code.
    """
    try:
        options = _parse_arguments(sys.argv[1:] if argv is None else argv)
    except SettingsError as exc:
        print(f"{APP_NAME}: {exc}", file=sys.stderr)
        return 2
    if options.show_version:
        print(f"{APP_NAME} {__version__}")
        return 0

    _prepare_qt_environment()
    application = _create_application("dicomviewer", options.qt_arguments)
    paths = AppPaths(APP_DIR_NAME)
    paths.ensure_dirs()
    try:
        settings_service = build_settings_service(paths)
        settings = settings_service.load()
        theme_manager = ThemeManager(settings_service, settings)
        if options.theme is not None:
            theme_manager.apply_override(options.theme)
    except SettingsError as exc:
        logger.error("Configuration error: {}", exc)
        print(f"{APP_NAME}: {exc}", file=sys.stderr)
        return 2
    configure_logging(settings.logging, paths.logs_dir)

    logger.info("Starting {name} {version}", name=APP_NAME, version=__version__)
    icon_provider = IconProvider(_icons_dir())
    theme_controller = ThemeController(theme_manager, ThemeProvider(application), icon_provider)
    window_state_store = JsonWindowStateStore(paths.config_dir / "window_state.json")
    window = MainWindow(
        APP_NAME,
        __version__,
        theme_controller,
        window_state_store,
        icon_provider,
        study_scanner=PydicomStudyScanner(),
        thumbnail_service=PydicomThumbnailService(),
        pixel_decoder=PydicomPixelDecoder(),
        view_renderer=NumpyViewRenderer(processing_pipeline=ProcessingPipeline(())),
        image_analyzer=NumpyImageAnalyzer(),
    )
    theme_controller.apply_current()
    window.show()

    if options.smoke_test:
        QTimer.singleShot(500, application.quit)

    exit_code = application.exec()
    logger.info("{name} stopped with exit code {code}", name=APP_NAME, code=exit_code)
    return exit_code


def entry() -> None:
    """Console entry point that converts the return code into a process exit."""
    raise SystemExit(main())


def _parse_arguments(argv: Sequence[str]) -> CliOptions:
    """Parse application-specific arguments, leaving Qt arguments untouched."""
    show_version = False
    smoke_test = False
    theme: str | None = None
    qt_arguments: list[str] = []
    index = 0
    while index < len(argv):
        argument = argv[index]
        if argument in ("--version", "-v"):
            show_version = True
        elif argument == "--smoke-test":
            smoke_test = True
        elif argument == "--theme":
            index += 1
            if index >= len(argv):
                raise SettingsError("The --theme option requires a value")
            theme = argv[index]
        elif argument.startswith("--theme="):
            theme = argument.split("=", 1)[1]
        else:
            qt_arguments.append(argument)
        index += 1
    return CliOptions(show_version, smoke_test, theme, tuple(qt_arguments))


def _icons_dir() -> Path:
    """Resolve the bundled icon directory for the current environment."""
    with as_file(files("dicomviewer.resources").joinpath("icons")) as path:
        return path


def _prepare_qt_environment() -> None:
    """Apply process-wide Qt settings before the application object exists.

    Qt 6 enables high-DPI scaling and high-DPI pixmaps by default, so no
    attributes are required today. This hook exists so platform-level setup
    has a single, well-defined location.
    """


def _create_application(program_name: str, qt_arguments: Sequence[str]) -> QApplication:
    """Create the QApplication, set metadata and force a consistent style."""
    application = QApplication([program_name, *qt_arguments])
    application.setApplicationName(APP_NAME)
    application.setApplicationDisplayName(APP_NAME)
    application.setApplicationVersion(__version__)
    application.setOrganizationName(ORGANIZATION_NAME)
    application.setStyle("Fusion")
    return application


if __name__ == "__main__":
    entry()
