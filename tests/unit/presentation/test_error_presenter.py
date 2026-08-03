"""Tests for the error presenter."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from dicomviewer.presentation.feedback.error_presenter import ErrorPresenter


def test_show_error_presents_the_friendly_message_only(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_critical(parent, title: str, text: str) -> QMessageBox.StandardButton:
        calls.append((title, text))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "critical", fake_critical)
    presenter = ErrorPresenter()
    presenter.show_error(None, "Load failed", "The folder could not be read.", "OSError: denied")
    assert calls == [("Load failed", "The folder could not be read.")]
