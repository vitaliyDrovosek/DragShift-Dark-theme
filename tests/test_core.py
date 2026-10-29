"""Run with: python -m pytest -q"""
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from dragshift import convert, imaging
from dragshift.util import category, sibling


@pytest.fixture
def img(tmp_path) -> Path:
    im = Image.new("RGBA", (640, 420), (255, 255, 255, 0))
    d = ImageDraw.Draw(im)
    d.rectangle((40, 40, 600, 380), fill=(255, 120, 80, 255))
    d.text((60, 60), "DragShift test", fill=(0, 0, 0, 255))
    p = tmp_path / "Page 001.png"
    exif = Image.Exif()
    exif[0x010F] = "TestCam"  # Make
    im.save(p, exif=exif)
    return p


@pytest.fixture
def pdf(tmp_path, img) -> Path:
    doc = convert.fitz.open()
    for i in range(2):
        page = doc.new_page()
        page.insert_text((72, 72), f"Hello page {i + 1}", fontsize=24)
        page.insert_text((72, 120), "Body text line for extraction.", fontsize=11)
        page.insert_image(convert.fitz.Rect(72, 150, 300, 300), filename=str(img))
    doc.set_metadata({"author": "Jimmy", "title": "Demo"})
    p = tmp_path / "Doc.pdf"
    doc.save(p)
    return p


@pytest.mark.parametrize("target", convert.targets_for("image", ".png"))
def test_image_targets(img, target):
    out = convert.convert(img, "image", target)[0]
    assert out.exists() and out.stat().st_size > 0
    if target != "PDF":
        Image.open(out).load()


def test_pdf_conversions(pdf):
    imgs = convert.convert(pdf, "pdf", "JPG")
    assert len(imgs) == 2 and all(p.exists() for p in imgs)
    txt = convert.convert(pdf, "pdf", "TXT")[0]
    assert "Hello page 2" in txt.read_text()
    docx = convert.convert(pdf, "pdf", "DOCX")[0]
    from docx import Document
    d = Document(docx)
    assert any("Hello page 1" in p.text for p in d.paragraphs)
    assert d.inline_shapes, "images should be carried over"


def test_docx_and_text(tmp_path, pdf):
    docx = convert.convert(pdf, "pdf", "DOCX")[0]
    out_pdf = convert.convert(docx, "docx", "PDF")[0]
    with convert.fitz.open(out_pdf) as d:
        assert "Hello page 1" in d[0].get_text()
    assert "Hello" in convert.convert(docx, "docx", "TXT")[0].read_text()
    t = tmp_path / "notes.txt"
    t.write_text("line one\nline two <b>not bold</b>\n" * 80)
    tp = convert.convert(t, "text", "PDF")[0]
    with convert.fitz.open(tp) as d:
        assert d.page_count >= 2 and "<b>not bold</b>" in d[0].get_text()
    assert convert.convert(t, "text", "DOCX")[0].exists()


def test_tools(img, pdf):
    im = convert.open_image(img)
    assert imaging.save_like(im.crop((0, 0, 100, 100)), img, "Cropped").name == "Page 001 Cropped.png"
    bg = imaging.add_background(im, imaging.Background(aspect="16:9"))
    assert abs(bg.width / bg.height - 16 / 9) < 0.01
    red = imaging.redact(im, [(40, 40, 200, 200)], "black")
    assert red.getpixel((100, 100))[:3] == (0, 0, 0)
    for m in ("pixelate", "blur"):
        imaging.redact(im, [(40, 40, 200, 200)], m)
    ed = imaging.apply_adjust(im, imaging.Adjust(brightness=1.2, rotate=90, flip_h=True, warmth=0.5, resize_pct=50))
    assert ed.size == (210, 320)
    assert "Make" in imaging.read_image_metadata(img)
    clean = imaging.strip_image_metadata(img)
    assert "Make" not in imaging.read_image_metadata(clean)
    c = imaging.compress_image(img, 60)
    assert c.exists()
    assert imaging.compress_image(img, 60, 300, to_webp=True).suffix == ".webp"
    assert imaging.read_pdf_metadata(pdf)["author"] == "Jimmy"
    assert "author" not in imaging.read_pdf_metadata(imaging.strip_pdf_metadata(pdf))
    assert len(imaging.split_pdf(pdf)) == 2
    assert imaging.compress_pdf(pdf).exists()
    assert imaging.rotate_pdf(pdf).exists()
    assert imaging.merge_pdfs([pdf, pdf]).exists()
    assert convert.images_to_single_pdf([img, img])[0].exists()


def test_paths(tmp_path):
    f = tmp_path / "a.jpg"
    f.write_bytes(b"x")
    assert sibling(f, ext=".jpg").name == "a (1).jpg"
    assert category("x.HEIC") == "image" and category("x.pdf") == "pdf" and category("x.zip") is None


@pytest.mark.skipif(__import__("sys").platform != "win32", reason="Windows shortcuts")
def test_shortcut_resolves_to_target(img, tmp_path):
    import win32com.client
    from dragshift.util import resolve_shortcuts
    lnk = tmp_path / "pic.lnk"
    sc = win32com.client.Dispatch("WScript.Shell").CreateShortcut(str(lnk))
    sc.TargetPath = str(img)
    sc.Save()
    out = resolve_shortcuts([str(lnk)])
    assert Path(out[0]) == img and category(out[0]) == "image"
    assert resolve_shortcuts([str(img)]) == [str(img)]


