import ctypes

import pytest

from app.automation.keyboard_input import (
    KeyBinding,
    _INPUT,
    default_binding_for_label,
    key_events_for_binding,
    label_for_binding,
    normalize_native_scan_code,
)


def test_win32_input_structure_matches_windows_abi_size():
    expected_size = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
    assert ctypes.sizeof(_INPUT) == expected_size


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        ("1", KeyBinding(0x02)),
        ("2", KeyBinding(0x03)),
        ("3", KeyBinding(0x04)),
        ("q", KeyBinding(0x10)),
        ("Q", KeyBinding(0x10)),
        ("A", KeyBinding(0x1E)),
        ("F1", KeyBinding(0x3B)),
        ("Left", KeyBinding(0x4B, True)),
        ("Ctrl+Q", KeyBinding(0x10, False, "ctrl")),
        ("Shift+Space", KeyBinding(0x39, False, "shift")),
        ("CTRL+1", KeyBinding(0x02, False, "ctrl")),
    ],
)
def test_default_bindings_are_case_insensitive_and_physical(label, expected):
    assert default_binding_for_label(label) == expected


def test_unsupported_or_multiple_modifiers_are_not_resolved():
    assert default_binding_for_label("Ctrl+Shift+Q") is None
    assert default_binding_for_label("Alt+Q") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0x02, KeyBinding(0x02)),
        (0x10, KeyBinding(0x10)),
        (0xE04B, KeyBinding(0x4B, True)),
    ],
)
def test_normalize_native_scan_code(raw, expected):
    assert normalize_native_scan_code(raw) == expected


def test_invalid_scan_codes_are_rejected():
    with pytest.raises(ValueError):
        normalize_native_scan_code(0)
    with pytest.raises(ValueError):
        normalize_native_scan_code(0xE11D)


def test_binding_label_is_physical_and_includes_single_modifier():
    assert label_for_binding(KeyBinding(0x10)) == "Q"
    assert label_for_binding(KeyBinding(0x4B, True)) == "LEFT"
    assert label_for_binding(KeyBinding(0x10, False, "ctrl")) == "Ctrl+Q"
    assert label_for_binding(KeyBinding(0x39, False, "shift")) == "Shift+SPACE"


def test_modifier_must_be_ctrl_or_shift():
    with pytest.raises(ValueError):
        KeyBinding(0x10, False, "alt")
    with pytest.raises(ValueError):
        KeyBinding(0x10, False, "ctrl+shift")


def test_modifier_is_pressed_before_primary_key_and_released_after_it():
    binding = KeyBinding(0x10, False, "ctrl")

    assert key_events_for_binding(binding) == (
        (KeyBinding(0x1D), False),
        (KeyBinding(0x10), False),
    )
    assert key_events_for_binding(binding, key_up=True) == (
        (KeyBinding(0x10), True),
        (KeyBinding(0x1D), True),
    )


def test_shift_sequence_uses_only_one_modifier():
    binding = KeyBinding(0x39, False, "shift")

    assert key_events_for_binding(binding) == (
        (KeyBinding(0x2A), False),
        (KeyBinding(0x39), False),
    )
