from __future__ import annotations

import numpy as np
import pytest

from app.vision.bar_detector import BarDetector

HP_GREEN = (30, 118, 40)
ES_AQUA = (130, 194, 182)
MANA_BLUE = (27, 69, 165)
BACKGROUND = (18, 23, 31)


def draw_pair(image: np.ndarray, *, x: int, y: int, hp_px: int, es_px: int, mana_px: int) -> None:
    if es_px:
        image[y - 1, x : x + es_px] = ES_AQUA
        image[y + 5, x : x + es_px] = ES_AQUA
    image[y : y + 5, x : x + hp_px] = HP_GREEN
    image[y + 8 : y + 13, x : x + mana_px] = MANA_BLUE


def frame(*, x: int = 24, y: int = 13, hp_px: int = 41, es_px: int = 0, mana_px: int = 82) -> np.ndarray:
    image = np.full((64, 160, 3), BACKGROUND, dtype=np.uint8)
    draw_pair(image, x=x, y=y, hp_px=hp_px, es_px=es_px, mana_px=mana_px)
    return image


def test_tracks_horizontal_and_vertical_translation_with_constant_percentages():
    detector = BarDetector(82)
    first = detector.detect(frame(x=24, y=13, hp_px=41))
    second = detector.detect(frame(x=31, y=18, hp_px=41))

    assert first.detected and second.detected
    assert first.hp == second.hp == pytest.approx(50.0, abs=0.1)
    assert first.mana == second.mana == pytest.approx(100.0, abs=0.1)
    assert first.bar_x == 24
    assert second.bar_x == 31
    assert second.hp_y == pytest.approx(20.0)
    assert second.mana_y == pytest.approx(28.0)


def test_prefers_previous_pair_when_a_similar_decoy_pair_is_visible():
    detector = BarDetector(82)
    assert detector.detect(frame(x=22, y=13, hp_px=65, mana_px=72)).detected

    image = frame(x=22, y=13, hp_px=65, mana_px=72)
    draw_pair(image, x=72, y=35, hp_px=65, es_px=0, mana_px=72)
    result = detector.detect(image)

    assert result.detected
    assert result.bar_x == 22
    assert result.hp_y == pytest.approx(15.0)


def test_reacquires_pair_at_new_position_after_a_brief_missed_frame():
    detector = BarDetector(82)
    assert detector.detect(frame(x=20, y=12, hp_px=60, mana_px=60)).detected
    missing = np.full((64, 160, 3), BACKGROUND, dtype=np.uint8)
    assert not detector.detect(missing).detected

    result = detector.detect(frame(x=37, y=22, hp_px=30, mana_px=55))
    assert result.detected
    assert result.bar_x == 37
    assert result.hp == pytest.approx(36.6, abs=0.1)


def test_percentage_uses_full_configured_width_not_current_fill_width():
    detector = BarDetector(82)
    result = detector.detect(frame(x=40, y=15, hp_px=20, mana_px=20))

    assert result.detected
    assert result.hp == pytest.approx(24.4, abs=0.1)
    assert result.mana == pytest.approx(24.4, abs=0.1)


def test_scene_with_only_one_color_bar_is_not_accepted_as_a_hud():
    detector = BarDetector(82)
    image = np.full((64, 160, 3), BACKGROUND, dtype=np.uint8)
    image[13:18, 24:106] = HP_GREEN

    assert not detector.detect(image).detected


def test_tracker_forgets_position_after_repeated_detection_losses():
    detector = BarDetector(82)
    assert detector.detect(frame()).detected
    missing = np.full((64, 160, 3), BACKGROUND, dtype=np.uint8)
    for _ in range(detector.MAX_TRACKING_MISSES):
        assert not detector.detect(missing).detected
    assert detector._last_position is None
