from __future__ import annotations

import numpy as np
import pytest

from app.vision.bar_detector import BarDetector, scaled_bar_width_px


BAR_WIDTH = 82
HP_GREEN = (30, 118, 40)
ES_AQUA = (130, 194, 182)
MANA_BLUE = (27, 69, 165)


def make_sample(hp_px: int, es_px: int, mana_px: int) -> np.ndarray:
    image = np.full((48, 140, 3), (18, 23, 31), dtype=np.uint8)
    x, y = 24, 13
    # ES is drawn as two bright edge strips on top of the green HP bar.
    if es_px:
        image[y - 1, x : x + es_px] = ES_AQUA
        image[y + 5, x : x + es_px] = ES_AQUA
    image[y : y + 5, x : x + hp_px] = HP_GREEN
    image[y + 8 : y + 13, x : x + mana_px] = MANA_BLUE
    return image


@pytest.mark.parametrize(
    ("hp_px", "es_px", "mana_px", "expected"),
    [
        (56, 0, 82, (68.3, 0.0, 100.0)),
        (82, 0, 82, (100.0, 0.0, 100.0)),
        (82, 56, 82, (100.0, 68.3, 100.0)),
        (82, 82, 82, (100.0, 100.0, 100.0)),
        (82, 82, 63, (100.0, 100.0, 76.8)),
    ],
)
def test_reference_states(hp_px, es_px, mana_px, expected):
    result = BarDetector(BAR_WIDTH).detect(make_sample(hp_px, es_px, mana_px))
    assert result.detected
    assert result.hp == pytest.approx(expected[0], abs=0.1)
    assert result.es == pytest.approx(expected[1], abs=0.1)
    assert result.mana == pytest.approx(expected[2], abs=0.1)


def test_empty_scene_is_not_interpreted_as_zero_resources():
    image = np.full((100, 160, 3), (18, 23, 31), dtype=np.uint8)
    result = BarDetector(BAR_WIDTH).detect(image)
    assert not result.detected


def test_one_colored_bar_is_not_enough_to_confirm_character_hud():
    image = np.full((48, 140, 3), (18, 23, 31), dtype=np.uint8)
    image[13:18, 24:106] = HP_GREEN
    result = BarDetector(BAR_WIDTH).detect(image)
    assert not result.detected


@pytest.mark.parametrize(
    ("current_width", "expected_width"),
    [
        (1920, 82),
        (1600, 68),
        (1280, 55),
        (2560, 109),
    ],
)
def test_bar_width_scales_with_current_screen_width(current_width, expected_width):
    assert scaled_bar_width_px(82, 1920, current_width) == expected_width


def test_scaled_width_gives_full_resources_at_1600x900_scale():
    effective_width = scaled_bar_width_px(82, 1920, 1600)
    result = BarDetector(effective_width).detect(make_sample(68, 0, 68))

    assert result.detected
    assert result.hp == pytest.approx(100.0, abs=0.1)
    assert result.mana == pytest.approx(100.0, abs=0.1)


@pytest.mark.parametrize(
    ("reference_width", "current_width"),
    [
        (None, 1600),
        (1920, None),
        (0, 1600),
        (1920, 0),
    ],
)
def test_missing_or_invalid_screen_width_keeps_configured_value(
    reference_width, current_width
):
    assert scaled_bar_width_px(82, reference_width, current_width) == 82
