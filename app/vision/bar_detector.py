"""Track the game's fixed-size HP and Mana bars while their screen position moves."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BarBand:
    """A colored fill segment observed across several adjacent scan lines."""

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
    message: str = "Пара HP/Mana не обнаружена"


class BarDetector:
    """Find and track a translated pair of resource bars in the selected region.

    The configured width is the constant full inner width, not the currently
    visible colored width. Horizontal and vertical movement changes only the
    tracked origin. HP and Mana are paired using their fixed relative layout;
    ES is measured relative to the current HP position.
    """

    EXPECTED_CENTER_GAP = 8.0
    MIN_CENTER_GAP = 4.0
    MAX_CENTER_GAP = 12.0
    MAX_X_GAP = 4
    MAX_TRACKING_MISSES = 3
    MIN_CONFIDENCE = 0.62

    def __init__(self, bar_width_px: int = 82, min_fill_px: int = 1) -> None:
        self.bar_width_px = max(20, int(bar_width_px))
        self.min_fill_px = max(1, int(min_fill_px))
        self._last_position: tuple[float, float, float] | None = None
        self._missed_frames = 0

    def reset(self) -> None:
        """Forget the previous position (for example when monitoring restarts)."""
        self._last_position = None
        self._missed_frames = 0

    def detect(self, rgb: np.ndarray) -> ResourceReadout:
        if rgb is None or rgb.ndim != 3 or rgb.shape[2] < 3 or rgb.size == 0:
            return self._miss("Область захвата пуста или имеет неверный формат")

        pixels = rgb[:, :, :3].astype(np.int16, copy=False)
        red, green, blue = pixels[:, :, 0], pixels[:, :, 1], pixels[:, :, 2]

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
            return self._miss("Пара HP/Mana не обнаружена; автонажатия приостановлены")

        hp_band, mana_band = pair
        vertical_gap = mana_band.y_center - hp_band.y_center
        x_gap = abs(hp_band.x - mana_band.x)
        confidence = self._pair_confidence(hp_band, mana_band, vertical_gap, x_gap)
        if confidence < self.MIN_CONFIDENCE:
            return self._miss("Положение баров определено недостаточно надёжно")

        # Keep a shared positional anchor for the next frame. This is a soft
        # preference only: _choose_pair still examines the entire ROI.
        self._last_position = (
            (hp_band.x + mana_band.x) / 2.0,
            hp_band.y_center,
            mana_band.y_center,
        )
        self._missed_frames = 0

        return ResourceReadout(
            detected=True,
            hp=self._percent(hp_band.width),
            es=self._detect_es(es_mask, hp_band),
            mana=self._percent(mana_band.width),
            confidence=confidence,
            bar_x=hp_band.x,
            hp_y=hp_band.y_center,
            mana_y=mana_band.y_center,
            message="HP/Mana обнаружены; положение отслеживается",
        )

    def _miss(self, message: str) -> ResourceReadout:
        self._missed_frames += 1
        if self._missed_frames >= self.MAX_TRACKING_MISSES:
            self._last_position = None
        return ResourceReadout(False, message=message)

    def _percent(self, fill_width: float) -> float:
        # The denominator is always the calibrated full width, never the
        # measured fill width or the current X coordinate.
        return round(max(0.0, min(100.0, fill_width / self.bar_width_px * 100.0)), 1)

    def _find_bands(self, mask: np.ndarray) -> list[BarBand]:
        """Group all matching scan-line runs, not just the longest run per row."""
        tracks: list[list[tuple[int, int, int]]] = []
        for y in range(mask.shape[0]):
            runs = [
                (y, x, width)
                for x, width in self._runs(mask[y])
                if self.min_fill_px <= width <= self.bar_width_px + 2
            ]
            assignments: list[tuple[float, int, int]] = []
            for track_index, track in enumerate(tracks):
                prev_y, prev_x, prev_width = track[-1]
                row_gap = y - prev_y
                if not (1 <= row_gap <= 2):
                    continue
                for run_index, (_, x, width) in enumerate(runs):
                    x_delta = abs(x - prev_x)
                    width_delta = abs(width - prev_width)
                    width_tolerance = max(6.0, prev_width * 0.15)
                    if x_delta <= 3 and width_delta <= width_tolerance:
                        cost = x_delta + width_delta * 0.25 + (row_gap - 1) * 1.5
                        assignments.append((cost, track_index, run_index))

            used_tracks: set[int] = set()
            used_runs: set[int] = set()
            for _, track_index, run_index in sorted(assignments):
                if track_index in used_tracks or run_index in used_runs:
                    continue
                tracks[track_index].append(runs[run_index])
                used_tracks.add(track_index)
                used_runs.add(run_index)

            for run_index, run in enumerate(runs):
                if run_index not in used_runs:
                    tracks.append([run])

        bands: list[BarBand] = []
        for rows in tracks:
            if len(rows) < 2:
                continue
            widths = np.asarray([row[2] for row in rows], dtype=np.float32)
            starts = np.asarray([row[1] for row in rows], dtype=np.float32)
            bands.append(
                BarBand(
                    x=int(round(float(np.median(starts)))),
                    width=int(round(float(np.median(widths)))),
                    y_top=min(row[0] for row in rows),
                    y_bottom=max(row[0] for row in rows),
                    rows=len(rows),
                )
            )
        return bands

    @staticmethod
    def _runs(row: np.ndarray) -> list[tuple[int, int]]:
        indices = np.flatnonzero(row)
        if indices.size == 0:
            return []
        split_points = np.where(np.diff(indices) > 1)[0] + 1
        groups = np.split(indices, split_points)
        return [
            (int(group[0]), int(group[-1] - group[0] + 1))
            for group in groups
            if group.size
        ]

    def _choose_pair(
        self, hp_bands: list[BarBand], mana_bands: list[BarBand]
    ) -> tuple[BarBand, BarBand] | None:
        best: tuple[float, BarBand, BarBand] | None = None
        for hp in hp_bands:
            for mana in mana_bands:
                vertical_gap = mana.y_center - hp.y_center
                x_gap = abs(mana.x - hp.x)
                if not (self.MIN_CENTER_GAP <= vertical_gap <= self.MAX_CENTER_GAP):
                    continue
                if x_gap > self.MAX_X_GAP:
                    continue

                # Geometry and stable five-row structure dominate the score.
                score = (
                    min(hp.rows, 5) * 2.0
                    + min(mana.rows, 5) * 2.0
                    - abs(vertical_gap - self.EXPECTED_CENTER_GAP) * 1.2
                    - x_gap * 1.1
                )
                if self._last_position is not None and self._missed_frames < self.MAX_TRACKING_MISSES:
                    old_x, old_hp_y, old_mana_y = self._last_position
                    movement = (
                        abs((hp.x + mana.x) / 2.0 - old_x)
                        + 0.75 * abs(hp.y_center - old_hp_y)
                        + 0.75 * abs(mana.y_center - old_mana_y)
                    )
                    # Soft tracking preference; never excludes a new location.
                    score -= min(8.0, movement * 0.12)

                if best is None or score > best[0]:
                    best = (score, hp, mana)
        return (best[1], best[2]) if best else None

    def _pair_confidence(
        self, hp: BarBand, mana: BarBand, vertical_gap: float, x_gap: int
    ) -> float:
        row_quality = (min(hp.rows, 5) + min(mana.rows, 5)) / 10.0
        geometry_penalty = abs(vertical_gap - self.EXPECTED_CENTER_GAP) * 0.015 + x_gap * 0.015
        confidence = 0.55 + 0.45 * row_quality - geometry_penalty
        return round(max(0.0, min(1.0, confidence)), 3)

    def _detect_es(self, mask: np.ndarray, hp: BarBand) -> float:
        candidates: list[int] = []
        center = hp.y_center
        for y in range(max(0, hp.y_top - 4), min(mask.shape[0], hp.y_bottom + 5)):
            distance = abs(y - center)
            if not (1.5 <= distance <= 3.5):
                continue
            for x, width in self._runs(mask[y]):
                if self.min_fill_px <= width <= self.bar_width_px + 2 and abs(x - hp.x) <= 3:
                    candidates.append(width)
        if not candidates:
            return 0.0
        return self._percent(float(np.median(np.asarray(candidates, dtype=np.float32))))
