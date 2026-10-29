"""Theme utilities: image conversion, window shapes, and the dark QSS stylesheet."""
from __future__ import annotations

import ctypes
import os
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QImage, QLinearGradient,
                           QPainter, QPainterPath, QPen, QPixmap, QRadialGradient)

# ---------------------------------------------------------------- Qt stylesheet (Темный стиль)
_QSS = """
* { 
    color: #ffffff; 
    font-family: "@FONT@", sans-serif; 
    font-size: 10pt; 
}

/* --- ГЛАВНЫЕ ОКНА --- */
QWidget { 
    background-color: #1e1e1e; 
}
QWidget#glassRoot { 
    background: transparent; 
}
QLabel#title { 
    font-size: 12pt; 
    font-weight: 600; 
    color: #ffffff;
}
QLabel#dim, QLabel.dim { 
    color: #aaaaaa; 
    font-size: 9pt; 
}
QLabel#section { 
    color: #aaaaaa; 
    font-size: 8.5pt; 
    font-weight: 600; 
    letter-spacing: 1px; 
}

/* --- КНОПКИ --- */
QPushButton {
    background-color: #2d2d2d; 
    border: 1px solid #3c3c3c;
    border-radius: 6px; 
    padding: 6px 15px; 
    min-height: 18px;
}
QPushButton:hover { 
    background-color: #3c3c3c; 
}
QPushButton:pressed { 
    background-color: #1a1a1a; 
}
QPushButton:checked {
    background-color: @ACCENT@;
    border: 1px solid @ACCENT@;
}
QPushButton#primary {
    background-color: @ACCENT@;
    border: 1px solid @ACCENT@;
    font-weight: 600; 
    padding: 7px 20px;
}
QPushButton#primary:hover { 
    background-color: @ACCENT_HOVER@;
}
QPushButton#chrome { 
    background: transparent; 
    border: none; 
    padding: 2px 8px; 
    border-radius: 4px; 
}
QPushButton#chrome:hover { 
    background: @CLOSE@; 
    color: white;
}

/* --- СЛАЙДЕРЫ --- */
QSlider::groove:horizontal { 
    height: 4px; 
    background: #3c3c3c; 
    border-radius: 2px; 
}
QSlider::sub-page:horizontal {
    background: @ACCENT@; 
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #ffffff; 
    width: 14px; 
    height: 14px; 
    margin: -6px 0; 
    border-radius: 7px;
    border: 1px solid #000000;
}

/* --- ПОЛЯ ВВОДА --- */
QSpinBox, QLineEdit, QComboBox {
    background-color: #2d2d2d; 
    border: 1px solid #3c3c3c;
    border-radius: 4px; 
    padding: 4px 8px; 
    selection-background-color: @ACCENT@;
}
QLineEdit:focus, QSpinBox:focus { 
    border: 1px solid @ACCENT@; 
}

/* --- БЛОКИ И КАРТОЧКИ --- */
QFrame#card { 
    background-color: #252525; 
    border: 1px solid #3c3c3c; 
    border-radius: 8px; 
}
QLabel#big { 
    font-size: 17pt; 
    font-weight: 700; 
}
QLabel#good { 
    color: #8dffb8; 
    font-weight: 600; 
}
QLabel#warn { 
    color: #ffd36b; 
    font-weight: 600; 
}

/* --- СПИСКИ И ТАБЛИЦЫ --- */
QComboBox QAbstractItemView { 
    background-color: #1e1e1e; 
    border: 1px solid #3c3c3c; 
}
QTableWidget { 
    background-color: #1e1e1e; 
    border: 1px solid #3c3c3c; 
    border-radius: 4px; 
    gridline-color: #3c3c3c; 
}
QHeaderView { 
    background: transparent; 
}
QHeaderView::section { 
    background-color: #2d2d2d; 
    border: none; 
    padding: 4px; 
    font-weight: 600; 
}

/* --- ЧЕКБОКСЫ --- */
QCheckBox::indicator { 
    width: 16px; 
    height: 16px; 
    border-radius: 3px; 
    border: 1px solid #3c3c3c; 
    background: #2d2d2d; 
}
QCheckBox::indicator:checked { 
    background-color: @ACCENT@; 
    border: 1px solid @ACCENT@; 
}

/* --- ПРОКРУТКА --- */
QScrollBar:vertical { 
    background: #1e1e1e; 
    width: 10px; 
}
QScrollBar::handle:vertical { 
    background: #3c3c3c; 
    border-radius: 5px; 
    min-height: 30px; 
}
QScrollBar::handle:vertical:hover { 
    background: #555555; 
}
QScrollBar::add-line, QScrollBar::sub-line { 
    height: 0; 
}

/* --- ПОДСКАЗКИ И МЕНЮ --- */
QToolTip { 
    background: #2d2d2d; 
    color: white; 
    border: 1px solid #3c3c3c; 
    border-radius: 4px; 
    padding: 4px; 
}
QMenu { 
    background: #1e1e1e; 
    border: 1px solid #3c3c3c; 
    border-radius: 6px; 
    padding: 4px; 
}
QMenu::item { 
    padding: 6px 18px; 
    border-radius: 4px; 
}
QMenu::item:selected { 
    background: #3c3c3c; 
}
"""


