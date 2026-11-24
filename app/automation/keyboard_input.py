from __future__ import annotations

import ctypes
import os
import threading
from dataclasses import dataclass
from ctypes import wintypes


@dataclass(frozen=True)
class KeyBinding:
    """A physical key and an optional single modifier."""

    scan_code: int
    extended: bool = False
    modifier: str | None = None

    def __post_init__(self) -> None:
        modifier = (self.modifier or "").strip().lower() or None
        if modifier not in (None, "ctrl", "shift"):
            raise ValueError("Only Ctrl or Shift can be used as a modifier.")
        object.__setattr__(self, "modifier", modifier)


_LABELS = {
    "1": (0x02, False), "2": (0x03, False), "3": (0x04, False), "4": (0x05, False),
    "5": (0x06, False), "6": (0x07, False), "7": (0x08, False), "8": (0x09, False),
    "9": (0x0A, False), "0": (0x0B, False),
    "Q": (0x10, False), "W": (0x11, False), "E": (0x12, False), "R": (0x13, False),
    "T": (0x14, False), "Y": (0x15, False), "U": (0x16, False), "I": (0x17, False),
    "O": (0x18, False), "P": (0x19, False),
    "A": (0x1E, False), "S": (0x1F, False), "D": (0x20, False), "F": (0x21, False),
    "G": (0x22, False), "H": (0x23, False), "J": (0x24, False), "K": (0x25, False),
    "L": (0x26, False),
    "Z": (0x2C, False), "X": (0x2D, False), "C": (0x2E, False), "V": (0x2F, False),
    "B": (0x30, False), "N": (0x31, False), "M": (0x32, False),
    "ESC": (0x01, False), "TAB": (0x0F, False), "BACKSPACE": (0x0E, False),
    "ENTER": (0x1C, False), "SPACE": (0x39, False),
    "F1": (0x3B, False), "F2": (0x3C, False), "F3": (0x3D, False), "F4": (0x3E, False),
    "F5": (0x3F, False), "F6": (0x40, False), "F7": (0x41, False), "F8": (0x42, False),
    "F9": (0x43, False), "F10": (0x44, False), "F11": (0x57, False), "F12": (0x58, False),
    "LEFT": (0x4B, True), "UP": (0x48, True), "RIGHT": (0x4D, True), "DOWN": (0x50, True),
    "INSERT": (0x52, True), "DELETE": (0x53, True), "HOME": (0x47, True), "END": (0x4F, True),
}

_MODIFIER_BINDINGS = {
    "ctrl": KeyBinding(0x1D),
    "shift": KeyBinding(0x2A),
}
_FORBIDDEN_PRIMARY_KEYS = {
    (0x1D, False),  # Left Ctrl
    (0x1D, True),   # Right Ctrl
    (0x2A, False),  # Left Shift
    (0x36, False),  # Right Shift
}


def default_binding_for_label(label: str) -> KeyBinding | None:
    """Resolve a saved display label, including Ctrl+ or Shift+ combinations."""
    parts = label.strip().upper().split("+")
    modifier = None
    if len(parts) == 2 and parts[0] in ("CTRL", "SHIFT"):
        modifier = parts[0].lower()
        key_label = parts[1]
    elif len(parts) == 1:
        key_label = parts[0]
    else:
        return None

    value = _LABELS.get(key_label)
    if value is None:
        return None
    return KeyBinding(*value, modifier=modifier)


def normalize_native_scan_code(raw: int) -> KeyBinding:
    raw = int(raw)
    if raw <= 0:
        raise ValueError("Windows did not provide a hardware scan code.")
    prefix = (raw >> 8) & 0xFF
    if prefix == 0xE0:
        return KeyBinding(raw & 0xFF, True)
    if prefix == 0xE1:
        raise ValueError("Pause/Break is not supported.")
    if raw > 0xFF:
        raise ValueError(f"Unsupported scan code 0x{raw:X}.")
    return KeyBinding(raw, False)


def label_for_binding(binding: KeyBinding) -> str:
    key_label = next(
        (label for label, pair in _LABELS.items()
         if pair == (binding.scan_code, binding.extended)),
        f"Scan {binding.scan_code:02X}",
    )
    if binding.modifier == "ctrl":
        return f"Ctrl+{key_label}"
    if binding.modifier == "shift":
        return f"Shift+{key_label}"
    return key_label


