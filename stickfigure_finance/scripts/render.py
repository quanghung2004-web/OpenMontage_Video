"""Render timeline.json into video segments in the stickfigure-finance-explainer style.

Everything is drawn procedurally with cairo: hand-drawn ink stick figures with
line boil, props, charts and burned captions. Each scene renders to its own
silent H.264 segment (in parallel); scripts/assemble.py joins them with audio.
"""
import json, math, os, subprocess, sys, hashlib
from multiprocessing import Pool
from pathlib import Path
import cairo

ROOT = Path(__file__).resolve().parents[1]
W, H = 1920, 1080
FPS = 24
GROUND = 800
INK = (0.12, 0.12, 0.12)
PAPER = (0.984, 0.969, 0.933)
HAND, MARKER = "Patrick Hand", "Permanent Marker"
BOIL_FPS = 8
CAP_TOP = 925


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


GREEN, RED, BLUE, YEL, PURP = map(hexc, ["#2E9E5B", "#E0483E", "#2F6FD6", "#F2A93B", "#7A52C7"])
HILITE = hexc("#FFE680")


# ---------------------------------------------------------------- utilities
def noise(*k):
    h = hashlib.md5(repr(k).encode()).digest()
    return (h[0] / 255.0) * 2 - 1, (h[1] / 255.0) * 2 - 1


class Ctx:
    """Drawing state: cairo context + current time + boil step."""

    def __init__(self, cr, t, dur):
        self.cr, self.t, self.dur = cr, t, dur
        self.boil = int(t * BOIL_FPS)


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(p):
    p = clamp(p)
    return 1 - (1 - p) ** 3


def pop(p):
    """Spring pop 0 -> 1.12 -> 1."""
    p = clamp(p)
    if p >= 1:
        return 1.0
    return 1 - math.exp(-6 * p) * math.cos(9 * p) if p > 0 else 0.0


def wob(c, pts, amp=1.6, key=0):
    out = []
    for i, (x, y) in enumerate(pts):
        nx, ny = noise(key, c.boil, i, round(x / 7), round(y / 7))
        out.append((x + nx * amp, y + ny * amp))
    return out


def stroke_path(c, pts, width=6, color=INK, close=False, amp=1.6, key=0, fill=None):
    cr = c.cr
    p = wob(c, pts, amp, key)
    cr.new_path()
    cr.move_to(*p[0])
    if len(p) > 2 and not close:
        for i in range(1, len(p) - 1):
            mx, my = (p[i][0] + p[i + 1][0]) / 2, (p[i][1] + p[i + 1][1]) / 2
            cr.curve_to(p[i][0], p[i][1], p[i][0], p[i][1], mx, my)
        cr.line_to(*p[-1])
    else:
        for q in p[1:]:
            cr.line_to(*q)
    if close:
        cr.close_path()
    if fill is not None:
        cr.set_source_rgba(*fill) if len(fill) == 4 else cr.set_source_rgb(*fill)
        cr.fill_preserve()
    cr.set_source_rgb(*color)
    cr.set_line_width(width)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.set_line_join(cairo.LINE_JOIN_ROUND)
    cr.stroke()


def line(c, x1, y1, x2, y2, width=6, color=INK, key=0):
    n = max(2, int(math.hypot(x2 - x1, y2 - y1) / 40) + 1)
    pts = [(x1 + (x2 - x1) * i / (n - 1), y1 + (y2 - y1) * i / (n - 1)) for i in range(n)]
    stroke_path(c, pts, width, color, key=key)


def circle(c, x, y, r, width=6, color=INK, fill=None, key=0):
    n = max(14, int(r / 3))
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        nx, _ = noise("c", key, c.boil, i)
        rr = r + nx * min(2.0, r * 0.05)
        pts.append((x + rr * math.cos(a), y + rr * math.sin(a)))
    stroke_path(c, pts, width, color, close=True, amp=0.6, key=key, fill=fill)


def rect(c, x, y, w, h, width=6, color=INK, fill=None, key=0):
    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    stroke_path(c, pts, width, color, close=True, amp=1.4, key=key, fill=fill)


