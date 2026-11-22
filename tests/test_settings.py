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
