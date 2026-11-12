"""Gesture-to-pointer decisions with an opt-in, injected action boundary."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from mouse_logic import is_click_gesture, is_move_gesture, map_coordinate, smooth_coordinate


@dataclass(frozen=True)
class ControllerSettings:
    margin: int = 80
    smoothing: float = 7.0
    sensitivity: float = 1.0
    pinch_threshold: float = 35.0


class MouseController:
    """Translate gestures to callbacks; disabled controllers never invoke them."""

    def __init__(self) -> None:
        self.enabled = False
        self.settings = ControllerSettings()
        self._previous_x: float | None = None
        self._previous_y: float | None = None
        self._click_armed = True

    def configure(self, settings: ControllerSettings) -> None:
        self.settings = settings

    def set_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled and not self.enabled:
            # Require pinch release after opting in, preventing an immediate click.
            self._click_armed = False
        elif not enabled:
            self._click_armed = True
        self.enabled = enabled

    def reset(self) -> None:
        self._previous_x = self._previous_y = None
        self._click_armed = True

    def update(
        self,
        fingers: list[int],
        index_point: tuple[int, int] | None,
        pinch_distance: float | None,
        frame_size: tuple[int, int],
        screen_size: tuple[int, int] | None = None,
        move_pointer: Callable[[int, int], None] | None = None,
        click_pointer: Callable[[], None] | None = None,
    ) -> tuple[str, tuple[int, int] | None]:
        """Return a UI gesture label and cursor target; actions require opt-in."""
        move = is_move_gesture(fingers)
        pinching = (
            pinch_distance is not None
            and is_click_gesture(fingers, pinch_distance, self.settings.pinch_threshold)
        )
        target = None
        if move and index_point is not None:
            frame_width, frame_height = frame_size
            margin = self.settings.margin
            x = map_coordinate(index_point[0], margin, frame_width - margin, 0, 1)
            y = map_coordinate(index_point[1], margin, frame_height - margin, 0, 1)
            x = min(max(0.5 + (x - 0.5) * self.settings.sensitivity, 0), 1)
            y = min(max(0.5 + (y - 0.5) * self.settings.sensitivity, 0), 1)
            if screen_size is not None:
                screen_width, screen_height = screen_size
                raw_x, raw_y = x * (screen_width - 1), y * (screen_height - 1)
                current_x = smooth_coordinate(self._previous_x, raw_x, self.settings.smoothing)
                current_y = smooth_coordinate(self._previous_y, raw_y, self.settings.smoothing)
                self._previous_x, self._previous_y = current_x, current_y
                target = (round(current_x), round(current_y))
                if self.enabled and move_pointer is not None:
                    move_pointer(*target)
            self._click_armed = True
            return ("Pointer active" if self.enabled else "Move · preview only"), target

        if pinching:
            if self._click_armed:
                self._click_armed = False
                if self.enabled and click_pointer is not None:
                    click_pointer()
                    return "Click sent", None
                return "Pinch · preview only", None
            return "Pinch held", None

        self._click_armed = True
        if len(fingers) >= 3 and fingers[1:3] == [1, 1]:
            return "Click gesture · bring fingers closer", None
        return "No active gesture", None
