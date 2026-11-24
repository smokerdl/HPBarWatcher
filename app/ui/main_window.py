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
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.automation.keyboard_input import KeyBinding, KeyboardSender, label_for_binding
from app.automation.trigger_manager import ThresholdTrigger
from app.config.settings import Region, ResourceSettings, load_settings, save_settings
from app.ui.key_capture import KeyCaptureButton
from app.vision.bar_detector import BarDetector, ResourceReadout
from app.vision.screen_capture import ScreenCapture
from app.ui.region_selector import RegionSelector


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("HPBarWatcher — диагностика")
        self.setMinimumSize(700, 800)
        self.settings = load_settings()
        self.capture: ScreenCapture | None = None
        self.detector = BarDetector(self.settings.bar_width_px)
        self._selector: RegionSelector | None = None
        self.triggers = {name: ThresholdTrigger() for name in ("hp", "es", "mana")}
        self.keyboard: KeyboardSender | None = None
        self.keyboard_error: str | None = None
        try:
            self.keyboard = KeyboardSender()
        except (OSError, AttributeError) as exc:
            self.keyboard_error = str(exc)
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
        subtitle = QLabel("Отслеживание HP, энергощита и маны · реакция на пороги")
        subtitle.setStyleSheet("color: #777;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        window_options = QHBoxLayout()
        self.always_on_top_check = QCheckBox("Поверх остальных окон")
        self.always_on_top_check.setToolTip(
            "Закрепить HPBarWatcher поверх окна игры и других приложений."
        )
        window_options.addWidget(self.always_on_top_check)
        window_options.addStretch(1)
        layout.addLayout(window_options)

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
        grid = QGridLayout(settings_box)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        for column, width in enumerate((100, 60, 52, 110, 65, 125)):
            grid.setColumnMinimumWidth(column, width)
        grid.setColumnStretch(5, 1)
        settings_box.setMinimumWidth(660)

        self.resource_controls: dict[str, tuple[QCheckBox, QDoubleSpinBox, KeyCaptureButton]] = {}
        for row_index, (key, label, default_threshold, default_key) in enumerate((
            ("hp", "HP", 30.0, "1"),
            ("es", "Энергощит", 20.0, "3"),
            ("mana", "Мана", 50.0, "2"),
        )):
            resource_label = QLabel(label)
            resource_label.setMinimumWidth(100)
            enabled = QCheckBox("Вкл.")
            enabled.setMinimumHeight(28)
            threshold_label = QLabel("Порог:")
            threshold_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            threshold = QDoubleSpinBox()
            threshold.setRange(0.0, 100.0)
            threshold.setDecimals(1)
            threshold.setSuffix(" %")
            threshold.setFixedSize(110, 28)
            key_label = QLabel("Клавиша:")
            key_label.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            key_button = KeyCaptureButton(default_key)
            key_button.setMinimumHeight(28)

            grid.addWidget(resource_label, row_index, 0)
            grid.addWidget(enabled, row_index, 1)
            grid.addWidget(threshold_label, row_index, 2)
            grid.addWidget(threshold, row_index, 3)
            grid.addWidget(key_label, row_index, 4)
            grid.addWidget(
                key_button, row_index, 5, alignment=Qt.AlignmentFlag.AlignLeft
            )
            grid.setRowMinimumHeight(row_index, 34)

            self.resource_controls[key] = (enabled, threshold, key_button)
            key_button.binding_changed.connect(
                lambda label, scan, ext, modifier, resource=key: self._on_key_binding_changed(
                    resource, label, scan, ext, modifier
                )
            )
        layout.addWidget(settings_box)

        action_box = QGroupBox("Автоматическое нажатие")
        action_layout = QHBoxLayout(action_box)
        self.auto_actions_check = QCheckBox("Включить автонажатия")
        self.auto_actions_check.setToolTip(
            "Клавиши отправляются при обнаруженном HP-баре, если HPBarWatcher не является активным окном. Пока отдельный процесс игры не задан, держи игру на переднем плане."
        )
        self.hold_duration_spin = QSpinBox()
        self.hold_duration_spin.setRange(20, 500)
        self.hold_duration_spin.setSuffix(" мс")
        self.hold_duration_spin.setFixedWidth(100)
        action_layout.addWidget(self.auto_actions_check)
        action_layout.addStretch(1)
        action_layout.addWidget(QLabel("Длительность нажатия:"))
        action_layout.addWidget(self.hold_duration_spin)
        layout.addWidget(action_box)

        technical_box = QGroupBox("Параметры распознавания")
        technical_form = QFormLayout(technical_box)
        self.width_spin = QSpinBox()
        self.width_spin.setRange(40, 240)
        self.width_spin.setSuffix(" px")
        self.width_spin.setFixedWidth(110)
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
        layout.addSpacing(10)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("Начать мониторинг")
        self.stop_button = QPushButton("Остановить")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self._start)
        self.stop_button.clicked.connect(self._stop)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        layout.addLayout(buttons)

        self.status_label = QLabel("Ожидание настройки области")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("padding: 3px 0;")
        layout.addWidget(self.status_label)

        self.auto_status_label = QLabel()
        self.auto_status_label.setWordWrap(True)
        self.auto_status_label.setStyleSheet("color: #777; font-size: 11px;")
        layout.addWidget(self.auto_status_label)

        self.last_action_label = QLabel("Последнее срабатывание: пока не было")
        self.last_action_label.setWordWrap(True)
        self.last_action_label.setStyleSheet("color: #777; font-size: 11px;")
        layout.addWidget(self.last_action_label)

        self.setCentralWidget(root)

    def _load_controls(self) -> None:
        if self.settings.region:
            self._set_region_label(self.settings.region)
        self.always_on_top_check.setChecked(self.settings.always_on_top)
        self.always_on_top_check.toggled.connect(self._on_always_on_top_toggled)
        self._apply_window_stacking(self.settings.always_on_top)
        for name, resource in (("hp", self.settings.hp), ("es", self.settings.es), ("mana", self.settings.mana)):
            enabled, threshold, key_button = self.resource_controls[name]
            enabled.setChecked(resource.enabled)
            threshold.setValue(resource.threshold)
            key_button.modifier = resource.modifier
            if resource.scan_code:
                key_button.scan_code = resource.scan_code
                key_button.extended = resource.extended
            key_button.key_label = label_for_binding(
                KeyBinding(key_button.scan_code, key_button.extended, key_button.modifier)
            )
            key_button._refresh_text()
            enabled.stateChanged.connect(self._save_controls)
            threshold.valueChanged.connect(self._save_controls)
        self.auto_actions_check.setChecked(self.settings.auto_actions_enabled)
        self.auto_actions_check.toggled.connect(self._on_auto_actions_toggled)
        self.hold_duration_spin.setValue(self.settings.key_hold_ms)
        self.hold_duration_spin.valueChanged.connect(self._save_controls)
        self.width_spin.setValue(self.settings.bar_width_px)
        self.width_spin.valueChanged.connect(self._save_controls)
        self.interval_spin.setValue(self.settings.poll_interval_ms)
        self.interval_spin.valueChanged.connect(self._save_controls)
        if self.keyboard is None:
            self.auto_actions_check.setEnabled(False)
            self.auto_actions_check.setToolTip(f"SendInput недоступен: {self.keyboard_error}")
        self._refresh_auto_status()

    def _apply_window_stacking(self, enabled: bool) -> None:
        """Toggle always-on-top while preserving visibility and avoiding focus theft."""
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        if was_visible:
            self.show()
            if enabled:
                self.raise_()
            else:
                self.lower()

    def _on_always_on_top_toggled(self, enabled: bool) -> None:
        self.settings.always_on_top = enabled
        self._apply_window_stacking(enabled)
        try:
            save_settings(self.settings)
        except OSError as exc:
            self.status_label.setText(f"Не удалось сохранить настройки: {exc}")

    def _on_auto_actions_toggled(self, enabled: bool) -> None:
        self.settings.auto_actions_enabled = enabled
        for trigger in self.triggers.values():
            trigger.reset()
        self._save_controls()
        self.status_label.setText(
            "Автонажатия включены. Срабатывание — только при переходе ниже порога."
            if enabled else "Автонажатия выключены."
        )
        self._refresh_auto_status()

    def _refresh_auto_status(self, detected: bool | None = None) -> None:
        if not self.auto_actions_check.isChecked():
            message = "Автонажатия выключены."
        elif self.keyboard is None:
            message = f"Автонажатия недоступны: {self.keyboard_error or 'SendInput не инициализирован'}."
        elif not self.timer.isActive():
            message = "Автонажатия включены, но мониторинг не запущен. Нажми «Начать мониторинг»."
        elif detected is False:
            message = "Автонажатия включены. Ожидание обнаружения HP-бара."
        elif not self.keyboard.foreground_is_external():
            message = "Автонажатия включены, но приостановлены: активным окном сейчас является HPBarWatcher. Переключись в игру."
        else:
            message = "Автонажатия включены. Ожидается падение ресурса ниже порога; уже низкое значение само по себе не вызывает нажатие. Убедись, что именно игра находится на переднем плане."
        self.auto_status_label.setText(message)

    def _on_key_binding_changed(
        self, resource: str, label: str, scan_code: int, extended: bool, modifier: str
    ) -> None:
        self._save_controls()
        self.status_label.setText(
            f"{resource.upper()}: назначено {label}, scan code 0x{scan_code:02X}."
        )

    def _save_controls(self, *_args) -> None:
        for name in ("hp", "es", "mana"):
            enabled, threshold, key_button = self.resource_controls[name]
            setattr(
                self.settings,
                name,
                ResourceSettings(
                    enabled.isChecked(), threshold.value(), key_button.key_label,
                    key_button.scan_code, key_button.extended, key_button.modifier
                ),
            )
        self.settings.auto_actions_enabled = self.auto_actions_check.isChecked()
        self.settings.key_hold_ms = self.hold_duration_spin.value()
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
        self.status_label.setText("Область сохранена. Можно запускать мониторинг.")

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
        for trigger in self.triggers.values():
            trigger.reset()
        self.timer.start(self.interval_spin.value())
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.select_button.setEnabled(False)
        self.status_label.setText("Мониторинг запущен. Ожидание HP-бара…")
        self._refresh_auto_status()

    def _stop(self) -> None:
        self.timer.stop()
        if self.keyboard is not None:
            self.keyboard.release_all()
        for trigger in self.triggers.values():
            trigger.reset()
        if self.capture is not None:
            self.capture.close()
            self.capture = None
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.select_button.setEnabled(True)
        self.status_label.setText("Мониторинг остановлен.")
        self._refresh_auto_status()

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

    def _process_triggers(self, result: ResourceReadout) -> list[str]:
        values = {"hp": result.hp, "es": result.es, "mana": result.mana}
        foreground_ok = (
            self.settings.auto_actions_enabled
            and self.keyboard is not None
            and self.keyboard.foreground_is_external()
        )
        actions: list[str] = []
        for name, value in values.items():
            enabled, threshold, key_button = self.resource_controls[name]
            should_fire = self.triggers[name].update(
                value,
                threshold.value(),
                detected=result.detected,
                enabled=enabled.isChecked() and foreground_ok,
            )
            if not should_fire:
                continue
            if self.keyboard is None or key_button.scan_code <= 0:
                action = f"{name.upper()}: физическая клавиша не назначена"
                actions.append(action)
                self.last_action_label.setText("Последняя попытка: " + action)
                continue
            try:
                sent = self.keyboard.tap(
                    KeyBinding(
                        key_button.scan_code, key_button.extended, key_button.modifier
                    ),
                    self.hold_duration_spin.value(),
                )
                if sent:
                    action = (
                        f"{name.upper()} ниже {threshold.value():g}% → "
                        f"{key_button.key_label} ({self.hold_duration_spin.value()} мс)"
                    )
                    actions.append(action)
                    self.last_action_label.setText("Последнее срабатывание: " + action)
                else:
                    action = (
                        f"{name.upper()}: порог пересечён, но SendInput не отправил клавишу. "
                        "Возможно, в момент нажатия изменился фокус окна или эта клавиша ещё удерживается."
                    )
                    actions.append(action)
                    self.last_action_label.setText("Последняя попытка: " + action)
            except (OSError, ValueError) as exc:
                action = f"Ошибка отправки {name.upper()}: {exc}"
                actions.append(action)
                self.last_action_label.setText("Последняя попытка: " + action)
        return actions

    def _show_preview(self, frame: np.ndarray) -> None:
        height, width, _ = frame.shape
        image = QImage(frame.data, width, height, frame.strides[0], QImage.Format.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
        )
        self.preview.setPixmap(pixmap)

    def _show_readout(self, result: ResourceReadout) -> None:
        if not result.detected:
            for trigger in self.triggers.values():
                trigger.reset()
            for key in self.value_bars:
                self.value_bars[key].setValue(0)
                self.value_labels[key].setText("—")
            self.status_label.setText(result.message)
            self._refresh_auto_status(detected=False)
            return
        values = {"hp": result.hp, "es": result.es, "mana": result.mana}
        for key, value in values.items():
            self.value_bars[key].setValue(int(round(value * 10)))
            self.value_labels[key].setText(f"{value:.1f}%")
        actions = self._process_triggers(result)
        if actions:
            self.status_label.setText("Нажатие: " + " · ".join(actions))
        else:
            self.status_label.setText(
                f"{result.message} · X={result.bar_x}, Y(HP)={result.hp_y:.1f} · уверенность {result.confidence:.0%}"
            )
        self._refresh_auto_status(detected=True)

    def _set_idle_status(self) -> None:
        if self.settings.region is None:
            self.status_label.setText("Сначала выбери область, в которой обычно расположен HP-бар.")
        else:
            self.status_label.setText("Область загружена. Нажми «Начать мониторинг».")

    def closeEvent(self, event) -> None:  # noqa: N802
        self._stop()
        super().closeEvent(event)