def rrect_path(cr, x, y, w, h, r):
    cr.new_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def font(c, size, face=HAND):
    c.cr.select_font_face(face, cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    c.cr.set_font_size(size)


def text(c, s, x, y, size=48, face=HAND, color=INK, align="center", alpha=1.0):
    cr = c.cr
    font(c, size, face)
    ext = cr.text_extents(s)
    if align == "center":
        tx = x - ext.width / 2 - ext.x_bearing
    elif align == "right":
        tx = x - ext.width - ext.x_bearing
    else:
        tx = x
    cr.move_to(tx, y)
    cr.set_source_rgba(*color, alpha)
    cr.show_text(s)
    return ext


def text_w(c, s, size, face=HAND):
    font(c, size, face)
    return c.cr.text_extents(s).x_advance


def wrap(c, s, size, maxw, face=HAND):
    words, lines, cur = s.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_w(c, trial, size, face) <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def fit_text(c, s, x, y, size, maxw, face=HAND, color=INK, max_lines=3, lh=1.15):
    while True:
        lines = wrap(c, s, size, maxw, face)
        if len(lines) <= max_lines or size < 24:
            break
        size *= 0.9
    for i, ln in enumerate(lines):
        text(c, ln, x, y + i * size * lh, size, face, color)
    return len(lines) * size * lh


def money(v, decimals=0):
    if decimals:
        return f"${v:,.{decimals}f}"
    return f"${v:,.0f}"


# ---------------------------------------------------------------- stick figure
def limb(ox, oy, a1, a2, l1, l2, face):
    ex, ey = ox + math.sin(a1) * l1 * face, oy + math.cos(a1) * l1
    hx, hy = ex + math.sin(a2) * l2 * face, ey + math.cos(a2) * l2
    return [(ox, oy), (ex, ey), (hx, hy)]


def pose(act, t, x_seed):
    """Return dict with arm/leg angles (front F, back B), lean, bob."""
    s = math.sin
    ph = x_seed * 3.1
    P = dict(F=(0.22 + 0.04 * s(1.7 * t + ph), 0.12), B=(-0.22 - 0.04 * s(1.7 * t + ph), -0.12),
             LF=(0.17, 0.17), LB=(-0.17, -0.17), lean=0.0, bob=4 * s(2.2 * t + ph), jit=0)
    if act == "wave":
        P["F"] = (1.95, 2.75 + 0.4 * s(7 * t))
    elif act == "cheer":
        j = abs(s(4.2 * t + ph))
        P.update(F=(2.25, 2.6), B=(-2.25, -2.6), bob=-28 * j, LF=(0.3 - 0.2 * j, 0.1), LB=(-0.3 + 0.2 * j, -0.1))
    elif act == "point":
        P["F"] = (1.45 + 0.05 * s(3 * t), 1.55 + 0.05 * s(3 * t))
    elif act == "shrug":
        k = 0.5 + 0.5 * s(3 * t)
        P.update(F=(0.75 + 0.15 * k, 2.2 + 0.2 * k), B=(-0.75 - 0.15 * k, -2.2 - 0.2 * k), bob=-6 * k)
    elif act == "shock":
        P.update(F=(2.0, 2.55), B=(-2.0, -2.55), jit=3)
    elif act == "think":
        P["F"] = (0.55, 2.75 + 0.06 * s(2 * t))
    elif act == "sweat":
        P.update(F=(0.12, 0.05), B=(-0.12, -0.05), lean=0.05, bob=2 * s(1.2 * t))
    elif act in ("run", "walk"):
        sp = 11 if act == "run" else 5.5
        a = (0.9 if act == "run" else 0.45) * s(sp * t)
        P.update(F=(a, a + (1.3 if act == "run" else 0.3)), B=(-a, -a + (1.3 if act == "run" else 0.3)),
                 LF=(a * 0.9, a * 0.9 - (0.6 * max(0, s(sp * t + 1.6)) if act == "run" else 0.15)),
                 LB=(-a * 0.9, -a * 0.9 - (0.6 * max(0, -s(sp * t + 1.6)) if act == "run" else 0.15)),
                 lean=0.15 if act == "run" else 0.04, bob=-8 * abs(s(sp * t)))
    elif act == "push":
        k = s(2.5 * t)
        P.update(F=(1.35 + 0.1 * k, 1.45 + 0.1 * k), B=(1.2 + 0.1 * k, 1.3 + 0.1 * k), lean=0.3,
                 LF=(0.35, 0.3), LB=(-0.4 + 0.1 * k, -0.5))
    return P


def face_draw(c, hx, hy, r, mood, face, t, key):
    cr = c.cr
    ex = hx + face * r * 0.28
    blink = (t % 3.7) < 0.12
    for dx in (-r * 0.28, r * 0.12):
        x = ex + dx
        if mood == "shocked":
            circle(c, x, hy - r * 0.12, 6, 3.5, key=key + 7)
        elif blink:
            line(c, x - 5, hy - r * 0.1, x + 5, hy - r * 0.1, 3.5, key=key + 8)
        else:
            cr.new_path(); cr.arc(x, hy - r * 0.1, 5.5, 0, 2 * math.pi); cr.set_source_rgb(*INK); cr.fill()
    my = hy + r * 0.38
    mx = ex - r * 0.08
    if mood == "happy":
        stroke_path(c, [(mx - 17, my - 6), (mx, my + 8), (mx + 17, my - 6)], 4, key=key + 9)
    elif mood == "sad":
        stroke_path(c, [(mx - 15, my + 7), (mx, my - 4), (mx + 15, my + 7)], 4, key=key + 9)
        line(c, ex - r * 0.42, hy - r * 0.42, ex - r * 0.16, hy - r * 0.32, 3, key=key + 10)
        line(c, ex + r * 0.26, hy - r * 0.32, ex + r * 0.0, hy - r * 0.42, 3, key=key + 11)
    elif mood == "shocked":
        circle(c, mx, my + 2, 10, 4, key=key + 9)
    elif mood == "confused":
        stroke_path(c, [(mx - 15, my), (mx - 5, my - 6), (mx + 5, my + 4), (mx + 15, my - 3)], 4, key=key + 9)
        line(c, ex + r * 0.0, hy - r * 0.48, ex + r * 0.3, hy - r * 0.38, 3, key=key + 10)
    elif mood == "thinking":
        stroke_path(c, [(mx - 8, my + 2), (mx + 14, my - 4)], 4, key=key + 9)
    else:
        line(c, mx - 13, my + 1, mx + 13, my + 1, 4, key=key + 9)


def bubble(c, x, y, s, size=46):
    cr = c.cr
    w = text_w(c, s, size) + 60
    h = size + 40
    bx, by = x - w / 2, y - h
    rrect_path(cr, bx, by, w, h, 24)
    cr.set_source_rgb(1, 1, 1); cr.fill_preserve()
    cr.set_source_rgb(*INK); cr.set_line_width(4.5); cr.stroke()
    cr.new_path(); cr.move_to(x - 14, by + h - 2); cr.line_to(x - 4, by + h + 26); cr.line_to(x + 12, by + h - 2)
    cr.close_path(); cr.set_source_rgb(1, 1, 1); cr.fill_preserve(); cr.set_source_rgb(*INK); cr.stroke()
    cr.new_path(); cr.rectangle(x - 12, by + h - 6, 22, 7); cr.set_source_rgb(1, 1, 1); cr.fill()
    text(c, s, x, by + h / 2 + size * 0.33, size)


def figure(c, f, sc=1.0, ground=GROUND, appear=0.0):
    t = c.t
    who, mood, act = f.get("who", "sam"), f.get("mood", "neutral"), f.get("act", "idle")
    x = f["x"] * W if f["x"] <= 1 else f["x"]
    face = f.get("face") or (1 if x < W / 2 + 1 else -1)
    if act in ("point", "push") and f.get("face") is None:
        face = 1 if x < W * 0.62 else -1
    k = pop((t - appear) / 0.45)
    if k <= 0:
        return
    key = hash(who) % 997
    cr = c.cr
    cr.save()
    cr.translate(x, ground)
    cr.scale(max(sc * k, 1e-3), max(sc * k, 1e-3))
    cr.translate(-x, -ground)
    P = pose(act, t, f["x"])
    jx = noise("j", c.boil * 3, key)[0] * P["jit"] if P["jit"] else 0
    age = f.get("age", 0)
    ground0 = ground
    if f.get("on") == "treadmill":
        tg = ground
        stroke_path(c, [(x - 190, tg - 40), (x + 190, tg - 40)], 7, key=1)
        stroke_path(c, [(x - 190, tg - 18), (x + 190, tg - 18)], 5, key=2)
        for i in range(9):
            ox = x - 180 + ((i * 45 - t * 260) % 400)
            line(c, ox, tg - 36, ox - 8, tg - 22, 3, key=3 + i)
        line(c, x + 190, tg - 40, x + 220, tg - 190, 7, key=12)
        line(c, x + 220, tg - 190, x + 150, tg - 205, 7, key=13)
        line(c, x - 170, tg - 18, x - 180, tg, 6, key=14)
        line(c, x + 170, tg - 18, x + 180, tg, 6, key=15)
        ground = tg - 40
    leg, thigh = 70, 68
    hipy = ground - leg - thigh + P["bob"] * 0.3
    hip = (x + jx, hipy + min(0, P["bob"]))
    body = 135
    lean = P["lean"] + (0.12 if age else 0)
    neck = (hip[0] + math.sin(lean) * body * face, hip[1] - math.cos(lean) * body)
    hr = 44
    head = (neck[0] + math.sin(lean) * (hr + 6) * face, neck[1] - hr - 4)
    lw = 7
    # legs
    for key2, (a1, a2) in (("LB", P["LB"]), ("LF", P["LF"])):
        pts = limb(hip[0], hip[1], a1, a2, thigh, leg, face)
        stroke_path(c, pts, lw, key=key + (1 if key2 == "LF" else 2))
        fx, fy = pts[-1]
        line(c, fx, fy, fx + 16 * face, fy + 1, lw, key=key + 30 + len(key2))
    # chain
    if f.get("chain"):
        ax, ay = limb(hip[0], hip[1], *P["LB"], thigh, leg, face)[-1]
        bx, by = ax - 170 * face, ground - 48
        for i in range(6):
            q = i / 5
            circle(c, ax + (bx - ax) * q, ay + (by - ay) * q + 10 * math.sin(q * math.pi), 9, 3.5, key=50 + i)
        circle(c, bx - 20 * face, ground - 50, 50, 6, fill=INK, key=60)
        text(c, "DEBT", bx - 20 * face, ground - 40, 30, MARKER, color=(1, 1, 1))
    # body
    stroke_path(c, [hip, ((hip[0] + neck[0]) / 2 + (6 * face if age else 0), (hip[1] + neck[1]) / 2), neck], lw, key=key + 3)
    # arms
    sh = (neck[0] + (hip[0] - neck[0]) * 0.12, neck[1] + (hip[1] - neck[1]) * 0.12)
    armB = limb(sh[0], sh[1], *P["B"], 62, 62, face)
    armF = limb(sh[0], sh[1], *P["F"], 62, 62, face)
    stroke_path(c, armB, lw, key=key + 4)
    # head
    circle(c, head[0], head[1], hr, lw, fill=(1, 1, 1), key=key + 5)
    if who == "alex":
        cr.new_path()
        cr.arc(head[0], head[1] - 4, hr + 2, math.pi * 1.05, math.pi * 1.95)
        cr.close_path()
        cr.set_source_rgb(*GREEN); cr.fill_preserve(); cr.set_source_rgb(*INK); cr.set_line_width(5); cr.stroke()
        line(c, head[0] + face * 10, head[1] - hr * 0.35, head[0] + face * (hr + 34), head[1] - hr * 0.3, 8, GREEN, key=key + 6)
    elif who == "sam":
        for i in range(3):
            a = -math.pi / 2 + (i - 1) * 0.35
            bx, by = head[0] + math.cos(a) * hr, head[1] + math.sin(a) * hr
            line(c, bx, by, bx + math.cos(a - 0.4) * 22, by + math.sin(a - 0.4) * 22, 5, key=key + 20 + i)
    if age:
        for i in range(2):
            line(c, head[0] - 22 + i * 30, head[1] - hr * 0.62, head[0] - 6 + i * 30, head[1] - hr * 0.66, 3, key=key + 40 + i)
    face_draw(c, head[0], head[1], hr, mood, face, t, key)
    stroke_path(c, armF, lw, key=key + 7)
    hx, hy = armF[-1]
    hold = f.get("hold")
    if hold:
        prop(c, hold, hx + 16 * face, hy + 4, 0.42, small=True)
    # effects
    if act == "sweat" or (mood == "sad" and act == "walk"):
        for i in range(2):
            ph = (t * 0.9 + i * 0.5) % 1
            dx = head[0] - face * (hr + 12 + i * 14)
            dy = head[1] - 10 + ph * 70
            cr.new_path(); cr.move_to(dx, dy - 12); cr.curve_to(dx + 9, dy, dx + 7, dy + 10, dx, dy + 10)
            cr.curve_to(dx - 7, dy + 10, dx - 9, dy, dx, dy - 12)
            cr.set_source_rgba(*BLUE, 1 - ph); cr.fill()
    if act == "shock":
        for i, a in enumerate((-2.3, -1.57, -0.84)):
            r1, r2 = hr + 14, hr + 38
            line(c, head[0] + math.cos(a) * r1, head[1] + math.sin(a) * r1,
                 head[0] + math.cos(a) * r2, head[1] + math.sin(a) * r2, 5, RED, key=key + 70 + i)
    if act == "think":
        for i in range(3):
            if (t * 2) % 4 > i:
                circle(c, head[0] + face * (hr + 18 + i * 22), head[1] - hr - 10 - i * 22, 6 + i * 4, 3.5, key=key + 80 + i)
    cr.restore()
    if f.get("name", True):
        name = {"sam": "Sam", "alex": "Alex"}.get(who)
        if name:
            text(c, name, x, ground0 + 52, 40, HAND, color=(0.35, 0.33, 0.3), alpha=clamp(k))
    if f.get("say") and t - appear > 0.6:
        bubble(c, head[0] + face * 70, head[1] - hr - 30, f["say"])


# ---------------------------------------------------------------- props
def coin(c, x, y, r=26, key=0, fill=YEL):
    circle(c, x, y, r, 4.5, fill=fill, key=key)
    text(c, "$", x, y + r * 0.42, r * 1.25, MARKER)


def cash(c, x, y, s, key=0):
    w, h = 170 * s, 86 * s
    rect(c, x - w / 2, y - h / 2, w, h, 5, fill=(0.80, 0.93, 0.83), key=key)
    rect(c, x - w / 2 + 10 * s, y - h / 2 + 10 * s, w - 20 * s, h - 20 * s, 2.5, color=GREEN, key=key + 1)
    circle(c, x, y, 24 * s, 3.5, color=GREEN, key=key + 2)
    text(c, "$", x, y + 12 * s, 38 * s, MARKER, GREEN)


def prop(c, kind, x, y, s=1.0, small=False, opts=None):
    o = opts or {}
    cr = c.cr
    t = c.t
    k = hash(kind) % 500
    if kind == "coin":
        coin(c, x, y, 40 * s, k)
    elif kind == "cash":
        cash(c, x, y, s, k)
    elif kind == "money_bag":
        r = 70 * s
        circle(c, x, y + 20 * s, r, 6, fill=(0.80, 0.93, 0.83), key=k)
        stroke_path(c, [(x - 28 * s, y - 45 * s), (x - 40 * s, y - 80 * s), (x + 40 * s, y - 80 * s), (x + 28 * s, y - 45 * s)], 6, key=k + 1, fill=(0.80, 0.93, 0.83))
        line(c, x - 34 * s, y - 50 * s, x + 34 * s, y - 50 * s, 6, key=k + 2)
        text(c, "$", x, y + 50 * s, 80 * s, MARKER, GREEN)
    elif kind == "card":
        col = hexc(o["color"]) if isinstance(o.get("color"), str) else (o.get("color") or BLUE)
        w, h = 190 * s, 120 * s
        rrect_path(cr, x - w / 2, y - h / 2, w, h, 14 * s)
        cr.set_source_rgb(*col); cr.fill_preserve(); cr.set_source_rgb(*INK); cr.set_line_width(5); cr.stroke()
        cr.new_path(); cr.rectangle(x - w / 2, y - h / 2 + 22 * s, w, 22 * s); cr.set_source_rgb(*INK); cr.fill()
        rect(c, x - w / 2 + 18 * s, y + 8 * s, 36 * s, 28 * s, 3, fill=YEL, key=k)
    elif kind == "phone":
        w, h = 80 * s, 150 * s
        rrect_path(cr, x - w / 2, y - h / 2, w, h, 14 * s)
        cr.set_source_rgb(*INK); cr.fill()
        rrect_path(cr, x - w / 2 + 7 * s, y - h / 2 + 14 * s, w - 14 * s, h - 32 * s, 6 * s)
        cr.set_source_rgb(0.75, 0.88, 1.0); cr.fill()
        if not small:
            for i in range(3):
                line(c, x - 22 * s, y - 40 * s + i * 22 * s, x + (22 - i * 8) * s, y - 40 * s + i * 22 * s, 4, key=k + i)
    elif kind == "coffee":
        stroke_path(c, [(x - 40 * s, y - 50 * s), (x - 30 * s, y + 50 * s), (x + 30 * s, y + 50 * s), (x + 40 * s, y - 50 * s)], 5, close=True, fill=(0.93, 0.85, 0.74), key=k)
        rect(c, x - 46 * s, y - 64 * s, 92 * s, 16 * s, 5, fill=(1, 1, 1), key=k + 1)
        for i in range(2):
            ph = (t * 0.7 + i * 0.5) % 1
            stroke_path(c, [(x - 10 * s + i * 20 * s, y - 75 * s - ph * 40 * s), (x - 18 * s + i * 20 * s, y - 95 * s - ph * 40 * s), (x - 8 * s + i * 20 * s, y - 115 * s - ph * 40 * s)], 3, color=(0.6, 0.6, 0.6), key=k + 3 + i)
    elif kind == "car":
        bw, bh = 300 * s, 70 * s
        col = (0.85, 0.85, 0.85) if o.get("broken") else (0.98, 0.78, 0.45)
        stroke_path(c, [(x - bw / 2, y), (x - bw / 2, y - bh), (x - bw * 0.28, y - bh), (x - bw * 0.15, y - bh * 1.9), (x + bw * 0.22, y - bh * 1.9), (x + bw * 0.33, y - bh), (x + bw / 2, y - bh * 0.9), (x + bw / 2, y)], 6, close=True, fill=col, key=k)
        rect(c, x - bw * 0.12, y - bh * 1.75, bw * 0.15, bh * 0.65, 4, fill=(0.8, 0.92, 1), key=k + 1)
        rect(c, x + bw * 0.07, y - bh * 1.75, bw * 0.15, bh * 0.65, 4, fill=(0.8, 0.92, 1), key=k + 2)
        ang = 0 if o.get("broken") else t * 0.0
        for wx in (-bw * 0.3, bw * 0.3):
            circle(c, x + wx, y, 36 * s, 6, fill=(0.25, 0.25, 0.25), key=k + 3)
            circle(c, x + wx, y, 12 * s, 3, fill=(0.9, 0.9, 0.9), key=k + 4)
        if o.get("broken"):
            for i in range(3):
                ph = (t * 0.6 + i / 3) % 1
                circle(c, x + bw * 0.42 + ph * 40 * s, y - bh * 1.1 - ph * 120 * s, (14 + ph * 26) * s, 3, color=(0.55, 0.55, 0.55), fill=(0.85, 0.85, 0.85, 1 - ph), key=k + 5 + i)
    elif kind == "house":
        w, h = 200 * s, 140 * s
        rect(c, x - w / 2, y - h / 2, w, h, 6, fill=(1, 0.95, 0.85), key=k)
        stroke_path(c, [(x - w / 2 - 20 * s, y - h / 2), (x, y - h / 2 - 100 * s), (x + w / 2 + 20 * s, y - h / 2)], 6, close=True, fill=(0.88, 0.45, 0.4), key=k + 1)
        rect(c, x - 25 * s, y + h / 2 - 75 * s, 50 * s, 75 * s, 5, fill=(0.6, 0.42, 0.3), key=k + 2)
        rect(c, x + 45 * s, y - 30 * s, 40 * s, 40 * s, 4, fill=(0.8, 0.92, 1), key=k + 3)
    elif kind == "bucket":
        w1, w2, h = 220 * s, 160 * s, 210 * s
        stroke_path(c, [(x - w1 / 2, y - h / 2), (x - w2 / 2, y + h / 2), (x + w2 / 2, y + h / 2), (x + w1 / 2, y - h / 2)], 6, fill=(0.8, 0.86, 0.9), key=k)
        cr.new_path(); cr.save(); cr.translate(x, y - h / 2); cr.scale(w1 / 2, 18 * s); cr.arc(0, 0, 1, 0, 2 * math.pi); cr.restore()
        cr.set_source_rgb(*INK); cr.set_line_width(5); cr.stroke()
        holes = [(-0.25, 0.25), (0.15, 0.1), (0.3, 0.32), (-0.05, 0.4), (-0.3, -0.05)]
        for i, (hx, hy) in enumerate(holes):
            px, py = x + hx * w1 * 0.8, y + hy * h
            cr.new_path(); cr.arc(px, py, 7 * s, 0, 2 * math.pi); cr.set_source_rgb(*INK); cr.fill()
            if o.get("leak"):
                for j in range(3):
                    ph = (t * 1.1 + j / 3 + i * 0.17) % 1
                    dx = px + (1 if hx > 0 else -1) * ph * 60 * s
                    dy = py + ph * ph * 230 * s
                    if dy > GROUND + 60: continue
                    coin(c, dx, dy, 12 * s, key=k + 10 + i * 3 + j)
    elif kind == "piggy":
        r = 90 * s
        cr.new_path(); cr.save(); cr.translate(x, y); cr.scale(1.25, 1); cr.arc(0, 0, r, 0, 2 * math.pi); cr.restore()
        cr.set_source_rgb(1.0, 0.75, 0.8); cr.fill_preserve(); cr.set_source_rgb(*INK); cr.set_line_width(6); cr.stroke()
        circle(c, x + r * 1.2, y + 5, 26 * s, 5, fill=(1.0, 0.68, 0.74), key=k)
        for dx in (-6, 6):
            cr.new_path(); cr.arc(x + r * 1.2 + dx * s, y + 5, 4 * s, 0, 2 * math.pi); cr.set_source_rgb(*INK); cr.fill()
        cr.new_path(); cr.arc(x + r * 0.6, y - r * 0.35, 6 * s, 0, 2 * math.pi); cr.fill()
        stroke_path(c, [(x + r * 0.55, y - r * 0.8), (x + r * 0.8, y - r * 1.15), (x + r * 0.95, y - r * 0.75)], 5, fill=(1.0, 0.68, 0.74), key=k + 1)
        for lx in (-0.7, -0.3, 0.3, 0.7):
            line(c, x + lx * r, y + r * 0.85, x + lx * r, y + r * 1.25, 9, key=k + 2)
        line(c, x - 25 * s, y - r * 0.98, x + 25 * s, y - r * 0.98, 7, key=k + 3)
        stroke_path(c, [(x - r * 1.25, y), (x - r * 1.45, y - 20 * s), (x - r * 1.35, y - 35 * s)], 4, key=k + 4)
    elif kind == "shield":
        h = 220 * s
        stroke_path(c, [(x, y - h / 2), (x + 95 * s, y - h / 2 + 30 * s), (x + 85 * s, y + 20 * s), (x, y + h / 2), (x - 85 * s, y + 20 * s), (x - 95 * s, y - h / 2 + 30 * s)], 7, close=True, fill=(0.75, 0.86, 1.0), key=k)
        coin(c, x, y - 5 * s, 42 * s, k + 1)
    elif kind == "tree":
        g = ease_out((t - o.get("appear", 0)) / 6.0) if o.get("grow") else 1
        g = 0.35 + 0.65 * g
        th = 170 * s * g
        stroke_path(c, [(x - 16 * s, y + 90 * s), (x - 10 * s, y + 90 * s - th), (x + 10 * s, y + 90 * s - th), (x + 16 * s, y + 90 * s)], 6, close=True, fill=(0.65, 0.45, 0.3), key=k)
        cy = y + 90 * s - th - 60 * s * g
        for i, (dx, dy, rr) in enumerate([(0, -30, 85), (-70, 10, 65), (70, 10, 65), (0, 40, 70)]):
            circle(c, x + dx * s * g, cy + dy * s * g, rr * s * g, 6, fill=(0.62, 0.84, 0.55), key=k + 1 + i)
        for i, (dx, dy) in enumerate([(-40, -40), (35, -20), (-70, 30), (60, 40), (5, 30), (10, -80)]):
            if g > 0.5 + i * 0.08:
                coin(c, x + dx * s * g, cy + dy * s * g, 16 * s, key=k + 10 + i)
    elif kind == "snowball":
        g = ease_out((t - o.get("appear", 0)) / 10.0) if o.get("grow") else 1
        r = (40 + 110 * g) * s
        cxp = x + 140 * s * g
        circle(c, cxp, y + 110 * s - r, r, 6, fill=(1, 1, 1), key=k)
        for i in range(5):
            a = t * 2.0 + i * 1.25
            stroke_path(c, [(cxp + math.cos(a) * r * 0.5, y + 110 * s - r + math.sin(a) * r * 0.5), (cxp + math.cos(a + 0.4) * r * 0.75, y + 110 * s - r + math.sin(a + 0.4) * r * 0.75)], 3, color=(0.6, 0.7, 0.8), key=k + 1 + i)
        text(c, "$", cxp, y + 110 * s - r + r * 0.4, r * 1.1, MARKER, GREEN)
    elif kind == "calendar":
        w, h = 170 * s, 160 * s
        rect(c, x - w / 2, y - h / 2, w, h, 6, fill=(1, 1, 1), key=k)
        cr.new_path(); cr.rectangle(x - w / 2, y - h / 2, w, 40 * s); cr.set_source_rgb(*RED); cr.fill()
        for i in range(3):
            for j in range(4):
                cx_, cy_ = x - w / 2 + 28 * s + j * 38 * s, y - h / 2 + 68 * s + i * 32 * s
                cr.new_path(); cr.rectangle(cx_ - 9 * s, cy_ - 9 * s, 18 * s, 18 * s)
                cr.set_source_rgb(*(GREEN if (i * 4 + j) == int(t * 2) % 12 else (0.82, 0.82, 0.82))); cr.fill()
    elif kind == "arrow_up" or kind == "arrow_down":
        col = hexc(o["color"]) if isinstance(o.get("color"), str) else (GREEN if kind == "arrow_up" else RED)
        d = -1 if kind == "arrow_up" else 1
        bob = 8 * math.sin(t * 3)
        yy = y + bob * d
        stroke_path(c, [(x - 25 * s, yy - d * 60 * s), (x + 25 * s, yy - d * 60 * s), (x + 25 * s, yy + d * 10 * s), (x + 55 * s, yy + d * 10 * s), (x, yy + d * 75 * s), (x - 55 * s, yy + d * 10 * s), (x - 25 * s, yy + d * 10 * s)], 5, close=True, fill=col, key=k)
    elif kind == "burger":
        w = 170 * s
        cr.new_path(); cr.arc(x, y - 10 * s, w / 2, math.pi, 2 * math.pi); cr.close_path()
        cr.set_source_rgb(0.95, 0.72, 0.4); cr.fill_preserve(); cr.set_source_rgb(*INK); cr.set_line_width(5); cr.stroke()
        rect(c, x - w / 2 - 5 * s, y - 10 * s, w + 10 * s, 14 * s, 4, fill=(0.45, 0.75, 0.35), key=k)
        rect(c, x - w / 2, y + 4 * s, w, 26 * s, 5, fill=(0.5, 0.3, 0.2), key=k + 1)
        rect(c, x - w / 2, y + 30 * s, w, 24 * s, 5, fill=(0.95, 0.72, 0.4), key=k + 2)
    elif kind == "sofa":
        w = 300 * s
        rect(c, x - w / 2, y - 40 * s, w, 70 * s, 6, fill=(0.6, 0.65, 0.85), key=k)
        rect(c, x - w / 2 - 20 * s, y - 70 * s, 40 * s, 100 * s, 6, fill=(0.6, 0.65, 0.85), key=k + 1)
        rect(c, x + w / 2 - 20 * s, y - 70 * s, 40 * s, 100 * s, 6, fill=(0.6, 0.65, 0.85), key=k + 2)
        rect(c, x - w / 2 + 20 * s, y - 100 * s, w - 40 * s, 60 * s, 6, fill=(0.66, 0.7, 0.9), key=k + 3)
    elif kind == "basket":
        w, h = 300 * s, 150 * s
        logos = ["A", "B", "C", "D", "E", "F", "G", "H", "I"]
        for i, L in enumerate(logos):
            bx = x - w * 0.36 + (i % 5) * w * 0.18 + (i // 5) * w * 0.09
            by = y - h * 0.55 - (i // 5) * 50 * s + 4 * math.sin(t * 2 + i)
            col = [GREEN, BLUE, YEL, RED, PURP][i % 5]
            circle(c, bx, by, 30 * s, 4, fill=col, key=k + 20 + i)
            text(c, L, bx, by + 11 * s, 32 * s, MARKER, (1, 1, 1))
        stroke_path(c, [(x - w / 2, y - h / 2), (x - w / 2 + 25 * s, y + h / 2), (x + w / 2 - 25 * s, y + h / 2), (x + w / 2, y - h / 2)], 6, close=True, fill=(0.85, 0.65, 0.4), key=k)
        for i in range(1, 6):
            line(c, x - w / 2 + i * w / 6, y - h / 2, x - w / 2 + 12 * s + i * (w - 24 * s) / 6, y + h / 2, 3, key=k + 1 + i)
        line(c, x - w / 2 + 10 * s, y, x + w / 2 - 10 * s, y, 3, key=k + 9)
    elif kind == "clock":
        r = 100 * s
        circle(c, x, y, r, 7, fill=(1, 1, 1), key=k)
        for i in range(12):
            a = i * math.pi / 6
            line(c, x + math.cos(a) * r * 0.82, y + math.sin(a) * r * 0.82, x + math.cos(a) * r * 0.92, y + math.sin(a) * r * 0.92, 4, key=k + 1 + i)
        a = t * 2.4 - math.pi / 2
        line(c, x, y, x + math.cos(a) * r * 0.75, y + math.sin(a) * r * 0.75, 6, RED, key=k + 20)
        a2 = t * 0.2 - math.pi / 2
        line(c, x, y, x + math.cos(a2) * r * 0.5, y + math.sin(a2) * r * 0.5, 8, key=k + 21)
    elif kind == "building":
        w, h = 260 * s, 200 * s
        stroke_path(c, [(x - w / 2 - 15 * s, y - h / 2), (x, y - h / 2 - 70 * s), (x + w / 2 + 15 * s, y - h / 2)], 6, close=True, fill=(0.9, 0.9, 0.95), key=k)
        for i in range(5):
            cx_ = x - w / 2 + 20 * s + i * (w - 40 * s) / 4
            rect(c, cx_ - 10 * s, y - h / 2 + 10 * s, 20 * s, h - 40 * s, 4, fill=(1, 1, 1), key=k + 1 + i)
        rect(c, x - w / 2 - 15 * s, y + h / 2 - 30 * s, w + 30 * s, 30 * s, 5, fill=(0.9, 0.9, 0.95), key=k + 9)
        text(c, "$", x, y - h / 2 - 12 * s, 48 * s, MARKER, GREEN)
    elif kind == "briefcase":
        w, h = 110 * s, 80 * s
        rect(c, x - w / 2, y - h / 2 + 30 * s, w, h, 5, fill=(0.6, 0.42, 0.3), key=k)
        stroke_path(c, [(x - 20 * s, y - h / 2 + 30 * s), (x - 20 * s, y - h / 2 + 12 * s), (x + 20 * s, y - h / 2 + 12 * s), (x + 20 * s, y - h / 2 + 30 * s)], 5, key=k + 1)
    elif kind == "book":
        w, h = 100 * s, 130 * s
        rect(c, x - w / 2, y - h / 2, w, h, 5, fill=BLUE, key=k)
        line(c, x - w / 2 + 14 * s, y - h / 2, x - w / 2 + 14 * s, y + h / 2, 4, key=k + 1)
    else:
        circle(c, x, y, 50 * s, 5, key=k)


def draw_prop_item(c, p):
    x, y = p["x"] * W, p["y"] * H
    s = p.get("s", 1.0)
    ap = p.get("appear", 0.2)
    k = pop((c.t - ap) / 0.5)
    if k <= 0:
        return
    cr = c.cr
    cr.save(); cr.translate(x, y); cr.scale(max(k, 1e-3), max(k, 1e-3)); cr.translate(-x, -y)
    opts = dict(p); opts["appear"] = ap
    prop(c, p["kind"], x, y, s, opts=opts)
    cr.restore()
    if p.get("label"):
        ly = y + {"car": 90, "bucket": 160, "piggy": 160, "tree": 140, "house": 110, "snowball": 150,
                  "basket": 120, "shield": 150, "building": 140, "sofa": 70, "clock": 145}.get(p["kind"], 115) * s
        if p["kind"] == "cash" and p.get("label"):
            ly = y + 90 * s
        size = 40
        w = text_w(c, p["label"], size) + 30
        if k > 0.6:
            cr.new_path(); cr.rectangle(x - w / 2, ly - size * 0.85, w, size * 1.15)
            cr.set_source_rgba(*HILITE, 0.85); cr.fill()
            text(c, p["label"], x, ly, size)


# ---------------------------------------------------------------- effects
def fx_draw(c, kind):
    t = c.t
    if kind == "coins_rain":
        for i in range(26):
            sx = (noise("cr", i)[0] * 0.5 + 0.5) * W
            sp = 260 + 160 * (noise("cs", i)[1] * 0.5 + 0.5)
            y = ((t * sp + i * 137) % (CAP_TOP + 100)) - 60
            coin(c, sx, y, 22, key=900 + i)
    elif kind == "pour":
        x0 = 0.62 * W
        for i in range(10):
            ph = (t * 0.9 + i / 10) % 1
            coin(c, x0 + noise("p", i)[0] * 60, 210 + ph * 240, 18, key=950 + i)
    elif kind == "coin_drop":
        x0, y0 = 0.68 * W, 0.6 * H - 90
        for i in range(3):
            ph = (t * 0.6 + i / 3) % 1
            coin(c, x0, 160 + ph * (y0 - 160), 24, key=970 + i)


# ---------------------------------------------------------------- scene types
def headline(c, s, y=125, size=74):
    if not s:
        return
    k = ease_out(c.t / 0.5)
    fit_text(c, s, W / 2, y - (1 - k) * 30, size, W - 260, MARKER, max_lines=1)


def scene_stage(c, v):
    headline(c, v.get("head"))
    fx = v.get("fx")
    if fx in ("pour",):
        fx_draw(c, fx)
    for p in v.get("props", []):
        draw_prop_item(c, p)
    ground_line(c)
    for i, f in enumerate(v.get("figs", [])):
        figure(c, f, sc=f.get("scale", 1.0), appear=0.05 + 0.15 * i)
    if fx in ("coins_rain", "coin_drop"):
        fx_draw(c, fx)


def ground_line(c):
    stroke_path(c, [(110, GROUND + 4), (W / 2, GROUND + 2), (W - 110, GROUND + 5)], 4, color=(0.55, 0.52, 0.48), key=777)


def scene_title(c, v):
    k = pop(c.t / 0.7)
    cr = c.cr
    cr.save(); cr.translate(W / 2, 260); cr.scale(max(k, 1e-3), max(k, 1e-3)); cr.translate(-W / 2, -260)
    text(c, v["title"], W / 2, 290, 150, MARKER)
    cr.restore()
    if c.t > 0.5:
        fit_text(c, v.get("sub", ""), W / 2, 395, 60, W - 300, HAND, max_lines=2)
    ground_line(c)
    figure(c, dict(who="sam", x=.34, mood="happy", act="wave"), appear=0.6)
    figure(c, dict(who="alex", x=.66, mood="happy", act="wave"), appear=0.8)
    for i in range(3):
        coin(c, W / 2 - 60 + i * 60, 660 - 12 * abs(math.sin(c.t * 3 + i)), 26, key=300 + i)


def scene_chapter(c, v):
    cr = c.cr
    k = ease_out(c.t / 0.6)
    if v.get("n"):
        text(c, f"CHAPTER {v['n']}", W / 2, 400, 64, MARKER, GREEN, alpha=k)
    size = 110 if not v.get("small") else 96
    lines = wrap(c, v["title"], size, W - 280, MARKER)
    y0 = 540 - (len(lines) - 1) * size * 0.55
    for i, ln in enumerate(lines):
        text(c, ln, W / 2, y0 + i * size * 1.1, size, MARKER, alpha=k)
    p = ease_out((c.t - 0.4) / 0.8)
    if p > 0:
        ww = min(text_w(c, max(lines, key=len), size, MARKER), W - 280)
        y = y0 + (len(lines) - 1) * size * 1.1 + 45
        x1 = W / 2 - ww / 2
        stroke_path(c, [(x1, y), (x1 + ww * p * 0.5, y + 6), (x1 + ww * p, y - 2)], 10, GREEN, key=55)
    for i in range(2):
        coin(c, 230 + i * 1460, 300 + 20 * math.sin(c.t * 2 + i * 2), 40, key=610 + i)
    figure(c, dict(who="sam", x=0.12, mood="happy", act="idle", face=1, name=False), sc=0.55, ground=GROUND + 60, appear=0.5)
    figure(c, dict(who="alex", x=0.88, mood="happy", act="idle", face=-1, name=False), sc=0.55, ground=GROUND + 60, appear=0.7)


def scene_big(c, v):
    col = hexc(v.get("color", "#1F1F1F"))
    cr = c.cr
    size = 104
    lines = wrap(c, v["text"], size, W - 300, MARKER)
    while len(lines) > 3:
        size *= 0.9
        lines = wrap(c, v["text"], size, W - 300, MARKER)
    y0 = 430 - (len(lines) - 1) * size * 0.55
    for i, ln in enumerate(lines):
        p = ease_out((c.t - 0.3 - i * 0.35) / 0.6)
        if p > 0:
            ww = text_w(c, ln, size, MARKER)
            yy = y0 + i * size * 1.15
            cr.new_path(); cr.rectangle(W / 2 - ww / 2 - 20, yy - size * 0.72, (ww + 40) * p, size * 0.95)
            cr.set_source_rgba(*HILITE, 0.9); cr.fill()
        text(c, ln, W / 2, y0 + i * size * 1.15, size, MARKER, col if i == 0 or True else INK, alpha=ease_out(c.t / 0.4))
    if v.get("sub") and c.t > 0.9:
        fit_text(c, v["sub"], W / 2, y0 + len(lines) * size * 1.15 + 40, 58, W - 300, HAND, (0.3, 0.3, 0.3), 2)
    who = "alex" if v.get("color") in ("#2E9E5B", "#2F6FD6") else "sam"
    mood = "happy" if who == "alex" else "confused"
    figure(c, dict(who=who, x=0.9, mood=mood, act="point", face=-1, name=False), sc=0.55, ground=GROUND + 10, appear=0.6)


def scene_stat(c, v):
    col = hexc(v.get("color", "#2E9E5B"))
    p = ease_out((c.t - 0.3) / 1.8)
    val = v["value"] * p
    s = f"{v.get('prefix', '')}{val:,.0f}{v.get('suffix', '')}"
    k = pop(c.t / 0.6)
    cr = c.cr
    cr.save(); cr.translate(W / 2, 470); cr.scale(max(k, 1e-3), max(k, 1e-3)); cr.translate(-W / 2, -470)
    text(c, s, W / 2, 520, 200, MARKER, col)
    cr.restore()
    if c.t > 0.8:
        fit_text(c, v.get("label", ""), W / 2, 650, 62, W - 300, HAND, max_lines=2)
    for i, (cx_, cy_) in enumerate([(260, 300), (1660, 300), (300, 760), (1620, 760)]):
        coin(c, cx_, cy_ + 18 * math.sin(c.t * 2.2 + i * 1.7), 34, key=640 + i)


def axes(c, x0, y0, x1, y1, p):
    stroke_path(c, [(x0, y1), (x0, y1 + (y0 - y1) * p)], 6, key=31)
    stroke_path(c, [(x0, y1), (x0 + (x1 - x0) * p, y1)], 6, key=32)


def nice_max(v):
    raw = v * 1.08 / 4
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        if m * mag >= raw:
            return 4 * m * mag
    return v


def nice_label(v, money_fmt):
    if not money_fmt:
        return f"{v:,.0f}"
    if v >= 1e6:
        return f"${v / 1e6:.2f}M"
    if v >= 1e4:
        return f"${v / 1e3:,.0f}k"
    return money(v)


def scene_line(c, v):
    headline(c, v.get("title"), 120, 64)
    x0, x1, y0, y1 = 260, 1620, 210, 820
    p_ax = ease_out(c.t / 0.8)
    axes(c, x0, y0, x1, y1, p_ax)
    series = v["series"]
    allv = [d for s in series for d in s["data"]]
    vmin = 0 if not v.get("wiggle") else 0
    vmax = nice_max(max(allv))
    n = len(series[0]["data"])
    text(c, v.get("xlabel", ""), x1, y1 + 95, 40, align="right", color=(0.4, 0.4, 0.4))
    # x ticks
    for i in range(n):
        if n <= 11 or i % max(1, (n - 1) // 6) == 0:
            xv = v["x0"] + (v["x1"] - v["x0"]) * i / (n - 1)
            xx = x0 + (x1 - x0) * i / (n - 1)
            if p_ax > 0.9:
                text(c, f"{xv:g}", xx, y1 + 45, 34, color=(0.4, 0.4, 0.4))
    for j in range(1, 5):
        yy = y1 - (y1 - y0) * j / 4
        val = vmin + (vmax - vmin) * j / 4
        if p_ax > 0.9:
            text(c, nice_label(val, v.get("money")), x0 - 20, yy + 12, 32, align="right", color=(0.4, 0.4, 0.4))
            c.cr.set_source_rgba(0, 0, 0, 0.08); c.cr.set_line_width(2); c.cr.move_to(x0, yy); c.cr.line_to(x1, yy); c.cr.stroke()
    draw_t = max(4.0, c.dur * 0.75)
    p = ease_out((c.t - 0.8) / draw_t) if not v.get("wiggle") else clamp((c.t - 0.8) / draw_t)
    for si, s in enumerate(series):
        col = hexc(s["color"])
        data = s["data"]
        m = p * (n - 1)
        pts = []
        for i in range(n):
            if i > m:
                break
            pts.append((x0 + (x1 - x0) * i / (n - 1), y1 - (y1 - y0) * (data[i] - vmin) / (vmax - vmin)))
        if m < n - 1 and m > 0:
            i = int(m); f = m - i
            xa, ya = x0 + (x1 - x0) * i / (n - 1), y1 - (y1 - y0) * (data[i] - vmin) / (vmax - vmin)
            xb, yb = x0 + (x1 - x0) * (i + 1) / (n - 1), y1 - (y1 - y0) * (data[i + 1] - vmin) / (vmax - vmin)
            pts.append((xa + (xb - xa) * f, ya + (yb - ya) * f))
        if len(pts) >= 2:
            cr = c.cr
            cr.new_path(); cr.move_to(*pts[0])
            for q in pts[1:]:
                cr.line_to(*q)
            cr.set_source_rgb(*col); cr.set_line_width(18 - 9 * si if len(series) > 1 else 9); cr.set_line_join(cairo.LINE_JOIN_ROUND); cr.set_line_cap(cairo.LINE_CAP_ROUND); cr.stroke()
            ex, ey = pts[-1]
            cr.new_path(); cr.arc(ex, ey, 11, 0, 2 * math.pi); cr.set_source_rgb(*col); cr.fill()
            if not v.get("wiggle"):
                cur = data[min(int(m), n - 1)] if m >= n - 1 else data[int(m)] + (data[min(int(m) + 1, n - 1)] - data[int(m)]) * (m - int(m))
                text(c, nice_label(cur, v.get("money")) if v.get("money") else f"{cur:,.0f}", ex + 18, ey - 18 + (50 if si == 1 and abs(cur - series[0]['data'][min(int(m), n - 1)]) < 0.08 * vmax else 0), 42, MARKER, col, align="left")
        # legend
        lx, ly = x0 + 40, y0 + 10 + si * 56
        c.cr.new_path(); c.cr.rectangle(lx, ly - 22, 40, 14); c.cr.set_source_rgb(*col); c.cr.fill()
        text(c, s["name"], lx + 56, ly - 4, 44, align="left")


def scene_bars(c, v):
    headline(c, v.get("title"), 140, 64)
    items = v["items"]
    n = len(items)
    vmax = max(i[1] for i in items)
    x0, x1 = 600, 1620
    top, gap = 260, min(150, 560 / n)
    bh = gap * 0.62
    span = max(1.5, (c.dur - 1.5) * 0.7)
    for i, (label, val, col) in enumerate(items):
        st = 0.5 + i * span / n
        p = ease_out((c.t - st) / 1.0)
        y = top + i * gap
        text(c, label, x0 - 30, y + bh * 0.68, 48, align="right", alpha=clamp((c.t - st + 0.3) / 0.3))
        if p <= 0:
            continue
        w = (x1 - x0) * (val / vmax) * p
        rect(c, x0, y, max(w, 6), bh, 5, fill=hexc(col), key=40 + i)
        s = money(val * p, 2 if (isinstance(val, float) and val < 1000) else 0) if v.get("money") else f"{val * p:,.0f}"
        text(c, s, x0 + w + 20, y + bh * 0.7, 54, MARKER, align="left")


def scene_bullets(c, v):
    headline(c, v.get("title"), 150, 80)
    items = v["items"]
    n = len(items)
    size = 58 if n <= 4 else 52
    gap = min(110, 600 / n)
    y0 = 300
    icon = v.get("icon", "check")
    span = c.dur * 0.82
    for i, it in enumerate(items):
        st = 0.4 + span * i / n
        k = pop((c.t - st) / 0.45)
        if k <= 0:
            continue
        y = y0 + i * gap
        x = 430
        cr = c.cr
        if icon == "num":
            circle(c, x, y - size * 0.32, 34 * k, 5, fill=GREEN if i % 2 == 0 else BLUE, key=200 + i)
            text(c, str(i + 1), x, y - size * 0.32 + 15, 40 * k, MARKER, (1, 1, 1))
        else:
            rect(c, x - 28, y - size * 0.32 - 28, 56, 56, 5, fill=(1, 1, 1), key=200 + i)
            if k > 0.5:
                stroke_path(c, [(x - 18, y - size * 0.32), (x - 4, y - size * 0.32 + 16), (x + 26, y - size * 0.32 - 26)], 8, GREEN, key=220 + i)
        cr.save(); cr.translate(x + 70, y); cr.scale(1, 1)
        text(c, it, 0, 0, size, align="left", alpha=clamp(k))
        cr.restore()
    figure(c, dict(who="alex", x=0.86, mood="happy", act="point", face=-1, name=False), sc=0.7, ground=GROUND + 40, appear=0.3)


def scene_versus(c, v):
    cr = c.cr
    p = ease_out(c.t / 0.6)
    stroke_path(c, [(W / 2, 90), (W / 2, 90 + (CAP_TOP - 120) * p)], 5, color=(0.6, 0.6, 0.6), key=90)
    for side, cx, tstart, tspan in (("left", W * 0.25, 0.5, 0.42), ("right", W * 0.75, 0.5 + c.dur * 0.47, 0.42)):
        d = v[side]
        hk = clamp((c.t - (0.2 if side == "left" else tstart - 0.6)) / 0.5)
        text(c, d["title"], cx, 140, 70, MARKER, GREEN if d.get("mood") == "happy" else RED, alpha=hk)
        figure(c, dict(who=d["who"], x=cx - 270, mood=d.get("mood", "neutral"), act="idle", face=1, name=False),
               sc=0.62, ground=520, appear=0.1 if side == "left" else tstart - 0.6)
        lines = d["lines"]
        for i, ln in enumerate(lines):
            st = (0.4 if side == "left" else tstart) + c.dur * tspan * i / len(lines)
            a = clamp((c.t - st) / 0.35)
            if a <= 0:
                continue
            y = 270 + i * 120
            col = INK if i < len(lines) - 1 else (GREEN if d.get("mood") == "happy" else RED)
            text(c, ln, cx + 60, y + 130, 54, MARKER if i == len(lines) - 1 else HAND, col, alpha=a)
            if i < len(lines) - 1 and a >= 1:
                stroke_path(c, [(cx + 60, y + 150), (cx + 60, y + 190)], 4, color=(0.6, 0.6, 0.6), key=95 + i)


def scene_pie(c, v):
    headline(c, v.get("title"), 140, 64)
    cr = c.cr
    items = v["items"]
    cx, cy, r = 640, 540, 300
    total = sum(i[1] for i in items)
    span = max(2.0, c.dur * 0.6)
    a0 = -math.pi / 2
    for i, (label, pct, col) in enumerate(items):
        st = 0.5 + span * i / len(items)
        p = ease_out((c.t - st) / 0.9)
        frac = pct / total
        if p > 0 and frac > 0:
            cr.new_path(); cr.move_to(cx, cy); cr.arc(cx, cy, r, a0, a0 + 2 * math.pi * frac * p); cr.close_path()
            cr.set_source_rgb(*hexc(col)); cr.fill_preserve(); cr.set_source_rgb(*INK); cr.set_line_width(5); cr.stroke()
            if p >= 1 and frac > 0.06:
                am = a0 + math.pi * frac
                text(c, f"{pct:g}%", cx + math.cos(am) * r * 0.62, cy + math.sin(am) * r * 0.62 + 16, 46, MARKER, (1, 1, 1))
        a0 += 2 * math.pi * frac
        ly = 320 + i * 90
        if c.t > st:
            cr.new_path(); cr.rectangle(1100, ly - 34, 44, 44); cr.set_source_rgb(*hexc(col)); cr.fill_preserve()
            cr.set_source_rgb(*INK); cr.set_line_width(4); cr.stroke()
            text(c, f"{label}  ({pct:g}%)", 1170, ly, 52, align="left", color=RED if pct == 0 else INK)
    circle(c, cx, cy, r, 6, key=500)


SCENES = dict(stage=scene_stage, title=scene_title, chapter=scene_chapter, big=scene_big, stat=scene_stat,
              line=scene_line, bars=scene_bars, bullets=scene_bullets, versus=scene_versus, pie=scene_pie)


# ---------------------------------------------------------------- captions + chrome
def caption_chunks(sentences):
    out = []
    for s in sentences:
        words = s["text"].split()
        chunks, cur = [], []
        for w in words:
            cur.append(w)
            if len(" ".join(cur)) > 78:
                chunks.append(cur); cur = []
        if cur:
            if chunks and len(" ".join(cur)) < 18:
                chunks[-1] += cur
            else:
                chunks.append(cur)
        total = sum(len(" ".join(ch)) for ch in chunks)
        t = s["start"]
        for ch in chunks:
            d = s["dur"] * len(" ".join(ch)) / total
            out.append((t, t + d, " ".join(ch)))
            t += d
    return out


def draw_caption(c, gt, chunks):
    cur = None
    for a, b, s in chunks:
        if a - 0.05 <= gt < b + 0.25:
            cur = s
    if not cur:
        return
    cr = c.cr
    size = 46
    lines = wrap(c, cur, size, W - 360)
    h = len(lines) * size * 1.2 + 26
    w = max(text_w(c, ln, size) for ln in lines) + 60
    y = CAP_TOP + 10 + (2 - len(lines)) * size * 0.6
    rrect_path(cr, W / 2 - w / 2, y, w, h, 18)
    cr.set_source_rgba(0.12, 0.12, 0.12, 0.88); cr.fill()
    for i, ln in enumerate(lines):
        text(c, ln, W / 2, y + 13 + size * 0.9 + i * size * 1.2, size, HAND, (1, 1, 1))


def draw_chrome(c, chapter_label, gt, total):
    if chapter_label:
        text(c, chapter_label, 60, 60, 34, HAND, (0.5, 0.47, 0.43), align="left")
    cr = c.cr
    cr.new_path(); cr.rectangle(0, H - 8, W * gt / total, 8); cr.set_source_rgba(*GREEN, 0.8); cr.fill()


_PAPER = None


def paper():
    global _PAPER
    if _PAPER is None:
        import random
        rnd = random.Random(7)
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        cr = cairo.Context(s)
        cr.set_source_rgb(*PAPER); cr.paint()
        for _ in range(2500):
            x, y = rnd.random() * W, rnd.random() * H
            cr.set_source_rgba(0.5, 0.42, 0.3, rnd.random() * 0.05)
            cr.rectangle(x, y, rnd.choice([1, 2, 3]), rnd.choice([1, 2]))
            cr.fill()
        g = cairo.RadialGradient(W / 2, H / 2, H * 0.4, W / 2, H / 2, H * 1.0)
        g.add_color_stop_rgba(0, 0, 0, 0, 0); g.add_color_stop_rgba(1, 0.35, 0.25, 0.1, 0.12)
        cr.set_source(g); cr.paint()
        _PAPER = s
    return _PAPER


def render_frame(surface, scene, local_t, gt, total, chunks, chapter_label):
    cr = cairo.Context(surface)
    cr.set_source_surface(paper(), 0, 0); cr.paint()
    c = Ctx(cr, local_t, scene["dur"])
    fade = clamp(local_t / 0.25)
    cr.push_group()
    SCENES[scene["visual"]["type"]](c, scene["visual"])
    cr.pop_group_to_source()
    cr.paint_with_alpha(fade)
    draw_chrome(c, chapter_label, gt, total)
    draw_caption(c, gt, chunks)


def render_scene(args):
    idx, tl_path, out_dir = args
    tl = json.load(open(tl_path))
    sc = tl["scenes"][idx]
    out = Path(out_dir) / f"seg_{idx:03d}.mp4"
    if out.exists() and out.stat().st_size > 1000:
        return str(out)
    chunks = caption_chunks(sc["sentences"])
    label = ""
    for s in tl["scenes"][: idx + 1]:
        v = s["visual"]
        if v["type"] == "chapter" and v.get("n"):
            label = f"Chapter {v['n']}: {v['title']}"
    f0, f1 = round(sc["start"] * FPS), round(sc["end"] * FPS)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    tmp = out.with_suffix(".tmp.mp4")
    proc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", f"{W}x{H}",
                             "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-tune", "animation",
                             "-crf", "20", "-pix_fmt", "yuv420p", "-threads", "2", str(tmp)], stdin=subprocess.PIPE)
    for f in range(f0, f1):
        gt = f / FPS
        render_frame(surface, sc, gt - sc["start"], gt, tl["total"], chunks, label)
        surface.flush()
        proc.stdin.write(bytes(surface.get_data()))
    proc.stdin.close(); proc.wait()
    tmp.rename(out)
    return str(out)


def preview(idx, t_local, path):
    tl = json.load(open(ROOT / "timeline.json"))
    sc = tl["scenes"][idx]
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
    render_frame(surface, sc, t_local, sc["start"] + t_local, tl["total"], caption_chunks(sc["sentences"]), "Chapter 1: Preview")
    surface.write_to_png(path)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        preview(int(sys.argv[2]), float(sys.argv[3]), sys.argv[4])
        sys.exit()
    tl_path = ROOT / "timeline.json"
    out_dir = ROOT / "build" / "segments"
    out_dir.mkdir(parents=True, exist_ok=True)
    n = len(json.load(open(tl_path))["scenes"])
    order = sorted(range(n), key=lambda i: -json.load(open(tl_path))["scenes"][i]["dur"])
    with Pool(int(os.environ.get("JOBS", "4"))) as pool:
        for i, r in enumerate(pool.imap_unordered(render_scene, [(i, str(tl_path), str(out_dir)) for i in order])):
            print(f"[{i + 1}/{n}] {r}", flush=True)