# Accent colours: macOS gets its own dark-mode system colours, Windows/Linux keep Fluent blue.
if sys.platform == "darwin":
    ACCENT, ACCENT_HOVER, CLOSE = "#0a84ff", "#409cff", "#ff453a"   # systemBlue / systemRed (dark)
else:
    ACCENT, ACCENT_HOVER, CLOSE = "#0078d4", "#1084d8", "#e81123"


def qss() -> str:
    """The stylesheet, with a font family that is really installed (see util.ui_family)."""
    from .util import ui_family
    return (_QSS.replace("@FONT@", ui_family(False)).replace("@ACCENT_HOVER@", ACCENT_HOVER)
            .replace("@ACCENT@", ACCENT).replace("@CLOSE@", CLOSE))


def dark_palette():
    """App-wide dark palette, so dialogs and menus Qt draws itself match the theme."""
    from PySide6.QtGui import QPalette
    pal = QPalette()
    base, window, text, dim = QColor(30, 30, 30), QColor(30, 30, 30), QColor(255, 255, 255), QColor(150, 150, 150)
    for role, col in ((QPalette.Window, window), (QPalette.WindowText, text), (QPalette.Base, QColor(37, 37, 37)),
                      (QPalette.AlternateBase, QColor(45, 45, 45)), (QPalette.Text, text),
                      (QPalette.Button, QColor(45, 45, 45)), (QPalette.ButtonText, text),
                      (QPalette.ToolTipBase, QColor(45, 45, 45)), (QPalette.ToolTipText, text),
                      (QPalette.PlaceholderText, dim), (QPalette.BrightText, QColor(CLOSE)),
                      (QPalette.Highlight, QColor(ACCENT)), (QPalette.HighlightedText, text),
                      (QPalette.Link, QColor(ACCENT_HOVER))):
        pal.setColor(role, col)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, dim)
    return pal


def __getattr__(name):        # keep `glass.QSS` working
    if name == "QSS":
        return qss()
    raise AttributeError(name)


# ---------------------------------------------------------------- image conversion helpers
def qimage_from_pil(im) -> QImage:
    im = im.convert("RGBA")
    data = im.tobytes("raw", "RGBA")
    qi = QImage(data, im.width, im.height, im.width * 4, QImage.Format_RGBA8888)
    return qi.copy()  # detach from the Python buffer


def pil_from_qimage(qi: QImage):
    from PIL import Image
    qi = qi.convertToFormat(QImage.Format_RGBA8888)
    ptr = qi.constBits()
    return Image.frombuffer("RGBA", (qi.width(), qi.height()), bytes(ptr), "raw", "RGBA",
                            qi.bytesPerLine(), 1).copy()


def rounded_rect_path(r: QRectF, radius: float) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(r, radius, radius)
    return path


# ---------------------------------------------------------------- Windows acrylic
class _ACCENT(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]


class _WCAD(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.c_void_p), ("SizeOfData", ctypes.c_size_t)]


def enable_acrylic(hwnd: int, tint_abgr: int = 0x40281E28) -> bool:
    """Real blur-behind for a frameless translucent window (Windows 10/11).
    Returns False elsewhere so callers can fall back to a painted frost."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        accent = _ACCENT(4, 2, tint_abgr, 0)  # 4 = ACCENT_ENABLE_ACRYLICBLURBEHIND
        data = _WCAD(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p), ctypes.sizeof(accent))
        ok = bool(user32.SetWindowCompositionAttribute(ctypes.c_void_p(hwnd), ctypes.byref(data)))
        try:  # rounded corners on Windows 11
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(hwnd), 33,
                                                       ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass
        return ok
    except Exception:
        return False


# ---------------------------------------------------------------- live liquid backing
def exclude_from_capture(hwnd: int) -> bool:
    """Hide a window from screen capture (Windows 10 2004+), so we can re-capture what's
    behind it while it's visible. Skipped while recording demos (it would hide us)."""
    import os
    if sys.platform == "darwin":
        from . import platform_mac
        return platform_mac.OK      # macOS: we capture "below our window" instead
    if sys.platform != "win32" or os.environ.get("DRAGSHIFT_RECORDING"):
        return False
    try:
        return bool(ctypes.windll.user32.SetWindowDisplayAffinity(ctypes.c_void_p(hwnd), 0x11))
    except Exception:
        return False


