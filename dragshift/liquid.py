"""Строгий черный стиль без эффектов стекла."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


@dataclass
class GlassStyle:
    bezel: float = 0.0         # Убираем линзу
    strength: float = 0.0      # Убираем искажение
    dispersion: float = 0.0    # Убираем радугу
    blur: float = 0.0          # Убираем размытие фона (фон не нужен)
    saturation: float = 1.0    
    spec: float = 0.0          # Убираем блики
    light: tuple[float, float] = (-0.55, -0.83)


# ---------------------------------------------------------------- signed distance fields
def sdf_rounded_rect(w: int, h: int, x0: float, y0: float, x1: float, y1: float, r: float) -> np.ndarray:
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    hx, hy = (x1 - x0) / 2 - r, (y1 - y0) / 2 - r
    qx = np.abs(xs - cx) - hx
    qy = np.abs(ys - cy) - hy
    outside = np.hypot(np.maximum(qx, 0), np.maximum(qy, 0))
    inside = np.minimum(np.maximum(qx, qy), 0)
    return outside + inside - r


def sdf_circle(w: int, h: int, cx: float, cy: float, r: float) -> np.ndarray:
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    return np.hypot(xs - cx, ys - cy) - r


def sdf_ring_sector(w: int, h: int, cx: float, cy: float, r0: float, r1: float,
                    a0: float, a1: float, round_r: float = 10.0) -> np.ndarray:
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32) + 0.5
    dx, dy = xs - cx, cy - ys
    rad = np.hypot(dx, dy)
    mid = math.radians((a0 + a1) / 2)
    half = math.radians((a1 - a0) / 2)
    ang = np.arctan2(dy, dx) - mid
    ang = (ang + np.pi) % (2 * np.pi) - np.pi
    side = rad * np.sin(np.abs(ang) - half)
    side = np.where(np.abs(ang) - half > np.pi / 2, rad, side)
    ring = np.maximum(r0 - rad, rad - r1)
    rr = round_r
    ring_s = ring + rr
    side_s = side + rr
    outside = np.hypot(np.maximum(ring_s, 0), np.maximum(side_s, 0))
    inside = np.minimum(np.maximum(ring_s, side_s), 0)
    return outside + inside - rr


def union(*fields: np.ndarray) -> np.ndarray:
    out = fields[0]
    for f in fields[1:]:
        out = np.minimum(out, f)
    return out


# ---------------------------------------------------------------- rendering
def render(backdrop: Image.Image, sdf: np.ndarray, style: GlassStyle = GlassStyle(),
           tint: tuple[int, int, int, float] | None = None) -> tuple[Image.Image, bool]:
    h, w = sdf.shape
    # Создаем сплошной черный фон
    out = np.zeros((h, w, 3), np.float32)
    
    # Формат цвета: (R, G, B). 20, 20, 20 - это темно-серый, почти черный.
    out[:, :] = [20, 20, 20] 

    alpha = np.clip(0.5 - sdf, 0, 1)
    inside = alpha > 0

    # Легкая окантовка по краю, чтобы лепестки не сливались в кашу
    depth = -sdf
    rim = np.clip(1 - depth / 1.5, 0, 1) * inside
    out += (rim[..., None] * np.array([70, 70, 70], np.float32))

    out = np.clip(out, 0, 255).astype(np.uint8)
    rgba = np.dstack([out, (alpha * 255).astype(np.uint8)])
    return Image.fromarray(rgba, "RGBA"), False


def shadow(sdf: np.ndarray, spread: float = 14.0, opacity: float = 0.32, offset: tuple[int, int] = (0, 6)) -> Image.Image:
    d = np.roll(np.roll(sdf, offset[1], axis=0), offset[0], axis=1)
    a = np.clip(1 - np.maximum(d, 0) / spread, 0, 1) ** 2 * opacity
    a = np.where(sdf < 0, 0, a)
    h, w = sdf.shape
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")