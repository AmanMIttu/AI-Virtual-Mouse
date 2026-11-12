"""Pure coordinate and gesture helpers; importing this module has no I/O."""
from __future__ import annotations

def map_coordinate(value: float, input_min: float, input_max: float, output_min: float, output_max: float) -> float:
    if input_max <= input_min:
        raise ValueError("input_max must be greater than input_min")
    bounded = min(max(float(value), input_min), input_max)
    return output_min + (bounded - input_min) * (output_max - output_min) / (input_max - input_min)

def smooth_coordinate(previous: float | None, target: float, smoothing: float) -> float:
    if smoothing < 1:
        raise ValueError("smoothing must be at least 1")
    return float(target) if previous is None else previous + (target - previous) / smoothing

def is_move_gesture(fingers: list[int]) -> bool:
    return len(fingers) >= 3 and fingers[1:3] == [1, 0]

def is_click_gesture(fingers: list[int], distance: float, threshold: float) -> bool:
    return len(fingers) >= 3 and fingers[1:3] == [1, 1] and distance <= threshold
