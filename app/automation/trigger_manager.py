"""Safe threshold-crossing state for individual resource bars."""
from __future__ import annotations


class ThresholdTrigger:
    """Fire once on a downward crossing; re-arm at threshold or above.

    A missing or disabled resource disarms the trigger, so a bar that
    reappears already below threshold cannot create a synthetic crossing.
    """

    def __init__(self) -> None:
        self._armed = False

    def reset(self) -> None:
        self._armed = False

    def update(
        self,
        value: float,
        threshold: float,
        *,
        detected: bool,
        enabled: bool = True,
    ) -> bool:
        if not detected or not enabled:
            self._armed = False
            return False
        if value >= threshold:
            self._armed = True
            return False
        if self._armed:
            self._armed = False
            return True
        return False