# ---------------------------------------------------------------- double tap (macOS Finder menu)
def test_double_tap_fires_on_two_quick_taps():
    from dragshift.trigger import DoubleTap
    d = DoubleTap()
    seq = [(False, 0.0), (True, 0.10), (False, 0.18), (True, 0.40), (False, 0.48)]
    fired = [d.update(k, t) for k, t in seq]
    assert fired == [False, False, False, False, True]


def test_double_tap_ignores_slow_held_and_dirty_taps():
    from dragshift.trigger import DoubleTap
    d = DoubleTap()   # gap too long
    assert not any(d.update(k, t) for k, t in [(True, 0.0), (False, 0.1), (True, 1.0), (False, 1.1)])
    d = DoubleTap()   # second press held (Shift used for typing / selecting)
    assert not any(d.update(k, t) for k, t in [(True, 0.0), (False, 0.1), (True, 0.3), (False, 1.2)])
    d = DoubleTap()   # something else happened in between (mouse button, letter typed)
    out = [d.update(True, 0.0), d.update(False, 0.1), d.update(False, 0.2, clean=False),
           d.update(True, 0.3), d.update(False, 0.4)]
    assert not any(out)
    d = DoubleTap()   # a slow first tap starts over, then two quick taps still work
    out = [d.update(k, t) for k, t in [(True, 0.0), (False, 0.1), (True, 2.0), (False, 2.1), (True, 2.3), (False, 2.4)]]
    assert out[-1] and sum(out) == 1


def _fake_watcher(monkeypatch, drag_alive=False):
    """A DragShiftWatcher wired to a fake macOS input layer and a fake clock."""
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QApplication
    from dragshift import trigger
    QApplication.instance() or QApplication([])

    class FakeMac:
        btn = shift = esc = False
        typed_ago = 1e9
        count = 1
        alive = drag_alive
        def left_button_down(self): return self.btn
        def key_down(self, name): return self.shift
        def escape_down(self): return self.esc
        def drag_change_count(self): return self.count
        def drag_session_active(self): return self.alive
        def other_modifiers_down(self, name): return False
        def seconds_since_key_typed(self): return self.typed_ago

    clock = {"t": 100.0}
    monkeypatch.setattr(trigger.time, "monotonic", lambda: clock["t"])
    pos = {"p": QPoint(100, 100)}
    monkeypatch.setattr(trigger.QCursor, "pos", staticmethod(lambda: pos["p"]))
    state = {"visible": False, "got": False}
    w = trigger.DragShiftWatcher(lambda: state["visible"], lambda: state["got"])
    fake = FakeMac()
    w._mac = w._darwin = fake
    ev = {"show": 0, "hide": 0, "tap": 0}
    w.show_menu.connect(lambda p: (ev.__setitem__("show", ev["show"] + 1), state.__setitem__("visible", True)))
    w.double_tap.connect(lambda p: ev.__setitem__("tap", ev["tap"] + 1))
    monkeypatch.setattr(trigger.QTimer, "singleShot", staticmethod(lambda ms, f: ev.__setitem__("hide", ev["hide"] + 1)))
    w.hide_menu.connect(lambda: ev.__setitem__("hide", ev["hide"] + 1))

    def tick(dt=0.015, **kw):
        for k, v in kw.items():
            setattr(fake, k, v)
        clock["t"] += dt
        w._tick()
    return w, fake, pos, ev, tick, state


def test_trackpad_flicker_does_not_close_the_menu(monkeypatch):
    from PySide6.QtCore import QPoint
    w, fake, pos, ev, tick, state = _fake_watcher(monkeypatch)
    tick(btn=True)
    pos["p"] = QPoint(130, 100); fake.count = 2          # Finder starts the drag
    tick(btn=True, shift=True)
    assert ev["show"] == 1 and w.fresh_file_drag()
    tick(btn=False); tick(btn=False); tick(btn=False)   # 45 ms "no button": trackpad blip
    assert ev["hide"] == 0
    tick(btn=True)
    for _ in range(10):                                  # real release
        tick(btn=False)
    assert ev["hide"] >= 1


def test_drag_picture_keeps_menu_open_while_button_reads_up(monkeypatch):
    from PySide6.QtCore import QPoint
    w, fake, pos, ev, tick, state = _fake_watcher(monkeypatch, drag_alive=True)
    tick(btn=True); pos["p"] = QPoint(130, 100); tick(btn=True, shift=True)
    for _ in range(40):                                  # three-finger drag: no button for 0.6 s
        tick(btn=False, shift=False)
    assert ev["hide"] == 0
    fake.alive = False                                   # drag picture gone = drop finished
    tick(dt=0.1, btn=False)
    assert ev["hide"] >= 1


def test_stale_drag_pasteboard_is_not_fresh(monkeypatch):
    from PySide6.QtCore import QPoint
    w, fake, pos, ev, tick, state = _fake_watcher(monkeypatch)
    tick(btn=True); pos["p"] = QPoint(130, 100); tick(btn=True, shift=True)   # count unchanged
    assert ev["show"] == 1 and not w.fresh_file_drag()


def test_double_tap_shift_emits_and_typing_does_not(monkeypatch):
    w, fake, pos, ev, tick, state = _fake_watcher(monkeypatch)
    tick(); tick(dt=0.1, shift=True); tick(dt=0.08, shift=False); tick(dt=0.2, shift=True); tick(dt=0.08, shift=False)
    assert ev["tap"] == 1
    tick(dt=1.0)
    tick(dt=0.1, shift=True); tick(dt=0.08, shift=False)
    fake.typed_ago = 0.05                                # a capital letter was just typed
    tick(dt=0.2, shift=True); tick(dt=0.08, shift=False)
    assert ev["tap"] == 1
