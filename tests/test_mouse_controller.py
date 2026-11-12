from mouse_controller import ControllerSettings, MouseController


def test_preview_never_calls_pointer_callbacks():
    calls = []
    controller = MouseController()
    controller.configure(ControllerSettings(smoothing=1, sensitivity=1.0))
    gesture, target = controller.update(
        [0, 1, 0, 0, 0], (320, 240), None, (640, 480), (1920, 1080),
        lambda *xy: calls.append(("move", xy)), lambda: calls.append(("click",)),
    )
    assert gesture == "Move · preview only"
    assert target == (960, 540)
    assert calls == []


def test_enabling_control_requires_pinch_release_before_click():
    controller = MouseController()
    calls = []
    controller.set_enabled(True)
    args = ([0, 1, 1, 0, 0], (320, 240), 10.0, (640, 480), (1920, 1080),
            lambda *xy: calls.append(("move", xy)), lambda: calls.append(("click",)))
    assert controller.update(*args)[0] == "Pinch held"
    assert calls == []
    controller.update([0, 1, 0, 0, 0], (320, 240), None, (640, 480), (1920, 1080))
    assert controller.update(*args)[0] == "Click sent"
    assert calls == [("click",)]
    assert controller.update(*args)[0] == "Pinch held"
    assert calls == [("click",)]
