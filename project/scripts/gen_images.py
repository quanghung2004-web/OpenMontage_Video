#!/usr/bin/env python3
"""Stage 2: procedurally generate every background scene as a stylized flat
silhouette illustration (no external image assets — this sandbox cannot
reach Pexels/BBC/NatGeo, so visuals are original generated art instead).

Style: gradient sky, silhouette wildlife, flat "documentary title card"
aesthetic. Canvas is oversized relative to the 1080p output so ffmpeg's
zoompan filter has room to pan/zoom (Ken Burns effect).
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "project" / "assets" / "images"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 2400, 1350  # oversized 16:9 canvas for Ken Burns headroom

PALETTES = {
    "dawn":      {"sky_top": (255, 187, 92), "sky_bot": (255, 235, 175), "sun": (255, 244, 214), "silhouette": (72, 40, 28), "ground": (94, 54, 32)},
    "sunset":    {"sky_top": (255, 128, 60),  "sky_bot": (255, 198, 120), "sun": (255, 236, 179), "silhouette": (48, 24, 20), "ground": (72, 38, 24)},
    "tense":     {"sky_top": (214, 96, 48),   "sky_bot": (247, 176, 96),  "sun": (255, 232, 170), "silhouette": (36, 18, 14), "ground": (66, 34, 20)},
    "mysterious":{"sky_top": (33, 56, 58),    "sky_bot": (94, 116, 96),   "sun": (214, 224, 180), "silhouette": (16, 22, 18), "ground": (30, 34, 24)},
    "heroic":    {"sky_top": (255, 170, 66),  "sky_bot": (255, 214, 140), "sun": (255, 244, 210), "silhouette": (44, 26, 16), "ground": (76, 44, 24)},
    "uplifting": {"sky_top": (120, 176, 224), "sky_bot": (255, 214, 150), "sun": (255, 248, 224), "silhouette": (40, 34, 46), "ground": (70, 56, 40)},
    "night":     {"sky_top": (16, 24, 40),    "sky_bot": (54, 62, 78),    "sun": (220, 224, 210), "silhouette": (8, 10, 14), "ground": (20, 20, 18)},
}

random.seed(42)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def vertical_gradient(w, h, top, bottom):
    img = Image.new("RGB", (w, h), top)
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        c = lerp(top, bottom, t ** 0.85)
        for x in range(w):
            px[x, y] = c
    return img


def add_sun(draw, cx, cy, r, color, glow=True):
    if glow:
        for i in range(6, 0, -1):
            alpha_r = r + i * 22
            glow_color = tuple(min(255, c) for c in color)
            draw.ellipse([cx - alpha_r, cy - alpha_r, cx + alpha_r, cy + alpha_r],
                         fill=None, outline=glow_color, width=3)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


def add_ground(img, draw, ground_color, horizon_y, w, h):
    draw.rectangle([0, horizon_y, w, h], fill=ground_color)
    # subtle grass texture blades
    blade_color = tuple(max(0, c - 14) for c in ground_color)
    rng = random.Random(7)
    for _ in range(int(w * 0.18)):
        x = rng.uniform(0, w)
        y = rng.uniform(horizon_y + 6, h - 8)
        bh = rng.uniform(10, 34)
        bw = rng.uniform(1.5, 3.5)
        lean = rng.uniform(-6, 6)
        draw.line([(x, y), (x + lean, y - bh)], fill=blade_color, width=int(bw))


def add_acacia(draw, x, base_y, scale, color):
    trunk_h = 60 * scale
    trunk_w = 6 * scale
    draw.rectangle([x - trunk_w / 2, base_y - trunk_h, x + trunk_w / 2, base_y], fill=color)
    canopy_w = 130 * scale
    canopy_h = 26 * scale
    cy = base_y - trunk_h - canopy_h / 2
    draw.ellipse([x - canopy_w / 2, cy - canopy_h / 2, x + canopy_w / 2, cy + canopy_h / 2], fill=color)
    # flat spread top typical of acacia
    draw.ellipse([x - canopy_w * 0.65, cy - canopy_h * 0.3, x + canopy_w * 0.65, cy + canopy_h * 0.5], fill=color)


def base_scene(mood_key, horizon_frac=0.62, sun_pos=(0.78, 0.30), sun_r=70, n_trees=3, stars=False):
    pal = PALETTES[mood_key]
    img = vertical_gradient(W, H, pal["sky_top"], pal["sky_bot"])
    draw = ImageDraw.Draw(img)
    horizon_y = int(H * horizon_frac)
    if stars:
        rng = random.Random(3)
        for _ in range(140):
            x, y = rng.uniform(0, W), rng.uniform(0, horizon_y * 0.7)
            r = rng.uniform(0.5, 1.8)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(230, 230, 220))
    add_sun(draw, int(W * sun_pos[0]), int(H * sun_pos[1]), sun_r, pal["sun"])
    add_ground(img, draw, pal["ground"], horizon_y, W, H)
    rng = random.Random(11)
    for i in range(n_trees):
        # Keep trees out of the center band where the hero animal sits.
        if rng.random() < 0.5:
            x = rng.uniform(W * 0.02, W * 0.20)
        else:
            x = rng.uniform(W * 0.82, W * 0.98)
        scale = rng.uniform(0.7, 1.5)
        base_y = horizon_y + rng.uniform(10, 40)
        add_acacia(draw, x, base_y, scale, pal["silhouette"])
    return img, draw, pal, horizon_y


# ---------------------------------------------------------------- animals --

def poly(draw, pts, color):
    draw.polygon(pts, fill=color)


def cheetah_silhouette(draw, cx, cy, scale, color, running=True, facing=1, spots=True, panting=False):
    """Build a cheetah out of composited body/leg/tail/head shapes."""
    s = scale
    body_len, body_h = 190 * s, 62 * s
    body = [cx - body_len / 2, cy - body_h / 2, cx + body_len / 2, cy + body_h / 2]
    draw.ellipse(body, fill=color)

    # chest taper
    draw.ellipse([cx - body_len / 2 - 18 * s, cy - body_h / 2 + 8 * s,
                  cx - body_len / 2 + 30 * s, cy + body_h / 2 - 4 * s], fill=color)

    head_cx = cx - facing * (body_len / 2 + 26 * s)
    head_cy = cy - body_h * 0.32 if not panting else cy + body_h * 0.05
    head_r = 26 * s
    # rounded skull
    draw.ellipse([head_cx - head_r, head_cy - head_r, head_cx + head_r * 0.9, head_cy + head_r * 0.85], fill=color)
    # muzzle (small snout bump on the facing side)
    muzzle_r = head_r * 0.55
    mux = head_cx - facing * head_r * 0.85
    draw.ellipse([mux - muzzle_r, head_cy + head_r * 0.05 - muzzle_r * 0.7,
                  mux + muzzle_r, head_cy + head_r * 0.05 + muzzle_r * 0.7], fill=color)
    if panting:
        mx = head_cx - facing * head_r * 0.9
        draw.polygon([(mx, head_cy + 10 * s), (mx - facing * 22 * s, head_cy + 8 * s),
                      (mx - facing * 2 * s, head_cy + 26 * s)], fill=color)
    # two small triangular cat ears sitting on top of the skull
    ear_h, ear_w = 16 * s, 12 * s
    for dx in (-0.55, 0.35):
        ex = head_cx + dx * head_r
        draw.polygon([
            (ex - ear_w / 2, head_cy - head_r * 0.65),
            (ex + ear_w / 2, head_cy - head_r * 0.65),
            (ex, head_cy - head_r * 0.65 - ear_h),
        ], fill=color)

    # tail — long curved, made of segmented ellipses
    tail_base = (cx + facing * (body_len / 2 - 10 * s), cy - 4 * s)
    prev = tail_base
    ang = -25 if running else -10
    for i in range(7):
        length = 20 * s
        a = math.radians(ang + i * (14 if running else 6) * facing)
        nx = prev[0] + facing * length * math.cos(a)
        ny = prev[1] + length * math.sin(a) - i * 2 * s
        r = max(4 * s, 9 * s - i * 0.9 * s)
        draw.ellipse([nx - r, ny - r, nx + r, ny + r], fill=color)
        prev = (nx, ny)

    # legs
    leg_w = 9 * s
    if running:
        leg_positions = [
            (cx - facing * body_len * 0.32, 1, -55),
            (cx - facing * body_len * 0.12, 1, 35),
            (cx + facing * body_len * 0.12, -1, -35),
            (cx + facing * body_len * 0.34, -1, 55),
        ]
        for lx, dirn, ang_deg in leg_positions:
            a = math.radians(ang_deg)
            length = 78 * s
            ex = lx + dirn * length * math.sin(a) * facing
            ey = cy + body_h * 0.35 + length * math.cos(a)
            draw.line([(lx, cy + body_h * 0.30), (ex, ey)], fill=color, width=int(leg_w))
            draw.ellipse([ex - leg_w * 0.6, ey - leg_w * 0.6, ex + leg_w * 0.6, ey + leg_w * 0.6], fill=color)
    else:
        for lx in [cx - facing * body_len * 0.28, cx + facing * body_len * 0.28]:
            ey = cy + body_h * 0.9
            draw.line([(lx, cy + body_h * 0.25), (lx, ey)], fill=color, width=int(leg_w))

    if spots:
        rng = random.Random(int(cx + cy))
        spot_color = tuple(max(0, c - 20) for c in color)
        for _ in range(int(26 * s)):
            sx = cx + rng.uniform(-body_len / 2, body_len / 2)
            sy = cy + rng.uniform(-body_h / 2, body_h / 2)
            r = rng.uniform(2, 4) * s
            draw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=spot_color)
    return head_cx, head_cy


def big_cat_body(draw, cx, cy, scale, color, crouch=False, mane=False):
    s = scale
    body_len, body_h = 210 * s, 92 * s if not crouch else 70 * s
    draw.ellipse([cx - body_len / 2, cy - body_h / 2, cx + body_len / 2, cy + body_h / 2], fill=color)
    head_cx, head_cy = cx - body_len / 2 - 22 * s, cy - body_h * 0.15
    if mane:
        mane_r = 46 * s
        draw.ellipse([head_cx - mane_r, head_cy - mane_r, head_cx + mane_r, head_cy + mane_r],
                     fill=tuple(max(0, c - 15) for c in color))
    head_r = 30 * s
    draw.ellipse([head_cx - head_r, head_cy - head_r * 0.85, head_cx + head_r, head_cy + head_r * 0.85], fill=color)
    muzzle_r = head_r * 0.45
    draw.ellipse([head_cx - head_r * 0.9 - muzzle_r, head_cy + head_r * 0.1 - muzzle_r * 0.6,
                  head_cx - head_r * 0.9 + muzzle_r, head_cy + head_r * 0.1 + muzzle_r * 0.6], fill=color)
    ear_h, ear_w = 18 * s, 16 * s
    for dx in (-14, 14):
        ex = head_cx + dx * s
        draw.polygon([(ex - ear_w / 2, head_cy - head_r * 0.7), (ex + ear_w / 2, head_cy - head_r * 0.7),
                      (ex, head_cy - head_r * 0.7 - ear_h)], fill=color)
    # legs
    leg_w = 13 * s
    ys = cy + body_h * 0.42
    for lx in [cx - body_len * 0.32, cx - body_len * 0.05, cx + body_len * 0.12, cx + body_len * 0.34]:
        leg_h = (60 if crouch else 95) * s
        draw.line([(lx, ys - 6 * s), (lx, ys + leg_h)], fill=color, width=int(leg_w))
    # tail with tuft
    tx, ty = cx + body_len / 2, cy
    draw.line([(tx, ty), (tx + 60 * s, ty - 40 * s)], fill=color, width=int(9 * s))
    draw.ellipse([tx + 55 * s, ty - 52 * s, tx + 75 * s, ty - 32 * s], fill=color)
    return head_cx, head_cy


def elephant_body(draw, cx, cy, scale, color, calf=False):
    s = scale * (0.55 if calf else 1.0)
    body_len, body_h = 230 * s, 150 * s
    draw.ellipse([cx - body_len / 2, cy - body_h / 2, cx + body_len / 2, cy + body_h / 2], fill=color)
    head_cx = cx - body_len / 2 - 40 * s
    head_r = 70 * s
    draw.ellipse([head_cx - head_r * 0.6, cy - body_h * 0.55, head_cx + head_r * 0.5, cy + body_h * 0.25], fill=color)
    # ear (big flat fan)
    ear_w, ear_h = 90 * s, 120 * s
    draw.ellipse([head_cx - ear_w * 0.3, cy - body_h * 0.5, head_cx + ear_w * 0.7, cy + body_h * 0.35], fill=color)
    draw.ellipse([head_cx - ear_w * 0.15, cy - body_h * 0.38, head_cx + ear_w * 0.5, cy + body_h * 0.20],
                 fill=tuple(min(255, c + 12) for c in color))
    # trunk, curved down
    prev = (head_cx - head_r * 0.5, cy)
    for i in range(8):
        a = math.radians(75 + i * 6)
        length = 16 * s
        nx = prev[0] - length * math.cos(a) * 0.5
        ny = prev[1] + length
        r = max(6 * s, 13 * s - i * s * 0.6)
        draw.ellipse([nx - r, ny - r, nx + r, ny + r], fill=color)
        prev = (nx, ny)
    # legs (thick columns)
    leg_w = 30 * s
    ys = cy + body_h * 0.42
    for lx in [cx - body_len * 0.28, cx - body_len * 0.02, cx + body_len * 0.18, cx + body_len * 0.36]:
        draw.rectangle([lx - leg_w / 2, ys, lx + leg_w / 2, ys + 90 * s], fill=color)
    # tail
    draw.line([(cx + body_len / 2, cy), (cx + body_len / 2 + 10 * s, cy + 50 * s)], fill=color, width=int(6 * s))
    return head_cx, cy


def zebra_body(draw, cx, cy, scale, color, stripe_color):
    s = scale
    body_len, body_h = 175 * s, 75 * s
    bbox = [cx - body_len / 2, cy - body_h / 2, cx + body_len / 2, cy + body_h / 2]
    draw.ellipse(bbox, fill=color)
    # clip stripes using a mask
    mask = Image.new("L", (int(body_len), int(body_h)), 0)
    mdraw = ImageDraw.Draw(mask)
    mdraw.ellipse([0, 0, body_len, body_h], fill=255)
    stripe_layer = Image.new("RGB", (int(body_len), int(body_h)), color)
    sdraw = ImageDraw.Draw(stripe_layer)
    n_stripes = 10
    for i in range(n_stripes):
        x = i * (body_len / n_stripes)
        sdraw.polygon([(x, 0), (x + 10 * s, 0), (x - 6 * s, body_h), (x - 24 * s, body_h)], fill=stripe_color)
    base_img = draw._image
    base_img.paste(stripe_layer, (int(bbox[0]), int(bbox[1])), mask)
    draw = ImageDraw.Draw(base_img)

    head_cx, head_cy = cx - body_len / 2 - 20 * s, cy - body_h * 0.35
    head_r = 22 * s
    draw.ellipse([head_cx - head_r, head_cy - head_r, head_cx + head_r * 0.8, head_cy + head_r], fill=color)
    # mane
    for i in range(6):
        mx = head_cx + 10 * s + i * 6 * s
        draw.line([(mx, head_cy - head_r), (mx, cy - body_h / 2)], fill=stripe_color, width=int(4 * s))
    leg_w = 9 * s
    ys = cy + body_h * 0.4
    for lx in [cx - body_len * 0.3, cx - body_len * 0.05, cx + body_len * 0.15, cx + body_len * 0.35]:
        draw.line([(lx, ys), (lx, ys + 65 * s)], fill=color, width=int(leg_w))
    draw.line([(cx + body_len / 2, cy), (cx + body_len / 2 + 5 * s, cy + 45 * s)], fill=color, width=int(6 * s))
    return head_cx, head_cy


def antelope_body(draw, cx, cy, scale, color, horns=True, ears_big=False):
    s = scale
    body_len, body_h = 140 * s, 58 * s
    draw.ellipse([cx - body_len / 2, cy - body_h / 2, cx + body_len / 2, cy + body_h / 2], fill=color)
    head_cx, head_cy = cx - body_len / 2 - 20 * s, cy - body_h * 0.5
    head_r = 16 * s
    draw.ellipse([head_cx - head_r, head_cy - head_r, head_cx + head_r, head_cy + head_r], fill=color)
    if horns:
        for dx in (-4, 4):
            draw.line([(head_cx + dx * s, head_cy - head_r), (head_cx + dx * s - 6 * s, head_cy - head_r - 46 * s)],
                      fill=color, width=int(4 * s))
    if ears_big:
        draw.ellipse([head_cx - 6 * s, head_cy - head_r - 14 * s, head_cx + 20 * s, head_cy - head_r + 8 * s], fill=color)
    leg_w = 6 * s
    ys = cy + body_h * 0.42
    for lx in [cx - body_len * 0.32, cx - body_len * 0.06, cx + body_len * 0.1, cx + body_len * 0.34]:
        draw.line([(lx, ys), (lx, ys + 60 * s)], fill=color, width=int(leg_w))
    return head_cx, head_cy


def meerkat_body(draw, cx, cy, scale, color, sentinel=False):
    s = scale
    body_w, body_h = 34 * s, 80 * s
    draw.rounded_rectangle([cx - body_w / 2, cy - body_h, cx + body_w / 2, cy], radius=body_w / 2, fill=color)
    head_r = 16 * s
    draw.ellipse([cx - head_r, cy - body_h - head_r * 1.6, cx + head_r, cy - body_h + head_r * 0.4], fill=color)
    if sentinel:
        # tail as prop for balance
        draw.line([(cx, cy), (cx + 4 * s, cy + 40 * s)], fill=color, width=int(10 * s))
    for lx in (cx - body_w * 0.25, cx + body_w * 0.25):
        draw.line([(lx, cy), (lx, cy + 14 * s)], fill=color, width=int(8 * s))
    return cx, cy - body_h


def wild_dog_body(draw, cx, cy, scale, color):
    s = scale
    body_len, body_h = 120 * s, 46 * s
    draw.ellipse([cx - body_len / 2, cy - body_h / 2, cx + body_len / 2, cy + body_h / 2], fill=color)
    head_cx, head_cy = cx - body_len / 2 - 18 * s, cy - body_h * 0.3
    head_r = 18 * s
    draw.ellipse([head_cx - head_r, head_cy - head_r, head_cx + head_r, head_cy + head_r], fill=color)
    ear_h = 16 * s
    draw.polygon([(head_cx - 6 * s, head_cy - head_r), (head_cx - 12 * s, head_cy - head_r - ear_h),
                  (head_cx, head_cy - head_r)], fill=color)
    draw.polygon([(head_cx + 10 * s, head_cy - head_r), (head_cx + 16 * s, head_cy - head_r - ear_h),
                  (head_cx + 4 * s, head_cy - head_r)], fill=color)
    leg_w = 7 * s
    ys = cy + body_h * 0.4
    for lx in [cx - body_len * 0.3, cx - body_len * 0.02, cx + body_len * 0.16, cx + body_len * 0.34]:
        draw.line([(lx, ys), (lx, ys + 55 * s)], fill=color, width=int(leg_w))
    draw.line([(cx + body_len / 2, cy), (cx + body_len / 2 + 22 * s, cy - 8 * s)], fill=color, width=int(6 * s))
    return head_cx, head_cy


def leopard_texture(draw, cx, cy, scale, color, spot_color):
    s = scale
    body_len, body_h = 200 * s, 78 * s
    draw.ellipse([cx - body_len / 2, cy - body_h / 2, cx + body_len / 2, cy + body_h / 2], fill=color)
    rng = random.Random(int(cx * 3 + cy))
    for _ in range(60):
        sx = cx + rng.uniform(-body_len / 2 + 10, body_len / 2 - 10)
        sy = cy + rng.uniform(-body_h / 2 + 8, body_h / 2 - 8)
        r = rng.uniform(4, 8) * s
        # rosette: ring of small arcs
        for a in range(0, 360, 60):
            rad = math.radians(a)
            ex, ey = sx + r * 0.7 * math.cos(rad), sy + r * 0.7 * math.sin(rad)
            draw.ellipse([ex - r * 0.35, ey - r * 0.35, ex + r * 0.35, ey + r * 0.35], fill=spot_color)
    head_cx, head_cy = cx - body_len / 2 - 26 * s, cy - body_h * 0.3
    head_r = 26 * s
    draw.ellipse([head_cx - head_r, head_cy - head_r * 0.8, head_cx + head_r, head_cy + head_r * 0.8], fill=color)
    for lx in [cx - body_len * 0.3, cx + body_len * 0.3]:
        draw.line([(lx, cy + body_h * 0.3), (lx, cy + body_h * 0.3 + 60 * s)], fill=color, width=int(10 * s))
    return head_cx, head_cy


# --------------------------------------------------------------- scenes ---

def save(img, name):
    path = OUT / f"{name}.png"
    img.save(path, "PNG")
    print("wrote", path.name)


def scene_dawn_savanna_wide():
    img, draw, pal, hz = base_scene("dawn", horizon_frac=0.60, n_trees=4)
    antelope_body(draw, W * 0.30, hz + 34, 0.9, pal["silhouette"])
    antelope_body(draw, W * 0.36, hz + 40, 0.75, pal["silhouette"])
    save(img, "dawn_savanna_wide")


def scene_sunset_acacia():
    img, draw, pal, hz = base_scene("sunset", horizon_frac=0.64, sun_pos=(0.5, 0.42), sun_r=95, n_trees=5)
    save(img, "sunset_acacia")


def scene_cheetah_run_side():
    img, draw, pal, hz = base_scene("tense", horizon_frac=0.66, n_trees=2)
    cheetah_silhouette(draw, W * 0.52, hz + 10, 1.5, pal["silhouette"], running=True, facing=1)
    save(img, "cheetah_run_side")


def scene_cheetah_face():
    img, draw, pal, hz = base_scene("tense", horizon_frac=0.60, sun_pos=(0.24, 0.26), n_trees=2)
    cheetah_silhouette(draw, W * 0.56, hz + 40, 2.5, pal["silhouette"], running=False, facing=-1, spots=True)
    save(img, "cheetah_face")


def scene_motion_streak():
    img, draw, pal, hz = base_scene("tense", horizon_frac=0.66, n_trees=1)
    # speed streak lines
    rng = random.Random(5)
    for _ in range(40):
        y = rng.uniform(hz * 0.3, hz + 60)
        length = rng.uniform(120, 420)
        x = rng.uniform(0, W)
        w = rng.uniform(2, 6)
        draw.line([(x, y), (x - length, y)], fill=(255, 255, 240), width=int(w))
    cheetah_silhouette(draw, W * 0.55, hz + 10, 1.6, pal["silhouette"], running=True, facing=1)
    save(img, "motion_streak")


def scene_exhausted_cheetah():
    img, draw, pal, hz = base_scene("sunset", horizon_frac=0.62, sun_pos=(0.75, 0.35), n_trees=2)
    cheetah_silhouette(draw, W * 0.5, hz + 60, 2.0, pal["silhouette"], running=False, facing=1, panting=True)
    save(img, "exhausted_cheetah")


def scene_lion_steal_kill():
    img, draw, pal, hz = base_scene("sunset", horizon_frac=0.64, sun_pos=(0.68, 0.32), n_trees=3)
    big_cat_body(draw, W * 0.36, hz + 30, 1.5, pal["silhouette"], mane=True)
    antelope_body(draw, W * 0.62, hz + 70, 1.1, tuple(max(0, c - 4) for c in pal["silhouette"]))
    save(img, "lion_steal_kill")


def scene_dappled_light():
    img, draw, pal, hz = base_scene("mysterious", horizon_frac=0.58, sun_pos=(0.5, 0.2), sun_r=50, n_trees=6)
    # dappled light spots overlay
    rng = random.Random(9)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    for _ in range(160):
        x, y = rng.uniform(0, W), rng.uniform(0, hz)
        r = rng.uniform(10, 40)
        odraw.ellipse([x - r, y - r, x + r, y + r], fill=(255, 240, 200, 26))
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"), (0, 0))
    save(img, "dappled_light")


def scene_oryx_camouflage():
    img, draw, pal, hz = base_scene("dawn", horizon_frac=0.62, n_trees=2)
    antelope_body(draw, W * 0.5, hz + 30, 1.8, pal["silhouette"], horns=True)
    antelope_body(draw, W * 0.68, hz + 44, 1.3, tuple(max(0, c - 6) for c in pal["silhouette"]), horns=True)
    save(img, "oryx_camouflage")


def scene_leopard_spots():
    img, draw, pal, hz = base_scene("mysterious", horizon_frac=0.6, sun_pos=(0.2, 0.22), n_trees=5)
    leopard_texture(draw, W * 0.55, hz + 20, 1.7, (120, 78, 40), (30, 18, 10))
    save(img, "leopard_spots")


def scene_lion_grass_stalk():
    img, draw, pal, hz = base_scene("tense", horizon_frac=0.6, sun_pos=(0.3, 0.28), n_trees=3)
    big_cat_body(draw, W * 0.5, hz + 60, 1.7, pal["silhouette"], crouch=True, mane=False)
    save(img, "lion_grass_stalk")


def scene_ground_nest_eggs():
    img, draw, pal, hz = base_scene("dawn", horizon_frac=0.55, n_trees=1)
    # close-up ground with speckled eggs
    draw.rectangle([0, hz - 40, W, H], fill=pal["ground"])
    rng = random.Random(4)
    for _ in range(400):
        x, y = rng.uniform(0, W), rng.uniform(hz - 40, H)
        r = rng.uniform(1, 3)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=tuple(max(0, c - 20) for c in pal["ground"]))
    for i, ex in enumerate([W * 0.42, W * 0.5, W * 0.58]):
        ey = H * 0.72
        draw.ellipse([ex - 34, ey - 26, ex + 34, ey + 26], fill=(196, 176, 130))
        for _ in range(14):
            sx = ex + rng.uniform(-28, 28)
            sy = ey + rng.uniform(-20, 20)
            draw.ellipse([sx - 2, sy - 2, sx + 2, sy + 2], fill=(110, 80, 50))
    save(img, "ground_nest_eggs")


def scene_lion_pride_hunt():
    img, draw, pal, hz = base_scene("heroic", horizon_frac=0.62, sun_pos=(0.7, 0.32), n_trees=3)
    big_cat_body(draw, W * 0.30, hz + 40, 1.3, pal["silhouette"], crouch=True)
    big_cat_body(draw, W * 0.48, hz + 55, 1.4, pal["silhouette"], crouch=True)
    big_cat_body(draw, W * 0.66, hz + 35, 1.2, pal["silhouette"], crouch=True)
    save(img, "lion_pride_hunt")


def scene_elephant_matriarch():
    img, draw, pal, hz = base_scene("heroic", horizon_frac=0.6, sun_pos=(0.72, 0.3), n_trees=3)
    elephant_body(draw, W * 0.48, hz + 60, 1.5, pal["silhouette"])
    elephant_body(draw, W * 0.72, hz + 80, 1.0, tuple(max(0, c - 4) for c in pal["silhouette"]), calf=True)
    save(img, "elephant_matriarch")


def scene_elephant_herd():
    img, draw, pal, hz = base_scene("heroic", horizon_frac=0.6, sun_pos=(0.25, 0.28), n_trees=4)
    elephant_body(draw, W * 0.28, hz + 60, 1.2, pal["silhouette"])
    elephant_body(draw, W * 0.5, hz + 70, 1.35, tuple(max(0, c - 2) for c in pal["silhouette"]))
    elephant_body(draw, W * 0.74, hz + 55, 1.1, pal["silhouette"], calf=True)
    save(img, "elephant_herd")


def scene_zebra_herd_stripes():
    img, draw, pal, hz = base_scene("heroic", horizon_frac=0.62, sun_pos=(0.5, 0.3), n_trees=2)
    zebra_body(draw, W * 0.30, hz + 40, 1.2, (250, 246, 236), (30, 26, 24))
    zebra_body(draw, W * 0.48, hz + 55, 1.35, (250, 246, 236), (30, 26, 24))
    zebra_body(draw, W * 0.68, hz + 42, 1.15, (250, 246, 236), (30, 26, 24))
    save(img, "zebra_herd_stripes")


def scene_mixed_herd_grazing():
    img, draw, pal, hz = base_scene("uplifting", horizon_frac=0.62, sun_pos=(0.5, 0.24), n_trees=4)
    zebra_body(draw, W * 0.30, hz + 45, 1.1, (250, 246, 236), (30, 26, 24))
    antelope_body(draw, W * 0.55, hz + 40, 1.4, pal["silhouette"])
    antelope_body(draw, W * 0.68, hz + 50, 1.1, tuple(max(0, c - 6) for c in pal["silhouette"]))
    save(img, "mixed_herd_grazing")


def scene_meerkat_sentinel():
    img, draw, pal, hz = base_scene("dawn", horizon_frac=0.66, n_trees=1)
    meerkat_body(draw, W * 0.5, hz + 70, 2.3, pal["silhouette"], sentinel=True)
    meerkat_body(draw, W * 0.42, hz + 78, 1.3, tuple(max(0, c - 6) for c in pal["silhouette"]))
    meerkat_body(draw, W * 0.60, hz + 80, 1.1, tuple(max(0, c - 6) for c in pal["silhouette"]))
    save(img, "meerkat_sentinel")


def scene_wild_dog_pack():
    img, draw, pal, hz = base_scene("heroic", horizon_frac=0.64, sun_pos=(0.72, 0.32), n_trees=2)
    for i, (fx, fs) in enumerate([(0.30, 1.1), (0.45, 1.3), (0.60, 1.0), (0.72, 1.15)]):
        wild_dog_body(draw, W * fx, hz + 30 + i * 6, fs, pal["silhouette"])
    save(img, "wild_dog_pack")


def scene_sunrise_finale():
    img, draw, pal, hz = base_scene("uplifting", horizon_frac=0.6, sun_pos=(0.5, 0.34), sun_r=110, n_trees=4)
    antelope_body(draw, W * 0.3, hz + 40, 1.0, pal["silhouette"])
    zebra_body(draw, W * 0.62, hz + 44, 1.1, (255, 250, 240), (40, 34, 30))
    save(img, "sunrise_finale")


def scene_title_card():
    img, draw, pal, hz = base_scene("night", horizon_frac=0.72, n_trees=3, stars=True)
    cheetah_silhouette(draw, W * 0.5, hz + 10, 1.3, (4, 4, 6), running=True, facing=1, spots=False)
    save(img, "title_card")


def scene_intro_bumper():
    pal = PALETTES["night"]
    img = vertical_gradient(W, H, (10, 12, 18), (28, 32, 40))
    draw = ImageDraw.Draw(img)
    rng = random.Random(2)
    for _ in range(200):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        r = rng.uniform(0.5, 1.6)
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(220, 220, 230))
    save(img, "intro_bumper")


def scene_cta_card():
    img, draw, pal, hz = base_scene("uplifting", horizon_frac=0.68, sun_pos=(0.5, 0.3), sun_r=100, n_trees=5)
    zebra_body(draw, W * 0.28, hz + 40, 1.0, (255, 250, 240), (40, 34, 30))
    antelope_body(draw, W * 0.7, hz + 40, 1.0, pal["silhouette"])
    save(img, "cta_card")


def main():
    scene_dawn_savanna_wide()
    scene_sunset_acacia()
    scene_cheetah_run_side()
    scene_cheetah_face()
    scene_motion_streak()
    scene_exhausted_cheetah()
    scene_lion_steal_kill()
    scene_dappled_light()
    scene_oryx_camouflage()
    scene_leopard_spots()
    scene_lion_grass_stalk()
    scene_ground_nest_eggs()
    scene_lion_pride_hunt()
    scene_elephant_matriarch()
    scene_elephant_herd()
    scene_zebra_herd_stripes()
    scene_mixed_herd_grazing()
    scene_meerkat_sentinel()
    scene_wild_dog_pack()
    scene_sunrise_finale()
    scene_title_card()
    scene_intro_bumper()
    scene_cta_card()
    print("All scenes generated.")


if __name__ == "__main__":
    main()
