"""Общие фикстуры тестов (offscreen QApplication для GUI-тестов)."""

import os

import pytest


@pytest.fixture(scope="session")
def qt_app():
    """QApplication в offscreen-режиме для GUI-тестов."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app
