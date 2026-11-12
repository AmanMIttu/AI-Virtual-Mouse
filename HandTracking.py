"""MediaPipe Hands wrapper with explicit lifecycle and safe empty-frame behavior."""
import math
import time

import cv2
import mediapipe as mp

class HandDetector:
    TIP_IDS = [4, 8, 12, 16, 20]

    def __init__(self, static_image_mode: bool = False, max_hands: int = 2,
                 detection_confidence: float = 0.7, tracking_confidence: float = 0.5):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=static_image_mode, max_num_hands=max_hands,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence)
        self.drawer = mp.solutions.drawing_utils
        self.results = None
        self.landmarks = []

    def find_hands(self, image, draw: bool = True):
        self.results = self.hands.process(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
        if draw and self.results.multi_hand_landmarks:
            for hand in self.results.multi_hand_landmarks:
                self.drawer.draw_landmarks(image, hand, self.mp_hands.HAND_CONNECTIONS)
        return image

    def find_position(self, image, hand_no: int = 0, draw: bool = True):
        self.landmarks = []
        hands = self.results.multi_hand_landmarks if self.results else None
        if not hands or hand_no < 0 or hand_no >= len(hands):
            return self.landmarks, ()
        height, width = image.shape[:2]
        points = []
        for index, landmark in enumerate(hands[hand_no].landmark):
            x, y = int(landmark.x * width), int(landmark.y * height)
            self.landmarks.append([index, x, y])
            points.append((x, y))
            if draw:
                cv2.circle(image, (x, y), 5, (255, 0, 255), cv2.FILLED)
        box = (min(x for x, _ in points), min(y for _, y in points),
               max(x for x, _ in points), max(y for _, y in points))
        if draw:
            x1, y1, x2, y2 = box
            cv2.rectangle(image, (x1 - 20, y1 - 20), (x2 + 20, y2 + 20), (0, 255, 0), 2)
        return self.landmarks, box

    def fingers_up(self):
        if len(self.landmarks) < 21:
            return [0] * 5
        fingers = [int(self.landmarks[4][1] > self.landmarks[3][1])]  # Assumes right hand faces camera.
        fingers.extend(int(self.landmarks[tip][2] < self.landmarks[tip - 2][2])
                       for tip in self.TIP_IDS[1:])
        return fingers

    def find_distance(self, point_a: int, point_b: int, image, draw: bool = True, radius: int = 15, thickness: int = 3):
        x1, y1 = self.landmarks[point_a][1:]
        x2, y2 = self.landmarks[point_b][1:]
        center = ((x1 + x2) // 2, (y1 + y2) // 2)
        if draw:
            cv2.line(image, (x1, y1), (x2, y2), (255, 0, 255), thickness)
            cv2.circle(image, (x1, y1), radius, (255, 0, 255), cv2.FILLED)
            cv2.circle(image, (x2, y2), radius, (255, 0, 255), cv2.FILLED)
            cv2.circle(image, center, radius, (0, 0, 255), cv2.FILLED)
        return math.hypot(x2 - x1, y2 - y1), image, [x1, y1, x2, y2, *center]

    def close(self) -> None:
        self.hands.close()

    # Compatibility methods for existing notebook/tutorial usage.
    findHands = find_hands
    findPosition = find_position
    fingersUp = fingers_up
    findDistance = find_distance

def main() -> None:
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("Could not open camera index 0")
    detector = HandDetector(max_hands=1)
    previous_time = time.perf_counter()
    try:
        while True:
            ok, image = cap.read()
            if not ok:
                raise RuntimeError("Camera stopped returning frames")
            image = detector.find_hands(image)
            landmarks, _ = detector.find_position(image)
            if landmarks:
                cv2.putText(image, f"Index: {landmarks[8][1:]}", (10, 70), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 255), 2)
            now = time.perf_counter()
            fps = 1 / max(now - previous_time, 1e-9)
            previous_time = now
            cv2.putText(image, f"FPS: {fps:.0f}", (10, 35), cv2.FONT_HERSHEY_PLAIN, 2, (255, 0, 255), 2)
            cv2.imshow("Hand tracking (Q to quit)", image)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        detector.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
