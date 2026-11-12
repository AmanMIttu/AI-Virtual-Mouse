import pytest
from mouse_logic import is_click_gesture, is_move_gesture, map_coordinate, smooth_coordinate

def test_mapping_clamps_and_maps_endpoints():
    assert map_coordinate(-1, 0, 10, 0, 100) == 0
    assert map_coordinate(5, 0, 10, 0, 100) == 50
    assert map_coordinate(11, 0, 10, 0, 100) == 100

def test_mapping_rejects_empty_range():
    with pytest.raises(ValueError):
        map_coordinate(1, 2, 2, 0, 10)

def test_smoothing_and_gesture_edges():
    assert smooth_coordinate(None, 20, 4) == 20
    assert smooth_coordinate(0, 20, 4) == 5
    assert is_move_gesture([0, 1, 0, 0, 0])
    assert is_click_gesture([0, 1, 1, 0, 0], 30, 35)
    assert not is_click_gesture([0, 1, 1, 0, 0], 40, 35)
