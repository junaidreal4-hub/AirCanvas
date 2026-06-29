WINDOW_NAME  = "AirCanvas Pro"
FRAME_WIDTH  = 1280
FRAME_HEIGHT = 720

# BGR colour palette (OpenCV uses BGR, not RGB)
COLORS = {
    "red":     (0,   30,  255),
    "orange":  (0,   140, 255),
    "yellow":  (0,   220, 220),
    "green":   (0,   200, 80),
    "cyan":    (200, 200, 0),
    "blue":    (255, 100, 0),
    "purple":  (180, 0,   180),
    "pink":    (180, 80,  255),
    "white":   (255, 255, 255),
    "black":   (20,  20,  20),
}

COLOR_NAMES  = list(COLORS.keys())
SHAPE_TYPES  = ["freehand", "rectangle", "circle", "line", "triangle"]

# ── Layout ────────────────────────────────────────────────────────────────
UI_BAR_HEIGHT    = 100

# ── Gesture tuning ──────────────────────────────────────────────────────────
PINCH_THRESHOLD  = 40   # px — below this = pinching
PINCH_RELEASE    = 60   # px — above this = open hand (dead zone prevents flicker)
SMOOTHING        = 0.35  # EMA factor for cursor (lower = smoother, more lag)

# ── Brush ─────────────────────────────────────────────────────────────────
MIN_BRUSH        = 3
MAX_BRUSH        = 50
DEFAULT_BRUSH    = 7

# ── Behaviour ───────────────────────────────────────────────────────────────
FIST_CLEAR_SECONDS = 2.0   # hold a fist this long to clear the canvas
HOVER_CLICK_FRAMES = 18    # frames to dwell on a UI button before it triggers
HISTORY_LIMIT      = 20    # max undo snapshots per layer
SAVE_DIR           = "exports"
