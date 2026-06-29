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

# Brush engine — see brush_engine.py
BRUSH_TYPES        = ["pen", "marker", "spray", "calligraphy", "neon"]
DEFAULT_BRUSH_TYPE = "pen"

# ── Layout ────────────────────────────────────────────────────────────────
# Three stacked rows live in the top bar: colour swatches, shapes + brushes,
# and tools + the 3D button.
UI_BAR_HEIGHT    = 150

# ── UI theme (all BGR) ──────────────────────────────────────────────────────
UI_ACCENT      = (220, 180, 0)    # cyan — hover/active highlight & progress arcs
UI_ACCENT_WARM = (0, 200, 255)    # amber — the canvas-flip dwell
UI_DANGER      = (60, 60, 235)    # red — destructive (hold-to-clear)
UI_PANEL_BG    = (28, 25, 22)     # toolbar / HUD card background
UI_BTN_BG      = (50, 46, 42)     # idle button fill
UI_BTN_HOVER   = (74, 68, 62)     # hovered button fill
UI_STROKE      = (70, 64, 58)     # subtle borders / dividers
UI_TEXT        = (236, 236, 236)  # primary label text
UI_TEXT_DIM    = (150, 150, 150)  # secondary text
UI_BTN_RADIUS  = 9                # button corner radius (px)

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

# ── Canvas mode (white sheet ⇄ live camera) ─────────────────────────────────
PALM_HOLD_SECONDS  = 0.8           # hold an open palm this long to flip the mode
CANVAS_FADE_FRAMES = 15            # frames for the white⇄air cross-fade
WHITE_CANVAS_BG    = (255, 255, 255)

# ── Brush engine tunables ───────────────────────────────────────────────────
MARKER_OPACITY        = 0.6        # marker stroke alpha
SPRAY_DENSITY         = 0.9        # dots per unit brush size, per frame
SPRAY_RADIUS_FACTOR   = 1.6        # scatter radius as a multiple of brush size
CALLIGRAPHY_NIB_RATIO = 0.33       # nib thinness (minor / major ellipse axis)
NEON_BLUR_KERNEL      = 21         # gaussian kernel for the neon glow (odd)
NEON_CORE_BOOST       = 80         # how much brighter the neon core is

# ── Circular HSV colour palette (color_wheel.py) ────────────────────────────
WHEEL_SWATCHES   = 36              # hues around the outer ring
WHEEL_R_OUTER    = 230            # radius of the outer hue ring (px)
WHEEL_R_INNER    = 150            # radius of the inner greyscale ring (px)
WHEEL_SWATCH_R   = 14             # swatch dot radius (px)
WHEEL_HOVER_PX   = 18             # index-tip must come within this of a swatch
# Inner ring: white → greys → black (BGR)
WHEEL_INNER_COLORS = [
    (255, 255, 255), (200, 200, 200), (128, 128, 128), (64, 64, 64), (20, 20, 20),
]

# ── Pseudo-3D extrusion (CanvasLayer.extrude_3d) ────────────────────────────
EXTRUDE_OFFSET     = 12            # px the extruded face is pushed down-right
EXTRUDE_DARKEN     = 0.5           # multiplier for the side/back shade
EXTRUDE_APPROX_EPS = 0.01          # approxPolyDP epsilon as a fraction of perimeter
EXTRUDE_MIN_AREA   = 60            # ignore contours smaller than this (px²)
