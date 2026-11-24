import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from app.ui.key_capture import KeyCaptureButton


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _key_event(key, modifiers, scan_code, virtual_key=0, native_modifiers=0):
    return QKeyEvent(
        QEvent.Type.KeyPress,
        key,
        modifiers,
        scan_code,
        virtual_key,
        native_modifiers,
        "",
        False,
        1,
    )


@pytest.mark.parametrize(
    ("modifier_key", "scan_code"),
    [
        (Qt.Key.Key_Control, 0x1D),
        (Qt.Key.Key_Shift, 0x2A),
    ],
)
def test_modifier_key_alone_does_not_complete_capture(qt_app, modifier_key, scan_code):
    button = KeyCaptureButton("1")
    button.begin_capture()

    button.keyPressEvent(
        _key_event(modifier_key, Qt.KeyboardModifier.NoModifier, scan_code)
    )

    assert button._capturing
    assert button.key_label == "1"


@pytest.mark.parametrize(
    ("modifier_key", "modifier_flag", "expected"),
    [
        (Qt.Key.Key_Control, Qt.KeyboardModifier.ControlModifier, "Ctrl+Q"),
        (Qt.Key.Key_Shift, Qt.KeyboardModifier.ShiftModifier, "Shift+Q"),
    ],
)
def test_single_modifier_plus_primary_key_is_captured(
    qt_app, modifier_key, modifier_flag, expected
):
    button = KeyCaptureButton("1")
    button.begin_capture()

    button.keyPressEvent(
        _key_event(modifier_key, Qt.KeyboardModifier.NoModifier, 0x1D)
    )
    button.keyPressEvent(
        _key_event(Qt.Key.Key_Q, modifier_flag, 0x10, virtual_key=0x51)
    )

    assert not button._capturing
    assert button.key_label == expected


def test_ctrl_and_shift_together_are_rejected(qt_app):
    button = KeyCaptureButton("1")
    button.begin_capture()

    button.keyPressEvent(
        _key_event(
            Qt.Key.Key_Q,
            Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
            0x10,
            virtual_key=0x51,
        )
    )

    assert button._capturing
    assert button.key_label == "1"
    assert "только один модификатор" in button.toolTip().lower()


def test_alt_combination_is_rejected(qt_app):
    button = KeyCaptureButton("1")
    button.begin_capture()

    button.keyPressEvent(
        _key_event(Qt.Key.Key_Q, Qt.KeyboardModifier.AltModifier, 0x10)
    )

    assert button._capturing
    assert button.key_label == "1"


def test_main_window_resource_grid_has_room_for_controls(qt_app):
    from app.ui.main_window import MainWindow

    window = MainWindow()
    try:
        window.show()
        qt_app.processEvents()
        settings_box = window.resource_controls["hp"][0].parentWidget()
        grid = settings_box.layout()
        assert grid.columnCount() == 6
        assert grid.rowCount() == 3
        assert settings_box.minimumWidth() >= 660
        assert window.minimumWidth() >= 700
        assert window.minimumHeight() >= 760
        assert settings_box.height() >= grid.sizeHint().height()

        labels = {"hp": "HP", "es": "Энергощит", "mana": "Мана"}
        for row, name in enumerate(("hp", "es", "mana")):
            enabled, threshold, key_button = window.resource_controls[name]
            assert grid.itemAtPosition(row, 0).widget().text() == labels[name]
            assert grid.itemAtPosition(row, 5).widget() is key_button
            assert enabled.minimumHeight() >= 28
            assert threshold.height() >= 28
            assert key_button.minimumHeight() >= 28
            assert grid.rowMinimumHeight(row) >= 34

        assert hasattr(window, "width_spin")
        assert not hasattr(window, "width_status_label")
        assert window.width_spin.value() == 82
    finally:
        window._stop()
        window.deleteLater()
