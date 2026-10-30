"""Windows helpers for the "tap Shift twice" menu.

* Which files are selected in File Explorer (including Windows 11 tabs) or on the desktop,
  asked through the Shell.Application COM object — the same thing Explorer scripts use.
* Global key state for the double tap: other modifiers held, and whether an ordinary key was
  typed (Shift used for capital letters is not a gesture). Polled with GetAsyncKeyState, so
  no keyboard hook and no admin rights are needed.
"""
from __future__ import annotations

import ctypes
import sys
import time

OK = sys.platform == "win32"
user32 = ctypes.windll.user32 if OK else None

EXPLORER_CLASSES = ("CabinetWClass", "ExploreWClass")
DESKTOP_CLASSES = ("Progman", "WorkerW")

NOT_EXPLORER, NO_SELECTION_API = 1, 2

VK_SHIFT, VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN = 0x10, 0x11, 0x12, 0x5B, 0x5C
MOD_VK = {"shift": VK_SHIFT, "ctrl": VK_CONTROL, "alt": VK_MENU}
# keys whose press means "typing", not a Shift tap: letters, digits, punctuation, space,
# Enter/Tab/Backspace/Delete, arrows/Home/End/PgUp/PgDn (Shift+arrow selects), numpad
TYPING_VKS = tuple(sorted(set(
    [0x08, 0x09, 0x0D, 0x20, 0x2E, 0xE2]
    + list(range(0x21, 0x29)) + list(range(0x30, 0x3A)) + list(range(0x41, 0x5B))
    + list(range(0x60, 0x70)) + list(range(0xBA, 0xC1)) + list(range(0xDB, 0xE0)))))


def _down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


class KeyActivity:
    """Same interface the double-tap logic uses on macOS (other_modifiers_down,
    seconds_since_key_typed). Windows has no "seconds since last key" query, so poll()
    scans the typing keys while a tap may be in progress."""

    def __init__(self):
        self._typed_at = -1e9

    def poll(self, now: float):
        for vk in TYPING_VKS:
            # only "down now": the "pressed since last query" bit can be stale from long ago
            if user32.GetAsyncKeyState(vk) & 0x8000:
                self._typed_at = now
                return

    def seconds_since_key_typed(self) -> float:
        return time.monotonic() - self._typed_at

    def other_modifiers_down(self, name: str) -> bool:
        mods = [VK_CONTROL, VK_MENU, VK_LWIN, VK_RWIN, VK_SHIFT]
        mods.remove(MOD_VK.get(name, VK_SHIFT))
        return any(_down(vk) for vk in mods)


# ---------------------------------------------------------------- Explorer selection
def _class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _window_text(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buf, 512)
    return buf.value


def foreground() -> tuple[str | None, int]:
    """('explorer' | 'desktop' | None, hwnd of the foreground window)."""
    if not OK:
        return None, 0
    hwnd = user32.GetForegroundWindow() or 0
    cls = _class_name(hwnd)
    if cls in EXPLORER_CLASSES:
        return "explorer", hwnd
    if cls in DESKTOP_CLASSES:
        return "desktop", hwnd
    return None, hwnd


def explorer_frontmost() -> bool:
    return foreground()[0] is not None


def _paths(items) -> list[str]:
    out = []
    for i in range(int(items.Count)):
        try:
            it = items.Item(i)
            p = str(it.Path or "")
            if p and (bool(it.IsFileSystem) or bool(it.IsLink)) and not bool(it.IsFolder):
                out.append(p)
        except Exception:
            continue
    return out


def _active_tab(hwnd) -> int:
    """Windows 11 File Explorer: the first ShellTabWindowClass child is the visible tab."""
    return user32.FindWindowExW(hwnd, None, "ShellTabWindowClass", None) or 0


def _tab_hwnd(win) -> int:
    """HWND of the tab a Shell.Application window object belongs to (0 if unknown)."""
    try:
        import pythoncom
        from win32com.shell import shell
        sp = win._oleobj_.QueryInterface(pythoncom.IID_IServiceProvider)
        sb = sp.QueryService(shell.IID_IShellBrowser, shell.IID_IShellBrowser)
        return int(sb.GetWindow())
    except Exception:
        return 0


def _desktop_window(shell_app):
    """The desktop's folder view (IShellWindows.FindWindowSW with SWC_DESKTOP)."""
    import pythoncom
    import win32com.client
    windows = shell_app.Windows()
    ole = windows._oleobj_
    dispid = ole.GetIDsOfNames("FindWindowSW")
    empty = win32com.client.VARIANT(pythoncom.VT_EMPTY, None)
    loc = win32com.client.VARIANT(pythoncom.VT_I4, 0)          # CSIDL_DESKTOP
    # FindWindowSW([in] VARIANT*, [in] VARIANT*, [in] int SWC_DESKTOP=8, [out] long* hwnd,
    #              [in] int SWFO_NEEDDISPATCH=1) -> IDispatch*
    types = ((pythoncom.VT_VARIANT | pythoncom.VT_BYREF, 1),
             (pythoncom.VT_VARIANT | pythoncom.VT_BYREF, 1),
             (pythoncom.VT_I4, 1),
             (pythoncom.VT_I4 | pythoncom.VT_BYREF, 3),
             (pythoncom.VT_I4, 1))
    attempts = (
        lambda: ole.InvokeTypes(dispid, 0, pythoncom.DISPATCH_METHOD, (pythoncom.VT_DISPATCH, 0),
                                types, loc, empty, 8, 0, 1),
        lambda: windows.FindWindowSW(0, empty, 8, 0, 1),
        lambda: windows.FindWindowSW(loc, empty, 8, 0, 1),
    )
    last = None
    for i, call in enumerate(attempts):
        try:
            res = call()
            disp = res[0] if isinstance(res, tuple) else res
            if disp is None:
                raise RuntimeError("no desktop window")
            win = disp if hasattr(disp, "Document") else win32com.client.Dispatch(disp)
            win.Document                              # must expose the folder view
            if i:
                print(f"desktop view via fallback {i}", flush=True)
            return win
        except Exception as e:
            last = e
    raise last


def explorer_selection() -> tuple[list[str], int]:
    """Files selected in the foreground File Explorer window (active tab) or on the desktop.
    Returns (paths, error); error 0 means the question was answered (maybe nothing selected)."""
    kind, hwnd = foreground()
    if kind is None:
        return [], NOT_EXPLORER
    try:
        import pythoncom
        import win32com.client
        try:
            pythoncom.CoInitialize()
        except Exception:
            pass
        shell_app = win32com.client.Dispatch("Shell.Application")
        if kind == "desktop":
            return _paths(_desktop_window(shell_app).Document.SelectedItems()), 0
        matches = []
        for w in shell_app.Windows():
            try:
                if int(w.HWND) == hwnd:
                    matches.append(w)
            except Exception:
                continue
        if not matches:
            return [], NO_SELECTION_API
        if len(matches) > 1:                         # tabs: pick the one that is showing
            tab = _active_tab(hwnd)
            exact = [w for w in matches if tab and _tab_hwnd(w) == tab]
            if exact:
                matches = exact
            else:                                    # fall back to the window title
                title = _window_text(hwnd)
                named = [w for w in matches if str(w.LocationName or "") and title.startswith(str(w.LocationName))]
                matches = named or matches
        return _paths(matches[0].Document.SelectedItems()), 0
    except Exception as e:
        print("explorer selection failed:", repr(e), flush=True)
        return [], NO_SELECTION_API
