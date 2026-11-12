"""Background camera and MediaPipe worker for the Qt control room."""
from __future__ import annotations

import threading
import time

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from mouse_controller import ControllerSettings, MouseController


class TrackingWorker(QThread):
    frame_ready = Signal(QImage)
    status_changed = Signal(str)
    gesture_changed = Signal(str)
    error_occurred = Signal(str)

    def __init__(self, camera_index: int, settings: ControllerSettings,
                 capture_factory=None, detector_factory=None, cv_module=None):
        super().__init__()
        self.camera_index = camera_index
        self._settings = settings
        self._capture_factory = capture_factory
        self._detector_factory = detector_factory
        self._cv_module = cv_module
        self._lock = threading.Lock()
        self._control_enabled = False
        self._stop_event = threading.Event()

    def configure(self, settings: ControllerSettings, control_enabled: bool) -> None:
        with self._lock:
            self._settings = settings
            self._control_enabled = bool(control_enabled)

    def request_stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        capture = None
        detector = None
        cv = self._cv_module
        try:
            if cv is None:
                import cv2 as cv
            if self._detector_factory is None:
                import HandTracking as tracking
                detector_factory = tracking.HandDetector
            else:
                detector_factory = self._detector_factory
            capture = (
                self._capture_factory(self.camera_index)
                if self._capture_factory else cv.VideoCapture(self.camera_index)
            )
            if not capture.isOpened():
                raise RuntimeError(f"Camera {self.camera_index} is unavailable. Check its connection or choose another camera.")
            capture.set(cv.CAP_PROP_FRAME_WIDTH, 640)
            capture.set(cv.CAP_PROP_FRAME_HEIGHT, 480)
            detector = detector_factory(max_hands=1)
            controller = MouseController()
            controller.reset()
            self.status_changed.emit(f"Connected · camera {self.camera_index}")
            last_time = time.perf_counter()

            while not self._stop_event.is_set():
                success, frame = capture.read()
                if not success or frame is None:
                    raise RuntimeError("Camera stopped returning frames. Reconnect it and try again.")
                frame = cv.flip(frame, 1)
                frame = detector.find_hands(frame)
                landmarks, _ = detector.find_position(frame, draw=True)
                fingers = detector.fingers_up() if landmarks else [0] * 5
                index_point = tuple(landmarks[8][1:]) if len(landmarks) > 8 else None
                pinch_distance = None
                if len(landmarks) > 12 and fingers[1:3] == [1, 1]:
                    pinch_distance, frame, _ = detector.find_distance(8, 12, frame)

                with self._lock:
                    settings = self._settings
                    enabled = self._control_enabled
                controller.configure(settings)
                controller.set_enabled(enabled)
                screen_size = None
                move_callback = click_callback = None
                if enabled:
                    import pyautogui
                    screen_size = pyautogui.size()
                    move_callback = lambda x, y: pyautogui.moveTo(x, y)
                    click_callback = pyautogui.click
                gesture, _ = controller.update(
                    fingers, index_point, pinch_distance,
                    (frame.shape[1], frame.shape[0]), screen_size,
                    move_callback, click_callback,
                )
                self.gesture_changed.emit(gesture)
                margin = settings.margin
                cv.rectangle(frame, (margin, margin),
                             (frame.shape[1] - margin, frame.shape[0] - margin),
                             (58, 180, 158), 1)
                control_text = "CONTROL ON" if enabled else "PREVIEW ONLY"
                cv.putText(frame, control_text, (18, 30), cv.FONT_HERSHEY_SIMPLEX,
                           0.65, (42, 140, 105) if enabled else (220, 180, 100), 2)
                now = time.perf_counter()
                fps = 1.0 / max(now - last_time, 1e-9)
                last_time = now
                cv.putText(frame, f"{fps:.0f} FPS", (frame.shape[1] - 105, 30),
                           cv.FONT_HERSHEY_SIMPLEX, 0.55, (235, 235, 235), 1)
                rgb = cv.cvtColor(frame, cv.COLOR_BGR2RGB)
                height, width = rgb.shape[:2]
                image = QImage(rgb.data, width, height, width * 3,
                               QImage.Format.Format_RGB888).copy()
                self.frame_ready.emit(image)

        except Exception as exc:
            self.error_occurred.emit(str(exc))
            self.status_changed.emit("Camera error")
        finally:
            cleanup_errors = []
            cleanup_actions = (
                (capture, "camera capture", "release"),
                (detector, "hand detector", "close"),
                (cv, "OpenCV windows", "destroyAllWindows"),
            )
            for resource, description, method_name in cleanup_actions:
                if resource is None:
                    continue
                try:
                    getattr(resource, method_name)()
                except Exception as exc:
                    cleanup_errors.append(f"{description}: {exc}")
            if cleanup_errors:
                message = "Resource cleanup failed: " + "; ".join(cleanup_errors)
                self.error_occurred.emit(message)
                self.status_changed.emit("Resource cleanup error")
            else:
                self.status_changed.emit("Stopped")
