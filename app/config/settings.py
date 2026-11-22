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


@dataclass
class AppSettings:
    region: Region | None = None
    always_on_top: bool = False
    bar_width_px: int = 82
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
            bar_width_px=_bounded_int(data.get("bar_width_px", 82), 40, 240, 82),
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


def _resource_from_dict(data: Any, fallback: ResourceSettings) -> ResourceSettings:
    if not isinstance(data, dict):
        return fallback
    try:
        threshold = float(data.get("threshold", fallback.threshold))
        threshold = max(0.0, min(100.0, threshold))
    except (TypeError, ValueError):
        threshold = fallback.threshold
    key = str(data.get("key", fallback.key)).strip()[:20] or fallback.key
    return ResourceSettings(bool(data.get("enabled", fallback.enabled)), threshold, key)
