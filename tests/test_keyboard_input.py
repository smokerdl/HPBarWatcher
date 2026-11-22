import ctypes

import pytest

from app.automation.keyboard_input import (
    KeyBinding,
    _INPUT,
    default_binding_for_label,
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
    ],
)
def test_default_bindings_are_case_insensitive_and_physical(label, expected):
    assert default_binding_for_label(label) == expected


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


def test_binding_label_is_physical():
    assert label_for_binding(KeyBinding(0x10)) == "Q"
    assert label_for_binding(KeyBinding(0x4B, True)) == "LEFT"
