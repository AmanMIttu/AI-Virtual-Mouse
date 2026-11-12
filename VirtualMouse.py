"""Legacy OpenCV preview entry point; system input is opt-in."""
from __future__ import annotations

import argparse
import time

from mouse_controller import ControllerSettings, MouseController


def run(camera: int = 0, width: int = 640, height: int = 480,
        margin: int = 80, smoothing: float = 7.0,
        sensitivity: float = 1.0, click_threshold: float = 35.0,
        enable_mouse_control: bool = False) -> None:
    """Run the legacy preview loop. Without explicit opt-in it is read-only."""
    import cv2
    import HandTracking as ht

    cap = cv2.VideoCapture(camera)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"Could not open camera index {camera}")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    detector = ht.HandDetector(max_hands=1)
    controller = MouseController()
    controller.configure(ControllerSettings(margin, smoothing, sensitivity, click_threshold))
    controller.set_enabled(enable_mouse_control)
    previous_time = time.perf_counter()
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("Camera stopped returning frames")
            frame = cv2.flip(frame, 1)
            frame = detector.find_hands(frame)
            landmarks, _ = detector.find_position(frame)
            fingers = detector.fingers_up() if landmarks else [0] * 5
            index = tuple(landmarks[8][1:]) if len(landmarks) > 8 else None
            distance = None
            if len(landmarks) > 12 and fingers[1:3] == [1, 1]:
                distance, frame, _ = detector.find_distance(8, 12, frame)
            screen_size = None
            mover = clicker = None
            if enable_mouse_control:
                import pyautogui
                screen_size = pyautogui.size()
                mover = pyautogui.moveTo
                clicker = pyautogui.click
            gesture, _ = controller.update(
                fingers, index, distance, (frame.shape[1], frame.shape[0]),
                screen_size, mover, clicker,
            )
            cv2.rectangle(frame, (margin, margin),
                          (frame.shape[1] - margin, frame.shape[0] - margin),
                          (255, 0, 255), 2)
            now = time.perf_counter()
            fps = 1 / max(now - previous_time, 1e-9)
            previous_time = now
            label = "CONTROL ON" if enable_mouse_control else "PREVIEW ONLY"
            cv2.putText(frame, f"{label} · {gesture} · {fps:.0f} FPS", (12, 32),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 0, 255), 2)
            cv2.imshow("AI Virtual Mouse — press Q to quit", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        detector.close()
        cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--margin", type=int, default=80)
    parser.add_argument("--smoothing", type=float, default=7.0)
    parser.add_argument("--sensitivity", type=float, default=1.0)
    parser.add_argument("--click-threshold", type=float, default=35.0)
    parser.add_argument("--enable-mouse-control", action="store_true",
                        help="explicitly enable real pointer movement and pinch clicks")
    args = parser.parse_args()
    run(args.camera, args.width, args.height, args.margin, args.smoothing,
        args.sensitivity, args.click_threshold, args.enable_mouse_control)


if __name__ == "__main__":
    main()
