"""Watches for "left button held + mouse moved + Shift pressed" anywhere on screen, which
is what a Shift+drag of a file looks like. Polling global input state is simple, needs no
admin rights and can't stall the system the way a broken hook can.
Windows: GetAsyncKeyState. macOS: NSEvent.pressedMouseButtons / modifierFlags (no
Accessibility or Input Monitoring permission required)."""
from __future__ import annotations

import ctypes
import sys
import time

from PySide6.QtCore import QObject, QPoint, QTimer, Signal
from PySide6.QtGui import QCursor

VK_LBUTTON, VK_SHIFT, VK_ESCAPE = 0x01, 0x10, 0x1B
DRAG_THRESHOLD = 10   # px the mouse must travel with the button held
NO_DRAG_TIMEOUT = 50  # ticks (≈ 0.75 s) to wait for a file drag to enter before hiding
UP_DEBOUNCE = 0.09   # s the button must read 'up' before the drag counts as finished
MAX_UP_WAIT = 8.0    # s to keep trusting a drag picture while the button reads 'up'


class DoubleTap:
    """Two quick taps of the trigger key, with nothing else going on in between -> fire.
    Pure logic (times are passed in), so it can be unit-tested."""
    MAX_PRESS = 0.35   # s a tap may be held
    MAX_GAP = 0.45     # s between releasing the first tap and pressing the second

    def __init__(self):
        self._was = False
        self.reset()

    def reset(self):
        self._press_t: float | None = None
        self._first_t: float | None = None   # release time of the first tap
        self.seq_start: float | None = None  # press time of the first tap

    def update(self, key: bool, now: float, clean: bool = True) -> bool:
        """clean=False (a mouse button, another modifier, a typed key...) cancels."""
        fired = False
        if not clean:
            self.reset()
        elif key and not self._was:                                   # press
            if self._first_t is not None and now - self._first_t > self.MAX_GAP:
                self.reset()
            if self._first_t is None:
                self.seq_start = now
            self._press_t = now
        elif not key and self._was and self._press_t is not None:     # release
            if now - self._press_t > self.MAX_PRESS:
                self.reset()                                         # held: not a tap
            elif self._first_t is not None:
                fired = True
                self.reset()
            else:
                self._first_t = now
                self._press_t = None
        self._was = key
        return fired


