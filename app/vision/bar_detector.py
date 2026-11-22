"""Color-based detector for the game's HP, energy shield and mana bars.

The first version is deliberately diagnostic: it reports measurements but never
sends keyboard input. The supplied reference crops show an 82 px inner bar width.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class BarBand:
    x: int
    width: int
    y_top: int
    y_bottom: int
    rows: int

    @property
    def y_center(self) -> float:
        return (self.y_top + self.y_bottom) / 2.0


@dataclass(frozen=True)
class ResourceReadout:
    detected: bool
    hp: float = 0.0
    es: float = 0.0
    mana: float = 0.0
    confidence: float = 0.0
    bar_x: int | None = None
    hp_y: float | None = None
    mana_y: float | None = None
    message: str = "HP-бар не обнаружен"


class BarDetector:
    """Detect the resource bars in a user-selected screen rectangle.

    Detection uses the green middle of HP, the blue Mana band and the brighter
    aqua top/bottom strokes used by ES. The full inner width is configurable.
    """

    def __init__(self, bar_width_px: int = 82, min_fill_px: int = 5) -> None:
        self.bar_width_px = max(20, int(bar_width_px))
        self.min_fill_px = max(2, int(min_fill_px))

    def detect(self, rgb: np.ndarray) -> ResourceReadout:
        if rgb is None or rgb.ndim != 3 or rgb.shape[2] < 3 or rgb.size == 0:
            return ResourceReadout(False, message="Нет изображения для анализа")

        pixels = rgb[:, :, :3].astype(np.int16, copy=False)
        red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]

        # Thresholds tolerate modest capture/compression color variation.
        hp_mask = (
            (green >= 65)
            & (green > red * 1.28)
            & (green > blue * 1.12)
        )
        mana_mask = (
            (blue >= 60)
            & (blue > red * 1.25)
            & (blue > green * 1.18)
        )
        es_mask = (
            (red >= 90)
            & (green >= 135)
            & (blue >= 130)
            & (green > red * 1.25)
            & (blue > red * 1.20)
            & (blue > green * 0.80)
        )

        hp_bands = self._find_bands(hp_mask)
        mana_bands = self._find_bands(mana_mask)
        pair = self._choose_pair(hp_bands, mana_bands)
        if pair is None:
            return ResourceReadout(False, message="HP-бар не обнаружен в выбранной области")

        hp_band, mana_band = pair
        hp_pct = self._percent(hp_band.width)
        mana_pct = self._percent(mana_band.width)
        es_pct = self._detect_es(es_mask, hp_band)

        confidence = min(1.0, 0.55 + 0.045 * min(hp_band.rows, 5) + 0.045 * min(mana_band.rows, 5))
        if abs(hp_band.x - mana_band.x) > 1:
            confidence -= 0.05
        return ResourceReadout(
            detected=True,
            hp=hp_pct,
            es=es_pct,
            mana=mana_pct,
            confidence=max(0.0, confidence),
            bar_x=hp_band.x,
            hp_y=hp_band.y_center,
            mana_y=mana_band.y_center,
            message="HP-бар обнаружен",
        )

    def _percent(self, fill_width: float) -> float:
        return round(max(0.0, min(100.0, fill_width / self.bar_width_px * 100.0)), 1)

    def _find_bands(self, mask: np.ndarray) -> list[BarBand]:
        row_runs: list[tuple[int, int, int]] = []
        for y in range(mask.shape[0]):
            runs = self._runs(mask[y])
            if runs:
                # Resource bars are a single, long run on each scanline.
                x, width = max(runs, key=lambda item: item[1])
                if width >= self.min_fill_px:
                    row_runs.append((y, x, width))

        bands: list[BarBand] = []
        current: list[tuple[int, int, int]] = []
        for item in row_runs:
            y, x, width = item
            if not current:
                current = [item]
                continue
            prev_y, prev_x, prev_width = current[-1]
            if y <= prev_y + 2 and abs(x - prev_x) <= 3 and abs(width - prev_width) <= 5:
                current.append(item)
            else:
                bands.extend(self._finish_band(current))
                current = [item]
        if current:
            bands.extend(self._finish_band(current))
        return bands

    def _finish_band(self, rows: list[tuple[int, int, int]]) -> list[BarBand]:
        if not rows:
            return []
        widths = np.asarray([row[2] for row in rows], dtype=np.float32)
        starts = np.asarray([row[1] for row in rows], dtype=np.float32)
        # A single bright pixel row may be scenery. Require at least two lines.
        if len(rows) < 2:
            return []
        return [
            BarBand(
                x=int(round(float(np.median(starts)))),
                width=int(round(float(np.median(widths)))),
                y_top=rows[0][0],
                y_bottom=rows[-1][0],
                rows=len(rows),
            )
        ]

    @staticmethod
    def _runs(row: np.ndarray) -> list[tuple[int, int]]:
        indices = np.flatnonzero(row)
        if indices.size == 0:
            return []
        split_points = np.where(np.diff(indices) > 1)[0] + 1
        groups = np.split(indices, split_points)
        return [(int(group[0]), int(group[-1] - group[0] + 1)) for group in groups if group.size]

    @staticmethod
    def _choose_pair(
        hp_bands: Iterable[BarBand], mana_bands: Iterable[BarBand]
    ) -> tuple[BarBand, BarBand] | None:
        best: tuple[float, BarBand, BarBand] | None = None
        for hp in hp_bands:
            for mana in mana_bands:
                vertical_gap = mana.y_center - hp.y_center
                x_gap = abs(mana.x - hp.x)
                if not (4.0 <= vertical_gap <= 12.0 and x_gap <= 4):
                    continue
                score = (
                    hp.rows + mana.rows
                    - abs(vertical_gap - 7.0) * 0.8
                    - x_gap * 2.0
                    + min(hp.width, mana.width) / 100.0
                )
                if best is None or score > best[0]:
                    best = (score, hp, mana)
        return (best[1], best[2]) if best else None

    def _detect_es(self, mask: np.ndarray, hp: BarBand) -> float:
        candidates: list[int] = []
        center = hp.y_center
        for y in range(max(0, hp.y_top - 4), min(mask.shape[0], hp.y_bottom + 5)):
            distance = abs(y - center)
            if not (1.5 <= distance <= 3.5):
                continue
            row_runs = self._runs(mask[y])
            for x, width in row_runs:
                if width >= self.min_fill_px and abs(x - hp.x) <= 3:
                    candidates.append(width)
        if not candidates:
            return 0.0
        return self._percent(float(np.median(np.asarray(candidates, dtype=np.float32))))
