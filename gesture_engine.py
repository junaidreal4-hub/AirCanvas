import math
import time

import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

from config import (
    FRAME_WIDTH, FRAME_HEIGHT,
    PINCH_THRESHOLD, PINCH_RELEASE, SMOOTHING,
)


def _dist(a, b, w, h):
    return math.hypot((a.x - b.x) * w, (a.y - b.y) * h)


def _smooth(prev, curr, alpha=SMOOTHING):
    if prev is None:
        return curr
    return (
        int(alpha * curr[0] + (1 - alpha) * prev[0]),
        int(alpha * curr[1] + (1 - alpha) * prev[1]),
    )


def _to_px(lm, w, h):
    return (int(lm.x * w), int(lm.y * h))


# Landmark indices (MediaPipe Hands topology)
FINGER_TIPS = [8, 12, 16, 20]   # index, middle, ring, pinky tips
FINGER_PIP  = [6, 10, 14, 18]   # the joint two below each tip


def get_extended_fingers(landmarks):
    """Returns [index, middle, ring, pinky] booleans — True = extended.

    Compares the tip against the PIP joint along the y-axis. Works while the
    hand is held roughly upright, which is the natural pose for drawing.
    """
    return [landmarks[tip].y < landmarks[pip].y
            for tip, pip in zip(FINGER_TIPS, FINGER_PIP)]


def is_fist(landmarks):
    """All four fingers folded."""
    return not any(get_extended_fingers(landmarks))


def is_index_only(landmarks):
    """Only the index finger is extended — the 'pen down' pose."""
    index, middle, ring, pinky = get_extended_fingers(landmarks)
    return index and not middle and not ring and not pinky


class HandState:
    """Per-hand tracked state, smoothed across frames."""

    def __init__(self):
        self.reset()

    def update(self, landmarks, w, h):
        thumb = landmarks[4]
        index = landmarks[8]

        self.present    = True
        self.pinch_dist = _dist(thumb, index, w, h)

        # Hysteresis: only flip the pinch flag when crossing a threshold,
        # leaving a dead zone in between so it never flickers.
        if self.pinch_dist < PINCH_THRESHOLD:
            self.pinching = True
        elif self.pinch_dist > PINCH_RELEASE:
            self.pinching = False

        mid_raw = (
            int((thumb.x + index.x) / 2 * w),
            int((thumb.y + index.y) / 2 * h),
        )
        self.pinch_point   = _smooth(self.prev_pinch_pt, mid_raw)
        self.prev_pinch_pt = self.pinch_point

        self.index_tip  = _smooth(self.prev_index, _to_px(index, w, h))
        self.prev_index = self.index_tip

        self.drawing = is_index_only(landmarks)
        self.fist    = is_fist(landmarks)

    def reset(self):
        self.present       = False
        self.pinching      = False
        self.pinch_point   = None
        self.pinch_dist    = 0
        self.prev_pinch_pt = None
        self.index_tip     = None
        self.prev_index    = None
        self.drawing       = False
        self.fist          = False


class GestureEngine:
    """Wraps the MediaPipe HandLandmarker (Tasks API) in VIDEO mode and
    exposes two semantic hands: the one you draw with and the one that
    controls brush size."""

    def __init__(self):
        base = mp_python.BaseOptions(model_asset_path="hand_landmarker.task")
        opts = vision.HandLandmarkerOptions(
            base_options=base,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.6,
            min_tracking_confidence=0.6,
        )
        self.detector           = vision.HandLandmarker.create_from_options(opts)
        self.draw_hand          = HandState()  # the hand you draw with
        self.size_hand          = HandState()  # the hand that controls brush size
        self.both_pinching      = False
        self.prev_two_hand_dist = None
        self._t0                = time.perf_counter()

    def process(self, rgb_frame):
        """Run detection on one RGB frame. Returns the two-hand pinch
        distance delta (px) when both hands are pinching, else 0."""
        mp_img       = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        timestamp_ms = int((time.perf_counter() - self._t0) * 1000)
        results      = self.detector.detect_for_video(mp_img, timestamp_ms)

        self.draw_hand.reset()
        self.size_hand.reset()

        if results.hand_landmarks:
            for i, landmarks in enumerate(results.hand_landmarks):
                # The frame is mirrored (cv2.flip) before we get here, so
                # MediaPipe's "Left" label corresponds to the user's right
                # hand on screen — the hand we draw with.
                label = results.handedness[i][0].display_name
                if label == "Left":
                    self.draw_hand.update(landmarks, FRAME_WIDTH, FRAME_HEIGHT)
                else:
                    self.size_hand.update(landmarks, FRAME_WIDTH, FRAME_HEIGHT)

        self.both_pinching = self.draw_hand.pinching and self.size_hand.pinching

        if self.both_pinching and self.draw_hand.pinch_point and self.size_hand.pinch_point:
            curr_dist = math.hypot(
                self.draw_hand.pinch_point[0] - self.size_hand.pinch_point[0],
                self.draw_hand.pinch_point[1] - self.size_hand.pinch_point[1],
            )
            delta = 0 if self.prev_two_hand_dist is None else curr_dist - self.prev_two_hand_dist
            self.prev_two_hand_dist = curr_dist
            return delta

        self.prev_two_hand_dist = None
        return 0

    def close(self):
        self.detector.close()
