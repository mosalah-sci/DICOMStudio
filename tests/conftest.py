"""Shared pytest fixtures."""

from __future__ import annotations

import os
from collections.abc import Callable
from importlib.resources import as_file, files
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from dicomviewer.application.theme_manager import ThemeManager
from dicomviewer.infrastructure.configuration.settings_service import (
    SettingsService,
    load_default_settings,
)
from dicomviewer.infrastructure.persistence.window_state_store import JsonWindowStateStore
from dicomviewer.presentation.theme.icon_provider import IconProvider
from dicomviewer.presentation.theme.theme_controller import ThemeController
from dicomviewer.presentation.theme.theme_provider import ThemeProvider
from dicomviewer.presentation.windows.main_window import MainWindow
from dicomviewer.shared.constants import APP_NAME, __version__
from tests.dicom_utils import (
    FakeErrorPresenter,
    FakeImageAnalyzer,
    FakeImageExporter,
    FakeMetadataService,
    FakePixelDecoder,
    FakeStudyScanner,
    FakeThumbnailService,
    FakeViewRenderer,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Provide a single Qt application instance for widget tests."""
    application = QApplication.instance() or QApplication(["dicomviewer-tests"])
    return application


@pytest.fixture
def icon_provider() -> IconProvider:
    """Provide an icon provider backed by the real bundled icons."""
    with as_file(files("dicomviewer.resources").joinpath("icons")) as icon_dir:
        yield IconProvider(icon_dir)


@pytest.fixture
def make_window(
    qapp: QApplication,
    tmp_path: Path,
    icon_provider: IconProvider,
) -> Callable[..., MainWindow]:
    """Return a factory that builds a fully wired MainWindow in a temp dir."""

    def _make(
        theme: str = "dark",
        version: str = __version__,
        study_scanner: FakeStudyScanner | None = None,
        thumbnail_service: FakeThumbnailService | None = None,
        pixel_decoder: FakePixelDecoder | None = None,
        view_renderer: FakeViewRenderer | None = None,
        image_analyzer: FakeImageAnalyzer | None = None,
        metadata_service: FakeMetadataService | None = None,
        image_exporter: FakeImageExporter | None = None,
        screenshot_dir: Path | None = None,
    ) -> MainWindow:
        settings_path = tmp_path / "settings.toml"
        settings_service = SettingsService(load_default_settings(), settings_path)
        theme_manager = ThemeManager(settings_service, load_default_settings())
        if theme != "dark":
            theme_manager.apply_override(theme)
        theme_controller = ThemeController(theme_manager, ThemeProvider(qapp), icon_provider)
        window_state_store = JsonWindowStateStore(tmp_path / "window_state.json")
        return MainWindow(
            APP_NAME,
            version,
            theme_controller,
            settings_manager=theme_manager,
            window_state_store=window_state_store,
            icon_provider=icon_provider,
            study_scanner=study_scanner or FakeStudyScanner(),
            thumbnail_service=thumbnail_service or FakeThumbnailService(),
            pixel_decoder=pixel_decoder or FakePixelDecoder(),
            view_renderer=view_renderer or FakeViewRenderer(),
            image_analyzer=image_analyzer or FakeImageAnalyzer(),
            metadata_service=metadata_service or FakeMetadataService(),
            image_exporter=image_exporter or FakeImageExporter(),
            screenshot_dir=screenshot_dir,
            error_presenter=FakeErrorPresenter(),
        )

    return _make
