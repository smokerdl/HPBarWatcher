"""Main diagnostic window."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QTimer, QRect
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.config.settings import AppSettings, Region, ResourceSettings, load_settings, save_settings
from app.vision.bar_detector import BarDetector, ResourceReadout
from app.vision.screen_capture import ScreenCapture
from app.ui.region_selector import RegionSelector


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HPBarWatcher — диагностика")
        self.setMinimumSize(620, 590)
        self.settings = load_settings()
        self.capture: ScreenCapture | None = None
        self.detector = BarDetector(self.settings.bar_width_px)
        self._selector: RegionSelector | None = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_screen)
        self._build_ui()
        self._load_controls()
        self._set_idle_status()

    def _build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)

        title = QLabel("HPBarWatcher")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        subtitle = QLabel("Этап 1 · Распознавание ресурсов без нажатия клавиш")
        subtitle.setStyleSheet("color: #777;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        region_box = QGroupBox("Область наблюдения")
        region_layout = QHBoxLayout(region_box)
        self.region_label = QLabel("Не выбрана")
        self.region_label.setWordWrap(True)
        self.select_button = QPushButton("Выбрать область…")
        self.select_button.clicked.connect(self._select_region)
        region_layout.addWidget(self.region_label, 1)
        region_layout.addWidget(self.select_button)
        layout.addWidget(region_box)

        settings_box = QGroupBox("Настройки ресурсов")
        form = QFormLayout(settings_box)
        self.resource_controls: dict[str, tuple[QCheckBox, QDoubleSpinBox, QLineEdit]] = {}
        for key, label, default_threshold, default_key in (
            ("hp", "HP", 30.0, "1"),
            ("es", "Энергощит", 20.0, "3"),
            ("mana", "Мана", 50.0, "2"),
        ):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            enabled = QCheckBox("Вкл.")
            threshold = QDoubleSpinBox()
            threshold.setRange(0.0, 100.0)
            threshold.setDecimals(1)
            threshold.setSuffix(" %")
            threshold.setFixedWidth(105)
            key_edit = QLineEdit(default_key)
            key_edit.setMaxLength(20)
            key_edit.setPlaceholderText("Клавиша")
            key_edit.setFixedWidth(95)
            row_layout.addWidget(enabled)
            row_layout.addWidget(QLabel("Порог:"))
            row_layout.addWidget(threshold)
            row_layout.addWidget(QLabel("Клавиша:"))
            row_layout.addWidget(key_edit)
            row_layout.addStretch(1)
            form.addRow(label, row)
            self.resource_controls[key] = (enabled, threshold, key_edit)
        layout.addWidget(settings_box)

        technical_box = QGroupBox("Параметры распознавания")
        technical_form = QFormLayout(technical_box)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(40, 240)
        self.width_spin.setSuffix(" px")
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(33, 250)
        self.interval_spin.setSuffix(" мс")
        technical_form.addRow("Полная ширина полосы:", self.width_spin)
        technical_form.addRow("Интервал проверки:", self.interval_spin)
        layout.addWidget(technical_box)

        current_box = QGroupBox("Текущие значения")
        current_layout = QFormLayout(current_box)
        self.value_bars: dict[str, QProgressBar] = {}
        self.value_labels: dict[str, QLabel] = {}
        for key, label in (("hp", "HP"), ("es", "Энергощит"), ("mana", "Мана")):
            line = QWidget()
            line_layout = QHBoxLayout(line)
            line_layout.setContentsMargins(0, 0, 0, 0)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(0)
            bar.setFormat("")
            value = QLabel("—")
            value.setMinimumWidth(55)
            value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            line_layout.addWidget(bar, 1)
            line_layout.addWidget(value)
            current_layout.addRow(label, line)
            self.value_bars[key] = bar
            self.value_labels[key] = value
        layout.addWidget(current_box)

        self.preview = QLabel("Предпросмотр выбранной области появится здесь")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(100)
        self.preview.setMaximumHeight(155)
        self.preview.setStyleSheet("background: #20242a; color: #bbb; border-radius: 5px;")
        layout.addWidget(self.preview)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("Начать диагностику")
        self.stop_button = QPushButton("Остановить")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self._start)
        self.stop_button.clicked.connect(self._stop)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        layout.addLayout(buttons)

        self.status_label = QLabel("Ожидание настройки области")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("padding: 7px; background: #292f36; border-radius: 4px;")
        layout.addWidget(self.status_label)

        note = QLabel("Диагностический режим не нажимает клавиши. Настройки порогов и клавиш пока сохраняются для следующего этапа.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #9a7b45; font-size: 11px;")
        layout.addWidget(note)

        self.setCentralWidget(root)

    def _load_controls(self) -> None:
        if self.settings.region:
            self._set_region_label(self.settings.region)
        for name, resource in (("hp", self.settings.hp), ("es", self.settings.es), ("mana", self.settings.mana)):
            enabled, threshold, key_edit = self.resource_controls[name]
            enabled.setChecked(resource.enabled)
            threshold.setValue(resource.threshold)
            key_edit.setText(resource.key)
            enabled.stateChanged.connect(self._save_controls)
            threshold.valueChanged.connect(self._save_controls)
            key_edit.textChanged.connect(self._save_controls)
        self.width_spin.setValue(self.settings.bar_width_px)
        self.interval_spin.setValue(self.settings.poll_interval_ms)
        self.width_spin.valueChanged.connect(self._save_controls)
        self.interval_spin.valueChanged.connect(self._save_controls)

    def _save_controls(self, *_args) -> None:
        for name in ("hp", "es", "mana"):
            enabled, threshold, key_edit = self.resource_controls[name]
            setattr(self.settings, name, ResourceSettings(enabled.isChecked(), threshold.value(), key_edit.text().strip()))
        self.settings.bar_width_px = self.width_spin.value()
        self.settings.poll_interval_ms = self.interval_spin.value()
        try:
            save_settings(self.settings)
        except OSError as exc:
            self.status_label.setText(f"Не удалось сохранить настройки: {exc}")

    def _set_region_label(self, region: Region) -> None:
        self.region_label.setText(
            f"X={region.x}, Y={region.y}, ширина={region.width}, высота={region.height}"
        )

    def _select_region(self) -> None:
        if self.timer.isActive():
            self._stop()
        screen = self.screen() or self.windowHandle().screen()
        if screen is None:
            QMessageBox.warning(self, "Выбор области", "Не удалось определить монитор.")
            return
        self.hide()
        self._selector = RegionSelector(screen.geometry())
        self._selector.region_selected.connect(self._region_selected)
        self._selector.cancelled.connect(self.show)
        self._selector.show()
        self._selector.raise_()
        self._selector.activateWindow()

    def _region_selected(self, rect: QRect) -> None:
        self.settings.region = Region(rect.x(), rect.y(), rect.width(), rect.height())
        self._set_region_label(self.settings.region)
        self._save_controls()
        self.show()
        self.raise_()
        self.activateWindow()
        self.status_label.setText("Область сохранена. Можно запускать диагностику.")

    def _start(self) -> None:
        if self.settings.region is None:
            QMessageBox.information(self, "Область не выбрана", "Сначала нажми «Выбрать область…» и обведи место, где находится HP-бар.")
            return
        try:
            self.capture = ScreenCapture()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка захвата экрана", str(exc))
            return
        self.detector = BarDetector(self.width_spin.value())
        self.timer.start(self.interval_spin.value())
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.select_button.setEnabled(False)
        self.status_label.setText("Мониторинг запущен. Ожидание HP-бара…")

    def _stop(self) -> None:
        self.timer.stop()
        if self.capture is not None:
            self.capture.close()
            self.capture = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.select_button.setEnabled(True)
        self.status_label.setText("Мониторинг остановлен. Никакие клавиши не нажимались.")

    def _poll_screen(self) -> None:
        if self.capture is None or self.settings.region is None:
            return
        try:
            frame = self.capture.capture(self.settings.region)
            self._show_preview(frame)
            result = self.detector.detect(frame)
            self._show_readout(result)
        except Exception as exc:
            self.status_label.setText(f"Ошибка захвата/анализа: {exc}")

    def _show_preview(self, frame: np.ndarray) -> None:
        height, width, _ = frame.shape
        image = QImage(frame.data, width, height, frame.strides[0], QImage.Format.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
        )
        self.preview.setPixmap(pixmap)

    def _show_readout(self, result: ResourceReadout) -> None:
        if not result.detected:
            for key in self.value_bars:
                self.value_bars[key].setValue(0)
                self.value_labels[key].setText("—")
            self.status_label.setText("HP-бар не обнаружен. Это состояние не считается нулевым HP.")
            return
        values = {"hp": result.hp, "es": result.es, "mana": result.mana}
        for key, value in values.items():
            self.value_bars[key].setValue(int(round(value * 10)))
            self.value_labels[key].setText(f"{value:.1f}%")
        self.status_label.setText(
            f"{result.message} · X={result.bar_x}, Y(HP)={result.hp_y:.1f} · уверенность {result.confidence:.0%}"
        )

    def _set_idle_status(self) -> None:
        if self.settings.region is None:
            self.status_label.setText("Сначала выбери область, в которой обычно расположен HP-бар.")
        else:
            self.status_label.setText("Область загружена. Нажми «Начать диагностику».")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop()
        super().closeEvent(event)
