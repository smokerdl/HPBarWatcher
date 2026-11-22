"""Full-screen drag-to-select overlay for the capture region."""
from __future__ import annotations

from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget


class RegionSelector(QWidget):
    region_selected = Signal(QRect)
    cancelled = Signal()

    def __init__(self, geometry: QRect, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setGeometry(geometry)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._origin = None
        self._current = None

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API name
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))
        painter.setPen(QPen(QColor(255, 255, 255), 1))
        painter.drawText(20, 35, "Обведи область с HP-баром. Esc — отмена.")
        if self._current is not None:
            local_rect = QRect(self._origin, self._current).normalized()
            painter.fillRect(local_rect, QColor(50, 160, 90, 35))
            painter.setPen(QPen(QColor(80, 220, 130), 2))
            painter.drawRect(local_rect)
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._current = self._origin
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._origin is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        end = event.position().toPoint()
        local_rect = QRect(self._origin, end).normalized()
        global_rect = QRect(local_rect)
        global_rect.translate(self.geometry().topLeft())
        self._origin = None
        self._current = None
        self.close()
        if global_rect.width() >= 30 and global_rect.height() >= 20:
            self.region_selected.emit(global_rect)
        else:
            self.cancelled.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)
