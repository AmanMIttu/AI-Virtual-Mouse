import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import importlib

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from mouse_controller import ControllerSettings
from tracking_worker import TrackingWorker
from virtual_mouse_app import MainWindow


@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication([])


def test_ui_launches_in_safe_preview_mode(qapp):
    window = MainWindow()
    window.show()
    qapp.processEvents()
    assert window.isVisible()
    assert window.control_toggle.isChecked() is False
    assert window.start_button.text() == "Start preview"
    assert window.camera.value() == 0
    window.close()


def test_settings_are_configurable(qapp):
    window = MainWindow()
    window.sensitivity.setValue(150)
    window.smoothing.setValue(9)
    window.threshold.setValue(48)
    settings = window._settings()
    assert settings.sensitivity == 1.5
    assert settings.smoothing == 9
    assert settings.pinch_threshold == 48
    window.close()


def test_start_stop_state_transitions(qapp):
    class FakeWorker(QObject):
        frame_ready = Signal(object)
        status_changed = Signal(str)
        gesture_changed = Signal(str)
        error_occurred = Signal(str)
        finished = Signal()

        def __init__(self, camera_index, settings):
            super().__init__()
            self.running = False
            self.configuration = (camera_index, settings)

        def isRunning(self):
            return self.running

        def configure(self, settings, control_enabled):
            self.control_enabled = control_enabled

        def start(self):
            self.running = True
            self.status_changed.emit("Connected · camera 0")

        def request_stop(self):
            self.running = False
            self.finished.emit()

    window = MainWindow(worker_factory=FakeWorker)
    window.start_tracking()
    qapp.processEvents()
    assert not window.start_button.isEnabled()
    assert window.stop_button.isEnabled()
    window.stop_tracking()
    qapp.processEvents()
    assert window.start_button.isEnabled()
    assert not window.stop_button.isEnabled()
    assert not window.control_toggle.isChecked()
    window.close()


def test_close_waits_responsively_for_worker_exit(qapp):
    class DeferredWorker(QObject):
        frame_ready = Signal(object)
        status_changed = Signal(str)
        gesture_changed = Signal(str)
        error_occurred = Signal(str)
        finished = Signal()

        def __init__(self, camera_index, settings):
            super().__init__()
            self.running = False
            self.stop_requested = False
            self.wait_calls = []

        def isRunning(self):
            return self.running

        def configure(self, settings, control_enabled):
            pass

        def start(self):
            self.running = True

        def request_stop(self):
            self.stop_requested = True

        def wait(self, timeout):
            self.wait_calls.append(timeout)
            return False

    window = MainWindow(worker_factory=DeferredWorker)
    window.start_tracking()
    worker = window.worker
    window.show()
    qapp.processEvents()

    window.close()
    qapp.processEvents()
    assert window.isVisible()
    assert worker.stop_requested
    assert worker.wait_calls == []
    assert "WAITING FOR CAMERA RELEASE" in window.status.text()

    worker.running = False
    worker.finished.emit()
    QTest.qWait(100)
    assert not window.isVisible()
    assert not window._close_pending


def test_worker_stop_releases_camera_and_detector():
    import numpy as np

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    worker_ref = {}

    class FakeCapture:
        released = False
        def isOpened(self):
            return True
        def set(self, *_):
            return True
        def read(self):
            worker_ref["worker"].request_stop()
            return True, frame.copy()
        def release(self):
            self.released = True

    class FakeDetector:
        closed = False
        def __init__(self, **_):
            pass
        def find_hands(self, image):
            return image
        def find_position(self, image, draw=True):
            return [], ()
        def fingers_up(self):
            return [0] * 5
        def close(self):
            self.closed = True

    class FakeCV:
        CAP_PROP_FRAME_WIDTH = 3
        CAP_PROP_FRAME_HEIGHT = 4
        COLOR_BGR2RGB = 1
        FONT_HERSHEY_SIMPLEX = 0
        def flip(self, image, _):
            return image
        def rectangle(self, *_):
            pass
        def putText(self, *_):
            pass
        def cvtColor(self, image, _):
            return image
        def destroyAllWindows(self):
            pass

    capture = FakeCapture()
    detector = FakeDetector()
    worker = TrackingWorker(
        0, ControllerSettings(), capture_factory=lambda _: capture,
        detector_factory=lambda **kwargs: detector, cv_module=FakeCV(),
    )
    worker_ref["worker"] = worker
    statuses = []
    worker.status_changed.connect(statuses.append)
    worker.run()

    assert capture.released
    assert detector.closed
    assert statuses[-1] == "Stopped"


def test_camera_unavailable_is_reported_without_mouse_input():
    class FakeCapture:
        def __init__(self):
            self.released = False
        def isOpened(self):
            return False
        def release(self):
            self.released = True

    class FakeCV:
        CAP_PROP_FRAME_WIDTH = 3
        CAP_PROP_FRAME_HEIGHT = 4
        def destroyAllWindows(self):
            pass

    capture = FakeCapture()
    worker = TrackingWorker(
        8, ControllerSettings(), capture_factory=lambda index: capture,
        detector_factory=lambda **kwargs: None, cv_module=FakeCV(),
    )
    errors = []
    worker.error_occurred.connect(errors.append)
    worker.run()
    assert capture.released
    assert errors and "Camera 8 is unavailable" in errors[0]


def test_legacy_module_import_has_no_camera_or_pointer_side_effects():
    module = importlib.import_module("VirtualMouse")
    assert callable(module.run)