from PySide6.QtCore import QObject, QRect, QRunnable, QThreadPool, QTimer, Signal  # noqa: E402


class _LiquidSig(QObject):
    done = Signal(int, QImage, bool)


class _LiquidJob(QRunnable):
    def __init__(self, serial, backdrop, w, h, radius, style):
        super().__init__()
        self.args = (serial, backdrop, w, h, radius, style)
        self.sig = _LiquidSig()

    def run(self):
        serial, backdrop, w, h, radius, style = self.args
        try:
            from . import liquid
            sdf = liquid.sdf_rounded_rect(w, h, 0.5, 0.5, w - 0.5, h - 0.5, radius)
            img, light = liquid.render(backdrop, sdf, style)
            try:
                self.sig.done.emit(serial, qimage_from_pil(img), light)
            except RuntimeError:
                pass  # window closed before the render finished
        except Exception:
            import traceback
            traceback.print_exc()


def grab_screen(x: int, y: int, w: int, h: int, below_window: int = 0):
    """Screen pixels under a rect (logical coords) as a PIL image of size w×h.
    macOS: native capture that leaves out the drag picture (and `below_window` and above)."""
    if sys.platform == "darwin":
        from . import platform_mac
        if platform_mac.OK:
            im = platform_mac.capture(x, y, w, h, below_window)
            if im is not None:
                return im
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QGuiApplication
    scr = QGuiApplication.screenAt(QPoint(x + w // 2, y + h // 2)) or QGuiApplication.primaryScreen()
    g = scr.geometry()
    try:
        shot = scr.grabWindow(0, x - g.x(), y - g.y(), w, h)
    except Exception:
        return None
    if shot.isNull():
        return None
    return pil_from_qimage(shot.toImage().scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))


class LiquidBacking(QObject):
    """Keeps a refracted snapshot of whatever is behind a rounded-rect window."""
    changed = Signal()

    def __init__(self, widget, radius: float, style=None):
        super().__init__(widget)
        from .liquid import GlassStyle
        self.w = widget
        self.radius = radius
        self.style = style or GlassStyle(blur=16, strength=14, bezel=20)
        self.image: QImage | None = None
        self.is_light = False
        self.excluded = False
        self._serial = 0
        self._debounce = QTimer(self, singleShot=True, interval=140, timeout=self.refresh)

    def capture_at(self, rect: QRect):
        """Grab the screen under `rect` (call before the window is shown, or when excluded)."""
        below = 0
        if sys.platform == "darwin" and self.w.isVisible():
            from . import platform_mac
            below = platform_mac.window_number(self.w)
        pil = grab_screen(rect.x(), rect.y(), rect.width(), rect.height(), below)
        if pil is None:
            return
        self._serial += 1
        job = _LiquidJob(self._serial, pil, rect.width(), rect.height(), self.radius, self.style)
        from .util import keep, release
        job.sig.done.connect(lambda *a, j=job: (release(j), self._done(*a)))
        QThreadPool.globalInstance().start(keep(job))

    def _done(self, serial, img, light):
        if serial == self._serial:
            self.image, self.is_light = img, light
            self.changed.emit()

    def moved(self):
        """Window moved/resized: refresh once it settles (only possible when excluded)."""
        if self.excluded:
            self.image = None if self.image is not None and self.image.size() != self.w.size() else self.image
            self._debounce.start()

    def refresh(self):
        if self.excluded and self.w.isVisible():
            self.capture_at(self.w.frameGeometry())


# ---------------------------------------------------------------- drag-image hiding
class hidden_drag_images:
    """While dragging, Windows draws a translucent picture of the file under the cursor.
    Hide it for the instant we capture the screen behind the menu, so it doesn't get frozen
    into the glass, then show it again. We hide every visible top-level window of another
    process that sits under the cursor and is layered + click-through (that is what drag
    images are), plus the known drag-image classes."""

    CLASSES = ("SysDragImage", "DragImageWindow", "DragWindow")
    WS_EX_LAYERED, WS_EX_TRANSPARENT = 0x00080000, 0x00000020

    def __init__(self, point=None):
        self.point = point
        self.hwnds: list[int] = []
        self.info: list[str] = []
        self.rects: list[tuple[int, int, int, int]] = []   # screen px, for inpainting

    def __enter__(self):
        if sys.platform != "win32":
            return self
        try:
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.GetWindowLongW.restype = ctypes.c_long
            pt = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            mypid = os.getpid()
            found = []
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

            def cb(hwnd, _):
                h = ctypes.c_void_p(hwnd)
                if not user32.IsWindowVisible(h):
                    return True
                r = wintypes.RECT()
                user32.GetWindowRect(h, ctypes.byref(r))
                near = r.left - 40 <= pt.x <= r.right + 40 and r.top - 40 <= pt.y <= r.bottom + 40
                if not near or (r.right - r.left) > 900 or (r.bottom - r.top) > 900:
                    return True
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
                if pid.value == mypid:
                    return True
                buf = ctypes.create_unicode_buffer(64)
                user32.GetClassNameW(h, buf, 64)
                ex = user32.GetWindowLongW(h, -20)  # GWL_EXSTYLE
                drag_like = (ex & self.WS_EX_LAYERED) and (ex & self.WS_EX_TRANSPARENT)
                if buf.value in self.CLASSES or drag_like:
                    found.append(hwnd)
                    self.rects.append((r.left, r.top, r.right, r.bottom))
                    self.info.append(f"{buf.value} ex=0x{ex & 0xffffffff:08x} {r.right - r.left}x{r.bottom - r.top}")
                return True
            user32.EnumWindows(WNDENUMPROC(cb), 0)
            for h in found:
                user32.ShowWindow(ctypes.c_void_p(h), 0)  # SW_HIDE
            self.hwnds = found
            if found:
                ctypes.windll.gdi32.GdiFlush()
                ctypes.windll.dwmapi.DwmFlush()  # wait for the compositor to drop them
                ctypes.windll.dwmapi.DwmFlush()
        except Exception as e:
            self.info.append(f"error: {e}")
        return self

    def __exit__(self, *exc):
        if self.hwnds:
            try:
                for h in self.hwnds:
                    ctypes.windll.user32.ShowWindow(ctypes.c_void_p(h), 8)  # SW_SHOWNA
            except Exception:
                pass
        return False


def inpaint_rects(im, rects, pad: int = 6):
    """Fill rectangles of a PIL image from their surroundings (normalised convolution):
    a smooth, colour-matched patch — invisible once refracted and blurred by the glass."""
    import numpy as np
    from PIL import Image, ImageFilter
    if not rects:
        return im
    rgb = im.convert("RGB")
    w, h = rgb.size
    mask = Image.new("L", (w, h), 255)
    from PIL import ImageDraw
    d = ImageDraw.Draw(mask)
    any_hit = False
    for (x0, y0, x1, y1) in rects:
        x0, y0, x1, y1 = max(0, x0 - pad), max(0, y0 - pad), min(w, x1 + pad), min(h, y1 + pad)
        if x1 > x0 and y1 > y0:
            d.rectangle((x0, y0, x1, y1), fill=0)
            any_hit = True
    if not any_hit:
        return im
    a = np.asarray(rgb, np.float32)
    m = np.asarray(mask, np.float32)[..., None] / 255
    radius = 28
    num = np.asarray(Image.fromarray(np.clip(a * m, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(radius)), np.float32)
    den = np.asarray(mask.filter(ImageFilter.GaussianBlur(radius)), np.float32)[..., None] / 255
    fill = num / np.maximum(den, 1e-3)
    fill = np.asarray(Image.fromarray(np.clip(fill, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), np.float32)
    # feather the seam: the glass bezel magnifies any hard edge into a visible line
    soft = np.asarray(mask.filter(ImageFilter.GaussianBlur(12)), np.float32)[..., None] / 255
    soft = np.minimum(soft, m)  # never let the drag picture bleed back in
    out = a * soft + fill * (1 - soft)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- no-compositor mode (XFCE etc.)
_NO_COMP = None


def no_compositor() -> bool:
    """Linux/X11 without a compositing manager: translucency would render black, so glass
    surfaces are cut to their exact shape with a window mask instead (XShape)."""
    global _NO_COMP
    if _NO_COMP is None:
        _NO_COMP = False
        if sys.platform.startswith("linux") and not os.environ.get("QT_QPA_PLATFORM", "").startswith("offscreen"):
            try:
                from . import platform_linux
                _NO_COMP = not platform_linux.composited()
            except Exception:
                _NO_COMP = False
    return _NO_COMP


def apply_shape(widget, path: QPainterPath):
    """Clip a top-level window to `path` when there's no compositor (no-op otherwise)."""
    if not no_compositor():
        return
    from PySide6.QtGui import QRegion
    region = QRegion()
    for poly in path.simplified().toFillPolygons():   # one polygon per separate piece
        region = region.united(QRegion(poly.toPolygon()))
    widget.setMask(region)