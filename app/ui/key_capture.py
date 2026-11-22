"""Button widget that captures one physical keyboard key."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QPushButton

from app.automation.keyboard_input import (
    default_binding_for_label,
    label_for_binding,
    normalize_native_scan_code,
)


_MODIFIER_KEYS = {
    Qt.Key.Key_Shift,
    Qt.Key.Key_Control,
    Qt.Key.Key_Alt,
    Qt.Key.Key_Meta,
    Qt.Key.Key_AltGr,
}


class KeyCaptureButton(QPushButton):
    binding_changed = Signal(str, int, bool)

    def __init__(self, label: str = "1", scan_code: int = 0, extended: bool = False, parent=None):
        super().__init__(parent)
        self.key_label = label or "1"
        fallback = default_binding_for_label(self.key_label)
        self.scan_code = int(scan_code or (fallback.scan_code if fallback else 0))
        self.extended = bool(extended if scan_code else (fallback.extended if fallback else extended))
        self._capturing = False
        self.setFixedWidth(105)
        self._refresh_text()
        self.setToolTip("Нажми кнопку, затем один раз нажми нужную клавишу на клавиатуре.")
        self.clicked.connect(self.begin_capture)

    def _refresh_text(self) -> None:
        self.setText("Нажмите клавишу…" if self._capturing else self.key_label)

    def begin_capture(self) -> None:
        self._capturing = True
        self._refresh_text()
        self.setFocus(Qt.FocusReason.MouseFocusReason)

    def cancel_capture(self) -> None:
        if self._capturing:
            self._capturing = False
            self._refresh_text()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if not self._capturing:
            super().keyPressEvent(event)
            return
        if event.isAutoRepeat() or event.key() in _MODIFIER_KEYS:
            event.accept()
            return
        try:
            binding = normalize_native_scan_code(event.nativeScanCode())
        except ValueError:
            self.key_label = "Повторите"
            self._capturing = False
            self._refresh_text()
            self.setToolTip("Не удалось определить scan code. Попробуй другую клавишу.")
            event.accept()
            return
        self.key_label = label_for_binding(binding)
        self.scan_code = binding.scan_code
        self.extended = binding.extended
        self._capturing = False
        self._refresh_text()
        self.setToolTip(f"Физическая клавиша · scan code 0x{self.scan_code:02X}")
        self.binding_changed.emit(self.key_label, self.scan_code, self.extended)
        event.accept()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self.cancel_capture()
        super().focusOutEvent(event)
