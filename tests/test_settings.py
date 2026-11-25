from pathlib import Path

from app.config.settings import AppSettings, load_settings, save_settings


def test_always_on_top_setting_round_trips(tmp_path: Path):
    settings_file = tmp_path / "settings.json"
    settings = AppSettings(always_on_top=True)

    save_settings(settings, settings_file)
    loaded = load_settings(settings_file)

    assert loaded.always_on_top is True


def test_always_on_top_defaults_to_false_for_older_settings(tmp_path: Path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text('{"bar_width_px": 82}', encoding="utf-8")

    loaded = load_settings(settings_file)

    assert loaded.always_on_top is False



def test_auto_action_key_settings_round_trip(tmp_path: Path):
    from app.config.settings import ResourceSettings

    settings_file = tmp_path / "settings.json"
    settings = AppSettings(
        auto_actions_enabled=True,
        key_hold_ms=85,
        hp=ResourceSettings(True, 28.5, "Q", 0x10, False),
    )
    save_settings(settings, settings_file)
    loaded = load_settings(settings_file)

    assert loaded.auto_actions_enabled is True
    assert loaded.key_hold_ms == 85
    assert loaded.hp.key == "Q"
    assert loaded.hp.scan_code == 0x10
    assert loaded.hp.extended is False


def test_legacy_settings_keep_auto_actions_disabled(tmp_path: Path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text('{"hp": {"enabled": true, "threshold": 30, "key": "1"}}', encoding="utf-8")
    loaded = load_settings(settings_file)

    assert loaded.auto_actions_enabled is False
    assert loaded.key_hold_ms == 50
    assert loaded.hp.scan_code == 0
    assert loaded.calibration_screen_width_px is None
    assert loaded.calibration_screen_height_px is None


def test_calibration_resolution_round_trips(tmp_path: Path):
    settings_file = tmp_path / "settings.json"
    settings = AppSettings(
        bar_width_px=82,
        calibration_screen_width_px=1920,
        calibration_screen_height_px=1080,
    )

    save_settings(settings, settings_file)
    loaded = load_settings(settings_file)

    assert loaded.bar_width_px == 82
    assert loaded.calibration_screen_width_px == 1920
    assert loaded.calibration_screen_height_px == 1080


def test_invalid_calibration_resolution_is_ignored(tmp_path: Path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        '{"calibration_screen_width_px": 0, "calibration_screen_height_px": "bad"}',
        encoding="utf-8",
    )

    loaded = load_settings(settings_file)

    assert loaded.calibration_screen_width_px is None
    assert loaded.calibration_screen_height_px is None


def test_resource_modifier_round_trips(tmp_path: Path):
    from app.config.settings import ResourceSettings

    settings_file = tmp_path / "settings.json"
    settings = AppSettings(
        hp=ResourceSettings(True, 25.0, "Ctrl+Q", 0x10, False, "ctrl"),
        mana=ResourceSettings(True, 50.0, "Shift+2", 0x03, False, "shift"),
    )

    save_settings(settings, settings_file)
    loaded = load_settings(settings_file)

    assert loaded.hp.key == "Ctrl+Q"
    assert loaded.hp.modifier == "ctrl"
    assert loaded.mana.key == "Shift+2"
    assert loaded.mana.modifier == "shift"


def test_legacy_combined_key_label_is_parsed_when_modifier_field_is_missing(tmp_path: Path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        '{"hp": {"enabled": true, "threshold": 30, "key": "Shift+Q", "scan_code": 16}}',
        encoding="utf-8",
    )

    loaded = load_settings(settings_file)

    assert loaded.hp.key == "Q"
    assert loaded.hp.modifier == "shift"
