"""Button widget that captures a physical key with an optional modifier."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QPushButton

from app.automation.keyboard_input import (
    KeyBinding,
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
    binding_changed = Signal(str, int, bool, str)

    def __init__(
        self,
        label: str = "1",
        scan_code: int = 0,
        extended: bool = False,
        modifier: str | None = None,
        parent=None,
    ):
        super().__init__(parent)
        fallback = default_binding_for_label(label or "1")
        self.scan_code = int(scan_code or (fallback.scan_code if fallback else 0))
        self.extended = bool(
            extended if scan_code else (fallback.extended if fallback else extended)
        )
        self.modifier = (
            (modifier or "").strip().lower()
            or (fallback.modifier if fallback else None)
        )
        self.key_label = label_for_binding(
            KeyBinding(self.scan_code, self.extended, self.modifier)
        ) if self.scan_code else (label or "1")
        self._capturing = False
        self.setFixedWidth(125)
        self.setMinimumHeight(27)
        self._refresh_text()
        self.setToolTip(
            "Нажми поле, затем обычную клавишу или зажми Ctrl/Shift и нажми клавишу. "
            "Ctrl и Shift по отдельности не назначаются."
        )
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

        modifiers = event.modifiers()
        has_ctrl = bool(modifiers & Qt.KeyboardModifier.ControlModifier)
        has_shift = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)
        has_unsupported = bool(
            modifiers
            & (
                Qt.KeyboardModifier.AltModifier
                | Qt.KeyboardModifier.MetaModifier
            )
        )

        if has_ctrl and has_shift:
            self.setToolTip(
                "Поддерживается только один модификатор: Ctrl или Shift. "
                "Отпусти один из них и повтори."
            )
            event.accept()
            return
        if has_unsupported:
            self.setToolTip(
                "Alt и системные модификаторы не поддерживаются. "
                "Используй обычную клавишу, Ctrl или Shift."
            )
            event.accept()
            return

        try:
            primary = normalize_native_scan_code(event.nativeScanCode())
            binding = KeyBinding(
                primary.scan_code,
                primary.extended,
                "ctrl" if has_ctrl else "shift" if has_shift else None,
            )
        except ValueError:
            self.key_label = "Повторите"
            self._capturing = False
            self._refresh_text()
            self.setToolTip(
                "Не удалось определить scan code. Попробуй другую клавишу."
            )
            event.accept()
            return

        self.key_label = label_for_binding(binding)
        self.scan_code = binding.scan_code
        self.extended = binding.extended
        self.modifier = binding.modifier
        self._capturing = False
        self._refresh_text()
        self.setToolTip(
            f"Физическая клавиша · scan code 0x{self.scan_code:02X}"
            + (f" · модификатор {self.modifier}" if self.modifier else "")
        )
        self.binding_changed.emit(
            self.key_label,
            self.scan_code,
            self.extended,
            self.modifier or "",
        )
        event.accept()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self.cancel_capture()
        super().focusOutEvent(event)
