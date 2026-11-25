"""Persistent user settings for HPBarWatcher."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Region:
    x: int
    y: int
    width: int
    height: int

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "Region | None":
        if not data:
            return None
        try:
            region = cls(
                x=int(data["x"]),
                y=int(data["y"]),
                width=int(data["width"]),
                height=int(data["height"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
        return region if region.width > 0 and region.height > 0 else None


@dataclass
class ResourceSettings:
    enabled: bool = True
    threshold: float = 30.0
    key: str = "1"
    scan_code: int = 0
    extended: bool = False
    modifier: str | None = None


@dataclass
class AppSettings:
    region: Region | None = None
    always_on_top: bool = False
    auto_actions_enabled: bool = False
    key_hold_ms: int = 50
    # Full inner width shared by HP, ES and Mana bars at the calibration resolution.
    bar_width_px: int = 82
    calibration_screen_width_px: int | None = None
    calibration_screen_height_px: int | None = None
    poll_interval_ms: int = 50
    hp: ResourceSettings = field(default_factory=lambda: ResourceSettings(True, 30.0, "1"))
    es: ResourceSettings = field(default_factory=lambda: ResourceSettings(True, 20.0, "3"))
    mana: ResourceSettings = field(default_factory=lambda: ResourceSettings(True, 50.0, "2"))


def settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".config"
    return root / "HPBarWatcher" / "settings.json"


def load_settings(path: Path | None = None) -> AppSettings:
    target = path or settings_path()
    if not target.exists():
        return AppSettings()
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return AppSettings(
            region=Region.from_dict(data.get("region")),
            always_on_top=bool(data.get("always_on_top", False)),
            auto_actions_enabled=bool(data.get("auto_actions_enabled", False)),
            key_hold_ms=_bounded_int(data.get("key_hold_ms", 50), 20, 500, 50),
            bar_width_px=_bounded_int(data.get("bar_width_px", 82), 40, 240, 82),
            calibration_screen_width_px=_optional_positive_int(
                data.get("calibration_screen_width_px")
            ),
            calibration_screen_height_px=_optional_positive_int(
                data.get("calibration_screen_height_px")
            ),
            poll_interval_ms=_bounded_int(data.get("poll_interval_ms", 50), 33, 250, 50),
            hp=_resource_from_dict(data.get("hp"), ResourceSettings(True, 30.0, "1")),
            es=_resource_from_dict(data.get("es"), ResourceSettings(True, 20.0, "3")),
            mana=_resource_from_dict(data.get("mana"), ResourceSettings(True, 50.0, "2")),
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return AppSettings()


def save_settings(settings: AppSettings, path: Path | None = None) -> Path:
    target = path or settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(settings)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _bounded_int(value: Any, minimum: int, maximum: int, fallback: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))
    except (TypeError, ValueError):
        return fallback


def _optional_positive_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if 0 < parsed <= 32768 else None


def _resource_from_dict(data: Any, fallback: ResourceSettings) -> ResourceSettings:
    if not isinstance(data, dict):
        return fallback
    try:
        threshold = float(data.get("threshold", fallback.threshold))
        threshold = max(0.0, min(100.0, threshold))
    except (TypeError, ValueError):
        threshold = fallback.threshold

    key = str(data.get("key", fallback.key)).strip()[:20] or fallback.key
    modifier_value = str(data.get("modifier", "")).strip().lower()
    modifier = modifier_value if modifier_value in ("ctrl", "shift") else None

    # Also accept a combined display label in settings written by an
    # intermediate development build that did not persist modifier separately.
    if modifier is None and "+" in key:
        prefix, primary = key.split("+", 1)
        if prefix.strip().lower() in ("ctrl", "shift"):
            modifier = prefix.strip().lower()
            key = primary.strip() or fallback.key

    scan_code = _bounded_int(data.get("scan_code", 0), 0, 0xFF, 0)
    return ResourceSettings(
        enabled=bool(data.get("enabled", fallback.enabled)),
        threshold=threshold,
        key=key,
        scan_code=scan_code,
        extended=bool(data.get("extended", False)),
        modifier=modifier,
    )
