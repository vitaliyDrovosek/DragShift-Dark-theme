"""The radial drop menu that pops up under the cursor while you Shift+drag a file."""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import (QEasingCurve, QObject, QPoint, QPointF, QRectF, QRunnable, Qt,
                            QThreadPool, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import (QColor, QCursor, QFont, QGuiApplication, QImage, QPainter,
                           QPainterPath, QPen, QPixmap, QBrush)
from PySide6.QtWidgets import QWidget

from . import glass
from .util import resolve_shortcuts, ui_family


@dataclass
class Item:
    label: str
    glyph: str = ""
    run: Callable[[list[str]], None] | None = None
    key: str = ""
    hint: str = ""


SIZE = 400          # window size (room for shadow + hover pop)
R_OUT = 158         # outer radius of petals
R_IN = 60           # inner radius of petals
R_HUB = 50          # hub radius
GAP_DEG = 3.2
CORNER = 10

# Настройки цветов для строгого черного стиля
BG_COLOR = QColor(20, 20, 20)      # Цвет фона (темно-серый, почти черный)
HOVER_COLOR = QColor(60, 60, 60)   # Цвет лепестка при наведении (светло-серый)
BORDER_COLOR = QColor(80, 80, 80)  # Цвет тонкой обводки лепестков


def sector_path(c: QPointF, r0: float, r1: float, a0: float, a1: float) -> QPainterPath:
    """Annular sector between angles a0..a1 (degrees, Qt convention: 0 = 3 o'clock, CCW)."""
    path = QPainterPath()
    outer = QRectF(c.x() - r1, c.y() - r1, 2 * r1, 2 * r1)
    inner = QRectF(c.x() - r0, c.y() - r0, 2 * r0, 2 * r0)
    path.arcMoveTo(outer, a0)
    path.arcTo(outer, a0, a1 - a0)
    path.arcTo(inner, a1, -(a1 - a0))
    path.closeSubpath()
    return path


def angles(n: int, i: int) -> tuple[float, float]:
    span = 360.0 / n
    start = 90 + span / 2 - (i + 1) * span   # first petal centred at 12 o'clock, clockwise
    return start + GAP_DEG / 2, start + span - GAP_DEG / 2


# ---------------------------------------------------------------- background render
class _RenderSig(QObject):
    done = Signal(int, int, QImage, bool)   # serial, petal count, image, is_light


class _RenderJob(QRunnable):
    def __init__(self, serial: int, n: int, backdrop):
        super().__init__()
        self.serial, self.n, self.backdrop = serial, n, backdrop
        self.sig = _RenderSig()

    def run(self):
        try:
            from . import liquid
            c = SIZE / 2
            fields = [liquid.sdf_circle(SIZE, SIZE, c, c, R_HUB)]
            for i in range(self.n):
                a0, a1 = angles(self.n, i)
                fields.append(liquid.sdf_ring_sector(SIZE, SIZE, c, c, R_IN, R_OUT, a0, a1, CORNER))
            sdf = liquid.union(*fields)
            # Рендерим строго черный фон из liquid.py
            img, light = liquid.render(self.backdrop, sdf, liquid.GlassStyle())
            
            # Делаем мягкую тень
            sh = liquid.shadow(sdf, spread=26, opacity=0.42 if light else 0.30, offset=(0, 8))
            sh.alpha_composite(img)
            
            try:
                self.sig.done.emit(self.serial, self.n, glass.qimage_from_pil(sh), light)
            except RuntimeError:
                pass
        except Exception:  # pragma: no cover
            import traceback
            traceback.print_exc()


class RadialMenu(QWidget):
    activated = Signal(object, list)     # Item, paths
    dismissed = Signal()

    def __init__(self, build_rings: Callable[[list[str]], dict[str, list[Item]]],
                 describe: Callable[[list[str]], str]):
        super().__init__(None)
        self.build_rings = build_rings
        self.describe = describe
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint |
                            Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.resize(SIZE, SIZE)

        self.paths: list[str] = []
        self.rings: dict[str, list[Item]] = {}
        self.ring_names: list[str] = []
        self.ring_idx = 0
        self.hover = -1          # petal index, -2 = hub, -1 = none
        self.cursor_pos = QPointF(SIZE / 2, SIZE / 2)
        self.hub_text = ""
        self.backdrop: QPixmap | None = None
        self._raw_backdrop = None
        self.liquid: dict[int, QImage] = {}
        self.is_light = False
        self._serial = 0
        self.got_drag = False
        self.fresh_drag = False   # macOS: files read from this drag's pasteboard
        self.key_flips_ring = True  # False when the global key watcher flips the rings
        self.hub_armed = False
        self.click_mode = False
        self._t = 1.0
        self._swap = 1.0
        self.spring: list[float] = []
        self.hub_spring = 0.0

        self.anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=190,
                                      easingCurve=QEasingCurve.OutBack)
        self.anim.valueChanged.connect(self._set_t)
        self.swap_anim = QVariantAnimation(self, startValue=0.0, endValue=1.0, duration=220,
                                           easingCurve=QEasingCurve.OutCubic)
        self.swap_anim.valueChanged.connect(self._set_swap)
        self.hub_timer = QTimer(self, singleShot=True, interval=420, timeout=self.next_ring)
        self.frame = QTimer(self, interval=16, timeout=self._tick)

    def popup(self, pos: QPoint | None = None, paths: list[str] | None = None, fresh: bool = True):
        pos = pos or QCursor.pos()
        tl = pos - QPoint(SIZE // 2, SIZE // 2)
        scr = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g = scr.geometry()
        tl.setX(min(max(tl.x(), g.left()), g.right() - SIZE))
        tl.setY(min(max(tl.y(), g.top()), g.bottom() - SIZE))
        
        self._serial += 1
        self.liquid = {}
        self._raw_backdrop = None
        self.backdrop = None
            
        self.move(tl)
        self.hover = -1
        self.got_drag = False
        self.hub_armed = False
        self.click_mode = paths is not None
        early = []
        self.fresh_drag = False
        if paths is None and fresh and sys.platform == "darwin":
            # macOS only reports a drag to a window once the cursor moves over it:
            # read the drag pasteboard so the slices show the moment the menu opens
            from . import platform_mac
            early = platform_mac.drag_files()
            if early:
                self.fresh_drag = True
                print(f"menu: {len(early)} file(s) from the drag pasteboard", flush=True)
        if paths is not None:
            self._load(paths)
        elif early:
            self._load(early)
        else:
            self.paths, self.rings, self.ring_names = [], {}, []
            self.hub_text = "Drop here"
            for n in (4, 7):
                self._render(n)
        self._t = 0.0
        self._shape()
        self.show()
        self.raise_()
        self.anim.start()
        self.frame.start()
        if self.click_mode:
            QTimer.singleShot(0, self.grabMouse)

    def load_drag_pasteboard(self):
        """macOS: the drag's files became readable after the menu opened."""
        if not self.isVisible() or self.click_mode or self.got_drag or self.fresh_drag:
            return
        from . import platform_mac
        early = platform_mac.drag_files()
        if early:
            self.fresh_drag = True
            print(f"menu: {len(early)} file(s) from the drag pasteboard (late)", flush=True)
            self._load(early)

    def close_menu(self):
        if self.isVisible():
            self.hide()
            self.frame.stop()
            self.hub_timer.stop()
            self.dismissed.emit()

    def hideEvent(self, e):
        self.frame.stop()
        if QWidget.mouseGrabber() is self:
            self.releaseMouse()
        super().hideEvent(e)

    def _render(self, n: int):
        if n <= 0 or n in self.liquid:
            return
        self.liquid[n] = QImage()
        job = _RenderJob(self._serial, n, self._raw_backdrop)
        from .util import keep, release
        job.sig.done.connect(lambda *a, j=job: (release(j), self._rendered(*a)))
        QThreadPool.globalInstance().start(keep(job))

    def _rendered(self, serial: int, n: int, img: QImage, light: bool):
        if serial == self._serial:
            self.liquid[n] = img
            self.is_light = light
            self.update()

    def _load(self, paths: list[str]):
        paths = resolve_shortcuts(paths)
        self.paths = paths
        self.rings = {k: v for k, v in self.build_rings(paths).items() if v}
        self.ring_names = list(self.rings)
        self.ring_idx = 0
        self.hub_text = self.describe(paths)
        for items in self.rings.values():
            self._render(len(items))
        self.spring = [0.0] * len(self.items)
        self._shape()
        self.update()

    def _shape(self):
        """No compositor (XFCE etc.): cut the window to the menu's outline."""
        if not glass.no_compositor():
            return
        c = QPointF(SIZE / 2, SIZE / 2)
        path = QPainterPath()
        path.addEllipse(c, R_HUB + 2, R_HUB + 2)
        n = len(self.items) or 0
        if n:
            for i in range(n):
                a0, a1 = angles(n, i)
                path = path.united(sector_path(c, R_IN - 2, R_OUT + 14, a0 - 1, a1 + 1))
        else:
            outer = QPainterPath()
            outer.addEllipse(c, R_OUT + 14, R_OUT + 14)
            path = path.united(outer)
        glass.apply_shape(self, path)

    def next_ring(self):
        if len(self.ring_names) > 1:
            self.ring_idx = (self.ring_idx + 1) % len(self.ring_names)
            self.hover = -1
            self.spring = [0.0] * len(self.items)
            self._swap = 0.0
            self.swap_anim.start()
            self._shape()
            self.update()

    def _set_t(self, v):
        self._t = float(v)
        self.update()

    def _set_swap(self, v):
        self._swap = float(v)
        self.update()

    def _tick(self):
        moved = False
        for i in range(len(self.spring)):
            target = 1.0 if i == self.hover else 0.0
            v = self.spring[i]
            nv = v + (target - v) * 0.32
            if abs(nv - target) < 0.003:
                nv = target
            if nv != v:
                self.spring[i] = nv
                moved = True
        ht = 1.0 if self.hover == -2 else 0.0
        nh = self.hub_spring + (ht - self.hub_spring) * 0.3
        if abs(nh - ht) < 0.003:
            nh = ht
        if nh != self.hub_spring:
            self.hub_spring = nh
            moved = True
        if moved:
            self.update()

    @property
    def items(self) -> list[Item]:
        if not self.ring_names:
            return []
        return self.rings[self.ring_names[self.ring_idx]]

    def _angles(self, n: int, i: int) -> tuple[float, float]:
        return angles(n, i)

    def hit(self, pos: QPointF) -> int:
        c = QPointF(SIZE / 2, SIZE / 2)
        dx, dy = pos.x() - c.x(), c.y() - pos.y()
        d = math.hypot(dx, dy)
        if d <= R_HUB + 4:
            return -2
        if d > R_OUT + 30 or not self.items:
            return -1
        ang = math.degrees(math.atan2(dy, dx)) % 360
        n = len(self.items)
        rel = (90 + 180.0 / n - ang) % 360
        return int(rel // (360.0 / n)) % n

    def _set_hover(self, h: int, pos: QPointF | None = None):
        if pos is not None:
            self.cursor_pos = QPointF(pos)
        if h != self.hover:
            self.hover = h
            if h >= 0:
                self.hub_armed = True
            if h == -2 and self.hub_armed and len(self.ring_names) > 1:
                self.hub_timer.start()
            else:
                self.hub_timer.stop()
        self.update()

    @staticmethod
    def _local_paths(md) -> list[str]:
        if not md.hasUrls():
            return []
        return [u.toLocalFile() for u in md.urls() if u.isLocalFile() and u.toLocalFile()]

    def dragEnterEvent(self, e):
        paths = self._local_paths(e.mimeData())
        if not paths:
            e.ignore()
            return
        self.got_drag = True
        if resolve_shortcuts(paths) != self.paths:
            self._load(paths)
        e.setDropAction(Qt.CopyAction)
        e.accept()

    def dragMoveEvent(self, e):
        self._set_hover(self.hit(e.position()), e.position())
        e.setDropAction(Qt.CopyAction)
        e.accept()

    def dragLeaveEvent(self, e):
        self._set_hover(-1)

    def dropEvent(self, e):
        idx = self.hit(e.position())
        items = self.items
        if 0 <= idx < len(items):
            e.setDropAction(Qt.CopyAction)
            e.accept()
            item, paths = items[idx], list(self.paths)
            self.hide()
            QTimer.singleShot(0, lambda: self.activated.emit(item, paths))
        else:
            e.ignore()
            self.close_menu()

    def mouseMoveEvent(self, e):
        if self.click_mode:
            self._set_hover(self.hit(e.position()), e.position())

    def mouseReleaseEvent(self, e):
        if not self.click_mode:
            return
        if e.button() == Qt.RightButton:
            self.close_menu()
            return
        idx = self.hit(e.position())
        if idx == -2:
            self.next_ring()
        elif 0 <= idx < len(self.items):
            item, paths = self.items[idx], list(self.paths)
            self.hide()
            QTimer.singleShot(0, lambda: self.activated.emit(item, paths))
        else:
            self.close_menu()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close_menu()
        elif e.key() == Qt.Key_Tab or (e.key() == Qt.Key_Shift and self.key_flips_ring):
            self.next_ring()

    def leaveEvent(self, e):
        if self.click_mode:
            self._set_hover(-1)

    def _text_colors(self) -> tuple[QColor, QColor, QColor]:
        # Белый текст для темного фона
        return QColor(255, 255, 255), QColor(200, 200, 200), QColor(0, 0, 0, 110)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        c = QPointF(SIZE / 2, SIZE / 2)
        t = self._t
        p.setOpacity(min(1.0, max(0.0, t * 1.5)))
        p.translate(c)
        s = 0.80 + 0.20 * t
        p.scale(s, s)
        p.translate(-c)

        items = self.items
        n = len(items)
        img = self.liquid.get(n) if n else (self.liquid.get(4) or self.liquid.get(7))
        have_liquid = img is not None and not img.isNull()

        if have_liquid:
            p.drawImage(0, 0, img)
        else:
            self._paint_fallback(p, c, n)

        fg, fg_dim, shadow_col = self._text_colors()
        rot = (1 - self._swap) * -22
        
        for i, it in enumerate(items):
            a0, a1 = angles(n, i)
            h = self.spring[i] if i < len(self.spring) else 0.0
            
            # Отрисовка подсветки при наведении
            if h > 0.001:
                self._paint_hover(p, c, a0, a1, h)
                
            self._petal_label(p, c, it, (a0 + a1) / 2 + rot, (R_IN + R_OUT) / 2, h,
                              fg, shadow_col)
                              
        if not n and self.paths:
            self._paint_unsupported(p, c, fg, fg_dim, shadow_col)

        self._paint_hub(p, c, fg, fg_dim, shadow_col)
        
        # ОБЯЗАТЕЛЬНО закрываем painter, иначе Qt будет ругаться
        p.end()

    def _paint_unsupported(self, p: QPainter, c: QPointF, fg: QColor, fg_dim: QColor,
                           shadow_col: QColor):
        ext = Path(self.paths[0]).suffix.lower() or "this file"
        f = QFont(ui_family(True))
        f.setPixelSize(13)
        f.setBold(True)
        p.setFont(f)
        r_mid = (R_IN + R_OUT) / 2
        self._text(p, QRectF(c.x() - R_OUT, c.y() - r_mid - 18, 2 * R_OUT, 18),
                   f"Can't convert {ext}", fg, shadow_col)
        f.setPixelSize(10)
        f.setBold(False)
        p.setFont(f)
        self._text(p, QRectF(c.x() - R_OUT, c.y() - r_mid + 1, 2 * R_OUT, 16),
                   "Images · PDF · Word · Text", fg_dim, None)

    def _paint_fallback(self, p: QPainter, c: QPointF, n: int):
        # Запасной вариант отрисовки, если поток не успел. Рисуем просто круги.
        p.setBrush(QBrush(BG_COLOR))
        p.setPen(Qt.NoPen)
        
        # Центр
        p.drawEllipse(c, R_HUB, R_HUB)
        
        # Лепестки
        for i in range(n):
            a0, a1 = angles(n, i)
            path = sector_path(c, R_IN, R_OUT, a0, a1)
            p.drawPath(path)

    def _paint_hover(self, p: QPainter, c: QPointF, a0: float, a1: float, h: float):
        # Просто закрашиваем сектор при наведении. Без масштабирования и искажений.
        path = sector_path(c, R_IN - 1, R_OUT + 1, a0, a1)
        p.save()
        p.setClipPath(sector_path(c, R_IN, R_OUT, a0, a1))
        color = QColor(HOVER_COLOR)
        color.setAlpha(int(255 * h))
        p.setBrush(QBrush(color))
        p.setPen(Qt.NoPen)
        p.drawPath(path)
        p.restore()

    def _paint_hub(self, p: QPainter, c: QPointF, fg: QColor, fg_dim: QColor, shadow_col: QColor):
        p.setPen(QPen(BORDER_COLOR, 1.2))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(c, R_HUB - 0.5, R_HUB - 0.5)

        items = self.items
        hov = items[self.hover] if 0 <= self.hover < len(items) else None
        if hov is not None:
            top, sub = hov.label if not hov.glyph else hov.label.title(), hov.hint or ""
        else:
            ring_name = self.ring_names[self.ring_idx] if self.ring_names else ""
            top = self.hub_text
            if len(self.ring_names) > 1:
                other = self.ring_names[(self.ring_idx + 1) % len(self.ring_names)]
                sub = f"⇧ {other.upper()}"
            else:
                sub = ring_name.upper()
        f = QFont(ui_family(True))
        f.setPixelSize(14)
        f.setBold(True)
        p.setFont(f)
        rect_top = QRectF(c.x() - R_HUB + 4, c.y() - 21, 2 * R_HUB - 8, 20)
        self._text(p, rect_top, top, fg, shadow_col)
        f.setPixelSize(10)
        f.setBold(False)
        p.setFont(f)
        self._text(p, QRectF(c.x() - R_HUB + 6, c.y() + 2, 2 * R_HUB - 12, 28), sub, fg_dim, None,
                   Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap)

    @staticmethod
    def _text(p: QPainter, r: QRectF, text: str, col: QColor, shadow: QColor | None,
              flags=Qt.AlignCenter):
        if shadow is not None:
            p.setPen(shadow)
            p.drawText(r.translated(0, 1), flags, text)
        p.setPen(col)
        p.drawText(r, flags, text)

    def _petal_label(self, p: QPainter, c: QPointF, it: Item, ang: float, r: float,
                     h: float, fg: QColor, shadow_col: QColor):
        rad = math.radians(ang)
        # Убрали push = 6 * h, чтобы текст не прыгал при наведении
        pt = QPointF(c.x() + r * math.cos(rad), c.y() - r * math.sin(rad))
        p.save()
        p.setOpacity(p.opacity() * (0.25 + 0.75 * self._swap))
        
        # Текст всегда белый, так как фон черный
        col = QColor(255, 255, 255) 
        
        f = QFont(ui_family(True))
        if it.glyph:
            f.setPixelSize(18) # Убрал +3 * h, чтобы размер не менялся
            p.setFont(f)
            self._text(p, QRectF(pt.x() - 30, pt.y() - 24, 60, 24), it.glyph, col, shadow_col,
                       Qt.AlignHCenter | Qt.AlignBottom)
            f.setPixelSize(10)
            f.setBold(True)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 0.7)
            p.setFont(f)
            self._text(p, QRectF(pt.x() - 42, pt.y() + 1, 84, 16), it.label.upper(), col, shadow_col)
        else:
            f.setPixelSize(14) # Убрал +2 * h
            f.setBold(True)
            f.setLetterSpacing(QFont.AbsoluteSpacing, 0.9)
            p.setFont(f)
            self._text(p, QRectF(pt.x() - 42, pt.y() - 12, 84, 24), it.label, col, shadow_col)
        p.restore()