class DragShiftWatcher(QObject):
    show_menu = Signal(QPoint)
    toggle_ring = Signal()
    hide_menu = Signal()
    pasteboard_ready = Signal()      # macOS: the file drag's pasteboard became readable
    double_tap = Signal(QPoint)      # trigger key tapped twice (Finder / Explorer selection menu)
    click_menu_mouse_down = Signal(QPoint)   # mouse pressed while a click menu is open

    def __init__(self, menu_visible, menu_got_drag, parent=None, click_menu_visible=None):
        super().__init__(parent)
        self.menu_visible = menu_visible
        self.menu_got_drag = menu_got_drag
        # a click menu (double-tap on a Finder selection, Open With, tray) is open: the
        # trigger key flips Convert ⇄ Tools there too, but nothing else is managed here
        self.click_menu_visible = click_menu_visible or (lambda: False)
        self.enabled = True
        self.double_tap_enabled = True
        self.vk = VK_SHIFT
        self.key_name = "shift"
        self._down_at: QPoint | None = None
        self._shift_was = False
        self._lbtn_was = False
        self._esc_was = False
        self._fired = False
        self._idle_ticks = 0
        self._shown_at = QPoint()
        self._up_since: float | None = None
        self._count_at_down: int | None = None
        self._alive_cache = (0.0, False)
        self._tap = DoubleTap()
        self._user32 = ctypes.windll.user32 if sys.platform == "win32" else None
        self._mac = None
        self._darwin = None          # platform_mac when on macOS
        self._keys = None            # other_modifiers_down / seconds_since_key_typed
        if sys.platform == "darwin":
            from . import platform_mac
            self._mac = platform_mac if platform_mac.OK else None
            self._darwin = self._mac
            self._keys = self._mac
        elif sys.platform == "win32":
            from . import platform_win
            self._keys = platform_win.KeyActivity()
        elif sys.platform.startswith("linux"):
            from . import platform_linux
            # same interface as platform_mac: left_button_down / key_down / escape_down
            self._mac = platform_linux if platform_linux.available() else None
        self.timer = QTimer(self, interval=15, timeout=self._tick)

    def set_key(self, name: str):
        self.key_name = name
        self.vk = {"shift": VK_SHIFT, "ctrl": 0x11, "alt": 0x12}.get(name, VK_SHIFT)

    def start(self):
        if self._user32 is not None or self._mac is not None:
            self.timer.start()

    def _down(self, vk: int) -> bool:
        return bool(self._user32.GetAsyncKeyState(vk) & 0x8000)

    def _state(self) -> tuple[bool, bool, bool]:
        """(left button, trigger key, escape)"""
        if self._mac is not None:
            m = self._mac
            return m.left_button_down(), m.key_down(self.key_name), m.escape_down()
        return self._down(VK_LBUTTON), self._down(self.vk), self._down(VK_ESCAPE)

    # ------------------------------------------------------------ macOS helpers
    def fresh_file_drag(self) -> bool:
        """macOS: has a new drag started since the button went down? (Otherwise the drag
        pasteboard still holds an older drag and must not be shown.)"""
        if self._darwin is None:
            return True
        return self._count_at_down is not None and self._darwin.drag_change_count() != self._count_at_down

    def _drag_still_alive(self, up_for: float) -> bool:
        """Button reads 'up' but a trackpad drag may still be running: trust the drag picture."""
        if self._darwin is None or up_for > MAX_UP_WAIT:
            return False
        t, alive = self._alive_cache
        now = time.monotonic()
        if now - t > 0.06:
            alive = self._darwin.drag_session_active()
            self._alive_cache = (now, alive)
        return alive

    def _other_mods(self) -> bool:
        """macOS: another modifier is held too (Cmd+Shift... shortcuts are not a tap)."""
        try:
            return bool(self._keys is not None and self._keys.other_modifiers_down(self.key_name))
        except Exception:
            return False

    # ------------------------------------------------------------ polling
    def _tick(self):
        lbtn, shift, esc = self._state()
        pos = QCursor.pos()
        now = time.monotonic()

        if self.click_menu_visible():
            self._tap.reset()
            self._down_at = None
            if shift and not self._shift_was and not lbtn and not self._other_mods():
                self.toggle_ring.emit()           # tap the key to flip Convert ⇄ Tools
            if lbtn and not self._lbtn_was:
                self.click_menu_mouse_down.emit(pos)
            if esc and not self._esc_was:
                self.hide_menu.emit()
            self._shift_was, self._lbtn_was, self._esc_was = shift, lbtn, esc
            return

        if self.menu_visible():
            self._tap.reset()
            # tap Shift again to flip Convert ⇄ Tools. Checked whatever the button reads:
            # trackpads (three-finger drag, tap-to-drag) often report "no button" mid-drag
            if shift and not self._shift_was and not esc:
                self.toggle_ring.emit()
            if esc:
                QTimer.singleShot(120, self.hide_menu.emit)
            elif not lbtn:
                if self._up_since is None:
                    self._up_since = now
                up_for = now - self._up_since
                # trackpads (tap-to-drag, three-finger drag) can report "no button" for a
                # moment in the middle of a drag: wait a little, and check the drag picture
                if up_for >= UP_DEBOUNCE and not self._drag_still_alive(up_for):
                    # drop happened (or was cancelled) – give the drop event a moment to land
                    QTimer.singleShot(120, self.hide_menu.emit)
            else:
                self._up_since = None
                if not self.menu_got_drag() and (pos - self._shown_at).manhattanLength() > 6:
                    # the cursor is moving over us but no file drag arrived: it's a window
                    # move or text selection, so get out of the way
                    self._idle_ticks += 1
                    if self._idle_ticks > NO_DRAG_TIMEOUT:
                        self.hide_menu.emit()
            if self._darwin is not None and not self.menu_got_drag() and self.fresh_file_drag():
                self.pasteboard_ready.emit()      # Finder wrote the drag a moment late
        else:
            self._up_since = None
            if lbtn:
                if self._down_at is None:
                    self._down_at = pos
                    self._fired = False
                    if self._darwin is not None:
                        self._count_at_down = self._darwin.drag_change_count()
                moved = (pos - self._down_at).manhattanLength() >= DRAG_THRESHOLD
                if self.enabled and moved and shift and not self._fired:
                    self._fired = True
                    self._idle_ticks = 0
                    self._shown_at = pos
                    self.show_menu.emit(pos)
            else:
                self._down_at = None
                self._fired = False
            if self._keys is not None and self.enabled and self.double_tap_enabled:
                m = self._keys
                if hasattr(m, "poll") and (shift or self._tap.seq_start is not None):
                    m.poll(now)                   # Windows: notice keys typed during the taps
                clean = not lbtn and not m.other_modifiers_down(self.key_name)
                if clean and self._tap.seq_start is not None:
                    # a letter typed during the taps: that was Shift for capitals, not a gesture
                    clean = m.seconds_since_key_typed() > now - self._tap.seq_start + 0.02
                if self._tap.update(shift, now, clean):
                    self.double_tap.emit(pos)
        self._shift_was, self._lbtn_was, self._esc_was = shift, lbtn, esc
