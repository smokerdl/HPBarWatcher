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