def key_events_for_binding(
    binding: KeyBinding, *, key_up: bool = False
) -> tuple[tuple[KeyBinding, bool], ...]:
    """Return ordered (physical key, key-up) events for SendInput.

    A modifier is pressed before the primary key and released after it.
    """
    primary = KeyBinding(binding.scan_code, binding.extended)
    modifier = _MODIFIER_BINDINGS.get(binding.modifier)
    if modifier is None:
        return ((primary, key_up),)
    if key_up:
        return ((primary, True), (modifier, True))
    return ((modifier, False), (primary, False))


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUTUNION(ctypes.Union):
    # INPUT contains the complete Win32 union, not only KEYBDINPUT.
    # MOUSEINPUT is the largest member on 64-bit Windows (32 bytes).
    _fields_ = [
        ("mi", _MOUSEINPUT),
        ("ki", _KEYBDINPUT),
        ("hi", _HARDWAREINPUT),
    ]


class _INPUT(ctypes.Structure):
    _anonymous_ = ("data",)
    _fields_ = [
        ("type", wintypes.DWORD),
        ("data", _INPUTUNION),
    ]


_EXPECTED_INPUT_SIZE = 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28
if ctypes.sizeof(_INPUT) != _EXPECTED_INPUT_SIZE:
    raise RuntimeError(
        f"Invalid Win32 INPUT structure size: {ctypes.sizeof(_INPUT)}; "
        f"expected {_EXPECTED_INPUT_SIZE} for this architecture."
    )


class KeyboardSender:
    KEYBOARD = 1
    SCANCODE = 0x0008
    EXTENDED = 0x0001
    KEYUP = 0x0002

    def __init__(self):
        if os.name != "nt":
            raise OSError("Keyboard input is available only on Windows.")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.SendInput.argtypes = (
            wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int
        )
        self.user32.SendInput.restype = wintypes.UINT
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.GetWindowThreadProcessId.argtypes = (
            wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
        )
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.lock = threading.RLock()
        self.timers: dict[tuple[str | None, int, bool], threading.Timer] = {}

    def foreground_is_external(self):
        hwnd = self.user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value != os.getpid()

    def _make_input(self, binding: KeyBinding, key_up: bool = False) -> _INPUT:
        flags = self.SCANCODE | (self.EXTENDED if binding.extended else 0)
        if key_up:
            flags |= self.KEYUP
        return _INPUT(
            type=self.KEYBOARD,
            data=_INPUTUNION(ki=_KEYBDINPUT(0, binding.scan_code, flags, 0, 0)),
        )

    def _send_events(self, events: tuple[tuple[KeyBinding, bool], ...]) -> None:
        inputs = (_INPUT * len(events))(
            *(self._make_input(binding, key_up) for binding, key_up in events)
        )
        sent = self.user32.SendInput(
            len(events), inputs, ctypes.sizeof(_INPUT)
        )
        if sent != len(events):
            raise ctypes.WinError(ctypes.get_last_error())

    def _send_sequence(self, binding: KeyBinding, *, key_up: bool) -> None:
        self._send_events(key_events_for_binding(binding, key_up=key_up))

    def tap(self, binding: KeyBinding, hold_ms: int = 50):
        if not self.foreground_is_external():
            return False
        if not 1 <= binding.scan_code <= 0xFF:
            raise ValueError("Invalid scan code.")
        if (binding.scan_code, binding.extended) in _FORBIDDEN_PRIMARY_KEYS:
            raise ValueError("Ctrl and Shift must be used only as modifiers.")
        key = (binding.modifier, binding.scan_code, binding.extended)
        with self.lock:
            if key in self.timers:
                return False
            try:
                self._send_sequence(binding, key_up=False)
            except OSError:
                # A partial SendInput call must not leave a modifier stuck.
                try:
                    self._send_sequence(binding, key_up=True)
                except OSError:
                    pass
                raise
            timer = threading.Timer(
                max(20, min(500, int(hold_ms))) / 1000,
                self._release,
                args=(key, binding),
            )
            timer.daemon = True
            self.timers[key] = timer
            timer.start()
        return True

    def _release(self, key, binding: KeyBinding):
        with self.lock:
            if key not in self.timers:
                return
            self.timers.pop(key, None)
            try:
                self._send_sequence(binding, key_up=True)
            except OSError:
                pass

    def release_all(self):
        with self.lock:
            pending = list(self.timers.items())
            self.timers.clear()
            for key, timer in pending:
                timer.cancel()
                binding = KeyBinding(key[1], key[2], key[0])
                try:
                    self._send_sequence(binding, key_up=True)
                except OSError:
                    pass
