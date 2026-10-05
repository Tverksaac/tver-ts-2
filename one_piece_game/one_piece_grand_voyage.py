#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================================
   ONE PIECE : ВЕЛИКИЙ ПУТЬ   (фанатская игра по вселенной One Piece)
=====================================================================
 Установка:   pip install pygame-ce numpy
 Запуск:      python3 one_piece_grand_voyage.py

 Всё — графика, музыка, звуки — генерируется кодом.
 Музыка синтезируется при первом запуске (оркестр, фортепиано, хор,
 фолк-инструменты) и кэшируется в ~/.onepiece_grand_voyage/

 УПРАВЛЕНИЕ НА ОСТРОВЕ
   WASD — движение        Мышь — прицел
   ЛКМ  — комбо           ПКМ (держать) — заряженный удар
   Space — рывок          Shift — блок / парирование (вовремя)
   1-4  — способности     R — ультимейт   F — пробуждение
   Q — Хаки Вооружения    C — Хаки Наблюдения   Z — Королевское Хаки
   X — съесть мясо        E — взаимодействие
   Tab / Esc — меню       F11 — полный экран
 УПРАВЛЕНИЕ НА КОРАБЛЕ
   W/S — паруса   A/D — руль   ЛКМ — бортовой залп (по стороне мыши)
   ПКМ — Гаон-пушка (держать)  Space — Coup de Burst   Shift — якорь
   E — высадиться / абордаж / подобрать   F — рыбалка   M — карта мира
=====================================================================
"""
import os, sys, math, random, json, time, threading, wave, copy, traceback, functools

try:
    import numpy as np
except ImportError:
    print("Нужен numpy:  pip install numpy")
    sys.exit(1)
try:
    import pygame
except ImportError:
    print("Нужен pygame-ce:  pip install pygame-ce")
    sys.exit(1)

V = pygame.math.Vector2

# ------------------------------------------------------------------
#  КОНСТАНТЫ
# ------------------------------------------------------------------
GAME_TITLE = "ONE PIECE: Великий Путь"
W, H = 1280, 720
FPS = 60
TILE = 40
SAVE_DIR = os.path.join(os.path.expanduser("~"), ".onepiece_grand_voyage")
MUSIC_VER = 3
DEBUG = "--debug" in sys.argv
HEADLESS_TEST = "--selftest" in sys.argv

try:
    os.makedirs(SAVE_DIR, exist_ok=True)
except Exception:
    pass

# ------------------------------------------------------------------
#  УТИЛИТЫ
# ------------------------------------------------------------------
def clamp(x, a, b):
    return a if x < a else (b if x > b else x)

def lerp(a, b, t):
    return a + (b - a) * t

def inv_lerp(a, b, x):
    return 0.0 if b == a else (x - a) / (b - a)

def ease_out(t):
    t = clamp(t, 0, 1)
    return 1 - (1 - t) ** 3

def ease_in(t):
    t = clamp(t, 0, 1)
    return t * t * t

def ease_in_out(t):
    t = clamp(t, 0, 1)
    return 3 * t * t - 2 * t * t * t

def ease_back(t):
    t = clamp(t, 0, 1)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2

def lerp_col(c1, c2, t):
    t = clamp(t, 0, 1)
    return (int(c1[0] + (c2[0] - c1[0]) * t), int(c1[1] + (c2[1] - c1[1]) * t), int(c1[2] + (c2[2] - c1[2]) * t))

def mul_col(c, k):
    return (clamp(int(c[0] * k), 0, 255), clamp(int(c[1] * k), 0, 255), clamp(int(c[2] * k), 0, 255))

def add_col(c, d):
    return (clamp(c[0] + d, 0, 255), clamp(c[1] + d, 0, 255), clamp(c[2] + d, 0, 255))

def ang_diff(a, b):
    d = (b - a) % (2 * math.pi)
    if d > math.pi:
        d -= 2 * math.pi
    return d

def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def dist2(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx * dx + dy * dy

def from_angle(a, l=1.0):
    return V(math.cos(a) * l, math.sin(a) * l)

def angle_to(a, b):
    return math.atan2(b[1] - a[1], b[0] - a[0])

def point_seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    px, py = p
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - ax, py - ay)
    t = clamp(((px - ax) * dx + (py - ay) * dy) / l2, 0, 1)
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

def fmt_num(n):
    n = int(n)
    s = f"{abs(n):,}".replace(",", " ")
    return ("-" if n < 0 else "") + s

def fmt_beli(n):
    n = int(n)
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.2f} млрд"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} млн"
    return fmt_num(n)

def wrap_text(font, text, width):
    lines = []
    for para in text.split("\n"):
        words = para.split(" ")
        cur = ""
        for w_ in words:
            test = (cur + " " + w_).strip()
            if font.size(test)[0] <= width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w_
        lines.append(cur)
    return lines

def weighted_choice(items, rng=random):
    tot = sum(w_ for _, w_ in items)
    r = rng.uniform(0, tot)
    acc = 0
    for it, w_ in items:
        acc += w_
        if r <= acc:
            return it
    return items[-1][0]

class Timer:
    __slots__ = ("t",)
    def __init__(self, t=0.0):
        self.t = t
    def tick(self, dt):
        self.t = max(0.0, self.t - dt)
        return self.t <= 0
    def ready(self):
        return self.t <= 0
    def set(self, t):
        self.t = t

def value_noise_2d(w, h, scale, seed, octaves=4):
    """Плавный шум (numpy) — для текстур и форм островов."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp = 1.0
    tot = 0.0
    s = scale
    for _ in range(octaves):
        gw = int(w / s) + 3
        gh = int(h / s) + 3
        grid = rng.random((gh, gw)).astype(np.float32)
        ys = np.arange(h) / s
        xs = np.arange(w) / s
        y0 = ys.astype(int)
        x0 = xs.astype(int)
        fy = (ys - y0)[:, None]
        fx = (xs - x0)[None, :]
        fy = fy * fy * (3 - 2 * fy)
        fx = fx * fx * (3 - 2 * fx)
        g00 = grid[y0[:, None], x0[None, :]]
        g10 = grid[y0[:, None], x0[None, :] + 1]
        g01 = grid[y0[:, None] + 1, x0[None, :]]
        g11 = grid[y0[:, None] + 1, x0[None, :] + 1]
        top = g00 + (g10 - g00) * fx
        bot = g01 + (g11 - g01) * fx
        out += (top + (bot - top) * fy) * amp
        tot += amp
        amp *= 0.5
        s = max(1.0, s / 2)
    return out / tot

def periodic_noise(n, cells, seed, octaves=4):
    """Бесшовный (тайлящийся) шум n×n."""
    rng = np.random.default_rng(seed)
    out = np.zeros((n, n), np.float32)
    amp = 1.0
    tot = 0.0
    c = cells
    for _ in range(octaves):
        grid = rng.random((c, c)).astype(np.float32)
        coords = np.arange(n) * c / n
        i0 = coords.astype(int) % c
        i1 = (i0 + 1) % c
        f = coords - np.floor(coords)
        f = f * f * (3 - 2 * f)
        fy = f[:, None]
        fx = f[None, :]
        g00 = grid[i0[:, None], i0[None, :]]
        g10 = grid[i0[:, None], i1[None, :]]
        g01 = grid[i1[:, None], i0[None, :]]
        g11 = grid[i1[:, None], i1[None, :]]
        top = g00 + (g10 - g00) * fx
        bot = g01 + (g11 - g01) * fx
        out += (top + (bot - top) * fy) * amp
        tot += amp
        amp *= 0.5
        c *= 2
    return out / tot

# ==================================================================
#  СИНТЕЗАТОР  (оркестр / фортепиано / хор / фолк) на numpy
# ==================================================================
SR = 32000
F32 = np.float32

def mtof(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)

_NN = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}

def nm(s):
    """'C#4' -> midi"""
    s = s.strip()
    n = _NN[s[0].upper()]
    i = 1
    while i < len(s) and s[i] in '#b':
        n += 1 if s[i] == '#' else -1
        i += 1
    return 12 * (int(s[i:]) + 1) + n

def env_adsr(total, hold, a, d, s, r):
    t = np.arange(total, dtype=F32) / SR
    a = max(a, 1e-3)
    d = max(d, 1e-3)
    r = max(r, 1e-3)
    e = np.where(t < a, t / a, s + (1 - s) * np.exp(-(t - a) / d))
    if hold < total:
        lvl = float(e[hold]) if hold > 0 else 0.0
        ht = hold / SR
        e = np.where(t < ht, e, lvl * np.exp(-np.maximum(t - ht, 0) * (6.0 / r)))
    return e.astype(F32)

def vibrato(t, rate, depth, delay=0.0, rng=None):
    ph = rng.uniform(0, 6.28) if rng is not None else 0.0
    ramp = np.clip((t - delay) / 0.5, 0, 1)
    return 1.0 + depth * np.sin(2 * np.pi * rate * t + ph) * ramp

def phase_from_freq(farr):
    return np.cumsum(farr, dtype=np.float64) / SR

def saw_blep(phase, dph):
    t = (phase % 1.0).astype(F32)
    dt = np.maximum(dph.astype(F32), 1e-5)
    y = 2.0 * t - 1.0
    m1 = t < dt
    if m1.any():
        x = t[m1] / dt[m1]
        y[m1] -= x + x - x * x - 1.0
    m2 = t > 1.0 - dt
    if m2.any():
        x = (t[m2] - 1.0) / dt[m2]
        y[m2] -= x * x + x + x + 1.0
    return y

def lp_noise(n, rng, smooth=8):
    x = rng.standard_normal(n).astype(F32)
    if smooth > 1:
        k = np.ones(smooth, F32) / smooth
        x = np.convolve(x, k, mode='same')
    return x

# ---------------- инструменты ----------------
def inst_strings(m, hold, vel, rng, a=0.22, r=0.55, bright=1.0, voices=3):
    f = mtof(m)
    total = hold + int(r * SR) + 1
    t = np.arange(total, dtype=F32) / SR
    y = np.zeros(total, F32)
    det = [-7, 0, 7, -12, 12][:voices]
    for c in det:
        fv = f * 2 ** (c / 1200.0) * vibrato(t, rng.uniform(4.8, 5.8), 0.0028, 0.25, rng)
        y += saw_blep(phase_from_freq(fv) + rng.random(), fv / SR)
    y /= voices
    env = env_adsr(total, hold, a, 0.4, 0.85, r)
    return y * env * (0.55 + 0.45 * vel)

def inst_strings_short(m, hold, vel, rng):
    f = mtof(m)
    hold = min(hold, int(0.2 * SR))
    total = hold + int(0.12 * SR)
    t = np.arange(total, dtype=F32) / SR
    y = np.zeros(total, F32)
    for c in (-6, 6):
        fv = np.full(total, f * 2 ** (c / 1200.0), F32)
        y += saw_blep(phase_from_freq(fv) + rng.random(), fv / SR)
    env = env_adsr(total, hold, 0.006, 0.09, 0.35, 0.08)
    return y * 0.5 * env * (0.5 + 0.5 * vel)

def inst_brass(m, hold, vel, rng, nharm=12, dark=1.0):
    f = mtof(m)
    total = hold + int(0.32 * SR)
    t = np.arange(total, dtype=F32) / SR
    env = env_adsr(total, hold, 0.05, 0.35, 0.78, 0.3)
    scoop = 1.0 - 0.025 * np.exp(-t / 0.035)
    fv = f * scoop * vibrato(t, 5.0, 0.0022, 0.35, rng)
    ph = 2 * np.pi * phase_from_freq(fv)
    bright = np.clip(env * (0.6 + 0.6 * vel), 0, 1).astype(F32)
    y = np.zeros(total, F32)
    nh = max(1, min(nharm, int(7000 / f)))
    for k in range(1, nh + 1):
        amp = (1.0 / k) * bright ** (dark * 0.55 * (k - 1))
        y += (amp * np.sin(k * ph)).astype(F32)
    return y * env * 0.55

def inst_horn(m, hold, vel, rng):
    return inst_brass(m, hold, vel, rng, nharm=8, dark=1.6)

def inst_trumpet(m, hold, vel, rng):
    return inst_brass(m, hold, vel, rng, nharm=14, dark=0.75)

def inst_piano(m, hold, vel, rng):
    f = mtof(m)
    sus = hold / SR
    dur = min(sus + 0.35, 3.8) if sus < 3.4 else 3.8
    dur = max(dur, 0.6)
    total = int(dur * SR) + int(0.25 * SR)
    t = np.arange(total, dtype=F32) / SR
    y = np.zeros(total, F32)
    nh = max(1, min(11, int(9000 / f)))
    B = 0.00035
    hi = (f / 261.6) ** 0.45
    for k in range(1, nh + 1):
        fk = k * f * math.sqrt(1 + B * k * k)
        amp = (1.0 / k ** 1.15) * (vel ** (0.25 * (k - 1)))
        dec = np.exp(-t * (0.45 + 0.42 * k) * hi)
        beat = 1.0 + 0.12 * np.cos(2 * np.pi * (0.6 + 0.15 * k) * t)
        y += (amp * dec * beat * np.sin(2 * np.pi * fk * t + rng.uniform(0, 6.28))).astype(F32)
    ham = lp_noise(total, rng, 3) * np.exp(-t / 0.004) * 0.08
    y += ham
    att = np.clip(t / 0.002, 0, 1)
    damp = np.where(t < sus, 1.0, np.exp(-(t - sus) * 9.0))
    return (y * att * damp * (0.35 + 0.65 * vel) * 0.6).astype(F32)

def inst_flute(m, hold, vel, rng):
    f = mtof(m)
    total = hold + int(0.18 * SR)
    t = np.arange(total, dtype=F32) / SR
    fv = f * vibrato(t, 5.2, 0.006, 0.28, rng)
    ph = 2 * np.pi * phase_from_freq(fv)
    y = np.sin(ph) + 0.22 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
    breath = lp_noise(total, rng, 6) * np.sin(ph) * 0.18
    chiff = lp_noise(total, rng, 2) * np.exp(-t / 0.03) * 0.15
    env = env_adsr(total, hold, 0.07, 0.3, 0.9, 0.15)
    return ((y + breath + chiff) * env * (0.5 + 0.5 * vel) * 0.5).astype(F32)

def inst_shakuhachi(m, hold, vel, rng):
    f = mtof(m)
    total = hold + int(0.25 * SR)
    t = np.arange(total, dtype=F32) / SR
    bend = 1.0 - 0.03 * np.exp(-t / 0.08)
    fv = f * bend * vibrato(t, 4.5, 0.011, 0.4, rng)
    ph = 2 * np.pi * phase_from_freq(fv)
    y = np.sin(ph) + 0.12 * np.sin(2 * ph)
    breath = lp_noise(total, rng, 4) * (0.35 + 0.3 * np.sin(ph)) * 0.35
    env = env_adsr(total, hold, 0.12, 0.3, 0.85, 0.22)
    return ((y + breath) * env * (0.5 + 0.5 * vel) * 0.45).astype(F32)

def inst_fiddle(m, hold, vel, rng):
    f = mtof(m)
    total = hold + int(0.12 * SR)
    t = np.arange(total, dtype=F32) / SR
    fv = f * vibrato(t, 6.0, 0.005, 0.15, rng)
    y = saw_blep(phase_from_freq(fv), fv / SR)
    env = env_adsr(total, hold, 0.03, 0.2, 0.8, 0.1)
    return (y * env * (0.5 + 0.5 * vel) * 0.45).astype(F32)

def inst_accordion(m, hold, vel, rng):
    f = mtof(m)
    total = hold + int(0.1 * SR)
    y = np.zeros(total, F32)
    for c in (-9, 9):
        fv = np.full(total, f * 2 ** (c / 1200), F32)
        ph = phase_from_freq(fv)
        dph = fv / SR
        y += saw_blep(ph, dph) - saw_blep(ph + 0.32, dph)
    t = np.arange(total, dtype=F32) / SR
    env = env_adsr(total, hold, 0.035, 0.2, 0.85, 0.08)
    return (y * 0.3 * env * (0.5 + 0.5 * vel)).astype(F32)

def inst_pluck(m, hold, vel, rng, bright=0.6, decay=0.996, length=None):
    f = mtof(m)
    P = SR / f
    L = int(P)
    w1 = P - L
    w0 = 1.0 - w1
    dur = length if length else min(max(hold / SR + 0.5, 0.8), 2.8)
    total = int(dur * SR)
    out = np.zeros(total + L + 2, F32)
    burst = rng.uniform(-1, 1, L + 1).astype(F32)
    sm = int(1 + (1 - bright) * 6)
    if sm > 1:
        burst = np.convolve(burst, np.ones(sm, F32) / sm, mode='same')
    out[:L + 1] = burst
    pos = L + 1
    end = total + L + 2
    while pos < end:
        n = min(L, end - pos)
        out[pos:pos + n] = decay * (w0 * out[pos - L:pos - L + n] + w1 * out[pos - L - 1:pos - L - 1 + n])
        pos += n
    y = out[:total]
    t = np.arange(total, dtype=F32) / SR
    rel = np.where(t < hold / SR + 0.25, 1.0, np.exp(-(t - hold / SR - 0.25) * 6))
    return (y * rel * (0.4 + 0.6 * vel) * 2.6).astype(F32)

def inst_guitar(m, hold, vel, rng):
    return inst_pluck(m, hold, vel, rng, bright=0.55, decay=0.995)

def inst_harp(m, hold, vel, rng):
    return inst_pluck(m, hold, vel, rng, bright=0.7, decay=0.9975, length=2.5)

def inst_koto(m, hold, vel, rng):
    y = inst_pluck(m, hold, vel, rng, bright=0.95, decay=0.9965, length=2.2)
    return y

def inst_shamisen(m, hold, vel, rng):
    y = inst_pluck(m, hold, vel, rng, bright=1.0, decay=0.991, length=1.0)
    return np.tanh(y * 1.6).astype(F32) * 0.8

def inst_choir(m, hold, vel, rng):
    f = mtof(m)
    total = hold + int(0.7 * SR)
    t = np.arange(total, dtype=F32) / SR
    y = np.zeros(total, F32)
    for c in (-11, -4, 3, 10):
        fv = f * 2 ** (c / 1200.0) * vibrato(t, rng.uniform(4.6, 5.6), 0.005, 0.3, rng)
        y += saw_blep(phase_from_freq(fv) + rng.random(), fv / SR)
    y *= 0.25
    y += lp_noise(total, rng, 3) * 0.05
    env = env_adsr(total, hold, 0.3, 0.6, 0.9, 0.65)
    return (y * env * (0.5 + 0.5 * vel)).astype(F32)

def inst_bell(m, hold, vel, rng):
    f = mtof(m)
    total = int(2.2 * SR)
    t = np.arange(total, dtype=F32) / SR
    y = np.zeros(total, F32)
    for ratio, amp, dec in ((1.0, 1.0, 1.6), (2.0, 0.5, 2.4), (3.0, 0.25, 3.5), (4.17, 0.2, 5.0), (5.43, 0.12, 6.5)):
        y += (amp * np.exp(-t * dec) * np.sin(2 * np.pi * f * ratio * t)).astype(F32)
    att = np.clip(t / 0.002, 0, 1)
    return (y * att * vel * 0.35).astype(F32)

def inst_celesta(m, hold, vel, rng):
    f = mtof(m)
    total = int(1.4 * SR)
    t = np.arange(total, dtype=F32) / SR
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 3) + 0.3 * np.sin(2 * np.pi * 4 * f * t) * np.exp(-t * 9)
    return (y * np.clip(t / 0.002, 0, 1) * vel * 0.4).astype(F32)

def inst_bass(m, hold, vel, rng):
    """контрабас / виолончель legato"""
    f = mtof(m)
    total = hold + int(0.3 * SR)
    t = np.arange(total, dtype=F32) / SR
    fv = f * vibrato(t, 4.8, 0.0025, 0.4, rng)
    y = saw_blep(phase_from_freq(fv), fv / SR) * 0.6 + np.sin(2 * np.pi * phase_from_freq(fv)) * 0.5
    env = env_adsr(total, hold, 0.06, 0.3, 0.85, 0.25)
    return (y * env * (0.5 + 0.5 * vel) * 0.6).astype(F32)

def inst_pizz(m, hold, vel, rng):
    return inst_pluck(m, hold, vel, rng, bright=0.35, decay=0.993, length=0.9)

# ---------------- ударные ----------------
def drum_timpani(m, hold, vel, rng):
    f = mtof(m)
    total = int(1.8 * SR)
    t = np.arange(total, dtype=F32) / SR
    fv = f * (1 + 0.08 * np.exp(-t / 0.05))
    ph = 2 * np.pi * phase_from_freq(fv)
    y = np.sin(ph) * np.exp(-t * 2.2) + 0.5 * np.sin(1.5 * ph) * np.exp(-t * 3.5) + 0.3 * np.sin(1.98 * ph) * np.exp(-t * 4)
    y += lp_noise(total, rng, 6) * np.exp(-t / 0.02) * 0.6
    return (y * vel * 0.7).astype(F32)

def drum_taiko(m, hold, vel, rng):
    total = int(1.0 * SR)
    t = np.arange(total, dtype=F32) / SR
    fv = 52 + 70 * np.exp(-t / 0.045)
    y = np.sin(2 * np.pi * phase_from_freq(fv)) * np.exp(-t * 5.0)
    y += lp_noise(total, rng, 10) * np.exp(-t / 0.03) * 0.9
    y = np.tanh(y * 1.5)
    return (y * vel * 0.8).astype(F32)

def drum_small_taiko(m, hold, vel, rng):
    total = int(0.5 * SR)
    t = np.arange(total, dtype=F32) / SR
    fv = 140 + 120 * np.exp(-t / 0.02)
    y = np.sin(2 * np.pi * phase_from_freq(fv)) * np.exp(-t * 12)
    y += lp_noise(total, rng, 3) * np.exp(-t / 0.015) * 0.6
    return (y * vel * 0.55).astype(F32)

def drum_snare(m, hold, vel, rng):
    total = int(0.35 * SR)
    t = np.arange(total, dtype=F32) / SR
    n = rng.standard_normal(total).astype(F32)
    n = n - np.convolve(n, np.ones(4, F32) / 4, mode='same')
    y = n * np.exp(-t * 16) * 0.7 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 25) * 0.6
    return (y * vel * 0.45).astype(F32)

def drum_cymbal(m, hold, vel, rng):
    total = int(3.0 * SR)
    t = np.arange(total, dtype=F32) / SR
    n = rng.standard_normal(total).astype(F32)
    n = n - np.convolve(n, np.ones(3, F32) / 3, mode='same')
    att = np.clip(t / 0.01, 0, 1)
    y = n * np.exp(-t * 1.4) * att
    return (y * vel * 0.22).astype(F32)

def drum_swell(m, hold, vel, rng):
    """нарастающая тарелка (свелл) длиной hold"""
    total = hold + int(0.4 * SR)
    t = np.arange(total, dtype=F32) / SR
    n = rng.standard_normal(total).astype(F32)
    n = n - np.convolve(n, np.ones(3, F32) / 3, mode='same')
    ht = max(hold / SR, 0.1)
    e = np.where(t < ht, (t / ht) ** 2.5, np.exp(-(t - ht) * 8))
    return (n * e * vel * 0.25).astype(F32)

def drum_bodhran(m, hold, vel, rng):
    total = int(0.45 * SR)
    t = np.arange(total, dtype=F32) / SR
    fv = 85 + 60 * np.exp(-t / 0.02)
    y = np.sin(2 * np.pi * phase_from_freq(fv)) * np.exp(-t * 9)
    y += lp_noise(total, rng, 5) * np.exp(-t / 0.012) * 0.5
    return (y * vel * 0.6).astype(F32)

def drum_shaker(m, hold, vel, rng):
    total = int(0.12 * SR)
    t = np.arange(total, dtype=F32) / SR
    n = rng.standard_normal(total).astype(F32)
    n = n - np.convolve(n, np.ones(2, F32) / 2, mode='same')
    e = np.clip(t / 0.01, 0, 1) * np.exp(-t * 40)
    return (n * e * vel * 0.18).astype(F32)

def drum_bass(m, hold, vel, rng):
    total = int(0.6 * SR)
    t = np.arange(total, dtype=F32) / SR
    fv = 45 + 60 * np.exp(-t / 0.03)
    y = np.sin(2 * np.pi * phase_from_freq(fv)) * np.exp(-t * 6)
    return (np.tanh(y * 2) * vel * 0.7).astype(F32)

INSTRUMENTS = {
    'strings': inst_strings, 'strings_short': inst_strings_short, 'brass': inst_brass,
    'horn': inst_horn, 'trumpet': inst_trumpet, 'piano': inst_piano, 'flute': inst_flute,
    'shakuhachi': inst_shakuhachi, 'fiddle': inst_fiddle, 'accordion': inst_accordion,
    'guitar': inst_guitar, 'harp': inst_harp, 'koto': inst_koto, 'shamisen': inst_shamisen,
    'choir': inst_choir, 'bell': inst_bell, 'celesta': inst_celesta, 'bass': inst_bass,
    'pizz': inst_pizz, 'timpani': drum_timpani, 'taiko': drum_taiko, 'taiko_s': drum_small_taiko,
    'snare': drum_snare, 'cymbal': drum_cymbal, 'swell': drum_swell, 'bodhran': drum_bodhran,
    'shaker': drum_shaker, 'kick': drum_bass,
    'strings_slow': lambda m, h, v, r: inst_strings(m, h, v, r, a=0.6, r=1.0),
    'strings_lead': lambda m, h, v, r: inst_strings(m, h, v, r, a=0.08, r=0.35, voices=3),
}

_NOTE_CACHE = {}

def render_note(inst, m, hold, vel):
    q = SR // 40
    hq = max(1, (hold + q // 2) // q) * q
    key = (inst, m, hq, round(vel, 1))
    y = _NOTE_CACHE.get(key)
    if y is None:
        rng = np.random.default_rng(abs(hash(key)) % (2 ** 31))
        y = INSTRUMENTS[inst](m, hq, round(vel, 1), rng).astype(F32)
        if len(_NOTE_CACHE) > 4000:
            _NOTE_CACHE.clear()
        _NOTE_CACHE[key] = y
    return y

# ---------------- обработка ----------------
def _nfft(n):
    return 1 << int(n - 1).bit_length()

def fft_eq(x, fn):
    n = x.shape[-1]
    N = _nfft(n + 16)
    X = np.fft.rfft(x, N)
    f = np.fft.rfftfreq(N, 1.0 / SR)
    X *= fn(f)
    return np.fft.irfft(X, N)[..., :n].astype(F32)

def g_lp(f, fc, order=2):
    return 1.0 / np.sqrt(1.0 + (f / fc) ** (2 * order))

def g_hp(f, fc, order=2):
    with np.errstate(divide='ignore'):
        r = np.where(f > 0, fc / np.maximum(f, 1e-6), 1e9)
    return 1.0 / np.sqrt(1.0 + r ** (2 * order))

def g_peak(f, fc, gain, bw):
    return 1.0 + gain * np.exp(-((f - fc) / bw) ** 2)

EQS = {
    'strings': lambda f: g_lp(f, 3600, 2) * g_hp(f, 70) * g_peak(f, 2600, 0.3, 700) * g_peak(f, 350, 0.25, 150),
    'strings_dark': lambda f: g_lp(f, 2300, 2) * g_hp(f, 50),
    'brass': lambda f: g_lp(f, 4500, 2) * g_hp(f, 80) * g_peak(f, 1200, 0.35, 500),
    'choir': lambda f: g_hp(f, 120) * (0.25 + g_peak(f, 750, 2.6, 160) + g_peak(f, 1150, 1.6, 170) * 0.5 +
                                        g_peak(f, 2700, 1.0, 260) * 0.35) * g_lp(f, 4200, 3),
    'fiddle': lambda f: g_lp(f, 4200, 2) * g_hp(f, 180) * g_peak(f, 450, 0.6, 140) * g_peak(f, 2900, 0.7, 600),
    'accordion': lambda f: g_lp(f, 3800, 2) * g_hp(f, 120) * g_peak(f, 1500, 0.3, 500),
    'bass': lambda f: g_lp(f, 1400, 2) * g_hp(f, 30),
    'warm': lambda f: g_lp(f, 6000, 1) * g_hp(f, 40),
    'drums': lambda f: g_lp(f, 9000, 1) * g_hp(f, 25),
    'none': lambda f: np.ones_like(f),
}

def make_reverb_ir(t60_lo=2.6, t60_hi=1.3, length=2.8, seed=7):
    rng = np.random.default_rng(seed)
    n = int(length * SR)
    t = np.arange(n, dtype=F32) / SR
    irs = []
    for ch in range(2):
        noise = rng.standard_normal(n).astype(F32)
        lo = fft_eq(noise, lambda f: g_lp(f, 1800, 2))
        hi = noise - lo
        ir = lo * np.exp(-6.9 * t / t60_lo) + hi * np.exp(-6.9 * t / t60_hi) * 0.6
        pre = int(0.022 * SR)
        ir = np.concatenate([np.zeros(pre, F32), ir])[:n]
        for d, g in ((0.011, 0.5), (0.019, 0.35), (0.027, 0.3), (0.041, 0.22)):
            k = int((d + ch * 0.003) * SR)
            ir[k] += g
        ir *= np.clip(t / 0.008, 0, 1)
        irs.append(ir / np.sqrt(np.sum(ir ** 2)))
    return np.stack(irs)

def fft_convolve_stereo(x, ir):
    n = x.shape[-1]
    N = _nfft(n + ir.shape[-1])
    out = np.zeros_like(x)
    for ch in range(2):
        X = np.fft.rfft(x[ch], N)
        Hh = np.fft.rfft(ir[ch], N)
        out[ch] = np.fft.irfft(X * Hh, N)[:n]
    return out

_IR = None

def get_ir():
    global _IR
    if _IR is None:
        _IR = make_reverb_ir()
    return _IR

# ---------------- аккорды ----------------
CHORD_Q = {
    '': [0, 4, 7], 'm': [0, 3, 7], '7': [0, 4, 7, 10], 'maj7': [0, 4, 7, 11], 'm7': [0, 3, 7, 10],
    'sus4': [0, 5, 7], 'sus2': [0, 2, 7], 'dim': [0, 3, 6], 'aug': [0, 4, 8], 'add9': [0, 4, 7, 14],
    'm9': [0, 3, 7, 10, 14], '5': [0, 7], 'm6': [0, 3, 7, 9], '6': [0, 4, 7, 9],
}

def parse_chord(name):
    bass = None
    if '/' in name:
        name, b = name.split('/')
        bass = _NN[b[0]] + (1 if '#' in b else (-1 if len(b) > 1 and b[1] == 'b' else 0))
    root = _NN[name[0]]
    i = 1
    if i < len(name) and name[i] in '#b':
        root += 1 if name[i] == '#' else -1
        i += 1
    q = name[i:]
    ints = CHORD_Q.get(q, [0, 4, 7])
    root %= 12
    if bass is None:
        bass = root
    return root, ints, bass % 12

def voice_chord(root, ints, center=62, prev=None):
    pcs = [(root + iv) % 12 for iv in ints]
    best = None
    best_cost = 1e9
    for base in range(center - 9, center + 4):
        notes = []
        for pc in pcs:
            nn = base + ((pc - base) % 12)
            notes.append(nn)
        notes.sort()
        if prev:
            cost = sum(min(abs(n - p) for p in prev) for n in notes)
        else:
            cost = abs(sum(notes) / len(notes) - center) * 2
        cost += max(0, notes[-1] - notes[0] - 12) * 2
        if cost < best_cost:
            best_cost = cost
            best = notes
    return best

def parse_seq(s):
    out = []
    for tok in s.split():
        acc = tok.endswith('!')
        tok = tok.rstrip('!')
        n, d = tok.split('/')
        dur = float(d)
        if n in ('R', 'r', '-'):
            out.append((None, dur, acc))
        else:
            out.append((nm(n), dur, acc))
    return out

class Song:
    def __init__(self, bpm, bpb=4, bars=32, loop=True, tail=3.0):
        self.spb = 60.0 / bpm
        self.bpb = bpb
        self.bars = bars
        self.loop = loop
        self.length = int(round(bars * bpb * self.spb * SR))
        self.tail = int(tail * SR)
        self.total = self.length + self.tail
        self.stems = {}

    def stem(self, name, send=0.3, eq='none', gain=1.0):
        if name not in self.stems:
            self.stems[name] = {'buf': np.zeros((2, self.total), F32), 'send': send, 'eq': eq, 'gain': gain}
        return name

    def note(self, stem, inst, m, beat, dur, vel=0.8, pan=0.0, legato=1.0):
        if m is None:
            return
        st = self.stems[stem]
        start = int(round(beat * self.spb * SR))
        if start >= self.total or start < 0:
            return
        hold = max(1, int(dur * legato * self.spb * SR))
        y = render_note(inst, m, hold, clamp(vel, 0.05, 1.0))
        n = min(len(y), self.total - start)
        p = clamp(pan, -1, 1)
        gl = math.cos((p + 1) * math.pi / 4)
        gr = math.sin((p + 1) * math.pi / 4)
        st['buf'][0, start:start + n] += y[:n] * gl
        st['buf'][1, start:start + n] += y[:n] * gr

    def line(self, stem, inst, seq, beat, vel=0.8, pan=0.0, tr=0, legato=0.98, accent=0.15, humanize=0.0):
        b = beat
        for m, d, acc in parse_seq(seq) if isinstance(seq, str) else seq:
            if m is not None:
                v = vel + (accent if acc else 0)
                off = random.uniform(-humanize, humanize) if humanize else 0
                self.note(stem, inst, m + tr, b + off, d, v, pan, legato)
            b += d
        return b

    def chords(self, prog, bar0=0):
        """prog: список строк (по такту), в строке несколько аккордов делят такт поровну.
        Возвращает список (beat, dur, root, ints, bass)."""
        out = []
        for i, bar in enumerate(prog):
            parts = bar.split()
            d = self.bpb / len(parts)
            for j, c in enumerate(parts):
                r, ints, bs = parse_chord(c)
                out.append(((bar0 + i) * self.bpb + j * d, d, r, ints, bs))
        return out

    def pad(self, stem, inst, chs, center=62, vel=0.6, pan=0.0, legato=1.02, spread=0.0):
        prev = None
        for beat, d, r, ints, bs in chs:
            notes = voice_chord(r, ints, center, prev)
            prev = notes
            for k, n in enumerate(notes):
                pp = pan + (k - len(notes) / 2) * spread
                self.note(stem, inst, n, beat, d, vel, pp, legato)

    def bassline(self, stem, inst, chs, octave=2, pattern=None, vel=0.75, pan=0.0, fifth=False):
        for beat, d, r, ints, bs in chs:
            base = 12 * (octave + 1) + bs
            if pattern is None:
                self.note(stem, inst, base, beat, d, vel, pan)
            else:
                for (off, dd, kind) in pattern:
                    if off >= d:
                        continue
                    n = base
                    if kind == 5:
                        n = 12 * (octave + 1) + (r + 7) % 12
                        if n < base:
                            n += 12
                    elif kind == 8:
                        n = base + 12
                    self.note(stem, inst, n, beat + off, min(dd, d - off), vel, pan)

    def arp(self, stem, inst, chs, pattern, step=0.5, center=60, vel=0.55, pan=0.0, legato=1.6):
        prev = None
        for beat, d, r, ints, bs in chs:
            notes = voice_chord(r, ints, center, prev)
            prev = notes
            ext = [notes[0] - 12] + notes + [n + 12 for n in notes]
            nsteps = int(round(d / step))
            for i in range(nsteps):
                idx = pattern[i % len(pattern)]
                if idx is None:
                    continue
                n = ext[idx % len(ext)]
                self.note(stem, inst, n, beat + i * step, step, vel * (1.0 if i % 4 == 0 else 0.85), pan, legato)

    def drums(self, stem, inst, pattern, bar0, bars, steps=16, m=40, vel=0.8, pan=0.0, accent_vel=1.0):
        st = self.bpb / steps
        for b in range(bars):
            for i, ch in enumerate(pattern):
                if ch == '.' or ch == ' ':
                    continue
                v = vel * (accent_vel if ch == 'X' else (0.6 if ch == 'o' else 1.0))
                self.note(stem, inst, m, (bar0 + b) * self.bpb + i * st, st, v, pan)

    def render(self):
        mix = np.zeros((2, self.total), F32)
        send = np.zeros((2, self.total), F32)
        for name, st in self.stems.items():
            buf = st['buf']
            if not buf.any():
                continue
            if st['eq'] != 'none':
                buf = fft_eq(buf, EQS[st['eq']])
            buf *= st['gain']
            mix += buf
            if st['send'] > 0:
                send += buf * st['send']
        wet = fft_convolve_stereo(send, get_ir())
        mix = mix + wet * 0.9
        if self.loop:
            mix[:, :self.tail] += mix[:, self.length:self.length + self.tail]
            mix = mix[:, :self.length]
        else:
            n = mix.shape[1]
            fade = np.ones(n, F32)
            fl = int(0.5 * SR)
            fade[-fl:] = np.linspace(1, 0, fl)
            mix *= fade
        mix -= mix.mean(axis=1, keepdims=True)
        rms = math.sqrt(float(np.mean(mix ** 2)) + 1e-12)
        mix *= 0.16 / rms
        drive = 1.4
        mix = np.tanh(mix * drive) / math.tanh(drive)
        peak = float(np.max(np.abs(mix)))
        if peak > 0.97:
            mix *= 0.97 / peak
        return (mix.T * 32767).astype(np.int16)

def write_wav(path, data):
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(np.ascontiguousarray(data).tobytes())

# ==================================================================
#  КОМПОЗИЦИИ (оригинальная музыка, написанная нотами)
# ==================================================================
def _timp_roll(s, stem, m, beat0, beats, v0=0.2, v1=0.9, rate=0.25):
    n = int(beats / rate)
    for i in range(n):
        s.note(stem, 'timpani', m, beat0 + i * rate, rate, lerp(v0, v1, i / max(1, n - 1)) * 0.7, 0.1)

def _strum(s, stem, inst, chs, offsets, center=57, vel=0.4, pan=-0.3, spread=0.03):
    prev = None
    for beat, d, r, ints, bs in chs:
        notes = voice_chord(r, ints, center, prev)
        prev = notes
        for off in offsets:
            if off >= d:
                continue
            for k, n in enumerate(notes):
                s.note(stem, inst, n, beat + off + k * spread, 0.5, vel * (0.85 + 0.15 * (k == 0)), pan)

def song_title():
    s = Song(bpm=104, bpb=4, bars=32)
    s.stem('str', 0.35, 'strings', 0.55)
    s.stem('lead', 0.38, 'strings', 1.0)
    s.stem('brass', 0.3, 'brass', 0.55)
    s.stem('choir', 0.5, 'choir', 0.45)
    s.stem('harp', 0.35, 'warm', 0.6)
    s.stem('bass', 0.2, 'bass', 0.8)
    s.stem('perc', 0.18, 'drums', 0.9)
    intro = ["D", "D", "G", "A"]
    A = ["D", "Bm", "G", "A", "D", "F#m", "G A", "D"]
    B = ["G", "A", "F#m", "Bm", "Em", "A", "D/F# G", "Asus4 A"]
    coda = ["D", "G", "A", "D"]
    prog = intro + A + B + A + coda
    chs = s.chords(prog)
    # струнный пэд всё время
    s.pad('str', 'strings_slow', chs, center=62, vel=0.5, spread=0.15)
    # бас
    s.bassline('bass', 'bass', chs, octave=2, pattern=[(0, 2, 0), (2, 2, 5)], vel=0.6)
    # вступление: литавры + валторны
    _timp_roll(s, 'perc', nm('D2'), 0, 7.5, 0.15, 1.0)
    s.note('perc', 'swell', 60, 4, 3.8, 0.8)
    call = "D4/1.5 A4/.5 D5/2  E5/1 F#5/.5 E5/.5 D5/1 A4/1  B4/1.5 C#5/.5 D5/1 E5/1  A4/4"
    s.line('brass', 'horn', call, 0, vel=0.75, pan=0.25)
    s.line('brass', 'horn', call, 0, vel=0.5, pan=0.3, tr=-12)
    s.note('perc', 'cymbal', 60, 16, 2, 0.9)
    # тема A: соло валторн + арфа
    themeA = ("A4/1 D5/1 F#5/1.5 E5/.5  D5/1 B4/1 F#4/2  G4/.5 A4/.5 B4/1 D5/1 G5/1  F#5/1.5 E5/.5 E5/2  "
              "A4/1 D5/1 F#5/1.5 A5/.5  A5/1 G5/.5 F#5/.5 C#5/2  B4/.5 C#5/.5 D5/1 E5/.5 F#5/.5 G5/1  D5/3 A4/1")
    s.line('brass', 'horn', themeA, 16, vel=0.8, pan=0.2)
    s.arp('harp', 'harp', s.chords(A, 4), [0, 1, 2, 3, 4, 5, 4, 3], step=0.5, center=60, vel=0.5, pan=-0.4)
    for b in range(4, 12):
        s.note('perc', 'timpani', 12 * 3 + parse_chord(prog[b].split()[0])[2] + (0 if parse_chord(prog[b].split()[0])[2] < 7 else -12), b * 4, 1, 0.5)
    # тема B: струнные поют
    themeB = ("B5/1.5 A5/.5 G5/1 D5/1  E5/1.5 F#5/.5 E5/1 C#5/1  F#5/1.5 E5/.5 C#5/1 A4/1  D5/1 F#5/1 B5/2  "
              "G5/1.5 F#5/.5 E5/1 G5/1  A5/1 G5/.5 F#5/.5 E5/2  F#5/1 A5/1 B5/1 D6/1  D6/2 C#6/2")
    s.line('lead', 'strings_lead', themeB, 48, vel=0.8, pan=-0.15)
    s.line('lead', 'strings_lead', themeB, 48, vel=0.55, pan=0.15, tr=-12)
    s.pad('brass', 'horn', s.chords(B, 12), center=58, vel=0.35)
    s.pad('choir', 'choir', s.chords(B[4:], 16), center=64, vel=0.5)
    s.arp('harp', 'harp', s.chords(B, 12), [0, 2, 3, 4, 5, 6, 5, 4], step=0.5, center=62, vel=0.45, pan=-0.4)
    s.note('perc', 'swell', 60, 76, 4, 0.9)
    # тема A': тутти
    s.note('perc', 'cymbal', 60, 80, 2, 1.0)
    s.line('lead', 'strings_lead', themeA, 80, vel=0.85, pan=-0.2, tr=12)
    s.line('brass', 'trumpet', themeA, 80, vel=0.8, pan=0.25)
    s.line('brass', 'horn', themeA, 80, vel=0.6, pan=0.3, tr=-12)
    s.pad('choir', 'choir', s.chords(A, 20), center=62, vel=0.6)
    s.drums('perc', 'snare', "X..o..o.X.o.o..o", 20, 8, vel=0.35)
    for b in range(20, 28):
        s.note('perc', 'timpani', nm('D2') if b % 2 == 0 else nm('A2'), b * 4, 1, 0.7)
    s.arp('harp', 'harp', s.chords(A, 20), [0, 1, 2, 3, 4, 5, 6, 5], step=0.5, center=64, vel=0.4, pan=-0.45)
    # кода
    coda_m = "D5/1 F#5/1 A5/2  B5/1.5 A5/.5 G5/2  E5/1 F#5/.5 G5/.5 A5/2  D6/4"
    s.line('brass', 'trumpet', coda_m, 112, vel=0.85, pan=0.2)
    s.line('lead', 'strings_lead', coda_m, 112, vel=0.8, pan=-0.2)
    s.line('brass', 'horn', coda_m, 112, vel=0.6, tr=-12)
    s.pad('choir', 'choir', s.chords(coda, 28), center=64, vel=0.65)
    _timp_roll(s, 'perc', nm('D2'), 120, 4, 0.3, 1.0)
    s.note('perc', 'cymbal', 60, 124, 2, 1.0)
    return s

def song_sea():
    s = Song(bpm=210, bpb=6, bars=32)
    s.stem('fid', 0.3, 'fiddle', 1.0)
    s.stem('flute', 0.35, 'warm', 0.75)
    s.stem('acc', 0.25, 'accordion', 0.55)
    s.stem('gtr', 0.25, 'warm', 0.4)
    s.stem('bass', 0.15, 'bass', 0.55)
    s.stem('perc', 0.12, 'drums', 0.8)
    s.stem('str', 0.35, 'strings', 0.35)
    A = ["G", "C", "G", "D", "G", "C", "D", "G"]
    B = ["Em", "C", "G", "D", "Em", "C", "D", "G"]
    prog = A + B + A + B
    chs = s.chords(prog)
    melA = ("D5/2 B4/1 G4/2 B4/1  C5/2 E5/1 G5/2 E5/1  D5/2 B4/1 D5/1 C5/1 B4/1  A4/3 D5/3  "
            "B4/2 D5/1 G5/2 F#5/1  E5/2 G5/1 E5/2 C5/1  D5/1 E5/1 D5/1 C5/2 A4/1  G4/5 D5/1")
    melB = ("E5/2 G5/1 B5/2 G5/1  A5/2 G5/1 E5/2 C5/1  D5/2 G5/1 B5/2 A5/1  A5/3 F#5/2 D5/1  "
            "G5/2 F#5/1 E5/2 B4/1  C5/2 E5/1 G5/2 E5/1  F#5/2 E5/1 D5/1 E5/1 F#5/1  G5/6")
    s.line('fid', 'fiddle', melA, 0, vel=0.75, pan=-0.2, humanize=0.02)
    s.line('acc', 'accordion', melB, 48, vel=0.7, pan=0.25)
    s.line('fid', 'fiddle', melB, 48, vel=0.5, pan=-0.2, tr=-12)
    s.line('flute', 'flute', melA, 96, vel=0.75, pan=0.3)
    s.line('fid', 'fiddle', melA, 96, vel=0.7, pan=-0.2, tr=-12)
    s.line('fid', 'fiddle', melB, 144, vel=0.8, pan=-0.2)
    s.line('flute', 'flute', melB, 144, vel=0.7, pan=0.3, tr=12)
    # гитара: бум-чк-чк
    s.bassline('bass', 'pizz', chs, octave=2, pattern=[(0, 1, 0), (3, 1, 5)], vel=0.8)
    _strum(s, 'gtr', 'guitar', chs, [1, 2, 4, 5], center=57, vel=0.32, pan=-0.35, spread=0.04)
    # аккордеон-пульс
    for beat, d, r, ints, bs in chs:
        if beat >= 48:
            notes = voice_chord(r, ints, 64)
            for n in notes:
                s.note('acc', 'accordion', n, beat, 2.6, 0.38, 0.3)
                s.note('acc', 'accordion', n, beat + 3, 2.6, 0.3, 0.3)
    s.pad('str', 'strings_slow', s.chords(B, 8), center=60, vel=0.4)
    s.pad('str', 'strings_slow', s.chords(A + B, 16), center=62, vel=0.45)
    s.drums('perc', 'bodhran', "X.oX.o", 0, 32, steps=6, vel=0.7)
    s.drums('perc', 'shaker', "xoxxox", 8, 24, steps=6, vel=0.6)
    s.note('perc', 'cymbal', 60, 96, 2, 0.4)
    return s

def song_island():
    s = Song(bpm=78, bpb=4, bars=32)
    s.stem('pno', 0.35, 'warm', 0.6)
    s.stem('flute', 0.4, 'warm', 0.9)
    s.stem('lead', 0.42, 'strings', 0.75)
    s.stem('str', 0.45, 'strings_dark', 0.4)
    s.stem('cel', 0.5, 'warm', 1.4)
    s.stem('bass', 0.25, 'bass', 0.6)
    s.stem('harp', 0.4, 'warm', 0.5)
    A = ["F", "C/E", "Dm", "Bb", "F", "Am", "Bb", "C"]
    B = ["Dm", "Bb", "F", "C", "Dm", "Gm", "Bb C", "F"]
    prog = A + B + A + B
    chs = s.chords(prog)
    mel = ("A5/1.5 G5/.5 F5/1 C5/1  E5/1.5 F5/.5 G5/2  F5/1 E5/.5 D5/.5 A4/2  Bb4/1 C5/1 D5/1 F5/1  "
           "C6/1.5 Bb5/.5 A5/1 F5/1  G5/1.5 A5/.5 E5/2  D5/1 F5/1 Bb5/1 A5/.5 G5/.5  G5/3 R/1  "
           "F5/1.5 E5/.5 D5/1 A5/1  Bb5/1.5 A5/.5 F5/2  A5/1 C6/1 A5/1 F5/1  G5/1.5 F5/.5 E5/1 C5/1  "
           "D5/1 F5/1 A5/1.5 G5/.5  G5/1 Bb5/1 D6/2  C6/1 Bb5/.5 A5/.5 G5/1 E5/1  F5/4")
    s.line('flute', 'flute', mel, 0, vel=0.7, pan=0.25)
    s.line('lead', 'strings_lead', mel, 64, vel=0.7, pan=-0.15, tr=-12)
    s.line('cel', 'celesta', mel, 64, vel=0.35, pan=0.3)
    s.arp('pno', 'piano', chs, [0, 2, 3, 4, 5, 4, 3, 2], step=0.5, center=55, vel=0.45, pan=-0.1, legato=2.0)
    s.pad('str', 'strings_slow', chs, center=62, vel=0.4, spread=0.1)
    s.bassline('bass', 'pizz', chs, octave=2, pattern=[(0, 1, 0), (2, 1, 5)], vel=0.55)
    s.arp('harp', 'harp', s.chords(B, 24), [0, 1, 2, 3, 4, 5, 6, 7], step=0.25, center=64, vel=0.25, pan=0.4)
    return s

def song_battle():
    s = Song(bpm=150, bpb=4, bars=32)
    s.stem('ost', 0.2, 'strings', 0.8)
    s.stem('lead', 0.3, 'strings', 1.0)
    s.stem('brass', 0.25, 'brass', 0.6)
    s.stem('choir', 0.45, 'choir', 0.42)
    s.stem('bass', 0.12, 'bass', 0.85)
    s.stem('taiko', 0.15, 'drums', 1.0)
    s.stem('perc', 0.15, 'drums', 0.7)
    A = ["Dm", "Bb", "C", "A", "Dm", "Bb", "Gm", "A"]
    B = ["Bb", "F", "C", "Dm", "Bb", "F", "Gm", "A"]
    prog = A + B + A + B
    chs = s.chords(prog)
    # остинато 16-ми
    prev = None
    pat = [0, 0, 1, 0, 2, 0, 1, 0, 0, 0, 1, 0, 2, 0, 1, 2]
    for beat, d, r, ints, bs in chs:
        notes = voice_chord(r, ints, 52, prev)
        prev = notes
        ext = notes + [notes[0] + 12]
        for i in range(int(d / 0.25)):
            s.note('ost', 'strings_short', ext[pat[i % 16] % len(ext)], beat + i * 0.25, 0.25, 0.85 if i % 4 == 0 else 0.6, -0.25)
    s.bassline('bass', 'bass', chs, octave=1, pattern=[(0, 1.5, 0), (1.5, 0.5, 0), (2, 1.5, 0), (3.5, 0.5, 8)], vel=0.75)
    melA = ("D5/1.5 E5/.5 F5/1 A5/1  Bb5/1.5 A5/.5 F5/2  G5/1 E5/1 C5/1 E5/1  A5/2 C#5/1 E5/1  "
            "D5/1.5 E5/.5 F5/1 A5/1  D6/1.5 C6/.5 Bb5/1 A5/1  G5/1 Bb5/1 A5/1 G5/1  A5/2 G5/.5 F5/.5 E5/1")
    melB = ("F5/2 D5/1 F5/1  A5/2 C6/1 A5/1  G5/1.5 F5/.5 E5/1 C5/1  D5/2 E5/1 F5/1  "
            "F5/1 Bb5/1 D6/1.5 C6/.5  C6/1 A5/1 F5/2  G5/1 A5/1 Bb5/1 D6/1  C#6/2 E6/2")
    s.line('brass', 'horn', melA, 0, vel=0.85, pan=0.2, tr=-12)
    s.line('lead', 'strings_lead', melB, 32, vel=0.85, pan=-0.1)
    s.pad('choir', 'choir', s.chords(B, 8), center=62, vel=0.6)
    s.line('brass', 'trumpet', melA, 64, vel=0.85, pan=0.25)
    s.line('brass', 'horn', melA, 64, vel=0.7, pan=0.1, tr=-12)
    s.pad('choir', 'choir', s.chords(A, 16), center=60, vel=0.45)
    s.line('lead', 'strings_lead', melB, 96, vel=0.9, pan=-0.15, tr=12)
    s.line('brass', 'trumpet', melB, 96, vel=0.8, pan=0.2)
    s.line('brass', 'horn', melB, 96, vel=0.6, pan=0.2, tr=-12)
    s.pad('choir', 'choir', s.chords(B, 24), center=64, vel=0.7)
    # стабы меди в B
    for beat, d, r, ints, bs in s.chords(B, 8):
        for n in voice_chord(r, ints, 55):
            s.note('brass', 'horn', n, beat, 0.5, 0.7, 0.2)
            s.note('brass', 'horn', n, beat + 2.5, 0.5, 0.6, 0.2)
    s.drums('taiko', 'taiko', "X..x..X.x.X.x..x", 0, 32, vel=0.85)
    s.drums('taiko', 'taiko_s', "..x...x...x.x.xx", 8, 24, vel=0.6, pan=0.3)
    s.drums('perc', 'snare', "....X.......X..o", 16, 16, vel=0.5)
    for b in range(32):
        s.note('perc', 'timpani', 12 * 2 + parse_chord(prog[b].split()[0])[0], b * 4, 1, 0.6)
    for b in (0, 8, 16, 24):
        s.note('perc', 'cymbal', 60, b * 4, 2, 0.8)
    s.note('perc', 'swell', 60, 28, 4, 0.8)
    s.note('perc', 'swell', 60, 92, 4, 0.8)
    return s

def song_boss():
    s = Song(bpm=138, bpb=4, bars=32)
    s.stem('trem', 0.25, 'strings', 0.55)
    s.stem('lead', 0.32, 'strings', 1.0)
    s.stem('brass', 0.25, 'brass', 0.6)
    s.stem('choir', 0.5, 'choir', 0.5)
    s.stem('bass', 0.12, 'bass', 0.9)
    s.stem('taiko', 0.18, 'drums', 1.0)
    s.stem('perc', 0.18, 'drums', 0.75)
    A = ["Cm", "Ab", "Fm", "G", "Cm", "Db", "Bbm", "G"]
    B = ["Ab", "Eb", "Fm", "G", "Cm", "Ab", "Db", "G"]
    prog = A + B + A + B
    chs = s.chords(prog)
    prev = None
    for beat, d, r, ints, bs in chs:
        notes = voice_chord(r, ints, 57, prev)
        prev = notes
        for i in range(int(d / 0.25)):
            n = notes[(i // 2) % len(notes)] if i % 2 == 0 else notes[-1]
            s.note('trem', 'strings_short', n, beat + i * 0.25, 0.25, 0.7, 0.2 * ((i % 2) * 2 - 1))
    s.bassline('bass', 'bass', chs, octave=1, pattern=[(0, 0.75, 0), (0.75, 0.75, 0), (1.5, 0.5, 0), (2, 0.75, 0), (2.75, 0.75, 8), (3.5, 0.5, 0)], vel=0.8)
    melA = ("C4/1.5 C4/.5 Eb4/1 G4/1  Ab4/2 G4/1 Eb4/1  F4/1.5 G4/.5 Ab4/1 C5/1  B4/2 G4/2  "
            "C5/1.5 Bb4/.5 G4/1 Eb4/1  F4/1 Ab4/1 Db5/2  Db5/1 C5/1 Bb4/1 Ab4/1  G4/3 B4/1")
    melB = ("C6/1.5 Bb5/.5 Ab5/1 G5/1  G5/1.5 F5/.5 Eb5/2  F5/1 Ab5/1 C6/1 Eb6/1  D6/2 B5/2  "
            "C6/1.5 D6/.5 Eb6/1 G6/1  F6/2 Eb6/1 C6/1  Db6/1.5 C6/.5 Bb5/1 Ab5/1  B5/2 G5/2")
    s.line('brass', 'horn', melA, 0, vel=0.9, pan=0.15)
    s.line('brass', 'horn', melA, 0, vel=0.6, pan=0.25, tr=-12)
    s.line('choir', 'choir', melA, 0, vel=0.55, tr=12)
    s.line('lead', 'strings_lead', melB, 32, vel=0.85, pan=-0.15)
    s.line('lead', 'strings_lead', melB, 32, vel=0.6, pan=0.15, tr=-12)
    s.pad('choir', 'choir', s.chords(B, 8), center=64, vel=0.7)
    for beat, d, r, ints, bs in s.chords(B, 8):
        for n in voice_chord(r, ints, 53):
            s.note('brass', 'brass', n, beat, 0.75, 0.75, 0.2)
    s.line('brass', 'trumpet', melA, 64, vel=0.9, pan=0.2, tr=12)
    s.line('brass', 'horn', melA, 64, vel=0.8, pan=0.1)
    s.line('choir', 'choir', melA, 64, vel=0.7, tr=12)
    s.line('lead', 'strings_lead', melB, 96, vel=0.9, pan=-0.15)
    s.line('brass', 'trumpet', melB, 96, vel=0.75, pan=0.2, tr=-12)
    s.pad('choir', 'choir', s.chords(B, 24), center=64, vel=0.75)
    s.pad('brass', 'horn', s.chords(B, 24), center=55, vel=0.55)
    s.drums('taiko', 'taiko', "X.x.X..xX.x.X.xx", 0, 32, vel=0.9)
    s.drums('taiko', 'taiko_s', "x.xxx.xxx.xxx.xx", 16, 16, vel=0.4, pan=-0.3)
    s.drums('perc', 'snare', "....X..o....X.oo", 8, 24, vel=0.5)
    for b in range(32):
        s.note('perc', 'timpani', 12 * 2 + parse_chord(prog[b].split()[0])[0], b * 4, 1, 0.75)
        s.note('perc', 'timpani', 12 * 2 + parse_chord(prog[b].split()[0])[0], b * 4 + 2.5, 1, 0.5)
    for b in (0, 8, 16, 24):
        s.note('perc', 'cymbal', 60, b * 4, 2, 0.9)
    s.note('perc', 'swell', 60, 60, 4, 0.9)
    s.note('perc', 'swell', 60, 124, 4, 0.9)
    return s

def song_sad():
    s = Song(bpm=66, bpb=4, bars=32)
    s.stem('pno', 0.4, 'warm', 0.9)
    s.stem('lead', 0.45, 'strings', 0.7)
    s.stem('str', 0.5, 'strings_dark', 0.45)
    s.stem('bass', 0.3, 'bass', 0.55)
    P = ["Am", "F", "C", "G", "Am", "F", "Dm E", "Am", "F", "G", "Em", "Am", "F", "G", "E", "Am"]
    prog = P + P
    chs = s.chords(prog)
    mel = ("E5/1 A5/1 B5/1 C6/1  C6/1.5 A5/.5 F5/2  G5/1 E5/1 G5/1 C6/1  B5/2 D5/2  "
           "E5/1 A5/1 B5/1 C6/1  D6/1.5 C6/.5 A5/2  F5/1 A5/1 G#5/1 B5/1  A5/4  "
           "C6/1.5 B5/.5 A5/1 F5/1  D6/1.5 C6/.5 B5/1 G5/1  B5/1 E6/1 D6/1 B5/1  C6/2 A5/2  "
           "A5/1 C6/1 F6/1.5 E6/.5  D6/1 B5/1 G5/2  G#5/1 B5/1 E6/1 D6/1  C6/2 A5/2")
    s.line('pno', 'piano', mel, 0, vel=0.7, tr=-12)
    s.arp('pno', 'piano', chs, [0, 2, 3, 4, 3, 2, 1, 2], step=0.5, center=50, vel=0.38, legato=2.5)
    s.line('pno', 'piano', mel, 64, vel=0.6)
    s.line('lead', 'strings_lead', mel, 64, vel=0.75, pan=-0.1, tr=-12)
    s.pad('str', 'strings_slow', s.chords(P, 16), center=60, vel=0.45, spread=0.12)
    s.pad('str', 'strings_slow', s.chords(P[8:], 8), center=57, vel=0.25)
    s.bassline('bass', 'bass', s.chords(P, 16), octave=2, vel=0.5)
    return s

def song_victory():
    s = Song(bpm=118, bpb=4, bars=4, loop=False, tail=2.8)
    s.stem('brass', 0.3, 'brass', 1.0)
    s.stem('str', 0.4, 'strings', 0.7)
    s.stem('perc', 0.2, 'drums', 0.9)
    s.stem('choir', 0.5, 'choir', 0.5)
    prog = ["D", "G A", "D", "D"]
    chs = s.chords(prog)
    mel = "A4/.5 D5/.5 F#5/.5 A5/2.5  B5/1 G5/1 A5/1 C#6/1  D6/4"
    s.line('brass', 'trumpet', mel, 0, vel=0.9, pan=0.2)
    s.line('brass', 'horn', mel, 0, vel=0.7, tr=-12)
    s.line('str', 'strings_lead', mel, 0, vel=0.7, pan=-0.2, tr=12)
    s.pad('str', 'strings', chs[:4], center=62, vel=0.6)
    s.pad('choir', 'choir', chs[1:4], center=64, vel=0.6)
    s.drums('perc', 'snare', "XoXoXoXoXoXoXXXX", 0, 1, vel=0.4)
    _timp_roll(s, 'perc', nm('A2'), 4, 3.5, 0.3, 0.9)
    s.note('perc', 'timpani', nm('D2'), 8, 2, 1.0)
    s.note('perc', 'cymbal', 60, 8, 2, 1.0)
    return s

def song_wano():
    s = Song(bpm=92, bpb=4, bars=32)
    s.stem('shaku', 0.45, 'warm', 0.8)
    s.stem('koto', 0.35, 'warm', 0.7)
    s.stem('sham', 0.25, 'warm', 1.3)
    s.stem('str', 0.45, 'strings_dark', 0.45)
    s.stem('lead', 0.4, 'strings', 0.65)
    s.stem('taiko', 0.2, 'drums', 1.0)
    s.stem('bass', 0.2, 'bass', 0.6)
    A = ["Am", "F", "Am", "E5", "Am", "F", "F E5", "Am"]
    B = ["Am", "F", "Am", "E5", "F", "Am", "F E5", "E5"]
    prog = A + B + A + B
    chs = s.chords(prog)
    melA = ("E5/1 F5/.5 E5/.5 C5/1 B4/1  A4/2 B4/1 C5/1  E5/1.5 F5/.5 A5/1 B5/1  A5/2 F5/1 E5/1  "
            "C6/1 B5/.5 A5/.5 F5/1 E5/1  F5/1 E5/1 C5/1 B4/1  A4/1 B4/.5 C5/.5 E5/1 F5/1  E5/4")
    melB = ("A5/.5 B5/.5 C6/1 B5/.5 A5/.5 F5/1  E5/.5 F5/.5 A5/1 F5/1 E5/1  C5/.5 E5/.5 F5/1 A5/1 B5/1  C6/2 B5/2  "
            "A5/.5 B5/.5 C6/1 E6/1 C6/1  B5/1 A5/1 F5/1 E5/1  F5/1 A5/.5 F5/.5 E5/1 C5/1  B4/2 E5/2")
    s.line('shaku', 'shakuhachi', melA, 0, vel=0.75, pan=0.15)
    s.line('koto', 'koto', melB, 32, vel=0.8, pan=-0.2)
    s.line('sham', 'shamisen', melB, 32, vel=0.5, pan=0.3, tr=-12)
    s.line('shaku', 'shakuhachi', melA, 64, vel=0.8, pan=0.15)
    s.line('lead', 'strings_lead', melA, 64, vel=0.55, pan=-0.2, tr=-12)
    s.line('koto', 'koto', melB, 96, vel=0.85, pan=-0.2)
    s.line('lead', 'strings_lead', melB, 96, vel=0.7, pan=0.1)
    s.line('shaku', 'shakuhachi', melB, 96, vel=0.5, pan=0.25, tr=-12)
    s.arp('koto', 'koto', s.chords(A, 0), [0, 1, 2, 3, 2, 1, 3, 4], step=0.5, center=57, vel=0.4, pan=-0.3)
    s.arp('koto', 'koto', s.chords(A, 16), [0, 2, 3, 4, 3, 2, 4, 5], step=0.5, center=57, vel=0.38, pan=-0.3)
    s.pad('str', 'strings_slow', chs, center=57, vel=0.4)
    s.bassline('bass', 'bass', chs, octave=1, vel=0.5)
    s.drums('taiko', 'taiko', "X.......x...x...", 0, 8, vel=0.7)
    s.drums('taiko', 'taiko', "X..x..x.X...x.xx", 8, 24, vel=0.8)
    s.drums('taiko', 'taiko_s', "..x...x...x...xx", 8, 24, vel=0.45, pan=0.3)
    return s

SONGS = {
    'title': song_title, 'sea': song_sea, 'island': song_island, 'battle': song_battle,
    'boss': song_boss, 'sad': song_sad, 'victory': song_victory, 'wano': song_wano,
}

# ==================================================================
#  ЗВУКОВЫЕ ЭФФЕКТЫ + МЕНЕДЖЕР АУДИО
# ==================================================================
def _sfx_t(dur):
    n = int(dur * SR)
    return n, np.arange(n, dtype=F32) / SR

def _noise(n, seed=0):
    return np.random.default_rng(seed).standard_normal(n).astype(F32)

def _hp(x, fc):
    return fft_eq(x, lambda f: g_hp(f, fc, 2))

def _lp(x, fc):
    return fft_eq(x, lambda f: g_lp(f, fc, 2))

def _bp(x, lo, hi):
    return fft_eq(x, lambda f: g_hp(f, lo, 2) * g_lp(f, hi, 2))

def sfx_hit_light():
    n, t = _sfx_t(0.16)
    y = _lp(_noise(n, 1), 3500) * np.exp(-t * 40) * 0.9
    y += np.sin(2 * np.pi * (180 * np.exp(-t * 12) + 60) * t) * np.exp(-t * 28) * 0.9
    return y

def sfx_hit_heavy():
    n, t = _sfx_t(0.45)
    fv = 40 + 140 * np.exp(-t / 0.04)
    y = np.sin(2 * np.pi * phase_from_freq(fv)) * np.exp(-t * 9) * 1.2
    y += _lp(_noise(n, 2), 2500) * np.exp(-t * 18) * 0.8
    y += _hp(_noise(n, 3), 3000) * np.exp(-t * 50) * 0.4
    return np.tanh(y * 1.5)

def sfx_slash():
    n, t = _sfx_t(0.28)
    nz = _noise(n, 4)
    sweep = np.zeros(n, F32)
    seg = n // 8
    for i in range(8):
        a, b = i * seg, min(n, (i + 1) * seg + seg)
        sweep[a:b] += _bp(nz[a:b], 1500 + i * 700, 2500 + i * 1100)[:b - a] * 0.5
    env = np.clip(t / 0.02, 0, 1) * np.exp(-t * 14)
    ring = np.sin(2 * np.pi * 3200 * t) * np.exp(-t * 25) * 0.12
    return sweep * env * 2.0 + ring

def sfx_whoosh():
    n, t = _sfx_t(0.32)
    y = _bp(_noise(n, 5), 400, 2500)
    env = np.sin(np.pi * np.clip(t / 0.32, 0, 1)) ** 2
    return y * env * 1.3

def sfx_explosion():
    n, t = _sfx_t(1.6)
    y = _lp(_noise(n, 6), 900) * np.exp(-t * 2.8) * 2.0
    y += _lp(_noise(n, 7), 4000) * np.exp(-t * 14) * 0.8
    y += np.sin(2 * np.pi * phase_from_freq(30 + 60 * np.exp(-t * 6))) * np.exp(-t * 3) * 1.0
    return np.tanh(y * 1.4)

def sfx_fire():
    n, t = _sfx_t(0.9)
    y = _bp(_noise(n, 8), 200, 3000) * 0.8
    cr = (np.random.default_rng(9).random(n) > 0.9985).astype(F32)
    cr = np.convolve(cr, np.exp(-np.arange(200) / 30.0).astype(F32), mode='same')
    y += _hp(cr * _noise(n, 10), 1500) * 1.5
    env = np.clip(t / 0.08, 0, 1) * np.exp(-t * 2.5)
    return y * env

def sfx_ice():
    n, t = _sfx_t(0.9)
    y = np.zeros(n, F32)
    for i, f in enumerate([2093, 2637, 3136, 4186, 3520]):
        y += np.sin(2 * np.pi * f * t + i) * np.exp(-t * (5 + i * 2)) * 0.25
    y += _hp(_noise(n, 11), 2500) * np.exp(-t * 20) * 0.7
    return y

def sfx_thunder():
    n, t = _sfx_t(2.0)
    y = _hp(_noise(n, 12), 1200) * np.exp(-t * 18) * 1.4
    y += _lp(_noise(n, 13), 400) * (np.exp(-t * 1.6) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))) * 2.0
    return np.tanh(y * 1.3)

def sfx_beam():
    n, t = _sfx_t(0.9)
    fv = 900 - 600 * t
    y = np.sin(2 * np.pi * phase_from_freq(fv)) * 0.4 + np.sin(2 * np.pi * phase_from_freq(fv * 1.5)) * 0.2
    y += _bp(_noise(n, 14), 1500, 6000) * 0.4
    env = np.clip(t / 0.03, 0, 1) * np.exp(-t * 3)
    return y * env

def sfx_quake():
    n, t = _sfx_t(2.0)
    y = _lp(_noise(n, 15), 250) * np.exp(-t * 1.5) * 3.0
    y += np.sin(2 * np.pi * phase_from_freq(28 + 20 * np.exp(-t * 3))) * np.exp(-t * 1.8) * 1.2
    crack = _hp(_noise(n, 16), 2000) * np.exp(-t * 25) * 1.2
    return np.tanh((y + crack) * 1.2)

def sfx_haki():
    n, t = _sfx_t(1.5)
    sw = np.clip(t / 0.35, 0, 1) ** 2
    y = _lp(_noise(n, 17), 1500) * sw * np.exp(-np.maximum(t - 0.35, 0) * 5) * 1.0
    boom = np.sin(2 * np.pi * phase_from_freq(35 + 50 * np.exp(-np.maximum(t - 0.35, 0) * 8)))
    boom *= np.where(t > 0.35, np.exp(-(t - 0.35) * 3), 0)
    return np.tanh((y + boom * 1.4) * 1.3)

def sfx_cannon():
    n, t = _sfx_t(1.0)
    y = np.sin(2 * np.pi * phase_from_freq(40 + 90 * np.exp(-t * 15))) * np.exp(-t * 5) * 1.5
    y += _lp(_noise(n, 18), 1800) * np.exp(-t * 7) * 1.0
    return np.tanh(y * 1.6)

def sfx_splash():
    n, t = _sfx_t(0.8)
    y = _bp(_noise(n, 19), 300, 5000) * np.clip(t / 0.02, 0, 1) * np.exp(-t * 5)
    return y * 1.1

def sfx_coin():
    n, t = _sfx_t(0.4)
    y = np.sin(2 * np.pi * 1975 * t) * np.exp(-t * 9) * 0.4
    y[int(0.07 * SR):] += np.sin(2 * np.pi * 2637 * t[:n - int(0.07 * SR)]) * np.exp(-t[:n - int(0.07 * SR)] * 8) * 0.4
    return y

def sfx_levelup():
    n, t = _sfx_t(1.6)
    y = np.zeros(n, F32)
    for i, m in enumerate([nm('D5'), nm('F#5'), nm('A5'), nm('D6'), nm('F#6')]):
        st = int(i * 0.09 * SR)
        tt = t[:n - st]
        y[st:] += (np.sin(2 * np.pi * mtof(m) * tt) + 0.3 * np.sin(4 * np.pi * mtof(m) * tt)) * np.exp(-tt * 2.5) * 0.25
    return y

def sfx_ui():
    n, t = _sfx_t(0.06)
    return np.sin(2 * np.pi * 1400 * t) * np.exp(-t * 80) * 0.5

def sfx_ui_ok():
    n, t = _sfx_t(0.3)
    return (np.sin(2 * np.pi * 1047 * t) + 0.5 * np.sin(2 * np.pi * 1568 * t)) * np.exp(-t * 12) * 0.35

def sfx_stretch():
    n, t = _sfx_t(0.35)
    fv = 180 + 500 * (t / 0.35) ** 0.6
    y = np.sin(2 * np.pi * phase_from_freq(fv)) * (1 + 0.6 * np.sin(2 * np.pi * 30 * t))
    return y * np.sin(np.pi * t / 0.35) * 0.45

def sfx_block():
    n, t = _sfx_t(0.4)
    y = np.zeros(n, F32)
    for f, a in ((820, 0.4), (1340, 0.3), (2210, 0.25), (3480, 0.15)):
        y += np.sin(2 * np.pi * f * t) * np.exp(-t * 10) * a
    y += _hp(_noise(n, 20), 2000) * np.exp(-t * 60) * 0.6
    return y

def sfx_parry():
    n, t = _sfx_t(0.9)
    y = np.zeros(n, F32)
    for f, a in ((1568, 0.35), (2349, 0.3), (3136, 0.25), (4699, 0.2)):
        y += np.sin(2 * np.pi * f * t) * np.exp(-t * 4) * a
    y += _hp(_noise(n, 21), 3000) * np.exp(-t * 40) * 0.6
    return y

def sfx_ult():
    """оркестровый удар"""
    n, t = _sfx_t(2.2)
    rng = np.random.default_rng(3)
    br = np.zeros(n, F32)
    for m in (nm('D3'), nm('A3'), nm('D4'), nm('F#4'), nm('A4')):
        z = inst_brass(m, int(0.3 * SR), 1.0, rng)
        br[:min(n, len(z))] += z[:min(n, len(z))] * 0.3
    for m in (nm('D4'), nm('A4'), nm('F#5')):
        z = inst_choir(m, int(0.4 * SR), 1.0, rng)
        br[:min(n, len(z))] += z[:min(n, len(z))] * 0.15
    tk = drum_taiko(0, 0, 1.0, rng)
    br[:len(tk)] += tk * 1.2
    cy = drum_cymbal(0, 0, 1.0, rng)
    br[:min(n, len(cy))] += cy[:min(n, len(cy))] * 1.2
    return np.tanh(br * 1.4)

def sfx_crumble():
    n, t = _sfx_t(1.4)
    y = _lp(_noise(n, 22), 600) * np.exp(-t * 2.2) * 1.8
    rng = np.random.default_rng(23)
    for _ in range(14):
        st = int(rng.uniform(0, 1.0) * SR)
        ln = int(0.08 * SR)
        if st + ln < n:
            y[st:st + ln] += _bp(_noise(ln, rng.integers(1000)), 800, 4000) * np.exp(-np.arange(ln) / (0.015 * SR)) * rng.uniform(0.3, 0.9)
    return np.tanh(y * 1.2)

def sfx_eat():
    n, t = _sfx_t(0.5)
    y = np.zeros(n, F32)
    for i in range(3):
        st = int(i * 0.14 * SR)
        ln = int(0.08 * SR)
        y[st:st + ln] += _lp(_noise(ln, 30 + i), 1800) * np.hanning(ln) * 0.8
    return y

def sfx_wind_loop():
    n, t = _sfx_t(4.0)
    y = _bp(_noise(n, 40), 200, 1200) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.25 * t))
    return y * 0.5

def sfx_waves_loop():
    n, t = _sfx_t(6.0)
    y = _lp(_noise(n, 41), 900) * (0.5 + 0.5 * np.sin(2 * np.pi * t / 3.0) ** 2) * 0.8
    y += _hp(_noise(n, 42), 3000) * (np.sin(2 * np.pi * t / 3.0 + 0.8) ** 8) * 0.3
    return y

def sfx_seaking():
    n, t = _sfx_t(1.8)
    fv = 70 + 40 * np.sin(2 * np.pi * 2.5 * t) + 30 * t
    y = saw_blep(phase_from_freq(fv), fv / SR) * 0.6
    y = _lp(y, 900) * np.clip(t / 0.2, 0, 1) * np.exp(-t * 1.2)
    y += _lp(_noise(n, 43), 500) * np.exp(-t * 2) * 0.6
    return np.tanh(y * 2)

def sfx_select():
    n, t = _sfx_t(0.18)
    return np.sin(2 * np.pi * (600 + 1800 * t) * t) * np.exp(-t * 18) * 0.4

def sfx_gong():
    n, t = _sfx_t(3.0)
    y = np.zeros(n, F32)
    for f, a, d in ((110, 0.6, 0.8), (167, 0.4, 1.0), (243, 0.35, 1.3), (331, 0.3, 1.6), (527, 0.2, 2.2)):
        y += np.sin(2 * np.pi * f * t * (1 + 0.002 * np.sin(2 * np.pi * 3 * t))) * np.exp(-t * d) * a
    return y

SFX_GEN = {
    'hit': sfx_hit_light, 'hit_heavy': sfx_hit_heavy, 'slash': sfx_slash, 'whoosh': sfx_whoosh,
    'explosion': sfx_explosion, 'fire': sfx_fire, 'ice': sfx_ice, 'thunder': sfx_thunder,
    'beam': sfx_beam, 'quake': sfx_quake, 'haki': sfx_haki, 'cannon': sfx_cannon,
    'splash': sfx_splash, 'coin': sfx_coin, 'levelup': sfx_levelup, 'ui': sfx_ui, 'ui_ok': sfx_ui_ok,
    'stretch': sfx_stretch, 'block': sfx_block, 'parry': sfx_parry, 'ult': sfx_ult,
    'crumble': sfx_crumble, 'eat': sfx_eat, 'wind': sfx_wind_loop, 'waves': sfx_waves_loop,
    'seaking': sfx_seaking, 'select': sfx_select, 'gong': sfx_gong,
}

def _to_sound(y, stereo_width=0.0):
    y = np.asarray(y, F32)
    peak = float(np.max(np.abs(y))) + 1e-9
    y = y / peak * 0.9
    st = np.stack([y, y], axis=1)
    return pygame.sndarray.make_sound(np.ascontiguousarray((st * 32767).astype(np.int16)))


class AudioManager:
    def __init__(self):
        self.ok = False
        self.music_ready = False
        self.progress = 0.0
        self.status = "Подготовка..."
        self.music_vol = 0.6
        self.sfx_vol = 0.8
        self.sounds = {}
        self.music_sounds = {}
        self.music_paths = {}
        self.current = None
        self.ch_music = [None, None]
        self.active = 0
        self.ambient = None
        self._last_play = {}
        try:
            pygame.mixer.pre_init(SR, -16, 2, 1024)
            pygame.mixer.init(SR, -16, 2, 1024)
            pygame.mixer.set_num_channels(32)
            pygame.mixer.set_reserved(3)
            self.ch_music = [pygame.mixer.Channel(0), pygame.mixer.Channel(1)]
            self.ch_amb = pygame.mixer.Channel(2)
            self.ok = True
        except Exception as e:
            print("Аудио недоступно:", e)
            self.ok = False

    def start_generation(self):
        th = threading.Thread(target=self._generate, daemon=True)
        th.start()

    def _generate(self):
        try:
            names = list(SONGS.keys())
            sfx_names = list(SFX_GEN.keys())
            total = len(names) + 1
            raw = {}
            self.status = "Синтез звуковых эффектов..."
            for i, nmx in enumerate(sfx_names):
                try:
                    raw[nmx] = SFX_GEN[nmx]()
                except Exception as e:
                    print("sfx err", nmx, e)
                self.progress = (i + 1) / len(sfx_names) / total
            self._raw_sfx = raw
            for i, name in enumerate(names):
                path = os.path.join(SAVE_DIR, f"music_{name}_v{MUSIC_VER}.wav")
                self.music_paths[name] = path
                if not os.path.exists(path):
                    self.status = f"Оркестр записывает: «{TRACK_TITLES.get(name, name)}»..."
                    song = SONGS[name]()
                    data = song.render()
                    tmp = path + ".tmp"
                    write_wav(tmp, data)
                    os.replace(tmp, path)
                self.progress = (i + 2) / total
            self.status = "Готово!"
            self.music_ready = True
        except Exception:
            traceback.print_exc()
            self.status = "Ошибка генерации музыки (игра продолжится без неё)"
            self.music_ready = True

    def finalize(self):
        """вызывается из главного потока после генерации"""
        if not self.ok:
            return
        for k, y in getattr(self, '_raw_sfx', {}).items():
            try:
                self.sounds[k] = _to_sound(y)
            except Exception as e:
                print("sound err", k, e)

    def _load_music(self, name):
        if name in self.music_sounds:
            return self.music_sounds[name]
        p = self.music_paths.get(name)
        if not p or not os.path.exists(p):
            return None
        try:
            snd = pygame.mixer.Sound(p)
            self.music_sounds[name] = snd
            return snd
        except Exception as e:
            print("music load err", e)
            return None

    def play_music(self, name, fade=1800, loop=True):
        if not self.ok or not self.music_ready:
            return
        if name == self.current:
            return
        snd = self._load_music(name)
        if snd is None:
            return
        old = self.ch_music[self.active]
        if old.get_busy():
            old.fadeout(fade)
        self.active = 1 - self.active
        ch = self.ch_music[self.active]
        ch.set_volume(self.music_vol)
        ch.play(snd, loops=-1 if loop else 0, fade_ms=fade)
        self.current = name

    def stop_music(self, fade=1000):
        if not self.ok:
            return
        for ch in self.ch_music:
            ch.fadeout(fade)
        self.current = None

    def set_music_volume(self, v):
        self.music_vol = clamp(v, 0, 1)
        if self.ok:
            for ch in self.ch_music:
                ch.set_volume(self.music_vol)

    def play(self, name, vol=1.0, pan=0.0, cooldown=0.03):
        if not self.ok:
            return
        snd = self.sounds.get(name)
        if snd is None:
            return
        now = time.time()
        if now - self._last_play.get(name, 0) < cooldown:
            return
        self._last_play[name] = now
        ch = pygame.mixer.find_channel()
        if ch is None:
            return
        v = clamp(vol * self.sfx_vol, 0, 1)
        p = clamp(pan, -1, 1)
        ch.set_volume(v * min(1, 1 - p), v * min(1, 1 + p))
        ch.play(snd)

    def ambient_loop(self, name, vol=0.3):
        if not self.ok:
            return
        snd = self.sounds.get(name)
        if name is None or snd is None:
            self.ch_amb.fadeout(800)
            self.ambient = None
            return
        if self.ambient == name:
            return
        self.ambient = name
        self.ch_amb.set_volume(vol * self.sfx_vol)
        self.ch_amb.play(snd, loops=-1, fade_ms=800)

TRACK_TITLES = {
    'title': 'Великий Путь', 'sea': 'Попутный ветер', 'island': 'Остров надежды', 'battle': 'Столкновение воль',
    'boss': 'Император моря', 'sad': 'Память о друзьях', 'victory': 'Победа!', 'wano': 'Земля самураев',
}

# ==================================================================
#  ГРАФИКА: шрифты, текст, свечение, примитивы
# ==================================================================
_FONT_CACHE = {}
_FONT_PATH = None

def _find_font():
    global _FONT_PATH
    if _FONT_PATH is not None:
        return _FONT_PATH
    cands = []
    for name in ("dejavusans", "arial", "liberationsans", "freesans", "helvetica", "verdana", "ubuntu"):
        try:
            p = pygame.font.match_font(name, bold=True)
            if p:
                cands.append(p)
        except Exception:
            pass
    _FONT_PATH = cands[0] if cands else ""
    return _FONT_PATH

def get_font(size, bold=True):
    key = (size, bold)
    f = _FONT_CACHE.get(key)
    if f is None:
        p = _find_font()
        try:
            f = pygame.font.Font(p if p else None, size)
        except Exception:
            f = pygame.font.Font(None, size)
        _FONT_CACHE[key] = f
    return f

_TEXT_CACHE = {}

def render_text(text, size, color=(255, 255, 255), outline=0, ocolor=(0, 0, 0)):
    key = (text, size, color, outline, ocolor)
    s = _TEXT_CACHE.get(key)
    if s is not None:
        return s
    f = get_font(size)
    base = f.render(text, True, color)
    if outline > 0:
        o = f.render(text, True, ocolor)
        w_, h_ = base.get_width() + outline * 2, base.get_height() + outline * 2
        s = pygame.Surface((w_, h_), pygame.SRCALPHA)
        for dx in range(-outline, outline + 1):
            for dy in range(-outline, outline + 1):
                if dx * dx + dy * dy <= outline * outline + 1:
                    s.blit(o, (dx + outline, dy + outline))
        s.blit(base, (outline, outline))
    else:
        s = base
    if len(_TEXT_CACHE) > 3000:
        _TEXT_CACHE.clear()
    _TEXT_CACHE[key] = s
    return s

def draw_text(surf, text, pos, size=20, color=(255, 255, 255), anchor="topleft", outline=2, ocolor=(0, 0, 0), alpha=255):
    s = render_text(str(text), size, color, outline, ocolor)
    r = s.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
    if alpha < 255:
        s = s.copy()
        s.set_alpha(alpha)
    surf.blit(s, r)
    return r

_GLOW_CACHE = {}

def glow_surf(radius, color, intensity=1.0):
    radius = max(2, int(radius))
    key = (radius, color, round(intensity, 2))
    s = _GLOW_CACHE.get(key)
    if s is not None:
        return s
    d = radius * 2
    yy, xx = np.mgrid[0:d, 0:d].astype(np.float32)
    r = np.sqrt((xx - radius + 0.5) ** 2 + (yy - radius + 0.5) ** 2) / radius
    a = np.clip(1 - r, 0, 1) ** 2 * intensity
    arr = np.zeros((d, d, 3), np.float32)
    for i in range(3):
        arr[..., i] = a * color[i]
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    s = pygame.Surface((d, d))
    pygame.surfarray.blit_array(s, arr.transpose(1, 0, 2))
    if len(_GLOW_CACHE) > 1500:
        _GLOW_CACHE.clear()
    _GLOW_CACHE[key] = s
    return s

def _qr(r):
    r = int(r)
    if r < 24:
        return max(2, r & ~1)
    if r < 80:
        return r & ~3
    return r & ~7

def draw_glow(surf, pos, radius, color, intensity=1.0):
    if type(color) is not tuple:
        color = tuple(int(c) for c in color)
    r = _qr(radius)
    if r <= 3:
        pygame.draw.circle(surf, color, (int(pos[0]), int(pos[1])), 2)
        return
    g = glow_surf(r, color, int(intensity * 8) / 8.0)
    surf.blit(g, (pos[0] - r, pos[1] - r), special_flags=pygame.BLEND_ADD)

_SOFT_CACHE = {}

def soft_circle(radius, color, alpha=255):
    radius = _qr(radius)
    key = (radius, color, alpha // 8)
    s = _SOFT_CACHE.get(key)
    if s is not None:
        return s
    d = radius * 2
    yy, xx = np.mgrid[0:d, 0:d].astype(np.float32)
    r = np.sqrt((xx - radius + 0.5) ** 2 + (yy - radius + 0.5) ** 2) / radius
    a = (np.clip(1 - r, 0, 1) ** 1.3 * alpha).astype(np.uint8)
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    s.fill((*color, 0))
    pa = pygame.surfarray.pixels_alpha(s)
    pa[:] = a.T
    del pa
    if len(_SOFT_CACHE) > 1500:
        _SOFT_CACHE.clear()
    _SOFT_CACHE[key] = s
    return s

_SHADOW_CACHE = {}

def shadow_surf(w_, h_, alpha=90):
    key = (int(w_), int(h_), alpha)
    s = _SHADOW_CACHE.get(key)
    if s is None:
        s = pygame.Surface((max(2, int(w_)), max(2, int(h_))), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, alpha), s.get_rect())
        _SHADOW_CACHE[key] = s
    return s

def vgradient(w_, h_, top, bot):
    s = pygame.Surface((w_, h_))
    arr = np.zeros((w_, h_, 3), np.uint8)
    t = np.linspace(0, 1, h_)[None, :, None]
    arr[:] = (np.array(top)[None, None, :] * (1 - t) + np.array(bot)[None, None, :] * t).astype(np.uint8)
    pygame.surfarray.blit_array(s, arr)
    return s

def alpha_rect(surf, rect, color, alpha):
    s = pygame.Surface((max(1, int(rect[2])), max(1, int(rect[3]))), pygame.SRCALPHA)
    s.fill((*color[:3], alpha))
    surf.blit(s, (rect[0], rect[1]))

def alpha_circle(surf, pos, r, color, alpha, width=0):
    r = max(1, int(r))
    s = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
    pygame.draw.circle(s, (*color[:3], alpha), (r + 1, r + 1), r, width)
    surf.blit(s, (pos[0] - r - 1, pos[1] - r - 1))

def alpha_poly(surf, pts, color, alpha):
    if len(pts) < 3:
        return
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    x0, y0 = int(min(xs)) - 1, int(min(ys)) - 1
    w_, h_ = int(max(xs)) - x0 + 2, int(max(ys)) - y0 + 2
    if w_ <= 0 or h_ <= 0 or w_ > 4000 or h_ > 4000:
        return
    s = pygame.Surface((w_, h_), pygame.SRCALPHA)
    pygame.draw.polygon(s, (*color[:3], alpha), [(p[0] - x0, p[1] - y0) for p in pts])
    surf.blit(s, (x0, y0))

def panel(surf, rect, color=(20, 24, 40), alpha=215, border=(220, 190, 120), radius=10, bw=2):
    r = pygame.Rect(rect)
    s = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    pygame.draw.rect(s, (*color, alpha), s.get_rect(), border_radius=radius)
    if border:
        pygame.draw.rect(s, (*border, 255), s.get_rect(), bw, border_radius=radius)
    surf.blit(s, r.topleft)

def bar(surf, rect, frac, col, bg=(30, 30, 40), border=(0, 0, 0), ghost=None, ghost_col=(255, 255, 255)):
    r = pygame.Rect(rect)
    pygame.draw.rect(surf, border, r.inflate(4, 4), border_radius=4)
    pygame.draw.rect(surf, bg, r, border_radius=3)
    if ghost is not None and ghost > frac:
        gw = int(r.w * clamp(ghost, 0, 1))
        pygame.draw.rect(surf, ghost_col, (r.x, r.y, gw, r.h), border_radius=3)
    fw = int(r.w * clamp(frac, 0, 1))
    if fw > 0:
        pygame.draw.rect(surf, col, (r.x, r.y, fw, r.h), border_radius=3)
        hl = add_col(col, 60)
        pygame.draw.rect(surf, hl, (r.x, r.y, fw, max(1, r.h // 3)), border_radius=3)

def oline(surf, col, a, b, w_, ow=2, ocol=(20, 14, 18)):
    pygame.draw.line(surf, ocol, a, b, int(w_ + ow * 2))
    pygame.draw.circle(surf, ocol, (int(a[0]), int(a[1])), int(w_ / 2 + ow))
    pygame.draw.circle(surf, ocol, (int(b[0]), int(b[1])), int(w_ / 2 + ow))
    pygame.draw.line(surf, col, a, b, int(w_))
    pygame.draw.circle(surf, col, (int(a[0]), int(a[1])), int(w_ / 2))
    pygame.draw.circle(surf, col, (int(b[0]), int(b[1])), int(w_ / 2))

def ocircle(surf, col, c, r, ow=2, ocol=(20, 14, 18)):
    pygame.draw.circle(surf, ocol, (int(c[0]), int(c[1])), int(r + ow))
    pygame.draw.circle(surf, col, (int(c[0]), int(c[1])), int(r))

def oellipse(surf, col, rect, ow=2, ocol=(20, 14, 18)):
    r = pygame.Rect(rect)
    pygame.draw.ellipse(surf, ocol, r.inflate(ow * 2, ow * 2))
    pygame.draw.ellipse(surf, col, r)

def opoly(surf, col, pts, ow=2, ocol=(20, 14, 18)):
    if len(pts) < 3:
        return
    pygame.draw.polygon(surf, ocol, pts, 0)
    pygame.draw.lines(surf, ocol, True, pts, ow * 2 + 1)
    pygame.draw.polygon(surf, col, pts, 0)

def orect(surf, col, rect, ow=2, ocol=(20, 14, 18), radius=4):
    r = pygame.Rect(rect)
    pygame.draw.rect(surf, ocol, r.inflate(ow * 2, ow * 2), border_radius=radius + ow)
    pygame.draw.rect(surf, col, r, border_radius=radius)

def star_points(cx, cy, r1, r2, n, rot=0.0, jitter=None):
    pts = []
    for i in range(n * 2):
        a = rot + i * math.pi / n
        r = r1 if i % 2 == 0 else r2
        if jitter:
            r *= jitter[i % len(jitter)]
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    return pts

def berry_text(n):
    return "฿ " + fmt_num(n)

# ------------------------------------------------------------------
#  ПЕРСОНАЖИ (аниме-силуэты, 3/4 сверху)
# ------------------------------------------------------------------
SKIN_TONES = [(255, 224, 189), (241, 194, 150), (224, 172, 125), (198, 134, 90), (141, 85, 54), (95, 60, 40),
              (150, 200, 230), (190, 210, 255), (230, 230, 240)]
HAIR_COLORS = [(25, 20, 20), (90, 50, 25), (160, 100, 40), (240, 210, 110), (210, 50, 40), (240, 240, 245),
               (60, 150, 80), (60, 110, 210), (240, 120, 180), (150, 70, 190), (255, 150, 50), (120, 120, 130)]
CLOTH_COLORS = [(200, 40, 40), (40, 80, 170), (240, 240, 240), (30, 30, 35), (60, 140, 70), (230, 190, 40),
                (150, 60, 160), (230, 120, 40), (80, 160, 200), (120, 80, 50), (240, 150, 190), (100, 100, 110)]
HAIR_STYLES = ["spiky", "messy", "long", "ponytail", "buzz", "afro", "slick", "mohawk", "twin", "bun", "bald", "wild"]
HAT_STYLES = ["none", "straw", "tricorn", "bandana", "cap", "marine_cap", "top_hat", "wide", "headband", "crown", "helmet", "kasa"]
OUTFITS = ["vest", "coat", "suit", "kimono", "marine", "tank", "robe", "armor", "shirt", "jacket"]

def default_app(**kw):
    a = dict(skin=SKIN_TONES[1], hair="spiky", hair_col=HAIR_COLORS[0], outfit="vest", top=CLOTH_COLORS[0],
             bottom=(60, 90, 160), hat="none", hat_col=(230, 200, 90), cape=None, scale=1.0, weapon="none",
             features=(), eye_col=(40, 30, 30), sash=None, fur=None)
    a.update(kw)
    return a

def _dir_of(angle):
    c, s = math.cos(angle), math.sin(angle)
    if s > 0.6:
        return 'd'
    if s < -0.6:
        return 'u'
    return 'r' if c >= 0 else 'l'

def draw_hair(surf, app, hx, hy, r, d, sx, back=False):
    hc = app['hair_col']
    st = app['hair']
    dk = mul_col(hc, 0.7)
    if st == 'bald':
        return
    if back:
        # задний слой: длинные волосы
        if st in ('long', 'wild'):
            pts = [(hx - r * 1.05, hy - r * 0.2), (hx + r * 1.05, hy - r * 0.2), (hx + r * 1.15, hy + r * 1.9),
                   (hx + r * 0.3, hy + r * 1.6), (hx - r * 0.3, hy + r * 1.9), (hx - r * 1.15, hy + r * 1.6)]
            opoly(surf, dk if st == 'long' else hc, [(int(a), int(b)) for a, b in pts])
        elif st == 'ponytail':
            bx = hx - sx * r * 0.9 if d in 'lr' else hx
            by = hy - r * 0.2 if d != 'u' else hy + r * 0.3
            oline(surf, hc, (bx, by), (bx - sx * r * 0.8 if d in 'lr' else bx, by + r * 1.5), r * 0.55)
        elif st == 'twin':
            for k in (-1, 1):
                oline(surf, hc, (hx + k * r * 0.95, hy - r * 0.3), (hx + k * r * 1.3, hy + r * 1.4), r * 0.45)
        return
    if st == 'afro':
        ocircle(surf, hc, (hx, hy - r * 0.5), r * 1.35)
        for i in range(7):
            a = i * 0.9
            pygame.draw.circle(surf, dk, (int(hx + math.cos(a) * r * 0.9), int(hy - r * 0.5 + math.sin(a) * r * 0.9)), int(r * 0.25))
        return
    if st == 'buzz':
        pygame.draw.ellipse(surf, hc, (hx - r, hy - r * 1.02, r * 2, r * 1.15))
        return
    if st == 'bun':
        ocircle(surf, hc, (hx, hy - r * 1.15), r * 0.5)
    # шапка волос
    cap_rect = (hx - r * 1.05, hy - r * 1.12, r * 2.1, r * 1.35)
    if d == 'u':
        cap_rect = (hx - r * 1.05, hy - r * 1.1, r * 2.1, r * 2.05)
    oellipse(surf, hc, cap_rect, 2)
    if st in ('spiky', 'wild', 'mohawk', 'messy'):
        n = 7 if st != 'mohawk' else 4
        for i in range(n):
            if st == 'mohawk':
                a = -math.pi / 2 + (i - 1.5) * 0.18
                ln = r * 1.0
            else:
                a = -math.pi + (i + 0.5) * math.pi / n
                ln = r * (0.75 if st == 'spiky' else (0.55 if st == 'messy' else 1.0))
            bx = hx + math.cos(a) * r * 0.85
            by = hy - r * 0.15 + math.sin(a) * r * 0.85
            tx = hx + math.cos(a) * (r * 0.85 + ln)
            ty = hy - r * 0.15 + math.sin(a) * (r * 0.85 + ln)
            pa = a + math.pi / 2
            w2 = r * 0.32
            pts = [(bx + math.cos(pa) * w2, by + math.sin(pa) * w2), (tx, ty), (bx - math.cos(pa) * w2, by - math.sin(pa) * w2)]
            opoly(surf, hc, [(int(p[0]), int(p[1])) for p in pts], 1)
    if st == 'slick' and d != 'u':
        pygame.draw.arc(surf, dk, (hx - r * 0.9, hy - r * 1.0, r * 1.8, r * 1.2), 0.3, 2.8, 2)
    # чёлка
    if d == 'd' and st not in ('slick', 'buzz', 'bald'):
        for i in range(-2, 3):
            px_ = hx + i * r * 0.38
            pts = [(px_ - r * 0.25, hy - r * 0.55), (px_ + r * 0.25, hy - r * 0.55), (px_ + i * 0.6, hy - r * 0.05)]
            pygame.draw.polygon(surf, hc, [(int(a), int(b)) for a, b in pts])
    elif d in 'lr' and st not in ('slick', 'buzz', 'bald'):
        pts = [(hx + sx * r * 0.2, hy - r * 0.9), (hx + sx * r * 1.0, hy - r * 0.5), (hx + sx * r * 0.55, hy - r * 0.05)]
        pygame.draw.polygon(surf, hc, [(int(a), int(b)) for a, b in pts])

def draw_hat(surf, app, hx, hy, r, d, sx):
    hat = app['hat']
    hc = app.get('hat_col', (230, 200, 90))
    if hat == 'none':
        return
    if hat == 'straw':
        oellipse(surf, (236, 205, 110), (hx - r * 1.65, hy - r * 0.95, r * 3.3, r * 1.15), 2)
        oellipse(surf, (240, 212, 120), (hx - r * 0.95, hy - r * 1.55, r * 1.9, r * 1.2), 2)
        pygame.draw.rect(surf, (200, 30, 30), (hx - r * 0.95, hy - r * 0.95, r * 1.9, r * 0.3))
        for i in range(5):
            pygame.draw.line(surf, (200, 170, 80), (hx - r * 1.3 + i * r * 0.6, hy - r * 0.55), (hx - r * 1.1 + i * r * 0.6, hy - r * 0.35), 1)
    elif hat == 'tricorn':
        pts = [(hx - r * 1.6, hy - r * 0.6), (hx, hy - r * 1.9), (hx + r * 1.6, hy - r * 0.6), (hx, hy - r * 0.8)]
        opoly(surf, hc, [(int(a), int(b)) for a, b in pts])
        pygame.draw.circle(surf, (240, 240, 240), (int(hx), int(hy - r * 1.25)), int(r * 0.3))
    elif hat == 'bandana':
        oellipse(surf, hc, (hx - r * 1.05, hy - r * 1.15, r * 2.1, r * 1.0), 2)
        if d in 'lr':
            oline(surf, hc, (hx - sx * r * 0.9, hy - r * 0.6), (hx - sx * r * 1.6, hy - r * 0.1), r * 0.3, 1)
    elif hat == 'headband':
        pygame.draw.rect(surf, hc, (hx - r * 1.02, hy - r * 0.75, r * 2.04, r * 0.32))
    elif hat in ('cap', 'marine_cap'):
        col = (245, 245, 245) if hat == 'marine_cap' else hc
        oellipse(surf, col, (hx - r * 1.05, hy - r * 1.25, r * 2.1, r * 1.0), 2)
        if d == 'd':
            oellipse(surf, mul_col(col, 0.85), (hx - r * 0.9, hy - r * 0.6, r * 1.8, r * 0.45), 1)
        elif d in 'lr':
            oellipse(surf, mul_col(col, 0.85), (hx + sx * r * 0.2 - r * 0.6, hy - r * 0.62, r * 1.5, r * 0.4), 1)
        if hat == 'marine_cap':
            pygame.draw.circle(surf, (60, 110, 200), (int(hx), int(hy - r * 0.85)), int(r * 0.22))
    elif hat == 'top_hat':
        orect(surf, hc, (hx - r * 0.75, hy - r * 2.3, r * 1.5, r * 1.5), 2, radius=2)
        oellipse(surf, hc, (hx - r * 1.3, hy - r * 1.0, r * 2.6, r * 0.6), 2)
        pygame.draw.rect(surf, (200, 40, 40) if hc[0] < 80 else (20, 20, 20), (hx - r * 0.75, hy - r * 1.2, r * 1.5, r * 0.25))
    elif hat == 'wide':
        oellipse(surf, hc, (hx - r * 2.0, hy - r * 1.0, r * 4.0, r * 1.2), 2)
        oellipse(surf, hc, (hx - r * 0.9, hy - r * 1.7, r * 1.8, r * 1.1), 2)
        pygame.draw.line(surf, (240, 240, 250), (hx + r * 0.6, hy - r * 1.4), (hx + r * 1.8, hy - r * 2.3), 3)
    elif hat == 'crown':
        pts = [(hx - r * 0.9, hy - r * 0.8), (hx - r * 0.9, hy - r * 1.6), (hx - r * 0.45, hy - r * 1.15), (hx, hy - r * 1.75),
               (hx + r * 0.45, hy - r * 1.15), (hx + r * 0.9, hy - r * 1.6), (hx + r * 0.9, hy - r * 0.8)]
        opoly(surf, (250, 210, 60), [(int(a), int(b)) for a, b in pts])
    elif hat == 'helmet':
        oellipse(surf, hc, (hx - r * 1.12, hy - r * 1.3, r * 2.24, r * 1.4), 2)
        pygame.draw.line(surf, mul_col(hc, 0.6), (hx, hy - r * 1.3), (hx, hy - r * 0.2), 2)
    elif hat == 'kasa':
        pts = [(hx - r * 2.0, hy - r * 0.5), (hx, hy - r * 1.7), (hx + r * 2.0, hy - r * 0.5)]
        opoly(surf, hc, [(int(a), int(b)) for a, b in pts])

def draw_face(surf, app, hx, hy, r, d, sx, expr='normal'):
    feats = app.get('features', ())
    ec = app.get('eye_col', (40, 30, 30))
    if d == 'u':
        return
    if 'sunglasses' in feats:
        if d == 'd':
            for k in (-1, 1):
                oellipse(surf, (30, 30, 40), (hx + k * r * 0.42 - r * 0.33, hy - r * 0.15, r * 0.66, r * 0.4), 1)
            pygame.draw.line(surf, (30, 30, 40), (hx - r * 0.1, hy), (hx + r * 0.1, hy), 2)
        else:
            oellipse(surf, (30, 30, 40), (hx + sx * r * 0.5 - r * 0.3, hy - r * 0.15, r * 0.6, r * 0.38), 1)
    else:
        eyes = [(-1, 1)] if d in 'lr' else [(-1, 0), (1, 0)]
        for k, _ in eyes:
            if d in 'lr':
                ex = hx + sx * r * 0.5
            else:
                ex = hx + k * r * 0.42
            ey = hy + r * 0.05
            ew, eh = r * 0.36, r * 0.5
            if expr == 'angry' or expr == 'ult':
                eh *= 0.8
            if 'scar_eye' in feats and k == -1 and d == 'd':
                pygame.draw.line(surf, (60, 20, 20), (ex - r * 0.1, ey - r * 0.45), (ex + r * 0.12, ey + r * 0.45), 2)
                pygame.draw.line(surf, (40, 30, 30), (ex - ew / 2, ey), (ex + ew / 2, ey), 2)
                continue
            pygame.draw.ellipse(surf, (255, 255, 255), (ex - ew / 2, ey - eh / 2, ew, eh))
            pygame.draw.ellipse(surf, ec, (ex - ew * 0.32 + (sx * ew * 0.12 if d in 'lr' else 0), ey - eh * 0.35, ew * 0.64, eh * 0.75))
            pygame.draw.circle(surf, (255, 255, 255), (int(ex + ew * 0.1), int(ey - eh * 0.18)), max(1, int(r * 0.07)))
            pygame.draw.ellipse(surf, (20, 14, 18), (ex - ew / 2, ey - eh / 2, ew, eh), 1)
            # брови
            by = ey - eh * 0.75
            if expr in ('angry', 'ult'):
                pygame.draw.line(surf, (30, 20, 20), (ex - ew * 0.6 * (k if d == 'd' else -sx), by - r * 0.12), (ex + ew * 0.6 * (k if d == 'd' else -sx), by + r * 0.05), 2)
            else:
                pygame.draw.line(surf, (30, 20, 20), (ex - ew * 0.5, by), (ex + ew * 0.5, by - r * 0.03), 2)
    # рот
    if 'mouth_cover' in feats:
        pygame.draw.rect(surf, app.get('cape') or (120, 30, 40), (hx - r * 0.9, hy + r * 0.35, r * 1.8, r * 0.7), border_radius=4)
    else:
        mx = hx + (sx * r * 0.35 if d in 'lr' else 0)
        my = hy + r * 0.6
        if expr == 'ult' or 'grin' in feats:
            pygame.draw.ellipse(surf, (255, 255, 255), (mx - r * 0.42, my - r * 0.15, r * 0.84, r * 0.4))
            pygame.draw.ellipse(surf, (20, 14, 18), (mx - r * 0.42, my - r * 0.15, r * 0.84, r * 0.4), 1)
            pygame.draw.line(surf, (20, 14, 18), (mx - r * 0.4, my + r * 0.05), (mx + r * 0.4, my + r * 0.05), 1)
        elif expr == 'hurt':
            pygame.draw.ellipse(surf, (90, 20, 20), (mx - r * 0.15, my - r * 0.1, r * 0.3, r * 0.3))
        else:
            pygame.draw.line(surf, (60, 30, 30), (mx - r * 0.2, my), (mx + r * 0.2, my), 2)
    if 'scar_cheek' in feats and d == 'd':
        pygame.draw.line(surf, (150, 50, 50), (hx - r * 0.55, hy + r * 0.35), (hx - r * 0.25, hy + r * 0.35), 1)
        for i in range(3):
            pygame.draw.line(surf, (150, 50, 50), (hx - r * 0.5 + i * r * 0.12, hy + r * 0.28), (hx - r * 0.5 + i * r * 0.12, hy + r * 0.42), 1)
    if 'stitch' in feats and d != 'u':
        pygame.draw.line(surf, (110, 60, 50), (hx - r * 0.9, hy + r * 0.05), (hx + r * 0.9, hy + r * 0.15), 2)
    if 'scars3' in feats and d == 'd':
        for i in range(3):
            pygame.draw.line(surf, (160, 40, 40), (hx - r * 0.7 + i * r * 0.12, hy - r * 0.45), (hx - r * 0.45 + i * r * 0.12, hy + r * 0.35), 2)
    if 'long_nose' in feats:
        nx = hx + (sx * r * 0.6 if d in 'lr' else 0)
        tip = (nx + (sx * r * 1.3 if d in 'lr' else 0), hy + r * (0.3 if d in 'lr' else 0.55))
        oline(surf, app['skin'], (nx, hy + r * 0.25), tip, r * 0.22, 1)
    if 'red_nose' in feats:
        ocircle(surf, (230, 30, 30), (hx + (sx * r * 0.7 if d in 'lr' else 0), hy + r * 0.3), r * 0.28, 1)
    if 'saw_nose' in feats:
        nx = hx + (sx * r * 0.6 if d in 'lr' else 0)
        tip = (nx + (sx * r * 1.6 if d in 'lr' else 0), hy + r * (0.2 if d in 'lr' else 0.9))
        oline(surf, (180, 190, 200), (nx, hy + r * 0.2), tip, r * 0.3, 1)
    if 'mustache' in feats or 'wb_mustache' in feats:
        big = 'wb_mustache' in feats
        mc = (245, 245, 245) if big else app['hair_col']
        for k in (-1, 1):
            if d in 'lr' and k == -sx:
                continue
            if big:
                pts = [(hx, hy + r * 0.45), (hx + k * r * 0.9, hy + r * 0.5), (hx + k * r * 1.75, hy - r * 0.05),
                       (hx + k * r * 1.2, hy + r * 0.75), (hx, hy + r * 0.68)]
            else:
                pts = [(hx, hy + r * 0.4), (hx + k * r * 0.6, hy + r * 0.5), (hx + k * r * 0.5, hy + r * 0.62), (hx, hy + r * 0.55)]
            opoly(surf, mc, [(int(a), int(b)) for a, b in pts], 1)
    if 'beard' in feats:
        bc = app.get('beard_col', app['hair_col'])
        oellipse(surf, bc, (hx - r * 0.8, hy + r * 0.3, r * 1.6, r * 1.1), 1)
    if 'cigar' in feats and d != 'u':
        cx = hx + (sx * r * 0.5 if d in 'lr' else r * 0.3)
        pygame.draw.line(surf, (120, 70, 40), (cx, hy + r * 0.6), (cx + (sx if d in 'lr' else 1) * r * 0.8, hy + r * 0.45), 3)
        pygame.draw.circle(surf, (255, 120, 40), (int(cx + (sx if d in 'lr' else 1) * r * 0.85), int(hy + r * 0.44)), 2)
    if 'mask_leather' in feats:
        pygame.draw.rect(surf, (30, 25, 30), (hx - r * 0.95, hy - r * 0.4, r * 1.9, r * 1.3), border_radius=5)
        pygame.draw.circle(surf, (255, 200, 60), (int(hx - r * 0.35), int(hy)), 2)
        pygame.draw.circle(surf, (255, 200, 60), (int(hx + r * 0.35), int(hy)), 2)
    if 'makeup' in feats and d == 'd':
        pygame.draw.circle(surf, (230, 230, 240), (int(hx), int(hy + r * 0.6)), int(r * 0.35), 1)

from collections import OrderedDict
_CHAR_CACHE = OrderedDict()
_CACHEABLE_POSES = ('idle', 'walk', 'hurt', 'block')

def draw_character(surf, x, y, app, facing, st):
    key = st.get('ckey')
    if key is None or st.get('z', 0) != 0 or st.get('flash', 0) > 0.05 or st.get('pose', 'idle') not in _CACHEABLE_POSES:
        return _draw_character_raw(surf, x, y, app, facing, st)
    d = _dir_of(facing)
    sx = 1 if (d == 'r' or (d in 'ud' and math.cos(facing) >= 0)) else -1
    walk = 1 if st.get('walk', 0) > 0.1 else 0
    fr = int((st.get('phase', 0) % 6.2832) / 6.2832 * 12)
    tint = st.get('tint')
    tk = (tint[0], round(tint[1], 1)) if tint else None
    s = app.get('scale', 1.0) * st.get('scale_mul', 1.0)
    full = (key, d, sx, st.get('pose'), walk, fr, tk, st.get('arm_col') is not None, st.get('expr'), round(s, 2))
    spr = _CHAR_CACHE.get(full)
    if spr is None:
        w_ = int(120 * s) + 8
        h_ = int(118 * s) + 8
        spr = pygame.Surface((w_, h_), pygame.SRCALPHA)
        st2 = dict(st)
        st2['phase'] = fr / 12 * 6.2832
        st2['walk'] = walk
        st2.pop('ckey', None)
        _draw_character_raw(spr, w_ / 2, h_ - 12 * s, app, facing if True else 0, st2)
        _CHAR_CACHE[full] = spr
        if len(_CHAR_CACHE) > 900:
            _CHAR_CACHE.popitem(last=False)
    else:
        _CHAR_CACHE.move_to_end(full)
    surf.blit(spr, (x - spr.get_width() / 2, y - (spr.get_height() - 12 * s)))

def _draw_character_raw(surf, x, y, app, facing, st):
    """x,y — точка ступней на экране. st: dict(phase, walk, pose, pose_t, z, tint, flash, expr, aim)"""
    s = app.get('scale', 1.0) * st.get('scale_mul', 1.0)
    z = st.get('z', 0)
    d = _dir_of(facing)
    sx = 1 if (d == 'r' or (d in 'ud' and math.cos(facing) >= 0)) else -1
    phase = st.get('phase', 0.0)
    walk = st.get('walk', 0.0)
    pose = st.get('pose', 'idle')
    pt = st.get('pose_t', 0.0)
    flash = st.get('flash', 0)
    tint = st.get('tint')
    feats = app.get('features', ())
    skin = app['skin']
    top = app['top']
    bot = app['bottom']
    if tint is not None:
        k = tint[1]
        skin = lerp_col(skin, tint[0], k)
        top = lerp_col(top, tint[0], k * 0.85)
        bot = lerp_col(bot, tint[0], k * 0.85)
    arm_col = st.get('arm_col') or skin
    if flash > 0:
        skin = lerp_col(skin, (255, 255, 255), flash)
        top = lerp_col(top, (255, 255, 255), flash)
        bot = lerp_col(bot, (255, 255, 255), flash)
        arm_col = lerp_col(arm_col, (255, 255, 255), flash)
    # тень
    sh = shadow_surf(28 * s * max(0.4, 1 - z / 200), 10 * s * max(0.4, 1 - z / 200))
    surf.blit(sh, (x - sh.get_width() / 2, y - sh.get_height() / 2))
    by = y - z
    if pose == 'down':
        # лежит
        oellipse(surf, top, (x - 18 * s, by - 10 * s, 30 * s, 12 * s))
        ocircle(surf, skin, (x + 16 * s * sx, by - 5 * s), 9 * s)
        return
    bob = math.sin(phase * 2) * 1.2 * s if walk < 0.1 else abs(math.sin(phase)) * -2 * s
    lean = 0
    if pose in ('punch', 'heavy', 'kick', 'slash', 'dash'):
        lean = 4 * s * sx * (1 if d in 'lr' else 0)
    if pose == 'hurt':
        lean = -5 * s * sx
    hipy = by - 14 * s + bob * 0.3
    sh_y = by - 33 * s + bob
    cx = x + lean * 0.5
    ow = max(1, int(2 * min(1.6, s)))
    # плащ сзади
    cape = app.get('cape')
    flap = math.sin(phase * 1.3 + 1.0) * 3 * s + walk * 5 * s
    if cape and d != 'u':
        pts = [(cx - 12 * s, sh_y - 1 * s), (cx + 12 * s, sh_y - 1 * s), (cx + 15 * s - sx * flap, by - 3 * s), (cx - 15 * s - sx * flap, by - 3 * s)]
        opoly(surf, cape, [(int(a), int(b)) for a, b in pts], ow)
    # волосы сзади
    hr = 11.5 * s
    hx = cx + lean
    hy = sh_y - hr * 0.95
    draw_hair(surf, dict(app, hair_col=app['hair_col']), hx, hy, hr, d, sx, back=True)
    # ноги
    sw = math.sin(phase) * 5 * s * min(1, walk * 1.5)
    if pose == 'kick':
        kick_ext = math.sin(pt * math.pi) * 18 * s
    else:
        kick_ext = 0
    legw = 6.5 * s
    for k in (-1, 1):
        lx = cx + k * 4.5 * s
        if d in 'lr':
            fx = lx + k * sw + (sx * kick_ext if k == 1 else 0)
            fy = by - (kick_ext * 0.5 if k == 1 else 0)
        else:
            fx = lx
            fy = by - max(0, k * math.sin(phase)) * 4 * s * min(1, walk * 1.5)
        oline(surf, bot, (lx, hipy), (fx, fy - 2 * s), legw, ow)
        oellipse(surf, (40, 30, 30), (fx - 4.5 * s, fy - 4 * s, 9 * s, 5 * s), 1)
    # дальняя рука (за телом)
    aim = st.get('aim', facing)
    ext = 0.0
    if pose in ('punch', 'heavy', 'cast', 'ult'):
        ext = math.sin(clamp(pt, 0, 1) * math.pi) if pose != 'cast' else min(1, pt * 3)
    sl = (cx - 11 * s, sh_y + 2 * s)
    sr = (cx + 11 * s, sh_y + 2 * s)
    armw = 5.5 * s
    def hand_pos(shoulder, extend, side):
        if extend > 0.05:
            ax = math.cos(aim)
            ay = math.sin(aim) * 0.75
            L = 8 * s + 15 * s * extend
            return (shoulder[0] + ax * L, shoulder[1] + ay * L - 2 * s)
        swing = math.sin(phase + (0 if side < 0 else math.pi)) * 4 * s * min(1, walk * 1.5)
        return (shoulder[0] + side * 2 * s + (swing if d in 'lr' else 0), shoulder[1] + 14 * s - (swing * 0.3 if d not in 'lr' else 0))
    if pose == 'block':
        hl = (cx - 4 * s + sx * 8 * s, sh_y - 2 * s)
        hrp = (cx + 4 * s + sx * 8 * s, sh_y - 2 * s)
    else:
        main_is_r = (sx > 0)
        hl = hand_pos(sl, ext if not main_is_r else ext * 0.25, -1)
        hrp = hand_pos(sr, ext if main_is_r else ext * 0.25, 1)
    back_first = d in 'lr'
    if back_first:
        bs, bh = (sl, hl) if sx > 0 else (sr, hrp)
        oline(surf, arm_col if pose not in ('idle', 'walk') or st.get('arm_col') else top, bs, bh, armw, ow)
        ocircle(surf, arm_col, bh, 3.6 * s, 1)
    # торс
    outfit = app['outfit']
    tw = 22 * s if d in 'ud' else 17 * s
    trect = (cx - tw / 2, sh_y - 3 * s, tw, hipy - sh_y + 6 * s)
    if outfit in ('coat', 'marine', 'robe'):
        ccol = (245, 245, 245) if outfit == 'marine' else top
        pts = [(cx - tw / 2 - 1 * s, sh_y - 2 * s), (cx + tw / 2 + 1 * s, sh_y - 2 * s), (cx + tw / 2 + 4 * s - sx * flap * 0.4, by - 4 * s),
               (cx - tw / 2 - 4 * s - sx * flap * 0.4, by - 4 * s)]
        if d != 'u':
            opoly(surf, mul_col(ccol, 0.85), [(int(a), int(b)) for a, b in pts], ow)
    inner = top
    if outfit == 'marine':
        inner = app.get('inner', (60, 90, 160))
    orect(surf, inner, trect, ow, radius=int(6 * s))
    if outfit == 'vest' and d == 'd':
        pygame.draw.rect(surf, skin, (cx - 3 * s, sh_y - 2 * s, 6 * s, hipy - sh_y + 2 * s))
        for i in range(3):
            pygame.draw.circle(surf, (250, 230, 120), (int(cx - 5.5 * s), int(sh_y + 3 * s + i * 5 * s)), max(1, int(1.3 * s)))
    elif outfit == 'suit' and d == 'd':
        pygame.draw.polygon(surf, (240, 240, 240), [(cx - 4 * s, sh_y - 2 * s), (cx + 4 * s, sh_y - 2 * s), (cx, sh_y + 7 * s)])
        pygame.draw.line(surf, app.get('tie', (180, 30, 40)), (cx, sh_y), (cx, sh_y + 10 * s), max(1, int(2.5 * s)))
    elif outfit == 'kimono' and d == 'd':
        pygame.draw.line(surf, mul_col(top, 0.6), (cx - 6 * s, sh_y - 2 * s), (cx + 2 * s, sh_y + 10 * s), max(1, int(2 * s)))
        pygame.draw.line(surf, mul_col(top, 0.6), (cx + 6 * s, sh_y - 2 * s), (cx - 2 * s, sh_y + 10 * s), max(1, int(2 * s)))
    elif outfit == 'tank' and d == 'd':
        pygame.draw.rect(surf, skin, (cx - tw / 2 + 1, sh_y - 3 * s, 4 * s, 6 * s))
        pygame.draw.rect(surf, skin, (cx + tw / 2 - 4 * s - 1, sh_y - 3 * s, 4 * s, 6 * s))
    elif outfit == 'armor':
        pygame.draw.line(surf, mul_col(top, 1.3), (cx - tw / 2 + 2, sh_y + 6 * s), (cx + tw / 2 - 2, sh_y + 6 * s), max(1, int(2 * s)))
        ocircle(surf, mul_col(top, 1.2), (cx - tw / 2, sh_y), 5 * s, 1)
        ocircle(surf, mul_col(top, 1.2), (cx + tw / 2, sh_y), 5 * s, 1)
    elif outfit == 'jacket' and d == 'd':
        pygame.draw.line(surf, mul_col(top, 0.6), (cx, sh_y - 2 * s), (cx, hipy), max(1, int(1.5 * s)))
    if app.get('sash'):
        pygame.draw.rect(surf, app['sash'], (trect[0], hipy - 4 * s, trect[2], 4 * s))
    if outfit == 'marine' and d != 'u':
        # плащ дозорного на плечах
        pts = [(cx - tw / 2 - 3 * s, sh_y - 3 * s), (cx + tw / 2 + 3 * s, sh_y - 3 * s), (cx + tw / 2 + 5 * s, sh_y + 8 * s), (cx - tw / 2 - 5 * s, sh_y + 8 * s)]
        opoly(surf, (248, 248, 248), [(int(a), int(b)) for a, b in pts], ow)
    if outfit == 'marine' and d == 'u':
        pygame.draw.rect(surf, (248, 248, 248), (cx - tw / 2 - 3 * s, sh_y - 3 * s, tw + 6 * s, by - sh_y))
        kx, ky = cx - 6 * s, sh_y + 6 * s
        kc = (40, 40, 70)
        lw = max(1, int(1.2 * s))
        for (x1, y1, x2, y2) in ((0, 0, 5, 0), (2.5, 0, 2.5, 8), (0, 4, 5, 4), (0, 8, 5, 8), (7, 0, 12, 0), (9.5, 0, 9.5, 8), (7, 3, 12, 3), (7, 6, 12, 6), (8, 8, 11, 6)):
            pygame.draw.line(surf, kc, (kx + x1 * s, ky + y1 * s), (kx + x2 * s, ky + y2 * s), lw)
    # мех/крылья/огонь на спине
    if 'wings_fire' in feats or 'lunarian' in feats:
        fl = math.sin(phase * 3) * 3
        for k in (-1, 1):
            pts = [(cx + k * 6 * s, sh_y + 2 * s), (cx + k * 22 * s, sh_y - 12 * s + fl), (cx + k * 14 * s, sh_y + 10 * s)]
            opoly(surf, (255, 140, 40), [(int(a), int(b)) for a, b in pts], 1)
    if 'fin' in feats and d != 'd':
        pts = [(cx - 3 * s, sh_y + 2 * s), (cx, sh_y - 12 * s), (cx + 5 * s, sh_y + 4 * s)]
        opoly(surf, mul_col(skin, 0.8), [(int(a), int(b)) for a, b in pts], 1)
    # ближняя рука
    fs, fh = (sr, hrp) if (not back_first or sx > 0) else (sl, hl)
    if not back_first:
        oline(surf, arm_col if st.get('arm_col') else top, sl, hl, armw, ow)
        ocircle(surf, arm_col, hl, 3.6 * s, 1)
    oline(surf, arm_col if (pose not in ('idle', 'walk') or st.get('arm_col')) else top, fs, fh, armw, ow)
    ocircle(surf, arm_col, fh, 3.8 * s, 1)
    if 'hook' in feats:
        hk = hl if fh is hrp else hrp
        pygame.draw.arc(surf, (240, 200, 60), (hk[0] - 5 * s, hk[1] - 2 * s, 10 * s, 10 * s), 0, 3.5, max(1, int(2 * s)))
    # голова
    if 'fishman' in feats:
        skin_h = skin
    else:
        skin_h = skin
    ocircle(surf, skin_h, (hx, hy), hr, ow)
    if 'mink' in feats or app.get('fur'):
        fc = app.get('fur') or app['hair_col']
        for k in (-1, 1):
            opoly(surf, fc, [(int(hx + k * hr * 0.4), int(hy - hr * 0.8)), (int(hx + k * hr * 1.0), int(hy - hr * 1.7)), (int(hx + k * hr * 1.05), int(hy - hr * 0.4))], 1)
    if 'horns' in feats:
        for k in (-1, 1):
            opoly(surf, (230, 220, 200), [(int(hx + k * hr * 0.35), int(hy - hr * 0.8)), (int(hx + k * hr * 1.2), int(hy - hr * 2.0)), (int(hx + k * hr * 0.8), int(hy - hr * 0.6))], 1)
    expr = st.get('expr', 'normal')
    draw_face(surf, app, hx, hy, hr, d, sx, expr)
    draw_hair(surf, app, hx, hy, hr, d, sx)
    draw_hat(surf, app, hx, hy, hr, d, sx)
    if 'halo_drums' in feats:
        pygame.draw.circle(surf, (240, 200, 80), (int(cx), int(sh_y + 2 * s)), int(20 * s), max(1, int(2 * s)))
        for i in range(4):
            a = phase + i * math.pi / 2
            ocircle(surf, (230, 180, 60), (cx + math.cos(a) * 20 * s, sh_y + 2 * s + math.sin(a) * 20 * s), 4 * s, 1)
    # оружие
    wp = app.get('weapon', 'none')
    if wp != 'none':
        draw_weapon(surf, app, wp, cx, sh_y, by, fh, hl if fh is hrp else hrp, aim, pose, pt, s, d, sx, hx, hy, hr)

def draw_weapon(surf, app, wp, cx, sh_y, by, hand, hand2, aim, pose, pt, s, d, sx, hx, hy, hr):
    blade = app.get('blade_col', (225, 230, 240))
    hilt = (60, 40, 30)
    if wp.startswith('sword'):
        n = int(wp[-1]) if wp[-1].isdigit() else 1
        if pose in ('slash', 'heavy', 'ult', 'punch', 'dash'):
            sw = (pt - 0.5) * 2.4 if pose != 'dash' else 0
            a = aim + sw * (1 if sx > 0 else -1)
            L = 30 * s * app.get('blade_len', 1.0)
            tip = (hand[0] + math.cos(a) * L, hand[1] + math.sin(a) * L * 0.8)
            pygame.draw.line(surf, (20, 14, 18), hand, tip, max(2, int(5 * s)))
            pygame.draw.line(surf, blade, hand, tip, max(1, int(3 * s)))
            if n >= 2:
                a2 = aim - sw * (1 if sx > 0 else -1) * 0.8
                tip2 = (hand2[0] + math.cos(a2) * L, hand2[1] + math.sin(a2) * L * 0.8)
                pygame.draw.line(surf, (20, 14, 18), hand2, tip2, max(2, int(5 * s)))
                pygame.draw.line(surf, blade, hand2, tip2, max(1, int(3 * s)))
            if n >= 3 and d != 'u':
                mx = hx + (sx * hr * 0.4 if d in 'lr' else 0)
                my = hy + hr * 0.6
                tip3 = (mx + math.cos(aim) * L * 0.9, my + math.sin(aim) * L * 0.6)
                pygame.draw.line(surf, (20, 14, 18), (mx, my), tip3, max(2, int(5 * s)))
                pygame.draw.line(surf, (240, 240, 250), (mx, my), tip3, max(1, int(3 * s)))
        else:
            for i in range(n):
                hx0 = cx - sx * (6 + i * 2) * s
                pygame.draw.line(surf, (20, 14, 18), (hx0, by - 16 * s), (hx0 - sx * 18 * s, by - 2 * s + i * 2 * s), max(2, int(4 * s)))
                pygame.draw.line(surf, app.get('sheath_col', (50, 60, 120)) if i == 0 else ((200, 30, 40) if i == 1 else (30, 30, 30)),
                                 (hx0, by - 16 * s), (hx0 - sx * 18 * s, by - 2 * s + i * 2 * s), max(1, int(2.5 * s)))
    elif wp == 'big_sword':
        a = aim if pose in ('slash', 'heavy', 'ult') else -math.pi / 2 - sx * 0.6
        if pose in ('slash', 'heavy', 'ult'):
            a = aim + (pt - 0.5) * 2.4 * sx
        L = 48 * s
        tip = (hand[0] + math.cos(a) * L, hand[1] + math.sin(a) * L * 0.8)
        pygame.draw.line(surf, (20, 14, 18), hand, tip, max(3, int(8 * s)))
        pygame.draw.line(surf, (30, 30, 40), hand, tip, max(2, int(6 * s)))
        pa = a + math.pi / 2
        pygame.draw.line(surf, (200, 170, 60), (hand[0] + math.cos(a) * 8 * s + math.cos(pa) * 7 * s, hand[1] + math.sin(a) * 6 * s + math.sin(pa) * 7 * s),
                         (hand[0] + math.cos(a) * 8 * s - math.cos(pa) * 7 * s, hand[1] + math.sin(a) * 6 * s - math.sin(pa) * 7 * s), max(2, int(3 * s)))
    elif wp in ('club', 'bisento', 'trident', 'axe', 'staff', 'jitte'):
        a = aim + ((pt - 0.5) * 2.0 * sx if pose in ('slash', 'heavy', 'ult', 'punch') else 0)
        if pose in ('idle', 'walk'):
            a = -math.pi / 2 + sx * 0.3
        L = {'club': 42, 'bisento': 55, 'trident': 46, 'axe': 30, 'staff': 40, 'jitte': 24}[wp] * s
        tip = (hand[0] + math.cos(a) * L, hand[1] + math.sin(a) * L * 0.8)
        col = {'club': (70, 60, 60), 'bisento': (120, 80, 40), 'trident': (200, 160, 60), 'axe': (110, 80, 50), 'staff': (130, 90, 50), 'jitte': (80, 80, 90)}[wp]
        oline(surf, col, hand, tip, (8 if wp == 'club' else 4) * s, 1)
        if wp == 'bisento':
            pa = a + math.pi / 2
            pts = [tip, (tip[0] + math.cos(a) * 14 * s + math.cos(pa) * 6 * s, tip[1] + math.sin(a) * 12 * s + math.sin(pa) * 6 * s),
                   (tip[0] + math.cos(a) * 20 * s, tip[1] + math.sin(a) * 16 * s), (tip[0] - math.cos(pa) * 4 * s, tip[1] - math.sin(pa) * 4 * s)]
            opoly(surf, (220, 225, 235), [(int(a_), int(b_)) for a_, b_ in pts], 1)
        elif wp == 'axe':
            ocircle(surf, (190, 190, 200), tip, 8 * s, 1)
        elif wp == 'trident':
            pa = a + math.pi / 2
            for k in (-1, 0, 1):
                b0 = (tip[0] + math.cos(pa) * k * 6 * s, tip[1] + math.sin(pa) * k * 6 * s)
                pygame.draw.line(surf, (220, 200, 90), b0, (b0[0] + math.cos(a) * 10 * s, b0[1] + math.sin(a) * 8 * s), max(1, int(2 * s)))
        elif wp == 'club':
            for i in range(4):
                p_ = (lerp(hand[0], tip[0], 0.5 + i * 0.15), lerp(hand[1], tip[1], 0.5 + i * 0.15))
                pygame.draw.circle(surf, (200, 200, 210), (int(p_[0]), int(p_[1])), max(1, int(2 * s)))
    elif wp in ('gun', 'rifle', 'slingshot'):
        a = aim
        L = (26 if wp == 'rifle' else 14) * s
        tip = (hand[0] + math.cos(a) * L, hand[1] + math.sin(a) * L * 0.8)
        oline(surf, (60, 50, 50) if wp != 'slingshot' else (120, 80, 40), hand, tip, 4 * s, 1)
    elif wp == 'claw':
        for k in (-1, 0, 1):
            pa = aim + k * 0.25
            pygame.draw.line(surf, (230, 230, 240), hand, (hand[0] + math.cos(pa) * 16 * s, hand[1] + math.sin(pa) * 13 * s), max(1, int(2 * s)))
    elif wp == 'clima':
        a = aim if pose != 'idle' else -math.pi / 2 + sx * 0.4
        tip = (hand[0] + math.cos(a) * 28 * s, hand[1] + math.sin(a) * 22 * s)
        oline(surf, (90, 160, 230), hand, tip, 3.5 * s, 1)
        ocircle(surf, (240, 240, 255), tip, 3 * s, 1)

def draw_portrait(surf, rect, app, expr='normal', facing_right=True, bg=None):
    """Крупный портрет (голова и плечи) для диалогов и катсцен."""
    r = pygame.Rect(rect)
    sub = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
    if bg:
        sub.fill((*bg, 255))
    sc = r.h / 70.0
    a2 = dict(app)
    a2['scale'] = sc
    facing = 0.15 if facing_right else math.pi - 0.15
    facing = math.pi / 2 if expr != 'side' else facing
    st = dict(phase=0.5, walk=0, pose='idle', pose_t=0, z=0, expr=expr if expr != 'side' else 'normal')
    draw_character(sub, r.w / 2, r.h * 1.22, a2, facing, st)
    surf.blit(sub, r.topleft)

# ------------------------------------------------------------------
#  ИКОНКИ
# ------------------------------------------------------------------
def draw_fruit_icon(surf, c, r, col, swirl=(255, 255, 255), stem=True):
    ocircle(surf, col, c, r, 2)
    dk = mul_col(col, 0.65)
    for i in range(3):
        a0 = i * 2.1
        pts = []
        for k in range(10):
            t = k / 9
            rr = r * (0.2 + 0.6 * t)
            a = a0 + t * 4.5
            pts.append((c[0] + math.cos(a) * rr, c[1] + math.sin(a) * rr))
        pygame.draw.lines(surf, dk, False, pts, max(1, int(r / 6)))
    pygame.draw.circle(surf, add_col(col, 70), (int(c[0] - r * 0.35), int(c[1] - r * 0.35)), max(1, int(r * 0.2)))
    if stem:
        pygame.draw.line(surf, (60, 120, 40), (c[0], c[1] - r), (c[0] + r * 0.3, c[1] - r * 1.4), max(1, int(r / 5)))
        pygame.draw.ellipse(surf, (70, 160, 60), (c[0] + r * 0.1, c[1] - r * 1.5, r * 0.7, r * 0.35))

def draw_item_icon(surf, c, r, item):
    k = item.get('kind', 'misc')
    col = RARITY_COLORS.get(item.get('rarity', 0), (200, 200, 200))
    pygame.draw.circle(surf, mul_col(col, 0.3), (int(c[0]), int(c[1])), int(r))
    pygame.draw.circle(surf, col, (int(c[0]), int(c[1])), int(r), 2)
    if k == 'sword':
        pygame.draw.line(surf, (230, 230, 240), (c[0] - r * 0.6, c[1] + r * 0.6), (c[0] + r * 0.6, c[1] - r * 0.6), 3)
        pygame.draw.line(surf, (200, 160, 60), (c[0] - r * 0.6, c[1]), (c[0], c[1] + r * 0.6), 3)
    elif k == 'gun':
        pygame.draw.rect(surf, (90, 80, 80), (c[0] - r * 0.6, c[1] - r * 0.2, r * 1.2, r * 0.35))
        pygame.draw.rect(surf, (90, 60, 40), (c[0] - r * 0.6, c[1], r * 0.35, r * 0.5))
    elif k == 'fist':
        ocircle(surf, (200, 200, 210), c, r * 0.5, 1)
    elif k == 'outfit':
        pygame.draw.polygon(surf, (200, 200, 220), [(c[0] - r * 0.6, c[1] - r * 0.4), (c[0] + r * 0.6, c[1] - r * 0.4), (c[0] + r * 0.4, c[1] + r * 0.6), (c[0] - r * 0.4, c[1] + r * 0.6)])
    elif k == 'acc':
        pygame.draw.circle(surf, (240, 210, 90), (int(c[0]), int(c[1])), int(r * 0.45), 3)
    elif k == 'food':
        pygame.draw.circle(surf, (170, 80, 50), (int(c[0] + r * 0.1), int(c[1] - r * 0.1)), int(r * 0.45))
        pygame.draw.line(surf, (240, 240, 230), (c[0] - r * 0.6, c[1] + r * 0.6), (c[0], c[1]), 4)
    elif k == 'fruit':
        draw_fruit_icon(surf, c, r * 0.55, item.get('col', (150, 60, 160)))
    elif k == 'mat':
        pygame.draw.polygon(surf, item.get('col', (160, 160, 170)), [(c[0], c[1] - r * 0.6), (c[0] + r * 0.55, c[1]), (c[0], c[1] + r * 0.6), (c[0] - r * 0.55, c[1])])
    elif k == 'dial':
        ocircle(surf, (230, 220, 190), c, r * 0.5, 1)
        pygame.draw.circle(surf, (150, 120, 90), (int(c[0]), int(c[1])), int(r * 0.2))
    else:
        pygame.draw.circle(surf, (200, 200, 200), (int(c[0]), int(c[1])), int(r * 0.3))

RARITY_COLORS = {0: (190, 190, 190), 1: (110, 200, 110), 2: (90, 150, 255), 3: (190, 100, 255), 4: (255, 170, 40), 5: (255, 60, 80)}
RARITY_NAMES = {0: "Обычный", 1: "Хороший", 2: "Редкий", 3: "Эпический", 4: "Легендарный", 5: "Верховный"}

def make_parchment(w_, h_, seed=1):
    n = value_noise_2d(w_, h_, 40, seed, 4)
    base = np.array([228, 205, 160], np.float32)
    arr = base[None, None, :] * (0.82 + 0.3 * n[..., None])
    yy, xx = np.mgrid[0:h_, 0:w_]
    edge = np.minimum(np.minimum(xx, w_ - 1 - xx), np.minimum(yy, h_ - 1 - yy)).astype(np.float32)
    arr *= np.clip(edge / 25.0, 0.55, 1.0)[..., None]
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    s = pygame.Surface((w_, h_))
    pygame.surfarray.blit_array(s, arr.transpose(1, 0, 2))
    return s

def make_wanted_poster(name, bounty, app, title="", dead_or_alive=True, marine=False):
    w_, h_ = 300, 420
    s = make_parchment(w_, h_, seed=len(name) + 3)
    draw_text(s, "WANTED" if not marine else "ЗАСЛУГИ", (w_ // 2, 18), 50, (60, 35, 20), "midtop", 0)
    pr = pygame.Rect(30, 82, w_ - 60, 190)
    pygame.draw.rect(s, (200, 180, 140), pr)
    draw_portrait(s, pr, app, 'ult' if not marine else 'normal', bg=(210, 190, 150))
    pygame.draw.rect(s, (60, 35, 20), pr, 3)
    draw_text(s, "DEAD OR ALIVE" if not marine else "МОРСКОЙ ДОЗОР", (w_ // 2, 280), 22, (60, 35, 20), "midtop", 0)
    draw_text(s, name.upper(), (w_ // 2, 310), 30 if len(name) < 14 else 22, (50, 30, 15), "midtop", 0)
    btxt = "฿ " + fmt_num(bounty) + " -"
    fs_ = 30 if len(btxt) < 16 else 24
    draw_text(s, btxt, (w_ // 2, 352), fs_, (50, 30, 15), "midtop", 0)
    if title:
        draw_text(s, title, (w_ // 2, 388), 15, (90, 60, 30), "midtop", 0)
    draw_text(s, "MARINE", (w_ // 2, h_ - 4), 10, (110, 80, 45), "midbottom", 0)
    return s

# ==================================================================
#  ЧАСТИЦЫ, ЭФФЕКТЫ, КАМЕРА
# ==================================================================
QUALITY = {'particles': 1.0}

class Particle:
    __slots__ = ("x", "y", "z", "vx", "vy", "vz", "life", "max", "size", "col", "kind", "drag", "grav", "rot", "vr", "grow")
    def __init__(self, x, y, vx, vy, life, size, col, kind, z=0.0, vz=0.0, drag=0.9, grav=0.0, grow=0.0):
        self.x = x; self.y = y; self.z = z
        self.vx = vx; self.vy = vy; self.vz = vz
        self.life = life; self.max = life
        self.size = size; self.col = col; self.kind = kind
        self.drag = drag; self.grav = grav
        self.rot = random.uniform(0, 6.28); self.vr = random.uniform(-8, 8)
        self.grow = grow

class Particles:
    MAX = 2200
    def __init__(self):
        self.ps = []

    def add(self, x, y, vx, vy, life, size, col, kind='glow', z=0.0, vz=0.0, drag=0.9, grav=0.0, grow=0.0):
        if len(self.ps) >= self.MAX * QUALITY['particles']:
            if random.random() < 0.5:
                return
            self.ps.pop(0)
        self.ps.append(Particle(x, y, vx, vy, life, size, col, kind, z, vz, drag, grav, grow))

    def burst(self, x, y, n, col, kind='spark', speed=300, life=0.4, size=3, spread=math.pi * 2, angle=0.0, z=0.0, vz=0.0, grav=0.0, drag=0.88, grow=0.0):
        n = int(n * QUALITY['particles'])
        for _ in range(n):
            a = angle + random.uniform(-spread / 2, spread / 2)
            sp = speed * random.uniform(0.3, 1.0)
            self.add(x, y, math.cos(a) * sp, math.sin(a) * sp, life * random.uniform(0.6, 1.2), size * random.uniform(0.6, 1.3), col, kind,
                     z, vz * random.uniform(0.5, 1.2), drag, grav, grow)

    def update(self, dt):
        alive = []
        for p in self.ps:
            p.life -= dt
            if p.life <= 0:
                continue
            f = p.drag ** (dt * 60)
            p.vx *= f
            p.vy *= f
            p.x += p.vx * dt
            p.y += p.vy * dt
            if p.grav:
                p.vz -= p.grav * dt
                p.z += p.vz * dt
                if p.z < 0:
                    p.z = 0
                    p.vz *= -0.35
                    p.vx *= 0.6
                    p.vy *= 0.6
            elif p.vz:
                p.z += p.vz * dt
            p.rot += p.vr * dt
            if p.grow:
                p.size += p.grow * dt
            alive.append(p)
        self.ps = alive

    def draw(self, surf, ox, oy, layer=None):
        sw, sh = surf.get_size()
        for p in self.ps:
            x = p.x - ox
            y = p.y - oy - p.z
            if x < -80 or y < -80 or x > sw + 80 or y > sh + 80:
                continue
            t = p.life / p.max
            k = p.kind
            if k == 'spark':
                l = 0.035
                ex, ey = x - p.vx * l, y - p.vy * l
                c = lerp_col((255, 255, 255), p.col, 1 - t)
                pygame.draw.line(surf, c, (x, y), (ex, ey), max(1, int(p.size * t + 0.5)))
            elif k == 'glow' or k == 'fire' or k == 'ember':
                r = p.size * (0.4 + 0.6 * t) if k != 'ember' else p.size
                if r < 2.2:
                    pygame.draw.circle(surf, p.col, (int(x), int(y)), 2)
                elif k == 'fire':
                    c = lerp_col(p.col, (120, 30, 10), 1 - t)
                    draw_glow(surf, (x, y), r * 2.2, c, 0.9 * t + 0.1)
                else:
                    draw_glow(surf, (x, y), r * 2, p.col, t)
            elif k == 'smoke' or k == 'dust':
                a = int(150 * t) if k == 'smoke' else int(110 * t)
                sc = soft_circle(int(p.size), p.col, max(8, a))
                surf.blit(sc, (x - sc.get_width() / 2, y - sc.get_height() / 2))
            elif k == 'debris':
                sz = p.size
                ca, sa = math.cos(p.rot), math.sin(p.rot)
                pts = [(x + ca * sz - sa * sz * 0.6, y + sa * sz + ca * sz * 0.6), (x - ca * sz - sa * sz * 0.6, y - sa * sz + ca * sz * 0.6),
                       (x - ca * sz + sa * sz * 0.6, y - sa * sz - ca * sz * 0.6), (x + ca * sz + sa * sz * 0.6, y + sa * sz - ca * sz * 0.6)]
                pygame.draw.polygon(surf, p.col, pts)
                pygame.draw.polygon(surf, mul_col(p.col, 0.5), pts, 1)
            elif k == 'shard':
                sz = p.size
                ca, sa = math.cos(p.rot), math.sin(p.rot)
                pts = [(x + ca * sz * 1.6, y + sa * sz * 1.6), (x - sa * sz * 0.5, y + ca * sz * 0.5), (x + sa * sz * 0.5, y - ca * sz * 0.5)]
                pygame.draw.polygon(surf, p.col, pts)
                pygame.draw.polygon(surf, (255, 255, 255), pts, 1)
            elif k == 'water':
                pygame.draw.circle(surf, p.col, (int(x), int(y)), max(1, int(p.size * (0.5 + 0.5 * t))))
            elif k == 'bubble':
                pygame.draw.circle(surf, p.col, (int(x), int(y)), max(2, int(p.size)), 1)
            elif k == 'petal' or k == 'leaf':
                sz = p.size
                w_ = abs(math.cos(p.rot)) * sz + 1
                pygame.draw.ellipse(surf, p.col, (x - w_, y - sz * 0.5, w_ * 2, sz))
            elif k == 'elec':
                pts = [(x, y)]
                for i in range(3):
                    pts.append((x + random.uniform(-p.size, p.size) * (i + 1), y + random.uniform(-p.size, p.size) * (i + 1)))
                pygame.draw.lines(surf, p.col, False, pts, 2)
            elif k == 'ring':
                r = p.size * (1 - t) + 2
                pygame.draw.circle(surf, p.col, (int(x), int(y)), int(r), max(1, int(3 * t)))
            elif k == 'dark':
                sc = soft_circle(int(p.size * (0.6 + 0.6 * (1 - t))), p.col, int(200 * t))
                surf.blit(sc, (x - sc.get_width() / 2, y - sc.get_height() / 2))
            elif k == 'line':
                ex, ey = x - p.vx * 0.06, y - p.vy * 0.06
                pygame.draw.line(surf, p.col, (x, y), (ex, ey), max(1, int(p.size)))

class FloatText:
    __slots__ = ("x", "y", "text", "col", "life", "max", "size", "vy", "crit")
    def __init__(self, x, y, text, col, size=22, life=0.9, crit=False):
        self.x = x + random.uniform(-34, 34); self.y = y + random.uniform(-18, 10); self.text = text; self.col = col
        self.life = life; self.max = life; self.size = size; self.vy = -90; self.crit = crit

# ---------------- эффекты ----------------
class Effect:
    layer = 1  # 0 под персонажами, 1 над
    def __init__(self, life):
        self.t = 0.0
        self.life = life
    def update(self, dt):
        self.t += dt
        return self.t < self.life
    @property
    def k(self):
        return clamp(self.t / self.life, 0, 1)
    def draw(self, surf, ox, oy):
        pass

class RingFX(Effect):
    def __init__(self, pos, r0, r1, life, col, width=6, add=False, layer=1, squash=0.55):
        super().__init__(life)
        self.pos = V(pos); self.r0 = r0; self.r1 = r1; self.col = col; self.width = width; self.add = add
        self.layer = layer; self.squash = squash
    def draw(self, surf, ox, oy):
        k = ease_out(self.k)
        r = lerp(self.r0, self.r1, k)
        w_ = max(1, int(self.width * (1 - self.k)))
        x, y = self.pos.x - ox, self.pos.y - oy
        rect = pygame.Rect(0, 0, r * 2, r * 2 * self.squash)
        rect.center = (x, y)
        if rect.w < 3:
            return
        c = lerp_col((255, 255, 255), self.col, self.k * 0.7 + 0.3)
        pygame.draw.ellipse(surf, c, rect, min(w_, rect.h // 2 or 1))

class SlashFX(Effect):
    def __init__(self, pos, angle, radius, arc=2.4, life=0.22, col=(200, 220, 255), thick=14, flip=False, core=(255, 255, 255)):
        super().__init__(life)
        self.pos = V(pos); self.a = angle; self.r = radius; self.arc = arc; self.col = col; self.th = thick; self.flip = flip; self.core = core
    def draw(self, surf, ox, oy):
        k = self.k
        sweep = ease_out(min(1, k * 2.2))
        fade = 1 - max(0, (k - 0.35) / 0.65)
        n = 16
        a0 = self.a - self.arc / 2
        a1 = a0 + self.arc * sweep
        if self.flip:
            a0, a1 = self.a + self.arc / 2, self.a + self.arc / 2 - self.arc * sweep
        x, y = self.pos.x - ox, self.pos.y - oy
        th = self.th * fade
        if th < 1:
            return
        outer, inner, core = [], [], []
        for i in range(n + 1):
            t = i / n
            a = lerp(a0, a1, t)
            w_ = math.sin(t * math.pi) * th
            outer.append((x + math.cos(a) * (self.r + w_ * 0.5), y + math.sin(a) * (self.r + w_ * 0.5) * 0.75))
            inner.append((x + math.cos(a) * (self.r - w_ * 0.5), y + math.sin(a) * (self.r - w_ * 0.5) * 0.75))
            core.append((x + math.cos(a) * self.r, y + math.sin(a) * self.r * 0.75))
        pts = outer + inner[::-1]
        if len(pts) >= 3:
            pygame.draw.polygon(surf, self.col, pts)
            pygame.draw.lines(surf, self.core, False, core, max(1, int(th * 0.35)))

class FistFX(Effect):
    """Растягивающаяся рука/нога (Гому-Гому)."""
    def __init__(self, owner, target, life=0.28, col=(240, 200, 160), fist_r=10, sleeve=(200, 40, 40), black=False):
        super().__init__(life)
        self.owner = owner; self.target = V(target); self.col = col; self.fr = fist_r; self.sleeve = sleeve; self.black = black
    def draw(self, surf, ox, oy):
        k = self.k
        ext = math.sin(min(1, k * 1.6) * math.pi / 2) if k < 0.6 else 1 - (k - 0.6) / 0.4
        sp = V(self.owner.pos.x - ox, self.owner.pos.y - oy - 30 * self.owner.scale - self.owner.z)
        tp = V(self.target.x - ox, self.target.y - oy - 22)
        e = sp + (tp - sp) * ext
        col = (35, 30, 40) if self.black else self.col
        oline(surf, col, sp, e, 7, 2)
        ocircle(surf, col, e, self.fr, 2)
        if self.black:
            pygame.draw.circle(surf, (120, 90, 160), (int(e.x - 3), int(e.y - 3)), 3)
        if ext > 0.8:
            for i in range(5):
                a = random.uniform(0, 6.28)
                pygame.draw.line(surf, (255, 255, 255), e + from_angle(a, self.fr + 3), e + from_angle(a, self.fr + 12), 2)

class BeamFX(Effect):
    def __init__(self, start, angle, length, width, life, col, core=(255, 255, 255), owner=None, follow=False):
        super().__init__(life)
        self.start = V(start); self.a = angle; self.len = length; self.w = width; self.col = col; self.core = core
        self.owner = owner; self.follow = follow
    def update(self, dt):
        if self.follow and self.owner is not None:
            self.start = V(self.owner.pos.x, self.owner.pos.y - 20)
            self.a = self.owner.aim
        return super().update(dt)
    def draw(self, surf, ox, oy):
        k = self.k
        grow = min(1, k * 8)
        fade = 1 - max(0, (k - 0.7) / 0.3)
        w_ = self.w * fade * (0.85 + 0.15 * math.sin(self.t * 60))
        if w_ < 1:
            return
        s = V(self.start.x - ox, self.start.y - oy)
        e = s + from_angle(self.a, self.len * grow)
        pygame.draw.line(surf, mul_col(self.col, 0.6), s, e, int(w_ * 1.6) + 2)
        pygame.draw.line(surf, self.col, s, e, int(w_) + 1)
        pygame.draw.line(surf, self.core, s, e, max(1, int(w_ * 0.4)))
        draw_glow(surf, s, w_ * 1.8, self.col, 0.9)
        draw_glow(surf, e, w_ * 1.5, self.col, 0.8)

def jag_points(a, b, segs=8, amp=18):
    pts = [V(a)]
    d = V(b) - V(a)
    L = d.length() or 1
    n = d.normalize().rotate(90) if L > 0 else V(0, 1)
    for i in range(1, segs):
        t = i / segs
        p = V(a) + d * t + n * random.uniform(-amp, amp) * math.sin(t * math.pi)
        pts.append(p)
    pts.append(V(b))
    return pts

class BoltFX(Effect):
    def __init__(self, a, b, col=(160, 200, 255), life=0.3, width=3, amp=22, branches=2, black=False):
        super().__init__(life)
        self.a = V(a); self.b = V(b); self.col = col; self.width = width; self.amp = amp; self.branches = branches
        self.black = black
        self.pts = jag_points(a, b, 9, amp)
        self.rt = 0
        self.br = []
    def update(self, dt):
        self.rt -= dt
        if self.rt <= 0:
            self.rt = 0.04
            self.pts = jag_points(self.a, self.b, 9, self.amp)
            self.br = []
            for _ in range(self.branches):
                p = random.choice(self.pts[1:-1]) if len(self.pts) > 2 else self.a
                self.br.append(jag_points(p, p + from_angle(random.uniform(0, 6.28), random.uniform(20, 60)), 4, 10))
        return super().update(dt)
    def draw(self, surf, ox, oy):
        fade = 1 - self.k
        off = V(ox, oy)
        pts = [p - off for p in self.pts]
        c = self.col
        if self.black:
            pygame.draw.lines(surf, (200, 20, 40), False, pts, int(self.width * 2 + 3))
            pygame.draw.lines(surf, (15, 5, 10), False, pts, int(self.width + 1))
        else:
            pygame.draw.lines(surf, mul_col(c, 0.7), False, pts, int(self.width * 2.5 * fade) + 1)
            pygame.draw.lines(surf, (255, 255, 255), False, pts, max(1, int(self.width * fade)))
        for b in self.br:
            bp = [p - off for p in b]
            pygame.draw.lines(surf, (15, 5, 10) if self.black else c, False, bp, 2)

class ImpactStarFX(Effect):
    """Аниме-вспышка удара."""
    def __init__(self, pos, size=40, life=0.18, col=(255, 240, 160), spikes=9):
        super().__init__(life)
        self.pos = V(pos); self.size = size; self.col = col; self.sp = spikes
        self.rot = random.uniform(0, 6.28)
        self.jit = [random.uniform(0.6, 1.4) for _ in range(spikes * 2)]
    def draw(self, surf, ox, oy):
        k = self.k
        s = self.size * (0.6 + 0.6 * ease_out(k * 2))
        if k > 0.6:
            s *= 1 - (k - 0.6) / 0.4
        if s < 2:
            return
        x, y = self.pos.x - ox, self.pos.y - oy
        pts = star_points(x, y, s, s * 0.35, self.sp, self.rot, self.jit)
        pygame.draw.polygon(surf, (20, 10, 10), star_points(x, y, s * 1.15, s * 0.42, self.sp, self.rot, self.jit))
        pygame.draw.polygon(surf, self.col, pts)
        pygame.draw.polygon(surf, (255, 255, 255), star_points(x, y, s * 0.55, s * 0.2, self.sp, self.rot, self.jit))

class AirCrackFX(Effect):
    """Трещины в воздухе (Гура-Гура)."""
    layer = 2
    def __init__(self, pos, size=120, life=0.8):
        super().__init__(life)
        self.pos = V(pos); self.size = size
        self.lines = []
        for i in range(10):
            a = i * 0.63 + random.uniform(-0.2, 0.2)
            pts = [V(0, 0)]
            p = V(0, 0)
            for j in range(4):
                p = p + from_angle(a + random.uniform(-0.4, 0.4), size * random.uniform(0.15, 0.3))
                pts.append(V(p))
            self.lines.append(pts)
        self.rings = [size * 0.3, size * 0.6]
    def draw(self, surf, ox, oy):
        k = self.k
        fade = 1 - max(0, (k - 0.5) / 0.5)
        grow = ease_out(min(1, k * 5))
        x, y = self.pos.x - ox, self.pos.y - oy
        for pts in self.lines:
            pp = [(x + p.x * grow, y + p.y * grow * 0.8) for p in pts]
            pygame.draw.lines(surf, (180, 200, 255), False, pp, max(1, int(5 * fade)))
            pygame.draw.lines(surf, (255, 255, 255), False, pp, max(1, int(2 * fade)))
        for rr in self.rings:
            r = rr * grow
            if r > 3:
                pts = []
                for i in range(14):
                    a = i / 14 * 6.28
                    rj = r * (0.9 + 0.2 * ((i * 37) % 7) / 7)
                    pts.append((x + math.cos(a) * rj, y + math.sin(a) * rj * 0.8))
                pygame.draw.lines(surf, (230, 240, 255), True, pts, max(1, int(2 * fade)))
        draw_glow(surf, (x, y), self.size * 0.5 * fade + 2, (120, 150, 255), fade)

class TelegraphFX(Effect):
    """Красная зона предупреждения атаки врага."""
    layer = 0
    def __init__(self, shape, life, col=(255, 40, 40), **kw):
        super().__init__(life)
        self.shape = shape; self.col = col; self.kw = kw
    def draw(self, surf, ox, oy):
        k = self.k
        a_fill = int(40 + 70 * k)
        if self.shape == 'circle':
            p = self.kw['pos']
            r = self.kw['r']
            x, y = p.x - ox, p.y - oy
            rect = pygame.Rect(0, 0, r * 2, r * 1.5)
            rect.center = (x, y)
            s = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.ellipse(s, (*self.col, a_fill // 2), s.get_rect())
            ir = s.get_rect().inflate(-(1 - k) * rect.w, -(1 - k) * rect.h)
            pygame.draw.ellipse(s, (*self.col, a_fill), ir)
            pygame.draw.ellipse(s, (*self.col, 220), s.get_rect(), 2)
            surf.blit(s, rect.topleft)
        elif self.shape == 'line':
            a = self.kw['a']
            p = self.kw['pos']
            L = self.kw['len']
            w_ = self.kw['w']
            s0 = V(p.x - ox, p.y - oy)
            d = from_angle(a)
            n = d.rotate(90) * (w_ / 2)
            e = s0 + d * L
            pts = [s0 + n, e + n, e - n, s0 - n]
            alpha_poly(surf, pts, self.col, a_fill // 2)
            e2 = s0 + d * L * k
            alpha_poly(surf, [s0 + n, e2 + n, e2 - n, s0 - n], self.col, a_fill)
        elif self.shape == 'cone':
            a = self.kw['a']
            p = self.kw['pos']
            r = self.kw['r']
            arc = self.kw['arc']
            x, y = p.x - ox, p.y - oy
            pts = [(x, y)]
            for i in range(13):
                aa = a - arc / 2 + arc * i / 12
                pts.append((x + math.cos(aa) * r, y + math.sin(aa) * r * 0.75))
            alpha_poly(surf, pts, self.col, a_fill)

class DomeFX(Effect):
    layer = 0
    def __init__(self, pos, r, life, col=(120, 180, 255), owner=None):
        super().__init__(life)
        self.pos = V(pos); self.r = r; self.col = col; self.owner = owner
    def draw(self, surf, ox, oy):
        k = self.k
        grow = ease_out(min(1, self.t * 4))
        fade = 1 - max(0, (k - 0.9) / 0.1)
        r = self.r * grow
        x, y = self.pos.x - ox, self.pos.y - oy
        rect = pygame.Rect(0, 0, r * 2, r * 1.5)
        rect.center = (x, y)
        if rect.w < 4:
            return
        s = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.ellipse(s, (*self.col, int(35 * fade)), s.get_rect())
        pygame.draw.ellipse(s, (*self.col, int(200 * fade)), s.get_rect(), 3)
        surf.blit(s, rect.topleft)

class AfterImageFX(Effect):
    def __init__(self, fighter, life=0.3, col=(120, 180, 255)):
        super().__init__(life)
        self.col = col
        sc = fighter.app.get('scale', 1.0)
        w_, h_ = int(90 * sc), int(110 * sc)
        self.surf = pygame.Surface((w_, h_), pygame.SRCALPHA)
        st = fighter.anim_state()
        st['flash'] = 0
        st['z'] = 0
        draw_character(self.surf, w_ / 2, h_ - 10, fighter.app, fighter.facing, st)
        tint = pygame.Surface((w_, h_), pygame.SRCALPHA)
        tint.fill((*col, 0))
        self.surf.fill((*col, 255), special_flags=pygame.BLEND_RGB_MAX)
        self.pos = V(fighter.pos.x, fighter.pos.y - fighter.z)
        self.wh = (w_, h_)
    def draw(self, surf, ox, oy):
        a = int(140 * (1 - self.k))
        self.surf.set_alpha(a)
        surf.blit(self.surf, (self.pos.x - ox - self.wh[0] / 2, self.pos.y - oy - self.wh[1] + 10))

class ProjTrailFX(Effect):
    def __init__(self, pts, col, width, life=0.25):
        super().__init__(life)
        self.pts = pts; self.col = col; self.width = width
    def draw(self, surf, ox, oy):
        if len(self.pts) < 2:
            return
        pp = [(p[0] - ox, p[1] - oy) for p in self.pts]
        pygame.draw.lines(surf, self.col, False, pp, max(1, int(self.width * (1 - self.k))))

class CageFX(Effect):
    """Птичья клетка Дофламинго — сужающиеся нити."""
    layer = 2
    def __init__(self, pos, r0, life, col=(255, 255, 255)):
        super().__init__(life)
        self.pos = V(pos); self.r0 = r0; self.col = col
    def radius(self):
        return self.r0 * (1 - 0.8 * self.k)
    def draw(self, surf, ox, oy):
        r = self.radius()
        x, y = self.pos.x - ox, self.pos.y - oy
        for i in range(28):
            a = i / 28 * 6.28 + self.t * 0.3
            p = (x + math.cos(a) * r, y + math.sin(a) * r * 0.75)
            pygame.draw.line(surf, self.col, p, (x + math.cos(a) * r * 0.2, y - r * 1.4), 1)

class Camera:
    def __init__(self):
        self.pos = V(0, 0)
        self.zoom = 1.0
        self.target_zoom = 1.0
        self.trauma = 0.0
        self.shake_off = V(0, 0)
        self.kick = V(0, 0)
        self.focus = None
        self.focus_t = 0
        self.bounds = None

    def add_shake(self, amount):
        self.trauma = clamp(self.trauma + amount, 0, 1.0)

    def punch(self, direction, amount=10):
        self.kick += V(direction) * amount

    def update(self, dt, target, look=V(0, 0)):
        tgt = V(target) + look
        if self.focus is not None and self.focus_t > 0:
            self.focus_t -= dt
            tgt = V(self.focus)
        self.pos += (tgt - self.pos) * min(1, dt * 7)
        self.zoom += (self.target_zoom - self.zoom) * min(1, dt * 6)
        self.trauma = max(0, self.trauma - dt * 1.4)
        sh = self.trauma ** 2 * 26
        self.shake_off = V(random.uniform(-sh, sh), random.uniform(-sh, sh))
        self.kick *= 0.8 ** (dt * 60)
        if self.bounds:
            vw, vh = W / self.zoom, H / self.zoom
            bx0, by0, bx1, by1 = self.bounds
            if bx1 - bx0 > vw:
                self.pos.x = clamp(self.pos.x, bx0 + vw / 2, bx1 - vw / 2)
            if by1 - by0 > vh:
                self.pos.y = clamp(self.pos.y, by0 + vh / 2, by1 - vh / 2)

    def offset(self, vw, vh):
        return (self.pos.x - vw / 2 + self.shake_off.x + self.kick.x, self.pos.y - vh / 2 + self.shake_off.y + self.kick.y)

    def view_size(self):
        return int(W / self.zoom), int(H / self.zoom)

# ==================================================================
#  ДАННЫЕ: СТИХИИ, ПРИЁМЫ, СТИЛИ, ФРУКТЫ
# ==================================================================
ELEMENTS = {
    'none':    dict(c1=(255, 240, 200), c2=(255, 255, 255), part='spark', terrain=None, status=None),
    'phys':    dict(c1=(255, 230, 170), c2=(255, 255, 255), part='spark', terrain=None, status=None),
    'rubber':  dict(c1=(255, 210, 170), c2=(255, 255, 255), part='spark', terrain=None, status=None),
    'nika':    dict(c1=(255, 255, 255), c2=(255, 240, 200), part='glow', terrain=None, status=None),
    'sword':   dict(c1=(190, 220, 255), c2=(255, 255, 255), part='spark', terrain=None, status=('bleed', 2.0, 0.25)),
    'fire':    dict(c1=(255, 130, 30), c2=(255, 230, 120), part='fire', terrain='fire', status=('burn', 3.0, 0.5)),
    'blue_fire': dict(c1=(80, 170, 255), c2=(230, 250, 120), part='fire', terrain=None, status=('burn', 2.0, 0.3)),
    'ice':     dict(c1=(150, 220, 255), c2=(240, 255, 255), part='shard', terrain='ice', status=('freeze', 1.6, 0.45)),
    'magma':   dict(c1=(255, 70, 20), c2=(255, 190, 60), part='fire', terrain='lava', status=('burn', 4.0, 0.7)),
    'light':   dict(c1=(255, 235, 100), c2=(255, 255, 220), part='glow', terrain='scorch', status=None),
    'thunder': dict(c1=(130, 190, 255), c2=(240, 250, 255), part='elec', terrain='scorch', status=('shock', 1.2, 0.4)),
    'sand':    dict(c1=(220, 190, 120), c2=(250, 230, 170), part='dust', terrain='sand', status=('slow', 2.0, 0.4)),
    'quake':   dict(c1=(200, 220, 255), c2=(255, 255, 255), part='debris', terrain='crater', status=('stun', 0.6, 0.35)),
    'dark':    dict(c1=(70, 20, 90), c2=(160, 80, 200), part='dark', terrain='crater', status=('slow', 2.0, 0.5)),
    'smoke':   dict(c1=(220, 220, 225), c2=(255, 255, 255), part='smoke', terrain=None, status=('slow', 1.5, 0.4)),
    'string':  dict(c1=(255, 255, 255), c2=(255, 190, 230), part='spark', terrain=None, status=('bind', 0.8, 0.3)),
    'mochi':   dict(c1=(245, 235, 215), c2=(255, 255, 255), part='smoke', terrain=None, status=('slow', 2.0, 0.5)),
    'room':    dict(c1=(110, 170, 255), c2=(220, 240, 255), part='glow', terrain=None, status=None),
    'water':   dict(c1=(60, 140, 255), c2=(200, 230, 255), part='water', terrain=None, status=('slow', 1.0, 0.3)),
    'poison':  dict(c1=(150, 60, 190), c2=(200, 255, 120), part='smoke', terrain='poison', status=('poison', 4.0, 0.7)),
    'gas':     dict(c1=(170, 120, 200), c2=(230, 200, 255), part='smoke', terrain=None, status=('poison', 3.0, 0.5)),
    'gravity': dict(c1=(150, 90, 230), c2=(230, 200, 255), part='debris', terrain='crater', status=('slow', 2.0, 0.6)),
    'soul':    dict(c1=(255, 150, 200), c2=(255, 230, 250), part='glow', terrain=None, status=('fear', 1.2, 0.35)),
    'paw':     dict(c1=(255, 180, 200), c2=(255, 240, 250), part='glow', terrain='crater', status=None),
    'petal':   dict(c1=(255, 140, 190), c2=(255, 220, 240), part='petal', terrain=None, status=('bind', 1.0, 0.3)),
    'love':    dict(c1=(255, 100, 180), c2=(255, 220, 240), part='glow', terrain=None, status=('petrify', 2.0, 0.6)),
    'barrier': dict(c1=(180, 230, 255), c2=(255, 255, 255), part='glow', terrain=None, status=None),
    'phoenix': dict(c1=(60, 180, 255), c2=(250, 240, 120), part='fire', terrain=None, status=None),
    'wind':    dict(c1=(200, 255, 230), c2=(255, 255, 255), part='line', terrain=None, status=None),
    'bomb':    dict(c1=(255, 160, 60), c2=(255, 240, 160), part='fire', terrain='crater', status=('burn', 1.5, 0.3)),
    'wax':     dict(c1=(240, 240, 230), c2=(255, 255, 255), part='smoke', terrain=None, status=('slow', 2.5, 0.6)),
    'shadow':  dict(c1=(60, 40, 80), c2=(140, 100, 170), part='dark', terrain=None, status=('slow', 1.5, 0.4)),
    'ghost':   dict(c1=(230, 220, 255), c2=(255, 255, 255), part='glow', terrain=None, status=('fear', 2.0, 0.6)),
    'haki':    dict(c1=(30, 10, 30), c2=(230, 40, 60), part='elec', terrain='crater', status=('stun', 0.5, 0.3)),
    'conq':    dict(c1=(20, 5, 15), c2=(230, 30, 50), part='elec', terrain='crater', status=('stun', 0.8, 0.5)),
    'electro': dict(c1=(255, 240, 120), c2=(255, 255, 255), part='elec', terrain=None, status=('shock', 1.0, 0.4)),
    'biscuit': dict(c1=(220, 170, 100), c2=(250, 220, 160), part='debris', terrain=None, status=None),
    'stone':   dict(c1=(150, 140, 130), c2=(210, 200, 190), part='debris', terrain='crater', status=('stun', 0.5, 0.3)),
    'toy':     dict(c1=(255, 200, 120), c2=(255, 255, 255), part='glow', terrain=None, status=('bind', 1.0, 0.25)),
    'thorn':   dict(c1=(90, 160, 60), c2=(200, 255, 150), part='shard', terrain=None, status=('bleed', 3.0, 0.5)),
    'nightmare': dict(c1=(120, 60, 160), c2=(255, 160, 230), part='dark', terrain=None, status=('sleep', 1.5, 0.35)),
    'dragon':  dict(c1=(120, 200, 255), c2=(255, 255, 255), part='line', terrain='crater', status=None),
    'blood':   dict(c1=(200, 30, 40), c2=(255, 120, 120), part='spark', terrain=None, status=('bleed', 3.0, 0.5)),
    'snow':    dict(c1=(240, 245, 255), c2=(255, 255, 255), part='glow', terrain='ice', status=('freeze', 1.0, 0.3)),
}

def el(e):
    return ELEMENTS.get(e, ELEMENTS['none'])

# --- короткие конструкторы примитивов ---
def P_melee(dmg=1.0, r=60, arc=120, knock=220, launch=0, vis='punch', el_='phys', stun=0.25, off=20, **kw):
    d = dict(p='melee', dmg=dmg, r=r, arc=arc, knock=knock, launch=launch, vis=vis, el=el_, stun=stun, off=off)
    d.update(kw)
    return d

def P_proj(dmg=1.0, spd=700, size=10, life=0.9, n=1, spread=0, shape='orb', el_='phys', pierce=0, knock=150, explode=0, homing=0, **kw):
    d = dict(p='proj', dmg=dmg, spd=spd, size=size, life=life, n=n, spread=spread, shape=shape, el=el_, pierce=pierce, knock=knock,
             explode=explode, homing=homing)
    d.update(kw)
    return d

def P_beam(dmg=0.4, length=500, w=24, life=0.6, el_='light', tick=0.08, knock=60, **kw):
    d = dict(p='beam', dmg=dmg, len=length, w=w, life=life, el=el_, tick=tick, knock=knock)
    d.update(kw)
    return d

def P_nova(dmg=1.5, r=140, at='self', delay=0.0, knock=400, launch=0, el_='phys', **kw):
    d = dict(p='nova', dmg=dmg, r=r, at=at, delay=delay, knock=knock, launch=launch, el=el_)
    d.update(kw)
    return d

def P_dash(dmg=1.0, dist=260, spd=1600, w=50, el_='phys', knock=250, **kw):
    d = dict(p='dash', dmg=dmg, dist=dist, spd=spd, w=w, el=el_, knock=knock)
    d.update(kw)
    return d

def P_barrage(dmg=0.25, n=14, dur=0.8, r=95, arc=70, el_='phys', vis='fists', **kw):
    d = dict(p='barrage', dmg=dmg, n=n, dur=dur, r=r, arc=arc, el=el_, vis=vis)
    d.update(kw)
    return d

def P_rain(dmg=0.8, n=10, dur=1.2, area=170, r=60, at='cursor', el_='fire', vis='meteor', **kw):
    d = dict(p='rain', dmg=dmg, n=n, dur=dur, area=area, r=r, at=at, el=el_, vis=vis)
    d.update(kw)
    return d

def P_zone(dmg=0.2, r=150, life=4.0, tick=0.4, at='self', el_='fire', pull=0, slow=0.0, vis='field', **kw):
    d = dict(p='zone', dmg=dmg, r=r, life=life, tick=tick, at=at, el=el_, pull=pull, slow=slow, vis=vis)
    d.update(kw)
    return d

def P_wave(dmg=1.0, n=7, step=60, dt_=0.06, r=55, el_='sand', vis='spike', **kw):
    d = dict(p='wave', dmg=dmg, n=n, step=step, dt=dt_, r=r, el=el_, vis=vis)
    d.update(kw)
    return d

def P_buff(dur=10, dmg=1.0, defn=1.0, spd=1.0, regen=0.0, aura=(255, 255, 255), form=None, **kw):
    d = dict(p='buff', dur=dur, dmg=dmg, defn=defn, spd=spd, regen=regen, aura=aura, form=form)
    d.update(kw)
    return d

def P_tp(rng_=350, dmg=0.0, r=90, el_='light', **kw):
    d = dict(p='teleport', range=rng_, dmg=dmg, r=r, el=el_)
    d.update(kw)
    return d

def P_summon(kind='doppel', n=1, life=12, **kw):
    d = dict(p='summon', kind=kind, n=n, life=life)
    d.update(kw)
    return d

def P_grab(dmg=2.0, r=260, el_='phys', **kw):
    d = dict(p='grab', dmg=dmg, r=r, el=el_)
    d.update(kw)
    return d

def P_shield(dur=3.0, absorb=0.6, reflect=False, aura=(180, 230, 255), **kw):
    d = dict(p='shield', dur=dur, absorb=absorb, reflect=reflect, aura=aura)
    d.update(kw)
    return d

def P_heal(frac=0.25, aura=(120, 220, 255), **kw):
    d = dict(p='heal', frac=frac, aura=aura)
    d.update(kw)
    return d

def P_fx(kind, **kw):
    d = dict(p='fx', kind=kind)
    d.update(kw)
    return d

def MV(name, cd, cost, steps, cast=0.12, desc="", ult=False, lock=0.3, sfx=None, tele=None, scale='atk', **kw):
    d = dict(name=name, cd=cd, cost=cost, steps=steps, cast=cast, desc=desc, ult=ult, lock=lock, sfx=sfx, tele=tele, scale=scale)
    d.update(kw)
    return d

S = lambda t, p: (t, p)

# ------------------------------------------------------------------
#  ПРИЁМЫ
# ------------------------------------------------------------------
MOVES = {
    # ==== ГОМУ ГОМУ / НИКА ====
    'gomu_pistol': MV("Гому Гому но Пистолет", 2.0, 12, [S(0, P_proj(1.6, 1300, 14, 0.32, shape='fist', el_='rubber', knock=420, pierce=2, stretch=True))],
                      desc="Растянутый удар кулаком на дальнюю дистанцию.", sfx='stretch', scale='fruit'),
    'gomu_gatling': MV("Гому Гому но Гатлинг", 6.0, 25, [S(0, P_barrage(0.32, 18, 1.0, 120, 70, 'rubber'))],
                       desc="Шквал растянутых ударов.", sfx='stretch', lock=1.0, scale='fruit'),
    'gomu_bazooka': MV("Гому Гому но Базука", 5.0, 22, [S(0.1, P_melee(3.0, 95, 70, 900, 260, 'palm', 'rubber', 0.6, off=40))],
                       desc="Двойной удар ладонями, отбрасывающий врагов.", cast=0.25, sfx='hit_heavy', scale='fruit'),
    'gear2': MV("Гир Второй", 25.0, 20, [S(0, P_buff(14, 1.35, 1.0, 1.45, 0, (255, 140, 160), form='gear2', steam=True))],
                desc="Ускоренный кровоток: скорость и сила.", sfx='whoosh', scale='fruit'),
    'gear3': MV("Гир Третий: Элефант Ган", 9.0, 35, [S(0.35, P_nova(4.0, 150, 'front', 0, 1100, 300, 'rubber', vis='giant_fist', destroy=3.0))],
                desc="Гигантский кулак из костей.", cast=0.4, sfx='hit_heavy', scale='fruit', tele='circle'),
    'gear4': MV("Гир Четвёртый: Конг Ган", 12.0, 45, [S(0.3, P_proj(5.0, 1100, 40, 0.5, shape='fist', el_='haki', knock=1300, pierce=8, explode=110, black=True, stretch=True))],
                desc="Баундмен: чёрный кулак, пробивающий всё.", cast=0.35, sfx='hit_heavy', scale='fruit'),
    'red_roc': MV("Гому Гому но Ред Рок", 40.0, 60, [S(0.2, P_proj(9.0, 1400, 36, 0.8, shape='comet', el_='fire', pierce=20, knock=1500, explode=180, destroy=4.0))],
                  desc="УЛЬТА. Пылающий кулак-комета.", ult=True, cast=0.3, sfx='explosion', scale='fruit'),
    'bajrang_gun': MV("Гому Гому но Баджранг Ган", 50.0, 80, [S(0.4, P_proj(14.0, 900, 80, 1.2, shape='fist', el_='nika', pierce=99, knock=2000, explode=320, destroy=8.0, white=True))],
                      desc="УЛЬТА (Ника). Кулак размером с остров.", ult=True, cast=0.5, sfx='explosion', scale='fruit'),
    'nika_dawn': MV("Рассветный Хлыст", 6.0, 20, [S(0, P_melee(3.0, 180, 200, 800, 300, 'whip', 'nika', 0.6, off=10))],
                    desc="Ника: мультяшный удар-хлыст.", scale='fruit'),
    'nika_grab': MV("Хватка Ники", 8.0, 25, [S(0, P_grab(4.0, 450, 'nika'))], desc="Хватает врага и швыряет его о землю.", scale='fruit'),
    'nika_lightning': MV("Ловля Молнии", 10.0, 35, [S(0, P_rain(2.0, 6, 0.8, 180, 70, 'cursor', 'thunder', 'bolt'))], desc="Ника хватает молнию и бьёт ей.", scale='fruit'),
    # ==== МЕРА МЕРА ====
    'hiken': MV("Хикен — Огненный Кулак", 4.0, 22, [S(0.1, P_proj(2.6, 900, 26, 0.8, shape='fireball', el_='fire', pierce=4, explode=90))],
                desc="Огромный огненный кулак.", sfx='fire', scale='fruit'),
    'higan': MV("Хиган — Огненные Пули", 3.0, 14, [S(0, P_proj(0.7, 1000, 8, 0.7, n=7, spread=0.5, shape='bullet', el_='fire'))],
                desc="Пули пламени из пальцев.", sfx='fire', scale='fruit'),
    'hibashira': MV("Хибашира — Огненный Столп", 7.0, 28, [S(0.2, P_nova(3.0, 120, 'cursor', 0.35, 300, 400, 'fire', vis='pillar'))],
                    desc="Колонна огня под врагом.", cast=0.25, sfx='fire', scale='fruit', tele='circle'),
    'enjomo': MV("Энджомо — Огненная Стена", 12.0, 30, [S(0, P_zone(0.35, 210, 5.0, 0.3, 'self', 'fire', vis='ring_wall'))],
                 desc="Кольцо огня вокруг тебя.", sfx='fire', scale='fruit'),
    'entei': MV("Энтей — Пламенный Император", 45.0, 70, [S(0.6, P_nova(10.0, 330, 'cursor', 0.5, 1400, 500, 'fire', vis='sun', destroy=6.0))],
                desc="УЛЬТА. Огненное солнце обрушивается на землю.", ult=True, cast=0.6, sfx='explosion', scale='fruit', tele='circle'),
    # ==== ХИЕ ХИЕ ====
    'ice_saber': MV("Ледяная Сабля", 2.0, 10, [S(0.05, P_melee(1.8, 90, 140, 260, 0, 'slash', 'ice', 0.35, off=25))], desc="Меч изо льда.", sfx='ice', scale='fruit'),
    'ice_partisan': MV("Партизан — Ледяные Копья", 4.0, 18, [S(0, P_proj(1.0, 950, 9, 0.8, n=5, spread=0.35, shape='spear', el_='ice'))],
                       desc="Залп ледяных копий.", sfx='ice', scale='fruit'),
    'ice_time': MV("Ледниковое Время", 9.0, 25, [S(0.1, P_nova(1.5, 150, 'front', 0, 100, 0, 'ice', vis='frost', freeze=2.5))],
                   desc="Замораживает всё впереди.", sfx='ice', scale='fruit'),
    'pheasant_beak': MV("Клюв Ледяного Фазана", 8.0, 30, [S(0.15, P_proj(3.5, 800, 34, 0.9, shape='bird', el_='ice', pierce=10, explode=100))],
                        desc="Огромная ледяная птица.", cast=0.2, sfx='ice', scale='fruit'),
    'ice_age': MV("Ледниковый Период", 45.0, 70, [S(0.3, P_nova(7.0, 420, 'self', 0.2, 300, 0, 'ice', vis='frost', freeze=4.0, terrain_r=520, destroy=3.0))],
                  desc="УЛЬТА. Мгновенно замораживает всё вокруг — даже море.", ult=True, cast=0.4, sfx='ice', scale='fruit'),
    # ==== МАГУ МАГУ ====
    'dai_funka': MV("Дай Функа — Великое Извержение", 5.0, 26, [S(0.15, P_proj(3.2, 800, 30, 0.8, shape='magma_fist', el_='magma', pierce=6, explode=110, destroy=2.5))],
                    desc="Кулак магмы.", sfx='fire', scale='fruit'),
    'inugami': MV("Инугами Гурен — Пёс Магмы", 8.0, 32, [S(0.2, P_wave(3.0, 7, 60, 0.05, 70, 'magma', 'magma_head'))],
                  desc="Голова пса из магмы, вырывающаяся из земли.", sfx='fire', scale='fruit'),
    'magma_pool': MV("Озеро Магмы", 12.0, 28, [S(0, P_zone(0.45, 170, 6.0, 0.35, 'cursor', 'magma', vis='lava'))],
                     desc="Превращает землю в лаву.", sfx='fire', scale='fruit'),
    'ryusei_kazan': MV("Рюсей Казан — Метеорный Вулкан", 45.0, 75, [S(0.3, P_rain(3.0, 26, 2.4, 330, 75, 'cursor', 'magma', 'meteor', destroy=3.0))],
                       desc="УЛЬТА. Дождь из магмовых кулаков.", ult=True, cast=0.4, sfx='explosion', scale='fruit'),
    # ==== ПИКА ПИКА ====
    'yasakani': MV("Ясакани но Магатама", 5.0, 25, [S(0, P_proj(0.55, 1500, 7, 0.6, n=16, spread=0.7, shape='light_orb', el_='light', explode=40, burst=0.05))],
                   desc="Дождь световых пуль.", sfx='beam', scale='fruit', lock=0.8),
    'ama_no_murakumo': MV("Ама но Муракумо — Световой Меч", 2.0, 10, [S(0, P_melee(2.0, 110, 140, 300, 0, 'slash', 'light', 0.3, off=25))], desc="Меч из света.", sfx='slash', scale='fruit'),
    'yata_no_kagami': MV("Ята но Кагами — Зеркало", 4.0, 15, [S(0, P_tp(420, 1.5, 90, 'light'))], desc="Мгновенное перемещение со скоростью света.", sfx='beam', scale='fruit'),
    'light_kick': MV("Удар Скорости Света", 6.0, 20, [S(0, P_dash(3.0, 420, 4000, 60, 'light', 700))], desc="Пинок со скоростью света.", sfx='beam', scale='fruit'),
    'yasakani_rain': MV("Ясакани: Ливень Света", 45.0, 70, [S(0.3, P_rain(2.4, 30, 2.2, 340, 60, 'cursor', 'light', 'light_drop', destroy=2.5))],
                        desc="УЛЬТА. Световые бомбы падают с неба.", ult=True, cast=0.4, sfx='beam', scale='fruit'),
    # ==== ГОРО ГОРО ====
    'el_thor': MV("Эль Тор", 7.0, 30, [S(0.2, P_nova(3.2, 100, 'cursor', 0.45, 300, 200, 'thunder', vis='bolt_pillar'))],
                  desc="Столб молнии с небес.", cast=0.2, sfx='thunder', scale='fruit', tele='circle'),
    'sango': MV("Санго — 200 млн вольт", 6.0, 26, [S(0.1, P_beam(0.55, 520, 34, 0.5, 'thunder', 0.07, 160))], desc="Разряд вперёд.", sfx='thunder', scale='fruit'),
    'kari': MV("Кари — Разряд", 8.0, 25, [S(0, P_nova(2.2, 180, 'self', 0, 500, 100, 'thunder', vis='elec_burst'))], desc="Электрический взрыв вокруг.", sfx='thunder', scale='fruit'),
    'enel_tp': MV("Молниеносный Шаг", 3.0, 12, [S(0, P_tp(450, 1.0, 80, 'thunder'))], desc="Перемещение молнией.", sfx='thunder', scale='fruit'),
    'raigo': MV("Райго — Грозовое Облако", 50.0, 80, [S(0.5, P_rain(2.5, 28, 2.6, 360, 70, 'cursor', 'thunder', 'bolt', destroy=2.5))],
                desc="УЛЬТА. Чудовищная гроза.", ult=True, cast=0.6, sfx='thunder', scale='fruit'),
    # ==== СУНА СУНА ====
    'sables': MV("Саблес — Песчаный Смерч", 6.0, 24, [S(0.1, P_proj(0.35, 380, 50, 2.2, shape='tornado', el_='sand', pierce=99, tick=0.15, knock=60, pull=200))],
                 desc="Песчаный смерч, затягивающий врагов.", sfx='whoosh', scale='fruit'),
    'desert_spada': MV("Дезерт Спада", 5.0, 22, [S(0.1, P_wave(2.2, 9, 55, 0.04, 50, 'sand', 'spike'))], desc="Лезвие песка по земле.", sfx='slash', scale='fruit'),
    'ground_death': MV("Граунд Сэт — Иссушение", 12.0, 30, [S(0.1, P_zone(0.5, 200, 3.0, 0.3, 'self', 'sand', vis='dry', drain=True))],
                       desc="Высасывает влагу из всего живого вокруг.", sfx='whoosh', scale='fruit'),
    'desert_girasole': MV("Дезерт Гирасоле", 45.0, 70, [S(0.3, P_zone(1.2, 340, 4.0, 0.25, 'cursor', 'sand', pull=380, vis='quicksand', destroy=2.0))],
                          desc="УЛЬТА. Гигантская воронка зыбучих песков.", ult=True, cast=0.4, sfx='quake', scale='fruit'),
    # ==== ГУРА ГУРА ====
    'quake_punch': MV("Удар Землетрясения", 4.0, 22, [S(0.15, P_melee(3.0, 170, 90, 1000, 200, 'quake', 'quake', 0.5, off=10, destroy=3.0))],
                      desc="Кулак, раскалывающий воздух.", cast=0.2, sfx='quake', scale='fruit'),
    'kabutowari': MV("Кабутовари — Раскол", 8.0, 30, [S(0.2, P_wave(3.0, 9, 70, 0.04, 70, 'quake', 'crack', destroy=3.0))], desc="Раскалывает землю перед собой.", sfx='quake', scale='fruit'),
    'gura_shock': MV("Сотрясающая Волна", 10.0, 35, [S(0.2, P_nova(3.5, 260, 'self', 0, 1200, 300, 'quake', vis='quake', destroy=3.0))], desc="Ударная волна во все стороны.", sfx='quake', scale='fruit'),
    'seaquake': MV("Морское Землетрясение — Цунами", 50.0, 85, [S(0.5, P_wave(6.0, 10, 90, 0.08, 150, 'quake', 'tsunami', destroy=6.0))],
                   desc="УЛЬТА. Сила, способная уничтожить мир.", ult=True, cast=0.6, sfx='quake', scale='fruit'),
    # ==== ЯМИ ЯМИ ====
    'kurouzu': MV("Куроузу — Чёрный Водоворот", 6.0, 25, [S(0, P_grab(2.5, 380, 'dark', nullify=True))], desc="Притягивает врага и отменяет его фрукт.", sfx='haki', scale='fruit'),
    'black_hole': MV("Чёрная Дыра", 12.0, 35, [S(0.1, P_zone(0.5, 200, 4.5, 0.3, 'cursor', 'dark', pull=320, vis='blackhole', destroy=2.0))],
                     desc="Поглощающая тьма.", sfx='haki', scale='fruit'),
    'liberation': MV("Освобождение", 9.0, 30, [S(0.1, P_proj(0.6, 800, 12, 0.8, n=14, spread=1.0, shape='rock', el_='dark', burst=0.03))], desc="Выплёвывает поглощённые обломки.", sfx='crumble', scale='fruit'),
    'black_vortex': MV("Чёрный Вихрь: Конец Света", 45.0, 75, [S(0.3, P_zone(2.0, 380, 3.5, 0.2, 'cursor', 'dark', pull=520, vis='blackhole', destroy=5.0)), S(3.6, P_nova(6.0, 380, 'cursor', 0, 1400, 300, 'dark', vis='quake'))],
                         desc="УЛЬТА. Тьма, пожирающая всё.", ult=True, cast=0.4, sfx='haki', scale='fruit'),
    # ==== ОПЕ ОПЕ ====
    'room': MV("ROOM", 14.0, 20, [S(0, P_zone(0, 330, 10.0, 1.0, 'self', 'room', vis='room', room=True))], desc="Создаёт операционную. Внутри приёмы сильнее.", sfx='beam', scale='fruit'),
    'shambles': MV("Шамблс", 3.0, 12, [S(0, P_tp(500, 2.0, 70, 'room', swap=True))], desc="Мгновенная перестановка.", sfx='whoosh', scale='fruit'),
    'injection_shot': MV("Инджекшн Шот", 5.0, 20, [S(0, P_dash(3.2, 380, 2600, 50, 'room', 600))], desc="Пронзающий выпад мечом.", sfx='slash', scale='fruit'),
    'gamma_knife': MV("Гамма Найф", 9.0, 30, [S(0.15, P_beam(1.2, 300, 26, 0.35, 'room', 0.06, 50, ignore_def=True))], desc="Разрушает органы изнутри.", sfx='beam', scale='fruit'),
    'puncture_wille': MV("Панкчер Вилле", 45.0, 70, [S(0.4, P_beam(3.0, 900, 60, 0.6, 'room', 0.05, 900, destroy=6.0))], desc="УЛЬТА. Удар, пронзающий небо.", ult=True, cast=0.5, sfx='beam', scale='fruit'),
    # ==== ИТО ИТО ====
    'overheat': MV("Оверхит — Огненная Нить", 4.0, 18, [S(0.1, P_beam(0.7, 520, 18, 0.35, 'string', 0.07, 200, col=(255, 120, 60)))], desc="Раскалённый канат.", sfx='whoosh', scale='fruit'),
    'tamaito': MV("Тамаито — Нитяные Пули", 3.0, 14, [S(0, P_proj(0.6, 1300, 5, 0.7, n=5, spread=0.25, shape='string', el_='string'))], desc="Пули из нитей.", sfx='whoosh', scale='fruit'),
    'parasite': MV("Паразит", 10.0, 25, [S(0, P_nova(0.5, 230, 'self', 0, 0, 0, 'string', vis='strings', status=('bind', 2.5, 1.0)))], desc="Сковывает врагов нитями.", sfx='whoosh', scale='fruit'),
    'goshikito': MV("Гошикито — Пять Цветов", 8.0, 30, [S(0.1, P_wave(2.6, 8, 65, 0.035, 50, 'string', 'string_lash'))], desc="Пять нитей разрезают землю.", sfx='slash', scale='fruit'),
    'birdcage': MV("Птичья Клетка", 50.0, 75, [S(0.3, P_zone(0.9, 430, 6.0, 0.2, 'self', 'string', vis='cage', shrink=True, destroy=4.0))], desc="УЛЬТА. Сужающаяся клетка из нитей.", ult=True, cast=0.4, sfx='slash', scale='fruit'),
    # ==== МОТИ МОТИ ====
    'mochi_tsuki': MV("Моти Цуки — Трезубец", 3.0, 14, [S(0.1, P_dash(2.2, 220, 1800, 55, 'mochi', 400))], desc="Выпад трезубцем.", sfx='slash', scale='fruit'),
    'zan_giri': MV("Дзан Гири Моти", 5.0, 20, [S(0.1, P_proj(1.2, 1000, 12, 0.6, n=5, spread=0.4, shape='mochi', el_='mochi'))], desc="Острые шипы моти.", sfx='whoosh', scale='fruit'),
    'power_mochi': MV("Пауэр Моти", 8.0, 30, [S(0.25, P_nova(3.8, 140, 'front', 0, 1000, 200, 'mochi', vis='giant_fist', destroy=2.5))], desc="Огромный кулак моти.", cast=0.3, sfx='hit_heavy', scale='fruit'),
    'buzz_cut': MV("Базз Кат Моти", 45.0, 70, [S(0.2, P_zone(1.4, 260, 3.0, 0.15, 'self', 'mochi', vis='mochi_ring', destroy=3.0))], desc="УЛЬТА. Вращающиеся кольца моти.", ult=True, cast=0.3, sfx='whoosh', scale='fruit'),
    # ==== МОКУ МОКУ ====
    'white_blow': MV("Уайт Блоу", 3.0, 14, [S(0.05, P_proj(1.8, 1000, 20, 0.5, shape='smoke_fist', el_='smoke', knock=500))], desc="Кулак из дыма.", sfx='whoosh', scale='fruit'),
    'white_snake': MV("Уайт Снейк", 8.0, 25, [S(0.1, P_grab(2.0, 420, 'smoke'))], desc="Дымовая змея хватает врага.", sfx='whoosh', scale='fruit'),
    'white_launcher': MV("Уайт Лаунчер", 5.0, 20, [S(0, P_dash(2.4, 380, 2200, 70, 'smoke', 500))], desc="Таран из дыма.", sfx='whoosh', scale='fruit'),
    'white_out': MV("Уайт Аут", 40.0, 65, [S(0.3, P_zone(0.6, 320, 5.0, 0.2, 'self', 'smoke', slow=0.6, vis='smoke_field', status=('bind', 1.0, 0.4)))], desc="УЛЬТА. Дымовая буря обездвиживает всех.", ult=True, cast=0.3, sfx='whoosh', scale='fruit'),
    # ==== БАРА БАРА ====
    'bara_cannon': MV("Бара Бара Пушка", 2.5, 12, [S(0, P_proj(1.4, 900, 12, 0.6, shape='fist', el_='phys', homing=3))], desc="Летящая рука с ножами.", sfx='whoosh', scale='fruit'),
    'bara_festival': MV("Бара Бара Фестиваль", 10.0, 30, [S(0, P_zone(0.4, 200, 4.0, 0.2, 'self', 'phys', vis='blades'))], desc="Части тела кружат и режут врагов.", sfx='slash', scale='fruit'),
    'muggy_ball': MV("Магги Бомба", 8.0, 30, [S(0.2, P_proj(3.5, 700, 24, 0.9, shape='cannonball', el_='bomb', explode=150, destroy=3.0))], desc="Бомба из носа корабля... то есть из пушки!", sfx='cannon', scale='fruit'),
    'bara_ult': MV("Бара Бара: Шоу Клоуна", 40.0, 60, [S(0.2, P_rain(2.0, 20, 2.0, 300, 60, 'cursor', 'bomb', 'meteor', destroy=2.0))], desc="УЛЬТА. Дождь из бомб.", ult=True, cast=0.3, sfx='explosion', scale='fruit'),
    # ==== НИКЮ НИКЮ ====
    'paw_shot': MV("Пад Хо — Лапа", 3.0, 15, [S(0, P_proj(2.0, 1300, 22, 0.6, shape='paw', el_='paw', knock=700, pierce=4))], desc="Отталкивающая лапа воздуха.", sfx='whoosh', scale='fruit'),
    'tsuppari': MV("Цуппари Пад Хо", 7.0, 28, [S(0, P_proj(1.0, 1300, 18, 0.6, n=9, spread=0.6, shape='paw', el_='paw', knock=400, burst=0.06))], desc="Град лап.", sfx='whoosh', scale='fruit', lock=0.7),
    'paw_tp': MV("Путешествие", 4.0, 15, [S(0, P_tp(500, 0.5, 60, 'paw'))], desc="Отталкивает себя куда угодно.", sfx='whoosh', scale='fruit'),
    'ursus_shock': MV("Урсус Шок", 50.0, 80, [S(0.6, P_nova(10.0, 340, 'cursor', 0.6, 1600, 400, 'paw', vis='pressure', destroy=6.0))], desc="УЛЬТА. Сжатый воздух взрывается.", ult=True, cast=0.6, sfx='explosion', scale='fruit', tele='circle'),
    # ==== КАГЕ КАГЕ ====
    'doppelman': MV("Доппельман", 20.0, 25, [S(0, P_summon('doppel', 1, 14))], desc="Призывает свою тень сражаться.", sfx='haki', scale='fruit'),
    'brick_bat': MV("Брик Бат", 5.0, 20, [S(0, P_proj(0.6, 900, 9, 1.0, n=10, spread=0.9, shape='bat', el_='shadow', homing=4))], desc="Стая теневых летучих мышей.", sfx='whoosh', scale='fruit'),
    'shadow_box': MV("Теневой Капкан", 9.0, 25, [S(0.1, P_zone(0.3, 160, 3.0, 0.3, 'cursor', 'shadow', slow=0.7, vis='shadow_pool'))], desc="Озеро теней замедляет.", sfx='haki', scale='fruit'),
    'shadow_asgard': MV("Теневой Асгард", 45.0, 70, [S(0, P_buff(15, 1.8, 1.4, 0.9, 0, (90, 50, 120), form='giant'))], desc="УЛЬТА. Поглощает тысячу теней и становится гигантом.", ult=True, sfx='haki', scale='fruit'),
    # ==== ЗУСИ ЗУСИ ====
    'gravity_blade': MV("Гравитационный Клинок", 3.0, 14, [S(0.05, P_melee(2.2, 120, 130, 300, 0, 'slash', 'gravity', 0.4))], desc="Удар мечом с гравитацией.", sfx='slash', scale='fruit'),
    'gravity_press': MV("Гравитационный Пресс", 9.0, 30, [S(0.2, P_zone(0.6, 200, 3.0, 0.25, 'cursor', 'gravity', slow=0.8, vis='gravity', destroy=2.0))], desc="Вдавливает врагов в землю.", sfx='quake', scale='fruit'),
    'meteor_fall': MV("Падение Метеорита", 50.0, 80, [S(0.8, P_nova(11.0, 330, 'cursor', 1.0, 1500, 500, 'stone', vis='meteor_big', destroy=7.0))], desc="УЛЬТА. Притягивает метеорит с неба.", ult=True, cast=0.5, sfx='explosion', scale='fruit', tele='circle'),
    # ==== СОРУ СОРУ (Биг Мам) ====
    'zeus': MV("Зевс — Грозовое Облако", 7.0, 28, [S(0.1, P_rain(1.6, 6, 0.8, 140, 70, 'cursor', 'thunder', 'bolt'))], desc="Хоми-облако метает молнии.", sfx='thunder', scale='fruit'),
    'prometheus': MV("Прометей — Солнце", 8.0, 30, [S(0.1, P_proj(2.6, 700, 32, 1.0, shape='fireball', el_='fire', explode=120))], desc="Хоми-солнце.", sfx='fire', scale='fruit'),
    'soul_pocus': MV("Соул Покус", 12.0, 35, [S(0.1, P_nova(2.5, 200, 'self', 0, 300, 0, 'soul', vis='soul', drain_life=True))], desc="«Жизнь или угощение?» — крадёт годы жизни.", sfx='haki', scale='fruit'),
    'heavenly_fire': MV("Небесный Огонь", 50.0, 80, [S(0.4, P_rain(3.0, 22, 2.4, 340, 80, 'cursor', 'fire', 'meteor', destroy=3.0))], desc="УЛЬТА. Гнев Императрицы.", ult=True, cast=0.4, sfx='explosion', scale='fruit'),
    # ==== УО УО (Сэйрю) ====
    'bolo_breath': MV("Боро Брес — Огненное Дыхание", 6.0, 30, [S(0.2, P_beam(0.7, 560, 46, 0.7, 'fire', 0.07, 200, col=(255, 120, 40)))], desc="Дыхание дракона.", cast=0.25, sfx='fire', scale='fruit'),
    'kaifu': MV("Кайфу — Воздушные Лезвия", 5.0, 22, [S(0, P_proj(1.2, 1000, 14, 0.7, n=5, spread=0.6, shape='wind_blade', el_='wind', pierce=3))], desc="Режущие вихри.", sfx='whoosh', scale='fruit'),
    'thunder_bagua': MV("Раймэй Хаккэ — Громовой Багуа", 9.0, 35, [S(0.35, P_nova(4.5, 160, 'front', 0, 1400, 400, 'conq', vis='club_smash', destroy=4.0))], desc="Удар дубиной, окутанной хаки.", cast=0.4, sfx='hit_heavy', scale='fruit', tele='circle'),
    'dragon_form': MV("Облик Лазурного Дракона", 50.0, 80, [S(0, P_buff(18, 1.7, 1.6, 1.2, 0.01, (90, 160, 255), form='dragon'))], desc="УЛЬТА. Превращение в огромного дракона.", ult=True, sfx='thunder', scale='fruit'),
    # ==== ТОРИ ТОРИ: ФЕНИКС ====
    'phoenix_brand': MV("Клеймо Феникса", 4.0, 18, [S(0, P_dash(2.6, 300, 2000, 60, 'phoenix', 600))], desc="Пинок с голубым пламенем.", sfx='fire', scale='fruit'),
    'phoenix_heal': MV("Пламя Возрождения", 16.0, 30, [S(0, P_heal(0.3, (80, 180, 255)))], desc="Голубое пламя лечит раны.", sfx='fire', scale='fruit'),
    'phoenix_wings': MV("Крылья Феникса", 7.0, 25, [S(0, P_melee(2.5, 170, 220, 600, 200, 'wing', 'phoenix', 0.4, off=0))], desc="Взмах пылающих крыльев.", sfx='fire', scale='fruit'),
    'phoenix_ult': MV("Голубой Феникс", 45.0, 70, [S(0.2, P_proj(6.0, 900, 50, 1.0, shape='bird', el_='phoenix', pierce=99, explode=200, col=(80, 180, 255)))], desc="УЛЬТА. Феникс таранит врагов.", ult=True, cast=0.3, sfx='fire', scale='fruit'),
    # ==== ИНУ ИНУ: ОКУТИ НО МАКАМИ ====
    'namuji': MV("Намудзи Хёга", 5.0, 22, [S(0.1, P_melee(2.6, 140, 120, 600, 150, 'slash', 'ice', 0.4))], desc="Ледяной удар дубинкой.", sfx='ice', scale='fruit'),
    'blizzard': MV("Метель Макамы", 9.0, 30, [S(0, P_zone(0.4, 220, 4.0, 0.3, 'self', 'snow', slow=0.5, vis='blizzard'))], desc="Ледяная буря вокруг.", sfx='ice', scale='fruit'),
    'yamato_ult': MV("Нарикабура — Наруками", 45.0, 70, [S(0.3, P_beam(2.5, 700, 70, 0.6, 'conq', 0.05, 900))], desc="УЛЬТА. Удар, окутанный королевским хаки.", ult=True, cast=0.4, sfx='thunder', scale='fruit'),
    # ==== РЮ РЮ: ПТЕРАНОДОН ====
    'tempura_udon': MV("Тэмпура Удон", 6.0, 25, [S(0.15, P_proj(3.0, 900, 30, 0.7, shape='fireball', el_='fire', explode=100))], desc="Огненный удар мечом-крылом.", sfx='fire', scale='fruit'),
    'ptera_dive': MV("Пике Птеранодона", 6.0, 24, [S(0, P_dash(2.8, 420, 2600, 70, 'fire', 700))], desc="Стремительное пике.", sfx='whoosh', scale='fruit'),
    'king_ult': MV("Огненный Император Лунарийцев", 45.0, 70, [S(0.3, P_rain(2.4, 18, 2.0, 280, 70, 'cursor', 'fire', 'meteor'))], desc="УЛЬТА. Пламя лунарийцев.", ult=True, cast=0.3, sfx='explosion', scale='fruit'),
    # ==== НЭКО НЭКО: ЛЕОПАРД ====
    'leopard_claw': MV("Когти Леопарда", 2.0, 10, [S(0, P_melee(2.0, 85, 120, 250, 0, 'claw', 'blood', 0.3))], desc="Рвущие когти.", sfx='slash', scale='fruit'),
    'leopard_pounce': MV("Прыжок Хищника", 5.0, 20, [S(0, P_dash(2.6, 320, 2400, 60, 'blood', 500))], desc="Молниеносный бросок.", sfx='whoosh', scale='fruit'),
    'leopard_form': MV("Пробуждение Хищника", 30.0, 30, [S(0, P_buff(14, 1.5, 1.3, 1.3, 0, (230, 200, 120), form='beast'))], desc="Превращение в боевую форму леопарда.", sfx='haki', scale='fruit'),
    'rokuogan_lucci': MV("Рокуоган: Сила Тигра", 45.0, 70, [S(0.3, P_nova(8.0, 200, 'front', 0, 1500, 300, 'phys', vis='shockwave6', ignore_def=True, destroy=4.0))], desc="УЛЬТА. Ударная волна, рвущая плоть.", ult=True, cast=0.4, sfx='hit_heavy', scale='fruit'),
    # ==== ХАНА ХАНА ====
    'clutch': MV("Клатч", 6.0, 20, [S(0, P_nova(2.4, 70, 'cursor', 0.15, 0, 300, 'petal', vis='arms', status=('bind', 1.5, 1.0)))], desc="Руки вырастают из земли и ломают врага.", sfx='hit_heavy', scale='fruit'),
    'mil_fleur': MV("Миль Флёр — Поле Рук", 9.0, 25, [S(0, P_zone(0.5, 180, 3.0, 0.3, 'cursor', 'petal', vis='arms_field', slow=0.6))], desc="Тысяча рук хватает врагов.", sfx='whoosh', scale='fruit'),
    'gigantesco': MV("Гигантеско Мано", 9.0, 30, [S(0.3, P_nova(4.0, 140, 'cursor', 0.3, 900, 200, 'petal', vis='giant_fist', destroy=2.5))], desc="Гигантские руки из лепестков.", sfx='hit_heavy', scale='fruit', tele='circle'),
    'demonio': MV("Демонио Флёр", 45.0, 70, [S(0.3, P_nova(8.0, 260, 'cursor', 0.3, 800, 400, 'petal', vis='giant_fist', status=('bind', 2.0, 1.0), destroy=4.0))], desc="УЛЬТА. Демоническая форма Робин.", ult=True, cast=0.4, sfx='hit_heavy', scale='fruit', tele='circle'),
    # ==== МЕРО МЕРО ====
    'pistol_kiss': MV("Пистолет Поцелуй", 3.0, 14, [S(0, P_proj(1.4, 1100, 10, 0.7, shape='heart', el_='love'))], desc="Сердечко, превращающее в камень.", sfx='beam', scale='fruit'),
    'slave_arrow': MV("Стрелы Рабыни", 7.0, 25, [S(0, P_proj(0.9, 1000, 9, 0.8, n=9, spread=0.8, shape='heart', el_='love', burst=0.03))], desc="Залп стрел-сердец.", sfx='beam', scale='fruit'),
    'perfume_femur': MV("Перфьюм Фемур", 4.0, 18, [S(0, P_melee(2.8, 110, 120, 600, 150, 'kick', 'love', 0.4))], desc="Окаменяющий пинок.", sfx='hit_heavy', scale='fruit'),
    'mero_ult': MV("Мероу Мероу Мелло", 45.0, 70, [S(0.2, P_beam(1.5, 700, 90, 0.8, 'love', 0.1, 300))], desc="УЛЬТА. Луч любви — кто дрогнет, станет камнем.", ult=True, cast=0.3, sfx='beam', scale='fruit'),
    # ==== БАРИ БАРИ ====
    'barrier': MV("Барьер", 10.0, 20, [S(0, P_shield(3.5, 1.0, True))], desc="Непробиваемый барьер.", sfx='block', scale='fruit'),
    'barrier_crash': MV("Барьер Крэш", 6.0, 22, [S(0, P_proj(2.8, 900, 40, 0.6, shape='wall', el_='barrier', pierce=10, knock=900, destroy=3.0))], desc="Таран барьером.", sfx='block', scale='fruit'),
    'barrier_ult': MV("Барьер Бол — Вершина", 40.0, 60, [S(0, P_shield(6.0, 1.0, True)), S(0, P_nova(5.0, 250, 'self', 0, 1500, 300, 'barrier', vis='barrier_burst'))], desc="УЛЬТА. Барьер-взрыв.", ult=True, sfx='block', scale='fruit'),
    # ==== ДОКУ ДОКУ ====
    'hydra': MV("Гидра", 6.0, 25, [S(0.1, P_proj(2.4, 800, 26, 0.9, shape='dragon_head', el_='poison', explode=90))], desc="Ядовитый дракон.", sfx='fire', scale='fruit'),
    'poison_cloud': MV("Ядовитое Облако", 10.0, 25, [S(0, P_zone(0.45, 200, 5.0, 0.3, 'cursor', 'poison', vis='poison'))], desc="Облако яда.", sfx='whoosh', scale='fruit'),
    'venom_demon': MV("Веном Демон", 45.0, 70, [S(0, P_zone(0.9, 300, 6.0, 0.25, 'self', 'poison', vis='poison', destroy=1.5))], desc="УЛЬТА. Демон из яда.", ult=True, sfx='fire', scale='fruit'),
    # ==== ГАСУ ГАСУ ====
    'gastanet': MV("Гастанет", 6.0, 24, [S(0.2, P_nova(3.0, 120, 'cursor', 0.3, 700, 200, 'gas', vis='explosion'))], desc="Взрыв газа.", sfx='explosion', scale='fruit', tele='circle'),
    'shinokuni': MV("Синокуни", 45.0, 70, [S(0, P_zone(1.0, 360, 6.0, 0.3, 'cursor', 'gas', vis='poison', destroy=1.0))], desc="УЛЬТА. Смертоносный газ.", ult=True, sfx='whoosh', scale='fruit'),
    # ==== ДОРУ ДОРУ (воск) ====
    'wax_wall': MV("Восковая Стена", 10.0, 20, [S(0, P_shield(3.0, 0.8))], desc="Броня из воска.", sfx='block', scale='fruit'),
    'wax_cage': MV("Восковая Клетка", 8.0, 25, [S(0, P_nova(1.0, 90, 'cursor', 0.2, 0, 0, 'wax', vis='wax', status=('bind', 2.5, 1.0)))], desc="Заточает в воск.", sfx='block', scale='fruit'),
    # ==== БОМУ БОМУ ====
    'bomb_kick': MV("Бомбо Пинок", 3.0, 14, [S(0, P_melee(2.5, 90, 110, 500, 100, 'kick', 'bomb', 0.4, explode=70))], desc="Взрывной пинок.", sfx='explosion', scale='fruit'),
    'nose_fancy': MV("Нос Фэнси Пушка", 4.0, 14, [S(0, P_proj(2.0, 900, 10, 0.7, shape='orb', el_='bomb', explode=80))], desc="Взрывная... козявка.", sfx='explosion', scale='fruit'),
    # ==== ХОРО ХОРО ====
    'negative_hollow': MV("Негатив Холлоу", 6.0, 22, [S(0, P_proj(0.3, 400, 18, 2.5, n=3, spread=0.6, shape='ghost', el_='ghost', homing=3, pierce=1))], desc="Призраки, лишающие воли к борьбе.", sfx='whoosh', scale='fruit'),
    'toku_hollow': MV("Току Холлоу", 9.0, 28, [S(0, P_proj(3.0, 350, 30, 2.0, shape='ghost', el_='bomb', homing=3, explode=130))], desc="Взрывающийся призрак.", sfx='explosion', scale='fruit'),
    # ==== БАКУ БАКУ ====
    'baku_munch': MV("Баку Баку Укус", 3.0, 14, [S(0, P_melee(2.4, 80, 90, 300, 0, 'bite', 'phys', 0.4, destroy=3.0))], desc="Пожирает всё на пути.", sfx='eat', scale='fruit'),
    'wapol_cannon': MV("Вапол Пушка", 5.0, 20, [S(0.2, P_proj(2.5, 800, 18, 0.8, shape='cannonball', el_='bomb', explode=100))], desc="Пушка изо рта.", sfx='cannon', scale='fruit'),
    # ==== СУПА СУПА ====
    'spa_blade': MV("Лезвия Тела", 2.5, 12, [S(0, P_melee(2.2, 90, 160, 300, 0, 'slash', 'sword', 0.3))], desc="Тело-клинок.", sfx='slash', scale='fruit'),
    'atomic_spa': MV("Атомный Спа", 6.0, 25, [S(0, P_dash(2.8, 300, 2400, 60, 'sword', 500))], desc="Режущий рывок.", sfx='slash', scale='fruit'),
    # ==== БАНЭ БАНЭ ====
    'spring_hopper': MV("Спринг Хоппер", 4.0, 15, [S(0, P_dash(2.2, 360, 2400, 50, 'phys', 500))], desc="Отскок пружинами.", sfx='stretch', scale='fruit'),
    'spring_snipe': MV("Спринг Снайп", 6.0, 22, [S(0.1, P_proj(2.4, 1300, 16, 0.5, shape='fist', el_='phys', knock=700, stretch=True))], desc="Пружинный удар.", sfx='stretch', scale='fruit'),
    # ==== ГОМУ‑копия? нет. ИСИ ИСИ (Пика) ====
    'stone_fist': MV("Каменный Кулак", 7.0, 28, [S(0.3, P_nova(3.6, 130, 'cursor', 0.35, 900, 300, 'stone', vis='giant_fist', destroy=3.0))], desc="Кулак скалы.", cast=0.3, sfx='quake', scale='fruit', tele='circle'),
    # ==== ХИРА ХИРА ====
    'flag_blade': MV("Флаг-Клинок", 3.0, 14, [S(0, P_proj(1.2, 900, 12, 0.7, n=3, spread=0.3, shape='wind_blade', el_='sword'))], desc="Летящие плоские клинки.", sfx='slash', scale='fruit'),
    # ==== ХОБИ ХОБИ (Шугар) ====
    'toy_touch': MV("Касание Игрушки", 8.0, 25, [S(0, P_melee(1.0, 70, 120, 100, 0, 'palm', 'toy', 0.4, status=('bind', 2.5, 1.0)))], desc="Превращает врага в игрушку.", sfx='beam', scale='fruit'),
    # ==== ХИТО ХИТО: ДАЙБУЦУ ====
    'buddha_wave': MV("Ударная Волна Будды", 7.0, 30, [S(0.2, P_nova(3.5, 230, 'front', 0, 1300, 200, 'light', vis='quake', destroy=3.0))], desc="Золотая ударная волна.", cast=0.3, sfx='quake', scale='fruit'),
    # ==== НИДХОГГ (Локи) ====
    'nidhogg_breath': MV("Дыхание Нидхёгга", 6.0, 30, [S(0.2, P_beam(0.8, 600, 50, 0.7, 'thunder', 0.07, 250, col=(140, 120, 255)))], desc="Дыхание мирового змея.", cast=0.25, sfx='thunder', scale='fruit'),
    'ragnir_smash': MV("Удар Рагнира", 8.0, 35, [S(0.3, P_nova(4.5, 170, 'front', 0, 1500, 400, 'thunder', vis='club_smash', destroy=4.0))], desc="Громовой молот великанов.", cast=0.35, sfx='thunder', scale='fruit', tele='circle'),
    'nidhogg_form': MV("Облик Нидхёгга", 50.0, 80, [S(0, P_buff(18, 1.7, 1.6, 1.1, 0.01, (140, 120, 255), form='dragon'))], desc="УЛЬТА. Превращение в дракона.", ult=True, sfx='thunder', scale='fruit'),
    # ==== ЮКИ ЮКИ ====
    'kamakura': MV("Камакура", 9.0, 22, [S(0, P_zone(0.3, 170, 4.0, 0.35, 'cursor', 'snow', slow=0.6, vis='blizzard'))], desc="Снежная ловушка.", sfx='ice', scale='fruit'),
    'snow_rabbit': MV("Снежные Кролики", 4.0, 16, [S(0, P_proj(0.9, 900, 10, 0.8, n=5, spread=0.5, shape='orb', el_='snow'))], desc="Снежные снаряды.", sfx='ice', scale='fruit'),
    # ==== ГОМУ‑ОРОСИ: СВЯТЫЕ РЫЦАРИ (Элбаф) ====
    'thorn_lash': MV("Шипастые Лозы", 4.0, 18, [S(0.1, P_wave(2.4, 8, 60, 0.04, 55, 'thorn', 'spike'))], desc="Лозы из шипов вырастают из земли.", sfx='slash', scale='fruit'),
    'thorn_prison': MV("Тюрьма Терновника", 10.0, 30, [S(0.1, P_zone(0.5, 180, 4.0, 0.3, 'cursor', 'thorn', vis='arms_field', slow=0.7))], desc="Клетка из шипов.", sfx='slash', scale='fruit'),
    'nightmare_mist': MV("Кошмарный Туман", 10.0, 30, [S(0.1, P_zone(0.4, 200, 4.0, 0.3, 'cursor', 'nightmare', vis='poison'))], desc="Туман, погружающий в кошмары.", sfx='whoosh', scale='fruit'),
    'holy_arrow': MV("Священные Стрелы", 4.0, 18, [S(0, P_proj(1.0, 1500, 7, 0.7, n=7, spread=0.3, shape='spear', el_='light', burst=0.04))], desc="Град небесных стрел.", sfx='beam', scale='fruit'),
    'saturn_legs': MV("Паучьи Лапы Гюки", 5.0, 22, [S(0.15, P_wave(2.6, 6, 70, 0.05, 60, 'poison', 'spike'))], desc="Гигантские лапы пронзают землю.", sfx='slash', scale='fruit'),
    'saturn_eyes': MV("Взор Гюки", 8.0, 30, [S(0.2, P_beam(0.8, 650, 40, 0.6, 'poison', 0.07, 200, col=(255, 60, 120)))], desc="Луч из глаз демона-быка.", cast=0.25, sfx='beam', scale='fruit'),
    'gorosei_reg': MV("Бессмертие Пятерых", 20.0, 0, [S(0, P_heal(0.18, (255, 60, 120)))], desc="Мгновенная регенерация.", sfx='haki', scale='fruit'),
    'shamrock_slash': MV("Клинок Проклятого Близнеца", 5.0, 22, [S(0.1, P_proj(2.6, 1300, 26, 0.6, shape='slash_wave', el_='conq', pierce=99))], desc="Летящий удар, окутанный хаки.", sfx='slash', scale='atk'),
}

# ------------------ БАЗОВЫЕ И СТИЛЕВЫЕ ПРИЁМЫ ------------------
MOVES.update({
    # Кулачный бой
    'brawl_haymaker': MV("Сокрушающий Хук", 4.0, 14, [S(0.1, P_melee(2.6, 80, 100, 700, 200, 'punch', 'phys', 0.5))], desc="Мощный размашистый удар."),
    'brawl_spin': MV("Вихрь Кулаков", 7.0, 22, [S(0, P_melee(2.0, 120, 360, 500, 100, 'spin', 'phys', 0.4)), S(0.15, P_melee(2.0, 120, 360, 500, 100, 'spin', 'phys', 0.4))], desc="Удар с разворота по всем вокруг."),
    'brawl_ground': MV("Удар о Землю", 9.0, 28, [S(0.2, P_nova(3.0, 170, 'self', 0, 700, 300, 'quake', vis='quake', destroy=2.0))], cast=0.3, desc="Удар по земле — ударная волна.", sfx='quake'),
    'brawl_ult': MV("Кулак Неукротимой Воли", 40.0, 60, [S(0.3, P_nova(8.0, 180, 'front', 0, 1500, 500, 'haki', vis='giant_fist', destroy=4.0))], ult=True, cast=0.35, desc="УЛЬТА. Удар, вложивший всю волю.", sfx='hit_heavy', tele='circle'),
    # Чёрная Нога
    'collier': MV("Колье Шот", 3.0, 14, [S(0, P_melee(2.4, 85, 90, 600, 250, 'kick', 'phys', 0.4))], desc="Удар ногой в шею, подбрасывающий врага."),
    'concasse': MV("Конкассе", 6.0, 20, [S(0.1, P_nova(3.0, 110, 'cursor', 0.15, 600, 0, 'phys', vis='stomp', range=260, jump=True))], desc="Прыжок и удар пяткой сверху.", sfx='hit_heavy'),
    'party_table': MV("Парти Тейбл Кик Курс", 8.0, 25, [S(0, P_melee(1.5, 130, 360, 500, 100, 'spin_kick', 'phys', 0.3)), S(0.15, P_melee(1.5, 130, 360, 500, 100, 'spin_kick', 'phys', 0.3)), S(0.3, P_melee(1.5, 130, 360, 600, 100, 'spin_kick', 'phys', 0.3))], desc="Вращающиеся удары ногами."),
    'diable_jambe': MV("Дьябль Джамб", 25.0, 25, [S(0, P_buff(14, 1.4, 1.0, 1.15, 0, (255, 110, 40), form='fire_legs', el_override='fire'))], desc="Раскалённые ноги: удары поджигают.", sfx='fire'),
    'ifrit_jambe': MV("Ифрит Джамб: Гуляш", 40.0, 60, [S(0, P_dash(6.0, 450, 3000, 70, 'blue_fire', 1100, destroy=3.0))], ult=True, desc="УЛЬТА. Голубое пламя — сокрушительный пинок.", sfx='fire'),
    # Один меч
    'iai_shishi': MV("Иай: Шиши Сонсон", 4.0, 16, [S(0, P_dash(2.8, 300, 3000, 50, 'sword', 400))], desc="Молниеносный удар из ножен.", sfx='slash'),
    'flying_slash': MV("Летящий Удар", 3.0, 14, [S(0, P_proj(1.8, 1100, 20, 0.6, shape='slash_wave', el_='sword', pierce=6))], desc="Режущая волна воздуха.", sfx='slash'),
    'sword_whirl': MV("Вихрь Клинка", 7.0, 24, [S(0, P_melee(1.8, 130, 360, 400, 0, 'spin_slash', 'sword', 0.3)), S(0.18, P_melee(1.8, 130, 360, 400, 0, 'spin_slash', 'sword', 0.3))], desc="Круговой удар мечом."),
    'one_ult': MV("Ичиторю: Дайшинкан", 40.0, 60, [S(0.25, P_proj(7.0, 1500, 60, 0.7, shape='slash_wave', el_='sword', pierce=99, destroy=5.0))], ult=True, cast=0.35, desc="УЛЬТА. Удар, рассекающий корабли.", sfx='slash'),
    # Два меча
    'nito_rashomon': MV("Нитору: Расёмон", 5.0, 18, [S(0, P_dash(3.0, 320, 3000, 55, 'sword', 500))], desc="Двойной режущий рывок.", sfx='slash'),
    'nito_crosscut': MV("Крест Ветра", 4.0, 16, [S(0, P_proj(1.4, 1100, 18, 0.6, n=2, spread=0.25, shape='slash_wave', el_='sword', pierce=4))], desc="Две перекрещенные волны.", sfx='slash'),
    'nito_hawk': MV("Ястребиная Волна", 7.0, 24, [S(0, P_proj(1.0, 1000, 14, 0.7, n=5, spread=0.7, shape='slash_wave', el_='sword', pierce=3))], desc="Веер режущих волн.", sfx='slash'),
    'nito_ult': MV("Нитору: Ракудай Росай", 40.0, 60, [S(0.25, P_barrage(0.9, 14, 0.9, 150, 140, 'sword', 'slashes'))], ult=True, cast=0.3, desc="УЛЬТА. Буря двух клинков.", sfx='slash', lock=1.0),
    # Три меча (Санторю)
    'oni_giri': MV("Они Гири", 4.0, 16, [S(0, P_dash(3.2, 320, 3200, 55, 'sword', 500))], desc="Демонический тройной разрез.", sfx='slash'),
    'tora_gari': MV("Тора Гари", 5.0, 18, [S(0.1, P_melee(3.0, 100, 100, 700, 0, 'slash', 'sword', 0.5, off=30))], desc="Охота на тигра — удар сверху.", sfx='slash'),
    'pound_ho': MV("108 Фунтовая Пушка", 4.0, 18, [S(0, P_proj(2.2, 1200, 24, 0.6, shape='slash_wave', el_='sword', pierce=6, triple=True))], desc="Тройная летящая волна.", sfx='slash'),
    'tatsumaki': MV("Санторю: Тацумаки", 8.0, 28, [S(0, P_zone(0.5, 150, 1.6, 0.15, 'self', 'wind', vis='tornado', follow=True))], desc="Режущий торнадо вокруг тебя.", sfx='whoosh'),
    'asura': MV("Киухиру: Асура", 30.0, 40, [S(0, P_buff(12, 1.8, 1.2, 1.1, 0, (60, 40, 70), form='asura'))], desc="Девять мечей. Три головы. Шесть рук.", sfx='haki'),
    'king_of_hell': MV("Санторю Огри: Король Ада", 45.0, 70, [S(0.3, P_dash(9.0, 520, 3600, 110, 'conq', 1400, destroy=5.0))], ult=True, cast=0.35, desc="УЛЬТА. Три тысячи миров — Король Ада.", sfx='slash'),
    # Снайпер
    'kayaku_boshi': MV("Каяку Боси — Взрывная Звезда", 3.0, 12, [S(0, P_proj(1.8, 1200, 9, 0.9, shape='orb', el_='bomb', explode=80))], desc="Взрывной снаряд рогатки."),
    'tabasco': MV("Табаско Боси", 5.0, 14, [S(0, P_proj(0.5, 1000, 9, 0.8, n=3, spread=0.3, shape='orb', el_='fire', status=('stun', 1.0, 1.0)))], desc="Острый соус в глаза!"),
    'pop_green': MV("Поп Грин: Хищное Растение", 9.0, 25, [S(0.2, P_zone(0.5, 140, 4.0, 0.3, 'cursor', 'thorn', vis='arms_field', slow=0.6))], desc="Растение-ловушка.", cast=0.2),
    'fire_bird_star': MV("Звезда Огненной Птицы", 40.0, 60, [S(0.2, P_proj(6.0, 1100, 34, 1.0, shape='bird', el_='fire', pierce=99, explode=140))], ult=True, cast=0.3, desc="УЛЬТА. Огненная птица из рогатки Кабуто.", sfx='fire'),
    # Рокусики
    'shigan': MV("Сиган — Палец-Пуля", 2.0, 10, [S(0, P_melee(2.4, 70, 40, 300, 0, 'finger', 'phys', 0.35, ignore_def=True))], desc="Удар пальцем, пробивающий как пуля."),
    'rankyaku': MV("Ранкяку — Буря Ног", 3.0, 14, [S(0, P_proj(1.8, 1100, 22, 0.6, shape='slash_wave', el_='wind', pierce=5))], desc="Режущий пинок воздухом."),
    'tekkai': MV("Теккай — Стальное Тело", 9.0, 15, [S(0, P_shield(2.5, 0.75))], desc="Тело твёрже стали."),
    'rokuogan': MV("Рокуоган", 40.0, 60, [S(0.3, P_nova(7.0, 160, 'front', 0, 1500, 200, 'phys', vis='shockwave6', ignore_def=True, destroy=3.0))], ult=True, cast=0.35, desc="УЛЬТА. Высшая техника Рокусики.", sfx='hit_heavy'),
    # Карате рыболюдей
    'uchimizu': MV("Утимидзу — Водяные Пули", 2.5, 10, [S(0, P_proj(0.8, 1200, 8, 0.6, n=4, spread=0.3, shape='orb', el_='water'))], desc="Капли воды, бьющие как пули."),
    'samehada': MV("Самэхада Сётэй", 9.0, 15, [S(0, P_shield(2.5, 0.8, True))], desc="Ладонь акульей кожи — отражает удары."),
    'karakusagawara': MV("Каракусагавара Сэйкэн", 6.0, 22, [S(0.15, P_melee(3.2, 150, 70, 1100, 100, 'water_punch', 'water', 0.6, off=30, ignore_def=True))], desc="Удар, передающий силу через воду в теле врага.", sfx='hit_heavy'),
    'vagabond_drill': MV("Вагабонд Дрилл", 5.0, 20, [S(0, P_dash(2.8, 340, 2600, 60, 'water', 600))], desc="Вращающийся таран."),
    'buraikan': MV("Бураикан — Удар Моря", 40.0, 60, [S(0.3, P_proj(7.0, 900, 60, 0.9, shape='wave', el_='water', pierce=99, knock=1400, destroy=4.0))], ult=True, cast=0.35, desc="УЛЬТА. Удар, поднимающий море.", sfx='splash'),
    # Электро (минки)
    'electro_punch': MV("Электро-Удар", 3.0, 12, [S(0, P_melee(2.4, 85, 90, 400, 0, 'punch', 'electro', 0.4))], desc="Удар электричеством."),
    'electro_dash': MV("Молния Минков", 4.0, 14, [S(0, P_dash(2.2, 340, 2800, 55, 'electro', 400))], desc="Электрический рывок."),
    'electro_burst': MV("Электрический Шторм", 9.0, 28, [S(0, P_nova(2.5, 180, 'self', 0, 600, 100, 'electro', vis='elec_burst'))], desc="Разряд вокруг.", sfx='thunder'),
    'sulong': MV("Форма Сулонг", 45.0, 60, [S(0, P_buff(15, 1.8, 1.2, 1.4, 0, (255, 255, 255), form='sulong'))], ult=True, desc="УЛЬТА. Под полной луной минк становится чудовищем.", sfx='haki'),
    # Окама Кэмпо
    'okama_kick': MV("Окама-Пинок Лебедя", 3.0, 12, [S(0, P_melee(2.6, 90, 90, 500, 200, 'kick', 'phys', 0.4))], desc="Изящный и смертельный пинок."),
    'death_wink': MV("Смертельное Подмигивание", 6.0, 22, [S(0.2, P_proj(2.6, 900, 30, 0.6, shape='orb', el_='wind', knock=1000, pierce=5))], desc="Подмигивание, сносящее с ног.", sfx='whoosh'),
    'hell_wink': MV("Адское Подмигивание", 40.0, 60, [S(0.3, P_beam(2.0, 650, 80, 0.5, 'wind', 0.06, 900))], ult=True, cast=0.3, desc="УЛЬТА. Ураган из глаз.", sfx='whoosh'),
    # Клима-Такт
    'thunder_tempo': MV("Сандерболт Темпо", 5.0, 18, [S(0.3, P_nova(2.8, 80, 'cursor', 0.4, 200, 0, 'thunder', vis='bolt_pillar'))], desc="Молния из облака.", sfx='thunder', tele='circle'),
    'mirage_tempo': MV("Мираж Темпо", 10.0, 15, [S(0, P_summon('mirage', 2, 6))], desc="Миражи-двойники отвлекают врагов."),
    'cyclone_tempo': MV("Циклон Темпо", 7.0, 22, [S(0, P_proj(0.4, 500, 40, 1.6, shape='tornado', el_='wind', pierce=99, tick=0.15, pull=150))], desc="Торнадо."),
    'zeus_breeze': MV("Зевс Бриз Темпо", 40.0, 60, [S(0.4, P_rain(2.8, 16, 1.8, 280, 70, 'cursor', 'thunder', 'bolt'))], ult=True, cast=0.4, desc="УЛЬТА. Зевс бьёт молниями.", sfx='thunder'),
    # Кулак Любви (Гарп)
    'fist_love': MV("Кулак Любви", 3.0, 14, [S(0.05, P_melee(3.0, 90, 80, 900, 300, 'punch', 'haki', 0.6))], desc="Воспитательный удар деда.", sfx='hit_heavy'),
    'cannonball_throw': MV("Метание Ядер", 6.0, 20, [S(0, P_proj(1.6, 1000, 16, 0.9, n=5, spread=0.5, shape='cannonball', el_='bomb', explode=60, burst=0.08))], desc="Кидает пушечные ядра голыми руками.", sfx='cannon'),
    'galaxy_impact': MV("Гэлакси Импакт", 45.0, 75, [S(0.5, P_nova(10.0, 380, 'front', 0, 1800, 600, 'conq', vis='galaxy', destroy=8.0))], ult=True, cast=0.5, desc="УЛЬТА. Удар, сносящий город.", sfx='explosion'),
    # Рюо (Вано)
    'ryuo_strike': MV("Рюо: Внутреннее Разрушение", 5.0, 20, [S(0.1, P_melee(3.5, 100, 80, 900, 200, 'punch', 'haki', 0.5, ignore_def=True, ryou=True, off=25))], desc="Хаки течёт внутрь врага и рвёт его изнутри.", sfx='haki'),
    'ryuo_wave': MV("Рюо: Волна Отталкивания", 9.0, 28, [S(0.1, P_nova(2.4, 200, 'self', 0, 1300, 200, 'haki', vis='haki_ring'))], desc="Отталкивает всё вокруг потоком хаки.", sfx='haki'),
    'ryuo_ult': MV("Рюо: Сокрушение Дракона", 45.0, 70, [S(0.35, P_proj(7.0, 1300, 50, 0.6, shape='fist', el_='haki', pierce=99, knock=1600, black=True, destroy=4.0))], ult=True, cast=0.4, desc="УЛЬТА. Кулак Рюо пробивает всё.", sfx='hit_heavy'),
    # Хаки
    'conq_burst': MV("Королевская Воля", 25.0, 0, [S(0, P_nova(0.5, 360, 'self', 0, 600, 0, 'conq', vis='conq', knockout=True))], desc="Королевское хаки: слабые падают без сознания.", sfx='haki', scale='haki'),
})

# ------------------------------------------------------------------
#  СТИЛИ БОЯ
# ------------------------------------------------------------------
# combo: 4 удара: (dmg, r, arc, knock, launch, vis)
STYLES = {
    'brawler': dict(name="Кулачный бой", desc="Чистая сила кулаков. Доступен всем.", weapon=None,
                    combo=[(1.0, 70, 100, 140, 0, 'punch'), (1.0, 70, 100, 140, 0, 'punch'), (1.2, 75, 110, 160, 0, 'punch'), (2.0, 85, 120, 520, 120, 'punch')],
                    heavy=('punch', 'phys'), moves=[(0, 'brawl_haymaker'), (8, 'brawl_spin'), (20, 'brawl_ground'), (40, 'brawl_ult')], mentor=None),
    'blackleg': dict(name="Чёрная Нога", desc="Стиль Зеффа: руки — для готовки, ноги — для боя.", weapon=None,
                     combo=[(1.1, 80, 110, 160, 0, 'kick'), (1.1, 80, 110, 160, 0, 'kick'), (1.3, 85, 140, 180, 0, 'kick'), (2.2, 95, 160, 600, 160, 'kick')],
                     heavy=('kick', 'phys'), moves=[(0, 'collier'), (10, 'concasse'), (20, 'party_table'), (35, 'diable_jambe'), (60, 'ifrit_jambe')], mentor='zeff'),
    'sword1': dict(name="Иттору (Один Меч)", desc="Путь одного клинка.", weapon='sword',
                   combo=[(1.2, 85, 130, 120, 0, 'slash'), (1.2, 85, 130, 120, 0, 'slash'), (1.4, 90, 150, 160, 0, 'slash'), (2.2, 100, 170, 480, 100, 'slash')],
                   heavy=('slash', 'sword'), moves=[(0, 'iai_shishi'), (8, 'flying_slash'), (20, 'sword_whirl'), (40, 'one_ult')], mentor=None),
    'sword2': dict(name="Нитору (Два Меча)", desc="Два клинка — двойной натиск.", weapon='sword',
                   combo=[(1.0, 85, 140, 110, 0, 'slash'), (1.0, 85, 140, 110, 0, 'slash'), (1.0, 85, 140, 110, 0, 'slash'), (2.4, 100, 180, 500, 100, 'slash')],
                   heavy=('slash', 'sword'), moves=[(0, 'nito_rashomon'), (10, 'nito_crosscut'), (22, 'nito_hawk'), (42, 'nito_ult')], mentor=None),
    'sword3': dict(name="Санторю (Три Меча)", desc="Стиль Ророноа Зоро: третий меч во рту.", weapon='sword',
                   combo=[(1.15, 90, 150, 130, 0, 'slash'), (1.15, 90, 150, 130, 0, 'slash'), (1.3, 95, 170, 160, 0, 'slash'), (2.6, 110, 200, 560, 140, 'slash')],
                   heavy=('slash', 'sword'), moves=[(0, 'oni_giri'), (8, 'tora_gari'), (15, 'pound_ho'), (28, 'tatsumaki'), (45, 'asura'), (65, 'king_of_hell')], mentor='mihawk'),
    'sniper': dict(name="Снайпер", desc="Рогатка и смекалка. Базовые атаки — выстрелы.", weapon=None, ranged=True,
                   combo=[(0.9, 0, 0, 100, 0, 'shot'), (0.9, 0, 0, 100, 0, 'shot'), (0.9, 0, 0, 100, 0, 'shot'), (1.6, 0, 0, 300, 0, 'shot')],
                   heavy=('shot', 'phys'), moves=[(0, 'kayaku_boshi'), (6, 'tabasco'), (18, 'pop_green'), (40, 'fire_bird_star')], mentor=None),
    'rokushiki': dict(name="Рокусики", desc="Шесть сверхчеловеческих техник Правительства. Рывок — Сору.", weapon=None, soru=True,
                      combo=[(1.1, 75, 90, 140, 0, 'punch'), (1.1, 75, 90, 140, 0, 'kick'), (1.3, 80, 100, 170, 0, 'finger'), (2.2, 90, 120, 520, 150, 'kick')],
                      heavy=('kick', 'wind'), moves=[(0, 'shigan'), (8, 'rankyaku'), (18, 'tekkai'), (45, 'rokuogan')], mentor='cp9'),
    'fishman_karate': dict(name="Карате Рыболюдей", desc="Управление водой в воздухе и в теле врага.", weapon=None,
                           combo=[(1.1, 80, 100, 160, 0, 'punch'), (1.1, 80, 100, 160, 0, 'punch'), (1.3, 85, 110, 180, 0, 'punch'), (2.3, 95, 130, 650, 100, 'water_punch')],
                           heavy=('water_punch', 'water'), moves=[(0, 'uchimizu'), (8, 'vagabond_drill'), (18, 'samehada'), (30, 'karakusagawara'), (50, 'buraikan')], mentor='jinbe'),
    'electro': dict(name="Электро", desc="Врождённая сила народа минков.", weapon=None,
                    combo=[(1.0, 75, 100, 140, 0, 'punch'), (1.0, 75, 100, 140, 0, 'kick'), (1.2, 80, 110, 160, 0, 'punch'), (2.1, 90, 130, 520, 120, 'kick')],
                    heavy=('punch', 'electro'), el='electro', moves=[(0, 'electro_punch'), (8, 'electro_dash'), (20, 'electro_burst'), (50, 'sulong')], mentor='minks'),
    'okama': dict(name="Окама Кэмпо", desc="Балетное искусство боя. Удары ногами, полными страсти.", weapon=None,
                  combo=[(1.1, 85, 110, 150, 0, 'kick'), (1.1, 85, 110, 150, 0, 'kick'), (1.4, 90, 130, 180, 0, 'kick'), (2.3, 95, 150, 600, 160, 'kick')],
                  heavy=('kick', 'phys'), moves=[(0, 'okama_kick'), (12, 'death_wink'), (45, 'hell_wink')], mentor='ivankov'),
    'clima': dict(name="Клима-Такт", desc="Наука погоды. Базовые атаки — разряды.", weapon='clima', ranged=True,
                  combo=[(0.85, 0, 0, 90, 0, 'zap'), (0.85, 0, 0, 90, 0, 'zap'), (0.85, 0, 0, 90, 0, 'zap'), (1.5, 0, 0, 250, 0, 'zap')],
                  heavy=('zap', 'thunder'), el='thunder', moves=[(0, 'thunder_tempo'), (10, 'mirage_tempo'), (20, 'cyclone_tempo'), (42, 'zeus_breeze')], mentor=None),
    'fist_love': dict(name="Кулак Любви", desc="Стиль Монки Д. Гарпа — Героя Дозора.", weapon=None,
                      combo=[(1.3, 80, 100, 200, 0, 'punch'), (1.3, 80, 100, 200, 0, 'punch'), (1.5, 85, 110, 240, 0, 'punch'), (2.8, 95, 130, 800, 200, 'punch')],
                      heavy=('punch', 'haki'), moves=[(0, 'fist_love'), (15, 'cannonball_throw'), (50, 'galaxy_impact')], mentor='garp'),
    'ryuo': dict(name="Рюо", desc="Искусство течения хаки страны Вано.", weapon=None,
                 combo=[(1.2, 80, 100, 200, 0, 'punch'), (1.2, 80, 100, 200, 0, 'punch'), (1.4, 85, 110, 220, 0, 'punch'), (2.5, 95, 130, 700, 150, 'punch')],
                 heavy=('punch', 'haki'), moves=[(0, 'ryuo_strike'), (12, 'ryuo_wave'), (40, 'ryuo_ult')], mentor='hyogoro'),
}

# ------------------------------------------------------------------
#  ДЬЯВОЛЬСКИЕ ФРУКТЫ
# ------------------------------------------------------------------
# moves: [(mastery, move_id)], awak: пробуждение (buff)
FRUITS = {
    'gomu': dict(name="Гому Гому но Ми", real="Хито Хито но Ми, модель: Ника", type="Мифический Зоан", col=(150, 60, 160), rarity=5,
                 desc="Тело из резины... или фрукт Бога Солнца Ники? Иммунитет к молниям, сопротивление ударам.",
                 moves=[(0, 'gomu_pistol'), (5, 'gomu_gatling'), (12, 'gomu_bazooka'), (20, 'gear2'), (30, 'gear3'), (45, 'gear4'), (55, 'red_roc'),
                        (75, 'nika_dawn'), (80, 'nika_grab'), (85, 'nika_lightning'), (90, 'bajrang_gun')],
                 awak=dict(name="Гир Пятый — Бог Солнца Ника", form='gear5', dmg=1.8, defn=1.6, spd=1.3, dur=25, aura=(255, 255, 255)),
                 passive=dict(immune='thunder', blunt=0.5), element='rubber', where="Сабаоди (аукцион) / Эгхэд"),
    'mera': dict(name="Мера Мера но Ми", type="Логия", col=(240, 120, 40), rarity=4, logia='fire',
                 desc="Тело из огня. Атаки без хаки проходят насквозь.",
                 moves=[(0, 'hiken'), (8, 'higan'), (18, 'hibashira'), (30, 'enjomo'), (50, 'entei')],
                 awak=dict(name="Пробуждение: Огненный Мир", form='flame', dmg=1.6, defn=1.3, spd=1.15, dur=22, aura=(255, 140, 40), spread_terrain='fire'),
                 element='fire', where="Дрессроза (Колизей)"),
    'hie': dict(name="Хие Хие но Ми", type="Логия", col=(120, 200, 255), rarity=4, logia='ice',
                desc="Тело изо льда. Может заморозить даже море.",
                moves=[(0, 'ice_saber'), (8, 'ice_partisan'), (18, 'ice_time'), (32, 'pheasant_beak'), (50, 'ice_age')],
                awak=dict(name="Пробуждение: Вечная Мерзлота", form='ice', dmg=1.5, defn=1.5, spd=1.1, dur=22, aura=(150, 220, 255), spread_terrain='ice'),
                element='ice', where="Панк Хазард"),
    'magu': dict(name="Магу Магу но Ми", type="Логия", col=(220, 60, 30), rarity=5, logia='magma',
                 desc="Магма — сильнейшая атакующая логия. Сжигает даже огонь.",
                 moves=[(0, 'dai_funka'), (10, 'inugami'), (22, 'magma_pool'), (50, 'ryusei_kazan')],
                 awak=dict(name="Пробуждение: Вулканический Ад", form='magma', dmg=1.8, defn=1.4, spd=1.0, dur=22, aura=(255, 80, 20), spread_terrain='lava'),
                 element='magma', where="Маринфорд (после войны)"),
    'pika': dict(name="Пика Пика но Ми", type="Логия", col=(255, 230, 90), rarity=5, logia='light',
                 desc="Свет. Быстрее всех в мире.",
                 moves=[(0, 'ama_no_murakumo'), (6, 'yata_no_kagami'), (15, 'yasakani'), (30, 'light_kick'), (50, 'yasakani_rain')],
                 awak=dict(name="Пробуждение: Сияние", form='light', dmg=1.5, defn=1.2, spd=1.6, dur=22, aura=(255, 240, 120)),
                 element='light', where="Эгхэд"),
    'goro': dict(name="Горо Горо но Ми", type="Логия", col=(120, 170, 255), rarity=5, logia='thunder',
                 desc="Молния. Сила «бога» Скайпии.",
                 moves=[(0, 'sango'), (8, 'enel_tp'), (18, 'el_thor'), (30, 'kari'), (50, 'raigo')],
                 awak=dict(name="Пробуждение: Амару", form='thunder', dmg=1.7, defn=1.3, spd=1.3, dur=22, aura=(140, 200, 255)),
                 element='thunder', where="Скайпия (Храм Бога)"),
    'suna': dict(name="Суна Суна но Ми", type="Логия", col=(220, 190, 120), rarity=3, logia='sand',
                 desc="Песок. Иссушает всё живое. Слабость — вода.",
                 moves=[(0, 'desert_spada'), (8, 'sables'), (20, 'ground_death'), (45, 'desert_girasole')],
                 awak=dict(name="Пробуждение: Пустыня", form='sand', dmg=1.5, defn=1.3, spd=1.1, dur=22, aura=(230, 200, 130), spread_terrain='sand'),
                 element='sand', where="Алабаста (подземелье Рейнбейса)"),
    'gura': dict(name="Гура Гура но Ми", type="Парамеция", col=(230, 230, 240), rarity=5,
                 desc="Сила, способная уничтожить мир. Землетрясения.",
                 moves=[(0, 'quake_punch'), (12, 'kabutowari'), (25, 'gura_shock'), (50, 'seaquake')],
                 awak=dict(name="Пробуждение: Конец Света", form='quake', dmg=1.9, defn=1.3, spd=1.0, dur=22, aura=(220, 230, 255)),
                 element='quake', where="Маринфорд / Хатиносу"),
    'yami': dict(name="Ями Ями но Ми", type="Логия", col=(60, 20, 80), rarity=5, logia='dark_special',
                 desc="Тьма. Поглощает всё и отменяет силы фруктов. Носитель может съесть второй фрукт!",
                 moves=[(0, 'kurouzu'), (10, 'liberation'), (22, 'black_hole'), (50, 'black_vortex')],
                 awak=dict(name="Пробуждение: Бездна", form='dark', dmg=1.7, defn=1.2, spd=1.0, dur=22, aura=(110, 50, 150)),
                 element='dark', where="Хатиносу / Импел Даун (уровень 6)"),
    'ope': dict(name="Опе Опе но Ми", type="Парамеция", col=(230, 160, 200), rarity=5,
                desc="Сила хирурга. Комната, в которой ты — бог.",
                moves=[(0, 'room'), (0, 'shambles'), (12, 'injection_shot'), (25, 'gamma_knife'), (50, 'puncture_wille')],
                awak=dict(name="Пробуждение: K-Room", form='room', dmg=1.6, defn=1.2, spd=1.2, dur=22, aura=(120, 180, 255)),
                element='room', where="Панк Хазард / Дрессроза"),
    'ito': dict(name="Ито Ито но Ми", type="Парамеция", col=(255, 150, 210), rarity=4,
                desc="Нити, способные резать скалы и управлять людьми.",
                moves=[(0, 'tamaito'), (8, 'overheat'), (18, 'parasite'), (30, 'goshikito'), (50, 'birdcage')],
                awak=dict(name="Пробуждение: Мир Нитей", form='string', dmg=1.6, defn=1.3, spd=1.2, dur=22, aura=(255, 200, 230)),
                element='string', where="Дрессроза (Королевский дворец)"),
    'mochi': dict(name="Моти Моти но Ми", type="Особая Парамеция", col=(240, 230, 210), rarity=4,
                  desc="Моти — особая парамеция, ведущая себя как логия.",
                  moves=[(0, 'mochi_tsuki'), (8, 'zan_giri'), (20, 'power_mochi'), (50, 'buzz_cut')],
                  awak=dict(name="Пробуждение: Мир Моти", form='mochi', dmg=1.6, defn=1.5, spd=1.1, dur=22, aura=(250, 240, 220)),
                  element='mochi', where="Остров Пирога (Зеркальный мир)"),
    'moku': dict(name="Моку Моку но Ми", type="Логия", col=(220, 220, 225), rarity=3, logia='smoke',
                 desc="Дым. Ловит и сковывает.",
                 moves=[(0, 'white_blow'), (8, 'white_launcher'), (20, 'white_snake'), (45, 'white_out')],
                 awak=dict(name="Пробуждение: Белый Мир", form='smoke', dmg=1.4, defn=1.4, spd=1.2, dur=22, aura=(240, 240, 245)),
                 element='smoke', where="Логтаун"),
    'bara': dict(name="Бара Бара но Ми", type="Парамеция", col=(230, 60, 60), rarity=2,
                 desc="Разделение тела. Иммунитет к режущим ударам!",
                 moves=[(0, 'bara_cannon'), (10, 'bara_festival'), (20, 'muggy_ball'), (40, 'bara_ult')],
                 awak=dict(name="Пробуждение: Великий Шут", form='clown', dmg=1.4, defn=1.3, spd=1.2, dur=22, aura=(255, 120, 120)),
                 passive=dict(immune='sword'), element='phys', where="Оранж Таун"),
    'nikyu': dict(name="Никю Никю но Ми", type="Парамеция", col=(255, 170, 200), rarity=5,
                  desc="Лапы, отталкивающие всё — даже боль и усталость.",
                  moves=[(0, 'paw_shot'), (8, 'paw_tp'), (20, 'tsuppari'), (50, 'ursus_shock')],
                  awak=dict(name="Пробуждение: Тиран", form='paw', dmg=1.6, defn=1.6, spd=1.2, dur=22, aura=(255, 180, 210)),
                  element='paw', where="Триллер Барк / Эгхэд"),
    'kage': dict(name="Кагэ Кагэ но Ми", type="Парамеция", col=(80, 50, 110), rarity=3,
                 desc="Власть над тенями.",
                 moves=[(0, 'brick_bat'), (10, 'shadow_box'), (20, 'doppelman'), (45, 'shadow_asgard')],
                 awak=dict(name="Пробуждение: Ночь", form='shadow', dmg=1.5, defn=1.3, spd=1.1, dur=22, aura=(110, 70, 150)),
                 element='shadow', where="Триллер Барк"),
    'zushi': dict(name="Дзуси Дзуси но Ми", type="Парамеция", col=(140, 90, 220), rarity=4,
                  desc="Гравитация. Притягивает метеориты с неба.",
                  moves=[(0, 'gravity_blade'), (12, 'gravity_press'), (50, 'meteor_fall')],
                  awak=dict(name="Пробуждение: Сила Небес", form='gravity', dmg=1.6, defn=1.3, spd=1.0, dur=22, aura=(170, 120, 255)),
                  element='gravity', where="Дрессроза"),
    'soru': dict(name="Сору Сору но Ми", type="Парамеция", col=(255, 120, 180), rarity=5,
                 desc="Власть над душами. Создание хоми.",
                 moves=[(0, 'prometheus'), (8, 'zeus'), (20, 'soul_pocus'), (50, 'heavenly_fire')],
                 awak=dict(name="Пробуждение: Императрица", form='homies', dmg=1.7, defn=1.6, spd=1.0, dur=22, aura=(255, 150, 200)),
                 element='soul', where="Остров Пирога"),
    'uo': dict(name="Уо Уо но Ми, модель: Сэйрю", type="Мифический Зоан", col=(60, 120, 230), rarity=5, zoan=True,
               desc="Лазурный дракон — сильнейшее существо.",
               moves=[(0, 'kaifu'), (10, 'bolo_breath'), (22, 'thunder_bagua'), (50, 'dragon_form')],
               awak=dict(name="Пробуждение: Дракон Онигасимы", form='dragon', dmg=1.9, defn=1.8, spd=1.1, dur=22, aura=(90, 150, 255)),
               element='fire', where="Вано (Онигасима)"),
    'tori_phoenix': dict(name="Тори Тори но Ми, модель: Феникс", type="Мифический Зоан", col=(60, 170, 255), rarity=5, zoan=True,
                         desc="Голубое пламя возрождения. Регенерация.",
                         moves=[(0, 'phoenix_brand'), (10, 'phoenix_heal'), (20, 'phoenix_wings'), (45, 'phoenix_ult')],
                         awak=dict(name="Пробуждение: Вечное Пламя", form='phoenix', dmg=1.4, defn=1.4, spd=1.4, dur=24, aura=(80, 180, 255), regen=0.02),
                         passive=dict(regen=0.004), element='phoenix', where="Сфинкс / Вано"),
    'inu_makami': dict(name="Ину Ину но Ми, модель: Окути но Маками", type="Мифический Зоан", col=(220, 240, 255), rarity=4, zoan=True,
                       desc="Божественный волк-хранитель. Лёд и хаки.",
                       moves=[(0, 'namuji'), (12, 'blizzard'), (45, 'yamato_ult')],
                       awak=dict(name="Пробуждение: Хранитель Вано", form='wolf', dmg=1.6, defn=1.5, spd=1.3, dur=22, aura=(220, 240, 255)),
                       element='ice', where="Вано (Кури)"),
    'ryu_ptera': dict(name="Рю Рю но Ми, модель: Птеранодон", type="Древний Зоан", col=(80, 60, 50), rarity=3, zoan=True,
                      desc="Древний летающий ящер. Броня и скорость.",
                      moves=[(0, 'ptera_dive'), (10, 'tempura_udon'), (40, 'king_ult')],
                      awak=dict(name="Пробуждение: Древний Ящер", form='beast', dmg=1.5, defn=1.6, spd=1.3, dur=22, aura=(255, 140, 60)),
                      element='fire', where="Вано (Онигасима)"),
    'neko_leopard': dict(name="Нэко Нэко но Ми, модель: Леопард", type="Плотоядный Зоан", col=(230, 190, 80), rarity=3, zoan=True,
                         desc="Плотоядный зоан. Убийственная скорость.",
                         moves=[(0, 'leopard_claw'), (8, 'leopard_pounce'), (20, 'leopard_form'), (45, 'rokuogan_lucci')],
                         awak=dict(name="Пробуждение: Ночной Хищник", form='beast', dmg=1.6, defn=1.4, spd=1.3, dur=22, aura=(255, 230, 150)),
                         element='blood', where="Эниес Лобби"),
    'hana': dict(name="Хана Хана но Ми", type="Парамеция", col=(255, 130, 180), rarity=3,
                 desc="Части тела расцветают где угодно.",
                 moves=[(0, 'clutch'), (10, 'mil_fleur'), (22, 'gigantesco'), (45, 'demonio')],
                 awak=dict(name="Пробуждение: Цветущий Демон", form='petal', dmg=1.5, defn=1.3, spd=1.1, dur=22, aura=(255, 150, 200)),
                 element='petal', where="Алабаста / Охара"),
    'mero': dict(name="Меро Меро но Ми", type="Парамеция", col=(255, 90, 170), rarity=3,
                 desc="Любовь, превращающая в камень.",
                 moves=[(0, 'pistol_kiss'), (8, 'perfume_femur'), (18, 'slave_arrow'), (45, 'mero_ult')],
                 awak=dict(name="Пробуждение: Императрица Любви", form='love', dmg=1.5, defn=1.3, spd=1.2, dur=22, aura=(255, 120, 190)),
                 element='love', where="Амазон Лили"),
    'bari': dict(name="Бари Бари но Ми", type="Парамеция", col=(170, 220, 255), rarity=2,
                 desc="Непробиваемые барьеры.",
                 moves=[(0, 'barrier'), (8, 'barrier_crash'), (40, 'barrier_ult')],
                 awak=dict(name="Пробуждение: Крепость", form='barrier', dmg=1.3, defn=2.0, spd=1.0, dur=22, aura=(200, 240, 255)),
                 element='barrier', where="Дрессроза (Колизей)"),
    'doku': dict(name="Доку Доку но Ми", type="Парамеция", col=(150, 60, 190), rarity=3,
                 desc="Яд, от которого нет противоядия.",
                 moves=[(0, 'hydra'), (12, 'poison_cloud'), (45, 'venom_demon')],
                 awak=dict(name="Пробуждение: Ядовитый Ад", form='poison', dmg=1.5, defn=1.3, spd=1.0, dur=22, aura=(170, 80, 220), spread_terrain='poison'),
                 element='poison', where="Импел Даун"),
    'gasu': dict(name="Гасу Гасу но Ми", type="Логия", col=(180, 130, 220), rarity=3, logia='gas',
                 desc="Газ. Может убрать кислород из воздуха.",
                 moves=[(0, 'gastanet'), (40, 'shinokuni')],
                 awak=dict(name="Пробуждение: Газовая Планета", form='gas', dmg=1.5, defn=1.3, spd=1.0, dur=22, aura=(200, 150, 240)),
                 element='gas', where="Панк Хазард"),
    'doru': dict(name="Дору Дору но Ми", type="Парамеция", col=(240, 240, 220), rarity=1,
                 desc="Воск, твёрдый как сталь.",
                 moves=[(0, 'wax_wall'), (8, 'wax_cage')],
                 awak=dict(name="Пробуждение: Восковой Замок", form='wax', dmg=1.3, defn=1.6, spd=1.0, dur=20, aura=(250, 250, 230)),
                 element='wax', where="Литл Гарден"),
    'bomu': dict(name="Бому Бому но Ми", type="Парамеция", col=(255, 150, 60), rarity=1,
                 desc="Всё тело — бомба.",
                 moves=[(0, 'bomb_kick'), (6, 'nose_fancy')],
                 awak=dict(name="Пробуждение: Ходячий Взрыв", form='bomb', dmg=1.4, defn=1.1, spd=1.0, dur=20, aura=(255, 180, 80)),
                 element='bomb', where="Виски Пик"),
    'horo': dict(name="Хоро Хоро но Ми", type="Парамеция", col=(240, 200, 240), rarity=2,
                 desc="Призраки, лишающие воли.",
                 moves=[(0, 'negative_hollow'), (12, 'toku_hollow')],
                 awak=dict(name="Пробуждение: Призрачная Принцесса", form='ghost', dmg=1.4, defn=1.2, spd=1.1, dur=22, aura=(250, 220, 250)),
                 element='ghost', where="Триллер Барк"),
    'baku': dict(name="Баку Баку но Ми", type="Парамеция", col=(200, 120, 60), rarity=1,
                 desc="Съесть можно что угодно.",
                 moves=[(0, 'baku_munch'), (6, 'wapol_cannon')],
                 awak=dict(name="Пробуждение: Пожиратель", form='bomb', dmg=1.3, defn=1.4, spd=1.0, dur=20, aura=(220, 150, 80)),
                 element='phys', where="Драм"),
    'supa': dict(name="Супа Супа но Ми", type="Парамеция", col=(200, 200, 210), rarity=2,
                 desc="Тело — клинок.",
                 moves=[(0, 'spa_blade'), (8, 'atomic_spa')],
                 awak=dict(name="Пробуждение: Стальной Человек", form='blade', dmg=1.4, defn=1.5, spd=1.1, dur=20, aura=(220, 220, 240)),
                 passive=dict(immune='sword'), element='sword', where="Алабаста"),
    'bane': dict(name="Банэ Банэ но Ми", type="Парамеция", col=(160, 160, 170), rarity=1,
                 desc="Ноги-пружины.",
                 moves=[(0, 'spring_hopper'), (6, 'spring_snipe')],
                 awak=dict(name="Пробуждение: Пружинный Ад", form='blade', dmg=1.3, defn=1.1, spd=1.4, dur=20, aura=(200, 200, 210)),
                 element='phys', where="Джая"),
    'nidhogg': dict(name="Рю Рю но Ми, модель: Нидхёгг", type="Мифический Зоан", col=(110, 90, 200), rarity=5, zoan=True,
                    desc="Дракон, грызущий корни Мирового Древа. Фрукт принца Эльбафа Локи.",
                    moves=[(0, 'nidhogg_breath'), (15, 'ragnir_smash'), (50, 'nidhogg_form')],
                    awak=dict(name="Пробуждение: Рагнарёк", form='dragon', dmg=1.9, defn=1.7, spd=1.1, dur=22, aura=(150, 120, 255)),
                    element='thunder', where="Эльбаф"),
    'yuki': dict(name="Юки Юки но Ми", type="Логия", col=(240, 245, 255), rarity=2, logia='snow',
                 desc="Снег и вьюга.",
                 moves=[(0, 'snow_rabbit'), (10, 'kamakura')],
                 awak=dict(name="Пробуждение: Снежная Королева", form='ice', dmg=1.4, defn=1.3, spd=1.1, dur=22, aura=(240, 250, 255), spread_terrain='ice'),
                 element='snow', where="Панк Хазард"),
    'ishi': dict(name="Иси Иси но Ми", type="Парамеция", col=(150, 140, 130), rarity=2,
                 desc="Слияние с камнем. Стань великаном из скал.",
                 moves=[(0, 'stone_fist')],
                 awak=dict(name="Пробуждение: Каменный Колосс", form='giant', dmg=1.5, defn=1.8, spd=0.9, dur=22, aura=(170, 160, 150)),
                 element='stone', where="Дрессроза"),
    'hito_daibutsu': dict(name="Хито Хито но Ми, модель: Дайбуцу", type="Мифический Зоан", col=(250, 210, 80), rarity=4, zoan=True,
                          desc="Золотой Будда.",
                          moves=[(0, 'buddha_wave')],
                          awak=dict(name="Пробуждение: Великий Будда", form='giant', dmg=1.6, defn=1.8, spd=0.9, dur=22, aura=(255, 220, 100)),
                          element='light', where="Штаб Дозора"),
}

# Фрукты, которые выпадают/продаются (обычные игроки находят «перерождённые» фрукты)
FRUIT_ORDER = ['bara', 'bomu', 'doru', 'baku', 'bane', 'supa', 'moku', 'suna', 'hana', 'horo', 'kage', 'bari', 'mero', 'neko_leopard',
               'doku', 'gasu', 'yuki', 'hie', 'mera', 'ope', 'ito', 'ishi', 'zushi', 'mochi', 'ryu_ptera', 'inu_makami', 'goro', 'pika',
               'magu', 'gura', 'yami', 'nikyu', 'soru', 'tori_phoenix', 'hito_daibutsu', 'uo', 'gomu', 'nidhogg']

# ==================================================================
#  ДАННЫЕ: ПРЕДМЕТЫ, ВРАГИ, БОССЫ, СПУТНИКИ, НАСТАВНИКИ, ФРАКЦИИ
# ==================================================================
A = default_app

# дополнительные приёмы боссов
MOVES.update({
    'kuro_shakushi': MV("Сякуси — Бесшумная Резня", 8.0, 0, [S(0, P_zone(0.5, 170, 2.0, 0.12, 'self', 'blood', vis='blades', follow=True))], desc="Бешеный вихрь когтей."),
    'jango_hypno': MV("Гипноз: Раз, два... Джанго!", 10.0, 0, [S(0.4, P_nova(0.3, 260, 'self', 0, 0, 0, 'nightmare', vis='soul', status=('sleep', 1.6, 0.9)))], cast=0.5, desc="Усыпляющий гипноз.", tele='circle'),
    'krieg_guns': MV("Пушечный Залп", 4.0, 0, [S(0, P_proj(0.8, 900, 8, 0.8, n=8, spread=0.8, shape='bullet', el_='phys'))], desc="Скрытые пушки на броне."),
    'krieg_mh5': MV("MH5 — Ядовитый Газ", 14.0, 0, [S(0.2, P_zone(0.4, 230, 5.0, 0.35, 'cursor', 'poison', vis='poison'))], desc="Отравляющая бомба."),
    'krieg_spear': MV("Копьё-Зонт", 5.0, 0, [S(0, P_dash(2.4, 300, 2000, 60, 'bomb', 500, explode=80))], desc="Взрывное копьё."),
    'shark_darts': MV("Акула на Дротиках", 5.0, 0, [S(0.1, P_dash(2.8, 380, 2400, 60, 'water', 600))], desc="Таран носом-пилой."),
    'kiribachi': MV("Кирибати", 4.0, 0, [S(0.05, P_melee(2.4, 120, 140, 400, 0, 'slash', 'blood', 0.4))], desc="Пила-меч."),
    'franky_fire': MV("Фреш Файр", 5.0, 0, [S(0.1, P_beam(0.5, 380, 30, 0.5, 'fire', 0.07, 120, col=(255, 140, 40)))], desc="Огнемёт изо рта."),
    'strong_right': MV("Стронг Райт", 4.0, 0, [S(0.05, P_proj(2.2, 1100, 16, 0.5, shape='fist', el_='phys', knock=600, stretch=True))], desc="Кулак на цепи."),
    'coup_de_vent': MV("Ку де Ван", 7.0, 0, [S(0.25, P_proj(2.6, 1000, 40, 0.6, shape='orb', el_='wind', knock=1200, pierce=9))], cast=0.3, desc="Воздушная пушка из рук."),
    'paci_laser': MV("Лазер Пацифисты", 3.5, 0, [S(0.4, P_proj(2.0, 1600, 10, 0.7, shape='light_orb', el_='light', explode=70))], cast=0.45, desc="Луч света.", tele='line'),
    'heavy_slam': MV("Сокрушительный Удар", 4.0, 0, [S(0.35, P_nova(2.8, 130, 'front', 0, 800, 200, 'stone', vis='stomp', destroy=2.0))], cast=0.4, desc="Удар с размаху.", tele='circle'),
    'jack_charge': MV("Таран Мамонта", 6.0, 0, [S(0.2, P_dash(3.0, 460, 1800, 90, 'stone', 900, destroy=3.0))], cast=0.3, desc="Сокрушительный таран.", tele='line'),
    'mato_throw': MV("Мато Мато — Метка", 4.0, 0, [S(0, P_proj(1.0, 700, 12, 2.0, n=4, spread=1.0, shape='rock', el_='phys', homing=5))], desc="Брошенные предметы всегда находят цель."),
    'flower_sword': MV("Цветочный Меч", 4.0, 0, [S(0, P_proj(1.0, 1000, 12, 0.6, n=6, spread=0.5, shape='slash_wave', el_='petal'))], desc="Лепестки-клинки."),
    'diamond_body': MV("Алмазное Тело", 12.0, 0, [S(0, P_shield(3.0, 0.85))], desc="Тело из алмаза."),
    'queen_laser': MV("Лазер Бракиозавра", 5.0, 0, [S(0.3, P_beam(0.6, 600, 26, 0.5, 'light', 0.07, 150, col=(255, 80, 80)))], cast=0.35, desc="Кибер-лазер.", tele='line'),
    'cracker_biscuits': MV("Бисквитные Солдаты", 15.0, 0, [S(0, P_summon('biscuit', 3, 15))], desc="Армия бисквитов."),
    'mihawk_slash': MV("Кокуто: Удар Ёру", 2.5, 0, [S(0.1, P_proj(3.2, 1500, 40, 0.8, shape='slash_wave', el_='sword', pierce=99, destroy=6.0))], cast=0.15, desc="Удар сильнейшего мечника."),
    'kamusari': MV("Камусари — Божественный Уход", 18.0, 0, [S(0.4, P_beam(2.0, 800, 60, 0.4, 'conq', 0.05, 1200, destroy=5.0))], cast=0.5, desc="Удар Шанкса, окутанный королевским хаки.", tele='line', ult=True),
    'dragon_claw': MV("Когти Дракона", 3.0, 0, [S(0, P_melee(2.4, 90, 90, 500, 100, 'claw', 'haki', 0.4))], desc="Драконий коготь Сабо."),
    'gifter_blast': MV("Сила SMILE", 4.0, 0, [S(0.2, P_proj(1.5, 900, 14, 0.7, shape='orb', el_='fire', explode=60))], cast=0.25, desc="Искусственная сила фрукта."),
    'sky_burn': MV("Бёрн Базука", 4.0, 0, [S(0.3, P_proj(1.6, 1000, 14, 0.6, shape='fireball', el_='fire', explode=60))], cast=0.3, desc="Небесная базука."),
    'reject_dial': MV("Реджект Дайл", 12.0, 0, [S(0.2, P_melee(5.0, 80, 70, 900, 200, 'palm', 'quake', 0.8))], cast=0.3, desc="В десять раз сильнее импакт-дайла.", tele='cone'),
    'rifle_shot': MV("Выстрел", 2.5, 0, [S(0.35, P_proj(1.0, 1300, 6, 0.8, shape='bullet', el_='phys'))], cast=0.4, desc="Выстрел из мушкета.", tele='line'),
    'arrow_volley': MV("Залп Стрел", 4.0, 0, [S(0.35, P_proj(0.7, 1100, 6, 0.8, n=3, spread=0.3, shape='spear', el_='phys'))], cast=0.4, desc="Стрелы.", tele='line'),
    'cannon_shot': MV("Пушечный Выстрел", 5.0, 0, [S(0.5, P_proj(2.0, 800, 14, 1.0, shape='cannonball', el_='bomb', explode=80))], cast=0.5, desc="Ядро.", tele='line'),
})

ITEMS = {
    # мечи
    'rusty_sword': dict(name="Ржавая катана", kind='sword', rarity=0, atk=8, price=500, desc="Лучше, чем ничего."),
    'katana': dict(name="Катана", kind='sword', rarity=1, atk=15, price=3000, desc="Простая, но надёжная."),
    'yubashiri': dict(name="Юбасири", kind='sword', rarity=2, atk=24, spd=0.05, price=40000, desc="Рё Вадзамоно. Лёгкий, как ветер."),
    'sandai_kitetsu': dict(name="Сандай Китэцу", kind='sword', rarity=2, atk=27, crit=0.10, price=45000, desc="Проклятый клинок. Вадзамоно."),
    'kiribachi': dict(name="Кирибати", kind='sword', rarity=2, atk=22, crit=0.05, price=30000, desc="Меч-пила Арлонга."),
    'wado': dict(name="Вадо Итимондзи", kind='sword', rarity=3, atk=35, price=0, desc="О Вадзамоно. Клинок обещания."),
    'shusui': dict(name="Сюсуй", kind='sword', rarity=3, atk=39, crit=0.05, price=0, desc="О Вадзамоно. Чёрный клинок Рюмы."),
    'nidai_kitetsu': dict(name="Нидай Китэцу", kind='sword', rarity=3, atk=40, crit=0.12, price=320000, desc="О Вадзамоно. Жаждет крови."),
    'enma': dict(name="Энма", kind='sword', rarity=4, atk=54, haki=0.15, price=0, desc="О Вадзамоно. Вытягивает хаки владельца... и усиливает его."),
    'ame_habakiri': dict(name="Амэ но Хабакири", kind='sword', rarity=4, atk=52, spd=0.05, price=0, desc="О Вадзамоно Кодзуки Одэна."),
    'shodai_kitetsu': dict(name="Сёдай Китэцу", kind='sword', rarity=5, atk=68, crit=0.15, price=0, desc="Сайдзё О Вадзамоно. Один из 12 высших клинков."),
    'yoru': dict(name="Кокуто Ёру", kind='sword', rarity=5, atk=76, price=0, big=True, desc="Сайдзё О Вадзамоно. Меч Соколиного Глаза."),
    'gryphon': dict(name="Грифон", kind='sword', rarity=5, atk=72, haki=0.1, price=0, desc="Сабля Красноволосого Шанкса."),
    'murakumogiri': dict(name="Муракумогири", kind='sword', rarity=5, atk=74, price=0, vis='bisento', desc="Бисэнто Белоуса. О Вадзамоно."),
    # стрелковое
    'flintlock': dict(name="Кремнёвый пистолет", kind='gun', rarity=0, atk=9, price=1500, desc="Для снайперов."),
    'kabuto': dict(name="Кабуто", kind='gun', rarity=2, atk=22, price=38000, vis='slingshot', desc="Рогатка-посох."),
    'kuro_kabuto': dict(name="Куро Кабуто", kind='gun', rarity=3, atk=34, price=0, vis='slingshot', desc="Улучшенная рогатка."),
    'clima_tact': dict(name="Клима-Такт", kind='clima', rarity=1, atk=12, price=12000, desc="Наука погоды."),
    'sorcery_clima': dict(name="Колдовской Клима-Такт", kind='clima', rarity=2, atk=24, price=90000, desc="Изобретение Усоппа."),
    'zeus_clima': dict(name="Клима-Такт Зевса", kind='clima', rarity=4, atk=48, price=0, desc="С облаком Зевса."),
    # кулаки
    'knuckles': dict(name="Кастет", kind='fist', rarity=0, atk=6, price=800, desc="Для кулачного боя."),
    'iron_gauntlets': dict(name="Стальные перчатки", kind='fist', rarity=1, atk=14, defn=3, price=8000, desc="Тяжёлые перчатки."),
    'kairoseki_knuckles': dict(name="Кастет из Кайросеки", kind='fist', rarity=3, atk=32, price=260000, seastone=True, desc="Морской камень: бьёт логию и ослабляет фруктовиков."),
    'jitte': dict(name="Дзиттэ Смокера", kind='sword', rarity=3, atk=30, price=0, vis='jitte', seastone=True, desc="Наконечник из Кайросеки."),
    'hassaikai': dict(name="Хассайкай", kind='sword', rarity=5, atk=80, price=0, vis='club', desc="Дубина Кайдо. Для кулачных и мечников."),
    # одежда
    'rags': dict(name="Старая одежда", kind='outfit', rarity=0, defn=1, price=100, desc="Видала лучшие дни."),
    'sailor': dict(name="Морская куртка", kind='outfit', rarity=1, defn=6, price=4000, desc="Для пиратов и моряков."),
    'marine_coat': dict(name="Плащ «Справедливость»", kind='outfit', rarity=2, defn=14, hp=40, price=0, desc="Плащ офицера Дозора."),
    'cp_suit': dict(name="Костюм агента CP", kind='outfit', rarity=2, defn=12, spd=0.05, price=60000, desc="Строгий чёрный костюм."),
    'fur_coat': dict(name="Меховое пальто", kind='outfit', rarity=2, defn=13, price=70000, desc="Роскошь пустыни."),
    'captain_coat': dict(name="Плащ капитана", kind='outfit', rarity=3, defn=22, hp=80, price=220000, desc="Капитанский плащ на плечах."),
    'wano_kimono': dict(name="Кимоно Вано", kind='outfit', rarity=3, defn=20, spd=0.05, price=180000, desc="Шёлк Вано."),
    'scale_armor': dict(name="Броня из чешуи Морского Короля", kind='outfit', rarity=3, defn=28, price=0, desc="Скована кузнецом из чешуи."),
    'raid_suit': dict(name="Рейд-костюм", kind='outfit', rarity=4, defn=32, spd=0.08, price=0, desc="Технология Германа. Невидимость и броня."),
    'wapometal_armor': dict(name="Вапометаллическая броня", kind='outfit', rarity=4, defn=36, price=0, desc="Металл Вапола."),
    'emperor_coat': dict(name="Плащ Императора", kind='outfit', rarity=5, defn=48, hp=200, price=0, desc="Плащ, которого боится весь мир."),
    # аксессуары
    'impact_dial': dict(name="Импакт-Дайл", kind='dial', rarity=2, heavy=0.25, price=30000, desc="Заряженный удар +25%."),
    'flame_dial': dict(name="Флейм-Дайл", kind='dial', rarity=2, fire=0.2, price=25000, desc="Огненные атаки +20%."),
    'breath_dial': dict(name="Брес-Дайл", kind='dial', rarity=1, spd=0.08, price=15000, desc="Порыв ветра: скорость +8%."),
    'reject_dial_acc': dict(name="Реджект-Дайл", kind='dial', rarity=4, heavy=0.6, crit=0.05, price=0, desc="Заряженный удар +60%. Опасно!"),
    'tone_dial': dict(name="Тон-Дайл", kind='dial', rarity=1, xp=0.1, price=12000, desc="Музыка вдохновляет: опыт +10%."),
    'vivre_card': dict(name="Карта Жизни", kind='acc', rarity=3, revive=True, price=0, desc="Раз за бой спасает от поражения."),
    'power_ring': dict(name="Кольцо силы", kind='acc', rarity=1, atk=5, price=6000, desc="Простое кольцо."),
    'haki_bracer': dict(name="Браслет воли", kind='acc', rarity=2, haki=0.15, price=60000, desc="Хаки +15%."),
    'fruit_charm': dict(name="Амулет фрукта", kind='acc', rarity=2, fruit=0.15, price=60000, desc="Сила фрукта +15%."),
    'emperor_ring': dict(name="Кольцо Императора", kind='acc', rarity=5, atk=25, haki=0.2, fruit=0.2, price=0, desc="Символ власти над морем."),
    'eternal_pose': dict(name="Этернал Поуз", kind='key', rarity=2, price=50000, desc="Позволяет плыть к уже посещённым островам напрямую (быстрое путешествие)."),
    # еда
    'meat': dict(name="Мясо на кости", kind='food', rarity=0, heal=0.35, price=300, desc="Восстанавливает 35% здоровья."),
    'sea_king_meat': dict(name="Мясо Морского Короля", kind='food', rarity=2, heal=0.8, price=3000, desc="Восстанавливает 80% здоровья."),
    'bento': dict(name="Бэнто кока", kind='food', rarity=1, heal=0.5, stam=1.0, price=1200, desc="Здоровье 50% и выносливость."),
    'rumble_ball': dict(name="Румбл-Бол", kind='food', rarity=2, buff=('dmg', 1.3, 30), price=8000, desc="Урон +30% на 30 сек."),
    'sake': dict(name="Саке", kind='food', rarity=1, buff=('haki', 1.0, 0), haki_restore=1.0, price=1500, desc="Полностью восстанавливает хаки."),
    'cola': dict(name="Кола", kind='mat', rarity=0, price=200, col=(120, 60, 30), desc="Топливо для Coup de Burst и Гаон-пушки."),
    'fish': dict(name="Рыба", kind='mat', rarity=0, price=60, col=(120, 180, 220), desc="Кок приготовит из неё еду."),
    # материалы
    'wood': dict(name="Древесина", kind='mat', rarity=0, price=100, col=(150, 100, 60), desc="Ремонт корабля."),
    'iron': dict(name="Железо", kind='mat', rarity=0, price=300, col=(160, 160, 170), desc="Ковка оружия."),
    'steel': dict(name="Сталь", kind='mat', rarity=1, price=1500, col=(190, 200, 210), desc="Прочная ковка."),
    'kairoseki': dict(name="Кайросеки", kind='mat', rarity=3, price=20000, col=(70, 90, 110), desc="Морской камень."),
    'adam_wood': dict(name="Древо Адама", kind='mat', rarity=3, price=50000, col=(220, 170, 90), desc="Сокровище-древесина."),
    'wapometal': dict(name="Вапометалл", kind='mat', rarity=3, price=40000, col=(200, 180, 120), desc="Металл с острова Драм."),
    'tamahagane': dict(name="Тамахаганэ", kind='mat', rarity=3, price=35000, col=(210, 220, 230), desc="Сталь Вано."),
    'sea_king_scale': dict(name="Чешуя Морского Короля", kind='mat', rarity=2, price=8000, col=(90, 160, 140), desc="Из неё куют броню."),
    'dial_shell': dict(name="Раковина Дайла", kind='mat', rarity=2, price=6000, col=(230, 220, 190), desc="Небесная ракушка."),
    'gold': dict(name="Золото", kind='mat', rarity=2, price=10000, col=(250, 210, 60), desc="Сокровища."),
    'giant_timber': dict(name="Древо Эльбафа", kind='mat', rarity=4, price=80000, col=(160, 120, 70), desc="Древесина великанов."),
    'pacifista_part': dict(name="Деталь Пацифисты", kind='mat', rarity=3, price=25000, col=(120, 120, 140), desc="Технология Вегапанка."),
}

FRUIT_PRICE = {1: 120000, 2: 450000, 3: 1500000, 4: 6000000, 5: 25000000}

def fruit_item(fid):
    f = FRUITS[fid]
    return dict(id='fruit_' + fid, name=f['name'], kind='fruit', rarity=f['rarity'], fid=fid, col=f['col'],
                price=FRUIT_PRICE[f['rarity']], desc=f['type'] + ". " + f['desc'])

def make_item(iid, **over):
    if iid.startswith('fruit_'):
        it = fruit_item(iid[6:])
    else:
        it = dict(ITEMS[iid])
        it['id'] = iid
    it['plus'] = 0
    it.update(over)
    return it

# ------------------------------------------------------------------
#  ВРАГИ (рядовые)
# ------------------------------------------------------------------
def _ea(**kw):
    return A(**kw)

ENEMY_TYPES = {
    'bandit': dict(name="Бандит", hp=1.0, dmg=1.0, spd=150, ai='melee', xp=8, app=_ea(hair='messy', hair_col=(90, 50, 25), outfit='tank', top=(140, 100, 60), bottom=(80, 70, 60), weapon='sword1', hat='bandana', hat_col=(150, 40, 40))),
    'bandit_big': dict(name="Громила", hp=2.2, dmg=1.4, spd=120, ai='melee', xp=14, app=_ea(scale=1.3, hair='bald', features=('beard',), outfit='tank', top=(110, 80, 60), weapon='club')),
    'pirate': dict(name="Пират", hp=1.0, dmg=1.0, spd=155, ai='melee', xp=9, app=_ea(hat='bandana', hat_col=(200, 40, 40), outfit='shirt', top=(220, 220, 210), bottom=(70, 60, 50), weapon='sword1')),
    'pirate_gun': dict(name="Пират-стрелок", hp=0.8, dmg=1.0, spd=145, ai='ranged', xp=10, moves=['rifle_shot'], app=_ea(hat='tricorn', hat_col=(40, 30, 30), outfit='coat', top=(120, 50, 40), weapon='rifle')),
    'pirate_brute': dict(name="Пират-громила", hp=2.5, dmg=1.5, spd=115, ai='melee', xp=16, moves=['heavy_slam'], app=_ea(scale=1.35, hair='mohawk', hair_col=(200, 60, 40), outfit='tank', top=(60, 60, 70), weapon='axe')),
    'marine': dict(name="Дозорный", hp=1.0, dmg=1.0, spd=155, ai='melee', xp=9, app=_ea(outfit='marine', hat='marine_cap', inner=(240, 240, 240), top=(240, 240, 240), bottom=(60, 90, 160), weapon='sword1')),
    'marine_rifle': dict(name="Дозорный-стрелок", hp=0.8, dmg=1.0, spd=145, ai='ranged', xp=10, moves=['rifle_shot'], app=_ea(outfit='marine', hat='marine_cap', inner=(240, 240, 240), top=(240, 240, 240), bottom=(60, 90, 160), weapon='rifle')),
    'marine_officer': dict(name="Офицер Дозора", hp=2.4, dmg=1.4, spd=160, ai='melee', xp=20, moves=['shigan', 'rankyaku'], app=_ea(outfit='marine', inner=(60, 80, 140), top=(240, 240, 240), bottom=(40, 50, 90), hair='slick', hair_col=(40, 30, 30), cape=(245, 245, 245), weapon='sword1')),
    'fishman': dict(name="Рыбочеловек", hp=1.6, dmg=1.3, spd=165, ai='melee', xp=13, moves=['uchimizu'], app=_ea(skin=(120, 170, 200), features=('fishman', 'fin', 'grin'), outfit='shirt', top=(240, 200, 80), hair='spiky', hair_col=(30, 40, 60))),
    'baroque': dict(name="Агент Барок Воркс", hp=1.1, dmg=1.1, spd=160, ai='melee', xp=11, app=_ea(outfit='suit', top=(50, 50, 60), bottom=(50, 50, 60), hat='top_hat', hat_col=(40, 40, 50), weapon='sword1')),
    'baroque_gun': dict(name="Стрелок Барок Воркс", hp=0.9, dmg=1.0, spd=150, ai='ranged', xp=11, moves=['rifle_shot'], app=_ea(outfit='suit', top=(50, 50, 60), weapon='rifle')),
    'drum_soldier': dict(name="Солдат Вапола", hp=1.1, dmg=1.0, spd=145, ai='ranged', xp=11, moves=['rifle_shot'], app=_ea(outfit='coat', top=(90, 60, 120), hat='helmet', hat_col=(160, 160, 170), weapon='rifle')),
    'sky_warrior': dict(name="Божественный Солдат", hp=1.2, dmg=1.2, spd=170, ai='ranged', xp=14, moves=['sky_burn'], app=_ea(outfit='robe', top=(240, 240, 230), hair='buzz', hair_col=(240, 240, 240), features=('wings_small',), weapon='staff')),
    'shandia': dict(name="Воин Шандии", hp=1.3, dmg=1.3, spd=170, ai='melee', xp=14, app=_ea(skin=(180, 120, 80), outfit='tank', top=(200, 120, 60), hair='long', hair_col=(30, 20, 20), weapon='rifle')),
    'franky_family': dict(name="Член семьи Фрэнки", hp=1.3, dmg=1.1, spd=150, ai='melee', xp=13, app=_ea(outfit='shirt', top=(240, 120, 160), hair='slick', hair_col=(60, 120, 220), features=('sunglasses',))),
    'cp_agent': dict(name="Агент CP", hp=1.5, dmg=1.4, spd=190, ai='melee', xp=16, moves=['shigan', 'rankyaku'], app=_ea(outfit='suit', top=(25, 25, 30), bottom=(25, 25, 30), hair='slick', hair_col=(30, 30, 30), features=('sunglasses',))),
    'zombie': dict(name="Зомби", hp=2.0, dmg=1.2, spd=110, ai='melee', xp=13, app=_ea(skin=(170, 190, 150), features=('stitch',), outfit='shirt', top=(90, 80, 100), hair='wild', hair_col=(80, 70, 90), weapon='sword1')),
    'pacifista': dict(name="Пацифиста", hp=6.0, dmg=1.8, spd=110, ai='ranged', xp=45, moves=['paci_laser', 'paw_shot'], elite=True, app=_ea(scale=1.8, skin=(150, 150, 160), outfit='coat', top=(30, 30, 35), hat='cap', hat_col=(240, 240, 240), features=('beard',), beard_col=(40, 40, 40))),
    'kuja': dict(name="Воительница Кудзя", hp=1.3, dmg=1.3, spd=175, ai='ranged', xp=15, moves=['arrow_volley'], app=_ea(outfit='robe', top=(220, 60, 120), hair='long', hair_col=(30, 20, 30), skin=(230, 190, 150))),
    'jailer': dict(name="Тюремщик", hp=1.6, dmg=1.3, spd=150, ai='melee', xp=15, app=_ea(outfit='armor', top=(70, 60, 50), hat='helmet', hat_col=(80, 70, 60), weapon='trident')),
    'jail_beast': dict(name="Тюремный зверь", hp=3.5, dmg=1.6, spd=130, ai='melee', xp=28, moves=['heavy_slam'], elite=True, app=_ea(scale=1.7, skin=(120, 110, 100), fur=(120, 110, 100), features=('mink', 'horns'), outfit='tank', top=(60, 50, 40))),
    'wb_pirate': dict(name="Пират Белоуса", hp=1.6, dmg=1.4, spd=165, ai='melee', xp=16, app=_ea(outfit='shirt', top=(240, 240, 240), hat='bandana', hat_col=(60, 60, 200), weapon='sword1')),
    'vice_admiral': dict(name="Вице-адмирал", hp=5.0, dmg=2.0, spd=170, ai='melee', xp=50, elite=True, moves=['fist_love', 'flying_slash', 'rankyaku'], app=_ea(scale=1.4, outfit='marine', inner=(40, 40, 50), top=(245, 245, 245), cape=(245, 245, 245), hair='slick', hair_col=(200, 200, 200), weapon='sword1')),
    'new_fishman': dict(name="Новый рыбочеловек", hp=2.0, dmg=1.5, spd=170, ai='melee', xp=18, moves=['uchimizu'], app=_ea(skin=(100, 140, 170), features=('fishman', 'fin', 'grin', 'saw_nose'), outfit='tank', top=(40, 40, 50))),
    'caesar_soldier': dict(name="Солдат Цезаря", hp=1.5, dmg=1.3, spd=150, ai='ranged', xp=16, moves=['rifle_shot'], app=_ea(outfit='coat', top=(200, 200, 200), hat='helmet', hat_col=(220, 220, 230), weapon='rifle')),
    'centaur': dict(name="Кентавр Панк Хазарда", hp=2.6, dmg=1.6, spd=200, ai='melee', xp=22, app=_ea(scale=1.4, outfit='tank', top=(130, 90, 60), hat='bandana', hat_col=(60, 60, 60), weapon='axe')),
    'toy_soldier': dict(name="Игрушечный солдат", hp=1.4, dmg=1.3, spd=165, ai='melee', xp=16, app=_ea(scale=0.9, outfit='armor', top=(200, 60, 60), hat='helmet', hat_col=(240, 200, 60), weapon='sword1')),
    'donquixote': dict(name="Член семьи Донкихот", hp=2.2, dmg=1.6, spd=170, ai='melee', xp=22, moves=['tamaito'], app=_ea(outfit='coat', top=(240, 120, 170), features=('sunglasses',), hair='spiky', hair_col=(240, 210, 110))),
    'gladiator': dict(name="Гладиатор", hp=2.0, dmg=1.6, spd=165, ai='melee', xp=20, app=_ea(outfit='armor', top=(160, 140, 90), hat='helmet', hat_col=(180, 160, 100), weapon='sword1')),
    'beast_pirate': dict(name="Пират Сотни Зверей", hp=2.2, dmg=1.7, spd=165, ai='melee', xp=22, app=_ea(outfit='coat', top=(90, 40, 120), hair='wild', hair_col=(60, 40, 40), features=('horns',), weapon='club')),
    'gifter': dict(name="Гифтер (SMILE)", hp=2.6, dmg=1.8, spd=165, ai='ranged', xp=26, moves=['gifter_blast'], app=_ea(outfit='coat', top=(90, 40, 120), hair='mohawk', hair_col=(200, 200, 60), features=('grin', 'horns'))),
    'samurai': dict(name="Самурай", hp=2.2, dmg=1.8, spd=175, ai='melee', xp=22, moves=['iai_shishi'], app=_ea(outfit='kimono', top=(60, 60, 110), hair='ponytail', hair_col=(20, 20, 20), weapon='sword1', sash=(200, 40, 40))),
    'chess_soldier': dict(name="Шахматный солдат", hp=2.2, dmg=1.6, spd=150, ai='melee', xp=22, app=_ea(outfit='armor', top=(240, 240, 240), hat='crown', weapon='trident')),
    'homie': dict(name="Хоми", hp=1.8, dmg=1.5, spd=160, ai='melee', xp=20, app=_ea(skin=(120, 180, 90), outfit='robe', top=(60, 140, 60), hair='afro', hair_col=(70, 140, 60), features=('grin',))),
    'mink_warrior': dict(name="Воин-минк", hp=2.0, dmg=1.7, spd=200, ai='melee', xp=22, moves=['electro_punch'], app=_ea(features=('mink',), fur=(200, 150, 90), hair='messy', hair_col=(200, 150, 90), outfit='armor', top=(110, 80, 60))),
    'seraphim': dict(name="Серафим", hp=7.0, dmg=2.4, spd=180, ai='ranged', xp=70, elite=True, moves=['paci_laser', 'flying_slash'], app=_ea(scale=1.1, features=('wings_fire',), outfit='suit', top=(240, 240, 240), hair='spiky', hair_col=(30, 30, 30), weapon='sword1')),
    'giant_warrior': dict(name="Воин-великан", hp=5.0, dmg=2.3, spd=140, ai='melee', xp=55, elite=True, moves=['heavy_slam'], app=_ea(scale=2.3, features=('beard',), outfit='armor', top=(140, 110, 80), hat='helmet', hat_col=(180, 170, 150), weapon='axe')),
    'holy_soldier': dict(name="Солдат Святых Рыцарей", hp=2.4, dmg=2.0, spd=175, ai='ranged', xp=30, moves=['holy_arrow'], app=_ea(outfit='robe', top=(240, 240, 240), hat='helmet', hat_col=(250, 250, 250), weapon='sword1', cape=(240, 230, 210))),
    'bb_pirate': dict(name="Пират Чёрной Бороды", hp=2.6, dmg=2.0, spd=170, ai='melee', xp=30, app=_ea(outfit='coat', top=(30, 30, 30), hat='bandana', hat_col=(40, 40, 40), features=('beard',), weapon='sword1')),
    'sea_beast': dict(name="Морской зверь", hp=3.0, dmg=1.6, spd=140, ai='melee', xp=25, app=_ea(scale=1.6, skin=(80, 140, 120), features=('fishman', 'fin', 'grin'), hair='bald', outfit='tank', top=(60, 110, 100))),
    'beast': dict(name="Зверь джунглей", hp=2.2, dmg=1.4, spd=180, ai='melee', xp=16, app=_ea(scale=1.3, fur=(160, 110, 60), features=('mink',), skin=(160, 110, 60), hair='wild', hair_col=(120, 80, 40), outfit='tank', top=(120, 80, 40))),
    'biscuit': dict(name="Бисквитный солдат", hp=1.6, dmg=1.3, spd=140, ai='melee', xp=8, app=_ea(skin=(220, 170, 100), outfit='armor', top=(210, 160, 90), hat='helmet', hat_col=(220, 170, 100), weapon='sword1')),
    'doppel': dict(name="Доппельман", hp=1.5, dmg=1.0, spd=190, ai='melee', xp=0, app=_ea(skin=(40, 30, 50), top=(40, 30, 50), bottom=(40, 30, 50), hair='spiky', hair_col=(30, 20, 40), features=('grin',))),
    'mirage': dict(name="Мираж", hp=0.6, dmg=0.3, spd=150, ai='melee', xp=0, app=_ea(skin=(200, 220, 255), top=(200, 220, 255), bottom=(180, 200, 240), hair='long', hair_col=(200, 220, 255))),
}

# ------------------------------------------------------------------
#  БОССЫ
# ------------------------------------------------------------------
def B(name, title, bounty, app, moves, hp=8.0, dmg=1.4, spd=170, logia=None, scale=None, phases=None, quotes=None, immune=None,
      dodge=0.0, music='boss', elite=False, ranged=False, armor=0.0, haki=False, drop=None, combo='brawler', fs=False):
    if scale is not None:
        app['scale'] = scale
    return dict(name=name, title=title, bounty=bounty, app=app, moves=moves, hp=hp, dmg=dmg, spd=spd, logia=logia,
                phases=phases or [], quotes=quotes or {}, immune=immune, dodge=dodge, music=music, elite=elite,
                ranged=ranged, armor=armor, haki=haki, drop=drop or [], combo=combo, fs=fs)

LUFFY_APP = A(hat='straw', features=('scar_cheek',), top=(200, 40, 40), bottom=(70, 110, 190), outfit='vest', hair='messy')
ZORO_APP = A(hair='buzz', hair_col=(60, 160, 80), outfit='kimono', top=(60, 110, 60), bottom=(40, 60, 40), weapon='sword3', sash=(200, 40, 40), features=('scar_eye',))

BOSSES = {
    'higuma': B("Хигума", "Горный Бандит", 8_000_000, A(hair='messy', hair_col=(40, 30, 20), features=('beard',), outfit='tank', top=(120, 80, 50), weapon='sword1', hat='bandana', hat_col=(160, 40, 40)),
                ['brawl_haymaker', 'flying_slash'], hp=6.0, dmg=1.2, spd=150, combo='sword1',
                quotes=dict(intro="Ха! Сопляк с моря решил мне помешать? Я Хигума, награда — восемь миллионов!", defeat="Н-не может быть... какой-то мальчишка...")),
    'morgan': B("Морган", "Капитан «Рука-Топор»", 0, A(outfit='marine', inner=(60, 80, 140), top=(245, 245, 245), hair='buzz', hair_col=(240, 200, 120), features=('stitch',), weapon='axe', scale=1.3),
                ['brawl_haymaker', 'sword_whirl', 'heavy_slam'], hp=7.0, dmg=1.3, spd=150, combo='sword1',
                quotes=dict(intro="Я — закон этого города! Мой ранг даёт мне право на всё!", defeat="Мой... ранг...")),
    'helmeppo': B("Хельмеппо", "Сын Моргана", 0, A(hair='slick', hair_col=(240, 210, 110), outfit='suit', top=(150, 60, 160), weapon='sword1'),
                  ['iai_shishi'], hp=3.0, dmg=0.9, elite=True, combo='sword1', quotes=dict(intro="Мой папочка капитан! Ты пожалеешь!")),
    'buggy': B("Багги", "Клоун", 15_000_000, A(hat='tricorn', hat_col=(40, 30, 40), hair='spiky', hair_col=(60, 110, 210), features=('red_nose', 'makeup', 'grin'), outfit='coat', top=(200, 40, 40), cape=(200, 40, 40)),
               ['bara_cannon', 'bara_festival', 'muggy_ball', 'bara_ult'], hp=8.0, dmg=1.3, immune='sword',
               quotes=dict(intro="Кто это там смеётся над моим носом?! Я — Капитан Багги, будущий Король Пиратов!", phase="Бара Бара Фестиваль! Узри моё великое шоу!", defeat="Я... ещё... вернусь!!! Запомни меня!")),
    'cabaji': B("Кабаджи", "Акробат", 5_000_000, A(hair='spiky', hair_col=(180, 160, 140), outfit='shirt', top=(90, 140, 200), weapon='sword1', hat='headband', hat_col=(220, 220, 220)),
                ['iai_shishi', 'flying_slash'], hp=3.5, elite=True, combo='sword1'),
    'mohji': B("Модзи", "Укротитель", 4_000_000, A(hair='afro', hair_col=(240, 240, 240), features=('mink',), fur=(240, 240, 240), outfit='vest', top=(230, 230, 230)),
               ['brawl_haymaker'], hp=3.0, elite=True),
    'kuro': B("Куро", "Капитан Сотни Планов", 16_000_000, A(hair='slick', hair_col=(30, 30, 30), outfit='suit', top=(40, 40, 50), features=('sunglasses',), weapon='claw'),
              ['leopard_pounce', 'kuro_shakushi', 'leopard_claw'], hp=8.5, dmg=1.4, spd=220, dodge=0.15,
              quotes=dict(intro="Три года я притворялся дворецким. Ты разрушил мой план!", phase="Сякуси! Теперь я не различаю врагов и союзников!", defeat="Мой... идеальный план...")),
    'jango': B("Джанго", "Гипнотизёр", 9_000_000, A(hair='bald', hat='top_hat', hat_col=(30, 30, 40), features=('sunglasses',), outfit='coat', top=(60, 80, 120), weapon='claw'),
               ['jango_hypno', 'tamaito'], hp=4.0, elite=True),
    'krieg': B("Дон Криг", "Адмирал Пиратов Ист Блю", 17_000_000, A(scale=1.5, hair='slick', hair_col=(40, 40, 40), outfit='armor', top=(200, 170, 60), features=('stitch',)),
               ['krieg_guns', 'krieg_mh5', 'krieg_spear', 'heavy_slam'], hp=10.0, dmg=1.5, spd=140, armor=0.2,
               quotes=dict(intro="Я — Дон Криг! Пять тысяч человек склонились передо мной!", phase="MH5! Хватит игр — задохнитесь все!", defeat="Это... невозможно... моя броня...")),
    'gin': B("Гин", "Демон", 12_000_000, A(hair='buzz', hair_col=(40, 40, 40), outfit='shirt', top=(60, 70, 80), hat='bandana', hat_col=(50, 50, 60), weapon='jitte'),
             ['brawl_spin', 'brawl_haymaker'], hp=4.0, elite=True),
    'arlong': B("Арлонг", "Пила", 20_000_000, A(scale=1.35, skin=(120, 160, 190), features=('fishman', 'saw_nose', 'grin', 'fin'), outfit='shirt', top=(240, 200, 70), hair='spiky', hair_col=(30, 40, 60), weapon='sword1', blade_col=(200, 200, 210)),
                ['shark_darts', 'kiribachi', 'uchimizu', 'karakusagawara'], hp=11.0, dmg=1.6, spd=170, armor=0.1, drop=['kiribachi'],
                quotes=dict(intro="Люди — низшая раса! Арлонг Парк — моя империя!", phase="Кирибати! Этот меч изрежет тебя на куски!", defeat="Высшая... раса... проиграла... человеку...")),
    'kuroobi': B("Куробе", "Мастер карате", 9_000_000, A(skin=(140, 120, 170), features=('fishman', 'fin'), outfit='kimono', top=(240, 240, 240), hair='buzz'),
                 ['uchimizu', 'karakusagawara'], hp=4.0, elite=True),
    'chew': B("Тю", "Водомёт", 5_500_000, A(skin=(150, 190, 120), features=('fishman', 'fin'), outfit='shirt', top=(200, 90, 60), hair='spiky'),
              ['uchimizu'], hp=3.5, elite=True, ranged=True),
    'hatchan': B("Хатчан", "Шесть Мечей", 8_000_000, A(skin=(230, 120, 120), features=('fishman', 'grin'), outfit='shirt', top=(240, 240, 240), hair='buzz', weapon='sword2'),
                 ['nito_hawk', 'nito_rashomon'], hp=4.5, elite=True, combo='sword2'),
    'smoker': B("Смокер", "Белый Охотник", 0, A(hair='buzz', hair_col=(240, 240, 240), outfit='jacket', top=(240, 240, 240), bottom=(60, 60, 70), features=('cigar',), weapon='jitte', cape=(245, 245, 245)),
                ['white_blow', 'white_launcher', 'white_snake', 'white_out'], hp=11.0, dmg=1.5, logia='smoke', drop=['jitte'],
                quotes=dict(intro="В моём городе пират не проскочит. Я — капитан Смокер.", phase="Уайт Аут!", defeat="...Иди. В следующий раз я тебя поймаю.")),
    'alvida': B("Альвида", "Железная Булава", 5_000_000, A(hair='long', hair_col=(30, 20, 20), outfit='coat', top=(220, 80, 140), weapon='club', hat='tricorn', hat_col=(220, 80, 140)),
                ['heavy_slam', 'brawl_haymaker'], hp=9.0, dmg=1.4, dodge=0.3,
                quotes=dict(intro="Кто самая прекрасная на всех морях? Конечно, я — Альвида!", defeat="Моя... гладкая кожа...")),
    'mr5': B("Мистер 5", "Бомбер Барок Воркс", 10_000_000, A(hair='slick', hair_col=(40, 40, 40), outfit='suit', top=(220, 200, 80), features=('sunglasses',)),
             ['bomb_kick', 'nose_fancy'], hp=9.5, dmg=1.5,
             quotes=dict(intro="Секретные агенты не прощают свидетелей.", defeat="Я... взорвался... сам...")),
    'mr3': B("Мистер 3", "Восковой Мастер", 24_000_000, A(hair='buzz', hair_col=(40, 40, 40), features=('sunglasses',), outfit='suit', top=(240, 240, 240), hat='top_hat', hat_col=(240, 240, 240)),
             ['wax_cage', 'wax_wall', 'gomu_pistol'], hp=10.0, dmg=1.4,
             quotes=dict(intro="Восковая Скульптура! Ты станешь моим шедевром!", defeat="Мой воск... растаял...")),
    'wapol': B("Вапол", "Король Жестяной Банки", 0, A(scale=1.3, hair='slick', hair_col=(30, 30, 30), outfit='coat', top=(90, 60, 120), hat='crown', features=('grin',)),
               ['baku_munch', 'wapol_cannon', 'heavy_slam'], hp=11.0, dmg=1.4,
               quotes=dict(intro="Я король Драма! Мой народ живёт только чтобы служить мне!", defeat="Я... король... я король!!!")),
    'crocodile': B("Сэр Крокодайл", "Шичибукай", 81_000_000, A(scale=1.25, hair='slick', hair_col=(30, 30, 30), features=('stitch', 'cigar', 'hook'), outfit='coat', top=(30, 30, 35), cape=(60, 50, 40)),
                   ['desert_spada', 'sables', 'ground_death', 'desert_girasole'], hp=15.0, dmg=1.7, logia='sand', spd=170,
                   phases=[(0.5, dict(say="Ты меня утомил. Пора закончить игры.", buff=1.3))],
                   quotes=dict(intro="Мечты? Глупая болезнь. В этом море нет места мечтам.", phase="Десерт Гирасоле! Утони в песке!", defeat="Этот... свет...")),
    'mr1': B("Мистер 1", "Человек-Клинок", 75_000_000, A(hair='bald', features=('sunglasses',), outfit='suit', top=(40, 40, 60)),
             ['spa_blade', 'atomic_spa'], hp=6.0, elite=True, immune='sword'),
    'bonclay': B("Мистер 2 Бон Клей", "Окама", 32_000_000, A(hair='bald', features=('makeup',), outfit='coat', top=(240, 240, 255), cape=(255, 255, 255), hat='crown', hat_col=(240, 120, 200)),
                 ['okama_kick', 'death_wink'], hp=5.5, elite=True, combo='okama'),
    'bellamy': B("Белами", "Гиена", 55_000_000, A(hair='spiky', hair_col=(240, 210, 110), outfit='vest', top=(240, 240, 240), features=('grin',)),
                 ['spring_hopper', 'spring_snipe'], hp=12.0, dmg=1.6, spd=200,
                 quotes=dict(intro="Мечтатели! Новая эпоха — эпоха реальности!", defeat="Хм... ты и правда... силён...")),
    'satori': B("Сатори", "Жрец Шаров", 0, A(hair='bald', outfit='robe', top=(240, 230, 210), features=('grin',)),
                ['tamaito', 'gomu_pistol'], hp=5.0, elite=True),
    'ohm': B("Ом", "Жрец Железа", 0, A(hair='buzz', hair_col=(240, 240, 240), outfit='robe', top=(250, 250, 250), features=('sunglasses',), weapon='sword1'),
             ['flying_slash', 'sword_whirl'], hp=6.0, elite=True, combo='sword1'),
    'wyper': B("Вайпер", "Берсеркер", 0, A(skin=(180, 120, 80), hair='buzz', outfit='tank', top=(120, 160, 80), features=('stitch',), weapon='rifle'),
               ['reject_dial', 'sky_burn'], hp=6.0, elite=True, ranged=True),
    'enel': B("Энель", "Бог Скайпии", 0, A(hair='bald', features=('halo_drums', 'grin'), outfit='robe', top=(240, 200, 80), skin=(245, 210, 170), hat='headband', hat_col=(240, 240, 240), weapon='staff'),
              ['sango', 'enel_tp', 'el_thor', 'kari', 'raigo'], hp=18.0, dmg=1.8, logia='thunder', spd=200, dodge=0.2, fs=True,
              phases=[(0.4, dict(say="Ты смеешь угрожать БОГУ?! Райго поглотит всю Скайпию!", buff=1.35))],
              quotes=dict(intro="Ятта! Я — Бог. А бог не проигрывает смертным.", phase="Мантра видит всё!", defeat="Не... может... быть... Бог...")),
    'franky': B("Фрэнки", "Железный Человек", 44_000_000, A(scale=1.3, hair='slick', hair_col=(60, 120, 220), features=('sunglasses', 'grin'), outfit='shirt', top=(240, 120, 160), skin=(230, 170, 130)),
                ['franky_fire', 'strong_right', 'coup_de_vent'], hp=15.0, dmg=1.7, armor=0.2,
                quotes=dict(intro="Супер-р-р! Ты пришёл не по адресу, братишка!", defeat="Это было... супер... ой...")),
    'kaku': B("Каку", "Агент CP9", 0, A(features=('long_nose',), hat='cap', hat_col=(40, 40, 50), outfit='suit', top=(30, 30, 35), weapon='sword2'),
              ['rankyaku', 'nito_rashomon', 'shigan'], hp=7.0, elite=True, combo='sword2'),
    'jabra': B("Джабура", "Агент CP9", 0, A(hair='long', hair_col=(40, 40, 40), outfit='suit', top=(30, 30, 35), features=('mustache',)),
               ['leopard_claw', 'shigan', 'tekkai'], hp=7.0, elite=True, combo='rokushiki'),
    'blueno': B("Блуно", "Агент CP9", 0, A(scale=1.3, hair='mohawk', hair_col=(40, 40, 40), outfit='suit', top=(30, 30, 35)),
                ['tekkai', 'shigan', 'heavy_slam'], hp=7.5, elite=True, armor=0.2, combo='rokushiki'),
    'lucci': B("Роб Луччи", "Сильнейший агент CP9", 0, A(hat='top_hat', hat_col=(25, 25, 30), outfit='suit', top=(25, 25, 30), bottom=(25, 25, 30), hair='long', hair_col=(30, 30, 30), features=('beard',)),
               ['shigan', 'rankyaku', 'tekkai', 'leopard_form', 'leopard_pounce', 'rokuogan_lucci'], hp=19.0, dmg=1.9, spd=210, dodge=0.15, combo='rokushiki',
               phases=[(0.6, dict(say="Звериная форма. Теперь ты познаешь силу Рокусики!", buff=1.3, form='beast'))],
               quotes=dict(intro="Справедливость Мирового Правительства абсолютна. Убийство — моя работа.", phase="Рокуоган!", defeat="Ты... сильнее... правосудия?...")),
    'luffy_g2': B("Монки Д. Луффи", "Соломенная Шляпа", 300_000_000, dict(LUFFY_APP),
                  ['gomu_pistol', 'gomu_gatling', 'gear2', 'gomu_bazooka'], hp=19.0, dmg=1.9, spd=210, dodge=0.15,
                  phases=[(0.6, dict(say="Гир Второй!", buff=1.35, form='gear2'))],
                  quotes=dict(intro="Отдай Робин! Я не уйду без своего друга!", defeat="Хе... ты сильный... но я не сдамся...")),
    'moria': B("Гекко Мория", "Шичибукай", 320_000_000, A(scale=2.0, skin=(210, 200, 220), hair='spiky', hair_col=(60, 40, 60), features=('grin', 'horns'), outfit='coat', top=(50, 30, 60), cape=(70, 40, 80)),
               ['brick_bat', 'shadow_box', 'doppelman', 'shadow_asgard'], hp=20.0, dmg=1.9, spd=130,
               phases=[(0.5, dict(say="Тени! Тысяча теней — ко мне! Теневой Асгард!", buff=1.4, form='giant'))],
               quotes=dict(intro="Кишишиши! Мне не нужны сильные подчинённые — мне нужны твоя тень!", defeat="Кишиши... опять... проиграл...")),
    'perona': B("Перона", "Призрачная Принцесса", 0, A(hair='twin', hair_col=(240, 140, 190), outfit='robe', top=(40, 30, 50), hat='crown', hat_col=(220, 60, 100)),
                ['negative_hollow', 'toku_hollow'], hp=6.0, elite=True, ranged=True),
    'oars': B("Оарс", "Зомби-великан", 0, A(scale=3.0, skin=(170, 190, 160), features=('stitch', 'horns'), outfit='tank', top=(110, 100, 90), hair='bald'),
              ['heavy_slam', 'brawl_ground'], hp=9.0, elite=True, spd=110, armor=0.2),
    'kizaru': B("Борсалино «Кизару»", "Адмирал", 0, A(scale=1.2, hair='messy', hair_col=(40, 30, 30), features=('sunglasses',), outfit='suit', top=(240, 210, 60), bottom=(240, 210, 60), cape=(245, 245, 245)),
                ['yasakani', 'ama_no_murakumo', 'yata_no_kagami', 'light_kick', 'yasakani_rain'], hp=24.0, dmg=2.1, logia='light', spd=220, dodge=0.2, haki=True, fs=True,
                quotes=dict(intro="О-о-о, как стра-а-ашно... Пиная со скоростью света, знаешь ли.", phase="Ясакани но Магатама~", defeat="Ох-хо... ты оказался... сильнее, чем я думал...")),
    'kid': B("Юстасс «Капитан» Кид", "Сверхновая", 470_000_000, A(hair='wild', hair_col=(220, 50, 40), features=('grin',), outfit='coat', top=(30, 30, 35), cape=(200, 40, 40), hat='headband', hat_col=(240, 200, 60)),
             ['liberation', 'stone_fist', 'brawl_haymaker'], hp=22.0, dmg=2.0,
             quotes=dict(intro="Дозор? Хах! Я разнесу этот архипелаг вместе с тобой!", defeat="Тч... я ещё стану Королём Пиратов...")),
    'charlos': B("Святой Чарлос", "Небесный Дракон", 0, A(scale=1.2, hair='slick', hair_col=(240, 230, 210), outfit='robe', top=(250, 250, 250), hat='helmet', hat_col=(200, 220, 255), features=('mustache',)),
                 ['rifle_shot'], hp=2.0, dmg=0.5, elite=True, ranged=True),
    'pacifista_boss': B("Пацифиста PX-4", "Человек-оружие", 0, dict(ENEMY_TYPES['pacifista']['app'], scale=2.0),
                        ['paci_laser', 'paw_shot', 'heavy_slam'], hp=8.0, elite=True, armor=0.3, ranged=True),
    'hancock': B("Боа Хэнкок", "Императрица Пиратов", 80_000_000, A(hair='long', hair_col=(20, 15, 25), outfit='robe', top=(200, 40, 80), cape=(255, 255, 255), skin=(250, 220, 200)),
                 ['pistol_kiss', 'perfume_femur', 'slave_arrow', 'mero_ult'], hp=22.0, dmg=2.0, spd=200, haki=True, dodge=0.15,
                 quotes=dict(intro="Что бы я ни делала, мир меня простит. Почему? Потому что я прекрасна!", defeat="Ты... не окаменел... почему...")),
    'sandersonia': B("Боа Сандерсония", "Горгона", 0, A(hair='long', hair_col=(60, 140, 80), outfit='robe', top=(60, 140, 80)), ['leopard_claw', 'leopard_pounce'], hp=7.0, elite=True, haki=True),
    'marigold': B("Боа Мариголд", "Горгона", 0, A(scale=1.4, hair='long', hair_col=(200, 120, 40), outfit='robe', top=(200, 120, 40)), ['hiken', 'heavy_slam'], hp=8.0, elite=True, haki=True),
    'magellan': B("Магеллан", "Начальник Импел Дауна", 0, A(scale=1.6, hair='spiky', hair_col=(40, 30, 30), features=('horns',), outfit='coat', top=(60, 60, 50), hat='helmet', hat_col=(60, 40, 40)),
                  ['hydra', 'poison_cloud', 'venom_demon'], hp=24.0, dmg=2.0, spd=150,
                  quotes=dict(intro="Ни один заключённый не покинет Импел Даун. Пока я жив.", phase="Веном Демон: Адский Суд!", defeat="Импел Даун... пал...")),
    'shiryu': B("Сирю «Дождь»", "Начальник стражи", 0, A(hair='long', hair_col=(30, 30, 30), features=('cigar',), outfit='suit', top=(40, 40, 50), weapon='sword1'),
                ['iai_shishi', 'flying_slash', 'one_ult'], hp=9.0, elite=True, combo='sword1'),
    'minotaurus': B("Минотавр", "Тюремный зверь", 0, A(scale=2.0, features=('horns', 'mink'), fur=(110, 80, 60), skin=(110, 80, 60), outfit='tank', top=(60, 50, 40), weapon='club'),
                    ['heavy_slam'], hp=8.0, elite=True, armor=0.2),
    'ivankov': B("Эмпорио Иванков", "Королева Окама", 0, A(scale=1.6, hair='afro', hair_col=(150, 70, 190), features=('makeup', 'grin'), outfit='coat', top=(200, 60, 120), cape=(240, 200, 60)),
                 ['death_wink', 'okama_kick', 'hell_wink'], hp=22.0, dmg=1.9,
                 quotes=dict(intro="Ви-и-и-и-и! Ты хочешь остановить чудо? Чудеса — это мы!", defeat="Хи-хи... хорошо дерёшься, кэндидат...")),
    'akainu': B("Сакадзуки «Акаину»", "Адмирал", 0, A(scale=1.35, hair='buzz', hair_col=(30, 30, 30), features=('stitch',), outfit='suit', top=(180, 30, 40), bottom=(180, 30, 40), cape=(245, 245, 245), hat='marine_cap'),
                ['dai_funka', 'inugami', 'magma_pool', 'ryusei_kazan'], hp=30.0, dmg=2.3, logia='magma', haki=True, armor=0.15,
                phases=[(0.5, dict(say="Абсолютная Справедливость! Ты сгоришь вместе со своими мечтами!", buff=1.35))],
                quotes=dict(intro="Зло должно быть уничтожено. Даже его возможность.", phase="Метеорный Вулкан!", defeat="Это... не конец... справедливость...")),
    'aokiji': B("Кудзан «Аокидзи»", "Адмирал", 0, A(scale=1.4, hair='messy', hair_col=(30, 30, 30), outfit='suit', top=(240, 240, 250), bottom=(60, 90, 160), cape=(245, 245, 245)),
                ['ice_saber', 'ice_partisan', 'ice_time', 'pheasant_beak'], hp=10.0, elite=True, logia='ice', haki=True),
    'whitebeard': B("Эдвард Ньюгейт «Белоус»", "Сильнейший человек в мире", 5_046_000_000, A(scale=2.1, skin=(200, 150, 110), features=('wb_mustache', 'stitch'), hair='bald', hat='bandana', hat_col=(40, 40, 40), outfit='coat', top=(250, 250, 250), cape=(250, 250, 250), weapon='bisento'),
                    ['quake_punch', 'kabutowari', 'gura_shock', 'seaquake'], hp=32.0, dmg=2.4, spd=140, haki=True, armor=0.2, combo='sword1',
                    phases=[(0.5, dict(say="Гурарарара! Я не умру, пока мои сыновья в опасности!", buff=1.4))],
                    quotes=dict(into="", intro="Гурарарара... Хочешь бросить вызов сильнейшему человеку мира?", phase="Мир содрогнётся!", defeat="Ван Пис... существует...")),
    'marco': B("Марко «Феникс»", "Командир 1-й дивизии", 1_374_000_000, A(hair='spiky', hair_col=(240, 210, 110), outfit='vest', top=(140, 80, 160)),
               ['phoenix_brand', 'phoenix_wings', 'phoenix_heal'], hp=10.0, elite=True, haki=True),
    'jozu': B("Джозу «Алмаз»", "Командир 3-й дивизии", 0, A(scale=1.7, hair='mohawk', hair_col=(40, 40, 40), outfit='shirt', top=(200, 200, 200)),
              ['diamond_body', 'heavy_slam'], hp=11.0, elite=True, armor=0.4),
    'beast_king': B("Владыка Русукайны", "Гигантский зверь", 0, A(scale=2.6, fur=(90, 70, 50), skin=(90, 70, 50), features=('mink', 'horns', 'grin'), hair='wild', hair_col=(70, 50, 30), outfit='tank', top=(70, 50, 40)),
                    ['heavy_slam', 'jack_charge', 'brawl_ground'], hp=28.0, dmg=2.2, spd=170, armor=0.15,
                    quotes=dict(intro="Р-Р-Р-РААААР!!!", defeat="(Зверь склоняет голову, признавая твою силу)")),
    'hody': B("Ходи Джонс", "Новые Пираты Рыболюдей", 0, A(scale=1.5, skin=(110, 150, 180), features=('fishman', 'saw_nose', 'grin', 'fin'), outfit='tank', top=(40, 40, 50), hair='spiky', hair_col=(240, 240, 240)),
               ['shark_darts', 'uchimizu', 'karakusagawara', 'buraikan'], hp=30.0, dmg=2.3, spd=180,
               phases=[(0.5, dict(say="Энергетические стероиды! Ещё! ЕЩЁ!!!", buff=1.45))],
               quotes=dict(intro="Ненависть к людям — вот моя сила! Я утоплю тебя в ней!", defeat="Я... был... пустым...")),
    'decken': B("Вандер Декен IX", "Капитан Летучего Голландца", 0, A(scale=1.3, skin=(150, 120, 160), features=('fishman', 'grin'), hat='tricorn', hat_col=(30, 30, 30), outfit='coat', top=(60, 40, 80)),
                ['mato_throw'], hp=10.0, elite=True, ranged=True),
    'caesar': B("Цезарь Клаун", "Безумный учёный", 300_000_000, A(scale=1.3, skin=(240, 220, 210), hair='long', hair_col=(80, 60, 90), features=('horns', 'grin', 'makeup'), outfit='coat', top=(220, 220, 230), cape=(140, 100, 170)),
                 ['gastanet', 'shinokuni', 'poison_cloud'], hp=30.0, dmg=2.3, logia='gas',
                 quotes=dict(intro="Шуроророрo! Добро пожаловать в мою лабораторию! Ты будешь подопытным!", defeat="Мастер... не простит...")),
    'monet': B("Моне", "Снежная Женщина", 0, A(hair='long', hair_col=(80, 160, 90), outfit='robe', top=(240, 240, 240), features=('fin',)),
               ['snow_rabbit', 'kamakura'], hp=10.0, elite=True, logia='snow'),
    'vergo': B("Верго", "Демон Джастиса", 0, A(hair='slick', hair_col=(40, 40, 40), features=('sunglasses',), outfit='suit', top=(240, 240, 240), weapon='staff'),
               ['ryuo_strike', 'fist_love', 'tekkai'], hp=11.0, elite=True, haki=True, armor=0.2),
    'doflamingo': B("Донкихот Дофламинго", "Небесный Демон", 340_000_000, A(scale=1.35, hair='buzz', hair_col=(240, 210, 110), features=('sunglasses', 'grin'), outfit='coat', top=(240, 120, 170), cape=(255, 140, 190)),
                    ['tamaito', 'overheat', 'parasite', 'goshikito', 'birdcage'], hp=36.0, dmg=2.5, spd=200, haki=True, dodge=0.1,
                    phases=[(0.4, dict(say="Пробуждение! Весь город — мои нити! Фуфуфуфу!", buff=1.4))],
                    quotes=dict(intro="Фуфуфуфу... Пираты? Герои? Победитель — вот кто прав!", phase="Птичья Клетка сожмётся — и никто не выйдет!", defeat="Фуфу... наступает... новая эпоха...")),
    'pica': B("Пика", "Каменный Великан", 0, A(scale=2.2, skin=(150, 140, 130), hair='buzz', outfit='armor', top=(120, 110, 100), weapon='big_sword'),
              ['stone_fist', 'heavy_slam'], hp=12.0, elite=True, armor=0.3),
    'diamante': B("Диаманте", "Герой Колизея", 0, A(scale=1.6, hair='long', hair_col=(240, 240, 240), outfit='coat', top=(140, 60, 160), cape=(240, 240, 240), weapon='sword1'),
                  ['flag_blade', 'flying_slash'], hp=12.0, elite=True, combo='sword1'),
    'sugar': B("Шугар", "Хозяйка Игрушек", 0, A(scale=0.85, hair='bun', hair_col=(80, 160, 90), outfit='robe', top=(200, 140, 200)), ['toy_touch'], hp=6.0, elite=True),
    'jack': B("Джек «Засуха»", "Бедствие", 1_000_000_000, A(scale=2.0, hair='long', hair_col=(240, 240, 240), features=('horns', 'mask_leather'), outfit='coat', top=(90, 40, 120), weapon='club'),
              ['jack_charge', 'heavy_slam', 'brawl_ground'], hp=36.0, dmg=2.6, spd=150, armor=0.25, haki=True,
              quotes=dict(intro="Где самураи Кодзуки? Говори — или Зоу исчезнет.", defeat="Кайдо-сан... простите...")),
    'katakuri': B("Шарлотта Катакури", "Сладкий Командир", 1_057_000_000, A(scale=1.6, hair='spiky', hair_col=(160, 40, 50), features=('mouth_cover', 'stitch'), cape=(200, 50, 70), outfit='armor', top=(80, 60, 70), weapon='trident'),
                  ['mochi_tsuki', 'zan_giri', 'power_mochi', 'buzz_cut'], hp=40.0, dmg=2.7, spd=200, haki=True, dodge=0.3, fs=True,
                  phases=[(0.5, dict(say="Я вижу будущее. И в нём ты проигрываешь.", buff=1.35)), (0.2, dict(say="...Нет. Я вижу будущее, в котором ТЫ стоишь. Пробуждение!", buff=1.3))],
                  quotes=dict(intro="Не сдавайся. Мне интересно, на что ты способен.", phase="Мир Моти!", defeat="...Ты станешь великим. Я горжусь, что проиграл тебе.")),
    'cracker': B("Шарлотта Крекер", "Тысячерукий", 860_000_000, A(scale=1.3, hair='spiky', hair_col=(160, 60, 160), outfit='armor', top=(220, 170, 100), weapon='sword1'),
                 ['cracker_biscuits', 'sword_whirl', 'flying_slash'], hp=12.0, elite=True, haki=True, combo='sword1'),
    'big_mom': B("Шарлотта Линлин «Биг Мам»", "Император Моря", 4_388_000_000, A(scale=2.4, hair='afro', hair_col=(240, 120, 170), features=('grin',), outfit='robe', top=(240, 150, 200), hat='tricorn', hat_col=(80, 40, 80), weapon='big_sword'),
                 ['prometheus', 'zeus', 'soul_pocus', 'heavenly_fire'], hp=50.0, dmg=2.9, spd=150, haki=True, armor=0.35,
                 phases=[(0.5, dict(say="Ма-ма-ма-ма! СВАДЕБНЫЙ ТОРТ!!! Я ХОЧУ ТОРТ!!!", buff=1.4))],
                 quotes=dict(intro="Ма-ма-ма-ма! Жизнь или угощение?!", defeat="Ма... ма... мама устала...")),
    'king': B("Кинг «Пожар»", "Бедствие", 1_390_000_000, A(scale=1.8, features=('mask_leather', 'wings_fire', 'lunarian'), hair='long', hair_col=(240, 240, 240), outfit='suit', top=(30, 30, 35), weapon='sword1'),
              ['ptera_dive', 'tempura_udon', 'king_ult'], hp=14.0, elite=True, haki=True, armor=0.3, combo='sword1'),
    'queen': B("Квин «Чума»", "Бедствие", 1_320_000_000, A(scale=2.0, hair='long', hair_col=(240, 230, 210), features=('sunglasses', 'grin'), outfit='coat', top=(240, 240, 240), skin=(230, 190, 160)),
               ['queen_laser', 'poison_cloud', 'heavy_slam'], hp=14.0, elite=True, haki=True, armor=0.2),
    'orochi': B("Курозуми Орочи", "Сёгун Вано", 0, A(scale=1.3, hair='slick', hair_col=(30, 30, 30), outfit='kimono', top=(180, 40, 40), hat='crown'),
                ['hydra', 'bolo_breath'], hp=8.0, elite=True),
    'kaido': B("Кайдо «Сто Зверей»", "Сильнейшее существо", 4_611_100_000, A(scale=2.7, hair='long', hair_col=(30, 30, 50), features=('horns', 'beard'), beard_col=(30, 30, 50), outfit='robe', top=(200, 190, 170), cape=(90, 60, 120), weapon='club'),
                ['kaifu', 'bolo_breath', 'thunder_bagua', 'heavy_slam', 'dragon_form'], hp=60.0, dmg=3.0, spd=150, haki=True, armor=0.4,
                phases=[(0.66, dict(say="Уоро-ро-ро... Ты мне нравишься. Покажи мне больше!", buff=1.3, form='dragon')),
                        (0.33, dict(say="Пьяный стиль! Эта ночь — лучшая в моей жизни!", buff=1.4))],
                quotes=dict(intro="Покажи мне, достоин ли ты стать Джой Боем. Мир застрял — и ему нужна встряска!", phase="Раймэй Хаккэ!", defeat="Уоро-ро... Одэн... так вот кого ты ждал...")),
    'kizaru_eh': B("Кизару (Эгхэд)", "Адмирал", 0, dict(A(scale=1.25, hair='messy', hair_col=(40, 30, 30), features=('sunglasses',), outfit='suit', top=(240, 210, 60), bottom=(240, 210, 60), cape=(245, 245, 245))),
                   ['yasakani', 'light_kick', 'ama_no_murakumo', 'yasakani_rain'], hp=16.0, elite=True, logia='light', haki=True, dodge=0.2),
    'lucci_eh': B("Роб Луччи (пробуждённый)", "CP0", 0, A(scale=1.4, fur=(230, 190, 80), features=('mink',), hair='long', hair_col=(240, 230, 210), outfit='suit', top=(240, 240, 240)),
                  ['leopard_claw', 'leopard_pounce', 'rokuogan_lucci'], hp=16.0, elite=True, haki=True),
    'seraphim_hawk': B("S-Хоук", "Серафим", 0, A(hair='messy', hair_col=(30, 30, 30), features=('wings_fire',), outfit='suit', top=(240, 240, 240), weapon='big_sword'),
                       ['mihawk_slash', 'flying_slash', 'spa_blade'], hp=14.0, elite=True, immune='sword', combo='sword1'),
    'saturn': B("Святой Джейгарсия Сатурн", "Пятый Старейшина", 0, A(scale=2.2, hair='bald', features=('beard', 'horns'), beard_col=(240, 240, 240), outfit='suit', top=(30, 30, 35), weapon='staff', skin=(220, 200, 190)),
                ['saturn_legs', 'saturn_eyes', 'poison_cloud', 'gorosei_reg'], hp=55.0, dmg=3.0, spd=150, haki=True, armor=0.3,
                phases=[(0.5, dict(say="Ничтожество. Ты действительно думаешь, что можешь убить бессмертного?", buff=1.35))],
                quotes=dict(intro="Пустой трон... и мы, Пятеро. Ваш мир держится на нашей воле.", phase="Гюки — облик демона-быка!", defeat="Невозможно... Имму-сама...")),
    'luffy_g5': B("Монки Д. Луффи «Ника»", "Пятый Император", 3_000_000_000, A(hat='straw', features=('scar_cheek', 'grin'), top=(250, 250, 250), bottom=(250, 250, 250), outfit='vest', hair='wild', hair_col=(250, 250, 250), skin=(255, 240, 230), cape=(255, 255, 255)),
                  ['nika_dawn', 'nika_grab', 'nika_lightning', 'gomu_gatling', 'bajrang_gun'], hp=60.0, dmg=3.0, spd=230, haki=True, dodge=0.25,
                  phases=[(0.5, dict(say="Ши-ши-ши-ши! Барабаны Освобождения!", buff=1.4))],
                  quotes=dict(intro="Ши-ши-ши! Ты дозорный? Ну давай повеселимся!", defeat="Хе-хе... ладно, ладно... ты меня поймал... пока что!")),
    'zoro_boss': B("Ророноа Зоро", "Король Ада", 1_111_000_000, dict(ZORO_APP), ['oni_giri', 'pound_ho', 'tatsumaki', 'asura', 'king_of_hell'],
                   hp=18.0, elite=True, haki=True, combo='sword3'),
    'shamrock': B("Фигарланд Шемрок", "Глава Святых Рыцарей", 0, A(scale=1.4, hair='long', hair_col=(160, 30, 40), features=('scars3',), outfit='robe', top=(250, 250, 250), cape=(240, 240, 250), weapon='sword1'),
                  ['shamrock_slash', 'holy_arrow', 'conq_burst', 'iai_shishi', 'kamusari'], hp=62.0, dmg=3.1, spd=200, haki=True, dodge=0.2, combo='sword1',
                  phases=[(0.5, dict(say="Тебе не понять величия Святых Рыцарей. Склонись перед Божьими Рыцарями!", buff=1.4))],
                  quotes=dict(intro="Эльбаф подчинится воле Мировой Знати. Как подчинился когда-то мой брат... нет, он не подчинился.", defeat="Значит... кровь Фигарландов... проиграла...")),
    'gunko': B("Гунко", "Святой Рыцарь", 0, A(hair='long', hair_col=(240, 240, 240), outfit='robe', top=(250, 250, 250), hat='helmet', hat_col=(250, 250, 250)),
               ['holy_arrow', 'tamaito'], hp=14.0, elite=True, haki=True, ranged=True),
    'sommers': B("Святой Соммерс", "Святой Рыцарь", 0, A(hair='slick', hair_col=(60, 120, 60), outfit='robe', top=(250, 250, 250), cape=(60, 120, 60)),
                 ['thorn_lash', 'thorn_prison'], hp=15.0, elite=True, haki=True),
    'killingham': B("Святой Киллингем", "Святой Рыцарь", 0, A(hair='messy', hair_col=(150, 90, 190), outfit='robe', top=(250, 250, 250), hat='top_hat', hat_col=(80, 50, 110)),
                    ['nightmare_mist', 'negative_hollow'], hp=15.0, elite=True, haki=True),
    'loki': B("Локи", "Проклятый Принц Эльбафа", 2_600_000_000, A(scale=3.0, hair='long', hair_col=(240, 210, 110), features=('beard', 'grin'), beard_col=(240, 210, 110), outfit='armor', top=(90, 80, 70), weapon='club'),
              ['nidhogg_breath', 'ragnir_smash', 'heavy_slam', 'nidhogg_form'], hp=60.0, dmg=3.0, spd=140, haki=True, armor=0.35,
              phases=[(0.5, dict(say="Нидхёгг! Я сожгу этот мир дотла!", buff=1.4, form='dragon'))],
              quotes=dict(intro="Хе-хе-хе! Цепи сняты! Теперь все узнают, кто настоящий король Эльбафа!", defeat="Хех... ты... ничего так...")),
    'mihawk': B("Дракул Михоук", "Соколиный Глаз", 3_590_000_000, A(hat='wide', hat_col=(30, 30, 40), features=('mustache',), hair='slick', hair_col=(30, 30, 30), outfit='coat', top=(40, 40, 50), cape=(30, 30, 35), weapon='big_sword', eye_col=(220, 180, 40)),
                ['mihawk_slash', 'iai_shishi', 'flying_slash', 'sword_whirl', 'one_ult'], hp=70.0, dmg=3.3, spd=210, haki=True, dodge=0.35, fs=True, combo='sword1',
                phases=[(0.5, dict(say="...Неплохо. Тогда я достану свой чёрный клинок всерьёз.", buff=1.4))],
                quotes=dict(intro="Слабак не держит меч. Покажи мне свою решимость.", defeat="Я буду ждать тебя на вершине. Сколько угодно лет.")),
    'blackbeard': B("Маршалл Д. Тич «Чёрная Борода»", "Император Моря", 3_996_000_000, A(scale=1.8, hair='wild', hair_col=(30, 30, 30), features=('beard', 'grin'), beard_col=(30, 30, 30), hat='bandana', hat_col=(40, 30, 30), outfit='shirt', top=(240, 240, 240), cape=(30, 30, 35), skin=(200, 150, 110)),
                    ['kurouzu', 'black_hole', 'liberation', 'quake_punch', 'gura_shock', 'seaquake'], hp=75.0, dmg=3.4, spd=150, haki=True, armor=0.3,
                    phases=[(0.5, dict(say="Зе-ха-ха-ха! Тьма и землетрясение — непобедимая сила!", buff=1.4))],
                    quotes=dict(intro="Зе-ха-ха-ха! Мечты людей никогда не кончаются! Моя мечта — ты в моей тьме!", defeat="Зе-ха... ха... это ещё не конец...")),
    'akainu_fa': B("Адмирал Флота Сакадзуки", "Абсолютная Справедливость", 0, A(scale=1.5, hair='buzz', hair_col=(30, 30, 30), features=('stitch',), outfit='suit', top=(180, 30, 40), bottom=(180, 30, 40), cape=(245, 245, 245), hat='marine_cap'),
                   ['dai_funka', 'inugami', 'magma_pool', 'ryusei_kazan'], hp=75.0, dmg=3.4, logia='magma', haki=True, armor=0.3,
                   quotes=dict(intro="Ты пришёл в сердце Справедливости. Здесь ты и сгоришь.", defeat="Это... ещё... не конец...")),
    'shanks': B("Шанкс", "Рыжеволосый Император", 4_048_900_000, A(hair='long', hair_col=(200, 40, 40), features=('scars3', 'grin'), outfit='shirt', top=(240, 240, 240), cape=(30, 30, 35), weapon='sword1'),
                ['kamusari', 'iai_shishi', 'flying_slash', 'conq_burst', 'one_ult'], hp=85.0, dmg=3.5, spd=210, haki=True, dodge=0.35, fs=True, combo='sword1',
                phases=[(0.5, dict(say="Ты отлично дерёшься. Ладно — больше никаких поддавков.", buff=1.4))],
                quotes=dict(intro="Ха-ха! Ну что ж, покажи, кем ты стал. Я поставлю на кон свою руку... то есть, мою оставшуюся!", defeat="Ха-ха-ха! Вот это да! Ты достоин нового века.")),
    'sabo_boss': B("Сабо", "Начальник Штаба Революции", 602_000_000, A(hat='top_hat', hat_col=(40, 40, 60), hair='messy', hair_col=(240, 210, 110), outfit='coat', top=(40, 50, 90), cape=(40, 50, 90), features=('scar_eye',), weapon='staff'),
                   ['dragon_claw', 'hiken', 'hibashira', 'entei'], hp=40.0, dmg=2.8, haki=True, logia='fire'),
}

# ------------------------------------------------------------------
#  СПУТНИКИ (канонные союзники)
# ------------------------------------------------------------------
COMPANIONS = {
    'koby': dict(name="Коби", app=A(hair='messy', hair_col=(240, 140, 180), outfit='marine', inner=(240, 240, 240), top=(240, 240, 240), features=('scar_cheek',)), moves=['shigan', 'rankyaku'], hp=1.0, dmg=1.0, combo='rokushiki', desc="Мечтает стать Адмиралом."),
    'helmeppo_c': dict(name="Хельмеппо", app=A(hair='slick', hair_col=(240, 210, 110), outfit='marine', inner=(240, 240, 240), top=(240, 240, 240), weapon='sword2'), moves=['nito_crosscut'], hp=0.9, dmg=0.9, combo='sword2', desc="Исправившийся сын Моргана."),
    'tashigi': dict(name="Тасиги", app=A(hair='messy', hair_col=(30, 30, 40), outfit='jacket', top=(240, 200, 220), weapon='sword1'), moves=['iai_shishi', 'flying_slash'], hp=1.0, dmg=1.1, combo='sword1', desc="Мечница Дозора."),
    'johnny': dict(name="Джонни и Йосаку", app=A(hair='spiky', hair_col=(40, 40, 40), features=('sunglasses',), outfit='shirt', top=(120, 160, 200), weapon='sword1'), moves=['flying_slash'], hp=0.9, dmg=0.9, combo='sword1', desc="Охотники за головами."),
    'bonclay_c': dict(name="Бон Клей", app=BOSSES['bonclay']['app'], moves=['okama_kick', 'death_wink'], hp=1.1, dmg=1.1, combo='okama', desc="Настоящий друг!"),
    'koala': dict(name="Коала", app=A(hair='long', hair_col=(200, 140, 70), hat='cap', hat_col=(240, 200, 120), outfit='shirt', top=(240, 240, 240)), moves=['uchimizu', 'karakusagawara'], hp=1.0, dmg=1.1, combo='fishman_karate', desc="Мастер карате рыболюдей Революции."),
    'wyper_c': dict(name="Вайпер", app=BOSSES['wyper']['app'], moves=['sky_burn', 'reject_dial'], hp=1.0, dmg=1.2, combo='brawler', desc="Воин Шандии."),
    'hachi': dict(name="Хатчан", app=BOSSES['hatchan']['app'], moves=['nito_hawk'], hp=1.2, dmg=1.0, combo='sword2', desc="Готовит лучшие такояки."),
    'bartolomeo': dict(name="Бартоломео", app=A(hair='mohawk', hair_col=(80, 200, 120), features=('grin',), outfit='coat', top=(240, 240, 240)), moves=['barrier', 'barrier_crash'], hp=1.3, dmg=1.0, combo='brawler', desc="Каннибал и фанат."),
    'cavendish': dict(name="Кавендиш", app=A(hair='long', hair_col=(240, 210, 110), outfit='coat', top=(240, 240, 255), cape=(200, 60, 80), weapon='sword1'), moves=['iai_shishi', 'flying_slash', 'one_ult'], hp=1.1, dmg=1.3, combo='sword1', desc="Белый Конь."),
    'carrot': dict(name="Кэррот", app=A(features=('mink',), fur=(250, 250, 250), hair='long', hair_col=(250, 250, 250), outfit='shirt', top=(240, 150, 60)), moves=['electro_punch', 'electro_dash'], hp=1.0, dmg=1.2, combo='electro', desc="Воительница-кролик."),
    'yamato': dict(name="Ямато", app=A(scale=1.3, hair='long', hair_col=(240, 240, 250), features=('horns',), outfit='kimono', top=(240, 240, 240), weapon='club', sash=(200, 40, 40)), moves=['namuji', 'blizzard', 'yamato_ult'], hp=1.5, dmg=1.5, combo='brawler', desc="«Я — Кодзуки Одэн!»"),
    'sabo': dict(name="Сабо", app=BOSSES['sabo_boss']['app'], moves=['dragon_claw', 'hiken', 'hibashira'], hp=1.4, dmg=1.5, combo='brawler', desc="Начальник штаба Революции."),
    'loki_c': dict(name="Локи", app=dict(BOSSES['loki']['app'], scale=2.2), moves=['ragnir_smash', 'nidhogg_breath'], hp=2.0, dmg=1.6, combo='brawler', desc="Принц Эльбафа."),
    'smoker_c': dict(name="Смокер", app=BOSSES['smoker']['app'], moves=['white_blow', 'white_launcher'], hp=1.4, dmg=1.3, combo='brawler', desc="Вице-адмирал Г-5."),
    'buggy_c': dict(name="Багги", app=BOSSES['buggy']['app'], moves=['bara_cannon', 'muggy_ball'], hp=1.0, dmg=1.0, combo='brawler', desc="Лидер Кросс Гильдии (по мнению всех, кроме него)."),
    'crew': dict(name="Член команды", app=A(), moves=[], hp=1.0, dmg=1.0, combo='brawler', desc=""),
}

# ------------------------------------------------------------------
#  НАСТАВНИКИ
# ------------------------------------------------------------------
MENTORS = {
    'zeff': dict(name="Красная Нога Зефф", app=A(hair='bald', hat='top_hat', hat_col=(250, 250, 250), features=('mustache',), hair_col=(240, 240, 220), outfit='suit', top=(250, 250, 250)),
                 style='blackleg', lvl=8, price=20000, text="Руки повара — святое. Хочешь драться — дерись ногами. Покажи, на что способен!"),
    'mihawk': dict(name="Дракул Михоук", app=BOSSES['mihawk']['app'], style='sword3', lvl=45, price=0, sword_bonus=20,
                   text="Ты хочешь превзойти меня? Тогда научись видеть «дыхание» всего сущего. Меч без воли — кусок железа."),
    'rayleigh': dict(name="Сильверс Рэйли", app=A(hair='long', hair_col=(240, 240, 240), features=('beard', 'scar_eye'), beard_col=(240, 240, 240), outfit='shirt', top=(240, 240, 240), hat='none', weapon='sword1'),
                     haki=True, lvl=40, price=100000, text="Хаки есть у каждого. Просто большинство не знает об этом. Я научу тебя слышать голос воли."),
    'jinbe': dict(name="Джинбэй", app=A(scale=1.5, skin=(110, 140, 200), features=('fishman', 'grin'), hair='bun', hair_col=(30, 30, 30), outfit='kimono', top=(240, 140, 40)),
                  style='fishman_karate', lvl=30, price=80000, text="Карате рыболюдей — это не только кулаки. Это управление водой, что есть во всём живом."),
    'ivankov': dict(name="Эмпорио Иванков", app=BOSSES['ivankov']['app'], style='okama', lvl=35, price=60000, text="Ви-и-и! Окама Кэмпо! Сила, идущая от сердца... и от лодыжек!"),
    'garp': dict(name="Монки Д. Гарп", app=A(scale=1.3, hair='buzz', hair_col=(240, 240, 240), features=('beard', 'stitch'), beard_col=(240, 240, 240), outfit='marine', inner=(60, 90, 160), top=(245, 245, 245), cape=(245, 245, 245)),
                 style='fist_love', lvl=20, price=0, text="Ха-ха-ха! Хочешь стать сильным? Терпи мой Кулак Любви!"),
    'hyogoro': dict(name="Хьёгоро «Цветок»", app=A(hair='long', hair_col=(240, 240, 240), features=('beard',), beard_col=(240, 240, 240), outfit='kimono', top=(120, 80, 140)),
                    style='ryuo', lvl=65, price=0, haki_ryou=True, text="Рюо. Хаки — это не броня, а поток. Не касайся врага — пусть твоя воля войдёт в него."),
    'minks': dict(name="Инуараши и Нэкомамуши", app=A(scale=1.4, features=('mink',), fur=(240, 240, 240), hair='long', hair_col=(240, 240, 240), outfit='armor', top=(120, 100, 60), weapon='sword1'),
                  style='electro', lvl=55, price=0, text="Электро — врождённая сила минков. Но и человек может научиться направлять его, если сердце горит."),
    'haredas': dict(name="Харедас из Везерии", app=A(hair='bald', features=('beard',), beard_col=(240, 240, 240), outfit='robe', top=(200, 220, 240), hat='none'),
                    style='clima', lvl=25, price=50000, text="Погода — это наука. Я научу тебя повелевать облаками и молниями."),
    'cp9_scroll': dict(name="Свиток Рокусики", app=A(outfit='suit', top=(30, 30, 35), hat='top_hat', hat_col=(30, 30, 35)),
                       style='rokushiki', lvl=30, price=0, text="Тайные записи CP9. Шесть техник, превосходящих человека."),
    'sniper_old': dict(name="Старый Снайпер Ясопп?", app=A(hair='long', hair_col=(40, 30, 20), outfit='shirt', top=(140, 120, 60), weapon='rifle', hat='bandana', hat_col=(140, 60, 40)),
                       style='sniper', lvl=5, price=8000, text="Целишься не глазами — сердцем. Ну... и глазами тоже."),
    'sword_master': dict(name="Мастер Додзё Косиро", app=A(hair='long', hair_col=(30, 30, 30), features=('sunglasses',), outfit='kimono', top=(40, 40, 60), weapon='sword1'),
                         style='sword1', lvl=1, price=5000, text="Меч рубит сталь, если сердце мечника ровно. Начнём с основ."),
    'sword_master2': dict(name="Мастер Двух Клинков", app=A(hair='ponytail', hair_col=(30, 30, 30), outfit='kimono', top=(90, 40, 40), weapon='sword2'),
                          style='sword2', lvl=10, price=15000, text="Два клинка — две воли. Научись слушать обе."),
    'koala_m': dict(name="Коала", app=COMPANIONS['koala']['app'], style='fishman_karate', lvl=15, price=0, text="Меня учили рыболюди. Теперь я научу тебя!"),
    'sabo_m': dict(name="Сабо", app=BOSSES['sabo_boss']['app'], haki=True, lvl=25, price=0, text="Хаки и Драконий Коготь — наше оружие против мирового правительства."),
}

# ------------------------------------------------------------------
#  ФРАКЦИИ И РАНГИ
# ------------------------------------------------------------------
FACTIONS = {
    'pirate': dict(name="Пират", rep_name="Награда", desc="Свобода! Плыви куда хочешь, сражайся с кем хочешь. Разрушения и победы над сильными поднимают твою награду. За тобой охотится Дозор.",
                   start='dawn', col=(220, 60, 50), flag='skull'),
    'marine': dict(name="Морской Дозор", rep_name="Заслуги", desc="Справедливость! Ловишь пиратов, растёшь в звании от рядового до Адмирала Флота. Разрушение городов карается. Пираты нападают на тебя.",
                   start='shells', col=(70, 120, 220), flag='seagull'),
    'revo': dict(name="Революционная Армия", rep_name="Влияние", desc="Освобождение! Свергай тиранов и бросай вызов Мировому Правительству. Награда за твою голову тоже растёт.",
                 start='dawn', col=(60, 160, 90), flag='revo'),
    'hunter': dict(name="Охотник за головами", rep_name="Репутация", desc="Наживa и слава! Побеждённые боссы приносят белли. Позже — вступление в Кросс Гильдию, где награды назначают за головы дозорных.",
                   start='dawn', col=(200, 160, 60), flag='cross'),
}

PIRATE_TITLES = [(0, "Безымянный пират"), (10_000_000, "Пират-новичок"), (50_000_000, "Известный пират"), (100_000_000, "Сверхновая"),
                 (300_000_000, "Худшее Поколение"), (500_000_000, "Великий пират"), (1_000_000_000, "Командир Императора"),
                 (3_000_000_000, "Император Моря"), (5_500_000_000, "Сильнейший пират мира")]
MARINE_RANKS = [(0, "Рядовой"), (150, "Матрос"), (600, "Старшина"), (1600, "Лейтенант"), (3500, "Капитан"), (7000, "Коммодор"),
                (12000, "Контр-адмирал"), (22000, "Вице-адмирал"), (42000, "Адмирал"), (70000, "Адмирал Флота")]
REVO_RANKS = [(0, "Новобранец"), (200, "Боец Свободы"), (800, "Агент"), (2500, "Командир Отряда"), (8000, "Командующий Армией"), (25000, "Начальник Штаба"), (50000, "Правая рука Драгона")]
HUNTER_RANKS = [(0, "Охотник-новичок"), (200, "Охотник"), (900, "Опытный охотник"), (3000, "Мастер охоты"), (9000, "Партнёр Кросс Гильдии"), (25000, "Легенда Кросс Гильдии")]

def title_for(table, value):
    t = table[0][1]
    for v, name in table:
        if value >= v:
            t = name
    return t

CREW_ROLES = {
    'navigator': dict(name="Штурман", desc="+15% скорость корабля, предсказание штормов.", icon='nav'),
    'cook': dict(name="Кок", desc="После боя лечит 30% HP. Готовит еду из рыбы.", icon='cook'),
    'doctor': dict(name="Врач", desc="+регенерация, снижает урон статусов.", icon='doc'),
    'shipwright': dict(name="Плотник", desc="Ремонт корабля в море, скидка на улучшения.", icon='ship'),
    'sniper': dict(name="Канонир", desc="+30% урон пушек.", icon='gun'),
    'musician': dict(name="Музыкант", desc="+10% опыта, +5% урон команды.", icon='music'),
    'helmsman': dict(name="Рулевой", desc="+25% поворот корабля.", icon='helm'),
    'archaeologist': dict(name="Археолог", desc="Читает понеглифы: знания и награды.", icon='book'),
    'fighter': dict(name="Боец", desc="Сражается рядом с тобой на островах.", icon='fist'),
}
CREW_FIRST = ["Рико", "Тоби", "Марла", "Гас", "Вэл", "Нико", "Бруно", "Сэм", "Лиза", "Карл", "Бет", "Огги", "Фин", "Ди", "Хэнк", "Мира", "Чоу", "Пако", "Ина", "Рэн", "Таро", "Юки", "Дрейк", "Сол"]
CREW_EPI = ["Морской Волк", "Весельчак", "Три Пальца", "Тихоня", "Буря", "Железный", "Удачливый", "Рыжий", "Песчаный", "Медведь", "Звезда", "Чайка", "Ворон"]

# ==================================================================
#  ДАННЫЕ: МИР И ОСТРОВА (все арки до Эльбафа)
# ==================================================================
WORLD_W, WORLD_H = 74000, 32000
REDLINE1_X = (14000, 14800)
REDLINE2_X = (44000, 44800)
REVERSE_GATE_Y = (15300, 16700)
GL_BAND = (12500, 19500)
CALM_BELTS = [(10000, 12500), (19500, 22000)]
NW_BAND = (10500, 21500)

def region_at(x, y):
    if x < REDLINE1_X[0]:
        return 'east'
    if x < REDLINE1_X[1]:
        return 'redline'
    if x < REDLINE2_X[0]:
        if GL_BAND[0] <= y <= GL_BAND[1]:
            return 'paradise'
        for a, b in CALM_BELTS:
            if a <= y <= b:
                return 'calm'
        return 'void'
    if x < REDLINE2_X[1]:
        return 'redline'
    if NW_BAND[0] <= y <= NW_BAND[1]:
        return 'new'
    if 8000 <= y <= 24000:
        return 'calm'
    return 'void'

REGION_NAMES = {'east': "Ист Блю", 'paradise': "Гранд Лайн: Рай", 'calm': "Затишье (Калм Белт)", 'new': "Новый Мир", 'redline': "Ред Лайн", 'void': "Край мира"}

def I(name, region, pos, lvl, theme, boss, enemies, intro, outro, size=(78, 60), mids=None, mentor=None, shop=None, flags=(),
      companion=None, reward=None, groups=6, music='island', weather=None, req=None, hidden=False, hub=None, fruit_shop=None,
      shipwright=0, blacksmith=False, tavern=True, enemies_marine=None, desc="", extra_boss=None, chest_fruit=None):
    return dict(name=name, region=region, pos=pos, lvl=lvl, theme=theme, boss=boss, enemies=enemies, intro=intro, outro=outro,
                size=size, mids=mids or {}, mentor=mentor or [], shop=shop or [], flags=set(flags), companion=companion or {},
                reward=reward or {}, groups=groups, music=music, weather=weather, req=req, hidden=hidden, hub=hub,
                fruit_shop=fruit_shop or [], shipwright=shipwright, blacksmith=blacksmith, tavern=tavern,
                enemies_marine=enemies_marine, desc=desc, extra_boss=extra_boss, chest_fruit=chest_fruit)

ISLANDS = {
    # ========================== ИСТ БЛЮ ==========================
    'dawn': I("Остров Рассвета: Деревня Фуша", 'east', (2600, 26000), 1, 'village', {'*': 'higuma'}, ['bandit', 'bandit', 'bandit_big'],
              intro={'*': [('nar', "Ист Блю. Самое мирное из морей... и колыбель величайших пиратов."),
                           ('x:Макино', "Ты всё-таки решил выйти в море? Будь осторожен — горный бандит Хигума снова спустился в деревню."),
                           ('nar', "Бандиты Хигумы терроризируют жителей. Пора показать, на что ты способен!")],
                     'pirate': [('me', "Я стану Королём Пиратов! А для начала — разберусь с этими бандитами.")],
                     'revo': [('x:Незнакомец в плаще', "За стенами королевства Гоа горит Мусорный Терминал. Мир прогнил, мальчик. Если хочешь изменить его — начни с малого."),
                              ('me', "Я освобожу этот остров. А потом — весь мир.")],
                     'hunter': [('x:Староста', "За голову Хигумы назначено восемь миллионов белли. Говорят, охотники за головами любят такие суммы."),
                                ('me', "Восемь миллионов? Отличное начало карьеры.")]},
              outro={'*': [('x:Макино', "Ты спас деревню! Вот, возьми — тебе в море пригодится. И возвращайся живым!"),
                           ('nar', "Твоё путешествие начинается. Впереди — Шеллс Таун. Подними паруса (W) и правь рулём (A/D)!")]},
              mentor=['sword_master', 'sniper_old'], shop=['meat', 'rusty_sword', 'knuckles', 'flintlock', 'rags', 'wood'], groups=4,
              reward=dict(beli=5000, items=['meat', 'meat', 'meat', 'katana'], xp=120), size=(64, 50), flags=('tutorial',),
              desc="Родина Луффи, Эйса и Сабо. Здесь начинается легенда."),
    'shells': I("Шеллс Таун", 'east', (4600, 23200), 3, 'base', {'*': 'morgan'}, ['marine', 'marine', 'marine_rifle'],
                enemies_marine=['marine', 'marine_rifle'],
                mids={'*': ['helmeppo']},
                intro={'*': [('nar', "Шеллс Таун — база 153-го отделения Дозора. Капитан Морган «Рука-топор» правит городом страхом."),
                             ('x:Рика', "Пожалуйста... моего друга Зоро держат привязанным на плацу уже девятый день...")],
                       'marine': [('x:Коби', "Ты новенький? Я Коби! Я мечтаю стать Адмиралом... но наш капитан — тиран. Он убивает невиновных!"),
                                  ('me', "Дозор должен защищать людей. Если капитан стал злом — я сам его арестую.")],
                       'pirate': [('me', "Дозорные, которые мучают детей? Отличный повод подраться.")]},
                outro={'*': [('nar', "Тирания Моргана окончена. Жители ликуют!")],
                       'marine': [('x:Коби', "Ты... настоящий дозорный! Я пойду с тобой — буду учиться у тебя!"),
                                  ('nar', "Вице-адмирал Гарп прибыл лично. Узнав о подвиге, он посмеялся и повысил тебя.")]},
                companion={'marine': 'koby'}, shop=['meat', 'katana', 'sailor', 'iron', 'wood'], blacksmith=True, groups=5,
                reward=dict(beli=12000, items=['meat', 'meat'], xp=220), size=(66, 52), desc="Город у базы Дозора."),
    'orange': I("Оранж Таун", 'east', (6600, 27200), 5, 'town', {'*': 'buggy'}, ['pirate', 'pirate_gun', 'pirate'],
                mids={'*': ['cabaji', 'mohji']},
                intro={'*': [('nar', "Пираты Багги-Клоуна захватили Оранж Таун. Жители бежали, а город трясётся от пушечного смеха."),
                             ('x:Мэр Будл', "Этот город — всё, что у меня есть! Я не позволю клоуну его разрушить!"),
                             ('buggy', "Ха-ха-ха! Пушка Магги! Сотри этот квартал с лица земли!")]},
                outro={'*': [('buggy', "Я ещё вернусь! Запомни моё имя — Великий Капитан Багги!"),
                             ('nar', "Багги улетел... по частям. Жители возвращаются домой.")]},
                shop=['meat', 'katana', 'iron', 'power_ring', 'flintlock'], fruit_shop=['bara'], groups=6,
                reward=dict(beli=20000, items=['meat', 'power_ring'], xp=320), desc="Захвачен Багги-Клоуном.",
                chest_fruit='bara'),
    'syrup': I("Деревня Сиропная", 'east', (8100, 24000), 7, 'village', {'*': 'kuro'}, ['pirate', 'pirate', 'pirate_gun'],
               mids={'*': ['jango']},
               intro={'*': [('nar', "Тихая деревня, где живёт известный лгун... и где три года назад «погиб» Капитан Куро."),
                            ('x:Кая', "Мой дворецкий Клахадор... ты говоришь, это пират? Не может быть!"),
                            ('kuro', "Сегодня наследство Каи станет моим. Пираты Чёрной Кошки — в атаку!")]},
               outro={'*': [('x:Кая', "Спасибо... Я дарю тебе корабль-каравеллу! Пусть он станет тебе домом."),
                            ('nar', "Получен новый корабль: Каравелла! Ищи в меню «Корабль».")]},
               mentor=['sniper_old'], shop=['meat', 'flintlock', 'kabuto', 'wood', 'iron'], groups=6, flags=('ship_caravel',),
               reward=dict(beli=26000, items=['meat', 'meat', 'bento'], xp=420), desc="Деревня под угрозой Пиратов Чёрной Кошки."),
    'baratie': I("Морской ресторан «Барати»", 'east', (9600, 28200), 9, 'restaurant', {'*': 'krieg'}, ['pirate', 'pirate_brute', 'pirate_gun'],
                 mids={'*': ['gin']},
                 intro={'*': [('nar', "«Барати» — плавучий ресторан, где повара сражаются не хуже пиратов."),
                              ('x:Санджи', "Голодных мы кормим. Даже врагов. Но этот Криг пришёл не есть..."),
                              ('krieg', "Мне нужен этот корабль! Отдайте его — или я пущу ко дну всех!")]},
                 outro={'*': [('zeff', "Хм. Неплохо. Если хочешь — научу тебя драться ногами. Но руки береги: они для готовки."),
                              ('nar', "Дракул Михоук ненадолго появился на горизонте... и исчез. Сильнейший мечник мира наблюдает.")]},
                 mentor=['zeff'], shop=['meat', 'bento', 'sea_king_meat', 'sake', 'sailor'], groups=5,
                 reward=dict(beli=32000, items=['bento', 'bento', 'sake'], xp=520), size=(54, 44), desc="Ресторан на воде."),
    'arlong': I("Арлонг Парк (деревня Коко)", 'east', (11100, 25600), 12, 'fishpark', {'*': 'arlong'}, ['fishman', 'fishman', 'pirate'],
                mids={'*': ['kuroobi', 'chew', 'hatchan']},
                intro={'*': [('nar', "Восемь лет пираты-рыболюди Арлонга держат острова Кономи в страхе, собирая дань."),
                             ('x:Ноджико', "Сестрёнка восемь лет рисовала для него карты, чтобы выкупить деревню... А он нас обманул."),
                             ('arlong', "Шахахаха! Человек решил бросить вызов рыболюдям? Ты в десять раз слабее, ничтожество!")],
                       'marine': [('x:Капитан Нэдзуми', "Чу-чу! Арлонг платит нам... то есть... не лезь в это дело, рядовой!"),
                                  ('me', "Коррупция в Дозоре? Сначала Арлонг. Потом — ты, Нэдзуми.")]},
                outro={'*': [('nar', "Арлонг Парк разрушен. Острова Кономи свободны! Мандарины снова цветут."),
                             ('x:Генсан', "Ты вернул нам улыбку Нами... и всем нам. Спасибо.")]},
                companion={'hunter': 'johnny', 'pirate': 'johnny'},
                shop=['meat', 'iron', 'steel', 'sailor', 'iron_gauntlets', 'clima_tact'], blacksmith=True, groups=7,
                reward=dict(beli=60000, items=['steel', 'sea_king_meat'], xp=700), desc="Владения Арлонга-Пилы."),
    'loguetown': I("Логтаун", 'east', (12500, 20600), 14, 'town', {'*': 'smoker', 'marine': 'alvida'}, ['marine', 'marine_rifle', 'marine'],
                   enemies_marine=['pirate', 'pirate_gun', 'pirate_brute'],
                   intro={'*': [('nar', "Логтаун — город начала и конца. Здесь казнили Гол Д. Роджера, Короля Пиратов."),
                                ('x:Старик у эшафота', "Перед смертью Роджер сказал: «Моё сокровище? Ищите! Я оставил его всё в одном месте!»"),
                                ('smoker', "Пираты на моём острове. Сегодня ты не уйдёшь на Гранд Лайн.")],
                          'marine': [('x:Тасиги', "Капитан Смокер приказал: Альвида и остатки банды Багги нападают на город! Защити горожан!"),
                                     ('alvida', "Дозорный? Как мило. Ты станешь первым трофеем моей красоты!")],
                          'revo': [('x:Незнакомец в плаще', "...Мир ждёт тебя. Ветер скоро переменится."),
                                   ('nar', "Таинственный человек исчез. Говорят, это был сам Монки Д. Драгон.")]},
                   outro={'*': [('nar', "Грянула внезапная буря — и ветер понёс твой корабль к Ревёрс Маунтин."),
                                ('nar', "Путь на Гранд Лайн открыт! Плыви на восток к гигантской горе посреди Ред Лайн.")],
                          'marine': [('x:Тасиги', "Ты дрался великолепно. Позволь мне присоединиться к тебе — я хочу собрать все великие мечи!"),
                                     ('smoker', "Хм. Ты не такой, как остальные. Я выбил тебе пропуск на Гранд Лайн. Не подведи.")]},
                   companion={'marine': 'tashigi'}, mentor=['sword_master2'],
                   shop=['meat', 'katana', 'yubashiri', 'sandai_kitetsu', 'steel', 'captain_coat', 'eternal_pose', 'sailor'],
                   blacksmith=True, groups=7, flags=('reverse_mountain', 'marine_armament', 'hunter_observation'), chest_fruit='moku',
                   reward=dict(beli=80000, items=['sea_king_meat', 'steel', 'steel'], xp=900), desc="Город, где казнили Короля Пиратов."),
    # ========================== РАЙ ==========================
    'twin_capes': I("Мыс Близнецов", 'paradise', (15900, 16000), 15, 'cape', {'*': None}, ['baroque'], groups=0,
                    intro={'*': [('nar', "Ты на Гранд Лайн! Огромный кит Лабун бьётся головой о Ред Лайн, ожидая своих друзей."),
                                 ('x:Крокус', "Здесь компас бесполезен. Возьми Лог Поуз — он укажет путь от острова к острову.")]},
                    outro={'*': [('nar', "Получен ЛОГ ПОУЗ. Стрелка указывает на следующий остров.")]},
                    shop=['meat', 'sea_king_meat', 'cola', 'wood'], flags=('log_pose', 'no_combat'), size=(48, 40),
                    reward=dict(beli=0, items=['meat'], xp=100), desc="Вход на Гранд Лайн."),
    'whisky': I("Виски Пик", 'paradise', (18600, 15000), 16, 'cactus', {'*': 'mr5'}, ['baroque', 'baroque', 'baroque_gun'],
                intro={'*': [('nar', "Город музыки и выпивки радушно встречает пиратов... слишком радушно."),
                             ('x:Мистер 8', "Мааа-мааа! Добро пожаловать! Пир в вашу честь!"),
                             ('nar', "Ночью охотники Барок Воркс сбросили маски. Город — ловушка!")]},
                outro={'*': [('nar', "Принцесса Виви из Алабасты раскрыла заговор: «Барок Воркс» — организация Шичибукая Крокодайла!")]},
                shop=['meat', 'sake', 'steel', 'breath_dial', 'tone_dial'], groups=6, chest_fruit='bomu',
                reward=dict(beli=90000, items=['sake', 'meat'], xp=1000), desc="Охотничьи угодья Барок Воркс."),
    'little_garden': I("Литл Гарден", 'paradise', (21600, 17000), 18, 'jungle', {'*': 'mr3'}, ['baroque', 'beast', 'baroque_gun'],
                       intro={'*': [('nar', "Доисторические джунгли. Здесь сто лет сражаются два великана Эльбафа — Дорри и Брогги."),
                                    ('x:Дорри', "Гагягягя! Храбрый человек! Битва воинов Эльбафа — святое дело!"),
                                    ('mr3', "Восковая Скульптура! Великаны станут моим шедевром, хе-хе!")]},
                       outro={'*': [('x:Брогги', "Гаргаргар! Ты спас нашу честь! Когда-нибудь приходи в Эльбаф — тебя там встретят как воина!")]},
                       shop=['meat', 'sea_king_meat', 'gold'], groups=6, flags=('giant_blessing',), chest_fruit='doru',
                       reward=dict(beli=100000, items=['gold', 'sea_king_meat'], xp=1150), weather=None, desc="Остров, застывший во времени."),
    'drum': I("Королевство Драм", 'paradise', (24100, 13900), 20, 'snow', {'*': 'wapol'}, ['drum_soldier', 'drum_soldier', 'bandit_big'],
              mids={'*': []},
              intro={'*': [('nar', "Зимний остров. Король Вапол бежал от пиратов Чёрной Бороды... и вернулся, чтобы вновь угнетать народ."),
                           ('x:Доктор Курэха', "Хи-хи-хи! Хочешь узнать секрет молодости? Сначала прогони эту жестяную банку."),
                           ('wapol', "Это моё королевство! Я съем всех, кто против!")]},
              outro={'*': [('x:Доктор Курэха', "Вишни зацвели на снегу... Хи-хи! Держи эти лекарства, мальчишка.")]},
              shop=['meat', 'bento', 'rumble_ball', 'wapometal', 'fur_coat'], groups=6, weather='snow', chest_fruit='baku',
              reward=dict(beli=120000, items=['rumble_ball', 'rumble_ball', 'wapometal'], xp=1300), desc="Остров вечной зимы."),
    'alabasta': I("Королевство Алабаста", 'paradise', (27100, 17600), 24, 'desert', {'*': 'crocodile'}, ['baroque', 'baroque_gun', 'baroque'],
                  mids={'*': ['mr1', 'bonclay']},
                  intro={'*': [('nar', "Королевство пустынь на грани гражданской войны. Три года без дождя — дело рук «Барок Воркс»."),
                               ('x:Принцесса Виви', "Мой народ убивает друг друга из-за одного человека! Пожалуйста... помоги!"),
                               ('crocodile', "Мечты, верность, дружба... Всё это — мусор. В моём мире выживают сильные.")],
                         'revo': [('koala', "Сабо прислал нас сюда — на остров Катория. Революция поможет Алабасте! Я научу тебя карате рыболюдей."),
                                  ('me', "Шичибукай с разрешением Правительства уничтожает страну. Вот вам и «Мировая Справедливость».")],
                         'marine': [('smoker', "Крокодайл — Шичибукай. Но если он виновен, я арестую его сам. Иди вперёд, я прикрою.")]},
                  outro={'*': [('nar', "Над Алабастой впервые за три года пошёл дождь. Война окончена."),
                               ('x:Принцесса Виви', "Если мы встретимся снова... ты назовёшь меня другом?")]},
                  companion={'*': 'bonclay_c', 'revo': 'koala'}, mentor=['koala_m'],
                  shop=['meat', 'fur_coat', 'gold', 'nidai_kitetsu', 'flame_dial'], groups=8, weather='sand', chest_fruit='suna',
                  flags=('revo_armament',), size=(86, 64),
                  reward=dict(beli=200000, items=['gold', 'gold', 'sea_king_meat'], xp=1800), desc="Пустынное королевство."),
    'jaya': I("Джая: Мок Таун", 'paradise', (30600, 15000), 27, 'jungle_town', {'*': 'bellamy'}, ['pirate', 'pirate_brute', 'pirate_gun'],
              intro={'*': [('nar', "Мок Таун — город, где пираты смеются над мечтами. Здесь не верят в Небесные Острова."),
                           ('bellamy', "Небесный остров? Ха-ха-ха! Эпоха мечтателей закончилась!"),
                           ('x:Толстяк с тёмной бородой', "Зе-ха-ха-ха! Мечты людей никогда не кончаются! Запомни это, малыш!")]},
              outro={'*': [('x:Монблан Кррикет', "Ты веришь в Город Золота? Тогда поплыви в Поток Нок-Ап — он подбросит корабль прямо в небо!"),
                           ('nar', "В море у Джаи теперь отмечен ПОТОК НОК-АП. Подплыви к нему — путь на Скайпию открыт!")]},
              shop=['meat', 'sake', 'gold', 'iron'], groups=6, flags=('knockup',), chest_fruit='bane',
              reward=dict(beli=210000, items=['gold'], xp=2000), desc="Остров насмешников."),
    'skypiea': I("Скайпия (Верхний Ярд)", 'sky', (30600, 14000), 30, 'sky', {'*': 'enel'}, ['sky_warrior', 'shandia', 'sky_warrior'],
                 mids={'*': ['satori', 'ohm', 'wyper']},
                 intro={'*': [('nar', "Небесный остров в десяти тысячах метров над морем. Облачное море, дайлы, золото Шандоры."),
                              ('x:Конис', "Бог Энель слышит всё... Мантра! Пожалуйста, не говори ничего плохого о нём!"),
                              ('enel', "Ятта! Добро пожаловать в мою страну. Скоро я уничтожу её и отправлюсь в Бесконечную Землю.")]},
                 outro={'*': [('nar', "Колокол Шандоры прозвенел над облаками! Народ Скайпии и Шандии наконец примирился."),
                              ('nar', "Ты чувствуешь странное... голоса людей. Это Мантра — ХАКИ НАБЛЮДЕНИЯ пробудилось!")]},
                 companion={'*': 'wyper_c'}, mentor=['haredas'], shop=['impact_dial', 'flame_dial', 'breath_dial', 'tone_dial', 'dial_shell', 'sorcery_clima'],
                 groups=7, flags=('haki_obs',), hidden=True, req='jaya', chest_fruit='goro', size=(84, 62),
                 reward=dict(beli=400000, items=['dial_shell', 'dial_shell', 'gold', 'gold', 'impact_dial'], xp=2400), desc="Остров в облаках."),
    'water7': I("Вотер Севен", 'paradise', (33600, 16600), 33, 'canal', {'*': 'franky'}, ['franky_family', 'franky_family', 'cp_agent'],
                intro={'*': [('nar', "Город Воды, столица кораблестроения. Каждый год Аква Лагуна затапливает его волнами."),
                             ('x:Айсберг', "Galley-La построит тебе корабль. Если, конечно, ты вернёшь украденные у тебя деньги."),
                             ('franky', "Ха! Ты хочешь вернуть свои денежки? Попробуй, братишка! Супе-е-ер!")]},
                outro={'*': [('franky', "Ты дерёшься как мужик! Когда-нибудь я построю корабль мечты... Держи, это древесина Адама."),
                             ('x:Айсберг', "Верфь Galley-La к твоим услугам. Здесь лучшие улучшения корабля во всём Раю.")]},
                shop=['meat', 'cola', 'adam_wood', 'steel', 'kairoseki', 'captain_coat'], shipwright=3, blacksmith=True,
                groups=6, reward=dict(beli=380000, items=['adam_wood', 'cola', 'cola', 'cola'], xp=2700), desc="Город корабелов."),
    'enies': I("Эниес Лобби", 'paradise', (35600, 14100), 36, 'judicial', {'*': 'lucci', 'marine': 'luffy_g2'}, ['cp_agent', 'marine', 'marine_rifle'],
               enemies_marine=['pirate', 'franky_family', 'pirate_brute'],
               mids={'*': ['kaku', 'jabra', 'blueno'], 'marine': ['zoro_boss']},
               intro={'*': [('nar', "Остров Правосудия, где никогда не наступает ночь. CP9 везёт пленницу к Вратам Правосудия."),
                            ('lucci', "Объявить войну Мировому Правительству? Ты даже не представляешь, что делаешь.")],
                      'pirate': [('me', "Я сожгу их флаг. Пусть знают — я объявляю войну всему миру!")],
                      'revo': [('me', "CP9 — тайные убийцы Правительства. Сегодня их правосудие падёт.")],
                      'marine': [('x:Вице-адмирал Лонз', "Пираты Соломенной Шляпы штурмуют Эниес Лобби! Это неслыханно! Останови их!"),
                                 ('luffy_g2', "Робин! Скажи, что хочешь жить!!!")]},
               outro={'*': [('nar', "Флаг Мирового Правительства сожжён. Об этом дне узнает весь мир."),
                            ('nar', "Среди обломков ты находишь СВИТОК РОКУСИКИ — тайные техники CP9.")],
                      'marine': [('nar', "Эниес Лобби пал, но твоя стойкость спасла сотни дозорных. Штаб отметил тебя.")]},
               mentor=['cp9_scroll'], shop=['cp_suit', 'steel', 'kairoseki', 'sea_king_meat'], groups=8, chest_fruit='neko_leopard',
               reward=dict(beli=520000, items=['kairoseki', 'sea_king_meat'], xp=3200), size=(84, 64), desc="Остров Правосудия."),
    'thriller': I("Триллер Барк", 'paradise', (38100, 17900), 39, 'ghost', {'*': 'moria'}, ['zombie', 'zombie', 'zombie'],
                  mids={'*': ['perona', 'oars']},
                  intro={'*': [('nar', "Огромный корабль-остров в Флорианском Треугольнике. Туман, зомби... и мёртвый мечник-скелет с афро."),
                               ('x:Брук', "Йо-хо-хо! Простите, можно взглянуть на ваши трусики? ...Шучу. Мория украл мою тень."),
                               ('moria', "Кишишиши! Твоя тень станет сильнейшим зомби моей армии!")]},
                  outro={'*': [('nar', "Утро. Тени вернулись к владельцам... Но на палубе появился Бартоломью Кума."),
                               ('x:Бартоломью Кума', "Если бы тебе предстояло путешествие... куда бы ты хотел отправиться?"),
                               ('nar', "Кума исчез, оставив странную лапу на твоём плече. Ты выжил.")]},
                  shop=['meat', 'sea_king_meat', 'vivre_card', 'iron'], groups=8, weather='fog', chest_fruit='horo',
                  reward=dict(beli=600000, items=['vivre_card', 'sea_king_meat'], xp=3700), desc="Остров-корабль ужасов."),
    'sabaody': I("Архипелаг Сабаоди", 'paradise', (42600, 16000), 42, 'mangrove', {'*': 'kizaru', 'marine': 'kid'}, ['marine', 'marine_rifle', 'pacifista'],
                 enemies_marine=['pirate', 'pirate_brute', 'pirate_gun'],
                 mids={'*': ['charlos', 'pacifista_boss'], 'marine': ['pacifista_boss']},
                 intro={'*': [('nar', "Сабаоди — 79 мангровых деревьев, пузыри, Небесные Драконы... и аукцион рабов."),
                              ('x:Шакки', "Рэйли сейчас в баре. Тебе нужно покрыть корабль смолой, чтобы спуститься к Острову Рыболюдей."),
                              ('charlos', "Ты не поклонился мне?! Ты, грязный простолюдин! Я тебя застрелю!")],
                        'marine': [('x:Адмирал Кизару', "Сверхновые устроили беспорядки. Иди — разберись с Юстассом Кидом, ладно?"),
                                   ('kid', "Дозорный? Отлично, будет кого швырнуть первым!")]},
                 outro={'*': [('x:Сильверс Рэйли', "Ты ударил Небесного Дракона? Ха-ха-ха! Мне это нравится. Я покрою твой корабль смолой. И... научу кое-чему."),
                              ('nar', "Корабль покрыт смолой! Теперь у Ред Лайн можно погрузиться к ОСТРОВУ РЫБОЛЮДЕЙ."),
                              ('nar', "Рэйли открыл в тебе ХАКИ ВООРУЖЕНИЯ (клавиша Q)!")],
                        'marine': [('nar', "Кид отступил. Штаб доволен. Тебе выдали разрешение спуститься в Новый Мир через Остров Рыболюдей.")]},
                 mentor=['rayleigh'], shop=['meat', 'sea_king_meat', 'kairoseki_knuckles', 'haki_bracer', 'fruit_charm', 'captain_coat'],
                 fruit_shop=['hana', 'mero', 'bari', 'yuki', 'kage', 'ope', 'gomu'], shipwright=2, blacksmith=True,
                 groups=8, flags=('coating', 'haki_arm', 'conq_awaken', 'auction'), weather='bubbles',
                 reward=dict(beli=800000, items=['sea_king_meat', 'kairoseki'], xp=4300), size=(86, 64), desc="Последний остров перед Новым Миром."),
    'amazon': I("Амазон Лили", 'calm', (37100, 21000), 44, 'jungle', {'*': 'hancock'}, ['kuja', 'kuja', 'beast'],
                mids={'*': ['sandersonia', 'marigold']},
                intro={'*': [('nar', "Остров женщин в Затишье. Мужчинам вход воспрещён под страхом смерти."),
                             ('x:Старейшина Нёон', "Ты не обращаешься в камень от взгляда Императрицы... Удивительно."),
                             ('hancock', "Неважно, что я делаю — мир меня простит. Встань на колени!")]},
                outro={'*': [('hancock', "...Ты... необычный. Возьми этот корабль на буксир — Юда-змеи доставят тебя куда захочешь."),
                             ('nar', "Императрица благодарна. Неподалёку отсюда — Импел Даун, а за ним — Маринфорд, где готовится казнь Портгаса Д. Эйса.")]},
                shop=['meat', 'sea_king_meat', 'haki_bracer', 'rumble_ball'], groups=6, chest_fruit='mero',
                reward=dict(beli=700000, items=['sea_king_meat', 'haki_bracer'], xp=4700), desc="Остров Кудзя."),
    'impel': I("Импел Даун", 'paradise', (39600, 12700), 47, 'prison', {'*': 'magellan', 'marine': 'ivankov'}, ['jailer', 'jailer', 'jail_beast'],
               enemies_marine=['pirate', 'pirate_brute', 'bandit_big'],
               mids={'*': ['minotaurus', 'shiryu'], 'marine': ['bonclay']},
               intro={'*': [('nar', "Великая подводная тюрьма. Шесть уровней ада: Багровый, Звериный, Голодный, Огненный, Ледяной... и Вечный."),
                            ('magellan', "Вторжение в Импел Даун? Ты либо безумец, либо герой. Здесь ты станешь узником.")],
                      'marine': [('x:Ханнябал', "Массовый побег! Иванков и Крокодайл ведут заключённых к выходу! Останови их!"),
                                 ('ivankov', "Ви-и-и-и! Чудеса бывают, дозорный! И мы — чудо!")]},
               outro={'*': [('ivankov', "Ты сильный кэндидат! В Ньюкама-лэнд тебя научат Окама Кэмпо — если найдёшь в себе смелость!"),
                            ('nar', "Сотни заключённых вырвались на свободу. Все плывут к Маринфорду.")],
                      'marine': [('nar', "Побег остановлен лишь частично. Война в Маринфорде начинается.")]},
               companion={'*': 'bonclay_c'}, mentor=['ivankov'], shop=['meat', 'sea_king_meat', 'kairoseki', 'vivre_card'],
               groups=8, chest_fruit='doku', reward=dict(beli=900000, items=['kairoseki', 'kairoseki'], xp=5200), desc="Тюрьма для худших преступников мира."),
    'marineford': I("Маринфорд: Война Величайших", 'paradise', (41600, 13600), 50, 'war', {'*': 'akainu', 'marine': 'whitebeard', 'hunter': 'whitebeard'},
                    ['marine', 'marine_officer', 'vice_admiral'], enemies_marine=['wb_pirate', 'wb_pirate', 'pirate_brute'],
                    mids={'*': ['aokiji'], 'marine': ['marco', 'jozu'], 'hunter': ['marco', 'jozu']},
                    intro={'*': [('nar', "Штаб Дозора. Белоус и 43 пиратских команды против Трёх Адмиралов и всей мощи Дозора."),
                                 ('nar', "На эшафоте — Портгас Д. Эйс, сын Короля Пиратов. Казнь через три часа."),
                                 ('akainu', "Сын Роджера должен умереть. Это и есть Справедливость.")],
                           'marine': [('x:Сэнгоку', "Пираты Белоуса здесь! Защитите эшафот любой ценой! Это решит судьбу эпохи!"),
                                      ('whitebeard', "Гурарарара! Я пришёл за своим сыном. Прочь с дороги, мальчишка!")],
                           'hunter': [('nar', "Награда за Белоуса — более пяти миллиардов. Самая большая добыча в истории."),
                                      ('whitebeard', "Охотник за головами, решивший охотиться на меня? Гурарарара!")]},
                    outro={'*': [('nar', "Война окончена. Эпоха изменилась. Шанкс Рыжеволосый остановил битву одной фразой."),
                                 ('x:Шанкс', "Эту войну закончу я! Кто хочет продолжить — сражайтесь со мной!"),
                                 ('nar', "Награда за твою голову взлетела до небес. Весь мир говорит о тебе.")],
                           'marine': [('nar', "Победа Дозора... ценой огромных потерь. Сэнгоку уходит в отставку. Тебя повышают.")]},
                    shop=['sea_king_meat', 'marine_coat', 'kairoseki', 'haki_bracer'], groups=10, flags=('war',),
                    reward=dict(beli=1500000, items=['sea_king_meat', 'sea_king_meat', 'kairoseki'], xp=6500), size=(92, 70),
                    chest_fruit='magu', desc="Штаб Морского Дозора."),
    'rusukaina': I("Русукайна", 'calm', (33100, 21200), 52, 'jungle', {'*': 'beast_king'}, ['beast', 'beast', 'sea_beast'],
                   intro={'*': [('nar', "Остров, где сменяются четыре сезона за год. Самые свирепые звери в мире."),
                                ('x:Сильверс Рэйли', "Два года. Я дам тебе два года. Сначала выживи здесь. Потом — хаки."),
                                ('nar', "ДВА ГОДА СПУСТЯ...")]},
                   outro={'*': [('x:Сильверс Рэйли', "Ты готов. Хаки Вооружения и Наблюдения — твои. Теперь — в Новый Мир!"),
                                ('nar', "Тренировка завершена! Предел хаки увеличен. Ты стал намного сильнее.")]},
                   mentor=['rayleigh'], groups=7, flags=('timeskip',), shop=['meat', 'sea_king_meat'],
                   reward=dict(beli=200000, items=['sea_king_meat', 'sea_king_meat'], xp=7000), desc="Остров тренировок."),
    'kuraigana': I("Курайгана (Замок Михоука)", 'calm', (24600, 20800), 60, 'ruins', {'*': 'mihawk'}, ['beast', 'beast', 'zombie'],
                   intro={'*': [('nar', "Руины королевства Шикка. Здесь живут обезьяны-воины хьюмандрилы... и Соколиный Глаз."),
                                ('mihawk', "Ты пришёл учиться — или пришёл умереть? Впрочем, разница невелика.")]},
                   outro={'*': [('mihawk', "Ты победил меня. Значит, меня превзошли. Возьми Ёру... и стань тем, кем должен.")]},
                   mentor=['mihawk'], groups=5, reward=dict(beli=1000000, items=['yoru'], xp=12000), weather='fog', desc="Древние руины. Сильнейший мечник."),
    # ========================== НОВЫЙ МИР ==========================
    'fishman': I("Остров Рыболюдей", 'new', (45700, 16000), 55, 'coral', {'*': 'hody'}, ['new_fishman', 'new_fishman', 'fishman'],
                 mids={'*': ['decken']},
                 intro={'*': [('nar', "В десяти тысячах метров под водой, у корней Древа Сабаоди, сияет коралловое королевство."),
                              ('x:Принцесса Сирахоси', "Я... я боюсь... Ходи Джонс хочет захватить королевство..."),
                              ('hody', "Ненависть к людям — это всё, что у нас есть! Королевство Рюгу утонет в ней!")]},
                 outro={'*': [('nar', "Солнце коснулось Острова Рыболюдей впервые за века. Рыболюди и люди — друзья."),
                              ('nar', "Впереди — Новый Мир. Здесь Лог Поуз с тремя стрелками... и здесь правят Императоры.")]},
                 companion={'*': 'hachi'}, mentor=['jinbe'], shop=['sea_king_meat', 'sea_king_scale', 'kairoseki', 'wano_kimono'],
                 groups=8, weather='bubbles', reward=dict(beli=1200000, items=['sea_king_scale', 'sea_king_scale'], xp=8000), desc="Подводное королевство."),
    'punk': I("Панк Хазард", 'new', (48600, 18600), 58, 'punk', {'*': 'caesar'}, ['caesar_soldier', 'centaur', 'caesar_soldier'],
              mids={'*': ['monet', 'vergo']},
              intro={'*': [('nar', "Остров, разделённый пополам: огонь и лёд — следы битвы Акаину и Аокидзи."),
                           ('x:Трафальгар Ло', "Цезарь Клаун делает SMILE для Кайдо. Если уничтожим лабораторию — запустим цепочку, что свергнет Императора."),
                           ('caesar', "Шуро-ро-ро! Мои дети — мои подопытные! Убирайтесь, или станете газом!")]},
              outro={'*': [('nar', "Лаборатория уничтожена. Дети спасены. Цепь событий начинается: Дофламинго в ярости.")]},
              shop=['sea_king_meat', 'kairoseki', 'steel', 'haki_bracer'], groups=8, chest_fruit='yuki',
              fruit_shop=['hie', 'gasu', 'yuki', 'ope'],
              reward=dict(beli=1400000, items=['kairoseki', 'pacifista_part'], xp=9000), desc="Остров огня и льда."),
    'dressrosa': I("Королевство Дрессроза", 'new', (51600, 15600), 62, 'toy', {'*': 'doflamingo'}, ['toy_soldier', 'donquixote', 'gladiator'],
                   mids={'*': ['pica', 'diamante', 'sugar']},
                   intro={'*': [('nar', "Страна любви, страсти и игрушек. Но игрушки — это люди, лишённые памяти."),
                                ('x:Ребекка', "В Колизее Корриды главный приз — Мера Мера но Ми, фрукт Огненного Кулака Эйса!"),
                                ('doflamingo', "Фуфуфуфу... Ты разрушил мой бизнес. Я разрушу тебя, страну... и твоих друзей.")]},
                   outro={'*': [('nar', "Птичья Клетка исчезла. Дрессроза свободна!"),
                                ('x:Бартоломео', "Сэмпай! Мы, 7 команд, клянёмся тебе в верности! Это ПЛАВАЮЩИЙ ФЛОТ!")],
                          'marine': [('x:Адмирал Фудзитора', "...Я поклонюсь этому народу. Дозор был слеп, когда позволил Дофламинго править."),
                                     ('nar', "Фудзитора извинился перед королём Дрессрозы. Ты стоял рядом.")]},
                   companion={'*': 'bartolomeo', 'revo': 'sabo', 'marine': 'smoker_c', 'hunter': 'cavendish'},
                   shop=['sea_king_meat', 'gold', 'nidai_kitetsu', 'captain_coat', 'vivre_card'], fruit_shop=['ito', 'bari', 'ishi', 'zushi', 'mera'],
                   blacksmith=True, groups=9, flags=('colosseum',), chest_fruit='mera', size=(88, 66),
                   reward=dict(beli=2200000, items=['gold', 'gold', 'vivre_card'], xp=11000), desc="Страна страсти и игрушек."),
    'zou': I("Зоу", 'new', (54600, 13100), 65, 'forest', {'*': 'jack'}, ['beast_pirate', 'beast_pirate', 'gifter'],
             intro={'*': [('nar', "Остров на спине гигантского слона Зунеши, бредущего по морю тысячу лет. Здесь живут минки."),
                          ('x:Кэррот', "Гару-гару! Джек «Засуха» напал на наш народ! Он ищет самураев Вано!"),
                          ('jack', "Где Райзо? Где ниндзя? Отвечайте — или я убью всех.")]},
             outro={'*': [('x:Инуараши', "Ты защитил Зоу. Мы покажем тебе Красный Понеглиф — один из четырёх, ведущих к Лаф Тейл."),
                          ('nar', "Получена копия Ласт-понеглифа (1/4)! Путь к Лаф Тейл начинается.")]},
             companion={'*': 'carrot'}, mentor=['minks'], shop=['sea_king_meat', 'sea_king_scale', 'wano_kimono'], groups=8,
             flags=('poneglyph',), reward=dict(beli=2400000, items=['sea_king_scale', 'gold'], xp=12000), desc="Остров на спине слона."),
    'wci': I("Тотленд: Остров Пирога", 'new', (58100, 18100), 68, 'candy', {'*': 'katakuri'}, ['chess_soldier', 'homie', 'chess_soldier'],
             mids={'*': ['cracker']}, extra_boss='big_mom',
             intro={'*': [('nar', "Королевство сладостей Императрицы Биг Мам. Деревья из конфет, реки газировки... и хоми, живущие душами."),
                          ('x:Пудинг', "Свадебное чаепитие — ловушка. Мама хочет получить Ласт-понеглиф... и вас всех."),
                          ('katakuri', "Ты прошёл далеко. Но в Зеркальном Мире я вижу будущее. Ты не уйдёшь.")]},
             outro={'*': [('katakuri', "...Будущее изменилось. Ты увидел его вместе со мной. Это — Предвидение."),
                          ('nar', "ХАКИ НАБЛЮДЕНИЯ эволюционировало: открыто ПРЕДВИДЕНИЕ БУДУЩЕГО (клавиша C)!"),
                          ('nar', "Получена копия Ласт-понеглифа (2/4)!")]},
             shop=['sea_king_meat', 'gold', 'rumble_ball', 'captain_coat'], fruit_shop=['mochi', 'soru'],
             groups=9, flags=('future_sight', 'poneglyph'), chest_fruit='mochi',
             reward=dict(beli=2800000, items=['gold', 'gold', 'sea_king_meat'], xp=14000), desc="Королевство сладостей."),
    'wano': I("Страна Вано: Онигасима", 'new', (62100, 14600), 73, 'wano', {'*': 'kaido'}, ['samurai', 'beast_pirate', 'gifter'],
              mids={'*': ['king', 'queen', 'orochi']}, music='wano',
              intro={'*': [('nar', "Страна самураев, закрытая от мира. Двадцать лет ею правят сёгун Орочи и Император Кайдо."),
                           ('x:Кодзуки Момоносукэ', "Двадцать лет назад мой отец Одэн погиб... Мы ждали этого дня. Огненный фестиваль!"),
                           ('x:Хьёгоро', "Хочешь победить Кайдо? Хаки Вооружения недостаточно. Тебе нужен Рюо."),
                           ('kaido', "Уоро-ро-ро! Кто осмелился напасть на Онигасиму в ночь фестиваля?!")]},
              outro={'*': [('nar', "Барабаны Освобождения звучат над Вано. Кайдо пал. Граница открыта!"),
                           ('x:Ямато', "Я — Кодзуки Одэн! ...Ну, вернее, его наследница. Возьми меня с собой в море!"),
                           ('nar', "Получена копия Ласт-понеглифа (3/4)! Получен клинок ЭНМА.")]},
              companion={'*': 'yamato'}, mentor=['hyogoro'], shop=['wano_kimono', 'tamahagane', 'nidai_kitetsu', 'sake', 'sea_king_meat'],
              fruit_shop=['inu_makami', 'ryu_ptera', 'uo'], blacksmith=True, groups=10, weather='petals', flags=('poneglyph', 'ryou', 'conq_coat'),
              chest_fruit='uo', size=(92, 70),
              reward=dict(beli=4000000, items=['enma', 'tamahagane', 'tamahagane', 'sake'], xp=18000), desc="Страна самураев."),
    'egghead': I("Остров Будущего Эгхэд", 'new', (66100, 17600), 80, 'future', {'*': 'saturn', 'marine': 'luffy_g5'}, ['seraphim', 'marine', 'cp_agent'],
                 enemies_marine=['pirate', 'pirate_brute', 'giant_warrior'],
                 mids={'*': ['kizaru_eh', 'lucci_eh', 'seraphim_hawk'], 'marine': ['zoro_boss']},
                 intro={'*': [('nar', "Остров на 500 лет опережающий мир. Лаборатория доктора Вегапанка."),
                              ('x:Доктор Вегапанк', "Мир скоро утонет. Море поднимется на двести метров... Я должен рассказать людям правду!"),
                              ('saturn', "Вегапанк знал слишком много. Бастер Колл. Никто не покинет этот остров.")],
                        'marine': [('x:Адмирал Кизару', "Это... приказ Старейшин. Сатурн-сама требует уничтожить остров. Прости, старый друг..."),
                                   ('luffy_g5', "Ши-ши-ши! Ты пришёл драться? Тогда держись!")]},
                 outro={'*': [('x:Доктор Вегапанк', "(Голос по всему миру) ...Мир должен узнать о Пустом Веке, о Древнем Королевстве и о Джой Бое!"),
                              ('nar', "Великаны Эльбафа прибыли на помощь. Корабль прорывается сквозь флот Бастер Колла!"),
                              ('nar', "Следующая цель — легендарная страна воинов-великанов: ЭЛЬБАФ.")],
                        'marine': [('nar', "Ты поймал... нет, остановил Бога Солнца. Но голос Вегапанка уже прозвучал на весь мир."),
                                   ('nar', "Твоё звание — легенда Дозора. Следующая цель: Эльбаф.")]},
                 shop=['raid_suit', 'pacifista_part', 'kairoseki', 'sea_king_meat', 'fruit_charm', 'haki_bracer'],
                 fruit_shop=['pika', 'nikyu', 'gomu'], groups=10, chest_fruit='pika', size=(90, 68),
                 reward=dict(beli=5000000, items=['raid_suit', 'pacifista_part'], xp=24000), desc="Остров будущего."),
    'elbaf': I("Эльбаф — Страна Великанов", 'new', (70600, 15600), 85, 'giant', {'*': 'shamrock', 'marine': 'loki'}, ['holy_soldier', 'giant_warrior', 'holy_soldier'],
               enemies_marine=['giant_warrior', 'giant_warrior', 'beast'],
               mids={'*': ['gunko', 'sommers', 'killingham'], 'marine': ['gunko']},
               intro={'*': [('nar', "Эльбаф. Мировое Древо Адама, на ветвях которого стоят города великанов. Страна величайших воинов."),
                            ('x:Ярул', "Святые Рыцари пришли из Мэри Джоа. Они хотят подчинить Эльбаф... и нашего проклятого принца."),
                            ('loki', "Хе-хе-хе! Освободи меня, и я скажу тебе, где спрятано величайшее оружие!"),
                            ('shamrock', "Великаны, пираты, мечтатели... Все склонятся перед Божьими Рыцарями.")],
                      'marine': [('x:Святой Гунко', "Дозор поддержит Святых Рыцарей. Принц Локи — угроза миру. Уничтожь его."),
                                 ('loki', "Дозорный, значит? Ха! Ну попробуй удержать меня в цепях!")]},
               outro={'*': [('loki', "Хе... ты сражался за Эльбаф. Мы, великаны, не забываем долгов. Я пойду с тобой, как воин!"),
                            ('nar', "Ты получаешь Ласт-понеглиф (4/4)... Путь к Лаф Тейл открыт?"),
                            ('nar', "...Продолжение истории ещё пишется. Но ты уже легенда этого моря.")],
                      'marine': [('nar', "Святые Рыцари довольны. Но в глубине души ты понимаешь: справедливость — не у тех, у кого власть."),
                                 ('nar', "Продолжение ещё пишется...")]},
               companion={'*': 'loki_c'}, shop=['giant_timber', 'scale_armor', 'sea_king_meat', 'tamahagane', 'sake'],
               fruit_shop=['nidhogg'], blacksmith=True, groups=10, flags=('poneglyph', 'finale'), chest_fruit='nidhogg', size=(92, 70),
               reward=dict(beli=6000000, items=['giant_timber', 'giant_timber', 'emperor_ring'], xp=30000), desc="Страна воинов-великанов."),
    # ========================== ХАБЫ И СУПЕРБОССЫ ==========================
    'marine_hq': I("Новый Маринфорд (Штаб Дозора)", 'new', (47100, 12500), 70, 'hq', {'*': 'akainu_fa', 'marine': None},
                   ['marine', 'vice_admiral', 'marine_rifle'], hub='marine',
                   intro={'*': [('nar', "Новый штаб Дозора в Новом Мире. Здесь правит Адмирал Флота Сакадзуки."),
                                ('akainu_fa', "Пират в сердце Справедливости? Сегодня ты сгоришь.")],
                          'marine': [('garp', "Гья-ха-ха! Хочешь тренироваться? Я научу тебя Кулаку Любви!"),
                                     ('nar', "Штаб Дозора: тренировки, снабжение и награды за службу.")]},
                   outro={'*': [('nar', "Адмирал Флота повержен. Ты бросил вызов самому сердцу Справедливости."),
                                ('nar', "Получен трофей: Плащ «Справедливость».")]},
                   mentor=['garp'], shop=['marine_coat', 'kairoseki', 'sea_king_meat', 'haki_bracer', 'eternal_pose'],
                   shipwright=4, blacksmith=True, groups=8, reward=dict(beli=3000000, items=['marine_coat'], xp=15000), desc="Сердце Справедливости."),
    'baltigo': I("Момоиро: Штаб Революции", 'new', (57600, 12100), 60, 'hq_revo', {'*': None}, ['bandit'], groups=0, hub='revo',
                 intro={'*': [('nar', "Тайная база Революционной Армии. Здесь Драгон планирует свержение Правительства."),
                              ('sabo_boss', "Ты пришёл к нам? Каждый, кто борется за свободу, — наш брат.")]},
                 outro={'*': [('nar', "Революционеры приветствуют тебя.")]},
                 mentor=['sabo_m', 'koala_m', 'ivankov'], shop=['sea_king_meat', 'haki_bracer', 'fruit_charm', 'vivre_card', 'eternal_pose'],
                 flags=('no_combat',), reward=dict(beli=0, items=[], xp=500), desc="База Революционной Армии."),
    'karai_bari': I("Карай Бари: Кросс Гильдия", 'new', (52600, 19600), 66, 'cactus', {'*': None}, ['pirate'], groups=0, hub='hunter',
                    intro={'*': [('buggy', "Добро пожаловать в Кросс Гильдию! Я — Великий Лидер Багги! Мы назначаем награды... за ДОЗОРНЫХ!"),
                                 ('crocodile', "...Только не путайся под ногами. Награды — на доске.")]},
                    outro={'*': [('nar', "Кросс Гильдия — лучшее место для охотника.")]},
                    companion={'hunter': 'buggy_c'}, mentor=['mihawk'], shop=['gold', 'sea_king_meat', 'nidai_kitetsu', 'eternal_pose', 'captain_coat'],
                    flags=('no_combat',), reward=dict(beli=0, items=[], xp=500), desc="База Кросс Гильдии."),
    'hachinosu': I("Хатиносу: Остров Пиратов", 'new', (64600, 19900), 92, 'pirate_isle', {'*': 'blackbeard'}, ['bb_pirate', 'bb_pirate', 'pirate_brute'],
                   intro={'*': [('nar', "Остров-крепость Пиратов Чёрной Бороды. Здесь собраны носители украденных фруктов."),
                                ('blackbeard', "Зе-ха-ха-ха! Ты пришёл прямо в мою тьму! Какая удача!")]},
                   outro={'*': [('nar', "Чёрная Борода отступил во тьму. Его империя пошатнулась."),
                                ('nar', "Получен трофей: Кольцо Императора.")]},
                   groups=9, chest_fruit='yami', fruit_shop=['gura', 'yami'], reward=dict(beli=8000000, items=['emperor_ring', 'emperor_coat'], xp=40000), desc="Логово Чёрной Бороды."),
    'shanks_isle': I("Остров Красноволосого", 'new', (68100, 12100), 98, 'village', {'*': 'shanks'}, ['pirate', 'pirate_gun', 'pirate_brute'],
                     intro={'*': [('nar', "Владения Императора Шанкса. Здесь пируют Пираты Рыжеволосого."),
                                  ('shanks', "О! Наконец-то. Я слышал о тебе. Ну что, выпьем — или подерёмся? А, давай и то и другое!")]},
                     outro={'*': [('shanks', "Ха-ха-ха! Ты великолепен! Новая эпоха в надёжных руках. Держи — это Грифон. Верни его мне... на вершине."),
                                  ('nar', "Ты победил Императора. Ты — легенда этого мира.")]},
                     groups=6, reward=dict(beli=10000000, items=['gryphon', 'emperor_coat'], xp=60000), desc="Император Шанкс."),
}

ISLAND_ORDER = ['dawn', 'shells', 'orange', 'syrup', 'baratie', 'arlong', 'loguetown', 'twin_capes', 'whisky', 'little_garden', 'drum',
                'alabasta', 'jaya', 'skypiea', 'water7', 'enies', 'thriller', 'sabaody', 'amazon', 'impel', 'marineford', 'rusukaina',
                'fishman', 'punk', 'dressrosa', 'zou', 'wci', 'wano', 'egghead', 'elbaf']
SIDE_ISLANDS = ['kuraigana', 'marine_hq', 'baltigo', 'karai_bari', 'hachinosu', 'shanks_isle']

KNOCKUP_POS = (31600, 13600)
REVERSE_MOUNTAIN_POS = (14400, 16000)
FISHMAN_GATE_POS = (44000, 16000)

THEMES = {
    'village': dict(ground=(96, 160, 70), ground2=(110, 175, 80), path=(180, 160, 110), sand=(225, 210, 160), water=(50, 130, 200),
                    bld=[(200, 170, 130), (220, 200, 160), (180, 140, 100)], roof=[(170, 60, 50), (90, 110, 160), (160, 110, 60)], trees='leafy',
                    density=0.35, town=0.45, plaza=(170, 150, 110)),
    'base': dict(ground=(110, 160, 80), ground2=(120, 170, 90), path=(170, 170, 170), sand=(225, 210, 160), water=(50, 130, 200),
                 bld=[(230, 230, 235), (210, 210, 220)], roof=[(70, 110, 190), (240, 240, 245)], trees='leafy', density=0.2, town=0.5, plaza=(185, 185, 190), fort=True),
    'town': dict(ground=(110, 160, 80), ground2=(100, 150, 75), path=(190, 175, 140), sand=(225, 210, 160), water=(50, 130, 200),
                 bld=[(230, 200, 150), (220, 180, 140), (200, 200, 210), (240, 220, 180)], roof=[(180, 70, 50), (150, 80, 60), (90, 90, 120), (200, 120, 50)],
                 trees='leafy', density=0.15, town=0.7, plaza=(200, 185, 150)),
    'restaurant': dict(ground=(140, 100, 60), ground2=(150, 108, 66), path=(160, 115, 70), sand=(140, 100, 60), water=(40, 120, 200),
                       bld=[(230, 220, 200)], roof=[(200, 60, 60)], trees=None, density=0.0, town=0.3, plaza=(160, 115, 70), deck=True),
    'fishpark': dict(ground=(100, 165, 80), ground2=(240, 160, 60), path=(170, 170, 170), sand=(225, 210, 160), water=(40, 120, 200),
                     bld=[(240, 240, 220), (220, 220, 200)], roof=[(60, 120, 160), (200, 100, 60)], trees='orange', density=0.3, town=0.4, plaza=(180, 180, 175)),
    'cape': dict(ground=(120, 160, 90), ground2=(130, 170, 95), path=(180, 170, 140), sand=(230, 215, 170), water=(40, 110, 190),
                 bld=[(230, 230, 230)], roof=[(120, 120, 120)], trees='palm', density=0.2, town=0.1, plaza=(180, 170, 140)),
    'cactus': dict(ground=(200, 170, 110), ground2=(210, 180, 120), path=(180, 150, 100), sand=(230, 210, 160), water=(40, 120, 200),
                   bld=[(220, 190, 140), (230, 200, 160)], roof=[(150, 100, 70), (200, 150, 90)], trees='cactus', density=0.25, town=0.55, plaza=(190, 160, 110)),
    'jungle': dict(ground=(60, 120, 50), ground2=(70, 135, 55), path=(140, 110, 70), sand=(220, 200, 150), water=(40, 120, 180),
                   bld=[(150, 110, 70)], roof=[(110, 140, 70)], trees='jungle', density=0.6, town=0.1, plaza=(130, 110, 70)),
    'jungle_town': dict(ground=(80, 130, 60), ground2=(90, 140, 65), path=(160, 130, 90), sand=(220, 200, 150), water=(40, 120, 180),
                        bld=[(170, 130, 90), (160, 120, 80)], roof=[(120, 80, 50), (100, 70, 40)], trees='jungle', density=0.4, town=0.45, plaza=(160, 130, 90)),
    'snow': dict(ground=(235, 240, 248), ground2=(220, 228, 240), path=(200, 205, 215), sand=(210, 215, 225), water=(40, 90, 150),
                 bld=[(200, 160, 120), (180, 140, 110)], roof=[(250, 250, 255), (230, 235, 245)], trees='pine', density=0.4, town=0.35, plaza=(205, 205, 215)),
    'desert': dict(ground=(225, 195, 130), ground2=(235, 205, 140), path=(205, 175, 115), sand=(240, 215, 160), water=(40, 120, 190),
                   bld=[(235, 215, 170), (225, 200, 150), (240, 225, 190)], roof=[(210, 180, 120), (200, 160, 100)], trees='palm', density=0.12, town=0.5, plaza=(220, 190, 135), palace=True),
    'sky': dict(ground=(250, 250, 255), ground2=(235, 240, 255), path=(200, 220, 250), sand=(240, 245, 255), water=(200, 225, 255),
                bld=[(240, 230, 200), (250, 240, 220)], roof=[(220, 180, 90), (250, 210, 110)], trees='jungle', density=0.3, town=0.3, plaza=(240, 220, 160), ruins=True),
    'canal': dict(ground=(170, 170, 175), ground2=(160, 160, 168), path=(200, 190, 170), sand=(210, 200, 180), water=(50, 140, 210),
                  bld=[(230, 210, 180), (220, 190, 160), (240, 230, 210)], roof=[(120, 140, 180), (180, 90, 60)], trees='leafy', density=0.05, town=0.75, plaza=(205, 195, 175), canals=True),
    'judicial': dict(ground=(190, 190, 195), ground2=(180, 180, 188), path=(210, 210, 215), sand=(200, 200, 205), water=(40, 100, 180),
                     bld=[(240, 240, 245), (225, 225, 235)], roof=[(80, 90, 120), (60, 70, 100)], trees='leafy', density=0.05, town=0.6, plaza=(215, 215, 220), fort=True),
    'ghost': dict(ground=(70, 80, 70), ground2=(60, 70, 62), path=(100, 95, 85), sand=(110, 105, 95), water=(30, 50, 70),
                  bld=[(90, 80, 90), (80, 70, 80)], roof=[(50, 40, 60), (70, 50, 70)], trees='dead', density=0.35, town=0.35, plaza=(95, 90, 85)),
    'mangrove': dict(ground=(120, 170, 100), ground2=(130, 180, 110), path=(190, 175, 140), sand=(220, 210, 170), water=(60, 150, 200),
                     bld=[(240, 220, 200), (230, 210, 230)], roof=[(200, 100, 140), (100, 160, 200)], trees='mangrove', density=0.3, town=0.5, plaza=(200, 190, 160)),
    'prison': dict(ground=(80, 70, 70), ground2=(90, 60, 55), path=(110, 100, 95), sand=(100, 90, 85), water=(30, 60, 90),
                   bld=[(110, 100, 100), (100, 90, 90)], roof=[(60, 50, 50), (80, 60, 50)], trees=None, density=0.0, town=0.55, plaza=(115, 105, 100), fort=True, lava_spots=True),
    'war': dict(ground=(190, 190, 195), ground2=(170, 200, 230), path=(210, 210, 215), sand=(200, 200, 205), water=(40, 100, 180),
                bld=[(240, 240, 245), (225, 225, 235)], roof=[(70, 110, 190), (230, 230, 240)], trees=None, density=0.0, town=0.4, plaza=(215, 215, 220), fort=True, ice_bay=True),
    'coral': dict(ground=(230, 200, 210), ground2=(210, 180, 220), path=(240, 220, 200), sand=(240, 230, 200), water=(40, 100, 170),
                  bld=[(250, 220, 230), (220, 240, 250)], roof=[(240, 120, 160), (120, 200, 230)], trees='coral', density=0.35, town=0.45, plaza=(240, 220, 210)),
    'punk': dict(ground=(230, 240, 250), ground2=(150, 60, 40), path=(160, 160, 170), sand=(170, 170, 175), water=(40, 80, 130),
                 bld=[(200, 200, 210)], roof=[(120, 130, 150)], trees='dead', density=0.15, town=0.25, plaza=(170, 170, 180), split=True),
    'toy': dict(ground=(140, 190, 90), ground2=(150, 200, 100), path=(230, 200, 150), sand=(230, 215, 170), water=(50, 140, 210),
                bld=[(250, 220, 170), (250, 200, 200), (230, 230, 250), (250, 250, 200)], roof=[(230, 70, 70), (250, 160, 40), (70, 140, 230), (230, 100, 170)],
                trees='leafy', density=0.15, town=0.65, plaza=(230, 205, 160), colosseum=True),
    'forest': dict(ground=(70, 140, 70), ground2=(80, 150, 75), path=(150, 120, 80), sand=(200, 190, 150), water=(40, 120, 170),
                   bld=[(170, 120, 80)], roof=[(90, 140, 70), (150, 100, 60)], trees='leafy', density=0.55, town=0.2, plaza=(150, 130, 90)),
    'candy': dict(ground=(250, 200, 220), ground2=(240, 230, 190), path=(250, 240, 230), sand=(250, 230, 200), water=(170, 120, 200),
                  bld=[(250, 230, 200), (240, 190, 220), (220, 240, 250)], roof=[(250, 120, 170), (150, 220, 250), (250, 200, 80)], trees='candy', density=0.35, town=0.5, plaza=(250, 235, 215)),
    'wano': dict(ground=(110, 150, 80), ground2=(120, 160, 90), path=(190, 175, 140), sand=(220, 205, 165), water=(60, 110, 160),
                 bld=[(140, 100, 70), (120, 85, 60), (200, 180, 150)], roof=[(60, 60, 70), (140, 40, 40), (80, 70, 60)], trees='sakura', density=0.3, town=0.55, plaza=(190, 175, 140), castle=True),
    'future': dict(ground=(220, 225, 235), ground2=(200, 210, 225), path=(240, 240, 250), sand=(230, 230, 240), water=(40, 120, 200),
                   bld=[(240, 245, 250), (220, 230, 245)], roof=[(120, 200, 240), (250, 150, 200)], trees='tech', density=0.15, town=0.55, plaza=(235, 240, 250)),
    'giant': dict(ground=(90, 140, 70), ground2=(100, 150, 80), path=(160, 140, 100), sand=(210, 200, 160), water=(40, 100, 160),
                  bld=[(170, 130, 90), (150, 110, 80)], roof=[(100, 80, 60), (120, 60, 50)], trees='giant', density=0.4, town=0.4, plaza=(160, 140, 100), big=True),
    'ruins': dict(ground=(90, 100, 80), ground2=(80, 90, 72), path=(130, 125, 115), sand=(150, 145, 130), water=(40, 70, 100),
                  bld=[(140, 135, 125), (120, 115, 108)], roof=[(90, 85, 80), (70, 70, 70)], trees='dead', density=0.3, town=0.3, plaza=(130, 125, 115), ruins=True),
    'hq': dict(ground=(190, 190, 195), ground2=(180, 180, 188), path=(215, 215, 220), sand=(200, 200, 205), water=(40, 100, 180),
               bld=[(245, 245, 250), (230, 230, 240)], roof=[(70, 110, 190), (240, 240, 245)], trees='leafy', density=0.05, town=0.6, plaza=(220, 220, 225), fort=True),
    'hq_revo': dict(ground=(240, 180, 200), ground2=(230, 170, 190), path=(250, 220, 220), sand=(240, 220, 210), water=(50, 120, 190),
                    bld=[(250, 220, 230), (240, 200, 220)], roof=[(200, 80, 130), (60, 140, 90)], trees='candy', density=0.2, town=0.45, plaza=(250, 220, 225)),
    'pirate_isle': dict(ground=(110, 100, 80), ground2=(100, 90, 72), path=(140, 120, 90), sand=(190, 175, 140), water=(30, 70, 110),
                        bld=[(120, 90, 70), (100, 80, 65)], roof=[(40, 35, 35), (70, 40, 40)], trees='dead', density=0.25, town=0.5, plaza=(140, 120, 95), fort=True),
}

# ==================================================================
#  БОЕВАЯ СИСТЕМА: УДАР, БОЕЦ
# ==================================================================
CC_STATUSES = ('freeze', 'stun', 'shock', 'bind', 'sleep', 'petrify', 'fear')
STATUS_NAMES = {'burn': "Ожог", 'freeze': "Заморозка", 'stun': "Оглушение", 'shock': "Шок", 'slow': "Замедление", 'bleed': "Кровотечение",
                'poison': "Яд", 'bind': "Скован", 'fear': "Страх", 'sleep': "Сон", 'petrify': "Камень", 'weaken': "Слабость", 'nullified': "Сила отменена",
                'wet': "Мокрый"}
LOGIA_COUNTER = {'sand': ('water',), 'fire': ('magma', 'water'), 'ice': ('magma', 'fire'), 'smoke': ('water',), 'gas': ('fire', 'water'),
                 'snow': ('fire', 'magma'), 'thunder': ('rubber', 'nika'), 'light': (), 'magma': (), 'dark_special': ()}

class Hit:
    __slots__ = ("dmg", "el", "knock", "launch", "stun", "src", "haki", "ignore_def", "status", "crit", "heavy", "destroy", "ryou",
                 "conq", "fruit", "seastone", "sword", "nullify", "ult", "pos", "knockout", "drain_life")
    def __init__(self, dmg, el='phys', knock=None, launch=0.0, stun=0.2, src=None, **kw):
        self.dmg = dmg; self.el = el; self.knock = knock if knock is not None else V(0, 0); self.launch = launch
        self.stun = stun; self.src = src
        self.haki = kw.get('haki', False); self.ignore_def = kw.get('ignore_def', False); self.status = kw.get('status')
        self.crit = kw.get('crit', False); self.heavy = kw.get('heavy', False); self.destroy = kw.get('destroy', 1.0)
        self.ryou = kw.get('ryou', False); self.conq = kw.get('conq', False); self.fruit = kw.get('fruit', False)
        self.seastone = kw.get('seastone', False); self.sword = kw.get('sword', False); self.nullify = kw.get('nullify', False)
        self.ult = kw.get('ult', False); self.pos = kw.get('pos'); self.knockout = kw.get('knockout', False)
        self.drain_life = kw.get('drain_life', False)

class Fighter:
    _id = 0
    def __init__(self, scene, team, app, pos, level=1, name="", kind='mook', hp_mult=1.0, dmg_mult=1.0, speed=160):
        Fighter._id += 1
        self.uid = Fighter._id
        self.scene = scene
        self.team = team
        self.app = app
        self.name = name
        self.kind = kind  # player/mook/elite/boss/ally/summon
        self.pos = V(pos)
        self.vel = V(0, 0)
        self.knock_v = V(0, 0)
        self.z = 0.0
        self.vz = 0.0
        self.facing = math.pi / 2
        self.aim = 0.0
        self.level = level
        self.scale = app.get('scale', 1.0)
        self.radius = 13 * self.scale
        self.max_hp = (60 + 22 * level) * hp_mult
        self.hp = self.max_hp
        self.ghost_hp = self.hp
        self.atk = (8 + 2.0 * level) * dmg_mult
        self.fruit_pow = self.atk
        self.haki_pow = self.atk
        self.defn = level * 1.2
        self.armor = 0.0
        self.base_speed = speed
        self.crit = 0.05
        self.state = 'idle'
        self.pose = 'idle'
        self.pose_t = 0.0
        self.pose_dur = 0.3
        self.phase = random.uniform(0, 6)
        self.walk = 0.0
        self.statuses = {}
        self.buffs = []
        self.shield = None
        self.cooldowns = {}
        self.moves = []
        self.action = None
        self.combo_i = 0
        self.combo_t = 0.0
        self.attack_cd = 0.0
        self.hitflash = 0.0
        self.invuln = 0.0
        self.stagger = 0.0
        self.logia = None
        self.immune = None
        self.blunt_res = 0.0
        self.dead = False
        self.death_t = 0.0
        self.remove = False
        self.ai = None
        self.is_boss = kind == 'boss'
        self.elite = kind in ('elite', 'boss')
        self.haki_always = False
        self.dodge = 0.0
        self.fs = False
        self.armament = False
        self.form = None
        self.form_t = 0.0
        self.style = 'brawler'
        self.combo_def = STYLES['brawler']['combo']
        self.combo_el = 'phys'
        self.ranged_basic = False
        self.weapon_seastone = False
        self.fruit_user = False
        self.fishman = False
        self.room = None
        self.life_t = None
        self.boss_id = None
        self.group = None
        self.xp_value = 10
        self.bounty = 0
        self.speech = None
        self.speech_t = 0.0
        self.last_safe = V(pos)
        self.drown_t = 0.0
        self.in_water = False
        self.hist = []
        self.tint = None
        self.guarding = False
        self.guard_t = 0.0
        self.parry_window = 0.0
        self.perfect_dodge = 0.0
        self.no_knock = False
        self.phase_idx = 0
        self.revive = False
        self.dmg_taken_mult = 1.0
        self.wet_t = 0.0
        self.heavy_bonus = 0.0
        self.fire_bonus = 0.0
        self.summoner = None
        self.drops = []
        self.knocked_out = False

    # --------------- свойства ---------------
    def alive(self):
        return not self.dead

    def has(self, st):
        return self.statuses.get(st, (0,))[0] > 0

    def can_act(self):
        if self.dead:
            return False
        for s in CC_STATUSES:
            if self.has(s):
                return False
        return self.stagger <= 0 and self.z <= 2 or (self.z > 2 and self.vz == 0 and self.form == 'dragon')

    def can_move(self):
        return self.can_act() and not self.has('bind')

    def buff_mult(self, key):
        m = 1.0
        for b in self.buffs:
            m *= b.get(key, 1.0)
        return m

    def speed(self):
        s = self.base_speed * self.buff_mult('spd')
        if self.has('slow'):
            s *= 0.5
        if self.in_water and not self.fishman:
            s *= 0.55 if not self.fruit_user else 0.3
        if self.in_water and self.fishman:
            s *= 1.35
        if self.guarding:
            s *= 0.4
        return s

    def power(self, scale='atk'):
        if scale == 'fruit':
            p = self.fruit_pow
        elif scale == 'haki':
            p = self.haki_pow
        else:
            p = self.atk
        m = self.buff_mult('dmg')
        if self.armament:
            m *= self.arm_mult()
        if self.has('weaken'):
            m *= 0.7
        return p * m

    def arm_mult(self):
        return 1.2

    def uses_haki(self):
        return self.armament or self.haki_always

    def hostile_to(self, other):
        if other is self or other.dead:
            return False
        if self.team == 'enemy':
            return other.team in ('player', 'ally')
        if self.team in ('player', 'ally'):
            return other.team == 'enemy'
        return False

    # --------------- анимация ---------------
    def set_pose(self, pose, dur=0.3):
        self.pose = pose
        self.pose_t = 0.0
        self.pose_dur = max(0.05, dur)

    def anim_state(self):
        pt = clamp(self.pose_t / self.pose_dur, 0, 1)
        pose = self.pose
        if self.dead:
            pose = 'down'
        elif self.has('stun') or self.has('sleep') or self.stagger > 0:
            pose = 'hurt'
        elif self.guarding:
            pose = 'block'
        elif pose != 'idle' and pt >= 1:
            pose = 'idle'
        if pose == 'idle' and self.walk > 0.1:
            pose = 'walk'
        expr = 'normal'
        if self.kind in ('boss', 'player') and self.action is not None:
            expr = 'angry'
        if self.action is not None and getattr(self.action, 'ult', False):
            expr = 'ult'
        if pose == 'hurt':
            expr = 'hurt'
        st = dict(phase=self.phase, walk=self.walk, pose=pose, pose_t=pt, z=self.z, flash=self.hitflash, expr=expr, aim=self.aim)
        if self.kind in ('mook', 'elite', 'summon', 'ally') and not self.form and not self.in_water:
            st['ckey'] = getattr(self, 'ckey', None) or id(self.app)
        if self.armament:
            st['arm_col'] = (35, 25, 40)
        tint = self.tint
        if self.has('freeze'):
            tint = ((170, 220, 255), 0.6)
        elif self.has('petrify'):
            tint = ((150, 140, 130), 0.85)
        elif self.has('burn'):
            tint = ((255, 120, 60), 0.25)
        elif self.has('poison'):
            tint = ((150, 60, 190), 0.25)
        if tint:
            st['tint'] = tint
        if self.form in ('giant',):
            st['scale_mul'] = 1.7
        elif self.form in ('sulong',):
            st['scale_mul'] = 1.3
        return st

    def draw_app(self):
        if self.form == 'gear5':
            a = dict(self.app)
            a['hair_col'] = (250, 250, 250)
            a['top'] = (250, 250, 250)
            a['bottom'] = (250, 250, 250)
            a['hair'] = 'wild'
            a['features'] = tuple(a.get('features', ())) + ('grin',)
            return a
        if self.form == 'sulong':
            a = dict(self.app)
            a['hair_col'] = (250, 250, 250)
            a['fur'] = (250, 250, 250)
            a['eye_col'] = (255, 60, 60)
            return a
        if self.form == 'beast':
            a = dict(self.app)
            a['fur'] = a.get('fur') or (230, 190, 90)
            a['features'] = tuple(a.get('features', ())) + ('mink',)
            return a
        if self.form == 'gear2':
            a = dict(self.app)
            a['skin'] = lerp_col(a['skin'], (255, 120, 140), 0.45)
            return a
        return self.app

    def draw(self, surf, ox, oy):
        x = self.pos.x - ox
        y = self.pos.y - oy
        if x < -200 or y < -250 or x > surf.get_width() + 200 or y > surf.get_height() + 250:
            return
        if self.dead and self.death_t > 1.6:
            return
        if self.form == 'dragon':
            self.draw_dragon(surf, ox, oy)
            return
        app = self.draw_app()
        st = self.anim_state()
        if self.in_water and not self.dead:
            st['z'] = -6
        # аура баффов
        for b in self.buffs:
            if b.get('aura'):
                k = 0.5 + 0.3 * math.sin(self.phase * 4)
                draw_glow(surf, (x, y - 25 * self.scale - self.z), 34 * self.scale, b['aura'], 0.35 * k)
        if self.form == 'asura':
            for k in (-1, 1):
                ghost = dict(app)
                st2 = dict(st)
                st2['tint'] = ((60, 30, 80), 0.6)
                draw_character(surf, x + k * 14 * self.scale, y - 3, ghost, self.facing + k * 0.3, st2)
        if self.room is not None and self.kind == 'player':
            pass
        draw_character(surf, x, y, app, self.facing, st)
        if self.form == 'gear5':
            for i in range(6):
                a = self.phase * 2 + i * 1.05
                pygame.draw.circle(surf, (255, 255, 255), (int(x + math.cos(a) * 16 * self.scale), int(y - 36 * self.scale - self.z + math.sin(a) * 5)), int(5 * self.scale))
        if self.has('freeze'):
            r = pygame.Rect(0, 0, 34 * self.scale, 52 * self.scale)
            r.midbottom = (x, y + 3)
            alpha_rect(surf, r, (180, 230, 255), 110)
            pygame.draw.rect(surf, (230, 250, 255), r, 2)
        if self.has('bind'):
            for i in range(3):
                yy = y - 12 * self.scale - i * 12 * self.scale - self.z
                pygame.draw.ellipse(surf, (240, 240, 240), (x - 15 * self.scale, yy - 3, 30 * self.scale, 7), 2)
        if self.has('stun') or self.has('sleep'):
            for i in range(3):
                a = self.phase * 3 + i * 2.1
                cx = x + math.cos(a) * 14
                cy = y - 58 * self.scale - self.z + math.sin(a) * 4
                if self.has('sleep'):
                    draw_text(surf, "z", (cx, cy), 14, (220, 220, 255), "center", 1)
                else:
                    pygame.draw.polygon(surf, (255, 230, 80), star_points(cx, cy, 5, 2, 5, a))
        if self.has('shock') and random.random() < 0.6:
            for _ in range(2):
                a0 = V(x + random.uniform(-15, 15), y - random.uniform(10, 50) * self.scale - self.z)
                pygame.draw.lines(surf, (200, 230, 255), False, [a0, a0 + V(random.uniform(-10, 10), random.uniform(-10, 10)), a0 + V(random.uniform(-15, 15), random.uniform(-15, 15))], 2)
        if self.shield:
            alpha_circle(surf, (x, y - 25 * self.scale - self.z), int(32 * self.scale), self.shield.get('aura', (180, 230, 255)), 60)
            pygame.draw.circle(surf, self.shield.get('aura', (180, 230, 255)), (int(x), int(y - 25 * self.scale - self.z)), int(32 * self.scale), 2)
        if self.guarding:
            a = self.aim
            c = V(x, y - 22 * self.scale) + from_angle(a, 20 * self.scale)
            pygame.draw.arc(surf, (180, 220, 255), (c.x - 22, c.y - 22, 44, 44), -a - 1.0, -a + 1.0, 3)
        # полоска HP у рядовых
        if self.team == 'enemy' and not self.is_boss and not self.dead and self.hp < self.max_hp:
            w_ = int(36 * max(1, self.scale * 0.8))
            bx = x - w_ / 2
            by = y - 66 * self.scale - self.z
            pygame.draw.rect(surf, (20, 10, 10), (bx - 1, by - 1, w_ + 2, 6))
            pygame.draw.rect(surf, (255, 255, 255), (bx, by, w_ * clamp(self.ghost_hp / self.max_hp, 0, 1), 4))
            pygame.draw.rect(surf, (220, 50, 50) if not self.elite else (240, 150, 40), (bx, by, w_ * clamp(self.hp / self.max_hp, 0, 1), 4))
        if self.team == 'ally' and not self.dead and self.kind != 'summon':
            w_ = 30
            pygame.draw.rect(surf, (10, 20, 10), (x - w_ / 2 - 1, y - 66 * self.scale - self.z - 1, w_ + 2, 5))
            pygame.draw.rect(surf, (80, 220, 100), (x - w_ / 2, y - 66 * self.scale - self.z, w_ * clamp(self.hp / self.max_hp, 0, 1), 3))
        if self.speech and self.speech_t > 0:
            self.draw_speech(surf, x, y - 80 * self.scale - self.z)

    def draw_speech(self, surf, x, y):
        f = get_font(15)
        lines = wrap_text(f, self.speech, 260)
        w_ = max(f.size(l)[0] for l in lines) + 16
        h_ = len(lines) * 18 + 10
        r = pygame.Rect(0, 0, w_, h_)
        r.midbottom = (x, y)
        pygame.draw.rect(surf, (20, 14, 18), r.inflate(4, 4), border_radius=10)
        pygame.draw.rect(surf, (255, 255, 250), r, border_radius=9)
        pygame.draw.polygon(surf, (255, 255, 250), [(x - 6, r.bottom - 1), (x + 6, r.bottom - 1), (x, r.bottom + 8)])
        for i, l in enumerate(lines):
            draw_text(surf, l, (r.x + 8, r.y + 5 + i * 18), 15, (20, 20, 30), outline=0)

    def draw_dragon(self, surf, ox, oy):
        col = (90, 150, 240) if not self.tint else self.tint[0]
        if self.boss_id == 'loki' or (self.tint and self.tint[0] == (150, 120, 255)):
            col = (130, 100, 230)
        pts = [self.pos] + self.hist
        sc = self.scale * (2.0 if self.kind == 'player' else 1.3)
        back = from_angle(self.facing + math.pi, 16 * sc)
        while len(pts) < 14:
            last = pts[-1]
            wig = from_angle(self.facing + math.pi / 2, math.sin(len(pts) * 0.8 + self.phase) * 8 * sc)
            pts.append(last + back + wig * 0.3)
        n = len(pts)
        for i in range(n - 1, -1, -1):
            p = pts[i]
            t = i / max(1, n - 1)
            r = (22 - 12 * t) * sc
            yy = p.y - oy - 60 * sc - math.sin(self.phase * 2 + i * 0.5) * 10
            ocircle(surf, col if i % 2 else mul_col(col, 0.85), (p.x - ox, yy), r, 3)
            if i % 3 == 0:
                pygame.draw.circle(surf, (240, 240, 250), (int(p.x - ox), int(yy - r * 0.6)), max(2, int(r * 0.25)))
        hx, hy = self.pos.x - ox, self.pos.y - oy - 60 * sc
        d = from_angle(self.aim)
        hp_ = V(hx, hy) + d * 18 * sc
        ocircle(surf, col, hp_, 20 * sc, 3)
        snout = hp_ + d * 20 * sc
        ocircle(surf, mul_col(col, 1.1), snout, 12 * sc, 2)
        for k in (-1, 1):
            hb = hp_ + d.rotate(90 * k) * 12 * sc
            pygame.draw.line(surf, (240, 220, 160), hb, hb + d * -14 * sc + d.rotate(90 * k) * 14 * sc, max(2, int(4 * sc)))
            eye = hp_ + d * 6 * sc + d.rotate(90 * k) * 8 * sc
            pygame.draw.circle(surf, (255, 230, 80), (int(eye.x), int(eye.y)), max(2, int(3 * sc)))
        sh = shadow_surf(80 * sc, 24 * sc, 70)
        surf.blit(sh, (self.pos.x - ox - sh.get_width() / 2, self.pos.y - oy - sh.get_height() / 2))
        if self.team == 'enemy' and not self.is_boss and self.hp < self.max_hp:
            pygame.draw.rect(surf, (220, 50, 50), (hx - 20, hy - 40 * sc, 40 * self.hp / self.max_hp, 4))

    # --------------- статусы ---------------
    def add_status(self, name, dur, power=0.0, src=None):
        if self.dead:
            return
        if self.is_boss and name in CC_STATUSES:
            dur *= 0.35
            if name in ('petrify', 'sleep', 'freeze'):
                dur = min(dur, 0.9)
        elif self.elite and name in CC_STATUSES:
            dur *= 0.6
        if self.team == 'player' and name in CC_STATUSES:
            dur *= 0.6
        if name == 'burn' and self.logia in ('fire', 'magma'):
            return
        if name == 'freeze' and self.logia in ('ice', 'snow'):
            return
        if name == 'shock' and (self.logia == 'thunder' or self.immune == 'thunder'):
            return
        if name == 'poison' and self.logia in ('gas',):
            return
        cur = self.statuses.get(name)
        if cur and cur[0] > dur:
            return
        self.statuses[name] = [dur, power, src]

    def update_statuses(self, dt):
        dead = []
        for name, st in self.statuses.items():
            st[0] -= dt
            if name in ('burn', 'bleed', 'poison'):
                tickdmg = st[1] * dt
                if tickdmg > 0 and not self.dead:
                    self.hp -= tickdmg
                    if random.random() < dt * 6:
                        c = (255, 140, 40) if name == 'burn' else ((200, 30, 30) if name == 'bleed' else (150, 60, 190))
                        self.scene.particles.add(self.pos.x + random.uniform(-10, 10), self.pos.y - random.uniform(10, 40), random.uniform(-20, 20), -60,
                                                 0.6, 5, c, 'fire' if name == 'burn' else 'glow')
                    if self.hp <= 0:
                        self.die(st[2])
            if st[0] <= 0:
                dead.append(name)
        for n in dead:
            del self.statuses[n]

    # --------------- урон ---------------
    def take_hit(self, hit):
        if self.dead or self.remove:
            return 0
        if self.invuln > 0:
            if self.kind == 'player' and self.perfect_dodge <= 0 and hit.src is not None:
                self.scene.on_perfect_dodge(self)
                self.perfect_dodge = 0.6
            return 0
        src = hit.src
        # уклонение боссов / предвидение
        if self.dodge > 0 and self.can_act() and self.action is None and random.random() < self.dodge and not hit.ult:
            self.dodge_jump(src)
            return 0
        if self.kind == 'player' and self.scene.observation_active(self):
            if self.scene.observation_dodge(self, hit):
                return 0
        # блок / парирование
        if self.guarding and src is not None:
            ang = angle_to(self.pos, src.pos)
            if abs(ang_diff(self.aim, ang)) < 1.3:
                if self.parry_window > 0:
                    self.scene.on_parry(self, src)
                    return 0
                if not hit.ult:
                    hit.dmg *= 0.3
                    hit.knock *= 0.3
                    hit.launch = 0
                    hit.stun = 0
                    hit.status = None
                    self.scene.audio_play('block', 0.6)
                    self.scene.particles.burst(self.pos.x + math.cos(ang) * 16, self.pos.y - 25 + math.sin(ang) * 10, 8, (200, 230, 255), 'spark', 260, 0.25)
                    self.guard_t += 0.2
        # щит
        if self.shield:
            if self.shield.get('reflect') and src is not None and not hit.ult:
                self.scene.particles.burst(self.pos.x, self.pos.y - 25, 10, self.shield.get('aura', (180, 230, 255)), 'spark', 300, 0.3)
                hit.dmg *= (1 - self.shield['absorb'])
                if src is not self and not src.dead and dist(src.pos, self.pos) < 200:
                    src.take_hit(Hit(self.power() * 0.6, 'barrier', from_angle(angle_to(self.pos, src.pos), 300), src=self))
            else:
                hit.dmg *= (1 - self.shield['absorb'])
                hit.knock *= 0.2
                hit.stun *= 0.2
        # иммунитеты
        if self.immune == 'sword' and (hit.el == 'sword' or hit.sword) and not hit.haki:
            self.scene.float_text(self.pos, "Бара Бара!", (255, 220, 120))
            self.scene.particles.burst(self.pos.x, self.pos.y - 25, 6, (255, 200, 160), 'debris', 200, 0.5, grav=600, z=20, vz=150)
            return 0
        if self.immune == 'thunder' and hit.el in ('thunder', 'electro'):
            self.scene.float_text(self.pos, "Резина!", (255, 220, 120))
            return 0
        mult = 1.0
        # логия
        if self.logia and not self.has('nullified') and not self.in_water and not self.has('wet'):
            counters = LOGIA_COUNTER.get(self.logia, ())
            haki = hit.haki or hit.seastone or (src is not None and src.uses_haki())
            if hit.el in counters or (src is not None and src.has('wet') and 'water' in counters):
                mult *= 1.25
            elif not haki:
                mult *= 0.25
                self.logia_splash()
                if src is not None and src.kind == 'player':
                    self.scene.hint_logia()
        if hit.el == 'water' and self.fruit_user and not self.fishman:
            mult *= 1.15
        if hit.seastone and self.fruit_user:
            self.add_status('weaken', 3.0)
            if self.logia:
                self.add_status('nullified', 2.0)
        # защита
        dmg = hit.dmg * mult * self.dmg_taken_mult
        if not hit.ignore_def:
            lvl = src.level if src is not None else self.level
            red = self.defn / (self.defn + 50 + 8 * lvl)
            dmg *= (1 - red) * (1 - self.armor if not (hit.ryou or (src is not None and src.armament and hit.haki)) else 1 - self.armor * 0.3)
        dmg *= 1.0 / self.buff_mult('defn')
        if self.armament:
            dmg *= self.arm_def()
        if self.blunt_res and hit.el in ('phys', 'rubber') and not hit.haki and not (src is not None and src.uses_haki()):
            dmg *= 1 - self.blunt_res
        if self.has('freeze') or self.has('petrify'):
            if hit.heavy or hit.dmg > self.max_hp * 0.05:
                dmg *= 1.6
                self.statuses.pop('freeze', None)
                self.statuses.pop('petrify', None)
                self.scene.particles.burst(self.pos.x, self.pos.y - 25, 18, (200, 240, 255), 'shard', 350, 0.6, grav=500, z=20, vz=200)
        if hit.knockout and not self.is_boss and not self.elite and src is not None and self.level <= src.level + 2 and self.team == 'enemy':
            self.knocked_out = True
            self.scene.float_text(self.pos, "Без сознания!", (255, 80, 80), 18)
            self.hp = 0
            self.die(src)
            return self.max_hp
        dmg = max(1.0, dmg)
        self.hp -= dmg
        self.hitflash = 1.0
        # отбрасывание
        k = V(hit.knock)
        if self.no_knock or self.is_boss:
            k *= 0.25 if self.is_boss else 0.0
        if self.has('bind'):
            k *= 0.2
        self.knock_v += k
        if hit.launch > 0 and not self.is_boss and not self.no_knock:
            self.vz = max(self.vz, hit.launch)
            self.z = max(self.z, 1)
        elif hit.launch > 0 and self.is_boss:
            self.vz = max(self.vz, hit.launch * 0.2)
        st = hit.stun if not self.is_boss else hit.stun * 0.25
        if self.elite and not self.is_boss:
            st *= 0.5
        if self.kind == 'player':
            st *= 0.6
        if st > 0 and not self.has('bind'):
            self.stagger = max(self.stagger, st)
            if self.action is not None and (st > 0.3 or not self.elite):
                if not getattr(self.action, 'armor', False):
                    self.action.cancel()
                    self.action = None
        if hit.status:
            name, dur, chance = hit.status
            if random.random() < chance:
                self.add_status(name, dur, hit.dmg * 0.12 if name in ('burn', 'bleed', 'poison') else 0, src)
        if hit.nullify:
            self.add_status('nullified', 4.0)
        if hit.drain_life and src is not None:
            src.hp = min(src.max_hp, src.hp + dmg * 0.3)
        if self.has('sleep'):
            self.statuses.pop('sleep', None)
        self.scene.on_damage(self, dmg, hit)
        if self.hp <= 0:
            if self.revive:
                self.revive = False
                self.hp = self.max_hp * 0.35
                self.invuln = 1.5
                self.scene.float_text(self.pos, "Воля не сломлена!", (255, 220, 80), 24)
                self.scene.flash((255, 240, 180), 0.3)
            else:
                self.die(src)
        return dmg

    def arm_def(self):
        return 0.85

    def logia_splash(self):
        e = {'sand': 'sand', 'fire': 'fire', 'ice': 'ice', 'magma': 'magma', 'light': 'light', 'thunder': 'thunder', 'smoke': 'smoke',
             'gas': 'gas', 'snow': 'snow', 'dark_special': 'dark'}.get(self.logia, 'none')
        ed = el(e)
        kind = ed['part'] if ed['part'] in ('fire', 'glow', 'smoke', 'dust', 'shard', 'elec', 'dark') else 'glow'
        self.scene.particles.burst(self.pos.x, self.pos.y - 25 * self.scale, 14, ed['c1'], kind, 220, 0.6, size=6)

    def dodge_jump(self, src):
        a = angle_to(src.pos, self.pos) if src is not None else random.uniform(0, 6.28)
        a += random.choice((-1, 1)) * 1.3
        d = from_angle(a, 110)
        np_ = self.pos + d
        if not self.scene.is_blocked(np_.x, np_.y, self.radius):
            self.scene.effects.append(AfterImageFX(self, 0.35, (200, 200, 255)))
            self.pos = np_
        self.scene.float_text(self.pos, "Уклон!" if not self.fs else "Предвидение!", (200, 220, 255), 16)
        self.invuln = 0.15

    def die(self, killer=None):
        if self.dead:
            return
        self.dead = True
        self.hp = 0
        self.death_t = 0
        self.action = None
        self.statuses = {}
        if self.kind not in ('player',):
            self.vz = max(self.vz, 260)
            self.z = max(self.z, 1)
        self.scene.on_kill(self, killer)

    # --------------- обновление ---------------
    def update(self, dt):
        self.phase += dt * (3 + self.walk * 7)
        self.pose_t += dt
        self.hitflash = max(0, self.hitflash - dt * 6)
        self.invuln = max(0, self.invuln - dt)
        self.stagger = max(0, self.stagger - dt)
        self.attack_cd = max(0, self.attack_cd - dt)
        self.combo_t = max(0, self.combo_t - dt)
        self.parry_window = max(0, self.parry_window - dt)
        self.perfect_dodge = max(0, self.perfect_dodge - dt)
        self.speech_t = max(0, self.speech_t - dt)
        self.ghost_hp += (self.hp - self.ghost_hp) * min(1, dt * 2.5) if self.ghost_hp > self.hp else (self.hp - self.ghost_hp)
        for k in list(self.cooldowns):
            self.cooldowns[k] -= dt
            if self.cooldowns[k] <= 0:
                del self.cooldowns[k]
        if self.life_t is not None:
            self.life_t -= dt
            if self.life_t <= 0 and not self.dead:
                self.dead = True
                self.remove = True
                self.scene.particles.burst(self.pos.x, self.pos.y - 20, 16, (120, 100, 160), 'smoke', 120, 0.8, size=14)
        if self.dead:
            self.death_t += dt
            self._physics(dt, dead=True)
            if self.death_t > 2.0 and self.kind not in ('player',):
                self.remove = True
            return
        self.update_statuses(dt)
        nb = []
        for b in self.buffs:
            b['t'] -= dt
            if b.get('regen'):
                self.hp = min(self.max_hp, self.hp + self.max_hp * b['regen'] * dt)
            if b['t'] > 0:
                nb.append(b)
            elif b.get('form') and self.form == b.get('form'):
                self.form = None
                self.tint = None
        self.buffs = nb
        if self.form:
            self.form_particles(dt)
        if self.shield:
            self.shield['t'] -= dt
            if self.shield['t'] <= 0:
                self.shield = None
        if self.action is not None:
            self.action.update(dt)
            if self.action is not None and self.action.done:
                self.action = None
        self._physics(dt)
        if self.form == 'dragon':
            if not self.hist or dist(self.hist[0], self.pos) > 16 * self.scale * (2.0 if self.kind == 'player' else 1.3):
                self.hist.insert(0, V(self.pos))
                if len(self.hist) > 14:
                    self.hist.pop()

    def form_particles(self, dt):
        pr = self.scene.particles
        f = self.form
        r = random.random
        x, y = self.pos.x, self.pos.y - 25 * self.scale - self.z
        if f in ('flame',) and r() < dt * 30:
            pr.add(x + random.uniform(-14, 14), y + random.uniform(-15, 20), random.uniform(-20, 20), -100, 0.6, 9, (255, 140, 40), 'fire')
        elif f == 'gear2' and r() < dt * 14:
            pr.add(x + random.uniform(-10, 10), y - 10, random.uniform(-10, 10), -50, 0.9, 10, (240, 230, 240), 'smoke', grow=14)
        elif f == 'gear5' and r() < dt * 10:
            pr.add(x + random.uniform(-20, 20), y + random.uniform(-25, 25), 0, -20, 0.7, 4, (255, 255, 255), 'glow')
        elif f == 'ice' and r() < dt * 16:
            pr.add(x + random.uniform(-14, 14), y + random.uniform(-15, 20), 0, 30, 0.8, 4, (190, 230, 255), 'shard')
        elif f == 'magma' and r() < dt * 20:
            pr.add(x + random.uniform(-14, 14), y + random.uniform(-15, 20), 0, 50, 0.6, 7, (255, 70, 20), 'fire')
        elif f == 'light' and r() < dt * 20:
            pr.add(x + random.uniform(-16, 16), y + random.uniform(-20, 20), 0, -30, 0.5, 6, (255, 240, 120), 'glow')
        elif f == 'thunder' and r() < dt * 15:
            pr.add(x + random.uniform(-16, 16), y + random.uniform(-20, 20), 0, 0, 0.2, 7, (160, 210, 255), 'elec')
        elif f in ('dark', 'shadow') and r() < dt * 18:
            pr.add(x + random.uniform(-16, 16), y + random.uniform(-15, 25), 0, -20, 0.9, 12, (50, 20, 70), 'dark')
        elif f == 'sand' and r() < dt * 18:
            a = random.uniform(0, 6.28)
            pr.add(x + math.cos(a) * 20, y + math.sin(a) * 10, -math.sin(a) * 100, math.cos(a) * 50, 0.6, 8, (220, 190, 120), 'dust')
        elif f in ('phoenix', 'wolf') and r() < dt * 20:
            pr.add(x + random.uniform(-18, 18), y + random.uniform(-15, 20), 0, -60, 0.6, 8, (80, 180, 255), 'fire')
        elif f == 'fire_legs' and r() < dt * 20:
            pr.add(self.pos.x + random.uniform(-8, 8), self.pos.y - 8, 0, -40, 0.4, 6, (255, 120, 40), 'fire')
        elif f == 'sulong' and r() < dt * 12:
            pr.add(x + random.uniform(-16, 16), y + random.uniform(-20, 20), 0, 0, 0.3, 6, (255, 255, 200), 'elec')
        elif f == 'asura' and r() < dt * 14:
            pr.add(x + random.uniform(-22, 22), y + random.uniform(-15, 25), 0, -30, 0.9, 14, (40, 20, 50), 'dark')
        elif f == 'quake' and r() < dt * 3:
            self.scene.effects.append(RingFX(V(self.pos.x, self.pos.y - 20), 10, 50, 0.4, (220, 230, 255), 2))
        elif f in ('string', 'room', 'love', 'paw', 'mochi', 'homies', 'gravity', 'barrier', 'poison', 'gas', 'ghost', 'petal', 'clown', 'blade', 'bomb', 'wax', 'giant', 'beast') and r() < dt * 10:
            pr.add(x + random.uniform(-16, 16), y + random.uniform(-15, 25), 0, -30, 0.7, 6, self.tint[0] if self.tint else (255, 255, 255), 'glow')
        spread = getattr(self, 'spread_terrain', None)
        if spread and r() < dt * 8:
            self.scene.terrain_effect(self.pos, 40, spread)

    def _physics(self, dt, dead=False):
        sc = self.scene
        # гравитация
        if self.z > 0 or self.vz > 0:
            if self.form != 'dragon':
                self.vz -= 1500 * dt
                self.z += self.vz * dt
                if self.z <= 0:
                    self.z = 0
                    if self.vz < -500 and not dead:
                        sc.particles.burst(self.pos.x, self.pos.y, 8, (200, 190, 170), 'dust', 120, 0.5, size=10)
                        self.stagger = max(self.stagger, 0.25)
                    if self.vz < -300:
                        self.vz = -self.vz * 0.25
                        if self.vz < 80:
                            self.vz = 0
                    else:
                        self.vz = 0
        elif self.form == 'dragon':
            self.z = 40
        move = self.vel * dt + self.knock_v * dt
        self.knock_v *= 0.0005 ** dt if not dead else 0.02 ** dt
        if self.knock_v.length_squared() < 100:
            self.knock_v = V(0, 0)
        if move.length_squared() > 0:
            self._move(move)
        # вода
        if self.form == 'dragon' or self.z > 20:
            self.in_water = False
            return
        w_ = sc.is_water(self.pos.x, self.pos.y)
        self.in_water = w_
        if w_ and not dead:
            if self.fruit_user and not self.fishman:
                self.drown_t += dt
                self.hp -= self.max_hp * 0.12 * dt
                if random.random() < dt * 10:
                    sc.particles.add(self.pos.x + random.uniform(-10, 10), self.pos.y, 0, -40, 0.6, 4, (200, 230, 255), 'bubble')
                if self.drown_t > 1.4:
                    self.pos = V(self.last_safe)
                    self.drown_t = 0
                    self.knock_v = V(0, 0)
                    sc.float_text(self.pos, "Фруктовик тонет!", (120, 180, 255), 16)
                if self.hp <= 0:
                    self.die(None)
            elif random.random() < dt * 3:
                sc.particles.add(self.pos.x, self.pos.y, 0, 0, 0.8, 14, (220, 240, 255), 'ring')
        else:
            self.drown_t = 0
            if not sc.is_water(self.pos.x, self.pos.y + 6):
                self.last_safe = V(self.pos)

    def _move(self, move):
        sc = self.scene
        r = self.radius * 0.8
        nx = self.pos.x + move.x
        hit_struct = None
        if not sc.is_blocked(nx, self.pos.y, r, self):
            self.pos.x = nx
        else:
            hit_struct = sc.struct_at(nx, self.pos.y, r)
        ny = self.pos.y + move.y
        if not sc.is_blocked(self.pos.x, ny, r, self):
            self.pos.y = ny
        else:
            hit_struct = hit_struct or sc.struct_at(self.pos.x, ny, r)
        if hit_struct is not None:
            spd = self.knock_v.length()
            if spd > 420:
                sc.wall_slam(self, hit_struct, spd)
                self.knock_v *= -0.25
        sc.clamp_pos(self)

# ==================================================================
#  ИСПОЛНЕНИЕ ПРИЁМОВ
# ==================================================================
class FallFX(Effect):
    """Объект, падающий с неба (метеор, кулак, молния, солнце)."""
    def __init__(self, pos, dur, kind='meteor', size=30, col=(255, 140, 40)):
        super().__init__(dur)
        self.pos = V(pos); self.kind = kind; self.size = size; self.col = col
        self.ang = random.uniform(-0.6, -0.3)
    def draw(self, surf, ox, oy):
        k = ease_in(self.k)
        hgt = (1 - k) * 700
        x = self.pos.x - ox + math.sin(self.ang) * hgt * 0.6
        y = self.pos.y - oy - hgt
        s = self.size
        if self.kind in ('meteor', 'sun', 'light_drop'):
            for i in range(6):
                tx = x - math.sin(self.ang) * i * s * 0.5
                ty = y - i * s * 0.7
                draw_glow(surf, (tx, ty), s * (1.4 - i * 0.18), self.col, 0.6 - i * 0.08)
            ocircle(surf, mul_col(self.col, 0.6) if self.kind != 'light_drop' else (255, 255, 220), (x, y), s * 0.6, 2)
            draw_glow(surf, (x, y), s * 1.6, self.col, 0.9)
        elif self.kind == 'fist':
            sc = s / 40
            ocircle(surf, self.col, (x, y), 40 * sc, 4)
            for i in range(4):
                ocircle(surf, mul_col(self.col, 0.9), (x - 30 * sc + i * 20 * sc, y - 30 * sc), 14 * sc, 2)
            draw_glow(surf, (x, y), s * 1.2, (255, 255, 255), 0.4)
        elif self.kind == 'rock':
            pts = star_points(x, y, s, s * 0.8, 7, self.t * 3)
            opoly(surf, (120, 100, 90), [(int(a), int(b)) for a, b in pts], 4)
            for i in range(4):
                draw_glow(surf, (x - math.sin(self.ang) * i * s * 0.4, y - i * s * 0.6), s * (1.2 - i * 0.2), (255, 120, 40), 0.6)
        sh = shadow_surf(s * 2 * (0.4 + 0.6 * k), s * 0.7 * (0.4 + 0.6 * k), int(60 + 80 * k))
        surf.blit(sh, (self.pos.x - ox - sh.get_width() / 2, self.pos.y - oy - sh.get_height() / 2))

class FistsFX(Effect):
    """Шквал кулаков (Гатлинг)."""
    def __init__(self, owner, dur, r, col=(240, 200, 160), black=False, kind='fists'):
        super().__init__(dur)
        self.owner = owner; self.r = r; self.col = col; self.black = black; self.kind = kind
    def draw(self, surf, ox, oy):
        o = self.owner
        a = o.aim
        base = V(o.pos.x - ox, o.pos.y - oy - 26 * o.scale - o.z)
        for i in range(9):
            aa = a + random.uniform(-0.45, 0.45)
            L = random.uniform(0.3, 1.0) * self.r
            e = base + from_angle(aa, L)
            if self.kind == 'slashes':
                n = from_angle(aa + 1.57, 18)
                pygame.draw.line(surf, (255, 255, 255), e - n, e + n, 3)
                pygame.draw.line(surf, (160, 200, 255), e - n * 1.3, e + n * 1.3, 1)
            else:
                c = (35, 30, 40) if self.black else self.col
                pygame.draw.line(surf, c, base, e, 5)
                ocircle(surf, c, e, 8, 2)
                for _ in range(2):
                    q = from_angle(random.uniform(0, 6.28), 14)
                    pygame.draw.line(surf, (255, 255, 255), e + q * 0.8, e + q * 1.4, 2)

class SpikeFX(Effect):
    """Шипы/лезвия из земли (песок, лёд, магма, трещины)."""
    layer = 1
    def __init__(self, pos, r, col, life=0.6, kind='spike', ang=0.0):
        super().__init__(life)
        self.pos = V(pos); self.r = r; self.col = col; self.kind = kind; self.ang = ang
        self.sp = [(random.uniform(-r, r), random.uniform(-r * 0.6, r * 0.6), random.uniform(0.5, 1.2)) for _ in range(6)]
    def draw(self, surf, ox, oy):
        k = self.k
        h = math.sin(min(1, k * 3) * math.pi / 2) * (1 - max(0, (k - 0.6) / 0.4))
        x0, y0 = self.pos.x - ox, self.pos.y - oy
        if self.kind == 'crack':
            pts = []
            for i in range(7):
                t = i / 6 - 0.5
                pts.append((x0 + math.cos(self.ang) * t * self.r * 2 + random.uniform(-4, 4), y0 + math.sin(self.ang) * t * self.r * 2 + random.uniform(-4, 4)))
            pygame.draw.lines(surf, (40, 30, 30), False, pts, 5)
            pygame.draw.lines(surf, self.col, False, pts, 2)
            for i in range(3):
                draw_glow(surf, pts[i * 3], 20 * h + 2, (200, 220, 255), 0.6)
            return
        if self.kind == 'magma_head':
            sz = self.r * h
            if sz > 3:
                ocircle(surf, (150, 30, 10), (x0, y0 - sz), sz * 0.9, 3)
                for kx in (-1, 1):
                    pygame.draw.polygon(surf, (120, 20, 10), [(x0 + kx * sz * 0.5, y0 - sz * 1.6), (x0 + kx * sz * 0.9, y0 - sz * 2.2), (x0 + kx * sz * 0.9, y0 - sz * 1.4)])
                draw_glow(surf, (x0, y0 - sz), sz * 1.6, (255, 90, 20), 0.9)
                pygame.draw.circle(surf, (255, 230, 120), (int(x0 - sz * 0.35), int(y0 - sz * 1.2)), max(2, int(sz * 0.12)))
                pygame.draw.circle(surf, (255, 230, 120), (int(x0 + sz * 0.35), int(y0 - sz * 1.2)), max(2, int(sz * 0.12)))
            return
        if self.kind == 'tsunami':
            w_ = self.r * 1.8
            hh = self.r * 1.5 * h
            if hh > 4:
                pa = self.ang + math.pi / 2
                d = V(math.cos(self.ang), math.sin(self.ang))
                n = V(math.cos(pa), math.sin(pa))
                base = V(x0, y0)
                pts_b, pts_t = [], []
                for i in range(13):
                    t = i / 12 - 0.5
                    bend = (1 - (t * 2) ** 2) * 18
                    pb = base + n * (t * w_) + d * bend
                    pts_b.append((pb.x, pb.y))
                    thick = self.r * 0.9 * h * (0.75 + 0.25 * math.cos(t * 3))
                    pts_t.append((pb.x - d.x * thick, pb.y - d.y * thick - hh * 0.35))
                poly = pts_b + pts_t[::-1]
                alpha_poly(surf, poly, (40, 110, 210), 190)
                alpha_poly(surf, pts_b + [(p[0], p[1] + hh * 0.35) for p in pts_t][::-1], (90, 170, 240), 140)
                pygame.draw.lines(surf, (240, 250, 255), False, pts_t, 5)
                for i in range(0, 13, 2):
                    pygame.draw.circle(surf, (255, 255, 255), (int(pts_t[i][0]), int(pts_t[i][1])), 6)
            return
        if self.kind == 'string_lash':
            for i in range(5):
                a = self.ang + (i - 2) * 0.2
                pygame.draw.line(surf, (255, 255, 255), (x0 - math.cos(a) * self.r, y0 - math.sin(a) * self.r), (x0 + math.cos(a) * self.r, y0 + math.sin(a) * self.r), 2)
            return
        for (dx, dy, s) in self.sp:
            hh = self.r * 1.1 * s * h
            if hh < 2:
                continue
            bx, by = x0 + dx, y0 + dy
            pts = [(bx - 7 * s, by), (bx, by - hh), (bx + 7 * s, by)]
            pygame.draw.polygon(surf, mul_col(self.col, 0.6), pts)
            pygame.draw.polygon(surf, self.col, [(bx - 3 * s, by), (bx, by - hh), (bx + 4 * s, by)])

class MoveRun:
    def __init__(self, f, mid, mv, target, charge=1.0, basic=False):
        self.f = f
        self.mid = mid
        self.mv = mv
        self.target = V(target)
        self.cast = mv.get('cast', 0.1)
        self.steps = sorted(mv['steps'], key=lambda s: s[0])
        if f.kind == 'player' and not basic:
            self.cast = min(self.cast, 0.3)
            self.steps = [(t * 0.5, p) for t, p in self.steps]
        self.t = -self.cast
        first_p = self.steps[0][1] if self.steps else {}
        self.charge_col = el(first_p.get('el', 'phys'))['c1'] if first_p.get('el') not in (None, 'phys', 'none') else (255, 240, 200)
        self.idx = 0
        self.done = False
        self.ult = mv.get('ult', False)
        self.armor = f.is_boss or self.ult or f.kind == 'player' and mv.get('armor', False)
        self.end = (self.steps[-1][0] if self.steps else 0) + mv.get('lock', 0.3)
        self.subs = []
        self.dash = None
        self.charge = charge
        self.basic = basic
        self.cancel_ok = 0.0
        self.tele = None
        first = self.steps[0][1] if self.steps else {}
        self.pose = self._pose_for(first)
        f.set_pose(self.pose if self.cast < 0.05 else ('cast' if self.pose not in ('slash', 'kick') else self.pose), self.cast + 0.25)
        if f.team == 'enemy' and (self.cast >= 0.18 or mv.get('tele')):
            self._telegraph(first)
        if mv.get('sfx') and self.cast > 0.2:
            pass

    def _pose_for(self, p):
        t = p.get('p')
        vis = p.get('vis', '')
        if t == 'melee':
            if vis in ('kick', 'spin_kick'):
                return 'kick'
            if vis in ('slash', 'spin_slash', 'claw', 'whip', 'wing'):
                return 'slash'
            return 'punch'
        if t in ('proj', 'beam', 'barrage', 'grab'):
            return 'punch' if t != 'beam' else 'cast'
        if t == 'dash':
            return 'dash' if self.f.app.get('weapon', 'none').startswith('sword') else 'punch'
        return 'cast'

    def _telegraph(self, p):
        f = self.f
        sc = f.scene
        life = max(0.25, self.cast + (self.steps[0][0] if self.steps else 0) + p.get('delay', 0))
        t = p.get('p')
        a = angle_to(f.pos, self.target)
        if t == 'nova':
            at = p.get('at', 'self')
            pos = f.pos if at == 'self' else (self.target if at == 'cursor' else f.pos + from_angle(a, p['r'] * 0.9))
            fx = TelegraphFX('circle', life, pos=V(pos), r=p['r'])
        elif t in ('proj', 'beam', 'dash'):
            L = p.get('len') or p.get('dist') or p.get('spd', 600) * p.get('life', 0.6) * 0.8
            w_ = p.get('w') or p.get('size', 10) * 2 + 10
            fx = TelegraphFX('line', life, pos=V(f.pos), a=a, len=min(L, 900), w=w_)
        elif t == 'melee':
            fx = TelegraphFX('cone', life, pos=V(f.pos), a=a, r=p['r'] + p.get('off', 20), arc=math.radians(p['arc']))
        elif t in ('rain', 'zone'):
            r = p.get('area', p.get('r', 150))
            pos = f.pos if p.get('at') == 'self' else self.target
            fx = TelegraphFX('circle', life, pos=V(pos), r=r)
        else:
            return
        self.tele = fx
        sc.effects.append(fx)

    def cancel(self):
        self.done = True
        self.subs = []
        if self.tele is not None:
            self.tele.t = self.tele.life

    def sub(self, delay, fn):
        self.subs.append([self.t + delay, fn])

    def update(self, dt):
        f = self.f
        self.t += dt
        if self.t < 0 and not self.basic and self.cast >= 0.12:
            sc = f.scene
            k = 1 - (-self.t / max(0.01, self.cast))
            n = 3 if self.ult else 1
            for _ in range(n):
                if random.random() < 0.8:
                    a = random.uniform(0, 6.28)
                    rr = random.uniform(50, 110) * f.scale
                    px, py = f.pos.x + math.cos(a) * rr, f.pos.y - 26 * f.scale + math.sin(a) * rr * 0.7
                    sc.particles.add(px, py, -math.cos(a) * rr * 3.5, -math.sin(a) * rr * 2.4, 0.28, 4 + 3 * k, self.charge_col, 'glow', drag=1.0)
            if self.ult and random.random() < 0.25:
                sc.effects.append(RingFX(V(f.pos.x, f.pos.y), 120 * f.scale, 10, 0.3, self.charge_col, 3))
            if random.random() < 0.3:
                sc.particles.add(f.pos.x + random.uniform(-14, 14), f.pos.y - 5, 0, -60, 0.4, 8, (210, 200, 180), 'dust')
        if self.t < 0 and f.team == 'enemy' and f.ai and f.ai.target is not None and self.t < -self.cast * 0.4:
            f.aim = angle_to(f.pos, f.ai.target.pos)
            if self.steps and self.steps[0][1].get('at') == 'cursor':
                self.target = V(f.ai.target.pos)
        while self.idx < len(self.steps) and self.steps[self.idx][0] <= self.t:
            p = self.steps[self.idx][1]
            self.idx += 1
            try:
                run_prim(self, p)
            except Exception:
                traceback.print_exc()
        if self.subs:
            due = [s for s in self.subs if s[0] <= self.t]
            if due:
                self.subs = [s for s in self.subs if s[0] > self.t]
                for s in due:
                    try:
                        s[1]()
                    except Exception:
                        traceback.print_exc()
        if self.dash is not None:
            self._dash_update(dt)
        if self.idx >= len(self.steps) and not self.subs and self.dash is None and self.t >= self.end:
            self.done = True

    def _dash_update(self, dt):
        d = self.dash
        f = self.f
        sc = f.scene
        step = d['spd'] * dt
        step = min(step, d['left'])
        d['left'] -= step
        np_ = f.pos + d['dir'] * step
        if sc.is_blocked(np_.x, np_.y, f.radius * 0.8, f):
            st = sc.struct_at(np_.x, np_.y, f.radius)
            if st is not None and d['p'].get('destroy', 1.0) >= 1.0:
                sc.damage_struct(st, d['dmg'] * d['p'].get('destroy', 1.0) * 2, d['el'])
            d['left'] = 0
        else:
            f.pos = np_
        f.invuln = max(f.invuln, 0.06)
        d['ai_t'] -= dt
        if d['ai_t'] <= 0:
            d['ai_t'] = 0.035
            sc.effects.append(AfterImageFX(f, 0.25, el(d['el'])['c1']))
        for t in sc.hostiles_near(f, f.pos, d['w'] + 10):
            if t.uid in d['hit']:
                continue
            d['hit'].add(t.uid)
            kd = d['dir'].rotate(random.choice((-25, 25)))
            hit = make_hit(f, d['p'], self.mv, kdir=kd, mult=self.charge)
            apply_hit(t, hit, f, heavy=True)
        if d['left'] <= 0:
            self.dash = None
            if d['p'].get('explode'):
                nova_at(self, f.pos, d['p'].get('explode'), d['p'], mult=0.8)
            sc.effects.append(SlashFX(f.pos - d['dir'] * 60, math.atan2(d['dir'].y, d['dir'].x) + math.pi / 2, 60, 3.0, 0.25, el(d['el'])['c1'], 10))

def scaled_dmg(f, p, mv, mult=1.0):
    return p.get('dmg', 1.0) * f.power(mv.get('scale', 'atk')) * mult

def make_hit(f, p, mv, kdir=None, mult=1.0, pos=None):
    e = p.get('el', 'phys')
    for b in f.buffs:
        if b.get('el_override') and e in ('phys', 'none'):
            e = b['el_override']
    if getattr(f, 'conq_coat', False) and f.armament and e in ('phys', 'sword', 'none'):
        e = 'haki'
    ed = el(e)
    status = p.get('status') or ed['status']
    crit = random.random() < f.crit
    dmg = scaled_dmg(f, p, mv, mult) * (1.6 if crit else 1.0)
    if f.room is not None and not f.room.dead and dist(f.pos, f.room.pos) < f.room.r and mv.get('scale') == 'fruit':
        dmg *= 1.35
    if p.get('heavy_flag') and f.heavy_bonus:
        dmg *= 1 + f.heavy_bonus
    if e == 'fire' and f.fire_bonus:
        dmg *= 1 + f.fire_bonus
    kn = p.get('knock', 200) * (0.6 + 0.4 * mult)
    knock = (kdir.normalize() if kdir is not None and kdir.length_squared() > 0 else V(0, 0)) * kn
    haki = f.uses_haki() or e in ('haki', 'conq')
    return Hit(dmg, e, knock, p.get('launch', 0) * (0.5 + 0.5 * mult), p.get('stun', 0.25), f, haki=haki,
               ignore_def=p.get('ignore_def', False) or (p.get('ryou') and f.armament), status=status, crit=crit,
               heavy=p.get('dmg', 1) >= 2.4 or mult > 1.5, destroy=p.get('destroy', 1.0),
               ryou=p.get('ryou', False) or getattr(f, 'ryou', False) and f.armament, conq=e == 'conq',
               fruit=mv.get('scale') == 'fruit', seastone=f.weapon_seastone and mv.get('scale', 'atk') == 'atk',
               sword=e == 'sword' or p.get('vis') in ('slash', 'spin_slash'), nullify=p.get('nullify', False),
               ult=mv.get('ult', False), pos=pos, knockout=p.get('knockout', False), drain_life=p.get('drain_life', False))

def apply_hit(t, hit, src, heavy=False):
    sc = t.scene
    dealt = t.take_hit(hit)
    if dealt <= 0:
        return 0
    ed = el(hit.el)
    hx, hy = t.pos.x, t.pos.y - 24 * t.scale - t.z
    big = hit.heavy or hit.crit or heavy or hit.ult
    part = ed['part']
    pk = part if part in ('spark', 'fire', 'shard', 'elec', 'glow', 'water', 'dark', 'smoke', 'dust', 'petal', 'line', 'debris') else 'spark'
    sc.particles.burst(hx, hy, 14 if big else 7, ed['c1'], pk if pk != 'debris' else 'spark', 420 if big else 280, 0.35, size=4 if pk != 'spark' else 3)
    sc.particles.burst(hx, hy, 6 if big else 3, (255, 255, 255), 'spark', 500, 0.2, size=2)
    if hit.haki or hit.conq:
        sc.particles.burst(hx, hy, 4, (230, 30, 60) if hit.conq else (90, 60, 140), 'elec', 200, 0.25, size=10)
        if hit.conq and big:
            for _ in range(3):
                sc.effects.append(BoltFX(V(hx, hy), V(hx, hy) + from_angle(random.uniform(0, 6.28), random.uniform(60, 140)), black=True, life=0.25, width=3))
    if big:
        sc.effects.append(ImpactStarFX(V(hx, hy), 34 if not hit.ult else 70, 0.2, ed['c2']))
    sc.float_dmg(t, dealt, hit.crit, src)
    if src is not None and (src.kind == 'player' or t.kind == 'player'):
        sc.hitstop(0.11 if hit.ult else (0.07 if big else 0.035))
        sc.cam.add_shake(0.35 if hit.ult else (0.22 if big else 0.08))
    elif big:
        sc.cam.add_shake(0.08)
    sc.audio_play('hit_heavy' if big else ('slash' if hit.sword else 'hit'), 0.8 if big else 0.5, pos=t.pos)
    if hit.ult and big:
        sc.impact_frame(3)
    return dealt

def nova_at(run, pos, r, p, mult=1.0, vis=None):
    f = run.f
    sc = f.scene
    mv = run.mv
    e = p.get('el', 'phys')
    ed = el(e)
    vis = vis or p.get('vis', 'explosion')
    pos = V(pos)
    for t in sc.hostiles_near(f, pos, r):
        kd = t.pos - pos
        if kd.length_squared() < 1:
            kd = from_angle(f.aim)
        hit = make_hit(f, p, mv, kdir=kd, mult=mult * run.charge, pos=pos)
        apply_hit(t, hit, f, heavy=p.get('dmg', 1) >= 2.0)
        if p.get('freeze'):
            t.add_status('freeze', p['freeze'])
    dmg = scaled_dmg(f, p, mv, mult)
    sc.damage_area(pos, r * 0.9, dmg * p.get('destroy', 1.0), e)
    tr = ed['terrain']
    if tr:
        sc.terrain_effect(pos, p.get('terrain_r', r * 0.8), tr)
    nova_visual(sc, pos, r, vis, ed, p)

def nova_visual(sc, pos, r, vis, ed, p):
    pr = sc.particles
    c1, c2 = ed['c1'], ed['c2']
    big = r >= 200
    sc.effects.append(RingFX(pos, r * 0.2, r * 1.1, 0.45, c1, 8 if big else 5, layer=0))
    if vis in ('pillar',):
        for i in range(40):
            pr.add(pos.x + random.uniform(-r * 0.4, r * 0.4), pos.y + random.uniform(-r * 0.2, r * 0.2), random.uniform(-30, 30), random.uniform(-500, -200),
                   random.uniform(0.4, 0.9), random.uniform(8, 16), c1, 'fire', drag=0.95)
    elif vis == 'sun':
        for i in range(70):
            a = random.uniform(0, 6.28)
            sp = random.uniform(100, r * 3)
            pr.add(pos.x, pos.y, math.cos(a) * sp, math.sin(a) * sp * 0.7, random.uniform(0.5, 1.2), random.uniform(12, 26), c1, 'fire')
        sc.effects.append(ImpactStarFX(pos, r * 0.7, 0.3, c2, 12))
        sc.flash(c2, 0.35)
    elif vis in ('bolt_pillar',):
        for i in range(3):
            sc.effects.append(BoltFX(pos + V(random.uniform(-40, 40), -650), pos + V(random.uniform(-r * 0.3, r * 0.3), 0), c1, 0.35, 5, 30, 3))
        sc.flash((220, 235, 255), 0.18)
        pr.burst(pos.x, pos.y, 25, c1, 'elec', 300, 0.3, size=12)
    elif vis == 'elec_burst':
        for i in range(10):
            a = i * 0.63
            sc.effects.append(BoltFX(pos, pos + from_angle(a, r), c1, 0.3, 3, 14, 1))
    elif vis == 'frost':
        for i in range(int(14 + r / 15)):
            a = random.uniform(0, 6.28)
            rr = random.uniform(0.2, 1.0) * r
            sc.effects.append(SpikeFX(pos + V(math.cos(a) * rr, math.sin(a) * rr * 0.75), 26, (190, 235, 255), 1.4, 'spike'))
        pr.burst(pos.x, pos.y, 30, (220, 245, 255), 'shard', r * 2.5, 0.8, size=5)
    elif vis in ('quake', 'galaxy', 'club_smash'):
        sc.effects.append(AirCrackFX(pos + V(0, -30), r * (1.0 if vis != 'galaxy' else 1.6), 0.9))
        sc.effects.append(RingFX(pos, r * 0.1, r * 1.5, 0.7, (230, 240, 255), 10, layer=0))
        pr.burst(pos.x, pos.y, 35, (140, 120, 100), 'debris', r * 3, 1.2, size=6, grav=900, z=5, vz=500)
        sc.cam.add_shake(0.6 if vis != 'galaxy' else 1.0)
        if vis == 'galaxy':
            sc.flash((255, 255, 255), 0.4)
        if vis == 'club_smash':
            for i in range(6):
                sc.effects.append(BoltFX(pos, pos + from_angle(random.uniform(0, 6.28), r * 1.2), black=True, life=0.5, width=4))
    elif vis == 'giant_fist':
        sc.effects.append(FallFX(pos, 0.01, 'fist', r * 0.5, c1))
        sc.effects.append(ImpactStarFX(pos, r * 0.6, 0.25, c2, 10))
        pr.burst(pos.x, pos.y, 30, (150, 130, 110), 'debris', r * 2.5, 1.0, size=6, grav=900, z=5, vz=400)
    elif vis == 'pressure':
        sc.effects.append(RingFX(pos, r * 0.1, r * 1.3, 0.9, c1, 14, layer=0))
        sc.effects.append(ImpactStarFX(pos, r * 0.8, 0.35, c2, 14))
        sc.flash(c2, 0.3)
    elif vis == 'shockwave6':
        for i in range(6):
            a = i * math.pi / 3
            sc.effects.append(RingFX(pos + from_angle(a, r * 0.5), 5, r * 0.6, 0.4, (240, 240, 255), 4))
    elif vis in ('haki_ring', 'conq'):
        sc.effects.append(RingFX(pos, 10, r * 1.2, 0.6, (20, 5, 15), 14, layer=0))
        sc.effects.append(RingFX(pos, 10, r * 1.25, 0.6, (230, 30, 50), 4))
        for i in range(10 if vis == 'conq' else 5):
            sc.effects.append(BoltFX(pos + from_angle(random.uniform(0, 6.28), r * 0.2), pos + from_angle(random.uniform(0, 6.28), r * 1.1), black=True, life=0.5, width=4))
        if vis == 'conq':
            sc.flash((120, 0, 20), 0.35)
            sc.cam.add_shake(0.6)
    elif vis == 'barrier_burst':
        sc.effects.append(RingFX(pos, 10, r * 1.2, 0.6, (200, 240, 255), 10))
    elif vis == 'arms':
        for i in range(8):
            a = random.uniform(0, 6.28)
            q = pos + from_angle(a, random.uniform(0, r))
            sc.effects.append(SpikeFX(q, 20, (255, 210, 180), 0.8, 'spike'))
        pr.burst(pos.x, pos.y, 15, (255, 150, 200), 'petal', 200, 0.8, size=6)
    elif vis == 'meteor_big':
        sc.effects.append(ImpactStarFX(pos, r * 0.8, 0.35, (255, 200, 120), 12))
        pr.burst(pos.x, pos.y, 60, (130, 110, 100), 'debris', r * 3, 1.5, size=8, grav=900, z=5, vz=600)
        pr.burst(pos.x, pos.y, 50, (255, 120, 40), 'fire', r * 2, 1.0, size=14)
        sc.flash((255, 220, 160), 0.4)
        sc.cam.add_shake(1.0)
    elif vis == 'soul':
        pr.burst(pos.x, pos.y, 30, (255, 170, 210), 'glow', r * 2, 0.8, size=6)
    elif vis == 'strings':
        for t in sc.fighters:
            if not t.dead and dist(t.pos, pos) < r:
                sc.effects.append(BoltFX(pos + V(0, -30), t.pos + V(0, -25), (255, 255, 255), 0.6, 1, 4, 0))
    else:
        pk = ed['part'] if ed['part'] in ('fire', 'glow', 'smoke', 'dust', 'shard', 'elec', 'dark', 'water', 'petal') else 'spark'
        pr.burst(pos.x, pos.y, int(20 + r / 6), c1, pk, r * 2.2, 0.7, size=8 if pk not in ('spark', 'elec') else 3)
        pr.burst(pos.x, pos.y, int(8 + r / 15), (200, 190, 170), 'dust', r, 0.9, size=16)
        sc.effects.append(ImpactStarFX(pos, min(80, r * 0.45), 0.2, c2))
    sc.cam.add_shake(min(0.6, r / 500))

def run_prim(run, p):
    f = run.f
    sc = f.scene
    t = p.get('p')
    mv = run.mv
    a = f.aim
    d = from_angle(a)
    ed = el(p.get('el', 'phys'))
    snd = mv.get('sfx')
    if t == 'melee':
        off = p.get('off', 20)
        center = f.pos + d * off
        r = p['r'] * (1.0 + 0.25 * (run.charge - 1) if run.charge > 1 else 1.0)
        arc = math.radians(p['arc'])
        if not f.is_boss and f.form != 'dragon':
            f.knock_v += d * (140 if f.kind == 'player' else 90)
        vis = p.get('vis', 'punch')
        f.set_pose(run.pose if vis not in ('kick', 'spin_kick') else 'kick', 0.22)
        hits = 0
        for tg in sc.hostiles_near(f, f.pos, r + off):
            v = tg.pos - f.pos
            if v.length_squared() > 1 and arc < 6.2:
                if abs(ang_diff(a, math.atan2(v.y, v.x))) > arc / 2 + 0.25:
                    continue
            kd = v if v.length_squared() > 1 else d
            hit = make_hit(f, p, mv, kdir=kd * 0.3 + d * 0.7 * kd.length() if kd.length() > 0 else d, mult=run.charge, pos=center)
            if apply_hit(tg, hit, f) > 0:
                hits += 1
        dmg = scaled_dmg(f, p, mv, run.charge)
        sc.damage_area(center + d * r * 0.35, r * 0.55, dmg * p.get('destroy', 1.0) * 0.6, p.get('el', 'phys'))
        melee_visual(sc, f, center, d, a, r, arc, vis, ed, p, hits)
        if p.get('explode'):
            nova_at(run, center + d * r * 0.5, p['explode'], p, 0.6, 'explosion')
        if not snd:
            sc.audio_play('slash' if vis in ('slash', 'spin_slash', 'claw') else 'whoosh', 0.45, pos=f.pos)
    elif t == 'proj':
        n = p.get('n', 1)
        spread = p.get('spread', 0)
        burst = p.get('burst', 0)
        src = f.pos + d * 20 * f.scale
        aim_a = a
        def spawn(i, extra=0.0):
            if n > 1 and not burst:
                aa = aim_a - spread / 2 + spread * i / (n - 1)
            elif burst:
                aa = aim_a + random.uniform(-spread / 2, spread / 2)
            else:
                aa = aim_a
            sc.projectiles.append(Projectile(sc, f, src if not burst else f.pos + from_angle(f.aim, 20), aa + extra, p, mv, run.charge))
        for i in range(n):
            if burst:
                run.sub(i * burst, functools.partial(spawn, i))
            else:
                spawn(i)
        if p.get('triple'):
            spawn(0, 0.18)
            spawn(0, -0.18)
        sc.audio_play(snd or ('slash' if p.get('shape') == 'slash_wave' else 'whoosh'), 0.6, pos=f.pos)
    elif t == 'beam':
        sc.beams.append(Beam(sc, f, p, mv, run.charge))
        sc.audio_play(snd or 'beam', 0.7, pos=f.pos)
    elif t == 'nova':
        at = p.get('at', 'self')
        if at == 'self':
            pos = V(f.pos)
        elif at == 'cursor':
            tg = V(run.target)
            rng_ = p.get('range', 520)
            if dist(tg, f.pos) > rng_:
                tg = f.pos + (tg - f.pos).normalize() * rng_
            pos = tg
        else:
            pos = f.pos + d * p['r'] * 0.9
        if p.get('jump'):
            f.knock_v = V(0, 0)
            np_ = V(pos)
            if not sc.is_blocked(np_.x, np_.y, f.radius):
                f.pos = np_
            f.vz = 0
            f.z = 0
        delay = p.get('delay', 0)
        vis = p.get('vis')
        if delay > 0:
            if vis in ('sun', 'meteor_big', 'giant_fist'):
                kind = {'sun': 'sun', 'meteor_big': 'rock', 'giant_fist': 'fist'}[vis]
                sc.effects.append(FallFX(pos, delay, kind, p['r'] * (0.45 if kind != 'fist' else 0.6), ed['c1']))
            if f.team != 'enemy':
                sc.effects.append(TelegraphFX('circle', delay, col=(255, 230, 120), pos=V(pos), r=p['r']))
            run.sub(delay, lambda: (nova_at(run, pos, p['r'], p), sc.audio_play(snd or 'explosion', 0.8, pos=pos)))
        else:
            nova_at(run, pos, p['r'], p)
            sc.audio_play(snd or 'hit_heavy', 0.8, pos=pos)
        f.set_pose('heavy' if at != 'cursor' else 'cast', 0.35)
    elif t == 'dash':
        f.set_pose('dash', p['dist'] / p['spd'] + 0.2)
        dirv = V(d)
        run.dash = dict(dir=dirv, spd=p['spd'], left=p['dist'], w=p.get('w', 50), hit=set(), p=p, el=p.get('el', 'phys'),
                        dmg=scaled_dmg(f, p, mv), ai_t=0)
        sc.audio_play(snd or 'whoosh', 0.7, pos=f.pos)
    elif t == 'barrage':
        n = p.get('n', 12)
        dur = p.get('dur', 0.8)
        vis = p.get('vis', 'fists')
        black = f.armament or p.get('el') == 'haki'
        col = f.app['skin'] if vis == 'fists' else (255, 255, 255)
        sc.effects.append(FistsFX(f, dur, p['r'], col, black, vis))
        f.set_pose('punch', dur)
        sub_p = dict(p='melee', dmg=p['dmg'], r=p['r'], arc=p.get('arc', 70), knock=60, launch=0, vis='none', el=p.get('el', 'phys'),
                     stun=0.18, off=10, destroy=p.get('destroy', 0.6))
        for i in range(n):
            last = i == n - 1
            pp = dict(sub_p)
            if last:
                pp['knock'] = 600
                pp['dmg'] = p['dmg'] * 3
            run.sub(i * dur / n, functools.partial(_barrage_hit, run, pp, last))
    elif t == 'rain':
        n = p.get('n', 10)
        dur = p.get('dur', 1.2)
        area = p.get('area', 170)
        center = V(run.target) if p.get('at', 'cursor') == 'cursor' else V(f.pos)
        if dist(center, f.pos) > 600:
            center = f.pos + (center - f.pos).normalize() * 600
        vis = p.get('vis', 'meteor')
        for i in range(n):
            ang = random.uniform(0, 6.28)
            rr = math.sqrt(random.random()) * area
            pos = center + V(math.cos(ang) * rr, math.sin(ang) * rr * 0.75)
            tt = i * dur / n
            run.sub(tt, functools.partial(_rain_drop, run, p, pos, vis, ed))
        sc.audio_play(snd or 'explosion', 0.6, pos=center)
    elif t == 'zone':
        at = p.get('at', 'self')
        pos = V(f.pos) if at == 'self' else V(run.target)
        if at != 'self' and dist(pos, f.pos) > 600:
            pos = f.pos + (pos - f.pos).normalize() * 600
        z = Zone(sc, f, pos, p, mv, run.charge)
        sc.zones.append(z)
        if p.get('room'):
            if f.room is not None:
                f.room.dead = True
            f.room = z
        sc.audio_play(snd or 'whoosh', 0.6, pos=pos)
    elif t == 'wave':
        n = p.get('n', 7)
        step = p.get('step', 60)
        start = V(f.pos)
        vis = p.get('vis', 'spike')
        for i in range(n):
            pos = start + d * step * (i + 1)
            run.sub(i * p.get('dt', 0.06), functools.partial(_wave_step, run, p, pos, vis, ed, a))
        sc.audio_play(snd or 'quake', 0.6, pos=f.pos)
    elif t == 'buff':
        b = dict(t=p['dur'], dmg=p.get('dmg', 1.0), defn=p.get('defn', 1.0), spd=p.get('spd', 1.0), regen=p.get('regen', 0.0),
                 aura=p.get('aura'), form=p.get('form'), el_override=p.get('el_override'))
        f.buffs = [x for x in f.buffs if not (x.get('form') and x.get('form') == b['form'])]
        f.buffs.append(b)
        if b['form']:
            f.form = b['form']
            f.tint = (b['aura'], 0.25) if b['aura'] and b['form'] not in ('gear2', 'gear5', 'sulong', 'beast', 'asura', 'dragon', 'giant') else None
            if b['form'] == 'dragon':
                f.hist = []
                f.tint = (b['aura'], 0.0)
        sc.effects.append(RingFX(f.pos, 10, 160, 0.6, b['aura'] or (255, 255, 255), 8))
        sc.particles.burst(f.pos.x, f.pos.y - 25, 30, b['aura'] or (255, 255, 255), 'glow', 300, 0.7, size=6)
        sc.float_text(f.pos, mv['name'], b['aura'] or (255, 255, 255), 20)
        sc.audio_play(snd or 'haki', 0.7, pos=f.pos)
        if b['form'] in ('giant', 'dragon'):
            sc.cam.add_shake(0.5)
    elif t == 'teleport':
        tg = V(run.target)
        rng_ = p.get('range', 350)
        if dist(tg, f.pos) > rng_:
            tg = f.pos + (tg - f.pos).normalize() * rng_
        swapped = False
        if p.get('swap'):
            for e2 in sc.fighters:
                if e2.hostile_to(f) and dist(e2.pos, tg) < 90 and not e2.is_boss:
                    e2.pos, f.pos = V(f.pos), V(e2.pos)
                    swapped = True
                    break
        sc.effects.append(AfterImageFX(f, 0.35, ed['c1']))
        sc.particles.burst(f.pos.x, f.pos.y - 25, 14, ed['c1'], 'glow', 200, 0.3, size=5)
        if not swapped:
            for k in range(8):
                q = f.pos + (tg - f.pos) * (1 - k / 8)
                if not sc.is_blocked(q.x, q.y, f.radius):
                    f.pos = V(q)
                    break
        f.invuln = max(f.invuln, 0.2)
        if p.get('dmg', 0) > 0:
            nova_at(run, f.pos, p.get('r', 90), p, 1.0, 'explosion')
        sc.audio_play(snd or 'whoosh', 0.6, pos=f.pos)
    elif t == 'summon':
        for i in range(p.get('n', 1)):
            pos = f.pos + from_angle(random.uniform(0, 6.28), 60)
            sc.spawn_summon(f, p.get('kind', 'doppel'), pos, p.get('life', 12))
        sc.particles.burst(f.pos.x, f.pos.y - 20, 20, (120, 100, 160), 'smoke', 200, 0.8, size=14)
    elif t == 'grab':
        best = None
        bd = 1e9
        for tg in sc.hostiles_near(f, f.pos, p.get('r', 260)):
            v = tg.pos - f.pos
            if v.length_squared() > 1 and abs(ang_diff(a, math.atan2(v.y, v.x))) > 0.7:
                continue
            if v.length() < bd:
                bd = v.length()
                best = tg
        sc.effects.append(FistFX(f, best.pos if best else f.pos + d * p.get('r', 260), 0.35, f.app['skin'] if p.get('el') in ('rubber', 'nika', 'phys') else ed['c1'], 12, black=f.armament))
        if best is not None:
            best.knock_v = V(0, 0)
            pullto = f.pos + d * 40
            best.add_status('bind', 0.35)
            def do_slam(tg=best):
                if tg.dead:
                    return
                if not tg.is_boss:
                    tg.pos = V(pullto) if not sc.is_blocked(pullto.x, pullto.y, tg.radius) else tg.pos
                hit = make_hit(f, dict(p, launch=600, knock=500, stun=0.6), mv, kdir=d, mult=run.charge)
                apply_hit(tg, hit, f, heavy=True)
                sc.effects.append(RingFX(tg.pos, 10, 90, 0.4, ed['c1'], 6))
                sc.particles.burst(tg.pos.x, tg.pos.y, 16, (170, 150, 120), 'debris', 300, 0.8, size=5, grav=900, z=5, vz=300)
            run.sub(0.25, do_slam)
        sc.audio_play(snd or 'stretch', 0.6, pos=f.pos)
    elif t == 'shield':
        f.shield = dict(t=p['dur'], absorb=p.get('absorb', 0.6), reflect=p.get('reflect', False), aura=p.get('aura', (180, 230, 255)))
        sc.effects.append(RingFX(f.pos, 10, 70, 0.4, p.get('aura', (180, 230, 255)), 6))
        sc.audio_play(snd or 'block', 0.6, pos=f.pos)
    elif t == 'heal':
        amt = f.max_hp * p.get('frac', 0.25)
        f.hp = min(f.max_hp, f.hp + amt)
        sc.particles.burst(f.pos.x, f.pos.y - 25, 30, p.get('aura', (120, 220, 255)), 'fire', 200, 0.9, size=8)
        sc.float_text(f.pos, "+" + fmt_num(amt), (120, 255, 150), 20)

def melee_visual(sc, f, center, d, a, r, arc, vis, ed, p, hits):
    c1 = ed['c1']
    if f.armament and vis in ('punch', 'kick', 'slash'):
        c1 = (60, 40, 80)
    if vis in ('slash', 'spin_slash'):
        thick = 16 if p.get('dmg', 1) < 2 else 26
        col = c1 if p.get('el') not in ('phys', 'sword') else (210, 230, 255)
        sc.effects.append(SlashFX(f.pos + d * 10, a, r * 0.85, min(6.28, arc + 0.4), 0.22, col, thick, flip=random.random() < 0.5))
    elif vis in ('spin', 'spin_kick'):
        sc.effects.append(SlashFX(f.pos, a, r * 0.8, 6.2, 0.3, c1 if p.get('el') != 'phys' else (255, 240, 210), 14))
    elif vis == 'kick':
        sc.effects.append(SlashFX(f.pos + d * 10, a, r * 0.7, 2.2, 0.2, c1 if p.get('el') != 'phys' else (255, 230, 190), 12, flip=random.random() < 0.5))
    elif vis == 'claw':
        for k in (-1, 0, 1):
            sc.effects.append(SlashFX(f.pos + d * 15 + d.rotate(90) * k * 10, a, r * 0.7, 1.4, 0.2, (240, 240, 255), 5))
    elif vis == 'quake':
        sc.effects.append(AirCrackFX(center + d * 40 + V(0, -25), r * 0.8, 0.7))
        sc.effects.append(RingFX(center + d * 40, 10, r, 0.5, (220, 230, 255), 8))
        sc.cam.add_shake(0.4)
        sc.audio_play('quake', 0.8, pos=center)
    elif vis in ('palm', 'water_punch'):
        sc.effects.append(RingFX(center + d * 30, 8, r * 0.9, 0.35, c1, 7))
        if vis == 'water_punch':
            sc.particles.burst(center.x + d.x * 30, center.y + d.y * 30, 18, (90, 160, 255), 'water', 300, 0.6, size=4)
    elif vis == 'whip':
        sc.effects.append(SlashFX(f.pos, a, r * 0.8, min(6.28, arc), 0.3, (255, 255, 255), 30))
        for i in range(8):
            q = f.pos + from_angle(a + random.uniform(-arc / 2, arc / 2), random.uniform(r * 0.4, r))
            sc.effects.append(ImpactStarFX(q, 18, 0.2, (255, 255, 255), 5))
    elif vis == 'wing':
        for k in (-1, 1):
            sc.effects.append(SlashFX(f.pos, a + k * 0.9, r * 0.75, 2.0, 0.3, c1, 22))
    elif vis == 'bite':
        sc.effects.append(SlashFX(center + d * 30, a + 1.57, 30, 2.4, 0.2, (255, 255, 255), 8))
        sc.effects.append(SlashFX(center + d * 30, a - 1.57, 30, 2.4, 0.2, (255, 255, 255), 8))
    elif vis == 'finger':
        sc.particles.burst(center.x + d.x * 30, center.y + d.y * 30, 6, (255, 255, 255), 'spark', 600, 0.2, angle=a, spread=0.4)
    elif vis == 'punch':
        if hits == 0:
            sc.particles.burst(center.x + d.x * r * 0.5, center.y + d.y * r * 0.5 - 20, 4, (255, 255, 255), 'line', 300, 0.15, angle=a, spread=0.5, size=2)
        if p.get('el') not in ('phys', None):
            sc.particles.burst(center.x + d.x * r * 0.4, center.y + d.y * r * 0.4 - 20, 10, c1, el(p.get('el'))['part'] if el(p.get('el'))['part'] in ('fire', 'glow', 'elec', 'water', 'shard', 'smoke') else 'spark', 250, 0.4, size=6)

def _barrage_hit(run, pp, last):
    f = run.f
    if f.dead:
        return
    sc = f.scene
    d = from_angle(f.aim)
    center = f.pos + d * 10
    for tg in sc.hostiles_near(f, f.pos, pp['r'] + 10):
        v = tg.pos - f.pos
        if v.length_squared() > 1 and abs(ang_diff(f.aim, math.atan2(v.y, v.x))) > math.radians(pp['arc']) / 2 + 0.3:
            continue
        hit = make_hit(f, pp, run.mv, kdir=d, mult=1.0)
        apply_hit(tg, hit, f, heavy=last)
    sc.damage_area(center + d * pp['r'] * 0.5, pp['r'] * 0.5, scaled_dmg(f, pp, run.mv) * pp.get('destroy', 0.6), pp.get('el', 'phys'))
    if random.random() < 0.5:
        sc.audio_play('hit', 0.35, pos=f.pos, cooldown=0.04)

def _rain_drop(run, p, pos, vis, ed):
    f = run.f
    sc = f.scene
    kind = {'meteor': 'meteor', 'light_drop': 'light_drop', 'bolt': None}.get(vis, 'meteor')
    delay = 0.35
    if kind:
        sc.effects.append(FallFX(pos, delay, kind, p.get('r', 60) * 0.5, ed['c1']))
    sc.effects.append(TelegraphFX('circle', delay, col=(255, 60, 60) if f.team == 'enemy' else (255, 220, 120), pos=V(pos), r=p.get('r', 60)))
    def hitit():
        if vis == 'bolt':
            sc.effects.append(BoltFX(pos + V(random.uniform(-60, 60), -700), pos, ed['c1'], 0.3, 4, 30, 2))
            sc.flash((200, 220, 255), 0.06)
            sc.audio_play('thunder', 0.5, pos=pos, cooldown=0.1)
        else:
            sc.audio_play('explosion', 0.45, pos=pos, cooldown=0.08)
        nova_at(run, pos, p.get('r', 60), p, 1.0, 'explosion' if vis != 'bolt' else 'bolt_small')
    run.sub(delay, hitit)

def _wave_step(run, p, pos, vis, ed, ang):
    f = run.f
    sc = f.scene
    if sc.is_blocked(pos.x, pos.y, 4) and p.get('destroy', 1.0) < 1.0:
        return
    r = p.get('r', 55)
    if vis in ('spike', 'crack', 'magma_head', 'tsunami', 'string_lash'):
        sc.effects.append(SpikeFX(pos, r, ed['c1'], 0.7 if vis != 'tsunami' else 0.9, vis, ang + (math.pi / 2 if vis in ('crack',) else 0)))
    for tg in sc.hostiles_near(f, pos, r):
        kd = from_angle(ang)
        hit = make_hit(f, dict(p, launch=p.get('launch', 300)), run.mv, kdir=kd, mult=run.charge, pos=pos)
        apply_hit(tg, hit, f, heavy=True)
    sc.damage_area(pos, r, scaled_dmg(f, p, run.mv) * p.get('destroy', 1.0), p.get('el', 'phys'))
    tr = ed['terrain']
    if tr:
        sc.terrain_effect(pos, r * 0.8, tr)
    sc.particles.burst(pos.x, pos.y, 8, ed['c1'], ed['part'] if ed['part'] in ('fire', 'glow', 'dust', 'shard', 'elec', 'water', 'dark', 'smoke') else 'spark', 200, 0.5, size=7)
    sc.cam.add_shake(0.08)

# ------------------------------------------------------------------
#  СНАРЯДЫ, ЛУЧИ, ЗОНЫ
# ------------------------------------------------------------------
class Projectile:
    def __init__(self, sc, owner, pos, angle, p, mv, charge=1.0):
        self.sc = sc
        self.owner = owner
        self.team = owner.team
        self.pos = V(pos)
        self.start = V(pos)
        self.vel = from_angle(angle, p.get('spd', 700))
        self.p = p
        self.mv = mv
        self.size = p.get('size', 10) * (1 + 0.3 * (charge - 1) if charge > 1 else 1)
        self.life = p.get('life', 0.8)
        self.max_life = self.life
        self.pierce = p.get('pierce', 0)
        self.hit = set()
        self.shape = p.get('shape', 'orb')
        self.e = p.get('el', 'phys')
        self.ed = el(self.e)
        self.col = p.get('col') or self.ed['c1']
        self.tick = p.get('tick')
        self.tick_t = 0.0
        self.dead = False
        self.charge = charge
        self.trail = []
        self.rot = 0.0
        self.black = p.get('black') or (owner.armament and self.shape == 'fist')

    def hostile(self, f):
        return self.owner.hostile_to(f) if not self.owner.dead else ((self.team == 'enemy') != (f.team == 'enemy'))

    def update(self, dt):
        self.life -= dt
        self.rot += dt * 10
        hm = self.p.get('homing', 0)
        if hm:
            best = None
            bd = 500
            for f in self.sc.fighters:
                if not f.dead and self.hostile(f):
                    dd = dist(f.pos, self.pos)
                    if dd < bd:
                        bd = dd
                        best = f
            if best is not None:
                want = (best.pos - self.pos)
                if want.length() > 0:
                    sp = self.vel.length()
                    self.vel = (self.vel + want.normalize() * sp * hm * dt).normalize() * sp
        self.pos += self.vel * dt
        self.trail.append(V(self.pos))
        if len(self.trail) > 10:
            self.trail.pop(0)
        self._particles(dt)
        # столкновения с бойцами
        if self.tick:
            self.tick_t -= dt
            if self.tick_t <= 0:
                self.tick_t = self.tick
                for f in self.sc.fighters:
                    if not f.dead and self.hostile(f) and dist(f.pos, self.pos) < self.size + f.radius:
                        self._hit(f)
            if self.p.get('pull'):
                for f in self.sc.fighters:
                    if not f.dead and self.hostile(f) and not f.is_boss:
                        dv = self.pos - f.pos
                        dd = dv.length()
                        if 0 < dd < self.size * 3:
                            f.knock_v += dv.normalize() * self.p['pull'] * dt * 4
        else:
            for f in self.sc.fighters:
                if f.dead or f.uid in self.hit or not self.hostile(f) or f.z > 80:
                    continue
                if dist2(f.pos + V(0, -20 * f.scale), self.pos) < (self.size + f.radius + 6) ** 2:
                    self.hit.add(f.uid)
                    self._hit(f)
                    if self.pierce <= 0:
                        self.explode()
                        return
                    self.pierce -= 1
        st = self.sc.struct_at(self.pos.x, self.pos.y, self.size * 0.6)
        if st is not None:
            dmg = scaled_dmg(self.owner, self.p, self.mv, self.charge) * self.p.get('destroy', 1.0) * 1.5
            self.sc.damage_struct(st, dmg, self.e)
            if self.p.get('destroy', 1.0) < 2.5 and self.pierce < 5:
                self.explode()
                return
        if self.life <= 0:
            self.explode()

    def _hit(self, f):
        kd = self.vel if self.vel.length_squared() > 0 else V(1, 0)
        hit = make_hit(self.owner, self.p, self.mv, kdir=kd, mult=self.charge, pos=self.pos)
        apply_hit(f, hit, self.owner, heavy=self.p.get('dmg', 1) >= 2.4)

    def explode(self):
        if self.dead:
            return
        self.dead = True
        r = self.p.get('explode', 0)
        sc = self.sc
        if r:
            fake = _FakeRun(self.owner, self.mv, self.charge)
            pp = dict(self.p)
            pp['dmg'] = self.p.get('dmg', 1) * 0.7
            nova_at(fake, self.pos, r, pp, 1.0, 'explosion')
            sc.audio_play('explosion', 0.5 if r < 150 else 0.9, pos=self.pos, cooldown=0.06)
        else:
            sc.particles.burst(self.pos.x, self.pos.y, 6, self.col, 'spark', 200, 0.25)

    def _particles(self, dt):
        pr = self.sc.particles
        s = self.shape
        if s in ('fireball', 'comet', 'magma_fist') and random.random() < dt * 60:
            pr.add(self.pos.x + random.uniform(-self.size * 0.5, self.size * 0.5), self.pos.y + random.uniform(-self.size * 0.5, self.size * 0.5),
                   -self.vel.x * 0.1, -self.vel.y * 0.1 - 30, 0.5, self.size * 0.5, self.col, 'fire')
        elif s in ('tornado',) and random.random() < dt * 40:
            a = random.uniform(0, 6.28)
            pr.add(self.pos.x + math.cos(a) * self.size, self.pos.y + math.sin(a) * self.size * 0.5, -math.sin(a) * 200, -80, 0.5, 8, self.col, 'dust')
        elif s in ('bird', 'dragon_head') and random.random() < dt * 40:
            pr.add(self.pos.x + random.uniform(-self.size, self.size), self.pos.y + random.uniform(-self.size * 0.5, self.size * 0.5), 0, -20, 0.5, 7,
                   self.col, 'fire' if self.e in ('fire', 'phoenix', 'poison') else 'glow')
        elif s == 'ghost' and random.random() < dt * 10:
            pr.add(self.pos.x, self.pos.y, 0, -20, 0.6, 6, (240, 230, 255), 'glow')
        elif s in ('smoke_fist',) and random.random() < dt * 30:
            pr.add(self.pos.x, self.pos.y, 0, 0, 0.5, self.size * 0.8, (230, 230, 235), 'smoke', grow=20)
        elif s == 'wave' and random.random() < dt * 40:
            pr.add(self.pos.x + random.uniform(-self.size, self.size), self.pos.y + random.uniform(-self.size * 0.3, self.size * 0.3), 0, -100, 0.6, 4, (200, 230, 255), 'water', z=10, vz=200, grav=500)

    def draw(self, surf, ox, oy):
        x, y = self.pos.x - ox, self.pos.y - oy - 22
        s = self.size
        c = self.col
        ang = math.atan2(self.vel.y, self.vel.x)
        sh = self.shape
        if sh in ('orb', 'light_orb', 'bullet', 'cannonball'):
            if sh == 'bullet':
                tail = V(x, y) - self.vel.normalize() * s * 3
                pygame.draw.line(surf, c, tail, (x, y), max(2, int(s * 0.6)))
                draw_glow(surf, (x, y), s * 1.6, c, 0.8)
            elif sh == 'cannonball':
                ocircle(surf, (40, 40, 45), (x, y), s * 0.8, 2)
                pygame.draw.circle(surf, (120, 120, 130), (int(x - s * 0.25), int(y - s * 0.25)), max(1, int(s * 0.2)))
            else:
                draw_glow(surf, (x, y), s * 2.4, c, 0.9)
                pygame.draw.circle(surf, (255, 255, 255), (int(x), int(y)), max(2, int(s * 0.5)))
        elif sh in ('fist', 'magma_fist', 'smoke_fist', 'comet'):
            col = (35, 30, 40) if self.black else (c if sh != 'fist' else self.owner.app['skin'])
            if self.p.get('white'):
                col = (255, 255, 255)
            if self.p.get('stretch') and not self.owner.dead:
                sp = V(self.owner.pos.x - ox, self.owner.pos.y - oy - 28 * self.owner.scale)
                oline(surf, col, sp, (x, y), max(5, s * 0.4), 2)
            if sh == 'comet':
                for i, tp in enumerate(self.trail):
                    draw_glow(surf, (tp.x - ox, tp.y - oy - 22), s * (0.6 + i * 0.12), (255, 120, 30), 0.5)
            ocircle(surf, col, (x, y), s, 3)
            for i in range(3):
                q = V(x, y) + from_angle(ang + 1.57, (i - 1) * s * 0.5) + from_angle(ang, s * 0.6)
                pygame.draw.circle(surf, mul_col(col, 0.8), (int(q.x), int(q.y)), max(1, int(s * 0.3)))
            if sh in ('magma_fist', 'comet'):
                draw_glow(surf, (x, y), s * 2, c, 0.8)
            if self.black:
                pygame.draw.circle(surf, (130, 100, 180), (int(x - s * 0.3), int(y - s * 0.3)), max(2, int(s * 0.25)))
                if random.random() < 0.3:
                    self.sc.effects.append(BoltFX(self.pos + V(0, -22), self.pos + V(0, -22) + from_angle(random.uniform(0, 6.28), s * 2), black=True, life=0.12, width=2, branches=0))
        elif sh == 'fireball':
            draw_glow(surf, (x, y), s * 2.6, c, 1.0)
            draw_glow(surf, (x, y), s * 1.3, (255, 240, 180), 1.0)
            ocircle(surf, (255, 200, 90), (x, y), s * 0.75, 0)
        elif sh in ('slash_wave', 'wind_blade'):
            pa = ang + math.pi / 2
            n = 9
            pts1, pts2 = [], []
            for i in range(n):
                t = i / (n - 1) - 0.5
                w_ = (1 - abs(t) * 2) * s * 0.45
                bend = -abs(t) * s * 1.2
                p0 = V(x, y) + from_angle(pa, t * s * 2.4) + from_angle(ang, bend)
                pts1.append(p0 + from_angle(ang, w_))
                pts2.append(p0 - from_angle(ang, w_))
            col = c if self.e not in ('phys',) else (220, 235, 255)
            if self.e == 'conq' or self.e == 'haki':
                pygame.draw.polygon(surf, (200, 20, 40), pts1 + pts2[::-1])
                pygame.draw.lines(surf, (20, 5, 10), False, pts1, 3)
            else:
                pygame.draw.polygon(surf, col, pts1 + pts2[::-1])
                pygame.draw.lines(surf, (255, 255, 255), False, pts1, 2)
        elif sh == 'spear':
            tip = V(x, y) + from_angle(ang, s * 2)
            back = V(x, y) - from_angle(ang, s * 2)
            n = from_angle(ang + 1.57, s * 0.5)
            pygame.draw.polygon(surf, c, [tip, back + n, back - n])
            pygame.draw.polygon(surf, (255, 255, 255), [tip, back + n, back - n], 1)
        elif sh == 'bird':
            flap = math.sin(self.rot * 2) * 0.5
            body = V(x, y)
            for k in (-1, 1):
                wing_tip = body + from_angle(ang + k * (2.2 + flap), s * 1.8)
                wing_mid = body + from_angle(ang + k * 1.4, s * 1.1)
                pygame.draw.polygon(surf, c, [body + from_angle(ang, s * 0.4), wing_mid, wing_tip, body - from_angle(ang, s * 0.6)])
            ocircle(surf, add_col(c, 40), body + from_angle(ang, s * 0.7), s * 0.4, 1)
            draw_glow(surf, (x, y), s * 2, c, 0.7)
        elif sh == 'tornado':
            for i in range(5):
                rr = s * (0.4 + i * 0.2)
                yy = y - i * s * 0.35
                pygame.draw.ellipse(surf, mul_col(c, 0.85 + i * 0.03), (x - rr, yy - rr * 0.3, rr * 2, rr * 0.6), 3)
        elif sh == 'rock':
            pts = star_points(x, y, s, s * 0.75, 6, self.rot)
            pygame.draw.polygon(surf, (110, 95, 90), pts)
            pygame.draw.polygon(surf, (40, 30, 30), pts, 2)
        elif sh == 'string':
            tail = V(x, y) - self.vel.normalize() * 40
            pygame.draw.line(surf, (255, 255, 255), tail, (x, y), 2)
        elif sh == 'mochi':
            ocircle(surf, (245, 235, 215), (x, y), s, 2)
            tip = V(x, y) + from_angle(ang, s * 1.8)
            pygame.draw.polygon(surf, (245, 235, 215), [tip, V(x, y) + from_angle(ang + 1.57, s), V(x, y) - from_angle(ang + 1.57, s)])
        elif sh == 'paw':
            ocircle(surf, (255, 190, 210), (x, y), s, 2)
            for k in range(3):
                q = V(x, y) + from_angle(ang + (k - 1) * 0.6, s * 1.1)
                ocircle(surf, (255, 170, 200), q, s * 0.35, 1)
        elif sh == 'bat':
            for k in (-1, 1):
                pygame.draw.polygon(surf, (40, 20, 50), [(x, y), (x + k * s * 1.3, y - s * (0.6 + 0.4 * math.sin(self.rot * 3))), (x + k * s * 0.7, y + s * 0.3)])
            pygame.draw.circle(surf, (255, 60, 60), (int(x), int(y)), 2)
        elif sh == 'ghost':
            ocircle(surf, (245, 240, 255), (x, y), s * 0.8, 2)
            pygame.draw.circle(surf, (40, 30, 50), (int(x - s * 0.25), int(y - s * 0.1)), max(1, int(s * 0.12)))
            pygame.draw.circle(surf, (40, 30, 50), (int(x + s * 0.25), int(y - s * 0.1)), max(1, int(s * 0.12)))
        elif sh == 'heart':
            pts = []
            for i in range(20):
                t = i / 20 * 6.28
                hx = 16 * math.sin(t) ** 3
                hy = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
                pts.append((x + hx * s / 16, y + hy * s / 16))
            pygame.draw.polygon(surf, (255, 90, 170), pts)
            draw_glow(surf, (x, y), s * 2, (255, 90, 170), 0.6)
        elif sh == 'wall':
            n = from_angle(ang + 1.57, s)
            f_ = from_angle(ang, s * 0.2)
            pts = [V(x, y) + n + f_, V(x, y) - n + f_, V(x, y) - n - f_, V(x, y) + n - f_]
            alpha_poly(surf, pts, (190, 235, 255), 150)
            pygame.draw.polygon(surf, (255, 255, 255), pts, 2)
        elif sh == 'dragon_head':
            ocircle(surf, c, (x, y), s, 3)
            tip = V(x, y) + from_angle(ang, s * 1.4)
            ocircle(surf, mul_col(c, 1.1), tip, s * 0.6, 2)
            for k in (-1, 1):
                pygame.draw.circle(surf, (255, 240, 120), (int(x + math.cos(ang + k * 0.7) * s * 0.5), int(y + math.sin(ang + k * 0.7) * s * 0.5)), max(2, int(s * 0.15)))
            draw_glow(surf, (x, y), s * 2, c, 0.6)
        elif sh == 'wave':
            n = from_angle(ang + 1.57, s)
            pts = [V(x, y) + n, V(x, y) - n, V(x, y) - n - from_angle(ang, s * 0.6), V(x, y) + n - from_angle(ang, s * 0.6)]
            alpha_poly(surf, pts, (70, 150, 240), 190)
            pygame.draw.line(surf, (240, 250, 255), pts[0], pts[1], 4)
        else:
            draw_glow(surf, (x, y), s * 2, c, 0.8)

class _FakeRun:
    def __init__(self, f, mv, charge=1.0):
        self.f = f
        self.mv = mv
        self.charge = charge
        self.subs = []
    def sub(self, d, fn):
        fn()

class Beam:
    def __init__(self, sc, owner, p, mv, charge=1.0):
        self.sc = sc
        self.owner = owner
        self.p = p
        self.mv = mv
        self.life = p.get('life', 0.6)
        self.tick = p.get('tick', 0.08)
        self.tick_t = 0
        self.len = p.get('len', 500)
        self.w = p.get('w', 24) * (1 + 0.3 * (charge - 1) if charge > 1 else 1)
        self.a = owner.aim
        self.charge = charge
        self.dead = False
        col = p.get('col') or el(p.get('el', 'light'))['c1']
        self.fx = BeamFX(owner.pos + V(0, -20), self.a, self.len, self.w, self.life, col, owner=owner, follow=p.get('follow', False))
        sc.effects.append(self.fx)
        self.structs_hit = set()

    def update(self, dt):
        self.life -= dt
        if self.life <= 0 or self.owner.dead:
            self.dead = True
            return
        if self.p.get('follow'):
            self.a = self.owner.aim
        self.tick_t -= dt
        if self.tick_t <= 0:
            self.tick_t = self.tick
            a = self.owner.pos
            b = a + from_angle(self.a, self.len)
            for f in self.sc.fighters:
                if f.dead or not self.owner.hostile_to(f):
                    continue
                if point_seg_dist(f.pos, a, b) < self.w / 2 + f.radius:
                    hit = make_hit(self.owner, self.p, self.mv, kdir=from_angle(self.a), mult=self.charge, pos=f.pos)
                    apply_hit(f, hit, self.owner)
            dmg = scaled_dmg(self.owner, self.p, self.mv, self.charge) * self.p.get('destroy', 1.0)
            self.sc.damage_line(a, b, self.w, dmg, self.p.get('el', 'light'))
            ed = el(self.p.get('el', 'light'))
            if ed['terrain'] and random.random() < 0.5:
                q = a + from_angle(self.a, random.uniform(0.2, 1.0) * self.len)
                self.sc.terrain_effect(q, self.w * 0.8, ed['terrain'])

class Zone:
    def __init__(self, sc, owner, pos, p, mv, charge=1.0):
        self.sc = sc
        self.owner = owner
        self.pos = V(pos)
        self.p = p
        self.mv = mv
        self.r0 = p.get('r', 150)
        self.r = self.r0
        self.life = p.get('life', 4.0)
        self.max_life = self.life
        self.tick = p.get('tick', 0.4)
        self.tick_t = 0.0
        self.dead = False
        self.vis = p.get('vis', 'field')
        self.ed = el(p.get('el', 'fire'))
        self.charge = charge
        self.t = 0.0
        self.cage = None
        if self.vis == 'cage':
            self.cage = CageFX(self.pos, self.r0, self.life)
            sc.effects.append(self.cage)
        if self.vis == 'room':
            sc.effects.append(DomeFX(self.pos, self.r0, self.life, (120, 180, 255)))

    def update(self, dt):
        self.life -= dt
        self.t += dt
        if self.life <= 0 or (self.owner.dead and self.vis not in ('lava',)):
            self.dead = True
            return
        if self.p.get('follow'):
            self.pos = V(self.owner.pos)
        if self.p.get('shrink'):
            self.r = self.r0 * (1 - 0.8 * (1 - self.life / self.max_life))
        pull = self.p.get('pull', 0)
        for f in self.sc.fighters:
            if f.dead or not self.owner.hostile_to(f):
                continue
            dv = self.pos - f.pos
            dd = dv.length()
            if dd > self.r + f.radius:
                if self.p.get('shrink') and dd < self.r + 60:
                    f.knock_v += dv.normalize() * 300 * dt * 10
                continue
            if pull and dd > 10 and not f.is_boss:
                f.knock_v += dv.normalize() * pull * dt * 3
            elif pull and f.is_boss and dd > 10:
                f.knock_v += dv.normalize() * pull * dt * 0.8
            if self.p.get('slow'):
                f.add_status('slow', 0.4)
        self.tick_t -= dt
        if self.tick_t <= 0 and self.p.get('dmg', 0) > 0:
            self.tick_t = self.tick
            for f in self.sc.fighters:
                if f.dead or not self.owner.hostile_to(f):
                    continue
                if dist(f.pos, self.pos) < self.r + f.radius:
                    kd = f.pos - self.pos
                    hit = make_hit(self.owner, dict(self.p, knock=self.p.get('knock', 40), stun=0.1), self.mv, kdir=kd, mult=self.charge, pos=f.pos)
                    dealt = apply_hit(f, hit, self.owner)
                    if self.p.get('drain') and dealt:
                        self.owner.hp = min(self.owner.max_hp, self.owner.hp + dealt * 0.2)
            if self.p.get('destroy', 0) > 0:
                self.sc.damage_area(self.pos, self.r, scaled_dmg(self.owner, self.p, self.mv) * self.p.get('destroy', 1.0), self.p.get('el', 'fire'))
            tr = self.ed['terrain']
            if tr and self.vis not in ('room',):
                self.sc.terrain_effect(self.pos + from_angle(random.uniform(0, 6.28), random.uniform(0, self.r)), 50, tr)
        self._particles(dt)

    def _particles(self, dt):
        pr = self.sc.particles
        v = self.vis
        c = self.ed['c1']
        if v in ('ring_wall',):
            for _ in range(int(dt * 80)):
                a = random.uniform(0, 6.28)
                pr.add(self.pos.x + math.cos(a) * self.r, self.pos.y + math.sin(a) * self.r * 0.75, 0, -120, 0.6, 12, c, 'fire')
        elif v in ('lava',):
            if random.random() < dt * 20:
                a = random.uniform(0, 6.28)
                rr = random.uniform(0, self.r)
                pr.add(self.pos.x + math.cos(a) * rr, self.pos.y + math.sin(a) * rr * 0.75, 0, -60, 0.8, 9, (255, 90, 20), 'fire')
        elif v in ('blackhole',):
            for _ in range(int(dt * 60)):
                a = random.uniform(0, 6.28)
                rr = self.r * random.uniform(0.6, 1.2)
                q = V(self.pos.x + math.cos(a) * rr, self.pos.y + math.sin(a) * rr * 0.75)
                vv = (self.pos - q) * 1.8 + V(-math.sin(a), math.cos(a)) * 150
                pr.add(q.x, q.y, vv.x, vv.y, 0.5, 10, (60, 20, 80), 'dark', drag=1.0)
        elif v in ('quicksand', 'dry'):
            for _ in range(int(dt * 50)):
                a = random.uniform(0, 6.28)
                rr = self.r * random.uniform(0.2, 1.0)
                pr.add(self.pos.x + math.cos(a) * rr, self.pos.y + math.sin(a) * rr * 0.75, -math.sin(a) * 160, math.cos(a) * 100, 0.6, 10, c, 'dust')
        elif v in ('poison', 'smoke_field'):
            for _ in range(int(dt * 30)):
                a = random.uniform(0, 6.28)
                rr = self.r * random.uniform(0, 1.0)
                pr.add(self.pos.x + math.cos(a) * rr, self.pos.y + math.sin(a) * rr * 0.75, random.uniform(-20, 20), -20, 1.2, 22, c, 'smoke', grow=10)
        elif v in ('blizzard',):
            for _ in range(int(dt * 60)):
                a = random.uniform(0, 6.28)
                rr = self.r * random.uniform(0, 1.0)
                pr.add(self.pos.x + math.cos(a) * rr, self.pos.y + math.sin(a) * rr * 0.75, -math.sin(a) * 200, math.cos(a) * 120, 0.5, 3, (240, 250, 255), 'glow')
        elif v in ('tornado', 'blades', 'mochi_ring'):
            for _ in range(int(dt * 40)):
                a = random.uniform(0, 6.28)
                rr = self.r * random.uniform(0.5, 1.0)
                col = (240, 240, 255) if v != 'mochi_ring' else (245, 235, 215)
                pr.add(self.pos.x + math.cos(a) * rr, self.pos.y + math.sin(a) * rr * 0.75, -math.sin(a) * 400, math.cos(a) * 300, 0.25, 3, col, 'line')
        elif v in ('arms_field',) and random.random() < dt * 10:
            a = random.uniform(0, 6.28)
            rr = self.r * random.uniform(0, 1.0)
            self.sc.effects.append(SpikeFX(self.pos + V(math.cos(a) * rr, math.sin(a) * rr * 0.75), 22, c, 0.6, 'spike'))
        elif v in ('gravity',) and random.random() < dt * 6:
            self.sc.effects.append(RingFX(self.pos, self.r, 10, 0.5, (170, 120, 255), 3, layer=0))
        elif v in ('shadow_pool',) and random.random() < dt * 20:
            a = random.uniform(0, 6.28)
            rr = self.r * random.uniform(0, 1.0)
            pr.add(self.pos.x + math.cos(a) * rr, self.pos.y + math.sin(a) * rr * 0.75, 0, -30, 0.8, 10, (40, 20, 60), 'dark')

    def draw(self, surf, ox, oy):
        x, y = self.pos.x - ox, self.pos.y - oy
        v = self.vis
        c = self.ed['c1']
        r = self.r
        fade = min(1, self.life * 2)
        if v in ('lava',):
            alpha_circle_e(surf, (x, y), r, (220, 60, 10), int(140 * fade))
        elif v in ('blackhole',):
            alpha_circle_e(surf, (x, y), r, (30, 5, 40), int(170 * fade))
            alpha_circle_e(surf, (x, y), r * 0.45, (0, 0, 0), int(230 * fade))
            for i in range(3):
                a = self.t * 3 + i * 2.1
                pygame.draw.arc(surf, (130, 60, 170), (x - r * 0.8, y - r * 0.6, r * 1.6, r * 1.2), a, a + 1.5, 3)
        elif v in ('quicksand', 'dry'):
            alpha_circle_e(surf, (x, y), r, (200, 170, 100), int(110 * fade))
            for i in range(4):
                a = -self.t * 2 + i * 1.57
                rr = r * (0.3 + 0.17 * i)
                pygame.draw.arc(surf, (160, 130, 70), (x - rr, y - rr * 0.75, rr * 2, rr * 1.5), a, a + 2.0, 2)
        elif v in ('ring_wall',):
            pygame.draw.ellipse(surf, (255, 140, 40), (x - r, y - r * 0.75, r * 2, r * 1.5), 4)
        elif v in ('cage', 'room'):
            pass
        elif v in ('gravity', 'shadow_pool', 'poison', 'smoke_field', 'arms_field', 'blizzard', 'field', 'blades', 'mochi_ring', 'tornado'):
            col = {'gravity': (120, 60, 200), 'shadow_pool': (30, 10, 40), 'poison': (120, 40, 150), 'smoke_field': (220, 220, 225),
                   'arms_field': (255, 150, 200), 'blizzard': (200, 230, 255), 'field': c, 'blades': (230, 230, 240), 'mochi_ring': (245, 235, 215), 'tornado': (220, 240, 255)}[v]
            alpha_circle_e(surf, (x, y), r, col, int(60 * fade))
            if v in ('blades', 'mochi_ring', 'tornado'):
                for i in range(6):
                    a = self.t * 7 + i * 1.05
                    q = (x + math.cos(a) * r * 0.85, y + math.sin(a) * r * 0.65 - 20)
                    if v == 'mochi_ring':
                        ocircle(surf, (245, 235, 215), q, 14, 2)
                    else:
                        pygame.draw.line(surf, (255, 255, 255), q, (q[0] + math.cos(a + 1.57) * 22, q[1] + math.sin(a + 1.57) * 16), 3)

def alpha_circle_e(surf, pos, r, color, alpha):
    r = max(2, int(r))
    s = pygame.Surface((r * 2, int(r * 1.5)), pygame.SRCALPHA)
    pygame.draw.ellipse(s, (*color[:3], clamp(alpha, 0, 255)), s.get_rect())
    surf.blit(s, (pos[0] - r, pos[1] - r * 0.75))

# ------------------------------------------------------------------
#  ИИ
# ------------------------------------------------------------------
def move_range(mv):
    if not mv['steps']:
        return 200
    p = mv['steps'][0][1]
    t = p.get('p')
    if t == 'melee':
        return p['r'] + p.get('off', 20)
    if t == 'proj':
        return min(700, p.get('spd', 700) * p.get('life', 0.8) * 0.8)
    if t == 'beam':
        return p.get('len', 500) * 0.9
    if t == 'nova':
        return {'self': p['r'] * 0.8, 'cursor': 480, 'front': p['r'] * 1.4}[p.get('at', 'self')]
    if t == 'dash':
        return p.get('dist', 260)
    if t == 'barrage':
        return p['r']
    if t in ('rain',):
        return 520
    if t == 'zone':
        return p['r'] * 0.8 if p.get('at') == 'self' else 450
    if t == 'wave':
        return p.get('n', 7) * p.get('step', 60)
    if t == 'grab':
        return p.get('r', 260)
    return 9999

def basic_move_for(f, idx, heavy=False, charge=1.0):
    """Синтезирует базовый удар из комбо стиля."""
    combo = f.combo_def
    dmg, r, arc, knock, launch, vis = combo[idx % len(combo)]
    e = f.combo_el
    if f.ranged_basic or vis in ('shot', 'zap'):
        shape = 'orb' if vis == 'shot' else 'light_orb'
        e2 = 'thunder' if vis == 'zap' else e
        p = P_proj(dmg * (2.2 if heavy else 1.0), 1100, 7 if not heavy else 14, 0.6, shape=shape, el_=e2, knock=knock * (2 if heavy else 1),
                   explode=60 if heavy else 0)
        return MV("Выстрел", 0, 0, [S(0, p)], cast=0.04 if not heavy else 0.0, lock=0.12 if not heavy else 0.25)
    if heavy:
        p = P_melee(dmg * 1.4, r * 1.25, arc + 20, knock * 1.4, max(launch, 200), vis, e, 0.5, off=24, destroy=2.0, heavy_flag=True)
        return MV("Заряженный удар", 0, 0, [S(0, p)], cast=0.0, lock=0.28)
    p = P_melee(dmg, r, arc, knock, launch, vis, e, 0.25 if idx < 3 else 0.45, off=18)
    return MV("Удар", 0, 0, [S(0, p)], cast=0.03 if f.kind == 'player' else (0.32 if not f.elite else 0.22), lock=0.12 if f.kind == 'player' else 0.25,
              tele='cone' if f.kind != 'player' else None)

class AIController:
    def __init__(self, f, kind='melee', aggro_r=430):
        self.f = f
        self.kind = kind
        self.target = None
        self.think = random.uniform(0, 0.4)
        self.aggro = False
        self.aggro_r = aggro_r
        self.strafe = random.choice((-1, 1))
        self.strafe_t = random.uniform(1, 3)
        self.home = V(f.pos)
        self.combo_left = 0
        self.special_cd = random.uniform(1.0, 3.0)
        self.ult_used = 0.0
        self.follow = None

    def pick_target(self):
        f = self.f
        sc = f.scene
        best = None
        bd = 1e9
        for o in sc.fighters:
            if not f.hostile_to(o):
                continue
            if o.kind == 'summon' and o.team != 'enemy' and random.random() < 0.3:
                pass
            dd = dist(o.pos, f.pos)
            if dd < bd:
                bd = dd
                best = o
        return best, bd

    def update(self, dt):
        f = self.f
        sc = f.scene
        if f.dead:
            return
        self.think -= dt
        self.special_cd -= dt
        self.strafe_t -= dt
        if self.strafe_t <= 0:
            self.strafe_t = random.uniform(1, 3)
            self.strafe = -self.strafe
        if not f.can_act():
            f.vel = V(0, 0)
            f.walk = 0
            return
        if self.think <= 0:
            self.think = 0.35
            tg, dd = self.pick_target()
            limit = self.aggro_r * (2.5 if self.aggro else 1.0)
            if f.team != 'enemy':
                limit = 650
            if tg is not None and dd < limit:
                self.target = tg
                if not self.aggro and f.team == 'enemy':
                    self.aggro = True
                    sc.alert_group(f)
            else:
                self.target = None
        tg = self.target
        if f.is_boss:
            self.boss_phase_check()
        if tg is None or tg.dead:
            self.idle(dt)
            return
        dv = tg.pos - f.pos
        dd = dv.length()
        if dd > 0:
            f.aim = math.atan2(dv.y, dv.x)
            f.facing = f.aim
        if f.action is not None:
            f.vel *= 0.0 if f.kind != 'player' else 1.0
            f.walk = 0
            return
        # специальные приёмы
        if self.special_cd <= 0 and f.moves:
            mids = list(f.moves)
            random.shuffle(mids)
            for mid in mids:
                if f.cooldowns.get(mid, 0) > 0:
                    continue
                mv = MOVES[mid]
                if mv.get('ult'):
                    hp_frac = f.hp / f.max_hp
                    if not f.is_boss or hp_frac > 0.75 or self.ult_used > 0:
                        continue
                p0 = mv['steps'][0][1]['p'] if mv['steps'] else ''
                rng_ = move_range(mv)
                if p0 in ('buff', 'shield', 'heal', 'summon'):
                    if p0 == 'heal' and f.hp > f.max_hp * 0.6:
                        continue
                    if p0 == 'buff' and any(b.get('form') for b in f.buffs):
                        continue
                    if random.random() > 0.35:
                        continue
                elif p0 == 'teleport':
                    if dd < 200 and random.random() > 0.3:
                        continue
                elif dd > rng_ * 1.05:
                    continue
                self.use_move(mid, tg)
                cd_scale = 1.0 if not f.is_boss else 0.7
                f.cooldowns[mid] = mv['cd'] * cd_scale * random.uniform(0.9, 1.4) + (2 if not f.elite else 0)
                self.special_cd = random.uniform(0.6, 1.6) if f.is_boss else random.uniform(1.5, 3.5)
                if mv.get('ult'):
                    self.ult_used = 1
                return
        reach = f.combo_def[0][1] + 18 if not f.ranged_basic else 420
        if f.kind != 'player' and self.kind == 'ranged':
            reach = 420
        if dd < reach * 0.95 and f.attack_cd <= 0 and (self.kind != 'ranged' or f.ranged_basic or not f.moves):
            idx = self.combo_left
            mv = basic_move_for(f, idx)
            f.action = MoveRun(f, None, mv, tg.pos, basic=True)
            self.combo_left = (self.combo_left + 1) % (3 if f.elite else 2)
            if self.combo_left == 0:
                f.attack_cd = random.uniform(0.8, 1.6) if not f.is_boss else random.uniform(0.3, 0.8)
            else:
                f.attack_cd = 0.15
            f.vel = V(0, 0)
            return
        # перемещение
        sp = f.speed()
        if self.kind == 'ranged' and f.kind != 'boss':
            want = 0
            if dd < 220:
                want = -1
            elif dd > 400:
                want = 1
            mvv = dv.normalize() * want + dv.normalize().rotate(90) * self.strafe * 0.6 if dd > 0 else V(0, 0)
        else:
            if dd > reach * 0.8:
                mvv = dv.normalize() + dv.normalize().rotate(90) * self.strafe * (0.35 if dd < 260 else 0.1)
                if dd > 110 and hasattr(sc, 'player_field') and (tg is sc.player or dist(tg.pos, sc.player.pos) < 140):
                    fd = sc.flow_dir(sc.player_field(), f.pos)
                    if fd is not None:
                        mvv = fd * 1.2 + dv.normalize() * 0.15
            else:
                mvv = dv.normalize().rotate(90) * self.strafe * 0.5
        # отталкивание от своих
        for o in sc.fighters:
            if o is f or o.dead or o.team != f.team:
                continue
            od = f.pos - o.pos
            l2 = od.length_squared()
            if 0 < l2 < (f.radius + o.radius + 8) ** 2:
                mvv += od.normalize() * 0.8
        if mvv.length_squared() > 0:
            mvv = mvv.normalize()
        f.vel = mvv * sp
        f.walk = 1.0 if mvv.length_squared() > 0 else 0
        if f.vel.length_squared() > 1 and f.action is None:
            f.facing = f.aim

    def use_move(self, mid, tg):
        f = self.f
        mv = MOVES[mid]
        if mv.get('ult') and f.is_boss:
            f.scene.cutin(f, mv, enemy=True)
        f.action = MoveRun(f, mid, mv, tg.pos)
        f.vel = V(0, 0)

    def idle(self, dt):
        f = self.f
        if f.team != 'enemy':
            pl = f.scene.player
            if pl is not None and not pl.dead:
                dv = pl.pos - f.pos
                dd = dv.length()
                if dd > 110:
                    mv_ = dv.normalize()
                    if hasattr(f.scene, 'player_field'):
                        fd = f.scene.flow_dir(f.scene.player_field(), f.pos)
                        if fd is not None:
                            mv_ = fd
                    f.vel = mv_ * f.speed() * (1.3 if dd > 400 else 1.0)
                    f.walk = 1
                    f.facing = math.atan2(dv.y, dv.x)
                    if dd > 1200:
                        f.pos = pl.pos + from_angle(random.uniform(0, 6.28), 60)
                    return
            f.vel = V(0, 0)
            f.walk = 0
            return
        dv = self.home - f.pos
        if dv.length() > 40:
            f.vel = dv.normalize() * f.speed() * 0.5
            f.walk = 0.6
            f.facing = math.atan2(dv.y, dv.x)
        else:
            f.vel = V(0, 0)
            f.walk = 0

    def boss_phase_check(self):
        f = self.f
        bd = BOSSES.get(f.boss_id)
        if not bd:
            return
        phases = bd['phases']
        if f.phase_idx < len(phases):
            thr, ph = phases[f.phase_idx]
            if f.hp <= f.max_hp * thr:
                f.phase_idx += 1
                f.scene.boss_phase(f, ph)

# ==================================================================
#  ИГРОК: ДАННЫЕ ПРОГРЕССИИ И БОЕЦ
# ==================================================================
RACES = {
    'human': dict(name="Человек", desc="Сбалансированный. Может стать кем угодно.", hp=1.0, atk=1.0, spd=1.0),
    'fishman': dict(name="Рыбочеловек", desc="В 10 раз сильнее человека, быстро плавает. Слабее на суше в скорости. Карате рыболюдей доступно сразу.",
                    hp=1.15, atk=1.15, spd=0.95, swim=True, style='fishman_karate'),
    'mink': dict(name="Минк", desc="Быстрые воины с силой Электро. Под полной луной могут стать Сулонгом.", hp=1.0, atk=1.05, spd=1.12, style='electro'),
    'skypiean': dict(name="Небесный житель", desc="Острое Наблюдение (Мантра) с самого начала. Лёгкий и быстрый.", hp=0.92, atk=1.0, spd=1.1, obs=True),
    'longleg': dict(name="Племя Длинноногих", desc="Сокрушительные удары ногами. Чёрная Нога доступна сразу.", hp=1.0, atk=1.08, spd=1.05, style='blackleg'),
    'lunarian': dict(name="Лунариец", desc="Огонь за спиной, невероятная живучесть. Мировое Правительство охотится на таких. Награда растёт быстрее.",
                     hp=1.3, atk=1.05, spd=1.0, fire=True),
    'halfgiant': dict(name="Полувеликан", desc="Огромная сила и здоровье, но медленнее.", hp=1.35, atk=1.2, spd=0.88, scale=1.35),
}
TRAITS = {
    'king': dict(name="Качества Короля", desc="Один на миллион: Королевское Хаки может пробудиться."),
    'd_will': dict(name="Воля «D.»", desc="Раз за бой не падаешь от смертельного удара. Смеёшься в лицо смерти."),
    'iron': dict(name="Железное тело", desc="+20% здоровья, +10% защиты."),
    'genius': dict(name="Гений боя", desc="Мастерство стилей и фруктов растёт на 40% быстрее."),
    'lucky': dict(name="Удачливый", desc="Больше белли и добычи, выше шанс крита."),
}

def xp_need(level):
    return int(40 * level ** 1.5) + 40

class PlayerData:
    def __init__(self):
        self.name = "Безымянный"
        self.app = default_app()
        self.race = 'human'
        self.faction = 'pirate'
        self.trait = 'king'
        self.level = 1
        self.xp = 0
        self.points = 0
        self.stats = {'str': 0, 'vit': 0, 'agi': 0, 'haki': 0, 'fruit': 0}
        self.beli = 3000
        self.bounty = 0
        self.merit = 0
        self.fruit = None
        self.fruit2 = None
        self.fruit_mastery = 0.0
        self.styles = {'brawler': 0.0}
        self.style = 'brawler'
        self.loadout = [None, None, None, None]
        self.ult = None
        self.haki = {'arm': 0, 'obs': 0, 'conq': 0}
        self.haki_xp = {'arm': 0.0, 'obs': 0.0, 'conq': 0.0}
        self.haki_cap = {'arm': 0, 'obs': 0, 'conq': 0}
        self.flags = set()
        self.inventory = []
        self.equip = {'weapon': None, 'outfit': None, 'acc1': None, 'acc2': None}
        self.mats = {}
        self.crew = []
        self.companions = []
        self.active_comp = []
        self.ship = new_ship('dinghy')
        self.islands = {}
        self.sea_pos = [2900, 26400]
        self.sea_heading = -1.2
        self.kills = 0
        self.destroyed = 0
        self.log = []
        self.playtime = 0.0
        self.mentors_done = set()
        self.poneglyphs = 0
        self.titles = []
        self.difficulty = 1.0
        self.last_island = None
        self.quests = []
        self.bosses_beaten = set()

    # ------------- сериализация -------------
    def to_json(self):
        d = dict(self.__dict__)
        d['flags'] = sorted(self.flags)
        d['mentors_done'] = sorted(self.mentors_done)
        d['bosses_beaten'] = sorted(self.bosses_beaten)
        d['app'] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in self.app.items()}
        return d

    @staticmethod
    def from_json(d):
        pd = PlayerData()
        for k, v in d.items():
            setattr(pd, k, v)
        pd.flags = set(d.get('flags', []))
        pd.mentors_done = set(d.get('mentors_done', []))
        pd.bosses_beaten = set(d.get('bosses_beaten', []))
        app = dict(default_app())
        for k, v in d.get('app', {}).items():
            if isinstance(v, list) and k in ('features',):
                app[k] = tuple(v)
            elif isinstance(v, list) and len(v) == 3 and all(isinstance(x, int) for x in v):
                app[k] = tuple(v)
            else:
                app[k] = v
        pd.app = app
        base_ship = new_ship(pd.ship.get('tier', 'dinghy'))
        base_ship.update(pd.ship)
        pd.ship = base_ship
        return pd

    # ------------- прогресс -------------
    def rep_value(self):
        return self.merit if self.faction in ('marine', 'revo', 'hunter') else self.bounty

    def title(self):
        if self.faction == 'marine':
            return title_for(MARINE_RANKS, self.merit)
        if self.faction == 'revo':
            return title_for(REVO_RANKS, self.merit)
        if self.faction == 'hunter':
            return title_for(HUNTER_RANKS, self.merit)
        return title_for(PIRATE_TITLES, self.bounty)

    def add_xp(self, amount):
        mult = 1.0
        for it in self.equipped_items():
            mult += it.get('xp', 0)
        if any(c['role'] == 'musician' for c in self.crew):
            mult += 0.1
        amount = int(amount * mult)
        self.xp += amount
        ups = 0
        while self.xp >= xp_need(self.level) and self.level < 100:
            self.xp -= xp_need(self.level)
            self.level += 1
            self.points += 3
            ups += 1
        return ups

    def style_gain(self, style, amount):
        if self.trait == 'genius':
            amount *= 1.4
        if self.fruit is None:
            amount *= 1.2
        cur = self.styles.get(style, 0.0)
        self.styles[style] = min(100.0, cur + amount)
        return int(cur) != int(self.styles[style])

    def fruit_gain(self, amount):
        if not self.fruit:
            return False
        if self.trait == 'genius':
            amount *= 1.4
        cur = self.fruit_mastery
        self.fruit_mastery = min(100.0, cur + amount)
        return int(cur) != int(self.fruit_mastery)

    def haki_gain(self, kind, amount):
        if self.haki_cap.get(kind, 0) <= 0:
            return False
        lvl = self.haki[kind]
        cap = self.haki_cap[kind]
        if lvl >= cap:
            return False
        self.haki_xp[kind] += amount * (1 + self.stats['haki'] * 0.02)
        need = 60 + 60 * lvl
        if self.haki_xp[kind] >= need:
            self.haki_xp[kind] -= need
            self.haki[kind] = lvl + 1
            return True
        return False

    def unlock_haki(self, kind, cap):
        if kind == 'conq' and self.trait != 'king':
            return False
        new = self.haki_cap.get(kind, 0) < cap
        self.haki_cap[kind] = max(self.haki_cap.get(kind, 0), cap)
        if self.haki[kind] == 0 and cap > 0:
            self.haki[kind] = 1
        return new

    def unlocked_moves(self):
        res = []
        for sid, m in self.styles.items():
            st = STYLES.get(sid)
            if not st:
                continue
            for lvl, mid in st['moves']:
                if m >= lvl:
                    res.append(mid)
        if self.fruit:
            for lvl, mid in FRUITS[self.fruit]['moves']:
                if self.fruit_mastery >= lvl:
                    res.append(mid)
        if self.fruit2:
            for lvl, mid in FRUITS[self.fruit2]['moves']:
                if self.fruit_mastery >= lvl + 10:
                    res.append(mid)
        out = []
        for m in res:
            if m and m not in out:
                out.append(m)
        return out

    def fix_loadout(self):
        um = self.unlocked_moves()
        normal = [m for m in um if not MOVES[m].get('ult')]
        ults = [m for m in um if MOVES[m].get('ult')]
        self.loadout = [m if (m in normal) else None for m in self.loadout]
        for m in normal:
            if m not in self.loadout and None in self.loadout:
                self.loadout[self.loadout.index(None)] = m
        if self.ult not in ults:
            self.ult = ults[-1] if ults else None

    def equipped_items(self):
        return [it for it in self.equip.values() if it]

    def weapon_kind(self):
        w_ = self.equip.get('weapon')
        return w_.get('kind') if w_ else None

    def style_usable(self, sid):
        st = STYLES[sid]
        if st.get('weapon') == 'sword':
            return self.weapon_kind() == 'sword'
        if st.get('weapon') == 'clima':
            return self.weapon_kind() == 'clima'
        return True

    def add_item(self, it):
        if it.get('kind') == 'mat':
            self.mats[it['id']] = self.mats.get(it['id'], 0) + 1
        else:
            self.inventory.append(it)

    def count(self, iid):
        if iid in ITEMS and ITEMS[iid]['kind'] == 'mat':
            return self.mats.get(iid, 0)
        return sum(1 for it in self.inventory if it.get('id') == iid)

    def remove_item(self, iid, n=1):
        if iid in ITEMS and ITEMS[iid]['kind'] == 'mat':
            if self.mats.get(iid, 0) < n:
                return False
            self.mats[iid] -= n
            return True
        for _ in range(n):
            for i, it in enumerate(self.inventory):
                if it.get('id') == iid:
                    self.inventory.pop(i)
                    break
            else:
                return False
        return True

    def island_state(self, iid):
        if iid not in self.islands:
            self.islands[iid] = {'done': False, 'visited': False, 'chest': False, 'extra': False}
        return self.islands[iid]

    def eat_fruit(self, fid):
        if self.fruit is None:
            self.fruit = fid
            self.fruit_mastery = 0.0
            first = FRUITS[fid]['moves'][0][1]
            self.loadout = [first] + [m for m in self.loadout if m != first][:3]
            self.fix_loadout()
            return 'ok'
        if self.fruit == 'yami' and self.fruit2 is None and fid != 'yami':
            self.fruit2 = fid
            self.fix_loadout()
            return 'second'
        return 'death'

def compute_stats(pd):
    r = RACES.get(pd.race, RACES['human'])
    s = pd.stats
    L = pd.level
    st = dict(max_hp=(110 + 20 * L + 14 * s['vit']) * r['hp'], atk=(10 + 2.2 * L + 1.6 * s['str']) * r['atk'],
              fruit=(10 + 2.2 * L + 1.6 * s['fruit']) * r['atk'], haki=(10 + 2.2 * L + 1.6 * s['haki']) * r['atk'],
              defn=L * 1.2 + s['vit'] * 1.8, speed=235 * r['spd'] * (1 + 0.004 * s['agi']), crit=0.05 + s['agi'] * 0.0015,
              max_st=100 + s['agi'] * 1.0 + L * 0.5, max_haki=100 + s['haki'] * 2.0, cdr=min(0.4, s['agi'] * 0.003),
              heavy=0.0, fire=0.0, xp=0.0, revive=False, seastone=False)
    if pd.trait == 'iron':
        st['max_hp'] *= 1.2
        st['defn'] *= 1.1
    if pd.trait == 'lucky':
        st['crit'] += 0.06
    for it in pd.equipped_items():
        plus = it.get('plus', 0)
        k = 1 + plus * 0.12
        st['atk'] += it.get('atk', 0) * k
        st['defn'] += it.get('defn', 0) * k
        st['max_hp'] += it.get('hp', 0) * k
        st['speed'] *= 1 + it.get('spd', 0)
        st['crit'] += it.get('crit', 0)
        st['haki'] *= 1 + it.get('haki', 0)
        st['fruit'] *= 1 + it.get('fruit', 0)
        st['heavy'] += it.get('heavy', 0)
        st['fire'] += it.get('fire', 0)
        if it.get('revive'):
            st['revive'] = True
        if it.get('seastone'):
            st['seastone'] = True
    if 'giant_blessing' in pd.flags:
        st['atk'] *= 1.05
    if 'timeskip' in pd.flags:
        st['max_hp'] *= 1.1
        st['atk'] *= 1.08
    return st

def new_ship(tier='dinghy'):
    T = SHIP_TIERS[tier]
    return dict(tier=tier, name=T['name'], hp=T['hp'], max_hp=T['hp'], cannons=T['cannons'], sail_lvl=0, hull_lvl=0, cannon_lvl=0,
                coup=False, gaon=False, kairo=False, cola=0, color=list(T['color']), sail_color=[240, 240, 235], figure='lion',
                flag='skull', dock=0)

SHIP_TIERS = {
    'dinghy': dict(name="Шлюпка", hp=500, speed=300, turn=1.9, cannons=1, size=0.7, color=(150, 105, 60), cost=0, masts=1),
    'caravel': dict(name="Каравелла", hp=800, speed=360, turn=1.6, cannons=2, size=1.0, color=(160, 115, 70), cost=60000, masts=1),
    'brig': dict(name="Бриг", hp=1600, speed=400, turn=1.4, cannons=3, size=1.2, color=(120, 80, 50), cost=400000, masts=2),
    'galleon': dict(name="Галеон из Древа Адама", hp=3200, speed=450, turn=1.35, cannons=4, size=1.45, color=(210, 160, 90), cost=2000000, masts=2),
    'warship': dict(name="Флагман", hp=5200, speed=480, turn=1.25, cannons=5, size=1.7, color=(90, 70, 60), cost=6000000, masts=3),
}
SHIP_ORDER = ['dinghy', 'caravel', 'brig', 'galleon', 'warship']

class PlayerFighter(Fighter):
    def __init__(self, scene, pd, pos):
        app = dict(pd.app)
        super().__init__(scene, 'player', app, pos, pd.level, pd.name, 'player')
        self.pd = pd
        self.st = 100
        self.haki_g = 100
        self.spirit = 0.0
        self.charging = False
        self.charge = 0.0
        self.obs_t = 0.0
        self.obs_cd = 0.0
        self.conq_cd = 0.0
        self.dash_cd = 0.0
        self.eat_cd = 0.0
        self.buffer = None
        self.buffer_t = 0.0
        self.combo_window = 0.0
        self.awak_t = 0.0
        self.ryou = False
        self.conq_coat = False
        self.fs_t = 0.0
        self.apply_stats(full=True)

    def apply_stats(self, full=False):
        pd = self.pd
        s = compute_stats(pd)
        self.stats = s
        self.level = pd.level
        r = RACES.get(pd.race, RACES['human'])
        old_frac = self.hp / self.max_hp if self.max_hp > 0 else 1
        self.max_hp = s['max_hp']
        self.hp = self.max_hp if full else self.max_hp * old_frac
        self.atk = s['atk']
        self.fruit_pow = s['fruit']
        self.haki_pow = s['haki']
        self.defn = s['defn']
        self.base_speed = s['speed']
        self.crit = s['crit']
        self.max_st = s['max_st']
        self.max_haki = s['max_haki']
        self.heavy_bonus = s['heavy']
        self.fire_bonus = s['fire']
        self.revive = s['revive'] or pd.trait == 'd_will'
        self.weapon_seastone = s['seastone']
        if full:
            self.st = self.max_st
            self.haki_g = self.max_haki
        sid = pd.style if pd.style_usable(pd.style) else 'brawler'
        st = STYLES[sid]
        self.style = sid
        self.combo_def = st['combo']
        self.combo_el = st.get('el', 'phys')
        self.ranged_basic = st.get('ranged', False)
        if r.get('fire'):
            self.combo_el = 'fire' if self.combo_el == 'phys' else self.combo_el
        self.fishman = r.get('swim', False)
        self.fruit_user = pd.fruit is not None
        self.logia = FRUITS[pd.fruit].get('logia') if pd.fruit else None
        passive = FRUITS[pd.fruit].get('passive', {}) if pd.fruit else {}
        self.immune = passive.get('immune')
        self.blunt_res = passive.get('blunt', 0.0)
        self.passive_regen = passive.get('regen', 0.0)
        self.ryou = 'ryou' in pd.flags and pd.haki['arm'] >= 8
        self.conq_coat = 'conq_coat' in pd.flags and pd.haki['conq'] >= 5
        self.fs = 'future_sight' in pd.flags and pd.haki['obs'] >= 7
        self.scale = r.get('scale', 1.0)
        app = dict(pd.app)
        app['scale'] = self.scale
        w_ = pd.equip.get('weapon')
        if w_ and w_.get('kind') == 'sword':
            if w_.get('vis'):
                app['weapon'] = w_['vis']
            elif w_.get('big'):
                app['weapon'] = 'big_sword'
            else:
                app['weapon'] = {'sword1': 'sword1', 'sword2': 'sword2', 'sword3': 'sword3'}.get(sid, 'sword1')
        elif w_ and w_.get('kind') == 'gun':
            app['weapon'] = w_.get('vis', 'gun')
        elif w_ and w_.get('kind') == 'clima':
            app['weapon'] = 'clima'
        elif w_ and w_.get('kind') == 'fist':
            app['weapon'] = 'none'
        else:
            app['weapon'] = 'none'
        feats = list(app.get('features', ()))
        if pd.race == 'fishman' and 'fishman' not in feats:
            feats += ['fishman', 'fin']
        if pd.race == 'mink' and 'mink' not in feats:
            feats += ['mink']
            app['fur'] = app.get('fur') or app['hair_col']
        if pd.race == 'lunarian' and 'lunarian' not in feats:
            feats += ['lunarian']
        if pd.race == 'longleg' and 'long_legs' not in feats:
            feats += ['long_legs']
        app['features'] = tuple(feats)
        o = pd.equip.get('outfit')
        if o and o.get('id') == 'marine_coat':
            app['cape'] = (245, 245, 245)
        self.app = app
        self.radius = 13 * self.scale
        self.moves = [m for m in pd.loadout if m]

    def arm_mult(self):
        lvl = self.pd.haki['arm']
        m = 1.12 + 0.035 * lvl
        if self.ryou:
            m += 0.15
        if self.conq_coat:
            m += 0.25
        return m

    def arm_def(self):
        return 1 - (0.06 + 0.025 * self.pd.haki['arm'])

    def uses_haki(self):
        return self.armament

def make_enemy(scene, etype, level, pos, team='enemy', group=None):
    E = ENEMY_TYPES[etype]
    app = dict(E['app'])
    kind = 'elite' if E.get('elite') else 'mook'
    f = Fighter(scene, team, app, pos, level, E['name'], kind, E['hp'], E['dmg'], E['spd'])
    f.moves = list(E.get('moves', []))
    wp = app.get('weapon', 'none')
    if wp.startswith('sword') or wp in ('axe', 'club', 'trident', 'jitte', 'staff', 'claw', 'bisento'):
        sid = 'sword1'
    else:
        sid = 'brawler'
    f.combo_def = STYLES[sid]['combo']
    f.ranged_basic = E['ai'] == 'ranged' and not f.moves
    f.ai = AIController(f, E['ai'])
    f.xp_value = int(E['xp'] * (1 + 0.6 * level))
    f.group = group
    f.fishman = 'fishman' in app.get('features', ())
    if level >= 55 and (kind == 'elite' or random.random() < 0.3):
        f.haki_always = True
    if etype in ('pacifista', 'seraphim'):
        f.armor = 0.25
    f.etype = etype
    f.ckey = 'e:' + etype
    return f

def make_boss(scene, bid, level, pos, team='enemy', elite_mode=False):
    B_ = BOSSES[bid]
    app = dict(B_['app'])
    kind = 'elite' if (B_.get('elite') or elite_mode) else 'boss'
    f = Fighter(scene, team, app, pos, level, B_['name'], kind, B_['hp'], B_['dmg'], B_['spd'])
    f.boss_id = bid
    f.moves = list(B_['moves'])
    f.combo_def = STYLES[B_.get('combo', 'brawler')]['combo']
    f.logia = B_.get('logia')
    f.immune = B_.get('immune')
    f.dodge = B_.get('dodge', 0)
    f.fs = B_.get('fs', False)
    f.armor = B_.get('armor', 0)
    f.haki_always = B_.get('haki', False)
    f.fruit_user = any(m in fruit_move_set() for m in f.moves)
    f.fishman = 'fishman' in app.get('features', ())
    f.ai = AIController(f, 'ranged' if B_.get('ranged') else 'melee', aggro_r=520 if kind == 'boss' else 450)
    f.xp_value = int(10 * B_['hp'] * (1 + level * 0.5))
    k = clamp(1 - (level - 20) * 0.008, 0.6, 1.0)
    f.max_hp *= k
    f.hp = f.max_hp
    f.bounty = B_.get('bounty', 0)
    f.title = B_.get('title', '')
    f.is_boss = kind == 'boss'
    f.elite = True
    if f.is_boss:
        f.radius = 15 * f.scale
    return f

_FRUIT_MOVE_SET = None

def fruit_move_set():
    global _FRUIT_MOVE_SET
    if _FRUIT_MOVE_SET is None:
        _FRUIT_MOVE_SET = set(mm for FR in FRUITS.values() for _, mm in FR['moves'])
    return _FRUIT_MOVE_SET

def make_companion(scene, cid, level, pos, crew=None):
    if crew is not None:
        app = crew['app']
        f = Fighter(scene, 'ally', app, pos, level, crew['name'], 'ally', 1.0, 0.9, 200)
        f.moves = ['brawl_haymaker']
        f.combo_def = STYLES['brawler']['combo']
        f.ai = AIController(f, 'melee')
        return f
    C = COMPANIONS[cid]
    f = Fighter(scene, 'ally', dict(C['app']), pos, level, C['name'], 'ally', 2.2 * C['hp'], 1.0 * C['dmg'], 215)
    f.moves = list(C['moves'])
    f.combo_def = STYLES[C.get('combo', 'brawler')]['combo']
    f.ai = AIController(f, 'melee')
    f.comp_id = cid
    return f

def make_crew_member(rng=random, lvl=1, role=None):
    role = role or rng.choice([r for r in CREW_ROLES])
    name = rng.choice(CREW_FIRST) + " «" + rng.choice(CREW_EPI) + "»"
    app = default_app(skin=rng.choice(SKIN_TONES[:6]), hair=rng.choice(HAIR_STYLES), hair_col=rng.choice(HAIR_COLORS),
                      outfit=rng.choice(['shirt', 'vest', 'tank', 'jacket', 'coat']), top=rng.choice(CLOTH_COLORS),
                      bottom=rng.choice(CLOTH_COLORS), hat=rng.choice(['none', 'bandana', 'cap', 'tricorn', 'headband', 'none']),
                      hat_col=rng.choice(CLOTH_COLORS))
    return dict(name=name, role=role, lvl=lvl, app=app, price=int(800 * (1 + lvl) ** 1.25))

# ==================================================================
#  ОСТРОВ: КАРТА, ЗЕМЛЯ, ПОСТРОЙКИ, РАЗРУШЕНИЯ
# ==================================================================
G_DEEP, G_SHALLOW, G_SAND, G_GRASS, G_GRASS2, G_PATH, G_DECK, G_PLAZA = 0, 1, 2, 3, 4, 5, 6, 7
S_NONE, S_BURN, S_SCORCH, S_ICE, S_LAVA, S_CRATER, S_DRY, S_POISON, S_RUBBLE = 0, 1, 2, 3, 4, 5, 6, 7, 8
CHUNK = 16
FLAMMABLE = (G_GRASS, G_GRASS2, G_DECK)

_GRAIN = None
_GRAIN_S = None

def grain_surfs():
    global _GRAIN_S
    if _GRAIN_S is None:
        g = grain()
        pos = np.clip(g, 0, 255).astype(np.uint8)
        neg = np.clip(-g, 0, 255).astype(np.uint8)
        sa = pygame.Surface((CHUNK * TILE, CHUNK * TILE))
        ss = pygame.Surface((CHUNK * TILE, CHUNK * TILE))
        pygame.surfarray.blit_array(sa, np.repeat(pos.T[:, :, None], 3, axis=2))
        pygame.surfarray.blit_array(ss, np.repeat(neg.T[:, :, None], 3, axis=2))
        _GRAIN_S = (sa, ss)
    return _GRAIN_S

def grain():
    global _GRAIN
    if _GRAIN is None:
        g = value_noise_2d(CHUNK * TILE, CHUNK * TILE, 6, 99, 3)
        _GRAIN = ((g - 0.5) * 26).astype(np.int16)
    return _GRAIN

class Structure:
    __slots__ = ("idx", "kind", "tx", "ty", "tw", "th", "hp", "max_hp", "col", "roof", "height", "destroyed", "burn", "tag",
                 "flammable", "civil", "seed", "loot", "hit_t", "scale", "name")
    def __init__(self, kind, tx, ty, tw, th, hp, col=(200, 180, 140), roof=(170, 70, 50), height=60, tag=None, flammable=True, civil=True):
        self.idx = -1
        self.kind = kind
        self.tx, self.ty, self.tw, self.th = tx, ty, tw, th
        self.hp = hp
        self.max_hp = hp
        self.col = col
        self.roof = roof
        self.height = height
        self.destroyed = False
        self.burn = 0.0
        self.tag = tag
        self.flammable = flammable
        self.civil = civil
        self.seed = random.random()
        self.loot = None
        self.hit_t = 0.0
        self.scale = 1.0
        self.name = None

    def rect(self):
        return pygame.Rect(self.tx * TILE, self.ty * TILE, self.tw * TILE, self.th * TILE)

    def base_y(self):
        return (self.ty + self.th) * TILE

    def center(self):
        return V((self.tx + self.tw / 2) * TILE, (self.ty + self.th / 2) * TILE)

class IslandMap:
    def __init__(self, iid, isl, rng):
        self.iid = iid
        self.isl = isl
        self.theme = THEMES[isl['theme']]
        self.rng = rng
        self.w, self.h = isl['size']
        self.ground = np.zeros((self.h, self.w), np.int8)
        self.state = np.zeros((self.h, self.w), np.int8)
        self.timer = np.zeros((self.h, self.w), np.float32)
        self.occ = np.full((self.h, self.w), -1, np.int32)
        self.var = value_noise_2d(self.w, self.h, 5, rng.randint(0, 9999), 3)
        self.structs = []
        self.chunks = {}
        self.dirty = set()
        self.burning = set()
        self.timed = set()
        self.dock = None
        self.spawn = None
        self.ship_pos = None
        self.town_c = None
        self.landmark = None
        self.camps = []
        self.npc_spots = []
        self.mid_spots = []
        self.civil_destroyed = 0
        self.enemy_destroyed = 0
        self.generate()

    # ---------------- генерация ----------------
    def generate(self):
        w_, h_ = self.w, self.h
        rng = self.rng
        T = self.theme
        cx, cy = w_ / 2, h_ / 2 - 2
        n = value_noise_2d(w_, h_, 9, rng.randint(0, 9999), 4)
        yy, xx = np.mgrid[0:h_, 0:w_].astype(np.float32)
        if T.get('shipdeck'):
            ex = (xx - cx) / (w_ * 0.42)
            ey = (yy - cy) / (h_ * 0.26)
            d = np.sqrt(ex ** 2 + (ey / np.clip(1.15 - np.abs(ex) ** 2.2, 0.2, 1.2)) ** 2)
        elif T.get('deck'):
            d = np.maximum(np.abs(xx - cx) / (w_ * 0.36), np.abs(yy - cy) / (h_ * 0.30))
            d = d + (n - 0.5) * 0.05
        else:
            d = np.sqrt(((xx - cx) / (w_ * 0.44)) ** 2 + ((yy - cy) / (h_ * 0.42)) ** 2) + (n - 0.5) * 0.45
        g = np.full((h_, w_), G_DEEP, np.int8)
        g[d < 1.1] = G_SHALLOW
        g[d < 1.0] = G_SAND
        g[d < 0.9] = G_GRASS
        g[(d < 0.9) & (self.var > 0.55)] = G_GRASS2
        if T.get('deck'):
            g[d < 1.0] = G_DECK
            g[d >= 1.0] = G_DEEP
        self.ground = g
        self.land = (g >= G_SAND)
        # причал на юге
        dock_x = int(cx + rng.randint(-6, 6))
        y = h_ - 1
        while y > 0 and g[y, dock_x] < G_SAND:
            y -= 1
        land_y = y
        if not T.get('shipdeck'):
            for yy2 in range(land_y + 1, min(h_, land_y + 7)):
                for xx2 in (dock_x - 1, dock_x, dock_x + 1):
                    if 0 <= xx2 < w_:
                        g[yy2, xx2] = G_DECK
        self.dock = V((dock_x + 0.5) * TILE, (land_y + 6) * TILE)
        self.ship_pos = V((dock_x + 0.5) * TILE + 30, (land_y + 9) * TILE)
        self.spawn = V((dock_x + 0.5) * TILE, (land_y - 2) * TILE)
        # город
        tcx = int(lerp(dock_x, cx, 0.55))
        tcy = int(lerp(land_y, cy, 0.5))
        self.town_c = V((tcx + 0.5) * TILE, (tcy + 0.5) * TILE)
        # достопримечательность / арена босса — на севере
        lx, ly = int(cx + rng.randint(-5, 5)), int(cy - h_ * 0.24)
        self.landmark = V((lx + 0.5) * TILE, (ly + 0.5) * TILE)
        self.arena = V((lx + 0.5) * TILE, (ly + 6.0) * TILE)
        pl = T.get('plaza', (180, 170, 150))
        # дороги
        self._road(dock_x, land_y, tcx, tcy, 2)
        self._road(tcx, tcy, lx, ly + 6, 2)
        for _ in range(3):
            ex = rng.randint(6, w_ - 6)
            ey = rng.randint(6, h_ - 6)
            if self.land[ey, ex]:
                self._road(tcx, tcy, ex, ey, 1)
        self._disc(tcx, tcy, 5, G_PLAZA)
        self._disc(lx, ly + 5, 8, G_PLAZA)
        self._disc(dock_x, land_y - 2, 2, G_PATH)
        if T.get('canals'):
            for k in range(-2, 3):
                xx3 = tcx + k * 9
                for y3 in range(4, h_ - 4):
                    if 0 <= xx3 < w_ and self.land[y3, xx3] and abs(y3 - tcy) > 2 and abs(y3 - (ly + 5)) > 8:
                        g[y3, xx3] = G_SHALLOW if (y3 % 7) else G_DECK
        if T.get('split'):
            left = xx < cx
            mask = left & (g >= G_GRASS)
            g[mask] = G_GRASS2
            self.split_ice = (~left) & (g >= G_SAND)
        if T.get('ice_bay'):
            for y3 in range(land_y - 8, land_y + 6):
                for x3 in range(tcx - 14, tcx + 14):
                    if 0 <= y3 < h_ and 0 <= x3 < w_ and g[y3, x3] <= G_SHALLOW:
                        self.state[y3, x3] = S_ICE
        self.land = (g >= G_SAND)
        # постройки
        if not T.get('shipdeck'):
            self._place_landmark(lx, ly)
            self._place_town(tcx, tcy)
        else:
            self.spawn = V(cx * TILE, (cy + h_ * 0.12) * TILE)
            self.dock = V(-9999, -9999)
            for k in (-1, 0, 1):
                mx = int(cx + k * w_ * 0.25)
                my = int(cy)
                if self.free(mx, my, 1, 1, 0, True):
                    self.add_struct(Structure('pillar', mx, my, 1, 1, self._hp(900), (120, 85, 55), (150, 110, 70), 110, None, True, False))
        self._place_camps(dock_x, land_y)
        self._place_nature()
        if T.get('lava_spots') or T.get('split'):
            for _ in range(10):
                x3, y3 = rng.randint(4, w_ - 5), rng.randint(4, h_ - 5)
                if self.land[y3, x3] and self.occ[y3, x3] < 0 and (not T.get('split') or x3 < cx):
                    for dy in range(-1, 2):
                        for dx in range(-2, 3):
                            if self.land[y3 + dy, x3 + dx]:
                                self.state[y3 + dy, x3 + dx] = S_LAVA
        if T.get('split'):
            ys, xs = np.where(self.split_ice)
            self.state[ys, xs] = np.where(self.state[ys, xs] == S_NONE, S_ICE, self.state[ys, xs])

    def _road(self, x0, y0, x1, y1, wdt):
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for i in range(n + 1):
            t = i / max(1, n)
            x = int(round(lerp(x0, x1, t) + math.sin(t * 6 + x0) * 1.5))
            y = int(round(lerp(y0, y1, t)))
            for dy in range(-wdt // 2, wdt - wdt // 2):
                for dx in range(-wdt // 2, wdt - wdt // 2):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < self.h and 0 <= xx < self.w and self.ground[yy, xx] >= G_SAND and self.ground[yy, xx] != G_DECK:
                        self.ground[yy, xx] = G_PATH

    def _disc(self, cx, cy, r, gt):
        for y in range(cy - r, cy + r + 1):
            for x in range(cx - r - 2, cx + r + 3):
                if 0 <= y < self.h and 0 <= x < self.w and ((x - cx) / 1.3) ** 2 + (y - cy) ** 2 <= r * r and self.ground[y, x] >= G_SAND:
                    self.ground[y, x] = gt

    def free(self, tx, ty, tw, th, margin=1, allow_path=False):
        for y in range(ty - margin, ty + th + margin):
            for x in range(tx - margin, tx + tw + margin):
                if not (0 <= y < self.h and 0 <= x < self.w):
                    return False
                gt = self.ground[y, x]
                if gt < G_SAND or gt == G_DECK:
                    return False
                if not allow_path and gt in (G_PATH, G_PLAZA) and (ty <= y < ty + th and tx <= x < tx + tw):
                    return False
                if self.occ[y, x] >= 0:
                    return False
        return True

    def add_struct(self, s):
        s.idx = len(self.structs)
        self.structs.append(s)
        self.occ[s.ty:s.ty + s.th, s.tx:s.tx + s.tw] = s.idx
        return s

    def _hp(self, base):
        return base * (1 + self.isl['lvl'] * 0.12)

    def _place_landmark(self, lx, ly):
        T = self.theme
        rng = self.rng
        big = T.get('big')
        enemy_owned = True
        if T.get('castle'):
            s = Structure('castle', lx - 4, ly - 4, 8, 5, self._hp(5000), (230, 225, 215), (60, 60, 70), 160, 'landmark', True, False)
        elif T.get('palace'):
            s = Structure('palace', lx - 5, ly - 3, 10, 4, self._hp(5000), (240, 225, 190), (220, 190, 120), 120, 'landmark', False, False)
        elif T.get('fort'):
            s = Structure('fort', lx - 5, ly - 3, 10, 4, self._hp(6000), T['bld'][0], T['roof'][0], 130, 'landmark', False, False)
            for k in range(-7, 8):
                for (x, y) in ((lx + k, ly + 2), (lx - 7, ly + 2 - abs(k) // 3)):
                    pass
        elif T.get('colosseum'):
            s = Structure('colosseum', lx - 5, ly - 4, 10, 4, self._hp(6000), (210, 180, 130), (180, 150, 100), 110, 'landmark', False, False)
        elif T.get('ruins'):
            s = Structure('ruin', lx - 4, ly - 3, 8, 3, self._hp(3500), (200, 190, 160), (160, 150, 120), 90, 'landmark', False, False)
        else:
            col = T['bld'][0]
            s = Structure('hall', lx - 4, ly - 3, 8, 4, self._hp(4000), col, T['roof'][0], 110 if not big else 160, 'landmark', True, False)
        if self.free(s.tx, s.ty, s.tw, s.th, 0, True):
            self.add_struct(s)
        # колонны у арены
        for k in range(6):
            a = k / 6 * math.pi * 2
            x = int(lx + math.cos(a) * 10)
            y = int(ly + 5 + math.sin(a) * 6)
            if self.free(x, y, 1, 1, 0):
                self.add_struct(Structure('pillar', x, y, 1, 1, self._hp(500), (220, 215, 205), (240, 235, 225), 70, None, False, False))

    def _place_town(self, tcx, tcy):
        T = self.theme
        rng = self.rng
        dens = T.get('town', 0.4)
        big = T.get('big')
        n = int(12 + dens * 30)
        placed = 0
        tries = 0
        while placed < n and tries < 800:
            tries += 1
            r = rng.uniform(5, 6 + dens * 18)
            a = rng.uniform(0, 6.28)
            tw = rng.choice([3, 3, 4, 2]) + (1 if big else 0)
            th = rng.choice([2, 2, 3]) + (1 if big else 0)
            tx = int(tcx + math.cos(a) * r * 1.3) - tw // 2
            ty = int(tcy + math.sin(a) * r) - th // 2
            if not self.free(tx, ty, tw, th, 2 if not big else 2):
                continue
            col = rng.choice(T['bld'])
            roof = rng.choice(T['roof'])
            kind = 'house'
            if rng.random() < 0.12 and not T.get('deck'):
                kind = 'tower'
                tw, th = 2, 2
            hgt = (50 + 15 * th + (60 if kind == 'tower' else 0)) * (1.4 if big else 1.0)
            s = Structure(kind, tx, ty, tw, th, self._hp(320 + 80 * tw * th), col, roof, hgt, None, True, True)
            self.add_struct(s)
            placed += 1
            if rng.random() < 0.3:
                ex, ey = tx + tw, ty + th
                if self.free(ex, ey, 1, 1, 0):
                    self.add_struct(Structure(rng.choice(['crate', 'barrel']), ex, ey, 1, 1, self._hp(30), (160, 110, 60), (130, 90, 50), 26, None, True, True))
        # места для NPC вокруг площади
        for k in range(10):
            a = k / 10 * 6.28
            p = V((tcx + math.cos(a) * 4 * 1.3 + 0.5) * TILE, (tcy + math.sin(a) * 3.2 + 0.5) * TILE)
            self.npc_spots.append(p)
        # бочки с водой (против песчаной логии и огня)
        for _ in range(4):
            for _t in range(30):
                x = tcx + rng.randint(-8, 8)
                y = tcy + rng.randint(-6, 6)
                if self.free(x, y, 1, 1, 0, True) and self.ground[y, x] in (G_PATH, G_PLAZA):
                    s = Structure('water_barrel', x, y, 1, 1, self._hp(60), (90, 140, 200), (120, 90, 60), 28, 'water', False, True)
                    self.add_struct(s)
                    break

    def _place_camps(self, dock_x, land_y):
        rng = self.rng
        groups = max(1, self.isl.get('groups', 6))
        tries = 0
        while len(self.camps) < groups + 4 and tries < 600:
            tries += 1
            x = rng.randint(5, self.w - 6)
            y = rng.randint(5, self.h - 6)
            if not self.land[y, x] or self.occ[y, x] >= 0:
                continue
            p = V((x + 0.5) * TILE, (y + 0.5) * TILE)
            if dist(p, self.spawn) < (12 if not self.theme.get('shipdeck') else 6) * TILE:
                continue
            if dist(p, self.landmark) < 9 * TILE:
                continue
            if any(dist(p, c) < 8 * TILE for c in self.camps):
                continue
            self.camps.append(p)
            for _ in range(rng.randint(1, 3)):
                ex, ey = x + rng.randint(-3, 3), y + rng.randint(-3, 3)
                k = rng.choice(['crate', 'barrel', 'tent', 'crate'] if not self.theme.get('shipdeck') else ['crate', 'barrel'])
                tw = 2 if k == 'tent' else 1
                if self.free(ex, ey, tw, tw, 0):
                    s = Structure(k, ex, ey, tw, tw, self._hp(40 if k != 'tent' else 120), (160, 110, 60) if k != 'tent' else (200, 190, 160),
                                  (130, 90, 50) if k != 'tent' else (170, 60, 50), 26 if k != 'tent' else 50, 'enemy', True, False)
                    if rng.random() < 0.4:
                        s.loot = 'beli'
                    self.add_struct(s)
        # средние боссы — у отдельных точек
        self.mid_spots = list(self.camps[-3:]) if len(self.camps) > 3 else list(self.camps)
        self.camps = self.camps[:groups] if len(self.camps) > groups else self.camps
        # сундук
        for _ in range(200):
            x = rng.randint(4, self.w - 5)
            y = rng.randint(4, self.h - 5)
            if self.free(x, y, 1, 1, 1) and dist(V(x * TILE, y * TILE), self.spawn) > 15 * TILE:
                s = Structure('chest', x, y, 1, 1, 99999, (200, 150, 60), (240, 200, 80), 24, 'chest', False, False)
                self.add_struct(s)
                break

    def _place_nature(self):
        T = self.theme
        rng = self.rng
        dens = T.get('density', 0.3)
        kind = T.get('trees')
        if not kind:
            return
        n = int(self.w * self.h * dens * 0.05)
        for _ in range(n * 3):
            if n <= 0:
                break
            x = rng.randint(1, self.w - 2)
            y = rng.randint(1, self.h - 2)
            gt = self.ground[y, x]
            if gt not in (G_GRASS, G_GRASS2, G_SAND) or self.occ[y, x] >= 0:
                continue
            if gt == G_SAND and kind not in ('palm', 'cactus'):
                continue
            p = V(x * TILE, y * TILE)
            if dist(p, self.spawn) < 3 * TILE or dist(p, self.town_c) < 4 * TILE:
                continue
            big = kind in ('giant', 'mangrove')
            tw = 2 if big else 1
            if not self.free(x, y, tw, tw, 1 if gt != G_SAND else 0):
                continue
            hgt = {'giant': 200, 'mangrove': 160, 'palm': 90, 'pine': 90, 'jungle': 100, 'leafy': 80, 'cactus': 50, 'dead': 70,
                   'coral': 60, 'candy': 70, 'sakura': 80, 'tech': 80, 'orange': 60}.get(kind, 80)
            s = Structure('tree', x, y, tw, tw, self._hp(70 if not big else 600), (110, 80, 50), (60, 140, 60), hgt, kind,
                          kind not in ('coral', 'tech', 'cactus'), False)
            s.scale = rng.uniform(0.85, 1.25)
            self.add_struct(s)
            n -= 1
        for _ in range(int(self.w * self.h * 0.004)):
            x = rng.randint(1, self.w - 3)
            y = rng.randint(1, self.h - 3)
            if self.free(x, y, 1, 1, 0) and dist(V(x * TILE, y * TILE), self.spawn) > 3 * TILE:
                self.add_struct(Structure('rock', x, y, 1, 1, self._hp(260), (140, 135, 130), (170, 165, 160), 30, None, False, False))

    # ---------------- запросы ----------------
    def tile(self, x, y):
        tx, ty = int(x // TILE), int(y // TILE)
        if 0 <= tx < self.w and 0 <= ty < self.h:
            return tx, ty
        return None

    def is_water(self, x, y):
        t = self.tile(x, y)
        if t is None:
            return True
        tx, ty = t
        return self.ground[ty, tx] == G_DEEP and self.state[ty, tx] != S_ICE

    def walkable(self, x, y):
        t = self.tile(x, y)
        if t is None:
            return False
        return self.occ[t[1], t[0]] < 0

    def struct_at(self, x, y):
        t = self.tile(x, y)
        if t is None:
            return None
        i = self.occ[t[1], t[0]]
        return self.structs[i] if i >= 0 else None

    # ---------------- рендер земли ----------------
    def colmap(self):
        cm = getattr(self, '_colmap', None)
        if cm is None:
            cm = np.zeros((self.h, self.w, 3), np.uint8)
            for ty in range(self.h):
                for tx in range(self.w):
                    cm[ty, tx] = self.tile_color(tx, ty)
            self._colmap = cm
        return cm

    def tile_color(self, tx, ty):
        T = self.theme
        gt = self.ground[ty, tx]
        st = self.state[ty, tx]
        v = self.var[ty, tx]
        if gt == G_DEEP:
            c = T['water']
            c = mul_col(c, 0.85 + 0.1 * v)
        elif gt == G_SHALLOW:
            c = lerp_col(T['water'], T['sand'], 0.35)
        elif gt == G_SAND:
            c = T['sand']
        elif gt == G_GRASS:
            c = T['ground']
        elif gt == G_GRASS2:
            c = T['ground2']
        elif gt == G_PATH:
            c = T['path']
        elif gt == G_PLAZA:
            c = T['plaza']
        elif gt == G_DECK:
            c = (150, 105, 65)
        else:
            c = (128, 128, 128)
        c = mul_col(c, 0.92 + 0.16 * v)
        if st == S_SCORCH or st == S_BURN:
            c = lerp_col(c, (40, 32, 30), 0.82)
        elif st == S_ICE:
            c = lerp_col(c, (200, 235, 255), 0.75)
        elif st == S_LAVA:
            c = (200 + int(40 * v), 60 + int(30 * v), 20)
        elif st == S_CRATER:
            c = lerp_col(c, (70, 60, 55), 0.55)
        elif st == S_DRY:
            c = lerp_col(c, (215, 185, 120), 0.8)
        elif st == S_POISON:
            c = lerp_col(c, (120, 50, 140), 0.6)
        elif st == S_RUBBLE:
            c = lerp_col(c, (120, 110, 100), 0.6)
        return c

    def render_chunk(self, cx, cy):
        x0, y0 = cx * CHUNK, cy * CHUNK
        tw = min(CHUNK, self.w - x0)
        th = min(CHUNK, self.h - y0)
        surf = pygame.Surface((CHUNK * TILE, CHUNK * TILE))
        if tw <= 0 or th <= 0:
            return surf
        water = self.theme['water']
        n = CHUNK + 2
        cols = np.zeros((n, n, 3), np.uint8)
        cols[:, :] = water
        cm = self.colmap()
        gx0, gy0 = max(0, x0 - 1), max(0, y0 - 1)
        gx1, gy1 = min(self.w, x0 + CHUNK + 1), min(self.h, y0 + CHUNK + 1)
        cols[gx0 - (x0 - 1):gx1 - (x0 - 1), gy0 - (y0 - 1):gy1 - (y0 - 1)] = cm[gy0:gy1, gx0:gx1].transpose(1, 0, 2)
        small = pygame.Surface((n, n))
        pygame.surfarray.blit_array(small, cols)
        smooth = pygame.transform.smoothscale(small, (n * TILE, n * TILE))
        sharp = pygame.transform.scale(small, (n * TILE, n * TILE))
        surf.blit(smooth, (-TILE, -TILE))
        sharp.set_alpha(95)
        surf.blit(sharp, (-TILE, -TILE))
        ga, gs = grain_surfs()
        surf.blit(ga, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(gs, (0, 0), special_flags=pygame.BLEND_RGB_SUB)
        # детали
        T = self.theme
        for ty in range(th):
            for tx in range(tw):
                gx, gy = x0 + tx, y0 + ty
                gt = self.ground[gy, gx]
                st = self.state[gy, gx]
                px, py = tx * TILE, ty * TILE
                h_ = (gx * 73856093 ^ gy * 19349663) & 0xffff
                if gt in (G_GRASS, G_GRASS2) and st == S_NONE and h_ % 5 == 0:
                    c = mul_col(T['ground'], 0.75)
                    bx, by = px + h_ % 30 + 5, py + (h_ >> 5) % 30 + 5
                    pygame.draw.line(surf, c, (bx, by), (bx - 3, by - 6), 2)
                    pygame.draw.line(surf, c, (bx, by), (bx + 3, by - 7), 2)
                    if h_ % 35 == 0:
                        pygame.draw.circle(surf, random.choice([(250, 240, 120), (255, 160, 200), (255, 255, 255)]), (bx + 6, by - 4), 3)
                elif gt == G_DECK:
                    pygame.draw.line(surf, (110, 75, 45), (px, py + 13), (px + TILE, py + 13), 1)
                    pygame.draw.line(surf, (110, 75, 45), (px, py + 27), (px + TILE, py + 27), 1)
                elif gt in (G_PATH, G_PLAZA) and h_ % 3 == 0 and st == S_NONE:
                    pygame.draw.ellipse(surf, mul_col(T['path'] if gt == G_PATH else T['plaza'], 0.88), (px + h_ % 20, py + (h_ >> 4) % 22, 14, 9), 1)
                elif gt == G_DEEP and h_ % 7 == 0:
                    pygame.draw.arc(surf, lerp_col(water, (255, 255, 255), 0.25), (px + h_ % 18, py + (h_ >> 3) % 20, 18, 8), 0.3, 2.8, 2)
                if gt == G_SAND and gy > 0 and self.ground[gy - 1, gx] >= G_GRASS:
                    pass
                if st == S_CRATER and h_ % 2 == 0:
                    pygame.draw.line(surf, (40, 34, 30), (px + 5, py + 8 + h_ % 10), (px + 30, py + 20 + h_ % 12), 2)
                elif st == S_ICE and h_ % 3 == 0:
                    pygame.draw.line(surf, (255, 255, 255), (px + 6, py + 30), (px + 18, py + 10), 2)
                elif st == S_RUBBLE:
                    for k in range(3):
                        pygame.draw.rect(surf, (110 + k * 15, 100 + k * 10, 90), (px + (h_ >> k) % 28, py + (h_ >> (k + 3)) % 28, 9, 7))
                elif st == S_SCORCH and h_ % 4 == 0:
                    pygame.draw.circle(surf, (25, 20, 20), (px + h_ % 30 + 5, py + (h_ >> 4) % 30 + 5), 4)
                # линия прибоя
                if gt == G_SHALLOW and h_ % 3 == 0:
                    pygame.draw.arc(surf, (235, 245, 250), (px + h_ % 14, py + (h_ >> 4) % 18, 22, 10), 0.2, 2.9, 2)
        return surf

    def get_chunk(self, cx, cy):
        key = (cx, cy)
        if key in self.dirty or key not in self.chunks:
            self.chunks[key] = self.render_chunk(cx, cy)
            self.dirty.discard(key)
        return self.chunks[key]

    def mark(self, tx, ty):
        self.dirty.add((tx // CHUNK, ty // CHUNK))

    def draw_ground(self, surf, ox, oy, max_rerender=3):
        vw, vh = surf.get_size()
        cs = CHUNK * TILE
        c0x, c0y = int(ox // cs), int(oy // cs)
        c1x, c1y = int((ox + vw) // cs), int((oy + vh) // cs)
        redraws = 0
        surf.fill(self.theme['water'])
        for cy in range(c0y, c1y + 1):
            for cx in range(c0x, c1x + 1):
                if cx < 0 or cy < 0 or cx * CHUNK >= self.w or cy * CHUNK >= self.h:
                    continue
                key = (cx, cy)
                if (key in self.dirty and redraws < max_rerender) or key not in self.chunks:
                    self.chunks[key] = self.render_chunk(cx, cy)
                    self.dirty.discard(key)
                    redraws += 1
                surf.blit(self.chunks[key], (cx * cs - ox, cy * cs - oy))

    # ---------------- эффекты земли ----------------
    def set_state(self, tx, ty, st, t=0.0):
        if not (0 <= tx < self.w and 0 <= ty < self.h):
            return
        cur = self.state[ty, tx]
        if cur == st:
            if t:
                self.timer[ty, tx] = max(self.timer[ty, tx], t)
            return
        self.state[ty, tx] = st
        self.timer[ty, tx] = t
        if getattr(self, '_colmap', None) is not None:
            self._colmap[ty, tx] = self.tile_color(tx, ty)
        if st == S_BURN:
            self.burning.add((tx, ty))
        else:
            self.burning.discard((tx, ty))
        if t > 0:
            self.timed.add((tx, ty))
        self.mark(tx, ty)

    def terrain_effect(self, pos, r, kind):
        cx, cy = int(pos.x // TILE), int(pos.y // TILE)
        rt = int(r // TILE) + 1
        for ty in range(cy - rt, cy + rt + 1):
            for tx in range(cx - rt, cx + rt + 1):
                if not (0 <= tx < self.w and 0 <= ty < self.h):
                    continue
                if (tx - cx) ** 2 + (ty - cy) ** 2 > rt * rt:
                    continue
                gt = self.ground[ty, tx]
                st = self.state[ty, tx]
                if kind == 'fire':
                    if gt in FLAMMABLE and st in (S_NONE, S_DRY) and self.occ[ty, tx] < 0 or (gt in FLAMMABLE and st == S_NONE):
                        self.set_state(tx, ty, S_BURN, random.uniform(3, 6))
                    elif gt >= G_SAND and st == S_ICE:
                        self.set_state(tx, ty, S_NONE)
                elif kind == 'ice':
                    if gt <= G_SHALLOW or st in (S_NONE, S_BURN, S_LAVA, S_DRY, S_SCORCH):
                        self.set_state(tx, ty, S_ICE, random.uniform(25, 40))
                elif kind == 'lava':
                    if gt >= G_SAND and st != S_LAVA:
                        self.set_state(tx, ty, S_LAVA, random.uniform(12, 20))
                    elif gt <= G_SHALLOW and st == S_ICE:
                        self.set_state(tx, ty, S_NONE)
                elif kind == 'scorch':
                    if gt >= G_SAND and st == S_NONE:
                        self.set_state(tx, ty, S_SCORCH)
                elif kind == 'crater':
                    if gt >= G_SAND and st in (S_NONE, S_DRY):
                        self.set_state(tx, ty, S_CRATER)
                elif kind == 'sand':
                    if gt >= G_GRASS and st == S_NONE:
                        self.set_state(tx, ty, S_DRY)
                elif kind == 'poison':
                    if gt >= G_SAND and st in (S_NONE,):
                        self.set_state(tx, ty, S_POISON, 10)

    def update(self, dt, scene):
        # таймеры
        if self.timed:
            done = []
            for (tx, ty) in list(self.timed):
                self.timer[ty, tx] -= dt
                if self.timer[ty, tx] <= 0:
                    done.append((tx, ty))
            for (tx, ty) in done:
                self.timed.discard((tx, ty))
                st = self.state[ty, tx]
                if st == S_BURN:
                    self.set_state(tx, ty, S_SCORCH)
                elif st == S_LAVA:
                    self.set_state(tx, ty, S_CRATER)
                else:
                    self.set_state(tx, ty, S_NONE)
        # распространение огня
        self.spread_t = getattr(self, 'spread_t', 0) - dt
        if self.spread_t <= 0 and self.burning:
            self.spread_t = 0.3
            lst = list(self.burning)
            if len(lst) > 500:
                lst = random.sample(lst, 500)
            for (tx, ty) in lst:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = tx + dx, ty + dy
                    if 0 <= nx < self.w and 0 <= ny < self.h and random.random() < 0.09:
                        if self.ground[ny, nx] in FLAMMABLE and self.state[ny, nx] == S_NONE and len(self.burning) < 900:
                            self.set_state(nx, ny, S_BURN, random.uniform(3, 6))
                        si = self.occ[ny, nx]
                        if si >= 0:
                            s = self.structs[si]
                            if s.flammable and not s.destroyed and s.burn <= 0 and random.random() < 0.25:
                                s.burn = random.uniform(6, 12)

    def draw_fire_overlay(self, surf, ox, oy, particles, dt):
        vw, vh = surf.get_size()
        for (tx, ty) in self.burning:
            x = tx * TILE - ox
            y = ty * TILE - oy
            if -40 < x < vw and -40 < y < vh:
                if random.random() < dt * 5:
                    particles.add(tx * TILE + random.uniform(4, 36), ty * TILE + random.uniform(4, 36), random.uniform(-10, 10), -70, 0.6, 9, (255, 130, 30), 'fire')
                if random.random() < dt * 1.2:
                    particles.add(tx * TILE + 20, ty * TILE + 10, 0, -40, 1.6, 12, (60, 55, 55), 'smoke', grow=18)
        # лава светится
        for (tx, ty) in self.timed:
            if self.state[ty, tx] == S_LAVA:
                x = tx * TILE - ox + 20
                y = ty * TILE - oy + 20
                if -40 < x < vw + 40 and -40 < y < vh + 40 and random.random() < dt * 2:
                    particles.add(tx * TILE + random.uniform(4, 36), ty * TILE + random.uniform(4, 36), 0, -40, 0.7, 7, (255, 120, 30), 'fire')

# ------------------------------------------------------------------
#  ОТРИСОВКА ПОСТРОЕК
# ------------------------------------------------------------------
def draw_structure(surf, s, ox, oy, theme, t):
    r = s.rect()
    x, y = r.x - ox, r.y - oy
    w_, h_ = r.w, r.h
    if x > surf.get_width() + 50 or y > surf.get_height() + 250 or x + w_ < -50 or y + h_ < -50:
        return
    shake = 0
    if s.hit_t > 0:
        shake = random.uniform(-3, 3)
    x += shake
    k = s.kind
    dmgf = 1 - s.hp / s.max_hp if s.max_hp < 90000 else 0
    if k in ('house', 'tower', 'hall', 'fort', 'palace', 'castle', 'colosseum', 'ruin'):
        H = s.height
        wall = s.col
        front = pygame.Rect(x, y + h_ - H * 0.55, w_, H * 0.55)
        top = pygame.Rect(x, y + h_ - H * 0.55 - h_ * 0.8, w_, h_ * 0.8 + 4)
        sh = shadow_surf(w_ + 20, 22, 70)
        surf.blit(sh, (x - 10, y + h_ - 12))
        orect(surf, mul_col(wall, 0.82), front, 2, radius=2)
        if k == 'castle':
            for i in range(3):
                rr = pygame.Rect(x + w_ * 0.1 + i * w_ * 0.05, top.y - i * 34, w_ * (0.8 - i * 0.1), 36)
                orect(surf, wall, rr, 2, radius=2)
                pts = [(rr.x - 14, rr.y + 6), (rr.right + 14, rr.y + 6), (rr.right - 6, rr.y - 14), (rr.x + 6, rr.y - 14)]
                opoly(surf, s.roof, [(int(a), int(b)) for a, b in pts], 2)
        elif k == 'colosseum':
            pygame.draw.ellipse(surf, (20, 14, 18), top.inflate(10, 30))
            pygame.draw.ellipse(surf, wall, top.inflate(6, 26))
            pygame.draw.ellipse(surf, mul_col(wall, 0.7), top.inflate(-w_ * 0.3, -top.h * 0.2))
            for i in range(12):
                a = i / 12 * 6.28
                px_ = top.centerx + math.cos(a) * w_ * 0.45
                py_ = top.centery + math.sin(a) * top.h * 0.6
                pygame.draw.line(surf, mul_col(wall, 0.6), (px_, py_), (px_, py_ + 30), 3)
        else:
            orect(surf, s.roof if k != 'ruin' else wall, top, 2, radius=4)
            if k in ('house', 'hall', 'tower'):
                pygame.draw.line(surf, mul_col(s.roof, 0.75), (top.x + 6, top.centery), (top.right - 6, top.centery), 3)
                for i in range(1, max(2, int(w_ / 26))):
                    xx = top.x + i * w_ / max(2, int(w_ / 26))
                    pygame.draw.line(surf, mul_col(s.roof, 0.88), (xx, top.y + 3), (xx, top.bottom - 3), 1)
            if k == 'palace':
                for i in range(3):
                    cx_ = top.x + w_ * (0.2 + i * 0.3)
                    ocircle(surf, (230, 200, 120), (cx_, top.y), 18, 2)
                    pygame.draw.line(surf, (240, 220, 140), (cx_, top.y - 18), (cx_, top.y - 34), 3)
            if k == 'fort':
                for i in range(int(w_ / 20)):
                    pygame.draw.rect(surf, mul_col(wall, 0.9), (top.x + i * 20, top.y - 10, 12, 12))
                draw_text(surf, "MARINE" if theme.get('roof', [(0, 0, 0)])[0] == (70, 110, 190) else "", (top.centerx, top.centery), 22, (60, 90, 170), "center", 0)
            if k == 'tower':
                pts = [(top.x - 4, top.y + 8), (top.right + 4, top.y + 8), (top.centerx, top.y - 40)]
                opoly(surf, s.roof, [(int(a), int(b)) for a, b in pts], 2)
        # окна / дверь
        if k != 'ruin':
            nwin = max(1, int(w_ / 34))
            for i in range(nwin):
                wx = front.x + (i + 0.5) * w_ / nwin - 7
                wy = front.y + 10
                lit = (255, 230, 150) if (int(s.seed * 100) + i) % 3 == 0 else (90, 110, 140)
                pygame.draw.rect(surf, (40, 30, 30), (wx - 1, wy - 1, 16, 14))
                pygame.draw.rect(surf, lit, (wx, wy, 14, 12))
            dx_ = front.centerx - 9
            pygame.draw.rect(surf, (40, 30, 30), (dx_ - 1, front.bottom - 25, 20, 25))
            pygame.draw.rect(surf, mul_col(wall, 0.5), (dx_, front.bottom - 24, 18, 24))
        else:
            for i in range(3):
                pygame.draw.line(surf, (60, 55, 50), (front.x + i * w_ / 3 + 10, front.y), (front.x + i * w_ / 3 + 22, front.bottom), 2)
        if dmgf > 0.25:
            for i in range(int(dmgf * 6)):
                a = s.seed * 10 + i
                cx_ = front.x + (math.sin(a * 3.1) * 0.5 + 0.5) * w_
                cy_ = front.y + (math.cos(a * 2.3) * 0.5 + 0.5) * front.h
                pygame.draw.lines(surf, (30, 25, 25), False, [(cx_, cy_), (cx_ + 8, cy_ + 6), (cx_ + 4, cy_ + 14), (cx_ + 12, cy_ + 20)], 2)
    elif k == 'tree':
        kind = s.tag
        sc = s.scale
        bx = x + w_ / 2
        by = y + h_ - 6
        sh = shadow_surf(46 * sc * (s.tw), 16 * sc, 70)
        surf.blit(sh, (bx - sh.get_width() / 2, by - 6))
        burnt = s.burn > 0 or dmgf > 0.7
        if kind == 'palm':
            pygame.draw.line(surf, (20, 14, 18), (bx, by), (bx + 10 * sc, by - 70 * sc), 9)
            pygame.draw.line(surf, (150, 110, 70), (bx, by), (bx + 10 * sc, by - 70 * sc), 6)
            top = (bx + 10 * sc, by - 70 * sc)
            for i in range(6):
                a = i / 6 * 6.28 + 0.3
                e = (top[0] + math.cos(a) * 36 * sc, top[1] + math.sin(a) * 18 * sc + 10)
                pygame.draw.line(surf, (20, 14, 18), top, e, 9)
                pygame.draw.line(surf, (60, 150, 60) if not burnt else (60, 40, 30), top, e, 6)
        elif kind == 'cactus':
            orect(surf, (70, 140, 70), (bx - 7, by - 46 * sc, 14, 46 * sc), 2, radius=6)
            orect(surf, (70, 140, 70), (bx - 20, by - 34 * sc, 10, 18), 2, radius=5)
            orect(surf, (70, 140, 70), (bx + 10, by - 40 * sc, 10, 20), 2, radius=5)
        elif kind == 'pine':
            pygame.draw.rect(surf, (90, 60, 40), (bx - 4, by - 18, 8, 18))
            for i in range(3):
                ww = (34 - i * 8) * sc
                yy = by - 14 - i * 20 * sc
                opoly(surf, (40, 100, 60) if not burnt else (50, 40, 35), [(int(bx - ww), int(yy)), (int(bx + ww), int(yy)), (int(bx), int(yy - 34 * sc))], 2)
                if theme.get('ground', (0, 0, 0))[0] > 220:
                    pygame.draw.polygon(surf, (245, 250, 255), [(bx - ww * 0.5, yy - 17 * sc), (bx + ww * 0.5, yy - 17 * sc), (bx, yy - 34 * sc)])
        elif kind == 'coral':
            for i in range(5):
                a = -math.pi / 2 + (i - 2) * 0.35
                e = (bx + math.cos(a) * 44 * sc, by + math.sin(a) * 44 * sc)
                oline(surf, (240, 120, 150) if i % 2 else (250, 170, 90), (bx, by), e, 6, 2)
        elif kind == 'candy':
            pygame.draw.line(surf, (20, 14, 18), (bx, by), (bx, by - 50 * sc), 7)
            pygame.draw.line(surf, (250, 250, 250), (bx, by), (bx, by - 50 * sc), 4)
            ocircle(surf, (250, 120, 170), (bx, by - 60 * sc), 20 * sc, 2)
            pygame.draw.arc(surf, (255, 255, 255), (bx - 14 * sc, by - 74 * sc, 28 * sc, 28 * sc), 0, 4, 3)
        elif kind == 'tech':
            orect(surf, (200, 210, 230), (bx - 6, by - 60 * sc, 12, 60 * sc), 2, radius=3)
            ocircle(surf, (120, 220, 255), (bx, by - 64 * sc), 9, 2)
            draw_glow(surf, (bx, by - 64 * sc), 18, (120, 220, 255), 0.5 + 0.3 * math.sin(t * 3 + s.seed * 10))
        elif kind == 'mangrove':
            for i in range(5):
                a = math.pi * (0.1 + 0.2 * i)
                pygame.draw.line(surf, (110, 80, 55), (bx, by - 60 * sc), (bx + math.cos(a) * 40 * sc, by + 6), 6)
            orect(surf, (130, 95, 60), (bx - 14 * sc, by - 140 * sc, 28 * sc, 90 * sc), 2, radius=8)
            ocircle(surf, (90, 160, 80), (bx, by - 150 * sc), 46 * sc, 3)
            ocircle(surf, (110, 180, 95), (bx - 20 * sc, by - 160 * sc), 26 * sc, 2)
            draw_text(surf, str(int(s.seed * 79) + 1), (bx, by - 95 * sc), 16, (250, 250, 240), "center", 2)
        else:
            col = {'leafy': (70, 150, 70), 'jungle': (40, 120, 50), 'dead': (90, 80, 70), 'sakura': (250, 170, 200), 'orange': (80, 150, 70),
                   'giant': (60, 130, 60)}.get(kind, (70, 150, 70))
            if burnt:
                col = (50, 40, 35)
            trunk_h = (30 if kind != 'giant' else 90) * sc
            pygame.draw.rect(surf, (20, 14, 18), (bx - 6 * sc - 2, by - trunk_h, 12 * sc + 4, trunk_h))
            pygame.draw.rect(surf, (110, 75, 45), (bx - 6 * sc, by - trunk_h, 12 * sc, trunk_h))
            R = (26 if kind != 'giant' else 70) * sc
            if kind == 'dead':
                for i in range(4):
                    a = -math.pi / 2 + (i - 1.5) * 0.5
                    pygame.draw.line(surf, (70, 60, 50), (bx, by - trunk_h), (bx + math.cos(a) * R, by - trunk_h + math.sin(a) * R), 4)
            else:
                ocircle(surf, mul_col(col, 0.85), (bx, by - trunk_h - R * 0.6), R, 3)
                ocircle(surf, col, (bx - R * 0.4, by - trunk_h - R * 0.9), R * 0.65, 2)
                ocircle(surf, add_col(col, 15), (bx + R * 0.35, by - trunk_h - R * 1.05), R * 0.55, 2)
                if kind == 'orange' and not burnt:
                    for i in range(5):
                        pygame.draw.circle(surf, (255, 150, 40), (int(bx + math.sin(i * 2.4 + s.seed) * R * 0.7), int(by - trunk_h - R * 0.7 + math.cos(i * 1.7) * R * 0.5)), 4)
        if s.burn > 0:
            draw_glow(surf, (bx, by - 40), 40, (255, 120, 30), 0.6)
    elif k == 'rock':
        bx, by = x + w_ / 2, y + h_ / 2
        pts = star_points(bx, by - 8, 20, 16, 5, s.seed * 6)
        opoly(surf, s.col, [(int(a), int(b)) for a, b in pts], 2)
        pygame.draw.line(surf, add_col(s.col, 30), (bx - 8, by - 16), (bx + 4, by - 20), 3)
    elif k in ('crate', 'barrel', 'water_barrel'):
        bx, by = x + w_ / 2, y + h_ / 2
        if k == 'crate':
            orect(surf, (170, 120, 70), (bx - 15, by - 22, 30, 30), 2, radius=2)
            pygame.draw.line(surf, (110, 75, 45), (bx - 13, by - 20), (bx + 13, by + 6), 2)
            pygame.draw.line(surf, (110, 75, 45), (bx + 13, by - 20), (bx - 13, by + 6), 2)
        else:
            col = (140, 95, 55) if k == 'barrel' else (100, 130, 190)
            oellipse(surf, col, (bx - 13, by - 22, 26, 32), 2)
            pygame.draw.line(surf, (60, 50, 50), (bx - 12, by - 12), (bx + 12, by - 12), 2)
            pygame.draw.line(surf, (60, 50, 50), (bx - 12, by), (bx + 12, by), 2)
            if k == 'water_barrel':
                draw_text(surf, "ВОДА", (bx, by - 30), 11, (220, 240, 255), "center", 2)
    elif k == 'tent':
        pts = [(x + 4, y + h_ - 4), (x + w_ / 2, y + 2 - 20), (x + w_ - 4, y + h_ - 4)]
        opoly(surf, s.roof, [(int(a), int(b)) for a, b in pts], 2)
        pygame.draw.polygon(surf, (40, 30, 30), [(x + w_ / 2 - 8, y + h_ - 4), (x + w_ / 2, y + h_ - 30), (x + w_ / 2 + 8, y + h_ - 4)])
    elif k == 'pillar':
        bx, by = x + w_ / 2, y + h_ - 6
        orect(surf, s.col, (bx - 10, by - s.height, 20, s.height), 2, radius=3)
        orect(surf, s.roof, (bx - 14, by - s.height - 8, 28, 10), 2, radius=2)
    elif k == 'chest':
        bx, by = x + w_ / 2, y + h_ / 2
        orect(surf, (150, 90, 40), (bx - 16, by - 16, 32, 22), 2, radius=3)
        orect(surf, (190, 120, 50), (bx - 16, by - 22, 32, 10), 2, radius=4)
        pygame.draw.rect(surf, (250, 210, 70), (bx - 4, by - 14, 8, 8))
        draw_glow(surf, (bx, by - 10), 30, (255, 210, 80), 0.35 + 0.2 * math.sin(t * 4))
    if s.burn > 0 and k not in ('tree',):
        r2 = s.rect()
        for i in range(max(1, s.tw)):
            fx = r2.x - ox + (i + 0.5) * r2.w / max(1, s.tw)
            fy = r2.y - oy + r2.h - s.height * 0.6
            draw_glow(surf, (fx, fy), 34, (255, 120, 30), 0.7)

# ==================================================================
#  СЦЕНА ОСТРОВА
# ==================================================================
def stable_seed(s):
    h = 2166136261
    for ch in s:
        h = ((h ^ ord(ch)) * 16777619) & 0xffffffff
    return h

class NPC:
    def __init__(self, scene, pos, app, role, name, data=None):
        self.scene = scene
        self.pos = V(pos)
        self.home = V(pos)
        self.app = app
        self.role = role
        self.name = name
        self.data = data
        self.facing = math.pi / 2
        self.phase = random.uniform(0, 6)
        self.walk = 0
        self.target = None
        self.wait = random.uniform(0, 3)
        self.panic = 0.0
        self.hurt = 0.0
        self.alive = True

    def update(self, dt):
        self.phase += dt * (3 + self.walk * 7)
        self.hurt = max(0, self.hurt - dt)
        sc = self.scene
        if self.role == 'villager':
            if sc.combat_near(self.pos, 380):
                self.panic = 2.0
            if self.panic > 0:
                self.panic -= dt
                if self.target is None or dist(self.target, self.pos) < 20:
                    away = self.pos - sc.player.pos
                    if away.length_squared() < 1:
                        away = V(1, 0)
                    self.target = self.pos + away.normalize().rotate(random.uniform(-40, 40)) * 200
            else:
                self.wait -= dt
                if self.wait <= 0:
                    self.wait = random.uniform(2, 5)
                    self.target = self.home + V(random.uniform(-120, 120), random.uniform(-90, 90))
            if self.target is not None:
                dv = self.target - self.pos
                if dv.length() > 8:
                    sp = 190 if self.panic > 0 else 60
                    step = dv.normalize() * sp * dt
                    np_ = self.pos + step
                    if not sc.is_blocked(np_.x, np_.y, 10) and not sc.map.is_water(np_.x, np_.y):
                        self.pos = np_
                    else:
                        self.target = None
                    self.walk = 1
                    self.facing = math.atan2(dv.y, dv.x)
                else:
                    self.walk = 0
                    self.target = None
        else:
            pl = sc.player
            if dist(pl.pos, self.pos) < 200:
                self.facing = angle_to(self.pos, pl.pos)

    def draw(self, surf, ox, oy):
        x, y = self.pos.x - ox, self.pos.y - oy
        if x < -60 or y < -100 or x > surf.get_width() + 60 or y > surf.get_height() + 100:
            return
        st = dict(phase=self.phase, walk=self.walk, pose='hurt' if self.hurt > 0 else 'idle', pose_t=0, z=0, expr='hurt' if self.panic > 0 else 'normal', ckey=id(self.app))
        draw_character(surf, x, y, self.app, self.facing, st)
        if self.role != 'villager':
            icon = {'shop': "$", 'smith': "⚒", 'shipwright': "⚓", 'tavern': "♣", 'mentor': "!", 'board': "?", 'heal': "+", 'colosseum': "★"}.get(self.role, "")
            bob = math.sin(self.phase * 1.5) * 3
            ic_col = {'mentor': (255, 210, 60), 'shop': (120, 255, 140), 'shipwright': (140, 200, 255), 'colosseum': (255, 120, 80), 'board': (255, 200, 120)}.get(self.role, (255, 255, 255))
            draw_text(surf, icon if icon not in ("⚒", "⚓", "♣") else {"⚒": "К", "⚓": "Ш", "♣": "Т"}[icon], (x, y - 78 * self.app.get('scale', 1) + bob), 22, ic_col, "center", 2)
            if dist(self.scene.player.pos, self.pos) < 140:
                draw_text(surf, self.name, (x, y - 98 * self.app.get('scale', 1)), 14, (255, 255, 255), "center", 2)

ROLE_NAMES = {'shop': "Торговец", 'smith': "Кузнец", 'shipwright': "Корабел", 'tavern': "Таверна (вербовка)", 'heal': "Врач"}

class IslandScene:
    kind = 'island'

    def __init__(self, game, iid, deck=None):
        self.game = game
        self.iid = iid
        self.deck = deck
        pd = game.pd
        if deck is not None:
            self.isl = deck['isl']
        else:
            self.isl = ISLANDS[iid]
        self.pd = pd
        self.ist = pd.island_state(iid) if deck is None else {'done': False, 'visited': True, 'chest': True}
        self.first_visit = not self.ist['visited']
        self.ist['visited'] = True
        self.done_before = self.ist['done']
        seed = stable_seed(iid) if deck is None else random.randint(0, 10 ** 9)
        self.map = IslandMap(iid, self.isl, random.Random(seed))
        self.rng = random.Random(seed + 7)
        self.fighters = []
        self.projectiles = []
        self.beams = []
        self.zones = []
        self.effects = []
        self.particles = Particles()
        self.texts = []
        self.npcs = []
        self.timers = []
        self.cam = Camera()
        self.cam.bounds = (0, 0, self.map.w * TILE, self.map.h * TILE)
        self.t = 0.0
        self.time_scale = 1.0
        self.slow_t = 0.0
        self.hitstop_t = 0.0
        self.flash_col = None
        self.flash_t = 0.0
        self.flash_max = 0.1
        self.impact_n = 0
        self.cutin_state = None
        self.clash = None
        self.cine = None
        self.combo = 0
        self.combo_t = 0.0
        self.combo_best = 0
        self.boss = None
        self.boss_spawned = False
        self.victory_t = None
        self.defeat_t = None
        self.weather = []
        self.hint_t = 0
        self.logia_hint_shown = False
        self.slam_cd = 0
        self.notifications = []
        self.spar = None
        self.dmg_log = 0
        self.view_surf = None
        self.paused = False
        self.lvl = self.isl['lvl'] if deck is None else deck['lvl']
        if self.done_before and deck is None:
            self.lvl = max(self.lvl, min(pd.level, self.lvl + 6))
        self.player = PlayerFighter(self, pd, self.map.spawn)
        self.fighters.append(self.player)
        self.cam.pos = V(self.player.pos)
        self._spawn_allies()
        self._spawn_npcs()
        self.objectives = []
        self._setup_objectives()
        self._init_weather()
        self.minimap = None
        self.minimap_t = 0
        self.music = self.isl.get('music', 'island')
        if deck is not None:
            self.music = 'battle'
        game.audio.play_music(self.music)
        game.audio.ambient_loop('waves', 0.25)
        if deck is None:
            self.intro_dialogue()
        else:
            self.notify("АБОРДАЖ! Победи команду корабля!", (255, 200, 80))

    # ---------------- настройка ----------------
    def faction(self):
        return self.pd.faction

    def pick(self, d):
        f = self.faction()
        if f in d:
            return d[f]
        return d.get('*')

    def enemy_pool(self):
        if self.deck is not None:
            return self.deck['pool']
        if self.faction() == 'marine' and self.isl.get('enemies_marine'):
            return self.isl['enemies_marine']
        return self.isl['enemies']

    def _spawn_allies(self):
        pd = self.pd
        pos = self.player.pos
        for i, cid in enumerate(pd.active_comp[:2]):
            if cid in COMPANIONS:
                f = make_companion(self, cid, max(1, pd.level - 1), pos + V(-50 + i * 100, 40))
                self.fighters.append(f)
        fighters = [c for c in pd.crew if c['role'] == 'fighter'][:2 - min(2, len(pd.active_comp))]
        for i, c in enumerate(fighters):
            f = make_companion(self, None, max(1, min(pd.level, c['lvl'])), pos + V(-30 + i * 60, 70), crew=c)
            self.fighters.append(f)

    def _spawn_npcs(self):
        if self.deck is not None:
            return
        m = self.map
        spots = list(m.npc_spots)
        self.rng.shuffle(spots)
        roles = []
        isl = self.isl
        if isl['shop'] or isl['fruit_shop']:
            roles.append(('shop', "Торговец"))
        if isl.get('blacksmith'):
            roles.append(('smith', "Кузнец"))
        if isl.get('shipwright'):
            roles.append(('shipwright', "Корабел"))
        if isl.get('tavern', True):
            roles.append(('tavern', "Хозяин таверны"))
        for mid in isl['mentor']:
            roles.append(('mentor:' + mid, MENTORS[mid]['name']))
        for role, name in roles:
            if not spots:
                break
            p = spots.pop()
            if role.startswith('mentor:'):
                mid = role.split(':')[1]
                app = dict(MENTORS[mid]['app'])
                self.npcs.append(NPC(self, p, app, 'mentor', name, mid))
            else:
                app = default_app(skin=self.rng.choice(SKIN_TONES[:6]), hair=self.rng.choice(HAIR_STYLES), hair_col=self.rng.choice(HAIR_COLORS),
                                  outfit='shirt', top=self.rng.choice(CLOTH_COLORS), hat=self.rng.choice(['none', 'cap', 'bandana']),
                                  hat_col=self.rng.choice(CLOTH_COLORS))
                if role == 'smith':
                    app.update(outfit='tank', top=(90, 70, 60), hair='bald', features=('beard',))
                self.npcs.append(NPC(self, p, app, role, name))
        nvill = 0 if 'war' in isl['flags'] else int(6 + isl.get('size', (70, 50))[0] / 10)
        for i in range(nvill):
            p = m.town_c + V(self.rng.uniform(-300, 300), self.rng.uniform(-220, 220))
            if m.is_water(p.x, p.y) or self.is_blocked(p.x, p.y, 10):
                continue
            app = default_app(skin=self.rng.choice(SKIN_TONES[:6]), hair=self.rng.choice(HAIR_STYLES), hair_col=self.rng.choice(HAIR_COLORS),
                              outfit=self.rng.choice(['shirt', 'vest', 'robe', 'kimono' if isl['theme'] == 'wano' else 'shirt']),
                              top=self.rng.choice(CLOTH_COLORS), bottom=self.rng.choice(CLOTH_COLORS), hat=self.rng.choice(['none', 'none', 'cap', 'kasa' if isl['theme'] == 'wano' else 'none']),
                              hat_col=self.rng.choice(CLOTH_COLORS))
            if isl['theme'] == 'coral':
                app.update(skin=(150, 190, 220), features=('fishman', 'fin'))
            if isl['theme'] == 'giant':
                app['scale'] = 2.0
            if isl['theme'] == 'forest':
                app.update(features=('mink',), fur=self.rng.choice(HAIR_COLORS))
            self.npcs.append(NPC(self, p, app, 'villager', "Житель"))

    def _setup_objectives(self):
        isl = self.isl
        boss = self.pick(isl['boss']) if self.deck is None else None
        mids = (self.pick(isl['mids']) or []) if self.deck is None else []
        if self.deck is not None:
            self.objectives = [dict(type='groups', need=len(self.map.camps[:2]) or 1, done=0, text="Победи команду корабля")]
            self._spawn_groups(self.map.camps[:2] or [self.map.town_c], deck=True)
            return
        no_combat = 'no_combat' in isl['flags'] or (boss is None and not self.isl['enemies'])
        if no_combat or boss is None:
            self.objectives = []
            if not self.done_before:
                self.timers.append([0.5, self._complete_peaceful])
            if self.isl.get('groups', 0) > 0 and boss is None and not no_combat:
                self._spawn_groups(self.map.camps)
            return
        camps = self.map.camps
        if self.done_before:
            self._spawn_groups(camps[:max(1, len(camps) // 2)])
            self.objectives = [dict(type='free', text="Остров освобождён. Тренируйся, торгуй или вызови босса на реванш (метка ★).")]
            self.boss_marker = V(self.map.arena)
            self.rematch = boss
            return
        self._spawn_groups(camps)
        need = max(1, int(math.ceil(len(camps) * 0.6)))
        self.objectives.append(dict(type='groups', need=need, done=0, text="Разгроми отряды врагов"))
        if mids:
            self.objectives.append(dict(type='mids', ids=list(mids), left=list(mids), text="Победи офицеров"))
        self.objectives.append(dict(type='boss', id=boss, text="Сразись с боссом: " + BOSSES[boss]['name']))
        self.boss_marker = V(self.map.arena)
        self.rematch = None
        self.mid_spawned = False

    def _spawn_groups(self, camps, deck=False):
        pool = self.enemy_pool()
        lvl = self.lvl
        for gi, c in enumerate(camps):
            n = self.rng.randint(3, 4) + (1 if lvl > 30 else 0) + (1 if lvl > 65 else 0)
            if deck:
                n += 2
            for k in range(n):
                et = self.rng.choice(pool)
                if ENEMY_TYPES[et].get('elite') and k > 0 and self.rng.random() < 0.6:
                    et = [e for e in pool if not ENEMY_TYPES[e].get('elite')][0] if any(not ENEMY_TYPES[e].get('elite') for e in pool) else et
                p = c + V(self.rng.uniform(-90, 90), self.rng.uniform(-70, 70))
                if self.is_blocked(p.x, p.y, 12) or self.map.is_water(p.x, p.y):
                    p = V(c)
                f = make_enemy(self, et, max(1, lvl + self.rng.randint(-1, 1)), p, group=('g', gi))
                self.fighters.append(f)

    def _spawn_mids(self):
        obj = self.cur_obj()
        if not obj or obj['type'] != 'mids' or self.mid_spawned:
            return
        self.mid_spawned = True
        spots = list(self.map.mid_spots) or [self.map.town_c]
        for i, bid in enumerate(obj['ids']):
            p = spots[i % len(spots)] + V(i * 40, 0)
            f = make_boss(self, bid, self.lvl + 1, p, elite_mode=True)
            f.mid_id = bid
            f.group = ('m', i)
            f.max_hp *= 0.55
            f.hp = f.max_hp
            self.fighters.append(f)
            for k in range(2):
                et = self.rng.choice(self.enemy_pool())
                self.fighters.append(make_enemy(self, et, self.lvl, p + V(self.rng.uniform(-80, 80), self.rng.uniform(-60, 60)), group=('m', i)))
        names = ", ".join(BOSSES[b]['name'] for b in obj['ids'])
        self.notify("Появились офицеры: " + names, (255, 180, 80))

    def cur_obj(self):
        return self.objectives[0] if self.objectives else None

    def intro_dialogue(self):
        lines = list(self.isl['intro'].get('*', []))
        lines += self.isl['intro'].get(self.faction(), [])
        if self.done_before:
            lines = [('nar', self.isl['name'] + ". Остров помнит тебя.")]
        if lines:
            self.game.dialogue(lines, self._after_intro)
        else:
            self._after_intro()

    def _after_intro(self):
        if 'tutorial' in self.isl['flags'] and not self.done_before:
            self.game.tutorial_hint()
        if self.cur_obj() and self.cur_obj()['type'] == 'mids':
            self._spawn_mids()

    def _complete_peaceful(self):
        if self.ist['done']:
            return
        self.ist['done'] = True
        lines = list(self.isl['outro'].get('*', [])) + self.isl['outro'].get(self.faction(), [])
        def fin():
            self.game.island_complete(self.iid, None)
        self.game.dialogue(lines, fin)

    # ---------------- поиск пути (поле потока) ----------------
    def flow_field(self, target):
        from collections import deque
        m = self.map
        t = m.tile(target.x, target.y)
        if t is None:
            return None
        w_, h_ = m.w, m.h
        blocked = (m.occ >= 0) | ((m.ground == G_DEEP) & (m.state != S_ICE))
        dist_ = np.full((h_, w_), 30000, np.int32)
        tx, ty = t
        dist_[ty, tx] = 0
        q = deque([(tx, ty)])
        bl = blocked.tolist()
        dl = dist_.tolist()
        while q:
            x, y = q.popleft()
            d = dl[y][x] + 1
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w_ and 0 <= ny < h_ and dl[ny][nx] > d and not bl[ny][nx]:
                    dl[ny][nx] = d
                    q.append((nx, ny))
        return dl

    def flow_dir(self, field, pos):
        if field is None:
            return None
        m = self.map
        t = m.tile(pos.x, pos.y)
        if t is None:
            return None
        x, y = t
        best = field[y][x]
        bx, by = x, y
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < m.w and 0 <= ny < m.h and field[ny][nx] < best:
                if dx and dy and (field[y][nx] >= 30000 or field[ny][x] >= 30000):
                    continue
                best = field[ny][nx]
                bx, by = nx, ny
        if (bx, by) == (x, y):
            return None
        v = V((bx + 0.5) * TILE, (by + 0.5) * TILE) - pos
        return v.normalize() if v.length_squared() > 0 else None

    def player_field(self):
        if self.t - getattr(self, '_pf_t', -9) > 0.4:
            self._pf_t = self.t
            self._pf = self.flow_field(self.player.pos)
        return self._pf

    # ---------------- API для боевой системы ----------------
    def hostiles_near(self, f, pos, r):
        out = []
        for o in self.fighters:
            if o.dead or not f.hostile_to(o):
                continue
            rr = r + o.radius
            if dist2(o.pos, pos) <= rr * rr and o.z < 140:
                out.append(o)
        return out

    def is_blocked(self, x, y, r, f=None):
        m = self.map
        if x < r or y < r or x > m.w * TILE - r or y > m.h * TILE - r:
            return True
        for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r * 0.6), (0, -r * 0.6)):
            t = m.tile(x + dx, y + dy)
            if t is None:
                return True
            if m.occ[t[1], t[0]] >= 0:
                return True
        if f is not None and f.z < 10 and m.is_water(x, y):
            if f.kind == 'player':
                if f.fruit_user and not f.fishman and f.knock_v.length_squared() < 300 * 300:
                    return True
            elif f.team != 'enemy' or not f.fishman:
                if f.knock_v.length_squared() < 300 * 300 and f.form != 'dragon':
                    return True
        return False

    def struct_at(self, x, y, r):
        m = self.map
        for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r * 0.6), (0, -r * 0.6)):
            s = m.struct_at(x + dx, y + dy)
            if s is not None and not s.destroyed:
                return s
        return None

    def is_water(self, x, y):
        return self.map.is_water(x, y)

    def clamp_pos(self, f):
        m = self.map
        f.pos.x = clamp(f.pos.x, 20, m.w * TILE - 20)
        f.pos.y = clamp(f.pos.y, 20, m.h * TILE - 20)

    def damage_area(self, pos, r, amount, e='phys'):
        if amount <= 0:
            return
        m = self.map
        x0, y0 = int((pos.x - r) // TILE), int((pos.y - r) // TILE)
        x1, y1 = int((pos.x + r) // TILE), int((pos.y + r) // TILE)
        seen = set()
        for ty in range(max(0, y0), min(m.h, y1 + 1)):
            for tx in range(max(0, x0), min(m.w, x1 + 1)):
                i = m.occ[ty, tx]
                if i >= 0 and i not in seen:
                    seen.add(i)
                    self.damage_struct(m.structs[i], amount, e)

    def damage_line(self, a, b, w_, amount, e='phys'):
        L = dist(a, b)
        n = max(1, int(L / 40))
        seen = set()
        m = self.map
        for i in range(n + 1):
            p = V(a) + (V(b) - V(a)) * (i / n)
            t = m.tile(p.x, p.y)
            if t is None:
                continue
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    tx, ty = t[0] + dx, t[1] + dy
                    if 0 <= tx < m.w and 0 <= ty < m.h:
                        si = m.occ[ty, tx]
                        if si >= 0 and si not in seen:
                            seen.add(si)
                            self.damage_struct(m.structs[si], amount * 0.5, e)

    def damage_struct(self, s, amount, e='phys'):
        if s.destroyed or s.max_hp >= 90000:
            return
        vul = 1.0
        if e in ('fire', 'magma', 'blue_fire', 'bomb') and s.flammable:
            vul = 1.6
            if random.random() < 0.35:
                s.burn = max(s.burn, random.uniform(5, 10))
        elif e in ('quake', 'gravity', 'stone', 'paw', 'conq', 'haki', 'nika'):
            vul = 1.5
        elif e in ('ice', 'snow'):
            vul = 0.7
        s.hp -= amount * vul
        s.hit_t = 0.15
        r = s.rect()
        if random.random() < 0.6:
            self.particles.burst(r.centerx + random.uniform(-r.w / 3, r.w / 3), r.bottom - s.height * 0.4, 5, s.col, 'debris', 180, 0.8, size=4, grav=900, z=20, vz=250)
        if s.hp <= 0:
            self.destroy_struct(s)

    def destroy_struct(self, s):
        if s.destroyed:
            return
        s.destroyed = True
        m = self.map
        m.occ[s.ty:s.ty + s.th, s.tx:s.tx + s.tw] = -1
        big = s.kind in ('house', 'tower', 'hall', 'fort', 'palace', 'castle', 'colosseum', 'ruin')
        for ty in range(s.ty, s.ty + s.th):
            for tx in range(s.tx, s.tx + s.tw):
                m.set_state(tx, ty, S_RUBBLE if big else S_CRATER)
        r = s.rect()
        n = int(18 + s.tw * s.th * 8)
        self.particles.burst(r.centerx, r.bottom - 10, n, s.col, 'debris', 220 + s.tw * 40, 1.4, size=5 + s.tw, grav=900, z=s.height * 0.5, vz=350)
        self.particles.burst(r.centerx, r.bottom - 10, n // 2, s.roof, 'debris', 260, 1.4, size=6, grav=900, z=s.height * 0.7, vz=400)
        for _ in range(int(4 + s.tw * 3)):
            self.particles.add(r.x + random.uniform(0, r.w), r.bottom - random.uniform(0, 20), random.uniform(-40, 40), random.uniform(-30, 10), 1.6, random.uniform(20, 40),
                               (190, 180, 165), 'dust', grow=30)
        if big:
            self.cam.add_shake(0.25 + s.tw * 0.04)
            self.audio_play('crumble', 0.8, pos=s.center())
        else:
            self.audio_play('hit_heavy', 0.4, pos=s.center())
        if s.kind == 'water_barrel':
            self.particles.burst(r.centerx, r.centery, 30, (90, 160, 255), 'water', 300, 0.7, size=4, grav=600, z=10, vz=200)
            for f in self.fighters:
                if not f.dead and dist(f.pos, r.center) < 120:
                    f.add_status('wet', 20)
                    if f.kind == 'player':
                        self.notify("Ты мокрый! Удары бьют по песчаной и дымовой логии.", (120, 200, 255))
        if s.loot or s.kind in ('crate', 'barrel'):
            self.drop_beli(V(r.center), int(60 * (1 + self.lvl * 0.4) * random.uniform(0.6, 1.4)))
            if random.random() < 0.25:
                self.drop_item(V(r.center))
        self.game.on_destroyed(self, s)

    def wall_slam(self, f, s, spd):
        dmgv = spd * 0.9 * f.scale
        self.damage_struct(s, dmgv, 'quake')
        if f.team == 'enemy' and not f.dead:
            f.hp -= f.max_hp * 0.03 + spd * 0.02
            f.stagger = max(f.stagger, 0.5)
            if f.hp <= 0:
                f.die(self.player)
        self.effects.append(ImpactStarFX(V(f.pos.x, f.pos.y - 25), 40, 0.2, (255, 240, 200)))
        self.cam.add_shake(0.15)
        if self.slam_cd <= 0:
            self.slam_cd = 0.6
            self.float_text(f.pos, "Удар о стену!", (255, 220, 160), 16)

    def terrain_effect(self, pos, r, kind):
        self.map.terrain_effect(pos, r, kind)
        if kind in ('fire', 'lava'):
            for s in self._structs_near(pos, r):
                if s.flammable and random.random() < 0.5:
                    s.burn = max(s.burn, random.uniform(5, 10))

    def _structs_near(self, pos, r):
        m = self.map
        x0, y0 = int((pos.x - r) // TILE), int((pos.y - r) // TILE)
        x1, y1 = int((pos.x + r) // TILE), int((pos.y + r) // TILE)
        seen = set()
        out = []
        for ty in range(max(0, y0), min(m.h, y1 + 1)):
            for tx in range(max(0, x0), min(m.w, x1 + 1)):
                i = m.occ[ty, tx]
                if i >= 0 and i not in seen:
                    seen.add(i)
                    out.append(m.structs[i])
        return out

    def spawn_summon(self, owner, kind, pos, life):
        f = make_enemy(self, kind if kind in ENEMY_TYPES else 'doppel', owner.level, pos, team=owner.team)
        f.kind = 'summon'
        f.life_t = life
        f.summoner = owner
        f.xp_value = 0
        if owner.team != 'enemy':
            f.ai.aggro = True
        self.fighters.append(f)

    def alert_group(self, f):
        if f.group is None:
            return
        for o in self.fighters:
            if o.group == f.group and o.ai is not None:
                o.ai.aggro = True

    def combat_near(self, pos, r):
        for f in self.fighters:
            if f.team == 'enemy' and not f.dead and f.ai and f.ai.aggro and dist(f.pos, pos) < r:
                return True
        return False

    def audio_play(self, name, vol=1.0, pos=None, cooldown=0.03):
        pan = 0.0
        if pos is not None:
            dx = pos.x - self.cam.pos.x
            pan = clamp(dx / 700, -0.8, 0.8)
            d = dist(pos, self.cam.pos)
            vol *= clamp(1.3 - d / 1100, 0.15, 1.0)
        self.game.audio.play(name, vol, pan, cooldown)

    def float_text(self, pos, text, col=(255, 255, 255), size=18):
        self.texts.append(FloatText(pos.x, pos.y - 60, text, col, size, 1.1))

    def float_dmg(self, t, dmg, crit, src):
        if t.kind == 'player':
            col = (255, 80, 80)
        elif src is not None and src.team in ('player', 'ally'):
            col = (255, 235, 120) if not crit else (255, 120, 40)
        else:
            col = (230, 230, 230)
        size = 20 if not crit else 28
        if dmg > t.max_hp * 0.2:
            size += 8
        self.texts.append(FloatText(t.pos.x, t.pos.y - 55 * t.scale - t.z, fmt_num(dmg) + ("!" if crit else ""), col, size, 0.9, crit))

    def notify(self, text, col=(255, 255, 255)):
        self.notifications.append([text, col, 3.5])

    def hitstop(self, t):
        self.hitstop_t = max(self.hitstop_t, t)

    def slowmo(self, t, scale=0.3):
        self.slow_t = max(self.slow_t, t)
        self.time_scale = scale

    def flash(self, col, t):
        self.flash_col = col
        self.flash_t = t
        self.flash_max = t

    def impact_frame(self, n):
        self.impact_n = max(self.impact_n, n)

    def hint_logia(self):
        if not self.logia_hint_shown:
            self.logia_hint_shown = True
            if self.pd.haki_cap['arm'] > 0:
                self.notify("ЛОГИЯ! Удары проходят насквозь. Включи Хаки Вооружения (Q)!", (255, 220, 120))
            else:
                self.notify("ЛОГИЯ! Обычные удары почти не ранят. Ищи слабость: вода (бочки «ВОДА»), стихия-противовес или хаки.", (255, 220, 120))

    def observation_active(self, f):
        return getattr(f, 'obs_t', 0) > 0

    def observation_dodge(self, f, hit):
        pd = self.pd
        lvl = pd.haki['obs']
        fs = f.fs
        chance = 1.0 if fs else 0.45 + 0.05 * lvl
        if random.random() > chance:
            return False
        src = hit.src
        f.dodge_jump(src)
        pd.haki_gain('obs', 2)
        if fs and src is not None and not src.dead:
            self.float_text(f.pos, "ПРЕДВИДЕНИЕ!", (255, 120, 200), 22)
            behind = src.pos + from_angle(angle_to(f.pos, src.pos), 50)
            if not self.is_blocked(behind.x, behind.y, f.radius):
                f.pos = behind
            f.aim = angle_to(f.pos, src.pos)
            hitc = Hit(f.power() * 2.2, 'haki' if f.armament else 'phys', from_angle(f.aim, 600), 200, 0.6, f, haki=f.armament, heavy=True)
            apply_hit(src, hitc, f, heavy=True)
            self.slowmo(0.35, 0.35)
        else:
            self.float_text(f.pos, "Наблюдение!", (200, 200, 255), 16)
        return True

    def on_perfect_dodge(self, f):
        self.slowmo(0.45, 0.3)
        self.float_text(f.pos, "Идеальное уклонение!", (160, 220, 255), 20)
        f.spirit = min(200, f.spirit + 10)
        self.audio_play('whoosh', 0.8)

    def on_parry(self, f, src):
        src.stagger = max(src.stagger, 0.5 if src.is_boss else 1.0)
        src.knock_v += from_angle(angle_to(f.pos, src.pos), 500 if not src.is_boss else 150)
        if src.action is not None:
            src.action.cancel()
            src.action = None
        self.float_text(f.pos, "ПАРИРОВАНИЕ!", (255, 255, 180), 24)
        self.slowmo(0.4, 0.3)
        self.flash((255, 255, 230), 0.12)
        self.audio_play('parry', 1.0)
        self.effects.append(ImpactStarFX(V((f.pos.x + src.pos.x) / 2, (f.pos.y + src.pos.y) / 2 - 25), 50, 0.25, (220, 240, 255)))
        f.spirit = min(200, f.spirit + 15)
        f.st = min(f.max_st, f.st + 15)

    def on_damage(self, t, dmg, hit):
        src = hit.src
        pl = self.player
        if src is pl or (src is not None and src.summoner is pl):
            self.combo += 1
            self.combo_t = 2.2
            self.combo_best = max(self.combo_best, self.combo)
            pl.spirit = min(200, pl.spirit + (2.4 if hit.heavy else 1.0) * (0.5 if t.team != 'enemy' else 1.0))
            pd = self.pd
            if hit.fruit:
                if pd.fruit_gain(0.07 if not hit.ult else 0.5):
                    self.check_unlocks()
            else:
                if pd.style_gain(pl.style, 0.05):
                    self.check_unlocks()
            if pl.armament:
                if pd.haki_gain('arm', 0.6):
                    self.notify(f"Хаки Вооружения: уровень {pd.haki['arm']}!", (190, 140, 255))
                    pl.apply_stats()
        if t is pl:
            pl.spirit = min(200, pl.spirit + 1.6)
            self.combo = 0
        if isinstance(t, Fighter) and t.team == 'player':
            pass

    def check_unlocks(self):
        before = set(m for m in self.pd.loadout if m)
        um = self.pd.unlocked_moves()
        new = [m for m in um if m not in getattr(self, '_known_moves', set())]
        if not hasattr(self, '_known_moves'):
            self._known_moves = set(um)
            return
        for m in new:
            self._known_moves.add(m)
            self.notify("Новый приём: " + MOVES[m]['name'] + " (меню → Приёмы)", (120, 255, 200))
            self.audio_play('levelup', 0.6)
        self.pd.fix_loadout()
        self.player.moves = [m for m in self.pd.loadout if m]

    def on_kill(self, f, killer):
        pd = self.pd
        if f is self.player:
            self.on_player_dead()
            return
        if f.team == 'enemy' and f.kind != 'summon':
            pd.kills += 1
            gap = f.level - pd.level
            xp = f.xp_value * (1 + 0.12 * max(0, gap)) * (0.4 if gap < -8 else 1.0)
            ups = pd.add_xp(xp)
            if ups:
                self.on_levelup(ups)
            luck = 1.25 if pd.trait == 'lucky' else 1.0
            self.drop_beli(f.pos, int((15 + f.level * 8) * (3 if f.elite else 1) * random.uniform(0.6, 1.4) * luck))
            if random.random() < (0.08 if not f.elite else 0.5) * luck:
                self.drop_item(f.pos)
            if f.knocked_out:
                self.particles.burst(f.pos.x, f.pos.y - 20, 6, (255, 255, 255), 'bubble', 60, 1.0, size=4)
            if pd.style and killer is self.player:
                pd.style_gain(self.player.style, 0.3)
            self._progress_kill(f)
            if f.is_boss and f is self.boss:
                self.on_boss_defeated(f)
            elif hasattr(f, 'mid_id'):
                self._mid_down(f)
            if getattr(f, 'spar', False):
                pass
            if self.deck is not None:
                pd.merit += 2 if pd.faction != 'pirate' else 0
        elif f.team == 'ally' and f.kind != 'summon':
            self.notify(f"{f.name} без сил!", (255, 150, 150))

    def on_levelup(self, ups):
        pl = self.player
        pl.apply_stats()
        pl.hp = pl.max_hp
        self.float_text(pl.pos, f"НОВЫЙ УРОВЕНЬ {self.pd.level}!", (255, 230, 90), 30)
        self.effects.append(RingFX(pl.pos, 10, 200, 0.8, (255, 230, 90), 8))
        self.particles.burst(pl.pos.x, pl.pos.y - 25, 40, (255, 230, 120), 'glow', 300, 1.0, size=5)
        self.audio_play('levelup', 1.0)
        self.notify(f"Уровень {self.pd.level}! +{3 * ups} очков характеристик (меню → Персонаж)", (255, 230, 90))

    def drop_beli(self, pos, amount):
        self.pd.beli += amount
        for _ in range(min(8, 2 + amount // 200)):
            self.particles.add(pos.x, pos.y - 20, random.uniform(-120, 120), random.uniform(-120, 60), 0.9, 4, (255, 215, 60), 'glow', z=20, vz=250, grav=700)
        self.texts.append(FloatText(pos.x, pos.y - 80, "+" + fmt_num(amount) + " ฿", (255, 215, 80), 14, 0.9))
        self.audio_play('coin', 0.35, pos=pos, cooldown=0.08)

    def drop_item(self, pos):
        lvl = self.lvl
        if random.random() < 0.55:
            iid = random.choice(['meat', 'meat', 'bento', 'sake'] + (['sea_king_meat'] if lvl > 25 else []))
        else:
            mats = ['wood', 'iron', 'iron']
            if lvl > 15:
                mats += ['steel', 'steel']
            if lvl > 30:
                mats += ['kairoseki', 'sea_king_scale', 'gold']
            if lvl > 55:
                mats += ['tamahagane', 'wapometal', 'adam_wood']
            iid = random.choice(mats)
        it = make_item(iid)
        self.pd.add_item(it)
        self.texts.append(FloatText(pos.x, pos.y - 95, "+ " + it['name'], RARITY_COLORS[it['rarity']], 14, 1.2))

    def _progress_kill(self, f):
        obj = self.cur_obj()
        if not obj:
            return
        if obj['type'] == 'groups' and f.group is not None and f.group[0] == 'g':
            alive = [o for o in self.fighters if o.group == f.group and not o.dead]
            if not alive:
                obj['done'] += 1
                self.notify(f"Отряд разгромлен! ({obj['done']}/{obj['need']})", (255, 220, 120))
                if obj['done'] >= obj['need']:
                    self.advance_obj()

    def _mid_down(self, f):
        obj = self.cur_obj()
        if obj and obj['type'] == 'mids' and f.mid_id in obj['left']:
            obj['left'].remove(f.mid_id)
            self.pd.bosses_beaten.add(f.mid_id)
            bd = BOSSES[f.mid_id]
            q = bd['quotes'].get('defeat')
            if q:
                f.speech = q
                f.speech_t = 3
            self.notify(f"Офицер повержен: {bd['name']}", (255, 200, 90))
            self.game.reward_rep(bd.get('bounty', 0) * 0.3 + 4000 * self.lvl, quiet=True)
            if not obj['left']:
                self.advance_obj()

    def advance_obj(self):
        if self.objectives:
            self.objectives.pop(0)
        obj = self.cur_obj()
        if not obj:
            if self.deck is not None:
                self.timers.append([1.5, lambda: self.game.deck_victory(self)])
            return
        if obj['type'] == 'mids':
            self._spawn_mids()
        elif obj['type'] == 'boss':
            self.notify("Путь к боссу открыт! Следуй за меткой ★", (255, 120, 80))

    def boss_phase(self, f, ph):
        say = ph.get('say', '')
        f.invuln = 1.2
        if say:
            f.speech = say
            f.speech_t = 3.5
        f.buffs.append(dict(t=999, dmg=ph.get('buff', 1.3), defn=1.1, spd=1.1, aura=(255, 60, 60)))
        if ph.get('form'):
            f.form = ph['form']
            if f.form == 'dragon':
                f.hist = []
                f.scale *= 1.1
        self.effects.append(RingFX(f.pos, 10, 380, 0.8, (255, 80, 80), 12))
        for o in self.fighters:
            if o.team != 'enemy' and not o.dead and dist(o.pos, f.pos) < 350:
                o.knock_v += from_angle(angle_to(f.pos, o.pos), 700)
        self.flash((255, 200, 200), 0.25)
        self.cam.add_shake(0.6)
        self.audio_play('haki', 1.0)
        self.cam.focus = V(f.pos)
        self.cam.focus_t = 1.0
        self.cam.target_zoom = 1.25
        self.timers.append([1.0, lambda: setattr(self.cam, 'target_zoom', 1.0)])
        if f.haki_always and BOSSES[f.boss_id].get('haki') and f.level >= 40:
            nova_visual(self, f.pos, 300, 'conq', el('conq'), {})

    # ---------------- босс ----------------
    def try_spawn_boss(self):
        obj = self.cur_obj()
        pl = self.player
        if getattr(self, 'rematch', None) and not self.boss_spawned:
            if dist(pl.pos, self.boss_marker) < 260:
                self.start_boss(self.rematch, rematch=True)
            return
        if not obj or obj['type'] != 'boss' or self.boss_spawned:
            return
        if dist(pl.pos, self.boss_marker) < 380:
            self.start_boss(obj['id'])

    def start_boss(self, bid, rematch=False, level_bonus=0):
        self.boss_spawned = True
        pos = self.boss_marker + V(0, -60)
        lvl = self.lvl + 2 + level_bonus
        f = make_boss(self, bid, lvl, pos)
        f.ai.aggro = True
        self.boss = f
        self.boss_rematch = rematch
        self.fighters.append(f)
        bd = BOSSES[bid]
        self.cine = dict(kind='boss_intro', t=0, dur=3.0, boss=f, name=bd['name'], title=bd['title'], bounty=bd['bounty'])
        self.cam.focus = V(f.pos)
        self.cam.focus_t = 2.6
        self.cam.target_zoom = 1.35
        self.game.audio.play_music(bd.get('music', 'boss') if self.isl.get('music') != 'wano' else 'boss', fade=800)
        self.audio_play('gong', 0.9)
        f.invuln = 3.0
        # союзники в войнах
        if 'war' in self.isl['flags'] and not rematch:
            kind = 'marine' if self.faction() in ('marine',) else 'wb_pirate'
            for i in range(5):
                a = self.make_war_ally(kind, i)
        if self.isl['theme'] == 'wano' and not rematch:
            for i in range(4):
                self.make_war_ally('samurai', i)
        if self.isl['theme'] == 'giant' and self.faction() != 'marine' and not rematch:
            for i in range(3):
                self.make_war_ally('giant_warrior', i)

    def make_war_ally(self, kind, i):
        p = self.player.pos + from_angle(i * 1.25, 90)
        a = make_enemy(self, kind, max(1, self.pd.level - 2), p, team='ally')
        a.ai.aggro = True
        a.kind = 'ally'
        self.fighters.append(a)
        return a

    def on_boss_defeated(self, f):
        bd = BOSSES[f.boss_id]
        q = bd['quotes'].get('defeat')
        if q:
            f.speech = q
            f.speech_t = 4
        self.slowmo(1.6, 0.18)
        self.cam.focus = V(f.pos)
        self.cam.focus_t = 2.0
        self.cam.target_zoom = 1.45
        self.flash((255, 255, 255), 0.5)
        self.impact_frame(4)
        self.effects.append(RingFX(f.pos, 10, 600, 1.2, (255, 240, 200), 14))
        self.particles.burst(f.pos.x, f.pos.y - 30, 80, (255, 230, 160), 'glow', 600, 1.2, size=6)
        self.audio_play('explosion', 1.0)
        for o in self.fighters:
            if o.team == 'enemy' and not o.dead and o is not f and o.kind != 'boss':
                o.knocked_out = True
                o.die(self.player)
        self.victory_t = 0.0
        self.pd.bosses_beaten.add(f.boss_id)
        self.game.audio.play_music('victory', fade=300, loop=False)

    def finish_victory(self):
        rematch = getattr(self, 'boss_rematch', False)
        bid = self.boss.boss_id if self.boss else None
        if rematch:
            self.boss = None
            self.boss_spawned = False
            self.victory_t = None
            self.cam.target_zoom = 1.0
            xp = int(BOSSES[bid]['hp'] * 30 * (1 + self.lvl)) // 2
            ups = self.pd.add_xp(xp)
            if ups:
                self.on_levelup(ups)
            self.game.reward_rep(BOSSES[bid].get('bounty', 0) * 0.05 + 2000 * self.lvl, quiet=False)
            self.notify(f"Реванш выигран! +{fmt_num(xp)} опыта", (255, 230, 120))
            self.game.audio.play_music(self.music)
            return
        lines = list(self.isl['outro'].get('*', [])) + self.isl['outro'].get(self.faction(), [])
        def fin():
            self.game.island_complete(self.iid, bid)
            self.game.audio.play_music(self.music)
        self.cam.target_zoom = 1.0
        self.game.dialogue(lines, fin)

    def on_player_dead(self):
        self.defeat_t = 0.0
        self.slowmo(1.5, 0.25)
        self.game.audio.play_music('sad', fade=1200)

    def respawn_player(self):
        pl = self.player
        pl.dead = False
        pl.death_t = 0
        pl.hp = pl.max_hp * 0.7
        pl.st = pl.max_st
        pl.pos = V(self.map.spawn)
        pl.invuln = 2.0
        pl.statuses = {}
        pl.action = None
        self.defeat_t = None
        lost = int(self.pd.beli * 0.1)
        self.pd.beli -= lost
        self.notify(f"Ты очнулся у причала. Потеряно {fmt_num(lost)} ฿", (255, 160, 160))
        if self.boss and not self.boss.dead:
            self.boss.hp = self.boss.max_hp
            self.boss.pos = self.boss_marker + V(0, -60)
            self.boss.phase_idx = 0
            self.boss.buffs = []
            self.boss.form = None
        self.game.audio.play_music(self.music)
        for f in self.fighters:
            if f.team == 'enemy' and f.ai:
                f.ai.aggro = False
                f.ai.target = None

# ==================================================================
#  ЦИКЛ ОСТРОВА: УПРАВЛЕНИЕ, КАТСЦЕНЫ, ОТРИСОВКА, HUD
# ==================================================================
def move_icon(surf, c, r, mid, active=True):
    mv = MOVES.get(mid)
    if not mv:
        return
    p = mv['steps'][0][1] if mv['steps'] else {}
    e = p.get('el', 'phys')
    ed = el(e)
    col = ed['c1'] if e not in ('phys', 'none') else (230, 200, 160)
    if not active:
        col = mul_col(col, 0.4)
    pygame.draw.circle(surf, mul_col(col, 0.45), c, r)
    pygame.draw.circle(surf, col, c, int(r * 0.8))
    pygame.draw.circle(surf, add_col(col, 50), (c[0] - r // 4, c[1] - r // 4), max(2, r // 4))
    t = p.get('p')
    k = (20, 14, 18)
    x, y = c
    if t == 'proj':
        pygame.draw.polygon(surf, k, [(x - r * 0.5, y - r * 0.3), (x + r * 0.5, y), (x - r * 0.5, y + r * 0.3)])
    elif t == 'nova' or t == 'rain':
        pygame.draw.polygon(surf, k, star_points(x, y, r * 0.55, r * 0.22, 7), 0)
    elif t == 'beam':
        pygame.draw.line(surf, k, (x - r * 0.6, y + r * 0.3), (x + r * 0.6, y - r * 0.3), 5)
    elif t == 'melee' or t == 'barrage':
        pygame.draw.arc(surf, k, (x - r * 0.55, y - r * 0.55, r * 1.1, r * 1.1), 0.5, 2.6, 4)
    elif t == 'dash' or t == 'teleport':
        for i in range(2):
            pygame.draw.lines(surf, k, False, [(x - r * 0.4 + i * r * 0.35, y - r * 0.35), (x - r * 0.05 + i * r * 0.35, y), (x - r * 0.4 + i * r * 0.35, y + r * 0.35)], 4)
    elif t == 'buff' or t == 'heal' or t == 'shield':
        pygame.draw.polygon(surf, k, [(x, y - r * 0.55), (x + r * 0.45, y), (x + r * 0.18, y), (x + r * 0.18, y + r * 0.5), (x - r * 0.18, y + r * 0.5), (x - r * 0.18, y), (x - r * 0.45, y)])
    elif t == 'zone' or t == 'wave':
        pygame.draw.circle(surf, k, c, int(r * 0.5), 3)
        pygame.draw.circle(surf, k, c, int(r * 0.2))
    else:
        pygame.draw.circle(surf, k, c, int(r * 0.3))
    if mv.get('ult'):
        pygame.draw.circle(surf, (255, 220, 80), c, r, 3)

class IslandLoop:
    # ---------------- обновление ----------------
    def update(self, dt_real):
        g = self.game
        self.t += dt_real
        self.minimap_t -= dt_real
        if self.cutin_state is not None:
            self.update_cutin(dt_real)
            return
        if self.clash is not None:
            self.update_clash(dt_real)
            return
        if self.cine is not None:
            c = self.cine
            c['t'] += dt_real
            self.cam.update(dt_real, self.player.pos)
            self.particles.update(dt_real)
            if c['t'] >= c['dur']:
                self.cine = None
                self.cam.target_zoom = 1.0
                bd = BOSSES[c['boss'].boss_id]
                q = bd['quotes'].get('intro')
                if q:
                    self.game.dialogue([(c['boss'].boss_id, q)], None)
            return
        if self.slow_t > 0:
            self.slow_t -= dt_real
            if self.slow_t <= 0:
                self.time_scale = 1.0
        dt = dt_real * self.time_scale
        if self.hitstop_t > 0:
            self.hitstop_t -= dt_real
            self.cam.update(dt_real, self.player.pos)
            return
        self.flash_t = max(0, self.flash_t - dt_real)
        self.slam_cd -= dt
        if self.combo_t > 0:
            self.combo_t -= dt
            if self.combo_t <= 0:
                self.combo = 0
        # таймеры
        if self.timers:
            nt = []
            for tm in self.timers:
                tm[0] -= dt
                if tm[0] <= 0:
                    try:
                        tm[1]()
                    except Exception:
                        traceback.print_exc()
                else:
                    nt.append(tm)
            self.timers = nt
        pl = self.player
        if self.defeat_t is not None:
            self.defeat_t += dt_real
        else:
            self.update_player(dt)
        for f in self.fighters:
            if f is not pl and f.ai is not None and not f.dead:
                if self.spar is None or f is self.spar or f.team != 'enemy' or True:
                    f.ai.update(dt)
            f.update(dt)
            if f.kind != 'player' and not f.dead:
                if f.has('poison') or self.map.state[min(self.map.h - 1, max(0, int(f.pos.y // TILE))), min(self.map.w - 1, max(0, int(f.pos.x // TILE)))] == S_LAVA:
                    if f.logia not in ('magma', 'fire') and f.z < 5:
                        f.hp -= f.max_hp * 0.03 * dt
                        if f.hp <= 0:
                            f.die(pl)
        # лава под игроком
        st_t = self.map.tile(pl.pos.x, pl.pos.y)
        if st_t is not None and not pl.dead and pl.z < 5:
            s_ = self.map.state[st_t[1], st_t[0]]
            if s_ == S_LAVA and pl.logia not in ('magma',):
                pl.hp -= pl.max_hp * 0.05 * dt
                if random.random() < dt * 4:
                    self.float_text(pl.pos, "Лава!", (255, 120, 40), 14)
                if pl.hp <= 0:
                    pl.die(None)
            elif s_ == S_BURN and pl.logia not in ('fire', 'magma'):
                if random.random() < dt * 2:
                    pl.add_status('burn', 1.0, pl.max_hp * 0.01)
            elif s_ == S_POISON and pl.logia != 'gas':
                pl.add_status('poison', 0.5, pl.max_hp * 0.01)
        self.fighters = [f for f in self.fighters if not f.remove]
        for p in self.projectiles:
            p.update(dt)
        self.projectiles = [p for p in self.projectiles if not p.dead]
        for b in self.beams:
            b.update(dt)
        self.beams = [b for b in self.beams if not b.dead]
        for z in self.zones:
            z.update(dt)
        self.zones = [z for z in self.zones if not z.dead]
        self.effects = [e for e in self.effects if e.update(dt)]
        self.particles.update(dt)
        for tx in self.texts:
            tx.life -= dt
            tx.y += tx.vy * dt
            tx.vy *= 0.9 ** (dt * 60)
        self.texts = [t for t in self.texts if t.life > 0]
        for n in self.npcs:
            n.update(dt)
        # постройки горят
        for s in self.map.structs:
            if s.hit_t > 0:
                s.hit_t -= dt
            if s.burn > 0 and not s.destroyed:
                s.burn -= dt
                s.hp -= s.max_hp * 0.06 * dt
                r = s.rect()
                if random.random() < dt * (6 + s.tw * 3):
                    self.particles.add(r.x + random.uniform(0, r.w), r.bottom - random.uniform(0, s.height * 0.8), random.uniform(-15, 15), -90,
                                       0.8, random.uniform(8, 16), (255, 130, 30), 'fire')
                if random.random() < dt * 2:
                    self.particles.add(r.centerx, r.bottom - s.height, 0, -40, 2.0, 18, (60, 55, 55), 'smoke', grow=20)
                if random.random() < dt * 0.6:
                    self.map.terrain_effect(V(r.centerx + random.uniform(-60, 60), r.bottom + random.uniform(-20, 40)), 30, 'fire')
                if s.hp <= 0:
                    self.destroy_struct(s)
        self.map.update(dt, self)
        self.map.draw_fire_overlay(self.view_surf or self.game.screen, *self.cam.offset(*self.cam.view_size()), self.particles, dt)
        # камера
        look = V(0, 0)
        if self.game.mouse is not None:
            mx, my = self.game.mouse
            look = V((mx - W / 2) * 0.12, (my - H / 2) * 0.12)
        self.cam.update(dt_real, pl.pos, look)
        for n in self.notifications:
            n[2] -= dt_real
        self.notifications = [n for n in self.notifications if n[2] > 0][-5:]
        self.try_spawn_boss()
        self.update_weather(dt_real)
        if self.victory_t is not None:
            self.victory_t += dt_real
            if self.victory_t > 3.2:
                self.victory_t = None
                self.finish_victory()
        if self.spar is not None:
            self.update_spar()

    def mouse_world(self):
        vw, vh = self.cam.view_size()
        ox, oy = self.cam.offset(vw, vh)
        mx, my = self.game.mouse
        z = self.cam.zoom
        return V(ox + mx / z, oy + my / z)

    def update_player(self, dt):
        g = self.game
        pl = self.player
        pd = self.pd
        if pl.dead:
            return
        keys = g.keys
        mw = self.mouse_world()
        pl.aim = angle_to(pl.pos + V(0, -20), mw)
        if pl.action is None or pl.action.basic:
            pl.facing = pl.aim
        mvv = V((1 if keys[pygame.K_d] else 0) - (1 if keys[pygame.K_a] else 0), (1 if keys[pygame.K_s] else 0) - (1 if keys[pygame.K_w] else 0))
        if mvv.length_squared() > 0:
            mvv = mvv.normalize()
        pl.guarding = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) and pl.can_act() and pl.action is None and pl.st > 5
        sp = pl.speed()
        if pl.action is not None:
            sp *= 0.25 if not pl.action.basic else 0.55
        if pl.charging:
            sp *= 0.45
        if not pl.can_move():
            sp = 0
        pl.vel = mvv * sp
        pl.walk = 1.0 if mvv.length_squared() > 0 and sp > 0 else 0
        # ресурсы
        if pl.guarding:
            pl.st = max(0, pl.st - 7 * dt)
        else:
            pl.st = min(pl.max_st, pl.st + (26 + pd.stats['agi'] * 0.2) * dt)
        if pl.armament:
            drain = max(1.5, 5.0 - pd.haki['arm'] * 0.35)
            pl.haki_g -= drain * dt
            if pl.haki_g <= 0:
                pl.haki_g = 0
                pl.armament = False
                self.notify("Хаки иссякло!", (200, 150, 255))
        else:
            pl.haki_g = min(pl.max_haki, pl.haki_g + (7 + pd.haki['arm']) * dt)
        pl.obs_t = max(0, pl.obs_t - dt)
        pl.obs_cd = max(0, pl.obs_cd - dt)
        pl.conq_cd = max(0, pl.conq_cd - dt)
        pl.dash_cd = max(0, pl.dash_cd - dt)
        pl.eat_cd = max(0, pl.eat_cd - dt)
        if getattr(pl, 'passive_regen', 0):
            pl.hp = min(pl.max_hp, pl.hp + pl.max_hp * pl.passive_regen * dt)
        if pl.awak_t > 0:
            pl.awak_t -= dt
            if pl.awak_t <= 0:
                pl.spread_terrain = None
        # ввод
        kp = g.kp
        mbp = g.mbp
        if 1 in mbp:
            pl.buffer = 'atk'
            pl.buffer_t = 0.28
        pl.buffer_t -= dt
        if pl.buffer_t <= 0:
            pl.buffer = None
        if pygame.K_LSHIFT in kp or pygame.K_RSHIFT in kp:
            pl.parry_window = 0.17
        if pygame.K_SPACE in kp:
            self.player_dash(mvv)
        if pl.can_act():
            # заряженный удар
            if g.mb[2] and pl.action is None and not pl.guarding:
                if not pl.charging:
                    pl.charging = True
                    pl.charge = 0
                pl.charge = min(1.0, pl.charge + dt * 1.1)
                if random.random() < dt * 30:
                    a = random.uniform(0, 6.28)
                    col = el(pl.combo_el)['c1'] if not pl.armament else (60, 30, 80)
                    self.particles.add(pl.pos.x + math.cos(a) * 50, pl.pos.y - 25 + math.sin(a) * 30, -math.cos(a) * 140, -math.sin(a) * 90, 0.35, 4, col, 'glow')
                if pl.charge >= 1.0 and int(self.t * 10) % 2 == 0:
                    pl.hitflash = 0.3
            elif pl.charging:
                pl.charging = False
                if pl.charge > 0.15:
                    mv = basic_move_for(pl, 3, heavy=True)
                    mult = 1.0 + 1.6 * pl.charge
                    pl.action = MoveRun(pl, None, mv, mw, charge=mult)
                    pl.action.basic = False
                    self.audio_play('hit_heavy' if pl.charge > 0.8 else 'whoosh', 0.7)
                    if pl.charge >= 1.0:
                        self.cam.punch(from_angle(pl.aim), 14)
                pl.charge = 0
            # базовая атака
            if pl.buffer == 'atk' and not pl.charging and not pl.guarding:
                ok = pl.action is None or (pl.action.basic and pl.action.t >= pl.action.end - 0.07)
                if ok and pl.attack_cd <= 0:
                    idx = pl.combo_i if pl.combo_t > 0 else 0
                    mv = basic_move_for(pl, idx)
                    pl.action = MoveRun(pl, None, mv, mw, basic=True)
                    pl.combo_i = (idx + 1) % 4
                    pl.combo_t = 0.6
                    if idx == 3:
                        pl.attack_cd = 0.3
                    pl.buffer = None
            # приёмы 1-4
            for i, key in enumerate((pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4)):
                if key in kp:
                    self.use_skill(i, mw)
            if pygame.K_r in kp:
                self.use_ult(mw)
            if pygame.K_f in kp:
                self.use_awakening()
            if pygame.K_q in kp:
                self.toggle_armament()
            if pygame.K_c in kp:
                self.use_observation()
            if pygame.K_z in kp:
                self.use_conqueror(mw)
            if pygame.K_x in kp:
                self.eat_food()
        if pygame.K_e in kp:
            self.interact()

    def player_dash(self, mvv):
        pl = self.player
        if pl.dash_cd > 0 or pl.st < 16 or not pl.can_move():
            return
        if pl.action is not None and not pl.action.basic and pl.action.armor:
            return
        if pl.action is not None:
            pl.action.cancel()
            pl.action = None
        d = mvv if mvv.length_squared() > 0 else from_angle(pl.aim)
        soru = STYLES[pl.style].get('soru')
        dist_ = 300 if soru else 190
        pl.st -= 16
        pl.dash_cd = 0.32
        pl.invuln = 0.26
        steps = 8
        for i in range(steps):
            np_ = pl.pos + d * (dist_ / steps)
            if self.is_blocked(np_.x, np_.y, pl.radius * 0.8, pl):
                break
            pl.pos = np_
            if i % 2 == 0:
                self.effects.append(AfterImageFX(pl, 0.25, (160, 200, 255) if not soru else (255, 255, 255)))
        self.particles.burst(pl.pos.x, pl.pos.y, 8, (220, 220, 210), 'dust', 150, 0.4, size=10)
        self.audio_play('whoosh', 0.5)
        if soru:
            self.particles.burst(pl.pos.x, pl.pos.y - 20, 6, (255, 255, 255), 'line', 400, 0.2)

    def use_skill(self, i, mw):
        pl = self.player
        pd = self.pd
        mid = pd.loadout[i] if i < len(pd.loadout) else None
        if not mid:
            return
        mv = MOVES[mid]
        if pl.cooldowns.get(mid, 0) > 0:
            return
        if pl.action is not None and not pl.action.basic:
            return
        cost = mv['cost']
        if pl.st < cost:
            self.float_text(pl.pos, "Мало выносливости!", (255, 220, 120), 14)
            return
        if pl.action is not None:
            pl.action.cancel()
        pl.st -= cost
        cdr = pl.stats.get('cdr', 0)
        pl.cooldowns[mid] = mv['cd'] * (1 - cdr)
        pl.action = MoveRun(pl, mid, mv, mw)
        self.float_text(pl.pos, mv['name'], (255, 255, 255), 15)
        if mv.get('scale') == 'fruit':
            pd.fruit_gain(0.25)
        else:
            pd.style_gain(pl.style, 0.25)

    def use_ult(self, mw):
        pl = self.player
        pd = self.pd
        # столкновение ультимейтов
        if self.boss is not None and not self.boss.dead and self.boss.action is not None and self.boss.action.ult and self.boss.action.t < 0.25:
            if pl.spirit >= 100 and dist(pl.pos, self.boss.pos) < 900:
                pl.spirit -= 100
                self.start_clash(self.boss)
                return
        if not pd.ult or pl.spirit < 100:
            if pd.ult:
                self.float_text(pl.pos, "Дух не накоплен!", (255, 220, 120), 14)
            return
        if pl.action is not None and not pl.action.basic:
            return
        mv = MOVES[pd.ult]
        pl.spirit -= 100
        if pl.action is not None:
            pl.action.cancel()
            pl.action = None
        def go():
            pl.action = MoveRun(pl, pd.ult, mv, self.mouse_world())
            pl.invuln = max(pl.invuln, mv.get('cast', 0.2) + 0.3)
            if mv.get('scale') == 'fruit':
                pd.fruit_gain(1.0)
            else:
                pd.style_gain(pl.style, 1.0)
        self.cutin(pl, mv, then=go)

    def awakening_info(self):
        pd = self.pd
        if pd.fruit and pd.fruit_mastery >= 100 and pd.level >= 50:
            return FRUITS[pd.fruit]['awak']
        if not pd.fruit and (pd.haki['arm'] >= 4 or pd.level >= 40):
            return dict(name="Режим Воли", form=None, dmg=1.5, defn=1.4, spd=1.2, dur=20, aura=(255, 220, 120))
        return None

    def use_awakening(self):
        pl = self.player
        aw = self.awakening_info()
        if aw is None:
            self.notify("Пробуждение недоступно: нужно 100% мастерства фрукта и 50 уровень (или хаки 4+ без фрукта).", (255, 200, 160))
            return
        if pl.spirit < 200:
            self.float_text(pl.pos, "Нужен полный Дух (2 сегмента)!", (255, 220, 120), 14)
            return
        pl.spirit = 0
        def go():
            b = dict(t=aw['dur'], dmg=aw['dmg'], defn=aw['defn'], spd=aw['spd'], aura=aw['aura'], form=aw.get('form'), regen=aw.get('regen', 0.0))
            pl.buffs.append(b)
            if aw.get('form'):
                pl.form = aw['form']
                if pl.form == 'dragon':
                    pl.hist = []
                pl.tint = (aw['aura'], 0.25) if aw['form'] not in ('gear5', 'dragon', 'giant', 'beast', 'sulong') else None
            pl.awak_t = aw['dur']
            pl.spread_terrain = aw.get('spread_terrain')
            pl.hp = min(pl.max_hp, pl.hp + pl.max_hp * 0.3)
            self.effects.append(RingFX(pl.pos, 10, 500, 1.0, aw['aura'], 14))
            nova_visual(self, pl.pos, 300, 'conq' if self.pd.haki['conq'] > 0 else 'haki_ring', el('conq'), {})
            for o in self.fighters:
                if o.hostile_to(pl) and dist(o.pos, pl.pos) < 300:
                    o.knock_v += from_angle(angle_to(pl.pos, o.pos), 900)
            self.notify(aw['name'].upper(), aw['aura'])
            self.flash(aw['aura'], 0.4)
            self.cam.add_shake(0.8)
        self.cutin(pl, dict(name=aw['name'], awak=True), then=go)

    def toggle_armament(self):
        pl = self.player
        pd = self.pd
        if pd.haki_cap['arm'] <= 0:
            self.notify("Хаки Вооружения ещё не пробудилось.", (200, 170, 255))
            return
        if pl.armament:
            pl.armament = False
            return
        if pl.haki_g < 10:
            return
        pl.armament = True
        self.audio_play('haki', 0.5)
        self.particles.burst(pl.pos.x, pl.pos.y - 25, 20, (40, 20, 60), 'dark', 150, 0.6, size=10)
        self.float_text(pl.pos, "Хаки Вооружения!" if not pl.ryou else "Рюо!", (200, 150, 255), 16)

    def use_observation(self):
        pl = self.player
        pd = self.pd
        if pd.haki_cap['obs'] <= 0:
            self.notify("Хаки Наблюдения ещё не пробудилось.", (200, 200, 255))
            return
        if pl.obs_cd > 0 or pl.haki_g < 25:
            return
        pl.haki_g -= 25
        pl.obs_t = 2.5 + 0.3 * pd.haki['obs'] + (1.0 if pl.fs else 0)
        pl.obs_cd = 6.0
        self.slowmo(0.4, 0.6)
        self.effects.append(RingFX(pl.pos, 10, 400, 0.7, (200, 200, 255) if not pl.fs else (255, 120, 200), 3))
        self.float_text(pl.pos, "Хаки Наблюдения" if not pl.fs else "ПРЕДВИДЕНИЕ БУДУЩЕГО", (220, 220, 255) if not pl.fs else (255, 150, 220), 18)
        self.audio_play('beam', 0.4)

    def use_conqueror(self, mw):
        pl = self.player
        pd = self.pd
        if pd.haki_cap['conq'] <= 0:
            if pd.trait == 'king':
                self.notify("В тебе дремлет Королевская воля... Она ещё не пробудилась.", (255, 120, 120))
            return
        if pl.conq_cd > 0 or pl.haki_g < 50:
            return
        pl.haki_g -= 50
        pl.conq_cd = 18
        mv = MOVES['conq_burst']
        pl.action = MoveRun(pl, 'conq_burst', mv, mw)
        pd.haki_gain('conq', 6)
        self.float_text(pl.pos, "КОРОЛЕВСКОЕ ХАКИ!", (255, 80, 80), 26)
        if self.boss is not None and not self.boss.dead and self.boss.haki_always and dist(self.boss.pos, pl.pos) < 500 and self.boss.level >= 40:
            self.conq_clash_fx(self.boss)

    def conq_clash_fx(self, b):
        mid = (self.player.pos + b.pos) / 2
        for i in range(14):
            a = random.uniform(0, 6.28)
            self.effects.append(BoltFX(mid + V(0, -40), mid + V(0, -40) + from_angle(a, random.uniform(150, 450)), black=True, life=0.9, width=5, amp=30))
        self.flash((60, 0, 10), 0.6)
        self.cam.add_shake(1.0)
        self.float_text(mid, "СТОЛКНОВЕНИЕ КОРОЛЕЙ!", (255, 60, 60), 30)
        self.audio_play('thunder', 1.0)
        for f in (self.player, b):
            f.knock_v += from_angle(angle_to(mid, f.pos), 600)

    def eat_food(self):
        pl = self.player
        pd = self.pd
        if pl.eat_cd > 0:
            return
        foods = [it for it in pd.inventory if it.get('kind') == 'food']
        if not foods:
            self.float_text(pl.pos, "Нет еды!", (255, 200, 160), 14)
            return
        foods.sort(key=lambda it: it.get('heal', 0))
        it = None
        need = 1 - pl.hp / pl.max_hp
        for f in foods:
            if f.get('heal', 0) >= need * 0.9:
                it = f
                break
        it = it or foods[-1]
        pd.inventory.remove(it)
        if it.get('heal'):
            amt = pl.max_hp * it['heal']
            pl.hp = min(pl.max_hp, pl.hp + amt)
            self.float_text(pl.pos, "+" + fmt_num(amt), (120, 255, 140), 20)
        if it.get('stam'):
            pl.st = pl.max_st
        if it.get('haki_restore'):
            pl.haki_g = pl.max_haki
        if it.get('buff'):
            k, v, d = it['buff']
            if k == 'dmg':
                pl.buffs.append(dict(t=d, dmg=v, aura=(255, 200, 120)))
        pl.eat_cd = 1.2
        pl.set_pose('punch', 0.4)
        self.audio_play('eat', 0.8)
        self.particles.burst(pl.pos.x, pl.pos.y - 30, 10, (255, 230, 180), 'glow', 120, 0.5, size=4)

    # ---------------- взаимодействие ----------------
    def best_interaction(self):
        pl = self.player
        best = None
        bd = 80
        for n in self.npcs:
            if n.role == 'villager':
                continue
            d = dist(n.pos, pl.pos)
            if d < bd:
                bd = d
                best = ('npc', n)
        for s in self._structs_near(pl.pos, 70):
            if s.destroyed:
                continue
            if s.kind == 'chest' and not self.ist.get('chest'):
                best = ('chest', s)
            elif s.kind == 'water_barrel' and best is None:
                best = ('water', s)
        if self.deck is None and (dist(self.map.dock, pl.pos) < 130 or dist(self.map.spawn, pl.pos) < 70) and best is None:
            if best is None:
                best = ('dock', None)
        if self.isl.get('extra_boss') and self.ist.get('done') and not self.ist.get('extra') and not self.boss_spawned:
            if dist(pl.pos, self.map.arena) < 200:
                best = ('extra', None)
        return best

    def interact(self):
        bi = self.best_interaction()
        if not bi:
            return
        kind, obj = bi
        g = self.game
        if kind == 'npc':
            if obj.role == 'mentor':
                g.open_mentor(obj.data, self)
            else:
                g.open_service(obj.role, self)
        elif kind == 'chest':
            self.open_chest(obj)
        elif kind == 'water':
            self.player.add_status('wet', 25)
            self.particles.burst(self.player.pos.x, self.player.pos.y - 30, 20, (90, 160, 255), 'water', 200, 0.6, size=4, z=20, vz=100, grav=500)
            self.notify("Ты облился водой! Песок и дым теперь уязвимы для тебя (25 сек).", (120, 200, 255))
            self.audio_play('splash', 0.7)
        elif kind == 'dock':
            if self.boss is not None and not self.boss.dead and self.boss_spawned:
                self.notify("Нельзя сбежать посреди битвы с боссом!", (255, 150, 150))
                return
            g.leave_island(self)
        elif kind == 'extra':
            bid = self.isl['extra_boss']
            def yes():
                self.ist['extra'] = False
                self.start_boss(bid, rematch=True, level_bonus=6)
            g.confirm(f"Бросить вызов: {BOSSES[bid]['name']}? Это очень опасно!", yes)

    def open_chest(self, s):
        pd = self.pd
        self.ist['chest'] = True
        s.destroyed = True
        self.map.occ[s.ty:s.ty + s.th, s.tx:s.tx + s.tw] = -1
        self.audio_play('coin', 1.0)
        self.particles.burst(s.center().x, s.center().y, 40, (255, 220, 80), 'glow', 300, 1.0, size=5)
        beli = int(2000 * (1 + self.lvl * 0.6) * random.uniform(0.8, 1.3))
        pd.beli += beli
        msgs = [f"Сундук: +{fmt_num(beli)} ฿"]
        for _ in range(2):
            self.drop_item(s.center())
        cf = self.isl.get('chest_fruit')
        if cf and self.rng.random() < 0.55:
            it = fruit_item(cf)
            pd.inventory.append(it)
            msgs.append("ДЬЯВОЛЬСКИЙ ФРУКТ: " + it['name'] + "!")
            self.flash((255, 220, 255), 0.3)
            self.audio_play('levelup', 1.0)
        for m in msgs:
            self.notify(m, (255, 220, 90))

    # ---------------- спарринг с наставником ----------------
    def start_spar(self, mid):
        M = MENTORS[mid]
        npc = next((n for n in self.npcs if n.role == 'mentor' and n.data == mid), None)
        pos = npc.pos + V(0, 80) if npc else self.player.pos + V(150, 0)
        lvl = self.pd.level + 2
        app = dict(M['app'])
        f = Fighter(self, 'enemy', app, pos, lvl, M['name'], 'boss', 7.0, 1.0, 210)
        st = M.get('style')
        if st:
            f.combo_def = STYLES[st]['combo']
            f.moves = [m for _, m in STYLES[st]['moves']][:4]
            f.combo_el = STYLES[st].get('el', 'phys')
        else:
            f.moves = ['fist_love', 'ryuo_wave', 'iai_shishi']
            f.haki_always = True
        f.ai = AIController(f, 'melee')
        f.ai.aggro = True
        f.dodge = 0.15
        f.spar = True
        f.boss_id = None
        self.spar = f
        self.spar_mid = mid
        if npc:
            npc.hidden = True
            self.npcs.remove(npc)
            self.spar_npc = npc
        self.fighters.append(f)
        self.boss = f
        self.notify("Спарринг! Сбей наставнику 85% здоровья.", (255, 220, 120))
        self.game.audio.play_music('battle', fade=600)

    def update_spar(self):
        f = self.spar
        pl = self.player
        won = f.hp <= f.max_hp * 0.15 or f.dead
        lost = pl.hp <= pl.max_hp * 0.12 or pl.dead
        if not won and not lost:
            return
        f.remove = True
        f.dead = True
        if pl.dead:
            pl.dead = False
        pl.hp = max(pl.hp, pl.max_hp * 0.4)
        self.defeat_t = None
        self.boss = None
        self.spar = None
        if hasattr(self, 'spar_npc'):
            self.npcs.append(self.spar_npc)
        self.game.audio.play_music(self.music)
        self.time_scale = 1.0
        self.slow_t = 0
        if won:
            self.game.mentor_success(self.spar_mid, self)
        else:
            self.game.dialogue([(self.spar_mid, "Ещё слабоват. Возвращайся, когда станешь сильнее.")], None)

    # ---------------- катсцены ----------------
    def cutin(self, f, mv, enemy=False, then=None):
        self.cutin_state = dict(t=0.0, dur=1.15 if not enemy else 0.95, f=f, mv=mv, enemy=enemy, then=then,
                                lines=[(random.uniform(0, H), random.uniform(0.5, 1.5)) for _ in range(30)])
        self.audio_play('ult', 0.9)

    def update_cutin(self, dt):
        c = self.cutin_state
        c['t'] += dt
        if c['t'] >= c['dur']:
            self.cutin_state = None
            self.flash((255, 255, 255), 0.18)
            self.cam.add_shake(0.4)
            self.speed_t = 0.7
            if not c['enemy']:
                self.cam.zoom = 1.18
                self.cam.target_zoom = 1.0
            if c['then']:
                c['then']()

    def start_clash(self, boss):
        self.clash = dict(t=0.0, boss=boss, power=0.5, mv=boss.action.mv if boss.action else None)
        self.audio_play('ult', 1.0)
        self.notify("СТОЛКНОВЕНИЕ! Жми ЛКМ / Space!", (255, 230, 120))

    def update_clash(self, dt):
        c = self.clash
        g = self.game
        c['t'] += dt
        b = c['boss']
        pl = self.player
        push = 0.36 + 0.02 * (b.level - pl.level)
        c['power'] -= push * dt
        if 1 in g.mbp or pygame.K_SPACE in g.kp:
            c['power'] += 0.055
            self.cam.add_shake(0.15)
            self.audio_play('hit', 0.4, cooldown=0.02)
        self.cam.update(dt, (pl.pos + b.pos) / 2)
        mid = pl.pos + (b.pos - pl.pos) * clamp(c['power'], 0.1, 0.9)
        if random.random() < 0.7:
            self.particles.burst(mid.x, mid.y - 30, 4, (255, 240, 200), 'spark', 600, 0.3)
        self.particles.update(dt)
        self.effects = [e for e in self.effects if e.update(dt)]
        if c['power'] >= 1.0 or c['power'] <= 0.0 or c['t'] > 4.0:
            win = c['power'] >= 0.5
            self.clash = None
            if win:
                if b.action:
                    b.action.cancel()
                    b.action = None
                b.hp -= b.max_hp * 0.14
                b.stagger = 1.8
                b.knock_v += from_angle(angle_to(pl.pos, b.pos), 900)
                self.effects.append(ImpactStarFX(V(b.pos.x, b.pos.y - 30), 120, 0.4, (255, 240, 180), 12))
                self.float_text(b.pos, "ПРОРЫВ!", (255, 230, 80), 34)
                self.impact_frame(4)
                self.flash((255, 255, 255), 0.4)
                pl.spirit = min(200, pl.spirit + 40)
                if b.hp <= 0:
                    b.die(pl)
            else:
                pl.hp -= pl.max_hp * 0.25
                pl.knock_v += from_angle(angle_to(b.pos, pl.pos), 800)
                pl.stagger = 0.8
                self.float_text(pl.pos, "Сила врага сильнее...", (255, 120, 120), 22)
                self.flash((255, 80, 80), 0.3)
                if pl.hp <= 0:
                    pl.die(b)
            self.cam.add_shake(1.0)
            self.audio_play('explosion', 1.0)

    # ---------------- погода ----------------
    def _init_weather(self):
        self.weather = []
        w_ = self.isl.get('weather')
        n = {'snow': 140, 'sand': 90, 'petals': 60, 'bubbles': 40, 'fog': 0, 'rain': 160}.get(w_, 0)
        for _ in range(n):
            self.weather.append([random.uniform(0, W), random.uniform(0, H), random.uniform(0.5, 1.5)])

    def update_weather(self, dt):
        w_ = self.isl.get('weather')
        for p in self.weather:
            k = p[2]
            if w_ == 'snow':
                p[0] += math.sin(self.t + p[1] * 0.01) * 20 * dt
                p[1] += 50 * k * dt
            elif w_ == 'sand':
                p[0] += 420 * k * dt
                p[1] += 40 * k * dt
            elif w_ == 'petals':
                p[0] += (60 + math.sin(self.t * 2 + p[1]) * 40) * dt
                p[1] += 40 * k * dt
            elif w_ == 'bubbles':
                p[1] -= 40 * k * dt
                p[0] += math.sin(self.t * 2 + p[1] * 0.03) * 20 * dt
            elif w_ == 'rain':
                p[0] += -120 * dt
                p[1] += 900 * k * dt
            if p[1] > H + 10:
                p[1] = -10
                p[0] = random.uniform(0, W)
            if p[1] < -12:
                p[1] = H + 10
            if p[0] > W + 10:
                p[0] = -10
            if p[0] < -10:
                p[0] = W + 10

    def draw_weather(self, scr):
        w_ = self.isl.get('weather')
        if w_ == 'snow':
            for p in self.weather:
                pygame.draw.circle(scr, (250, 250, 255), (int(p[0]), int(p[1])), int(1 + p[2] * 1.5))
        elif w_ == 'sand':
            for p in self.weather:
                pygame.draw.line(scr, (230, 200, 140), (p[0], p[1]), (p[0] - 18 * p[2], p[1] - 2), 2)
        elif w_ == 'petals':
            for p in self.weather:
                pygame.draw.ellipse(scr, (255, 180, 210), (p[0], p[1], 6 * p[2], 4 * p[2]))
        elif w_ == 'bubbles':
            for p in self.weather:
                pygame.draw.circle(scr, (220, 240, 255), (int(p[0]), int(p[1])), int(3 + p[2] * 4), 1)
        elif w_ == 'rain':
            for p in self.weather:
                pygame.draw.line(scr, (180, 200, 230), (p[0], p[1]), (p[0] + 3, p[1] - 14), 1)
        elif w_ == 'fog':
            if not hasattr(self, '_fog'):
                self._fog = pygame.Surface((W, H), pygame.SRCALPHA)
                n = value_noise_2d(W // 8, H // 8, 12, 5, 3)
                arr = (np.clip(n * 1.4 - 0.2, 0, 1) * 120).astype(np.uint8)
                small = pygame.Surface((W // 8, H // 8), pygame.SRCALPHA)
                small.fill((200, 210, 220, 0))
                pa = pygame.surfarray.pixels_alpha(small)
                pa[:] = arr.T
                del pa
                self._fog = pygame.transform.smoothscale(small, (W * 2, H))
            off = int(self.t * 20) % W
            scr.blit(self._fog, (-off, 0))

    # ---------------- отрисовка ----------------
    def draw(self, screen):
        cam = self.cam
        vw, vh = cam.view_size()
        if abs(cam.zoom - 1.0) > 0.01:
            if self.view_surf is None or self.view_surf.get_size() != (vw, vh):
                self.view_surf = pygame.Surface((vw, vh))
            view = self.view_surf
        else:
            view = screen
            self.view_surf = None
        ox, oy = cam.offset(vw, vh)
        ox, oy = int(ox), int(oy)
        self.map.draw_ground(view, ox, oy)
        if self.deck is None:
            draw_moored_ship(view, self.map.ship_pos.x - ox, self.map.ship_pos.y - oy, self.pd.ship, self.t)
        for z in self.zones:
            z.draw(view, ox, oy)
        for e in self.effects:
            if e.layer == 0:
                e.draw(view, ox, oy)
        # маркер босса
        bm = getattr(self, 'boss_marker', None)
        obj = self.cur_obj()
        if bm is not None and not self.boss_spawned and ((obj and obj['type'] == 'boss') or getattr(self, 'rematch', None)):
            mx, my = bm.x - ox, bm.y - oy
            pulse = 0.5 + 0.5 * math.sin(self.t * 4)
            pygame.draw.ellipse(view, (255, 80, 60), (mx - 90, my - 40, 180, 80), 3)
            draw_glow(view, (mx, my), 90 + 20 * pulse, (255, 60, 40), 0.25)
            draw_text(view, "★", (mx, my - 60 - pulse * 8), 34, (255, 210, 60), "center", 3)
        # y-сортировка
        items = []
        vis_r = pygame.Rect(ox - 200, oy - 300, vw + 400, vh + 500)
        for s in self.map.structs:
            if not s.destroyed:
                r = s.rect()
                if vis_r.colliderect(r):
                    items.append((s.base_y(), 0, s))
        for f in self.fighters:
            items.append((f.pos.y, 1, f))
        for n in self.npcs:
            items.append((n.pos.y, 2, n))
        items.sort(key=lambda it: it[0])
        theme = self.map.theme
        for _, k, obj_ in items:
            if k == 0:
                draw_structure(view, obj_, ox, oy, theme, self.t)
            else:
                obj_.draw(view, ox, oy)
        for p in self.projectiles:
            p.draw(view, ox, oy)
        for e in self.effects:
            if e.layer >= 1:
                e.draw(view, ox, oy)
        self.particles.draw(view, ox, oy)
        for tx in self.texts:
            a = clamp(tx.life / tx.max * 2, 0, 1)
            sc = 1.0 + (0.6 if tx.crit else 0.25) * max(0, (tx.life / tx.max - 0.75) * 4)
            draw_text(view, tx.text, (tx.x - ox, tx.y - oy), int(tx.size * sc), tx.col, "center", 2, alpha=int(255 * a))
        if self.isl['theme'] in ('ghost', 'prison', 'pirate_isle'):
            dark = pygame.Surface((vw, vh), pygame.SRCALPHA)
            dark.fill((10, 10, 30, 90))
            view.blit(dark, (0, 0))
        if view is not screen:
            pygame.transform.smoothscale(view, (W, H), screen)
        self.draw_weather(screen)
        if self.flash_t > 0 and self.flash_col:
            a = int(130 * self.flash_t / max(0.01, self.flash_max))
            fl = pygame.Surface((W, H))
            fl.fill(self.flash_col)
            fl.set_alpha(a)
            screen.blit(fl, (0, 0))
        if self.impact_n > 0:
            self.impact_n -= 1
            gs = pygame.transform.grayscale(screen)
            inv = pygame.Surface((W, H))
            inv.fill((255, 255, 255))
            inv.blit(gs, (0, 0), special_flags=pygame.BLEND_RGB_SUB)
            screen.blit(inv, (0, 0))
        st_ = getattr(self, 'speed_t', 0)
        if st_ > 0:
            self.speed_t = st_ - 1 / 60
            k = st_ / 0.7
            lines = pygame.Surface((W, H), pygame.SRCALPHA)
            rng = random.Random(int(self.t * 30))
            for i in range(46):
                a = rng.uniform(0, 6.28)
                r0 = rng.uniform(330, 520)
                r1 = r0 + rng.uniform(200, 500)
                cx, cy = W / 2, H / 2
                pygame.draw.line(lines, (255, 255, 255, int(170 * k)), (cx + math.cos(a) * r0, cy + math.sin(a) * r0 * 0.7),
                                 (cx + math.cos(a) * r1, cy + math.sin(a) * r1 * 0.7), rng.randint(2, 5))
            screen.blit(lines, (0, 0))
        if self.player.obs_t > 0:
            tint = pygame.Surface((W, H), pygame.SRCALPHA)
            tint.fill((120, 60, 160, 40) if self.player.fs else (60, 60, 140, 35))
            screen.blit(tint, (0, 0))
        self.draw_hud(screen)
        if self.cine is not None:
            self.draw_boss_intro(screen)
        if self.cutin_state is not None:
            self.draw_cutin(screen)
        if self.clash is not None:
            self.draw_clash(screen)
        if self.victory_t is not None:
            self.draw_victory(screen)
        if self.defeat_t is not None:
            self.draw_defeat(screen)

    def draw_boss_intro(self, scr):
        c = self.cine
        t = c['t']
        k = ease_out(min(1, t / 0.4))
        bh = int(90 * k)
        pygame.draw.rect(scr, (0, 0, 0), (0, 0, W, bh))
        pygame.draw.rect(scr, (0, 0, 0), (0, H - bh, W, bh))
        if t > 0.5:
            k2 = ease_out(min(1, (t - 0.5) / 0.4))
            out = max(0, (t - c['dur'] + 0.4) / 0.4)
            x0 = -W + k2 * W - out * W
            band = [(x0 + 0, H * 0.58), (x0 + W * 1.1, H * 0.5), (x0 + W * 1.1, H * 0.72), (x0 + 0, H * 0.8)]
            pygame.draw.polygon(scr, (150, 20, 30), band)
            pygame.draw.polygon(scr, (20, 5, 10), band, 4)
            draw_text(scr, c['name'], (x0 + W * 0.5, H * 0.6), 54, (255, 255, 255), "center", 4)
            draw_text(scr, "«" + c['title'] + "»", (x0 + W * 0.5, H * 0.68), 26, (255, 220, 160), "center", 3)
            if c['bounty']:
                draw_text(scr, "Награда: ฿ " + fmt_num(c['bounty']), (x0 + W * 0.5, H * 0.74), 22, (255, 230, 100), "center", 2)

    def draw_cutin(self, scr):
        c = self.cutin_state
        t = c['t']
        dur = c['dur']
        f = c['f']
        enemy = c['enemy']
        k = ease_out(min(1, t / 0.25))
        out = max(0, (t - dur + 0.2) / 0.2)
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, int(150 * k * (1 - out))))
        scr.blit(dim, (0, 0))
        col = FACTIONS[self.pd.faction]['col'] if not enemy else (140, 10, 20)
        y0, y1 = H * 0.25, H * 0.75
        slide = (1 - k) * (W if not enemy else -W) + out * (-W if not enemy else W)
        band = [(slide - 50, y0 + 60), (slide + W + 50, y0), (slide + W + 50, y1 - 60), (slide - 50, y1)]
        pygame.draw.polygon(scr, col, band)
        pygame.draw.polygon(scr, (255, 255, 255), band, 5)
        cx = W * 0.5 + slide
        for (ly, sp) in c['lines']:
            if y0 < ly < y1:
                lx = (t * 3000 * sp + ly * 7) % (W + 400) - 200
                pygame.draw.line(scr, add_col(col, 60), (lx + slide, ly), (lx + slide + 150 * sp, ly - 20 * sp), 2)
        pr = pygame.Rect(0, 0, 380, 380)
        if not enemy:
            pr.midbottom = (W * 0.27 + slide * 1.2, y1 + 20)
        else:
            pr.midbottom = (W * 0.73 + slide * 1.2, y1 + 20)
        draw_portrait(scr, pr, f.draw_app() if hasattr(f, 'draw_app') else f.app, 'ult', facing_right=not enemy)
        name = c['mv'].get('name', '')
        tx = W * 0.62 + slide * 0.8 if not enemy else W * 0.36 + slide * 0.8
        lab = "ПРОБУЖДЕНИЕ" if c['mv'].get('awak') else ("УЛЬТИМЕЙТ" if not enemy else "ОПАСНОСТЬ!")
        draw_text(scr, lab, (tx, H * 0.36), 24, (255, 230, 120), "center", 3)
        fs_ = 50 if len(name) < 22 else (40 if len(name) < 30 else 32)
        lines = wrap_text(get_font(fs_), name, 560)
        for i, ln in enumerate(lines):
            draw_text(scr, ln, (tx, H * 0.46 + i * (fs_ + 6)), fs_, (255, 255, 255), "center", 4)
        draw_text(scr, f.name if not enemy else f.name, (tx, H * 0.62), 22, (255, 255, 255), "center", 2)

    def draw_clash(self, scr):
        c = self.clash
        b = c['boss']
        pl = self.player
        vw, vh = self.cam.view_size()
        ox, oy = self.cam.offset(vw, vh)
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 20, 120))
        scr.blit(dim, (0, 0))
        a = V(pl.pos.x - ox, pl.pos.y - oy - 30)
        bb = V(b.pos.x - ox, b.pos.y - oy - 30)
        mid = a + (bb - a) * clamp(c['power'], 0.05, 0.95)
        pc = FACTIONS[self.pd.faction]['col']
        ec = (220, 40, 60)
        wob = math.sin(self.t * 40) * 4
        pygame.draw.line(scr, pc, a, mid, int(26 + wob))
        pygame.draw.line(scr, (255, 255, 255), a, mid, 8)
        pygame.draw.line(scr, ec, bb, mid, int(26 - wob))
        pygame.draw.line(scr, (255, 255, 255), bb, mid, 8)
        draw_glow(scr, mid, 120 + wob * 5, (255, 240, 200), 1.0)
        pygame.draw.circle(scr, (255, 255, 255), (int(mid.x), int(mid.y)), 30)
        r = pygame.Rect(W / 2 - 300, H - 120, 600, 26)
        bar(scr, r, c['power'], pc, bg=ec)
        draw_text(scr, "ЖМИ ЛКМ / SPACE!", (W / 2, H - 150), 34, (255, 240, 150), "center", 3)

    def draw_victory(self, scr):
        t = self.victory_t
        k = ease_back(min(1, t / 0.6))
        cx, cy = W / 2, H * 0.35
        for i in range(16):
            a = i / 16 * 6.28 + t * 0.5
            pygame.draw.polygon(scr, (255, 220, 120), [(cx, cy), (cx + math.cos(a) * 900, cy + math.sin(a) * 900), (cx + math.cos(a + 0.12) * 900, cy + math.sin(a + 0.12) * 900)])
        draw_text(scr, "ПОБЕДА!", (cx, cy), int(90 * k) + 10, (255, 230, 90), "center", 6, (80, 30, 0))

    def draw_defeat(self, scr):
        t = self.defeat_t
        a = int(min(1, t / 1.2) * 180)
        s = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill((20, 0, 0, a))
        scr.blit(s, (0, 0))
        if t > 1.0:
            draw_text(scr, "ПОРАЖЕНИЕ", (W / 2, H * 0.4), 80, (230, 60, 60), "center", 5)
            draw_text(scr, "Space — очнуться у причала (−10% белли)      Esc — вернуться на корабль", (W / 2, H * 0.55), 22, (255, 230, 230), "center", 2)
            g = self.game
            if pygame.K_SPACE in g.kp:
                self.respawn_player()
            elif pygame.K_ESCAPE in g.kp:
                self.respawn_player()
                g.leave_island(self)

    # ---------------- HUD ----------------
    def draw_hud(self, scr):
        pl = self.player
        pd = self.pd
        # портрет и полосы
        px, py = 18, H - 128
        panel(scr, (px - 6, py - 8, 360, 128), (15, 18, 30), 190, (200, 170, 110), 12)
        if not hasattr(self, '_por') or self.t - getattr(self, '_por_t', -99) > 5:
            self._por = pygame.Surface((76, 76), pygame.SRCALPHA)
            draw_portrait(self._por, (0, 0, 76, 76), pl.draw_app(), 'normal')
            self._por_t = self.t
        pygame.draw.circle(scr, (30, 30, 40), (px + 38, py + 40), 40)
        scr.blit(self._por, (px, py + 2))
        pygame.draw.circle(scr, (220, 190, 120), (px + 38, py + 40), 40, 3)
        draw_text(scr, f"Ур. {pd.level}", (px + 38, py + 86), 16, (255, 230, 150), "midtop", 2)
        bx = px + 88
        bar(scr, (bx, py + 6, 250, 18), pl.hp / pl.max_hp, (215, 50, 50), ghost=pl.ghost_hp / pl.max_hp)
        draw_text(scr, f"{fmt_num(max(0, pl.hp))} / {fmt_num(pl.max_hp)}", (bx + 125, py + 6), 14, (255, 255, 255), "midtop", 2)
        bar(scr, (bx, py + 30, 200, 10), pl.st / pl.max_st, (240, 200, 60))
        if pd.haki_cap['arm'] > 0 or pd.haki_cap['obs'] > 0:
            bar(scr, (bx, py + 46, 200, 10), pl.haki_g / pl.max_haki, (160, 90, 220) if not pl.armament else (210, 120, 255))
            draw_text(scr, "Хаки", (bx + 206, py + 43), 13, (200, 160, 255), "topleft", 2)
        draw_text(scr, "Выносл.", (bx + 206, py + 27), 13, (240, 210, 120), "topleft", 2)
        # дух
        sx = bx
        sy = py + 64
        for i in range(2):
            frac = clamp((pl.spirit - i * 100) / 100, 0, 1)
            r = pygame.Rect(sx + i * 128, sy, 122, 14)
            col = (255, 200, 60) if frac >= 1 else (200, 150, 50)
            bar(scr, r, frac, col)
            if frac >= 1:
                draw_glow(scr, r.center, 40, (255, 200, 80), 0.4 + 0.3 * math.sin(self.t * 6))
        draw_text(scr, "ДУХ", (sx, sy + 16), 13, (255, 220, 130), "topleft", 2)
        xpn = xp_need(pd.level)
        bar(scr, (sx + 40, sy + 22, 216, 6), pd.xp / xpn, (120, 200, 255))
        # слоты приёмов
        slots_x = W / 2 - 250
        sy2 = H - 76
        for i in range(4):
            mid = pd.loadout[i] if i < len(pd.loadout) else None
            r = pygame.Rect(slots_x + i * 66, sy2, 58, 58)
            panel(scr, r, (20, 22, 35), 210, (150, 140, 110), 8)
            if mid:
                move_icon(scr, r.center, 24, mid, pl.st >= MOVES[mid]['cost'])
                cd = pl.cooldowns.get(mid, 0)
                if cd > 0:
                    frac = cd / max(0.1, MOVES[mid]['cd'])
                    alpha_rect(scr, (r.x, r.y + r.h * (1 - frac), r.w, r.h * frac), (0, 0, 0), 150)
                    draw_text(scr, f"{cd:.0f}" if cd >= 1 else f"{cd:.1f}", r.center, 18, (255, 255, 255), "center", 2)
            draw_text(scr, str(i + 1), (r.x + 4, r.y + 2), 14, (255, 230, 150), "topleft", 2)
        # ульта
        r = pygame.Rect(slots_x + 4 * 66 + 10, sy2 - 8, 70, 70)
        ready = pl.spirit >= 100 and pd.ult
        panel(scr, r, (40, 25, 15), 220, (255, 200, 80) if ready else (120, 100, 70), 10, 3)
        if pd.ult:
            move_icon(scr, r.center, 28, pd.ult, ready)
            if ready:
                draw_glow(scr, r.center, 60, (255, 200, 80), 0.35 + 0.25 * math.sin(self.t * 6))
        draw_text(scr, "R", (r.x + 5, r.y + 3), 16, (255, 230, 150), "topleft", 2)
        r2 = pygame.Rect(r.right + 8, sy2, 58, 58)
        aw = self.awakening_info()
        panel(scr, r2, (30, 20, 40), 220, (255, 120, 255) if (aw and pl.spirit >= 200) else (90, 70, 100), 8)
        draw_text(scr, "F", (r2.x + 4, r2.y + 2), 14, (255, 200, 255), "topleft", 2)
        draw_text(scr, "ПРОБ." if aw else "—", r2.center, 14, (255, 200, 255) if aw else (120, 110, 130), "center", 2)
        # хаки
        hx = r2.right + 14
        for j, (key, kind, label) in enumerate((('Q', 'arm', "Воор."), ('C', 'obs', "Набл."), ('Z', 'conq', "Корол."))):
            rr = pygame.Rect(hx + j * 52, sy2 + 6, 46, 46)
            unlocked = pd.haki_cap[kind] > 0
            active = (kind == 'arm' and pl.armament) or (kind == 'obs' and pl.obs_t > 0)
            col = {'arm': (130, 60, 200), 'obs': (90, 120, 230), 'conq': (210, 40, 60)}[kind]
            panel(scr, rr, mul_col(col, 0.35) if unlocked else (25, 25, 30), 220, col if unlocked else (60, 60, 70), 8, 3 if active else 2)
            if active:
                draw_glow(scr, rr.center, 40, col, 0.6)
            draw_text(scr, key, (rr.x + 4, rr.y + 2), 13, (255, 255, 255) if unlocked else (100, 100, 110), "topleft", 2)
            draw_text(scr, str(pd.haki[kind]) if unlocked else "—", rr.center, 18, (255, 255, 255) if unlocked else (90, 90, 100), "center", 2)
            draw_text(scr, label, (rr.centerx, rr.bottom + 1), 11, (200, 200, 220), "midtop", 1)
        nmeat = sum(1 for it in pd.inventory if it.get('kind') == 'food')
        draw_text(scr, f"X: еда ×{nmeat}", (W / 2 - 250, sy2 - 22), 15, (255, 220, 180), "topleft", 2)
        # остров и задача
        draw_text(scr, self.isl['name'] if self.deck is None else "Абордаж", (18, 12), 22, (255, 240, 200), "topleft", 3)
        obj = self.cur_obj()
        oy = 42
        if obj:
            txt = obj['text']
            if obj['type'] == 'groups':
                txt += f"  ({obj['done']}/{obj['need']})"
            elif obj['type'] == 'mids':
                txt += ": " + ", ".join(BOSSES[b]['name'] for b in obj['left'])
            panel(scr, (12, oy - 4, min(620, get_font(16).size(txt)[0] + 40), 30), (15, 18, 30), 180, (200, 170, 110), 8)
            draw_text(scr, "▶ " + txt, (22, oy), 16, (255, 230, 150), "topleft", 2)
            self._arrow_tgt = self.objective_target()
        elif self.ist.get('done') and self.deck is None:
            draw_text(scr, "Остров пройден. Причал (E) — вернуться на корабль.", (22, oy), 15, (200, 230, 200), "topleft", 2)
        # деньги / награда
        rep = self.pd.title()
        draw_text(scr, f"฿ {fmt_num(pd.beli)}", (W - 18, 182), 18, (255, 220, 90), "topright", 2)
        rv = pd.bounty if pd.faction in ('pirate', 'revo', 'lunar') else pd.merit
        lbl = FACTIONS[pd.faction]['rep_name']
        val = ("฿ " + fmt_beli(pd.bounty)) if pd.faction in ('pirate',) else fmt_num(pd.merit)
        draw_text(scr, f"{lbl}: {val}", (W - 18, 204), 15, (255, 200, 200), "topright", 2)
        if pd.faction in ('revo', 'hunter', 'marine') and pd.bounty > 0:
            draw_text(scr, f"Награда: ฿ {fmt_beli(pd.bounty)}", (W - 18, 224), 14, (255, 170, 170), "topright", 2)
        draw_text(scr, rep, (W - 18, 244 if pd.bounty and pd.faction != 'pirate' else 224), 14, (220, 220, 255), "topright", 2)
        self.draw_minimap(scr)
        if obj and getattr(self, '_arrow_tgt', None) is not None:
            self.draw_edge_arrow(scr, self._arrow_tgt)
        # босс
        b = self.boss
        if b is not None and not b.dead and self.cine is None:
            bw = 560
            bxp = W / 2 - bw / 2
            panel(scr, (bxp - 10, 6, bw + 20, 50), (20, 8, 10), 200, (220, 80, 80), 8)
            draw_text(scr, b.name + ("  «" + getattr(b, 'title', '') + "»" if getattr(b, 'title', '') else ""), (W / 2, 9), 17, (255, 230, 220), "midtop", 2)
            bar(scr, (bxp, 32, bw, 14), b.hp / b.max_hp, (210, 40, 50), ghost=b.ghost_hp / b.max_hp, ghost_col=(255, 220, 200))
            if b.logia and not b.has('nullified'):
                draw_text(scr, "ЛОГИЯ", (bxp + bw - 4, 9), 13, (255, 220, 120), "topright", 2)
        if b is not None and not b.dead and b.action is not None and b.action.ult and b.action.t < 0.25:
            if pl.spirit >= 100 and int(self.t * 8) % 2 == 0:
                draw_text(scr, "R — СТОЛКНОВЕНИЕ!", (W / 2, H * 0.3), 44, (255, 220, 80), "center", 4, (120, 20, 20))
            elif pl.spirit < 100:
                draw_text(scr, "Босс готовит ультимейт! Уходи из красной зоны!", (W / 2, H * 0.3), 26, (255, 140, 120), "center", 3)
        # комбо
        if self.combo >= 3:
            k = 1 + 0.3 * max(0, self.combo_t - 1.9) * 3
            col = (255, 255, 255) if self.combo < 15 else ((255, 220, 80) if self.combo < 40 else (255, 90, 60))
            draw_text(scr, f"{self.combo}", (W - 40, H * 0.42), int(54 * k), col, "topright", 4)
            draw_text(scr, "УДАРОВ!", (W - 40, H * 0.42 + 56 * k), 20, col, "topright", 2)
        # уведомления
        for i, (txt, col, t) in enumerate(self.notifications):
            a = clamp(t * 2, 0, 1)
            draw_text(scr, txt, (W / 2, 70 + i * 28), 19, col, "midtop", 3, alpha=int(255 * a))
        # подсказка взаимодействия
        bi = self.best_interaction()
        if bi:
            kind, obj_ = bi
            txt = {'npc': lambda: "E — " + (obj_.name if obj_.role == 'mentor' else ROLE_NAMES.get(obj_.role, obj_.name)),
                   'chest': lambda: "E — открыть сундук", 'water': lambda: "E — облиться водой", 'dock': lambda: "E — вернуться на корабль",
                   'extra': lambda: "E — бросить вызов: " + BOSSES[self.isl['extra_boss']]['name']}[kind]()
            draw_text(scr, txt, (W / 2, H - 120), 20, (255, 255, 255), "center", 3)
        if pl.has('wet'):
            draw_text(scr, "Мокрый", (bx + 260, py + 6), 13, (120, 200, 255), "topleft", 2)
        sts = [STATUS_NAMES[s] for s in pl.statuses if s in STATUS_NAMES and s != 'wet']
        if sts:
            draw_text(scr, " · ".join(sts), (bx, py - 24), 14, (255, 170, 140), "topleft", 2)

    def objective_target(self):
        obj = self.cur_obj()
        pl = self.player
        if not obj:
            return None
        if obj['type'] == 'groups':
            best = None
            bd = 1e9
            for f in self.fighters:
                if f.team == 'enemy' and not f.dead and f.group and f.group[0] == 'g':
                    d = dist(f.pos, pl.pos)
                    if d < bd:
                        bd = d
                        best = f.pos
            return best
        if obj['type'] == 'mids':
            for f in self.fighters:
                if hasattr(f, 'mid_id') and not f.dead:
                    return f.pos
        if obj['type'] == 'boss':
            return self.boss.pos if self.boss and not self.boss.dead else self.boss_marker
        return None

    def draw_edge_arrow(self, scr, tgt):
        vw, vh = self.cam.view_size()
        ox, oy = self.cam.offset(vw, vh)
        z = self.cam.zoom
        sx, sy = (tgt.x - ox) * z, (tgt.y - oy) * z
        if 40 < sx < W - 40 and 60 < sy < H - 140:
            pygame.draw.polygon(scr, (255, 210, 60), [(sx, sy - 70), (sx - 10, sy - 88), (sx + 10, sy - 88)])
            return
        cx, cy = W / 2, H / 2
        a = math.atan2(sy - cy, sx - cx)
        tmax = min((W / 2 - 50) / max(1e-3, abs(math.cos(a))), (H / 2 - 90) / max(1e-3, abs(math.sin(a))))
        ex = cx + math.cos(a) * tmax
        ey = cy + math.sin(a) * tmax
        if ex > W - 240 and ey < 180:
            ey = 190
        pts = [(ex + math.cos(a) * 20, ey + math.sin(a) * 20), (ex + math.cos(a + 2.5) * 16, ey + math.sin(a + 2.5) * 16), (ex + math.cos(a - 2.5) * 16, ey + math.sin(a - 2.5) * 16)]
        pygame.draw.polygon(scr, (20, 14, 18), [(p[0] + 2, p[1] + 2) for p in pts])
        pygame.draw.polygon(scr, (255, 210, 60), pts)
        d = dist(tgt, self.player.pos)
        draw_text(scr, f"{int(d / TILE)} м", (ex - math.cos(a) * 30, ey - math.sin(a) * 30), 13, (255, 230, 150), "center", 2)

    def draw_minimap(self, scr):
        m = self.map
        mw_, mh_ = 200, int(200 * m.h / m.w)
        if self.minimap is None or self.minimap_t <= 0:
            self.minimap_t = 2.0
            cols = np.zeros((m.w, m.h, 3), np.uint8)
            gt = m.ground.T
            stt = m.state.T
            T = m.theme
            cols[:] = T['water']
            cols[gt == G_SHALLOW] = lerp_col(T['water'], T['sand'], 0.4)
            cols[gt == G_SAND] = T['sand']
            cols[(gt == G_GRASS) | (gt == G_GRASS2)] = T['ground']
            cols[(gt == G_PATH) | (gt == G_PLAZA)] = T['path']
            cols[gt == G_DECK] = (150, 105, 65)
            cols[(stt == S_BURN) | (stt == S_SCORCH)] = (50, 40, 35)
            cols[stt == S_ICE] = (200, 235, 255)
            cols[stt == S_LAVA] = (220, 70, 20)
            occ = m.occ.T >= 0
            cols[occ] = (cols[occ] * 0.6).astype(np.uint8)
            s = pygame.Surface((m.w, m.h))
            pygame.surfarray.blit_array(s, cols)
            self.minimap = pygame.transform.scale(s, (mw_, mh_))
        x0, y0 = W - mw_ - 14, 12
        pygame.draw.rect(scr, (20, 14, 18), (x0 - 3, y0 - 3, mw_ + 6, mh_ + 6), border_radius=6)
        scr.blit(self.minimap, (x0, y0))
        sx = mw_ / (m.w * TILE)
        sy = mh_ / (m.h * TILE)
        obs = self.pd.haki_cap['obs'] > 0
        for f in self.fighters:
            if f.dead:
                continue
            if f.team == 'enemy' and not obs and dist(f.pos, self.player.pos) > 600 and not f.is_boss:
                continue
            col = (255, 60, 60) if f.team == 'enemy' else ((80, 255, 120) if f.team == 'ally' else (255, 255, 255))
            r = 4 if f.is_boss else 2
            pygame.draw.circle(scr, col, (int(x0 + f.pos.x * sx), int(y0 + f.pos.y * sy)), r)
        for n in self.npcs:
            if n.role != 'villager':
                pygame.draw.circle(scr, (255, 220, 80), (int(x0 + n.pos.x * sx), int(y0 + n.pos.y * sy)), 2)
        bm = getattr(self, 'boss_marker', None)
        if bm is not None:
            draw_text(scr, "★", (x0 + bm.x * sx, y0 + bm.y * sy), 14, (255, 200, 60), "center", 1)
        pygame.draw.circle(scr, (255, 255, 255), (int(x0 + self.player.pos.x * sx), int(y0 + self.player.pos.y * sy)), 4, 2)
        dk = self.map.dock
        pygame.draw.rect(scr, (140, 200, 255), (x0 + dk.x * sx - 3, y0 + dk.y * sy - 3, 6, 6))

for _k, _v in list(IslandLoop.__dict__.items()):
    if callable(_v) and not _k.startswith('__'):
        setattr(IslandScene, _k, _v)

def draw_moored_ship(surf, x, y, ship, t, heading=-math.pi / 2, scale=1.0):
    draw_ship_sprite(surf, x, y, heading, ship, t, scale * 1.4, sails=0.3)

# ==================================================================
#  МОРЕ: КОРАБЛИ, ВЕТЕР, МОРСКИЕ КОРОЛИ, ШТОРМЫ, КАРТА МИРА
# ==================================================================
THEMES['shipdeck'] = dict(ground=(150, 105, 65), ground2=(140, 98, 60), path=(160, 112, 70), sand=(150, 105, 65), water=(30, 90, 160),
                          bld=[(170, 120, 70)], roof=[(120, 80, 50)], trees=None, density=0.0, town=0.0, plaza=(160, 112, 70), deck=True, shipdeck=True)

def ship_points(scale):
    L, Wd = 70 * scale, 24 * scale
    return [(L, 0), (L * 0.55, -Wd * 0.75), (-L * 0.1, -Wd), (-L * 0.85, -Wd * 0.85), (-L, -Wd * 0.4), (-L, Wd * 0.4), (-L * 0.85, Wd * 0.85),
            (-L * 0.1, Wd), (L * 0.55, Wd * 0.75)]

def _rot(pts, a, x, y):
    c, s = math.cos(a), math.sin(a)
    return [(x + px * c - py * s, y + px * s + py * c) for px, py in pts]

def draw_ship_sprite(surf, x, y, heading, ship, t, scale=1.0, sails=1.0, team_col=None, flag='skull', wind=0.0, damaged=0.0):
    tier = ship.get('tier', 'caravel') if isinstance(ship, dict) else 'caravel'
    T = SHIP_TIERS.get(tier, SHIP_TIERS['caravel'])
    sc = scale * T['size']
    hull = tuple(ship.get('color', T['color'])) if isinstance(ship, dict) else T['color']
    sail_col = tuple(ship.get('sail_color', (240, 240, 235))) if isinstance(ship, dict) else (240, 240, 235)
    if team_col is not None:
        sail_col = team_col
    bob = math.sin(t * 2 + x * 0.01) * 1.5
    y += bob
    # тень/волна
    pts = _rot(ship_points(sc * 1.08), heading, x + 6, y + 8)
    alpha_poly(surf, pts, (0, 20, 40), 70)
    pts = _rot(ship_points(sc), heading, x, y)
    opoly(surf, hull, [(int(a), int(b)) for a, b in pts], 3)
    inner = _rot(ship_points(sc * 0.8), heading, x, y)
    pygame.draw.polygon(surf, mul_col(hull, 1.18), inner)
    for i in range(-3, 4):
        a0 = _rot([(-55 * sc, i * 5 * sc), (45 * sc, i * 5 * sc)], heading, x, y)
        pygame.draw.line(surf, mul_col(hull, 0.9), a0[0], a0[1], 1)
    # пушки по бортам
    nc = ship.get('cannons', 2) if isinstance(ship, dict) else 2
    for i in range(nc):
        px_ = -35 * sc + i * (60 * sc / max(1, nc))
        for side in (-1, 1):
            p = _rot([(px_, side * 22 * sc)], heading, x, y)[0]
            pygame.draw.circle(surf, (40, 40, 45), (int(p[0]), int(p[1])), max(2, int(3 * sc)))
    # носовая фигура
    fig = ship.get('figure', 'lion') if isinstance(ship, dict) else 'lion'
    fp = _rot([(74 * sc, 0)], heading, x, y)[0]
    if fig == 'lion':
        for i in range(8):
            a = i / 8 * 6.28
            pygame.draw.circle(surf, (230, 140, 40), (int(fp[0] + math.cos(a) * 9 * sc), int(fp[1] + math.sin(a) * 9 * sc)), max(2, int(5 * sc)))
        ocircle(surf, (250, 220, 90), fp, 8 * sc, 2)
    elif fig == 'sheep':
        ocircle(surf, (250, 250, 245), fp, 9 * sc, 2)
        for k in (-1, 1):
            pygame.draw.circle(surf, (200, 180, 140), (int(fp[0] + math.cos(heading + k * 1.8) * 8 * sc), int(fp[1] + math.sin(heading + k * 1.8) * 8 * sc)), max(2, int(4 * sc)))
    elif fig == 'shark':
        ocircle(surf, (120, 150, 180), fp, 9 * sc, 2)
    elif fig == 'dragon':
        ocircle(surf, (80, 160, 90), fp, 9 * sc, 2)
    elif fig == 'seagull':
        ocircle(surf, (245, 245, 245), fp, 8 * sc, 2)
        pygame.draw.circle(surf, (60, 90, 170), (int(fp[0]), int(fp[1])), max(2, int(3 * sc)))
    # мачты и паруса
    masts = T['masts']
    for m in range(masts):
        mx = lerp(28, -42, m / (masts - 1)) * sc if masts > 1 else 5 * sc
        mp = _rot([(mx, 0)], heading, x, y)[0]
        sw = (44 if masts == 1 else (40 - 4 * m)) * sc
        billow = (5 + (9 if masts == 1 else 6) * sails) * sc
        a = heading + math.pi / 2
        p1 = (mp[0] + math.cos(a) * sw / 2, mp[1] + math.sin(a) * sw / 2)
        p2 = (mp[0] - math.cos(a) * sw / 2, mp[1] - math.sin(a) * sw / 2)
        fwd = (math.cos(heading) * billow, math.sin(heading) * billow)
        if sails > 0.05:
            ptsS = [p1, (p1[0] + fwd[0] * 0.6, p1[1] + fwd[1] * 0.6), (mp[0] + fwd[0], mp[1] + fwd[1]), (p2[0] + fwd[0] * 0.6, p2[1] + fwd[1] * 0.6), p2,
                    (mp[0] - fwd[0] * 0.2, mp[1] - fwd[1] * 0.2)]
            opoly(surf, sail_col if damaged < 0.5 else mul_col(sail_col, 0.75), [(int(a_), int(b_)) for a_, b_ in ptsS], 2)
            if m == 0 or masts == 1:
                ec = (mp[0] + fwd[0] * 0.55, mp[1] + fwd[1] * 0.55)
                if flag == 'skull':
                    pygame.draw.circle(surf, (20, 20, 25), (int(ec[0]), int(ec[1])), max(3, int(7 * sc)))
                    pygame.draw.circle(surf, (250, 250, 250), (int(ec[0]), int(ec[1])), max(2, int(4.5 * sc)))
                    hb = (ec[0] - math.cos(heading) * 5 * sc, ec[1] - math.sin(heading) * 5 * sc)
                    pygame.draw.line(surf, (240, 210, 90), (hb[0] + math.cos(a) * 6 * sc, hb[1] + math.sin(a) * 6 * sc),
                                     (hb[0] - math.cos(a) * 6 * sc, hb[1] - math.sin(a) * 6 * sc), max(2, int(3 * sc)))
                elif flag == 'seagull':
                    pygame.draw.circle(surf, (60, 100, 190), (int(ec[0]), int(ec[1])), max(3, int(6 * sc)))
                elif flag == 'revo':
                    pygame.draw.circle(surf, (40, 120, 70), (int(ec[0]), int(ec[1])), max(3, int(6 * sc)))
                elif flag == 'cross':
                    pygame.draw.line(surf, (30, 30, 30), (ec[0] - 5 * sc, ec[1] - 5 * sc), (ec[0] + 5 * sc, ec[1] + 5 * sc), 3)
                    pygame.draw.line(surf, (30, 30, 30), (ec[0] + 5 * sc, ec[1] - 5 * sc), (ec[0] - 5 * sc, ec[1] + 5 * sc), 3)
        ocircle(surf, (90, 60, 40), mp, 4 * sc, 1)
    if damaged > 0.5 and random.random() < 0.3:
        pass

class SeaShip:
    def __init__(self, scene, pos, heading, team, level, name, tier='caravel', pool=None, is_player=False, flag='skull', sail_col=None):
        self.scene = scene
        self.pos = V(pos)
        self.heading = heading
        self.speed = 0.0
        self.sail = 0.0
        self.sail_target = 0
        self.team = team
        self.level = level
        self.name = name
        self.tier = tier
        self.is_player = is_player
        T = SHIP_TIERS[tier]
        self.max_hp = T['hp'] * (0.4 + level * 0.03) if not is_player else 0
        self.hp = self.max_hp
        self.max_speed = T['speed'] * (0.85 if not is_player else 1)
        self.turn = T['turn']
        self.cannons = T['cannons']
        self.reload = {1: 0.0, -1: 0.0}
        self.dead = False
        self.sink_t = 0.0
        self.disabled = False
        self.pool = pool or ['pirate', 'pirate_gun']
        self.flag = flag
        self.sail_col = sail_col
        self.data = dict(tier=tier, cannons=T['cannons'], color=list(T['color']), sail_color=list(sail_col or (240, 240, 235)), figure='seagull' if flag == 'seagull' else 'lion')
        self.ai_t = 0.0
        self.hit_flash = 0.0
        self.burst_t = 0.0
        self.radius = 60 * T['size']
        self.boardable = not is_player
        self.wake_t = 0

    def update(self, dt, wind_dir, wind_str):
        sc = self.scene
        if self.dead:
            self.sink_t += dt
            return
        self.hit_flash = max(0, self.hit_flash - dt)
        for k in self.reload:
            self.reload[k] = max(0, self.reload[k] - dt)
        self.sail += (self.sail_target - self.sail) * min(1, dt * 1.5)
        rel = abs(ang_diff(self.heading, wind_dir))
        if rel < 0.6:
            wf = 1.0
        elif rel < 1.6:
            wf = 1.05 - (rel - 0.6) * 0.15
        elif rel < 2.4:
            wf = 0.9 - (rel - 1.6) * 0.6
        else:
            wf = 0.25
        target = (self.sail / 3) * self.max_speed * (0.25 + 0.75 * wind_str * wf)
        if self.sail_target > 0:
            target = max(target, self.max_speed * 0.18)
        if self.burst_t > 0:
            self.burst_t -= dt
            target = self.max_speed * 3.2
        acc = 90 if target > self.speed else 140
        self.speed += clamp(target - self.speed, -acc * dt, acc * dt)
        if self.is_player and sc.anchor:
            self.speed *= 0.9 ** (dt * 60)
        self.pos += from_angle(self.heading, self.speed * dt)
        self.wake_t -= dt
        if self.speed > 40 and self.wake_t <= 0:
            self.wake_t = 0.05
            back = self.pos - from_angle(self.heading, 60 * SHIP_TIERS[self.tier]['size'])
            for k in (-1, 1):
                sc.particles.add(back.x + random.uniform(-6, 6), back.y + random.uniform(-6, 6), -math.cos(self.heading) * 30 + math.cos(self.heading + k * 1.4) * 40,
                                 -math.sin(self.heading) * 30 + math.sin(self.heading + k * 1.4) * 40, 1.6, 6, (230, 245, 255), 'smoke', grow=10)
        if self.disabled and random.random() < dt * 4:
            sc.particles.add(self.pos.x + random.uniform(-20, 20), self.pos.y + random.uniform(-10, 10), 0, -30, 1.5, 14, (60, 55, 55), 'smoke', grow=15)

    def fire(self, side, target_pt, dmg):
        sc = self.scene
        if self.reload[side] > 0:
            return False
        n = self.cannons
        self.reload[side] = 2.4 if self.is_player else 3.5
        perp = self.heading + side * math.pi / 2
        for i in range(n):
            off = (-30 + i * (60 / max(1, n))) * SHIP_TIERS[self.tier]['size']
            src = self.pos + from_angle(self.heading, off) + from_angle(perp, 22 * SHIP_TIERS[self.tier]['size'])
            tp = V(target_pt) + V(random.uniform(-40, 40), random.uniform(-40, 40))
            d = dist(src, tp)
            maxr = 700 if self.is_player else 600
            if d > maxr:
                tp = src + (tp - src).normalize() * maxr
            sc.balls.append(CannonBall(sc, self, src, tp, dmg, delay=i * 0.08))
            sc.particles.burst(src.x, src.y, 6, (220, 220, 220), 'smoke', 80, 0.8, size=10, angle=perp, spread=0.8)
        sc.audio_play('cannon', 0.8 if self.is_player else 0.5, pos=self.pos)
        if self.is_player:
            sc.cam.add_shake(0.2)
        return True

    def take(self, dmg, src=None):
        if self.dead:
            return
        self.hp -= dmg
        self.hit_flash = 0.2
        self.scene.particles.burst(self.pos.x, self.pos.y, 10, (150, 110, 70), 'debris', 200, 0.8, size=5, grav=600, z=10, vz=200)
        if not self.is_player and self.hp <= self.max_hp * 0.25 and not self.disabled:
            self.disabled = True
            self.sail_target = 0
            self.scene.notify(f"«{self.name}» обездвижен! E — абордаж, или добей пушками.", (255, 220, 120))
        if self.hp <= 0:
            self.sink(src)

    def sink(self, src=None):
        if self.dead:
            return
        self.dead = True
        sc = self.scene
        sc.particles.burst(self.pos.x, self.pos.y, 40, (255, 140, 40), 'fire', 300, 1.0, size=12)
        sc.particles.burst(self.pos.x, self.pos.y, 30, (130, 95, 60), 'debris', 300, 1.5, size=6, grav=600, z=10, vz=300)
        sc.audio_play('explosion', 1.0, pos=self.pos)
        if not self.is_player:
            sc.on_ship_sunk(self)

    def draw(self, surf, ox, oy, t):
        x, y = self.pos.x - ox, self.pos.y - oy
        if x < -200 or y < -200 or x > W + 200 or y > H + 200:
            return
        if self.dead:
            k = min(1, self.sink_t / 2.5)
            if k >= 1:
                return
            s = pygame.Surface((300, 300), pygame.SRCALPHA)
            draw_ship_sprite(s, 150, 150 + k * 20, self.heading + k * 0.6, self.data, t, 1.0 - k * 0.3, self.sail * 0.3, flag=self.flag)
            s.set_alpha(int(255 * (1 - k)))
            surf.blit(s, (x - 150, y - 150))
            return
        draw_ship_sprite(surf, x, y, self.heading, self.data, t, 1.0, self.sail / 3 if self.sail > 0.1 else 0.0, flag=self.flag,
                         damaged=1 - self.hp / self.max_hp if self.max_hp else 0)
        if self.hit_flash > 0:
            draw_glow(surf, (x, y), 70, (255, 200, 150), self.hit_flash * 2)
        if not self.is_player:
            w_ = 80
            pygame.draw.rect(surf, (20, 10, 10), (x - w_ / 2 - 1, y - 70, w_ + 2, 7))
            pygame.draw.rect(surf, (220, 60, 50) if not self.disabled else (240, 180, 60), (x - w_ / 2, y - 69, w_ * self.hp / self.max_hp, 5))
            draw_text(surf, f"{self.name} [{self.level}]", (x, y - 86), 13, (255, 220, 220) if self.team == 'enemy' else (220, 255, 220), "center", 2)

class CannonBall:
    def __init__(self, sc, owner, src, tgt, dmg, delay=0.0, big=False):
        self.sc = sc
        self.owner = owner
        self.src = V(src)
        self.tgt = V(tgt)
        self.dmg = dmg
        self.delay = delay
        d = dist(src, tgt)
        self.dur = max(0.35, d / 750)
        self.t = 0.0
        self.dead = False
        self.big = big

    def pos(self):
        k = clamp(self.t / self.dur, 0, 1)
        p = self.src + (self.tgt - self.src) * k
        z = math.sin(k * math.pi) * (60 + dist(self.src, self.tgt) * 0.12)
        return p, z

    def update(self, dt):
        if self.delay > 0:
            self.delay -= dt
            return
        self.t += dt
        if self.t >= self.dur:
            self.dead = True
            self.land()

    def land(self):
        sc = self.sc
        p = self.tgt
        hit = sc.ship_hit_at(p, 45, self.owner)
        if hit is not None:
            hit.take(self.dmg, self.owner)
            sc.particles.burst(p.x, p.y, 20, (255, 160, 60), 'fire', 220, 0.6, size=10)
            sc.audio_play('explosion', 0.5, pos=p, cooldown=0.05)
            if self.owner.is_player:
                sc.cam.add_shake(0.1)
        else:
            sk = sc.seaking_at(p, 70)
            if sk is not None and self.owner.is_player:
                sk.take(self.dmg)
                sc.particles.burst(p.x, p.y, 12, (255, 160, 60), 'fire', 200, 0.5, size=8)
            else:
                sc.particles.burst(p.x, p.y, 16, (220, 240, 255), 'water', 220, 0.8, size=4, grav=500, z=5, vz=300)
                sc.effects.append(RingFX(p, 5, 50, 0.6, (220, 240, 255), 3))
                sc.audio_play('splash', 0.3, pos=p, cooldown=0.05)

    def draw(self, surf, ox, oy):
        if self.delay > 0:
            return
        p, z = self.pos()
        pygame.draw.circle(surf, (0, 30, 50), (int(p.x - ox), int(p.y - oy)), 4)
        ocircle(surf, (40, 40, 45), (p.x - ox, p.y - oy - z), 6 if not self.big else 10, 2)

class SeaKing:
    def __init__(self, sc, pos, level):
        self.sc = sc
        self.pos = V(pos)
        self.level = level
        self.max_hp = 1500 * (1 + level * 0.12)
        self.hp = self.max_hp
        self.state = 'rise'
        self.t = 0.0
        self.dead = False
        self.attack_t = 2.0
        self.target_pt = None
        self.col = random.choice([(90, 150, 130), (150, 90, 160), (200, 120, 60), (80, 110, 170)])
        self.heading = random.uniform(0, 6.28)
        self.hit_flash = 0

    def take(self, dmg):
        self.hp -= dmg
        self.hit_flash = 0.2
        if self.hp <= 0 and not self.dead:
            self.dead = True
            self.state = 'die'
            self.t = 0
            self.sc.on_seaking_dead(self)

    def update(self, dt):
        self.t += dt
        self.hit_flash = max(0, self.hit_flash - dt)
        sc = self.sc
        pl = sc.ship
        if self.state == 'rise':
            if self.t > 1.2:
                self.state = 'idle'
                self.t = 0
        elif self.state == 'idle':
            d = pl.pos - self.pos
            if d.length() > 260:
                self.pos += d.normalize() * 120 * dt
            self.heading = math.atan2(d.y, d.x)
            self.attack_t -= dt
            if self.attack_t <= 0:
                self.state = 'wind'
                self.t = 0
                self.target_pt = V(pl.pos) + from_angle(pl.heading, pl.speed * 0.9)
                sc.effects.append(TelegraphFX('circle', 1.0, pos=V(self.target_pt), r=110))
                sc.audio_play('seaking', 0.8, pos=self.pos)
        elif self.state == 'wind':
            if self.t > 1.0:
                self.state = 'strike'
                self.t = 0
                p = self.target_pt
                sc.effects.append(RingFX(p, 10, 160, 0.6, (230, 245, 255), 6))
                sc.particles.burst(p.x, p.y, 40, (220, 240, 255), 'water', 400, 1.0, size=5, grav=500, z=10, vz=400)
                sc.cam.add_shake(0.5)
                if dist(pl.pos, p) < 130 and pl.burst_t <= 0:
                    sc.player_ship_damage(160 + self.level * 14)
        elif self.state == 'strike':
            if self.t > 0.8:
                self.state = 'idle'
                self.t = 0
                self.attack_t = random.uniform(2.0, 3.5)
        elif self.state == 'die':
            if self.t > 2.0:
                self.state = 'gone'

    def draw(self, surf, ox, oy):
        if self.state == 'gone':
            return
        x, y = self.pos.x - ox, self.pos.y - oy
        if self.state == 'rise':
            k = min(1, self.t / 1.2)
        elif self.state == 'die':
            k = 1 - min(1, self.t / 2)
        else:
            k = 1
        col = self.col if self.hit_flash <= 0 else (255, 230, 220)
        # кольца тела
        for i in range(5):
            a = self.heading + math.pi + (i - 2) * 0.4
            p = (x + math.cos(a) * (60 + i * 30), y + math.sin(a) * (60 + i * 30) * 0.7 + math.sin(self.t * 3 + i) * 6)
            r = 30 * k * (1 - i * 0.12)
            if r > 2:
                pygame.draw.ellipse(surf, (20, 40, 60), (p[0] - r * 1.1, p[1] - r * 0.3 + 6, r * 2.2, r * 0.8))
                ocircle(surf, col, (p[0], p[1] - r * 0.4), r, 3)
        head_h = 90 * k
        if self.state == 'wind':
            head_h += 30
        hx, hy = x, y - head_h
        pygame.draw.line(surf, (20, 14, 18), (x, y), (hx, hy), int(44 * k) + 6)
        pygame.draw.line(surf, col, (x, y), (hx, hy), int(44 * k) + 1)
        ocircle(surf, col, (hx, hy), 40 * k + 2, 3)
        for kx in (-1, 1):
            pygame.draw.circle(surf, (255, 230, 60), (int(hx + kx * 15 * k), int(hy - 8 * k)), max(2, int(6 * k)))
            pygame.draw.circle(surf, (20, 14, 18), (int(hx + kx * 15 * k), int(hy - 8 * k)), max(1, int(3 * k)))
        pygame.draw.arc(surf, (255, 255, 255), (hx - 26 * k, hy + 2, 52 * k, 26 * k), 3.4, 6.0, 3)
        pygame.draw.ellipse(surf, (230, 245, 255), (x - 60, y - 10, 120, 24), 3)
        if self.state not in ('die',):
            w_ = 100
            pygame.draw.rect(surf, (20, 10, 10), (x - w_ / 2 - 1, y - head_h - 70, w_ + 2, 7))
            pygame.draw.rect(surf, (200, 80, 220), (x - w_ / 2, y - head_h - 69, w_ * max(0, self.hp) / self.max_hp, 5))
            draw_text(surf, f"Морской Король [{self.level}]", (x, y - head_h - 88), 13, (240, 200, 255), "center", 2)

class LootBarrel:
    def __init__(self, pos, kind='barrel'):
        self.pos = V(pos)
        self.kind = kind
        self.t = random.uniform(0, 6)
        self.dead = False

    def draw(self, surf, ox, oy):
        x, y = self.pos.x - ox, self.pos.y - oy + math.sin(self.t * 2) * 3
        if self.kind == 'wreck':
            pygame.draw.polygon(surf, (90, 60, 40), [(x - 30, y), (x + 20, y - 10), (x + 30, y + 8), (x - 20, y + 14)])
            pygame.draw.line(surf, (70, 50, 30), (x, y), (x + 10, y - 40), 4)
            draw_glow(surf, (x, y), 40, (255, 220, 120), 0.3)
        else:
            oellipse(surf, (150, 105, 60), (x - 10, y - 12, 20, 24), 2)
            pygame.draw.line(surf, (70, 50, 40), (x - 9, y - 4), (x + 9, y - 4), 2)
        pygame.draw.ellipse(surf, (220, 240, 255), (x - 18, y + 6, 36, 10), 2)

def make_wave_texture(seed, col, layer=0):
    w_ = 256
    n = periodic_noise(w_, 4, seed, 5)
    n2 = periodic_noise(w_, 16, seed + 1, 3)
    arr = np.zeros((w_, w_, 3), np.float32)
    base = np.array(col, np.float32)
    shade = 0.9 + 0.16 * n
    arr[:] = base[None, None, :] * shade[..., None]
    band = np.abs(np.sin((n2 * 9.0 + n * 3.0) * math.pi))
    crest = np.clip((band - 0.86) * 7, 0, 1) * np.clip((n - 0.35) * 3, 0, 1)
    arr += crest[..., None] * np.array([70, 85, 95], np.float32)[None, None, :]
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    s = pygame.Surface((w_, w_))
    pygame.surfarray.blit_array(s, arr.transpose(1, 0, 2))
    return s

REGION_SEA_COL = {'east': (45, 130, 205), 'paradise': (35, 115, 195), 'calm': (70, 150, 180), 'new': (28, 85, 160), 'redline': (40, 90, 140), 'void': (20, 40, 70)}

def make_island_icon(iid, isl):
    T = THEMES[isl['theme']]
    rng = random.Random(stable_seed(iid))
    R = 170 + min(120, isl['size'][0] * 1.2) if isl['theme'] != 'restaurant' else 120
    R = int(R)
    s = pygame.Surface((R * 2 + 40, R * 2 + 40), pygame.SRCALPHA)
    c = (R + 20, R + 20)
    pts = []
    for i in range(36):
        a = i / 36 * 6.28
        rr = R * (0.8 + 0.25 * math.sin(a * 3 + rng.random() * 6) * 0.5 + rng.uniform(-0.06, 0.06))
        pts.append((c[0] + math.cos(a) * rr, c[1] + math.sin(a) * rr * 0.85))
    shallow = [(c[0] + (p[0] - c[0]) * 1.12, c[1] + (p[1] - c[1]) * 1.12) for p in pts]
    pygame.draw.polygon(s, (*lerp_col(T['water'], (230, 240, 255), 0.35), 200), shallow)
    pygame.draw.polygon(s, T['sand'], pts)
    inner = [(c[0] + (p[0] - c[0]) * 0.85, c[1] + (p[1] - c[1]) * 0.85) for p in pts]
    pygame.draw.polygon(s, T['ground'], inner)
    for i in range(int(14 + T.get('density', 0.3) * 20)):
        a = rng.uniform(0, 6.28)
        rr = rng.uniform(0, R * 0.7)
        p = (c[0] + math.cos(a) * rr, c[1] + math.sin(a) * rr * 0.8)
        pygame.draw.circle(s, mul_col(T['ground'], 0.7), (int(p[0]), int(p[1])), rng.randint(6, 12))
    for i in range(int(4 + T.get('town', 0.3) * 14)):
        a = rng.uniform(0, 6.28)
        rr = rng.uniform(0, R * 0.5)
        p = (c[0] + math.cos(a) * rr, c[1] + math.sin(a) * rr * 0.8)
        col = rng.choice(T['bld'])
        roof = rng.choice(T['roof'])
        pygame.draw.rect(s, (20, 14, 18), (p[0] - 7, p[1] - 6, 16, 13))
        pygame.draw.rect(s, roof, (p[0] - 6, p[1] - 5, 14, 11))
    pygame.draw.polygon(s, (20, 14, 18), pts, 3)
    return s

class SeaScene:
    kind = 'sea'

    def __init__(self, game, start_pos=None, heading=None):
        self.game = game
        self.pd = game.pd
        pd = self.pd
        p = V(start_pos) if start_pos is not None else V(pd.sea_pos)
        self.t = 0.0
        self.particles = Particles()
        self.effects = []
        self.balls = []
        self.ships = []
        self.kings = []
        self.loot = []
        self.whirls = []
        self.notifications = []
        self.cam = Camera()
        self.cam.pos = V(p)
        self.anchor = False
        self.wind_dir = random.uniform(0, 6.28)
        self.wind_str = 0.8
        self.wind_target = self.wind_dir
        self.weather = 'clear'
        self.weather_t = random.uniform(40, 80)
        self.rain = [[random.uniform(0, W), random.uniform(0, H), random.uniform(0.6, 1.4)] for _ in range(160)]
        self.lightning_t = 3.0
        self.spawn_t = 8.0
        self.loot_t = 5.0
        self.king_t = 6.0
        self.fishing = None
        self.gaon_charge = 0.0
        self.map_open = False
        self.flash_t = 0.0
        self.flash_col = (255, 255, 255)
        self.textures = {}
        self.island_icons = {}
        self.region = None
        self.region_banner = 0.0
        self.ship = SeaShip(self, p, heading if heading is not None else pd.sea_heading, 'player', pd.level, pd.ship['name'], pd.ship['tier'], is_player=True,
                            flag=FACTIONS[pd.faction]['flag'])
        self.apply_ship_stats()
        self.ships.append(self.ship)
        self.knockup_t = 0
        game.audio.play_music('sea')
        game.audio.ambient_loop('waves', 0.35)
        self.texts = []
        self.check_region(force=True)

    def apply_ship_stats(self):
        pd = self.pd
        s = pd.ship
        T = SHIP_TIERS[s['tier']]
        nav = 1.15 if any(c['role'] == 'navigator' for c in pd.crew) else 1.0
        helm = 1.25 if any(c['role'] == 'helmsman' for c in pd.crew) else 1.0
        sh = self.ship
        sh.tier = s['tier']
        sh.max_speed = T['speed'] * (1 + 0.1 * s['sail_lvl']) * nav
        sh.turn = T['turn'] * (1 + 0.08 * s['sail_lvl']) * helm
        s['max_hp'] = int(T['hp'] * (1 + 0.3 * s['hull_lvl']))
        s['hp'] = min(s['hp'], s['max_hp'])
        sh.cannons = T['cannons'] + s['cannon_lvl'] // 2
        s['cannons'] = sh.cannons
        sh.data = s
        sh.radius = 60 * T['size']
        sh.name = s['name']

    def cannon_dmg(self):
        pd = self.pd
        s = pd.ship
        m = 1.3 if any(c['role'] == 'sniper' for c in pd.crew) else 1.0
        return (40 + pd.level * 9) * (1 + 0.3 * s['cannon_lvl']) * m

    def notify(self, text, col=(255, 255, 255)):
        self.notifications.append([text, col, 4.0])

    def audio_play(self, name, vol=1.0, pos=None, cooldown=0.03):
        pan = 0.0
        if pos is not None:
            pan = clamp((pos.x - self.cam.pos.x) / 700, -0.8, 0.8)
            vol *= clamp(1.4 - dist(pos, self.cam.pos) / 1200, 0.1, 1.0)
        self.game.audio.play(name, vol, pan, cooldown)

    def float_text(self, pos, text, col=(255, 255, 255), size=18):
        self.texts.append(FloatText(pos.x, pos.y - 60, text, col, size, 1.4))

    # ---------------- мир ----------------
    def known_islands(self):
        pd = self.pd
        out = []
        for iid, isl in ISLANDS.items():
            if isl.get('hidden'):
                continue
            reg = isl['region']
            if reg == 'east':
                out.append(iid)
            elif reg in ('paradise', 'calm') and ('log_pose' in pd.flags or 'reverse' in pd.flags):
                out.append(iid)
            elif reg == 'new' and 'new_world' in pd.flags:
                out.append(iid)
        return out

    def next_story_island(self):
        pd = self.pd
        for iid in ISLAND_ORDER:
            isl = ISLANDS[iid]
            if not pd.island_state(iid)['done']:
                return iid
        return None

    def check_region(self, force=False):
        p = self.ship.pos
        r = region_at(p.x, p.y)
        if r != self.region or force:
            if self.region is not None or force:
                self.region_banner = 3.0
            self.region = r

    def world_block(self, p):
        """True — проход закрыт (Ред Лайн, край мира)."""
        pd = self.pd
        x, y = p.x, p.y
        if x < 200 or y < 200 or x > WORLD_W - 200 or y > WORLD_H - 200:
            return "Край известного мира."
        if REDLINE1_X[0] <= x <= REDLINE1_X[1]:
            if REVERSE_GATE_Y[0] <= y <= REVERSE_GATE_Y[1] and 'reverse' in pd.flags:
                return None
            return "Ред Лайн — непреодолимая стена. Путь на Гранд Лайн — через Ревёрс Маунтин (после Логтауна)."
        if REDLINE2_X[0] <= x <= REDLINE2_X[1]:
            return "Ред Лайн. В Новый Мир — только через Остров Рыболюдей (нужно покрытие корабля на Сабаоди)."
        r = region_at(x, y)
        if r == 'void':
            return "Дальше — лишь бесконечный шторм. Поверни назад."
        return None

    # ---------------- обновление ----------------
    def update(self, dt):
        g = self.game
        self.t += dt
        pd = self.pd
        sh = self.ship
        if self.map_open:
            if pygame.K_m in g.kp or pygame.K_ESCAPE in g.kp:
                self.map_open = False
            return
        if pygame.K_m in g.kp:
            self.map_open = True
            return
        # ветер
        self.wind_target += random.uniform(-0.3, 0.3) * dt
        reg = region_at(sh.pos.x, sh.pos.y)
        if reg == 'calm':
            self.wind_str += (0.05 - self.wind_str) * dt * 0.5
        elif self.weather == 'storm':
            self.wind_str += (1.2 - self.wind_str) * dt * 0.5
            self.wind_target += random.uniform(-1.5, 1.5) * dt
        else:
            self.wind_str += (0.8 + 0.2 * math.sin(self.t * 0.05) - self.wind_str) * dt * 0.3
        self.wind_dir += ang_diff(self.wind_dir, self.wind_target) * dt * 0.3
        self.weather_t -= dt
        if self.weather_t <= 0:
            self.change_weather(reg)
        # управление
        if self.fishing is not None:
            self.update_fishing(dt)
        else:
            keys = g.keys
            if pygame.K_w in g.kp:
                sh.sail_target = min(3, sh.sail_target + 1)
                self.anchor = False
            if pygame.K_s in g.kp:
                sh.sail_target = max(0, sh.sail_target - 1)
            turn = (1 if keys[pygame.K_d] else 0) - (1 if keys[pygame.K_a] else 0)
            tr = sh.turn * (0.35 + 0.65 * min(1, sh.speed / 150))
            sh.heading += turn * tr * dt * 0.6
            self.anchor = bool(keys[pygame.K_LSHIFT])
            mw = self.mouse_world()
            if 1 in g.mbp:
                v = mw - sh.pos
                fwd = from_angle(sh.heading)
                cross = fwd.x * v.y - fwd.y * v.x
                side = 1 if cross > 0 else -1
                if sh.fire(side, mw, self.cannon_dmg()):
                    pass
                elif self.t - getattr(self, '_reload_msg', -9) > 1.0:
                    self._reload_msg = self.t
                    self.float_text(sh.pos, "Перезарядка...", (255, 220, 150), 14)
            if g.mb[2] and pd.ship.get('gaon'):
                if pd.ship['cola'] >= 10 or self.gaon_charge > 0:
                    self.gaon_charge = min(1.5, self.gaon_charge + dt)
                    if random.random() < 0.5:
                        bow = sh.pos + from_angle(sh.heading, 70)
                        self.particles.add(bow.x + random.uniform(-20, 20), bow.y + random.uniform(-20, 20), 0, 0, 0.3, 6, (255, 220, 120), 'glow')
            elif self.gaon_charge > 0:
                if self.gaon_charge >= 1.4:
                    self.fire_gaon()
                self.gaon_charge = 0
            if pygame.K_SPACE in g.kp:
                if pd.ship.get('coup') and pd.ship['cola'] >= 3 and sh.burst_t <= 0:
                    pd.ship['cola'] -= 3
                    sh.burst_t = 1.6
                    self.notify("COUP DE BURST!", (255, 230, 120))
                    self.audio_play('explosion', 0.8)
                    self.cam.add_shake(0.6)
                    back = sh.pos - from_angle(sh.heading, 60)
                    self.particles.burst(back.x, back.y, 40, (255, 240, 200), 'smoke', 400, 1.0, size=16, angle=sh.heading + math.pi, spread=0.6)
                elif not pd.ship.get('coup'):
                    self.notify("Coup de Burst не установлен (корабел: Вотер Севен).", (200, 200, 200))
                else:
                    self.notify("Нужно 3 колы!", (200, 200, 200))
            if pygame.K_f in g.kp and sh.speed < 40:
                self.start_fishing()
            if pygame.K_e in g.kp:
                self.interact()
        # движение
        old = V(sh.pos)
        sh.update(dt, self.wind_dir, self.wind_str)
        blk = self.world_block(sh.pos)
        if blk and sh.burst_t <= 0:
            sh.pos = old
            sh.speed *= -0.3
            if not hasattr(self, '_blk_t') or self.t - self._blk_t > 3:
                self._blk_t = self.t
                self.notify(blk, (255, 200, 160))
        # острова — столкновение
        for iid in self.known_islands():
            isl = ISLANDS[iid]
            ip = V(isl['pos'])
            R = self.island_radius(iid)
            d = dist(ip, sh.pos)
            if d < R * 0.7:
                push = (sh.pos - ip).normalize() if d > 0 else V(1, 0)
                sh.pos = ip + push * R * 0.7
                if sh.speed > 150:
                    self.player_ship_damage(sh.speed * 0.3)
                    self.notify("Корабль сел на мель!", (255, 180, 150))
                sh.speed *= 0.3
        # особые места
        self.check_special()
        self.check_region()
        if self.region_banner > 0:
            self.region_banner -= dt
        # враги
        self.spawn_t -= dt
        if self.spawn_t <= 0:
            self.spawn_t = random.uniform(18, 32)
            self.maybe_spawn_ship(reg)
        self.king_t -= dt
        if self.king_t <= 0:
            self.king_t = random.uniform(8, 14) if reg == 'calm' else random.uniform(45, 90)
            if (reg == 'calm' and not pd.ship.get('kairo') and pd.faction != 'marine') or (reg in ('paradise', 'new') and random.random() < 0.3):
                if len([k for k in self.kings if not k.dead]) < (3 if reg == 'calm' else 1):
                    lvl = self.region_level()
                    p = sh.pos + from_angle(random.uniform(0, 6.28), random.uniform(350, 550))
                    self.kings.append(SeaKing(self, p, lvl))
                    self.notify("МОРСКОЙ КОРОЛЬ!", (220, 150, 255))
                    self.audio_play('seaking', 1.0)
        self.loot_t -= dt
        if self.loot_t <= 0:
            self.loot_t = random.uniform(6, 14)
            if len(self.loot) < 8:
                p = sh.pos + from_angle(random.uniform(0, 6.28), random.uniform(400, 900))
                if not self.world_block(p):
                    self.loot.append(LootBarrel(p, 'wreck' if random.random() < 0.12 else 'barrel'))
        for s in self.ships:
            if s is not sh:
                self.enemy_ai(s, dt)
                s.update(dt, self.wind_dir, self.wind_str)
        self.ships = [s for s in self.ships if not (s.dead and s.sink_t > 2.5) and (s is sh or dist(s.pos, sh.pos) < 4000)]
        for k in self.kings:
            k.update(dt)
        self.kings = [k for k in self.kings if k.state != 'gone' and dist(k.pos, sh.pos) < 3000]
        for b in self.balls:
            b.update(dt)
        self.balls = [b for b in self.balls if not b.dead]
        for l in self.loot:
            l.t += dt
            if dist(l.pos, sh.pos) < 70:
                self.collect_loot(l)
        self.loot = [l for l in self.loot if not l.dead and dist(l.pos, sh.pos) < 3500]
        self.effects = [e for e in self.effects if e.update(dt)]
        self.particles.update(dt)
        for tx in self.texts:
            tx.life -= dt
            tx.y += tx.vy * dt * 0.5
        self.texts = [t for t in self.texts if t.life > 0]
        # шторм
        if self.weather == 'storm':
            self.lightning_t -= dt
            if self.lightning_t <= 0:
                self.lightning_t = random.uniform(1.5, 5)
                p = sh.pos + from_angle(random.uniform(0, 6.28), random.uniform(100, 600))
                self.effects.append(BoltFX(p + V(0, -700), p, (200, 220, 255), 0.35, 5, 40, 3))
                self.flash_t = 0.12
                self.audio_play('thunder', 0.8)
                if dist(p, sh.pos) < 120:
                    self.player_ship_damage(80 + pd.level * 4)
            if random.random() < dt * 0.5:
                sh.heading += random.uniform(-0.15, 0.15)
        # ремонт плотником
        if any(c['role'] == 'shipwright' for c in pd.crew):
            pd.ship['hp'] = min(pd.ship['max_hp'], pd.ship['hp'] + pd.ship['max_hp'] * 0.004 * dt)
        self.flash_t = max(0, self.flash_t - dt)
        for n in self.notifications:
            n[2] -= dt
        self.notifications = [n for n in self.notifications if n[2] > 0][-5:]
        self.cam.update(dt, sh.pos + from_angle(sh.heading, min(250, sh.speed * 0.6)))
        pd.sea_pos = [sh.pos.x, sh.pos.y]
        pd.sea_heading = sh.heading
        if pd.ship['hp'] <= 0:
            self.ship_wrecked()

    def region_level(self):
        x = self.ship.pos.x
        if x < REDLINE1_X[0]:
            return max(2, int(2 + x / 1000))
        if x < REDLINE2_X[0]:
            return int(15 + (x - REDLINE1_X[1]) / (REDLINE2_X[0] - REDLINE1_X[1]) * 37)
        return int(55 + (x - REDLINE2_X[1]) / (WORLD_W - REDLINE2_X[1]) * 35)

    def change_weather(self, reg):
        old = self.weather
        if reg == 'east':
            self.weather = weighted_choice([('clear', 6), ('storm', 1)])
        elif reg == 'new':
            self.weather = weighted_choice([('clear', 3), ('storm', 3), ('fog', 1)])
        elif reg == 'calm':
            self.weather = 'clear'
        else:
            self.weather = weighted_choice([('clear', 4), ('storm', 2), ('fog', 1)])
        self.weather_t = random.uniform(40, 90)
        nav = any(c['role'] == 'navigator' for c in self.pd.crew)
        if self.weather != old:
            if self.weather == 'storm':
                self.notify("Надвигается шторм!" + (" (штурман: держи паруса пониже)" if nav else ""), (180, 200, 255))
            elif self.weather == 'fog':
                self.notify("Опустился туман...", (200, 200, 210))
            else:
                self.notify("Небо прояснилось.", (220, 240, 255))

    def island_radius(self, iid):
        isl = ISLANDS[iid]
        return 170 + min(120, isl['size'][0] * 1.2) if isl['theme'] != 'restaurant' else 120

    def check_special(self):
        pd = self.pd
        sh = self.ship
        p = sh.pos
        if 'knockup' in pd.flags and dist(p, KNOCKUP_POS) < 900:
            self.knockup_t += 0.016
            if random.random() < 0.3:
                q = V(KNOCKUP_POS) + from_angle(random.uniform(0, 6.28), random.uniform(0, 200))
                self.particles.add(q.x, q.y, 0, -50, 1.0, 20, (230, 245, 255), 'smoke', grow=20)

    def nearby_interaction(self):
        sh = self.ship
        pd = self.pd
        for iid in self.known_islands():
            ip = V(ISLANDS[iid]['pos'])
            if dist(ip, sh.pos) < self.island_radius(iid) + 160:
                return ('island', iid)
        if 'knockup' in pd.flags and dist(sh.pos, KNOCKUP_POS) < 260:
            return ('knockup', None)
        if dist(sh.pos, V(FISHMAN_GATE_POS) + V(-250, 0)) < 400:
            return ('fishman_gate', None)
        if REDLINE2_X[1] <= sh.pos.x < REDLINE2_X[1] + 500 and abs(sh.pos.y - FISHMAN_GATE_POS[1]) < 400:
            return ('back_gate', None)
        for s in self.ships:
            if s is not sh and not s.dead and s.disabled and dist(s.pos, sh.pos) < 220:
                return ('board', s)
        return None

    def interact(self):
        ni = self.nearby_interaction()
        if not ni:
            return
        kind, obj = ni
        g = self.game
        pd = self.pd
        if kind == 'island':
            if self.ship.speed > 260:
                self.notify("Сбавь скорость, чтобы пристать к берегу!", (255, 220, 150))
                return
            g.enter_island(obj)
        elif kind == 'knockup':
            if ISLANDS['jaya'] and pd.island_state('jaya')['done']:
                self.notify("ПОТОК НОК-АП! Корабль взмывает в небо!", (230, 240, 255))
                g.cinematic_knockup()
        elif kind == 'fishman_gate':
            if 'coating' in pd.flags:
                g.cinematic_dive()
            else:
                self.notify("Без покрытия смолой (Сабаоди) к Острову Рыболюдей не спуститься.", (255, 200, 160))
        elif kind == 'back_gate':
            if 'coating' in pd.flags:
                sh = self.ship
                sh.pos = V(REDLINE2_X[0] - 600, FISHMAN_GATE_POS[1])
                sh.heading = math.pi
                self.notify("Ты вернулся в Рай через Остров Рыболюдей.", (200, 230, 255))
        elif kind == 'board':
            g.start_boarding(obj)

    def mouse_world(self):
        ox, oy = self.cam.offset(W, H)
        return V(ox + self.game.mouse[0], oy + self.game.mouse[1])

    def fire_gaon(self):
        pd = self.pd
        sh = self.ship
        pd.ship['cola'] -= 10
        a = sh.heading
        start = sh.pos + from_angle(a, 70)
        self.effects.append(BeamFX(start, a, 1200, 60, 0.8, (255, 220, 120)))
        self.flash_t = 0.2
        self.cam.add_shake(0.8)
        self.audio_play('beam', 1.0)
        self.audio_play('explosion', 1.0)
        dmg = self.cannon_dmg() * 8
        end = start + from_angle(a, 1200)
        for s in self.ships:
            if s is not sh and not s.dead and point_seg_dist(s.pos, start, end) < 80:
                s.take(dmg, sh)
        for k in self.kings:
            if not k.dead and point_seg_dist(k.pos, start, end) < 100:
                k.take(dmg)
        self.notify("ГАОН-ПУШКА!", (255, 230, 120))

    def player_ship_damage(self, dmg):
        pd = self.pd
        if self.ship.burst_t > 0:
            return
        dmg *= 1 - 0.1 * pd.ship['hull_lvl'] / 3
        pd.ship['hp'] -= dmg
        self.ship.hit_flash = 0.25
        self.cam.add_shake(0.3)
        self.float_text(self.ship.pos, "-" + fmt_num(dmg), (255, 120, 120), 18)

    def ship_hit_at(self, p, r, owner):
        for s in self.ships:
            if s is owner or s.dead:
                continue
            if s.is_player and owner.team == 'player':
                continue
            if not s.is_player and owner.team != 'player' and owner.team == s.team:
                continue
            if dist(s.pos, p) < s.radius * 0.7 + r:
                if s.is_player:
                    self.player_ship_damage(owner.level * 5 + 20)
                    return None
                return s
        return None

    def seaking_at(self, p, r):
        for k in self.kings:
            if not k.dead and dist(k.pos, p) < 90 + r:
                return k
        return None

    def maybe_spawn_ship(self, reg):
        pd = self.pd
        if reg in ('void', 'redline'):
            return
        if len([s for s in self.ships if not s.is_player and not s.dead]) >= 3:
            return
        lvl = self.region_level()
        heat = pd.bounty / 1e8 if pd.faction != 'marine' else 0
        choices = []
        if pd.faction != 'marine':
            choices.append(('marine', 3 + min(6, heat)))
        if pd.faction in ('marine', 'hunter', 'revo'):
            choices.append(('pirate', 5))
        if pd.faction == 'pirate':
            choices.append(('pirate', 2))
            choices.append(('hunter', 1.5))
        if pd.faction == 'revo':
            choices.append(('hunter', 1))
        kind = weighted_choice(choices)
        tier = SHIP_ORDER[min(4, 1 + lvl // 25)]
        p = self.ship.pos + from_angle(random.uniform(0, 6.28), 1400)
        if self.world_block(p):
            return
        if kind == 'marine':
            name = random.choice(["Военный корабль Дозора", "Патруль Дозора", "Фрегат «Справедливость»"])
            s = SeaShip(self, p, 0, 'enemy', lvl, name, tier, pool=['marine', 'marine_rifle', 'marine_officer'] if lvl > 20 else ['marine', 'marine_rifle'],
                        flag='seagull', sail_col=(245, 245, 250))
            s.data['color'] = [240, 240, 245] if tier in ('warship', 'galleon') else [200, 200, 205]
        elif kind == 'hunter':
            s = SeaShip(self, p, 0, 'enemy', lvl, "Охотники за головами", tier, pool=['bandit', 'pirate_gun', 'bandit_big'], flag='cross', sail_col=(200, 180, 130))
        else:
            name = random.choice(["Пираты Ржавого Якоря", "Пираты Кровавой Луны", "Пираты Морского Змея", "Пираты Чёрного Ворона", "Пираты Весёлого Черепа"])
            s = SeaShip(self, p, 0, 'enemy', lvl, name, tier, pool=['pirate', 'pirate_gun', 'pirate_brute'], flag='skull', sail_col=(60, 50, 50))
        s.heading = angle_to(s.pos, self.ship.pos)
        s.sail_target = 2
        self.ships.append(s)
        self.notify(f"На горизонте: {s.name}!", (255, 200, 160))

    def enemy_ai(self, s, dt):
        if s.dead or s.disabled:
            s.sail_target = 0
            return
        pl = self.ship
        d = pl.pos - s.pos
        dd = d.length()
        if dd > 2600:
            s.sail_target = 1
            return
        want = math.atan2(d.y, d.x)
        if dd < 520:
            want += math.pi / 2 * (1 if ang_diff(s.heading, want) < 0 else -1)
            s.sail_target = 1
        else:
            s.sail_target = 3
        s.heading += clamp(ang_diff(s.heading, want), -s.turn * dt * 0.5, s.turn * dt * 0.5)
        if dd < 600:
            fwd = from_angle(s.heading)
            cross = fwd.x * d.y - fwd.y * d.x
            side = 1 if cross > 0 else -1
            lead = pl.pos + from_angle(pl.heading, pl.speed * 0.8)
            s.fire(side, lead, 0)

    def on_ship_sunk(self, s):
        pd = self.pd
        beli = int((800 + s.level * 300) * random.uniform(0.8, 1.3))
        pd.beli += beli
        xp = int(40 * (1 + s.level * 0.8))
        ups = pd.add_xp(xp)
        self.notify(f"{s.name} потоплен! +{fmt_num(beli)} ฿, +{xp} опыта", (255, 220, 120))
        if ups:
            self.notify(f"НОВЫЙ УРОВЕНЬ {pd.level}!", (255, 230, 90))
            self.audio_play('levelup', 1.0)
        self.game.reward_rep(s.level * 30000 if s.flag == 'seagull' else s.level * 15000, quiet=True, kind='ship')
        for _ in range(2):
            self.loot.append(LootBarrel(s.pos + V(random.uniform(-60, 60), random.uniform(-60, 60))))

    def on_seaking_dead(self, k):
        pd = self.pd
        pd.add_item(make_item('sea_king_meat'))
        pd.add_item(make_item('sea_king_scale'))
        xp = int(80 * (1 + k.level * 0.8))
        ups = pd.add_xp(xp)
        self.notify(f"Морской Король повержен! Мясо и чешуя Морского Короля, +{xp} опыта", (220, 170, 255))
        if ups:
            self.notify(f"НОВЫЙ УРОВЕНЬ {pd.level}!", (255, 230, 90))

    def collect_loot(self, l):
        pd = self.pd
        l.dead = True
        self.audio_play('coin', 0.8)
        lvl = self.region_level()
        if l.kind == 'wreck':
            beli = int(3000 * (1 + lvl * 0.3))
            pd.beli += beli
            msg = f"Обломки корабля: +{fmt_num(beli)} ฿"
            for _ in range(2):
                iid = random.choice(['wood', 'iron', 'steel', 'gold', 'cola', 'sea_king_meat'])
                pd.add_item(make_item(iid))
            if random.random() < 0.04:
                fid = random.choice(FRUIT_ORDER[:20])
                pd.inventory.append(fruit_item(fid))
                msg += " ...и ДЬЯВОЛЬСКИЙ ФРУКТ!"
            self.notify(msg, (255, 220, 120))
        else:
            r = random.random()
            if r < 0.4:
                beli = int(300 * (1 + lvl * 0.25))
                pd.beli += beli
                self.float_text(l.pos, f"+{fmt_num(beli)} ฿", (255, 220, 90))
            elif r < 0.7:
                pd.ship['cola'] += 2
                self.float_text(l.pos, "+2 колы", (200, 140, 90))
            elif r < 0.9:
                iid = random.choice(['wood', 'wood', 'iron', 'meat', 'fish'])
                pd.add_item(make_item(iid))
                self.float_text(l.pos, "+ " + ITEMS[iid]['name'], (220, 220, 220))
            elif r < 0.997:
                pd.add_item(make_item('meat'))
                self.float_text(l.pos, "+ Мясо", (220, 160, 120))
            else:
                fid = random.choice(FRUIT_ORDER[:16])
                pd.inventory.append(fruit_item(fid))
                self.notify("В бочке ДЬЯВОЛЬСКИЙ ФРУКТ: " + FRUITS[fid]['name'] + "!", (255, 150, 255))

    def start_fishing(self):
        self.fishing = dict(t=0.0, pos=0.0, dirn=1, zone=random.uniform(0.2, 0.75), w=0.14, wait=random.uniform(1.0, 2.5), bite=False)
        self.notify("Рыбалка: жди поклёвку, затем жми F, когда метка в зелёной зоне.", (200, 230, 255))

    def update_fishing(self, dt):
        f = self.fishing
        g = self.game
        f['t'] += dt
        if not f['bite']:
            if f['t'] > f['wait']:
                f['bite'] = True
                self.audio_play('splash', 0.6)
            if pygame.K_f in g.kp and f['t'] > 0.2:
                self.fishing = None
            return
        f['pos'] += f['dirn'] * dt * 1.3
        if f['pos'] > 1:
            f['pos'] = 1
            f['dirn'] = -1
        if f['pos'] < 0:
            f['pos'] = 0
            f['dirn'] = 1
        if pygame.K_f in g.kp:
            if f['zone'] <= f['pos'] <= f['zone'] + f['w']:
                pd = self.pd
                n = random.randint(1, 3)
                for _ in range(n):
                    pd.add_item(make_item('fish'))
                if random.random() < 0.2:
                    pd.add_item(make_item('meat'))
                self.notify(f"Улов: рыба ×{n}!" + (" Кок приготовит еду (меню → Команда)." if any(c['role'] == 'cook' for c in pd.crew) else ""), (150, 230, 255))
                self.audio_play('coin', 0.6)
            else:
                self.notify("Сорвалась...", (200, 200, 200))
            self.fishing = None
        if f['t'] > f['wait'] + 6:
            self.fishing = None

    def ship_wrecked(self):
        pd = self.pd
        pd.ship['hp'] = pd.ship['max_hp'] * 0.5
        lost = int(pd.beli * 0.15)
        pd.beli -= lost
        last = pd.last_island or ISLAND_ORDER[0]
        p = ISLANDS[last]['pos']
        self.ship.pos = V(p) + V(0, self.island_radius(last) + 220)
        self.ship.speed = 0
        self.ship.sail_target = 0
        self.ships = [self.ship]
        self.kings = []
        self.notify(f"Корабль разбит! Команда дотащила его до {ISLANDS[last]['name']}. Потеряно {fmt_num(lost)} ฿", (255, 150, 150))

    # ---------------- отрисовка ----------------
    def tex(self, reg):
        if reg not in self.textures:
            self.textures[reg] = [make_wave_texture(11 + i * 7 + hash(reg) % 100, REGION_SEA_COL.get(reg, (40, 110, 190))) for i in range(2)]
        return self.textures[reg]

    def draw(self, scr):
        if self.map_open:
            self.draw_world_map(scr)
            return
        ox, oy = self.cam.offset(W, H)
        reg = region_at(self.cam.pos.x, self.cam.pos.y)
        texs = self.tex(reg)
        ts = 256
        for li, (dx_, dy_) in enumerate(((14, 6), (-9, 11))):
            tex = texs[li]
            sx_ = ox + self.t * dx_
            sy_ = oy + self.t * dy_
            tx0 = -(sx_ % ts)
            ty0 = -(sy_ % ts)
            if li == 1:
                tex.set_alpha(110)
            y = ty0
            while y < H:
                x = tx0
                while x < W:
                    scr.blit(tex, (x, y))
                    x += ts
                y += ts
        if random.random() < 0.6:
            for _ in range(3):
                self.particles.add(ox + random.uniform(0, W), oy + random.uniform(0, H), 0, 0, 0.5, 3, (230, 245, 255), 'glow')
        # Ред Лайн
        for (x0, x1) in (REDLINE1_X, REDLINE2_X):
            if x1 - ox > -100 and x0 - ox < W + 100:
                rr = pygame.Rect(x0 - ox, 0, x1 - x0, H)
                pygame.draw.rect(scr, (150, 70, 50), rr)
                for i in range(0, H, 40):
                    pygame.draw.line(scr, (120, 50, 40), (rr.x, i + (oy % 40)), (rr.right, i + 20 + (oy % 40)), 3)
                pygame.draw.rect(scr, (90, 40, 30), rr, 4)
        gy0 = REVERSE_GATE_Y[0] - oy
        if REDLINE1_X[0] - ox < W and REDLINE1_X[1] - ox > 0:
            col = (90, 180, 255) if 'reverse' in self.pd.flags else (90, 90, 120)
            pygame.draw.rect(scr, col, (REDLINE1_X[0] - ox, gy0, REDLINE1_X[1] - REDLINE1_X[0], REVERSE_GATE_Y[1] - REVERSE_GATE_Y[0]))
            draw_text(scr, "РЕВЁРС МАУНТИН", (REDLINE1_X[0] - ox + 400, gy0 - 30), 22, (255, 255, 255), "center", 3)
        if REDLINE2_X[0] - ox < W + 300 and REDLINE2_X[1] - ox > -300:
            gp = V(FISHMAN_GATE_POS) - V(ox, oy)
            draw_glow(scr, (gp.x - 250, gp.y), 140, (120, 200, 255), 0.4 + 0.2 * math.sin(self.t * 2))
            draw_text(scr, "Спуск к Острову Рыболюдей", (gp.x - 250, gp.y - 160), 18, (220, 240, 255), "center", 2)
        # калм белт
        if reg == 'calm':
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((200, 230, 240, 25))
            scr.blit(ov, (0, 0))
        # Нок-ап
        if 'knockup' in self.pd.flags:
            kp = V(KNOCKUP_POS) - V(ox, oy)
            if -400 < kp.x < W + 400 and -400 < kp.y < H + 400:
                for i in range(4):
                    r = 80 + i * 50 + (self.t * 40) % 50
                    pygame.draw.ellipse(scr, (230, 245, 255), (kp.x - r, kp.y - r * 0.6, r * 2, r * 1.2), 2)
                draw_text(scr, "Поток Нок-Ап (E)", (kp.x, kp.y - 120), 18, (255, 255, 255), "center", 2)
        # острова
        pd = self.pd
        nxt = self.next_story_island()
        for iid in self.known_islands():
            isl = ISLANDS[iid]
            ip = V(isl['pos'])
            R = self.island_radius(iid)
            sx, sy = ip.x - ox, ip.y - oy
            if sx < -R - 300 or sy < -R - 300 or sx > W + R + 300 or sy > H + R + 300:
                continue
            ic = self.island_icons.get(iid)
            if ic is None:
                ic = make_island_icon(iid, isl)
                self.island_icons[iid] = ic
            scr.blit(ic, (sx - ic.get_width() / 2, sy - ic.get_height() / 2))
            st = pd.island_state(iid)
            col = (180, 255, 180) if st['done'] else ((255, 230, 120) if iid == nxt else (255, 255, 255))
            draw_text(scr, isl['name'], (sx, sy - R * 0.85 - 40), 20, col, "center", 3)
            lvtxt = f"Ур. {isl['lvl']}" + ("  ✓" if st['done'] else "")
            draw_text(scr, lvtxt.replace("✓", "пройден"), (sx, sy - R * 0.85 - 16), 15, col, "center", 2)
        for l in self.loot:
            l.draw(scr, ox, oy)
        for w in self.whirls:
            w.draw(scr, ox, oy)
        for k in self.kings:
            k.draw(scr, ox, oy)
        for s in sorted(self.ships, key=lambda s: s.pos.y):
            s.draw(scr, ox, oy, self.t)
        for b in self.balls:
            b.draw(scr, ox, oy)
        for e in self.effects:
            e.draw(scr, ox, oy)
        self.particles.draw(scr, ox, oy)
        for tx in self.texts:
            draw_text(scr, tx.text, (tx.x - ox, tx.y - oy), tx.size, tx.col, "center", 2, alpha=int(255 * clamp(tx.life, 0, 1)))
        # погода
        if self.weather == 'storm':
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((20, 30, 50, 90))
            scr.blit(ov, (0, 0))
            for p in self.rain:
                p[1] += 1000 * p[2] * 0.016
                p[0] -= 300 * 0.016
                if p[1] > H:
                    p[1] = -10
                    p[0] = random.uniform(0, W + 200)
                pygame.draw.line(scr, (170, 190, 220), (p[0], p[1]), (p[0] + 5, p[1] - 16), 1)
        elif self.weather == 'fog':
            ov = pygame.Surface((W, H), pygame.SRCALPHA)
            ov.fill((210, 215, 225, 110))
            scr.blit(ov, (0, 0))
        if self.flash_t > 0:
            fl = pygame.Surface((W, H))
            fl.fill((255, 255, 255))
            fl.set_alpha(int(200 * self.flash_t / 0.12))
            scr.blit(fl, (0, 0))
        self.draw_hud(scr)

    def draw_hud(self, scr):
        pd = self.pd
        sh = self.ship
        s = pd.ship
        panel(scr, (12, H - 132, 360, 120), (15, 18, 30), 190, (200, 170, 110), 12)
        draw_text(scr, f"{s['name']}  ({SHIP_TIERS[s['tier']]['name']})", (24, H - 126), 16, (255, 240, 200), "topleft", 2)
        bar(scr, (24, H - 102, 330, 16), s['hp'] / s['max_hp'], (200, 140, 60))
        draw_text(scr, f"Корпус {fmt_num(max(0, s['hp']))}/{fmt_num(s['max_hp'])}", (189, H - 102), 13, (255, 255, 255), "midtop", 2)
        for i in range(3):
            c = (240, 240, 230) if sh.sail_target > i else (70, 70, 80)
            pygame.draw.rect(scr, c, (24 + i * 34, H - 78, 28, 18), border_radius=4)
        draw_text(scr, "Паруса (W/S)", (130, H - 78), 14, (220, 220, 220), "topleft", 2)
        draw_text(scr, f"Скорость: {int(sh.speed / 10)} уз.", (24, H - 54), 15, (200, 230, 255), "topleft", 2)
        draw_text(scr, f"Кола: {s['cola']}", (200, H - 54), 15, (220, 160, 110), "topleft", 2)
        for i, side in enumerate((-1, 1)):
            rl = sh.reload[side]
            col = (120, 230, 120) if rl <= 0 else (200, 120, 80)
            draw_text(scr, ("Левый" if side < 0 else "Правый") + " борт: " + ("готов" if rl <= 0 else f"{rl:.1f}"), (24 + i * 170, H - 32), 14, col, "topleft", 2)
        # компас ветра
        cx, cy = W - 90, H - 90
        pygame.draw.circle(scr, (20, 24, 40), (cx, cy), 62)
        pygame.draw.circle(scr, (200, 170, 110), (cx, cy), 62, 2)
        for i, lab in enumerate("ВЮЗС"):
            a = i * math.pi / 2
            draw_text(scr, "ВЮЗС"[i], (cx + math.cos(a) * 50, cy + math.sin(a) * 50), 13, (200, 200, 200), "center", 1)
        wa = self.wind_dir
        pygame.draw.line(scr, (180, 220, 255), (cx - math.cos(wa) * 30, cy - math.sin(wa) * 30), (cx + math.cos(wa) * 34, cy + math.sin(wa) * 34), 4)
        pygame.draw.polygon(scr, (180, 220, 255), [(cx + math.cos(wa) * 42, cy + math.sin(wa) * 42), (cx + math.cos(wa + 2.6) * 14 + math.cos(wa) * 30, cy + math.sin(wa + 2.6) * 14 + math.sin(wa) * 30),
                                                   (cx + math.cos(wa - 2.6) * 14 + math.cos(wa) * 30, cy + math.sin(wa - 2.6) * 14 + math.sin(wa) * 30)])
        ha = sh.heading
        pygame.draw.line(scr, (255, 220, 120), (cx, cy), (cx + math.cos(ha) * 26, cy + math.sin(ha) * 26), 3)
        draw_text(scr, f"Ветер {int(self.wind_str * 100)}%", (cx, cy + 70), 13, (200, 230, 255), "midtop", 2)
        # лог поуз
        nxt = self.next_story_island()
        if nxt and (ISLANDS[nxt]['region'] == 'east' or 'log_pose' in pd.flags or 'reverse' in pd.flags):
            tp = V(ISLANDS[nxt]['pos']) if not ISLANDS[nxt].get('hidden') else V(KNOCKUP_POS)
            a = angle_to(sh.pos, tp)
            lx, ly = W - 230, H - 90
            pygame.draw.circle(scr, (20, 24, 40), (lx, ly), 44)
            pygame.draw.circle(scr, (220, 200, 120), (lx, ly), 44, 2)
            pygame.draw.line(scr, (255, 80, 60), (lx, ly), (lx + math.cos(a) * 34, ly + math.sin(a) * 34), 4)
            pygame.draw.circle(scr, (255, 255, 255), (lx, ly), 5)
            draw_text(scr, "Лог Поуз" if 'log_pose' in pd.flags else "Компас", (lx, ly + 50), 13, (230, 220, 160), "midtop", 2)
            nm_ = ISLANDS[nxt]['name'] if not ISLANDS[nxt].get('hidden') else "Поток Нок-Ап → " + ISLANDS[nxt]['name']
            draw_text(scr, nm_, (lx, ly - 64), 13, (255, 230, 150), "midbottom", 2)
            draw_text(scr, f"{int(dist(sh.pos, tp) / 100)} миль", (lx, ly + 66), 12, (200, 200, 200), "midtop", 1)
        draw_text(scr, REGION_NAMES.get(region_at(sh.pos.x, sh.pos.y), ""), (18, 12), 22, (255, 240, 200), "topleft", 3)
        draw_text(scr, f"฿ {fmt_num(pd.beli)}   ·   {pd.title()}", (18, 40), 16, (255, 220, 120), "topleft", 2)
        draw_text(scr, "M — карта мира   Tab — меню   ЛКМ — залп   ПКМ — Гаон   Space — Coup de Burst   F — рыбалка", (W / 2, H - 18), 13, (200, 210, 230), "midbottom", 2)
        if self.region_banner > 0:
            a = clamp(self.region_banner, 0, 1)
            draw_text(scr, REGION_NAMES.get(self.region, ""), (W / 2, H * 0.22), 46, (255, 255, 255), "center", 4, alpha=int(255 * a))
        for i, (txt, col, t) in enumerate(self.notifications):
            draw_text(scr, txt, (W / 2, 60 + i * 28), 19, col, "midtop", 3, alpha=int(255 * clamp(t, 0, 1)))
        ni = self.nearby_interaction()
        if ni:
            kind, obj = ni
            txt = {'island': lambda: f"E — высадиться: {ISLANDS[obj]['name']} (ур. {ISLANDS[obj]['lvl']})",
                   'knockup': lambda: "E — войти в Поток Нок-Ап (на Скайпию)",
                   'fishman_gate': lambda: "E — погрузиться к Острову Рыболюдей",
                   'back_gate': lambda: "E — вернуться в Рай",
                   'board': lambda: f"E — АБОРДАЖ: {obj.name}"}[kind]()
            draw_text(scr, txt, (W / 2, H - 150), 22, (255, 255, 255), "center", 3)
        if self.fishing is not None:
            f = self.fishing
            r = pygame.Rect(W / 2 - 200, H / 2 + 80, 400, 30)
            panel(scr, r.inflate(20, 40), (15, 18, 30), 220, (150, 200, 255), 10)
            if f['bite']:
                pygame.draw.rect(scr, (40, 50, 70), r)
                pygame.draw.rect(scr, (80, 220, 120), (r.x + r.w * f['zone'], r.y, r.w * f['w'], r.h))
                pygame.draw.rect(scr, (255, 255, 255), (r.x + r.w * f['pos'] - 3, r.y - 6, 6, r.h + 12))
                draw_text(scr, "КЛЮЁТ! Жми F!", (W / 2, r.y - 30), 22, (255, 230, 120), "center", 2)
            else:
                draw_text(scr, "Ждём поклёвку..." + "." * (int(f['t'] * 2) % 3), (W / 2, r.centery), 20, (220, 230, 255), "center", 2)
        if self.gaon_charge > 0:
            bar(scr, (W / 2 - 100, H / 2 + 60, 200, 10), self.gaon_charge / 1.5, (255, 220, 120))

    def draw_world_map(self, scr):
        if not hasattr(self, '_map_bg'):
            self._map_bg = make_parchment(W, H, 77)
        scr.blit(self._map_bg, (0, 0))
        pd = self.pd
        mx0, my0, mw_, mh_ = 60, 90, W - 120, H - 170
        sx = mw_ / WORLD_W
        sy = mh_ / WORLD_H
        def P(x, y):
            return (mx0 + x * sx, my0 + y * sy)
        pygame.draw.rect(scr, (150, 190, 210), (mx0, my0, mw_, mh_))
        # регионы
        for (a, b) in CALM_BELTS:
            r = pygame.Rect(P(REDLINE1_X[1], a), (sx * (REDLINE2_X[0] - REDLINE1_X[1]), sy * (b - a)))
            pygame.draw.rect(scr, (175, 205, 210), r)
        r = pygame.Rect(P(REDLINE1_X[1], GL_BAND[0]), (sx * (REDLINE2_X[0] - REDLINE1_X[1]), sy * (GL_BAND[1] - GL_BAND[0])))
        pygame.draw.rect(scr, (120, 170, 210), r)
        r = pygame.Rect(P(REDLINE2_X[1], NW_BAND[0]), (sx * (WORLD_W - REDLINE2_X[1]), sy * (NW_BAND[1] - NW_BAND[0])))
        pygame.draw.rect(scr, (100, 140, 190), r)
        for (x0, x1) in (REDLINE1_X, REDLINE2_X):
            pygame.draw.rect(scr, (160, 70, 50), (P(x0, 0)[0], my0, max(3, (x1 - x0) * sx), mh_))
        draw_text(scr, "ИСТ БЛЮ", P(6500, 3000), 22, (60, 40, 30), "center", 0)
        draw_text(scr, "ГРАНД ЛАЙН: РАЙ", P(29000, (GL_BAND[0] + GL_BAND[1]) / 2), 22, (40, 30, 30), "center", 0)
        draw_text(scr, "НОВЫЙ МИР", P(59000, (NW_BAND[0] + NW_BAND[1]) / 2), 22, (230, 230, 240), "center", 0)
        draw_text(scr, "Затишье", P(29000, 11200), 14, (80, 60, 40), "center", 0)
        draw_text(scr, "Затишье", P(29000, 20700), 14, (80, 60, 40), "center", 0)
        draw_text(scr, "Ред Лайн", P(14400, 2000), 14, (120, 40, 30), "center", 0)
        draw_text(scr, "Ред Лайн", P(44400, 2000), 14, (120, 40, 30), "center", 0)
        nxt = self.next_story_island()
        known = set(self.known_islands())
        prev = None
        for iid in ISLAND_ORDER:
            isl = ISLANDS[iid]
            if isl.get('hidden'):
                continue
            p = P(*isl['pos'])
            if prev is not None and iid in known:
                pygame.draw.line(scr, (140, 100, 70), prev, p, 1)
            if iid in known:
                prev = p
        for iid, isl in ISLANDS.items():
            if isl.get('hidden') or iid not in known:
                continue
            p = P(*isl['pos'])
            st = pd.island_state(iid)
            col = (60, 140, 60) if st['done'] else ((220, 120, 30) if iid == nxt else (90, 70, 50))
            pygame.draw.circle(scr, col, (int(p[0]), int(p[1])), 7)
            pygame.draw.circle(scr, (40, 30, 20), (int(p[0]), int(p[1])), 7, 2)
            draw_text(scr, isl['name'].split(':')[0][:22], (p[0], p[1] - 10), 11, (50, 35, 25), "midbottom", 0)
        sp = P(self.ship.pos.x, self.ship.pos.y)
        pygame.draw.circle(scr, (220, 30, 30), (int(sp[0]), int(sp[1])), 6)
        pygame.draw.line(scr, (220, 30, 30), sp, (sp[0] + math.cos(self.ship.heading) * 16, sp[1] + math.sin(self.ship.heading) * 16), 3)
        draw_text(scr, "КАРТА МИРА", (W / 2, 24), 40, (70, 45, 25), "midtop", 0)
        draw_text(scr, "Зелёный — пройден, оранжевый — следующая цель. M/Esc — закрыть.", (W / 2, H - 50), 16, (70, 45, 25), "midtop", 0)
        if 'eternal_pose' in pd.flags or pd.count('eternal_pose') > 0:
            draw_text(scr, "Этернал Поуз: кликни по пройденному острову для быстрого путешествия.", (W / 2, H - 28), 14, (90, 60, 30), "midtop", 0)
            if 1 in self.game.mbp:
                mx, my = self.game.mouse
                for iid in known:
                    if pd.island_state(iid)['done']:
                        p = P(*ISLANDS[iid]['pos'])
                        if dist(p, (mx, my)) < 12:
                            self.ship.pos = V(ISLANDS[iid]['pos']) + V(0, self.island_radius(iid) + 200)
                            self.map_open = False
                            self.notify("Этернал Поуз привёл тебя к " + ISLANDS[iid]['name'], (255, 230, 150))
                            break

# ==================================================================
#  ДОП. КОНТЕНТ МОРЯ: ВОДОВОРОТЫ, БАСТЕР КОЛЛ
# ==================================================================
class Whirlpool:
    def __init__(self, pos, r=260):
        self.pos = V(pos)
        self.r = r
        self.t = 0.0
        self.life = random.uniform(40, 70)

    def update(self, dt, sc):
        self.t += dt
        self.life -= dt
        sh = sc.ship
        d = self.pos - sh.pos
        dd = d.length()
        if dd < self.r * 1.6 and sh.burst_t <= 0:
            k = 1 - dd / (self.r * 1.6)
            sh.pos += (d.normalize() * 120 + d.normalize().rotate(90) * 160) * k * dt
            sh.heading += 0.6 * k * dt
            if dd < self.r * 0.35:
                sc.player_ship_damage(60 * dt * (1 + sc.region_level() * 0.05))
        return self.life > 0

    def draw(self, surf, ox, oy):
        x, y = self.pos.x - ox, self.pos.y - oy
        if x < -400 or y < -400 or x > W + 400 or y > H + 400:
            return
        for i in range(6):
            rr = self.r * (1 - i * 0.15)
            a0 = self.t * (1.5 + i * 0.4)
            rect = pygame.Rect(x - rr, y - rr * 0.6, rr * 2, rr * 1.2)
            pygame.draw.arc(surf, (220, 240, 255) if i % 2 == 0 else (30, 70, 120), rect, a0, a0 + 2.2, 3)
            pygame.draw.arc(surf, (220, 240, 255) if i % 2 else (30, 70, 120), rect, a0 + 3.14, a0 + 5.0, 2)
        alpha_circle_e(surf, (x, y), self.r * 0.35, (10, 30, 60), 160)

_orig_sea_init = SeaScene.__init__

def _sea_init_ext(self, game, start_pos=None, heading=None):
    _orig_sea_init(self, game, start_pos, heading)
    self.whirls = []
    self.whirl_t = random.uniform(30, 60)
    self.buster_check()

SeaScene.__init__ = _sea_init_ext

def _buster_check(self):
    pd = self.pd
    if 'buster_pending' in pd.flags and pd.faction != 'marine':
        pd.flags.discard('buster_pending')
        lvl = max(20, self.region_level() + 4)
        n = 5
        for i in range(n):
            p = self.ship.pos + from_angle(i * 6.28 / n + 0.3, 1100)
            s = SeaShip(self, p, 0, 'enemy', lvl, "Бастер Колл: военный корабль", 'warship' if lvl > 50 else 'galleon',
                        pool=['marine', 'marine_officer', 'vice_admiral'], flag='seagull', sail_col=(245, 245, 250))
            s.data['color'] = [240, 240, 245]
            s.heading = angle_to(s.pos, self.ship.pos)
            s.sail_target = 3
            s.buster = True
            self.ships.append(s)
        self.notify("БАСТЕР КОЛЛ! Пять вице-адмиралов и флот Дозора идут за тобой!", (255, 90, 90))
        self.audio_play('gong', 1.0)
        self.game.audio.play_music('boss', fade=800)
        self.buster_active = True

SeaScene.buster_check = _buster_check

_orig_sea_update = SeaScene.update

def _sea_update_ext(self, dt):
    _orig_sea_update(self, dt)
    if self.map_open:
        return
    reg = region_at(self.ship.pos.x, self.ship.pos.y)
    self.whirl_t -= dt
    if self.whirl_t <= 0:
        self.whirl_t = random.uniform(35, 70)
        if reg in ('new', 'paradise') and len(self.whirls) < 2 and random.random() < (0.7 if reg == 'new' else 0.35):
            p = self.ship.pos + from_angle(random.uniform(0, 6.28), random.uniform(700, 1100))
            if not self.world_block(p):
                self.whirls.append(Whirlpool(p, random.uniform(200, 320)))
                self.notify("Впереди водоворот! Держись подальше.", (180, 220, 255))
    self.whirls = [w for w in self.whirls if w.update(dt, self)]
    if getattr(self, 'buster_active', False):
        if not any(getattr(s, 'buster', False) and not s.dead for s in self.ships):
            self.buster_active = False
            pd = self.pd
            pd.bounty += 50_000_000
            pd.beli += 500000
            self.notify("Ты пережил Бастер Колл! Награда +50 млн, +500 000 ฿", (255, 230, 120))
            self.game.audio.play_music('sea')

SeaScene.update = _sea_update_ext


# ==================================================================
#  ИНТЕРФЕЙС: ОВЕРЛЕИ И МЕНЮ
# ==================================================================
def ui_button(scr, game, rect, text, enabled=True, size=18, selected=False, col=(40, 46, 70), tip=None):
    r = pygame.Rect(rect)
    hover = r.collidepoint(game.mouse) and enabled
    c = col if enabled else (35, 35, 40)
    if selected:
        c = add_col(col, 40)
    if hover:
        c = add_col(c, 25)
    pygame.draw.rect(scr, (15, 12, 15), r.inflate(4, 4), border_radius=9)
    pygame.draw.rect(scr, c, r, border_radius=8)
    pygame.draw.rect(scr, (230, 200, 130) if (hover or selected) else (120, 110, 90), r, 2, border_radius=8)
    draw_text(scr, text, r.center, size, (255, 255, 255) if enabled else (120, 120, 130), "center", 2)
    if hover and tip:
        game.tooltip = tip
    if hover and 1 in game.mbp:
        game.audio.play('ui', 0.7)
        game.mbp.discard(1)
        return True
    return False

def speaker_info(game, who):
    pd = game.pd
    if who == 'me':
        return pd.name, pd.app
    if who == 'nar':
        return None, None
    if who.startswith('x:'):
        name = who[2:]
        rng = random.Random(stable_seed(name))
        app = default_app(skin=rng.choice(SKIN_TONES[:6]), hair=rng.choice(HAIR_STYLES), hair_col=rng.choice(HAIR_COLORS), outfit=rng.choice(['shirt', 'robe', 'coat', 'vest', 'kimono']),
                          top=rng.choice(CLOTH_COLORS), bottom=rng.choice(CLOTH_COLORS), hat=rng.choice(['none', 'none', 'cap', 'bandana', 'top_hat', 'wide']),
                          hat_col=rng.choice(CLOTH_COLORS), features=tuple(rng.sample(['beard', 'mustache', 'sunglasses', 'scar_eye', 'grin', 'stitch'], rng.randint(0, 1))))
        if 'Шанкс' in name:
            app = dict(BOSSES['shanks']['app'])
        elif 'Вегапанк' in name:
            app = default_app(hair='afro', hair_col=(120, 70, 50), outfit='coat', top=(240, 240, 240), features=('beard',))
        elif 'Ло' in name and 'Трафальгар' in name:
            app = default_app(hat='cap', hat_col=(240, 240, 240), hair='messy', hair_col=(30, 30, 40), outfit='coat', top=(30, 30, 40), features=('beard',), weapon='sword1')
        elif 'Рэйли' in name:
            app = dict(MENTORS['rayleigh']['app'])
        elif 'Кума' in name:
            app = default_app(scale=1.4, hat='cap', hat_col=(200, 180, 140), outfit='coat', top=(40, 40, 50), features=('beard',))
        elif 'Ямато' in name:
            app = dict(COMPANIONS['yamato']['app'])
        elif 'Хьёгоро' in name:
            app = dict(MENTORS['hyogoro']['app'])
        elif 'Коби' in name:
            app = dict(COMPANIONS['koby']['app'])
        elif 'Тасиги' in name:
            app = dict(COMPANIONS['tashigi']['app'])
        elif 'Кизару' in name:
            app = dict(BOSSES['kizaru']['app'])
        elif 'Белоус' in name:
            app = dict(BOSSES['whitebeard']['app'])
        elif 'Толстяк' in name:
            app = dict(BOSSES['blackbeard']['app'])
        elif 'Кэррот' in name:
            app = dict(COMPANIONS['carrot']['app'])
        elif 'Бартоломео' in name:
            app = dict(COMPANIONS['bartolomeo']['app'])
        elif 'Сирахоси' in name:
            app = default_app(scale=1.0, hair='long', hair_col=(240, 140, 180), outfit='robe', top=(240, 220, 250), skin=(250, 230, 230), features=('fishman',))
        elif 'Санджи' in name:
            app = default_app(hair='slick', hair_col=(240, 210, 110), outfit='suit', top=(30, 30, 35), bottom=(30, 30, 35), features=('cigar',))
        elif 'Брук' in name:
            app = default_app(hair='afro', hair_col=(20, 20, 20), skin=(240, 240, 235), hat='top_hat', hat_col=(30, 30, 30), outfit='suit', top=(30, 30, 35))
        return name, app
    if who in BOSSES:
        return BOSSES[who]['name'], BOSSES[who]['app']
    if who in COMPANIONS:
        return COMPANIONS[who]['name'], COMPANIONS[who]['app']
    if who in MENTORS:
        return MENTORS[who]['name'], MENTORS[who]['app']
    return who, default_app()

class Overlay:
    pauses = True
    done = False
    def handle_event(self, e):
        pass
    def update(self, dt):
        pass
    def draw(self, scr):
        pass

class DialogueOverlay(Overlay):
    def __init__(self, game, lines, on_done=None):
        self.game = game
        self.lines = [l for l in lines if l]
        self.on_done = on_done
        self.i = 0
        self.chars = 0.0
        self.cache = {}
        self.t = 0
        if not self.lines:
            self.finish()

    def finish(self):
        self.done = True
        if self.on_done:
            cb = self.on_done
            self.on_done = None
            cb()

    def update(self, dt):
        g = self.game
        self.t += dt
        self.chars += dt * 55
        if 1 in g.mbp or pygame.K_SPACE in g.kp or pygame.K_RETURN in g.kp or pygame.K_e in g.kp:
            g.mbp.discard(1)
            who, text = self.lines[self.i]
            if self.chars < len(text):
                self.chars = len(text)
            else:
                self.i += 1
                self.chars = 0
                g.audio.play('ui', 0.5)
                if self.i >= len(self.lines):
                    self.finish()
        if pygame.K_ESCAPE in g.kp:
            self.finish()

    def draw(self, scr):
        if self.done or self.i >= len(self.lines):
            return
        who, text = self.lines[self.i]
        name, app = speaker_info(self.game, who)
        dim = pygame.Surface((W, 260), pygame.SRCALPHA)
        for y in range(260):
            a = int(200 * (y / 260) ** 1.2)
            pygame.draw.line(dim, (0, 0, 0, a), (0, y), (W, y))
        scr.blit(dim, (0, H - 260))
        r = pygame.Rect(40, H - 200, W - 80, 180)
        panel(scr, r, (20, 18, 28), 235, (230, 200, 130), 14, 3)
        tx = r.x + 30
        if app is not None:
            key = who
            if key not in self.cache:
                s = pygame.Surface((190, 190), pygame.SRCALPHA)
                draw_portrait(s, (0, 0, 190, 190), app, 'normal')
                self.cache[key] = s
            pr = pygame.Rect(r.x + 14, r.y - 70, 190, 190)
            pygame.draw.rect(scr, (40, 34, 50), (pr.x, pr.y + 40, pr.w, pr.h - 40), border_radius=12)
            scr.blit(self.cache[key], pr.topleft)
            pygame.draw.rect(scr, (230, 200, 130), (pr.x, pr.y + 40, pr.w, pr.h - 40), 3, border_radius=12)
            tx = pr.right + 24
            nr = pygame.Rect(tx - 6, r.y - 18, get_font(22).size(name)[0] + 30, 34)
            panel(scr, nr, (150, 30, 40) if who in BOSSES and who != 'me' else (40, 60, 120), 255, (240, 220, 160), 8)
            draw_text(scr, name, (nr.x + 15, nr.y + 5), 22, (255, 255, 255), "topleft", 2)
        shown = text[:int(self.chars)]
        col = (230, 220, 190) if who == 'nar' else (255, 255, 255)
        lines = wrap_text(get_font(22), shown, r.right - tx - 30)
        for i, ln in enumerate(lines[:5]):
            draw_text(scr, ln, (tx, r.y + 26 + i * 30), 22, col, "topleft", 2)
        if self.chars >= len(text) and int(self.t * 3) % 2 == 0:
            draw_text(scr, "▼", (r.right - 30, r.bottom - 30), 20, (255, 220, 140), "center", 2)
        draw_text(scr, "ЛКМ / Space — далее   Esc — пропустить", (r.right - 20, r.bottom + 4), 12, (180, 180, 190), "topright", 1)

class ConfirmOverlay(Overlay):
    def __init__(self, game, text, yes, no=None):
        self.game = game
        self.text = text
        self.yes = yes
        self.no = no

    def update(self, dt):
        if pygame.K_ESCAPE in self.game.kp:
            self.done = True
            if self.no:
                self.no()

    def draw(self, scr):
        g = self.game
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        scr.blit(dim, (0, 0))
        r = pygame.Rect(W / 2 - 330, H / 2 - 110, 660, 220)
        panel(scr, r, (25, 22, 35), 245, (230, 200, 130), 14, 3)
        for i, ln in enumerate(wrap_text(get_font(22), self.text, 600)):
            draw_text(scr, ln, (W / 2, r.y + 30 + i * 30), 22, (255, 255, 255), "midtop", 2)
        if ui_button(scr, g, (r.centerx - 210, r.bottom - 70, 190, 46), "Да", col=(50, 110, 60)):
            self.done = True
            self.yes()
        if ui_button(scr, g, (r.centerx + 20, r.bottom - 70, 190, 46), "Нет", col=(110, 50, 50)):
            self.done = True
            if self.no:
                self.no()

class MessageOverlay(Overlay):
    def __init__(self, game, title, lines, on_done=None, poster=None, col=(230, 200, 130)):
        self.game = game
        self.title = title
        self.lines = lines
        self.on_done = on_done
        self.poster = poster
        self.t = 0
        self.col = col

    def update(self, dt):
        self.t += dt
        g = self.game
        if self.t > 0.6 and (pygame.K_RETURN in g.kp or pygame.K_SPACE in g.kp or pygame.K_ESCAPE in g.kp):
            self.close()

    def close(self):
        self.done = True
        if self.on_done:
            cb = self.on_done
            self.on_done = None
            cb()

    def draw(self, scr):
        g = self.game
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        scr.blit(dim, (0, 0))
        hw = 900 if self.poster else 700
        r = pygame.Rect(W / 2 - hw / 2, 80, hw, H - 160)
        panel(scr, r, (25, 22, 35), 245, self.col, 16, 3)
        draw_text(scr, self.title, (r.centerx, r.y + 20), 36, (255, 230, 150), "midtop", 3)
        tx = r.x + 40
        y = r.y + 80
        for ln in self.lines:
            if isinstance(ln, tuple):
                txt, c = ln
            else:
                txt, c = ln, (240, 240, 240)
            for sub in wrap_text(get_font(19), txt, (hw - 380) if self.poster else hw - 80):
                draw_text(scr, sub, (tx, y), 19, c, "topleft", 2)
                y += 26
        if self.poster:
            k = ease_back(min(1, self.t / 0.7))
            p = self.poster
            ps = pygame.transform.rotozoom(p, (1 - k) * 25 - 3, 0.85 * k + 0.01)
            scr.blit(ps, (r.right - 300 - ps.get_width() / 2 + 140, r.y + 70 + (1 - k) * -200))
        if self.t > 0.6 and ui_button(scr, g, (r.centerx - 120, r.bottom - 66, 240, 48), "Продолжить", col=(60, 90, 140)):
            self.close()

# ------------------------------------------------------------------
#  МЕНЮ ПАУЗЫ
# ------------------------------------------------------------------
TABS = [('char', "Персонаж"), ('moves', "Приёмы и стили"), ('equip', "Снаряжение"), ('crew', "Команда"), ('ship', "Корабль"), ('log', "Журнал"), ('settings', "Настройки")]
STAT_NAMES = {'str': ("Сила", "Урон кулаков, мечей и стилей"), 'vit': ("Живучесть", "Здоровье и защита"), 'agi': ("Ловкость", "Скорость, выносливость, крит, перезарядка"),
              'haki': ("Воля (Хаки)", "Сила и запас хаки, рост уровней хаки"), 'fruit': ("Сила фрукта", "Урон приёмов дьявольского фрукта")}

class PauseMenu(Overlay):
    def __init__(self, game, tab='char'):
        self.game = game
        self.tab = tab
        self.sel_move = None
        self.sel_item = None
        self.scroll = 0
        self.t = 0
        self.poster = None
        self.poster_val = None

    def update(self, dt):
        self.t += dt
        g = self.game
        if pygame.K_ESCAPE in g.kp or pygame.K_TAB in g.kp:
            self.done = True
            g.apply_player_changes()
        if g.wheel:
            self.scroll = max(0, self.scroll - g.wheel * 40)

    def draw(self, scr):
        g = self.game
        pd = g.pd
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((5, 8, 20, 200))
        scr.blit(dim, (0, 0))
        x = 30
        for tid, name in TABS:
            w_ = get_font(18).size(name)[0] + 34
            if ui_button(scr, g, (x, 16, w_, 40), name, selected=self.tab == tid, size=18):
                self.tab = tid
                self.scroll = 0
                self.sel_move = None
                self.sel_item = None
            x += w_ + 8
        if ui_button(scr, g, (W - 150, 16, 120, 40), "Закрыть", col=(110, 50, 50)):
            self.done = True
            g.apply_player_changes()
        area = pygame.Rect(30, 70, W - 60, H - 100)
        panel(scr, area, (16, 18, 30), 240, (200, 170, 110), 14, 2)
        getattr(self, 'tab_' + self.tab)(scr, area)
        if g.tooltip:
            tip = g.tooltip
            lines = wrap_text(get_font(15), tip, 360)
            mx, my = g.mouse
            r = pygame.Rect(mx + 16, my + 10, 380, len(lines) * 20 + 14)
            if r.right > W:
                r.x = mx - 396
            if r.bottom > H:
                r.y = H - r.h - 4
            panel(scr, r, (10, 10, 18), 245, (230, 200, 130), 8)
            for i, ln in enumerate(lines):
                draw_text(scr, ln, (r.x + 8, r.y + 7 + i * 20), 15, (240, 240, 240), "topleft", 1)

    # --------- персонаж ---------
    def tab_char(self, scr, area):
        g = self.game
        pd = g.pd
        x0, y0 = area.x + 20, area.y + 20
        pr = pygame.Rect(x0, y0, 220, 220)
        pygame.draw.rect(scr, (40, 36, 55), pr, border_radius=14)
        draw_portrait(scr, pr, pd.app, 'normal')
        pygame.draw.rect(scr, (230, 200, 130), pr, 3, border_radius=14)
        draw_text(scr, pd.name, (x0, pr.bottom + 10), 28, (255, 240, 200), "topleft", 2)
        draw_text(scr, f"{RACES[pd.race]['name']} · {FACTIONS[pd.faction]['name']}", (x0, pr.bottom + 44), 17, (210, 210, 230), "topleft", 2)
        draw_text(scr, pd.title(), (x0, pr.bottom + 68), 18, (255, 200, 120), "topleft", 2)
        draw_text(scr, f"Черта: {TRAITS[pd.trait]['name']}", (x0, pr.bottom + 94), 15, (200, 200, 255), "topleft", 2)
        draw_text(scr, f"Уровень {pd.level}   Опыт {fmt_num(pd.xp)} / {fmt_num(xp_need(pd.level))}", (x0, pr.bottom + 120), 16, (180, 220, 255), "topleft", 2)
        draw_text(scr, f"Награда: ฿ {fmt_num(pd.bounty)}", (x0, pr.bottom + 146), 16, (255, 170, 170), "topleft", 2)
        if pd.faction != 'pirate':
            draw_text(scr, f"{FACTIONS[pd.faction]['rep_name']}: {fmt_num(pd.merit)}", (x0, pr.bottom + 170), 16, (170, 220, 255), "topleft", 2)
        if ui_button(scr, g, (x0, pr.bottom + 200, 220, 40), "Плакат «WANTED»"):
            self.poster = make_wanted_poster(pd.name, pd.bounty, pd.app, pd.title())
        # характеристики
        sx = area.x + 300
        draw_text(scr, f"Очки характеристик: {pd.points}", (sx, y0), 22, (255, 230, 120), "topleft", 2)
        for i, (k, (nm_, desc)) in enumerate(STAT_NAMES.items()):
            y = y0 + 44 + i * 52
            draw_text(scr, f"{nm_}: {pd.stats[k]}", (sx, y + 8), 20, (255, 255, 255), "topleft", 2)
            draw_text(scr, desc, (sx, y + 32), 13, (170, 170, 190), "topleft", 1)
            if pd.points > 0:
                if ui_button(scr, g, (sx + 260, y + 4, 40, 34), "+", col=(50, 100, 60)):
                    pd.stats[k] += 1
                    pd.points -= 1
                if pd.points >= 5 and ui_button(scr, g, (sx + 306, y + 4, 54, 34), "+5", col=(50, 100, 60), size=15):
                    pd.stats[k] += 5
                    pd.points -= 5
        st = compute_stats(pd)
        y = y0 + 44 + 5 * 52 + 10
        info = [("Здоровье", fmt_num(st['max_hp'])), ("Сила атаки", fmt_num(st['atk'])), ("Сила фрукта", fmt_num(st['fruit'])), ("Сила хаки", fmt_num(st['haki'])),
                ("Защита", fmt_num(st['defn'])), ("Скорость", fmt_num(st['speed'])), ("Крит", f"{st['crit'] * 100:.1f}%"), ("Выносливость", fmt_num(st['max_st']))]
        for i, (a, b) in enumerate(info):
            draw_text(scr, f"{a}: {b}", (sx + (i % 2) * 200, y + (i // 2) * 26), 16, (210, 230, 210), "topleft", 1)
        # фрукт и хаки
        fx = area.x + 720
        draw_text(scr, "Дьявольский фрукт", (fx, y0), 22, (255, 200, 255), "topleft", 2)
        if pd.fruit:
            F = FRUITS[pd.fruit]
            draw_fruit_icon(scr, (fx + 30, y0 + 70), 24, F['col'])
            draw_text(scr, F['name'], (fx + 70, y0 + 44), 19, (255, 255, 255), "topleft", 2)
            if F.get('real') and pd.fruit_mastery >= 75:
                draw_text(scr, "Истинное имя: " + F['real'], (fx + 70, y0 + 68), 14, (255, 230, 150), "topleft", 1)
            draw_text(scr, F['type'], (fx + 70, y0 + 88), 15, (200, 200, 220), "topleft", 1)
            bar(scr, (fx, y0 + 112, 420, 14), pd.fruit_mastery / 100, (220, 120, 255))
            draw_text(scr, f"Мастерство: {pd.fruit_mastery:.1f} / 100", (fx, y0 + 130), 14, (230, 200, 255), "topleft", 1)
            aw = F['awak']
            ok = pd.fruit_mastery >= 100 and pd.level >= 50
            draw_text(scr, ("✔ " if ok else "Пробуждение: ") + aw['name'] + ("" if ok else " (100% и ур. 50)"), (fx, y0 + 152), 14, (255, 200, 120) if ok else (170, 170, 180), "topleft", 1)
            if pd.fruit2:
                draw_text(scr, "Второй фрукт: " + FRUITS[pd.fruit2]['name'], (fx, y0 + 174), 14, (255, 150, 150), "topleft", 1)
        else:
            draw_text(scr, "Нет. Ты можешь плавать! (+20% к мастерству стилей)", (fx, y0 + 44), 15, (180, 220, 255), "topleft", 1)
            draw_text(scr, "Фрукты: сундуки островов, магазины, морские бочки, аукцион Сабаоди.", (fx, y0 + 66), 14, (170, 170, 190), "topleft", 1)
        hy = y0 + 210
        draw_text(scr, "Хаки", (fx, hy), 22, (200, 160, 255), "topleft", 2)
        for i, (k, nm_, extra) in enumerate((('arm', "Вооружение", "Рюо" if 'ryou' in pd.flags else ""), ('obs', "Наблюдение", "Предвидение" if 'future_sight' in pd.flags else ""),
                                              ('conq', "Королевское", "Покрытие" if 'conq_coat' in pd.flags else ""))):
            y = hy + 36 + i * 46
            cap = pd.haki_cap[k]
            if cap <= 0:
                txt = f"{nm_}: не пробуждено" + (" (нет Качеств Короля)" if k == 'conq' and pd.trait != 'king' else "")
                draw_text(scr, txt, (fx, y), 16, (140, 140, 150), "topleft", 1)
            else:
                draw_text(scr, f"{nm_}: ур. {pd.haki[k]} / {cap}  {extra}", (fx, y), 16, (230, 210, 255), "topleft", 1)
                need = 60 + 60 * pd.haki[k]
                bar(scr, (fx, y + 22, 300, 8), pd.haki_xp[k] / need if pd.haki[k] < cap else 1, (170, 110, 240))
        ssy = hy + 180
        draw_text(scr, "Мастерство стилей", (fx, ssy), 20, (255, 230, 150), "topleft", 2)
        for i, (sid, m) in enumerate(sorted(pd.styles.items(), key=lambda kv: -kv[1])[:6]):
            draw_text(scr, f"{STYLES[sid]['name']}: {m:.0f}", (fx + (i % 2) * 220, ssy + 30 + (i // 2) * 24), 15, (230, 230, 230), "topleft", 1)
        if self.poster is not None:
            r = self.poster.get_rect(center=(W / 2, H / 2))
            scr.blit(self.poster, r)
            if 1 in g.mbp:
                self.poster = None
                g.mbp.discard(1)

    # --------- приёмы ---------
    def tab_moves(self, scr, area):
        g = self.game
        pd = g.pd
        um = pd.unlocked_moves()
        normal = [m for m in um if not MOVES[m].get('ult')]
        ults = [m for m in um if MOVES[m].get('ult')]
        x0, y0 = area.x + 20, area.y + 16
        draw_text(scr, "Слоты (выбери приём справа, затем кликни слот):", (x0, y0), 17, (255, 230, 150), "topleft", 2)
        for i in range(4):
            r = pygame.Rect(x0 + i * 150, y0 + 30, 140, 70)
            mid = pd.loadout[i]
            sel = False
            if ui_button(scr, g, r, "", col=(30, 34, 52), tip=(MOVES[mid]['name'] + ": " + MOVES[mid]['desc']) if mid else None):
                if self.sel_move and self.sel_move in normal:
                    if self.sel_move in pd.loadout:
                        j = pd.loadout.index(self.sel_move)
                        pd.loadout[j] = pd.loadout[i]
                    pd.loadout[i] = self.sel_move
                    self.sel_move = None
            draw_text(scr, str(i + 1), (r.x + 8, r.y + 4), 16, (255, 230, 150), "topleft", 2)
            if mid:
                move_icon(scr, (r.x + 34, r.centery + 4), 20, mid)
                for k_, ln in enumerate(wrap_text(get_font(13), MOVES[mid]['name'], 84)[:3]):
                    draw_text(scr, ln, (r.x + 58, r.y + 10 + k_ * 16), 13, (255, 255, 255), "topleft", 1)
        r = pygame.Rect(x0 + 620, y0 + 30, 200, 70)
        ui_button(scr, g, r, "", col=(60, 40, 20), tip=(MOVES[pd.ult]['name'] + ": " + MOVES[pd.ult]['desc']) if pd.ult else "Ультимейт ещё не открыт")
        draw_text(scr, "R — ульта", (r.x + 8, r.y + 4), 15, (255, 220, 120), "topleft", 2)
        if pd.ult:
            move_icon(scr, (r.x + 34, r.centery + 6), 20, pd.ult)
            for k_, ln in enumerate(wrap_text(get_font(13), MOVES[pd.ult]['name'], 140)[:2]):
                draw_text(scr, ln, (r.x + 60, r.y + 24 + k_ * 16), 13, (255, 240, 200), "topleft", 1)
        # список приёмов
        ly = y0 + 120
        draw_text(scr, f"Открытые приёмы ({len(normal)}):", (x0, ly), 17, (200, 230, 255), "topleft", 2)
        for i, mid in enumerate(normal):
            col_ = i % 3
            row = i // 3
            r = pygame.Rect(x0 + col_ * 270, ly + 28 + row * 50 - self.scroll, 260, 44)
            if r.bottom > area.bottom - 120 or r.top < ly + 20:
                continue
            mv = MOVES[mid]
            if ui_button(scr, g, r, "", selected=self.sel_move == mid, col=(32, 38, 60), tip=f"{mv['desc']}  КД {mv['cd']:.0f}с, выносл. {mv['cost']}"):
                self.sel_move = mid
            move_icon(scr, (r.x + 24, r.centery), 16, mid)
            draw_text(scr, mv['name'][:30], (r.x + 46, r.y + 6), 14, (255, 255, 255), "topleft", 1)
            draw_text(scr, f"КД {mv['cd']:.0f}с · {mv['cost']} выносл.", (r.x + 46, r.y + 24), 12, (180, 190, 210), "topleft", 1)
        # ульты
        uy = area.bottom - 110
        draw_text(scr, "Ультимейты:", (x0, uy), 17, (255, 220, 120), "topleft", 2)
        for i, mid in enumerate(ults[:6]):
            r = pygame.Rect(x0 + i * 180, uy + 26, 170, 40)
            if ui_button(scr, g, r, MOVES[mid]['name'][:20], selected=pd.ult == mid, size=13, col=(60, 40, 20), tip=MOVES[mid]['desc']):
                pd.ult = mid
        # стили
        sx = area.x + 860
        draw_text(scr, "Стиль боя:", (sx, ly), 17, (255, 230, 150), "topleft", 2)
        for i, sid in enumerate(sorted(pd.styles)):
            S_ = STYLES[sid]
            ok = pd.style_usable(sid)
            r = pygame.Rect(sx, ly + 28 + i * 46, 340, 40)
            tip = S_['desc'] + ("" if ok else "  (нужно оружие: " + ("меч" if S_['weapon'] == 'sword' else "клима-такт") + ")")
            if ui_button(scr, g, r, f"{S_['name']} ({pd.styles[sid]:.0f})", enabled=True, selected=pd.style == sid, size=15, tip=tip):
                if ok:
                    pd.style = sid
                else:
                    g.toast("Для этого стиля нужно " + ("экипировать меч" if S_['weapon'] == 'sword' else "клима-такт"))

    # --------- снаряжение ---------
    def tab_equip(self, scr, area):
        g = self.game
        pd = g.pd
        x0, y0 = area.x + 20, area.y + 20
        draw_text(scr, "Экипировка", (x0, y0), 22, (255, 230, 150), "topleft", 2)
        slots = [('weapon', "Оружие"), ('outfit', "Одежда"), ('acc1', "Аксессуар 1"), ('acc2', "Аксессуар 2")]
        for i, (k, nm_) in enumerate(slots):
            r = pygame.Rect(x0, y0 + 40 + i * 74, 330, 64)
            it = pd.equip.get(k)
            tip = self.item_tip(it) if it else None
            if ui_button(scr, g, r, "", col=(30, 34, 52), tip=tip):
                if it:
                    pd.equip[k] = None
                    pd.inventory.append(it)
            draw_text(scr, nm_, (r.x + 8, r.y + 4), 13, (200, 190, 160), "topleft", 1)
            if it:
                draw_item_icon(scr, (r.x + 34, r.centery + 6), 20, it)
                draw_text(scr, it['name'] + (f" +{it['plus']}" if it.get('plus') else ""), (r.x + 64, r.y + 22), 16, RARITY_COLORS[it['rarity']], "topleft", 2)
            else:
                draw_text(scr, "— пусто —", (r.x + 64, r.y + 24), 15, (120, 120, 130), "topleft", 1)
        draw_text(scr, "Клик по слоту — снять. Клик по предмету — надеть / использовать.", (x0, y0 + 350), 14, (170, 170, 190), "topleft", 1)
        mats = [(k, v) for k, v in pd.mats.items() if v > 0]
        draw_text(scr, "Материалы:", (x0, y0 + 380), 17, (200, 230, 200), "topleft", 2)
        for i, (k, v) in enumerate(mats[:14]):
            draw_text(scr, f"{ITEMS[k]['name']}: {v}", (x0 + (i % 2) * 170, y0 + 406 + (i // 2) * 22), 14, (220, 220, 220), "topleft", 1)
        ix = area.x + 380
        draw_text(scr, f"Инвентарь ({len(pd.inventory)})", (ix, y0), 22, (255, 230, 150), "topleft", 2)
        cols = 8
        for i, it in enumerate(pd.inventory):
            r = pygame.Rect(ix + (i % cols) * 92, y0 + 40 + (i // cols) * 92 - self.scroll, 84, 84)
            if r.bottom > area.bottom - 10 or r.top < y0 + 34:
                continue
            if ui_button(scr, g, r, "", col=(30, 34, 52), tip=self.item_tip(it)):
                self.use_item(it)
            draw_item_icon(scr, (r.centerx, r.centery - 8), 24, it)
            draw_text(scr, it['name'][:11], (r.centerx, r.bottom - 18), 11, RARITY_COLORS[it['rarity']], "midtop", 1)

    def item_tip(self, it):
        if not it:
            return None
        parts = [it['name'] + (f" +{it['plus']}" if it.get('plus') else ""), RARITY_NAMES[it['rarity']]]
        for k, nm_ in (('atk', "Атака"), ('defn', "Защита"), ('hp', "Здоровье"), ('spd', "Скорость"), ('crit', "Крит"), ('haki', "Хаки"), ('fruit', "Фрукт"), ('heal', "Лечение"), ('heavy', "Заряд. удар")):
            if it.get(k):
                v = it[k]
                parts.append(f"{nm_}: +{v * 100:.0f}%" if isinstance(v, float) and v < 1.5 else f"{nm_}: +{v}")
        parts.append(it.get('desc', ''))
        if it.get('price'):
            parts.append(f"Цена: {fmt_num(it['price'])} ฿")
        return " · ".join(p for p in parts if p)

    def use_item(self, it):
        g = self.game
        pd = g.pd
        k = it.get('kind')
        if k in ('sword', 'gun', 'fist', 'clima'):
            old = pd.equip.get('weapon')
            pd.inventory.remove(it)
            if old:
                pd.inventory.append(old)
            pd.equip['weapon'] = it
            if k == 'sword' and not any(STYLES[s].get('weapon') == 'sword' for s in pd.styles):
                pd.styles['sword1'] = pd.styles.get('sword1', 0.0)
                g.toast("Открыт стиль: Иттору (Один Меч)")
            if k == 'clima':
                pd.styles['clima'] = pd.styles.get('clima', 0.0)
            if not pd.style_usable(pd.style):
                pd.style = 'brawler'
        elif k == 'outfit':
            old = pd.equip.get('outfit')
            pd.inventory.remove(it)
            if old:
                pd.inventory.append(old)
            pd.equip['outfit'] = it
        elif k in ('acc', 'dial'):
            slot = 'acc1' if not pd.equip.get('acc1') else ('acc2' if not pd.equip.get('acc2') else 'acc1')
            old = pd.equip.get(slot)
            pd.inventory.remove(it)
            if old:
                pd.inventory.append(old)
            pd.equip[slot] = it
        elif k == 'food':
            g.toast("Еду едят в бою клавишей X.")
        elif k == 'fruit':
            fid = it['fid']
            F = FRUITS[fid]
            if pd.fruit is None:
                txt = f"Съесть {F['name']}? ({F['type']}). Ты навсегда потеряешь способность плавать."
            elif pd.fruit == 'yami' and pd.fruit2 is None:
                txt = f"Тьма поглотит силу {F['name']}... Ями Ями позволяет взять второй фрукт. Съесть?"
            else:
                txt = f"У тебя уже есть сила фрукта. Второй фрукт разорвёт твоё тело! Ты точно хочешь съесть {F['name']}?"
            def yes(it=it, fid=fid):
                res = pd.eat_fruit(fid)
                pd.inventory.remove(it)
                if res == 'death':
                    pd.level = max(1, pd.level - 5)
                    g.message("Тело разрывает на части!", [f"Ты чудом выжил, но потерял 5 уровней. Сила {FRUITS[fid]['name']} утрачена."], col=(220, 60, 60))
                elif res == 'second':
                    g.message("Тьма поглотила второй фрукт!", [f"Ты владеешь силой двух фруктов: {FRUITS[pd.fruit]['name']} и {FRUITS[fid]['name']}!"])
                else:
                    F2 = FRUITS[fid]
                    lines = [F2['desc'], f"Тип: {F2['type']}", "Новые приёмы открываются с ростом мастерства фрукта.", "Внимание: в глубокой воде ты тонешь!"]
                    if F2.get('logia'):
                        lines.append("Логия: обычные атаки почти не ранят тебя. Хаки и стихии-противовесы — опасны.")
                    g.message("Сила фрукта обретена!", lines, col=(220, 140, 255))
                pd.fix_loadout()
                g.apply_player_changes()
            g.confirm(txt, yes)
        elif k == 'key':
            if it['id'] == 'eternal_pose':
                pd.flags.add('eternal_pose')
                g.toast("Этернал Поуз активирован: быстрый переход по карте мира (M).")

    # --------- команда ---------
    def tab_crew(self, scr, area):
        g = self.game
        pd = g.pd
        x0, y0 = area.x + 20, area.y + 20
        draw_text(scr, f"Команда корабля ({len(pd.crew)}/8)", (x0, y0), 22, (255, 230, 150), "topleft", 2)
        for i, c in enumerate(pd.crew):
            r = pygame.Rect(x0, y0 + 40 + i * 64, 520, 58)
            panel(scr, r, (30, 34, 52), 230, (120, 110, 90), 8)
            s = pygame.Surface((56, 56), pygame.SRCALPHA)
            draw_portrait(s, (0, 0, 56, 56), c['app'])
            scr.blit(s, (r.x + 4, r.y + 1))
            draw_text(scr, c['name'], (r.x + 70, r.y + 6), 17, (255, 255, 255), "topleft", 2)
            role = CREW_ROLES[c['role']]
            draw_text(scr, f"{role['name']} · ур. {c['lvl']} — {role['desc']}", (r.x + 70, r.y + 30), 13, (190, 210, 230), "topleft", 1)
            if ui_button(scr, g, (r.right - 90, r.y + 12, 80, 32), "Уволить", size=13, col=(100, 50, 50)):
                pd.crew.remove(c)
                break
        if any(c['role'] == 'cook' for c in pd.crew):
            nf = pd.mats.get('fish', 0)
            if ui_button(scr, g, (x0, area.bottom - 60, 340, 44), f"Кок: приготовить бэнто (3 рыбы) [рыбы: {nf}]", enabled=nf >= 3, size=15):
                pd.mats['fish'] -= 3
                pd.inventory.append(make_item('bento'))
                g.toast("Кок приготовил бэнто!")
        cx = area.x + 580
        draw_text(scr, "Спутники (в бою максимум 2):", (cx, y0), 22, (255, 230, 150), "topleft", 2)
        for i, cid in enumerate(pd.companions):
            C = COMPANIONS[cid]
            r = pygame.Rect(cx, y0 + 40 + i * 64, 560, 58)
            act = cid in pd.active_comp
            if ui_button(scr, g, r, "", selected=act, col=(30, 34, 52), tip=C['desc']):
                if act:
                    pd.active_comp.remove(cid)
                elif len(pd.active_comp) < 2:
                    pd.active_comp.append(cid)
                else:
                    g.toast("В бою могут быть только 2 спутника.")
            s = pygame.Surface((56, 56), pygame.SRCALPHA)
            draw_portrait(s, (0, 0, 56, 56), C['app'])
            scr.blit(s, (r.x + 4, r.y + 1))
            draw_text(scr, C['name'] + ("  [В БОЮ]" if act else ""), (r.x + 70, r.y + 8), 17, (120, 255, 150) if act else (255, 255, 255), "topleft", 2)
            draw_text(scr, C['desc'], (r.x + 70, r.y + 32), 13, (190, 210, 230), "topleft", 1)
        if not pd.companions:
            draw_text(scr, "Пока никого. Канонные персонажи присоединяются после арок.", (cx, y0 + 44), 15, (160, 160, 180), "topleft", 1)

    # --------- корабль ---------
    def tab_ship(self, scr, area):
        g = self.game
        pd = g.pd
        s = pd.ship
        x0, y0 = area.x + 20, area.y + 20
        T = SHIP_TIERS[s['tier']]
        draw_text(scr, f"{s['name']} — {T['name']}", (x0, y0), 24, (255, 230, 150), "topleft", 2)
        surf = pygame.Surface((420, 300), pygame.SRCALPHA)
        draw_ship_sprite(surf, 210, 150, -0.3, s, self.t, 1.6, 1.0, flag=FACTIONS[pd.faction]['flag'])
        scr.blit(surf, (x0, y0 + 40))
        info = [f"Корпус: {fmt_num(s['hp'])} / {fmt_num(s['max_hp'])}", f"Скорость: {int(T['speed'] * (1 + 0.1 * s['sail_lvl']))}",
                f"Пушек на борт: {T['cannons'] + s['cannon_lvl'] // 2}", f"Улучшения: корпус {s['hull_lvl']}/5, паруса {s['sail_lvl']}/5, пушки {s['cannon_lvl']}/6",
                f"Coup de Burst: {'есть' if s.get('coup') else 'нет'}   Гаон-пушка: {'есть' if s.get('gaon') else 'нет'}",
                f"Корпус из Кайросеки: {'есть (Морские Короли не чуют)' if s.get('kairo') else 'нет'}", f"Кола: {s['cola']}"]
        for i, t_ in enumerate(info):
            draw_text(scr, t_, (x0 + 460, y0 + 50 + i * 30), 17, (230, 230, 240), "topleft", 2)
        draw_text(scr, "Улучшения — у корабелов (Вотер Севен, Сабаоди, Штаб Дозора и др.)", (x0 + 460, y0 + 270), 15, (170, 190, 210), "topleft", 1)
        draw_text(scr, "Внешний вид:", (x0, y0 + 360), 18, (255, 230, 150), "topleft", 2)
        if ui_button(scr, g, (x0, y0 + 390, 200, 40), "Носовая фигура", size=15):
            figs = ['lion', 'sheep', 'shark', 'dragon', 'seagull']
            s['figure'] = figs[(figs.index(s.get('figure', 'lion')) + 1) % len(figs)]
        if ui_button(scr, g, (x0 + 210, y0 + 390, 200, 40), "Цвет парусов", size=15):
            cols = [[240, 240, 235], [40, 40, 45], [200, 50, 50], [60, 90, 170], [240, 200, 60], [90, 160, 90], [230, 140, 190]]
            cur = list(s.get('sail_color', cols[0]))
            idx = cols.index(cur) if cur in cols else -1
            s['sail_color'] = cols[(idx + 1) % len(cols)]
        if ui_button(scr, g, (x0 + 420, y0 + 390, 200, 40), "Цвет корпуса", size=15):
            cols = [list(T['color']), [120, 80, 50], [210, 160, 90], [240, 240, 240], [60, 60, 70], [160, 60, 50]]
            cur = list(s.get('color', cols[0]))
            idx = cols.index(cur) if cur in cols else -1
            s['color'] = cols[(idx + 1) % len(cols)]

    # --------- журнал ---------
    def tab_log(self, scr, area):
        g = self.game
        pd = g.pd
        x0, y0 = area.x + 20, area.y + 16
        draw_text(scr, "Путь по морям", (x0, y0), 22, (255, 230, 150), "topleft", 2)
        for i, iid in enumerate(ISLAND_ORDER + SIDE_ISLANDS):
            isl = ISLANDS[iid]
            st = pd.island_state(iid)
            col_ = i // 18
            row = i % 18
            done = st['done']
            c = (130, 230, 130) if done else ((240, 220, 140) if st['visited'] else (150, 150, 160))
            mark = "✔" if done else ("•" if st['visited'] else "·")
            draw_text(scr, f"{mark} {isl['name'][:30]} [{isl['lvl']}]", (x0 + col_ * 360, y0 + 34 + row * 24), 14, c, "topleft", 1)
        sx = area.x + 760
        stats = [f"Время в игре: {int(pd.playtime // 3600)} ч {int(pd.playtime % 3600 // 60)} мин", f"Побеждено врагов: {fmt_num(pd.kills)}",
                 f"Разрушено построек: {fmt_num(pd.destroyed)}", f"Повержено боссов: {len(pd.bosses_beaten)}", f"Ласт-понеглифы: {pd.poneglyphs} / 4"]
        draw_text(scr, "Статистика", (sx, y0 + 470), 18, (255, 230, 150), "topleft", 2)
        for i, s in enumerate(stats):
            draw_text(scr, s, (sx, y0 + 498 + i * 22), 14, (220, 220, 230), "topleft", 1)
        if ui_button(scr, g, (area.right - 260, area.bottom - 120, 240, 44), "Сохранить игру", col=(50, 90, 60)):
            g.save()
            g.toast("Игра сохранена.")
        if ui_button(scr, g, (area.right - 260, area.bottom - 66, 240, 44), "В главное меню", col=(100, 50, 50)):
            def yes():
                g.save()
                self.done = True
                g.to_title()
            g.confirm("Сохранить и выйти в главное меню?", yes)

    # --------- настройки ---------
    def tab_settings(self, scr, area):
        g = self.game
        a = g.audio
        x0, y0 = area.x + 40, area.y + 40
        draw_text(scr, f"Громкость музыки: {int(a.music_vol * 100)}%", (x0, y0), 20, (255, 255, 255), "topleft", 2)
        if ui_button(scr, g, (x0 + 340, y0 - 4, 44, 36), "−"):
            a.set_music_volume(a.music_vol - 0.1)
        if ui_button(scr, g, (x0 + 390, y0 - 4, 44, 36), "+"):
            a.set_music_volume(a.music_vol + 0.1)
        draw_text(scr, f"Громкость эффектов: {int(a.sfx_vol * 100)}%", (x0, y0 + 60), 20, (255, 255, 255), "topleft", 2)
        if ui_button(scr, g, (x0 + 340, y0 + 56, 44, 36), "−"):
            a.sfx_vol = clamp(a.sfx_vol - 0.1, 0, 1)
        if ui_button(scr, g, (x0 + 390, y0 + 56, 44, 36), "+"):
            a.sfx_vol = clamp(a.sfx_vol + 0.1, 0, 1)
        draw_text(scr, f"Частицы: {int(QUALITY['particles'] * 100)}%", (x0, y0 + 120), 20, (255, 255, 255), "topleft", 2)
        if ui_button(scr, g, (x0 + 340, y0 + 116, 44, 36), "−"):
            QUALITY['particles'] = clamp(QUALITY['particles'] - 0.25, 0.25, 1.0)
        if ui_button(scr, g, (x0 + 390, y0 + 116, 44, 36), "+"):
            QUALITY['particles'] = clamp(QUALITY['particles'] + 0.25, 0.25, 1.0)
        if ui_button(scr, g, (x0, y0 + 180, 300, 44), "Полный экран (F11)"):
            g.toggle_fullscreen()
        help_lines = ["ОСТРОВ: WASD — ход, мышь — прицел, ЛКМ — комбо, ПКМ (держать) — заряженный удар",
                      "Space — рывок (вовремя = идеальное уклонение), Shift — блок (нажать вовремя = парирование)",
                      "1-4 — приёмы, R — ультимейт (Дух ≥ 1 сегмент; во время ульты босса — СТОЛКНОВЕНИЕ!)",
                      "F — пробуждение (2 сегмента Духа), Q/C/Z — Хаки Вооружения / Наблюдения / Королевское",
                      "X — съесть еду, E — взаимодействие, Tab — меню",
                      "МОРЕ: W/S — паруса, A/D — руль, ЛКМ — залп по стороне мыши, ПКМ — Гаон, Space — Coup de Burst",
                      "Shift — якорь, F — рыбалка, M — карта мира, E — высадка / абордаж"]
        for i, ln in enumerate(help_lines):
            draw_text(scr, ln, (x0, y0 + 260 + i * 28), 16, (210, 220, 240), "topleft", 1)

# ------------------------------------------------------------------
#  СЕРВИСЫ: МАГАЗИН, КУЗНИЦА, КОРАБЕЛ, ТАВЕРНА, НАСТАВНИК
# ------------------------------------------------------------------
class ServiceOverlay(Overlay):
    def __init__(self, game, role, scene):
        self.game = game
        self.role = role
        self.scene = scene
        self.isl = scene.isl
        self.mode = 'buy'
        self.t = 0
        self.scroll = 0
        if role == 'tavern':
            self.recruits = self.make_recruits()

    def make_recruits(self):
        pd = self.game.pd
        rng = random.Random(stable_seed(self.scene.iid) + int(pd.playtime // 600))
        lvl = max(1, self.isl['lvl'] - 2)
        return [make_crew_member(rng, lvl + rng.randint(0, 3)) for _ in range(3)]

    def update(self, dt):
        self.t += dt
        g = self.game
        if pygame.K_ESCAPE in g.kp or pygame.K_e in g.kp and self.t > 0.3:
            self.done = True
            g.apply_player_changes()
        if g.wheel:
            self.scroll = max(0, self.scroll - g.wheel * 40)

    def draw(self, scr):
        g = self.game
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((5, 8, 20, 190))
        scr.blit(dim, (0, 0))
        area = pygame.Rect(80, 50, W - 160, H - 100)
        panel(scr, area, (18, 20, 32), 245, (230, 200, 130), 14, 3)
        title = {'shop': "Торговец", 'smith': "Кузница", 'shipwright': "Верфь", 'tavern': "Таверна"}.get(self.role, "")
        draw_text(scr, title + " — " + self.isl['name'], (area.x + 24, area.y + 16), 26, (255, 230, 150), "topleft", 2)
        draw_text(scr, f"฿ {fmt_num(g.pd.beli)}", (area.right - 24, area.y + 18), 24, (255, 220, 90), "topright", 2)
        if ui_button(scr, g, (area.right - 140, area.bottom - 56, 120, 42), "Выйти", col=(110, 50, 50)):
            self.done = True
            g.apply_player_changes()
        getattr(self, 'draw_' + self.role)(scr, area)
        if g.tooltip:
            tip = g.tooltip
            lines = wrap_text(get_font(15), tip, 360)
            mx, my = g.mouse
            r = pygame.Rect(mx + 16, my + 10, 380, len(lines) * 20 + 14)
            if r.right > W:
                r.x = mx - 396
            if r.bottom > H:
                r.y = H - r.h - 4
            panel(scr, r, (10, 10, 18), 245, (230, 200, 130), 8)
            for i, ln in enumerate(lines):
                draw_text(scr, ln, (r.x + 8, r.y + 7 + i * 20), 15, (240, 240, 240), "topleft", 1)

    def price_mult(self):
        pd = self.game.pd
        m = 1.0
        if pd.faction == 'marine' and self.isl.get('hub') == 'marine':
            m *= 0.7
        if pd.trait == 'lucky':
            m *= 0.9
        return m

    def draw_shop(self, scr, area):
        g = self.game
        pd = g.pd
        x0, y0 = area.x + 24, area.y + 64
        if ui_button(scr, g, (x0, y0, 140, 36), "Купить", selected=self.mode == 'buy', size=16):
            self.mode = 'buy'
        if ui_button(scr, g, (x0 + 150, y0, 140, 36), "Продать", selected=self.mode == 'sell', size=16):
            self.mode = 'sell'
        y = y0 + 54
        pm = self.price_mult()
        if self.mode == 'buy':
            items = [make_item(i) for i in self.isl['shop']] + [fruit_item(f) for f in self.isl['fruit_shop']]
            if 'auction' in self.isl['flags']:
                draw_text(scr, "Чёрный рынок Сабаоди: дьявольские фрукты на аукционе!", (x0 + 320, y0 + 6), 16, (255, 180, 255), "topleft", 2)
            for i, it in enumerate(items):
                r = pygame.Rect(x0 + (i % 2) * 520, y + (i // 2) * 64 - self.scroll, 510, 58)
                if r.top < y - 4 or r.bottom > area.bottom - 70:
                    continue
                price = int(it['price'] * pm * (1.0 if it['kind'] != 'fruit' else 1.0))
                tip = PauseMenu.item_tip(None, it)
                ok = pd.beli >= price and price > 0
                if ui_button(scr, g, r, "", enabled=ok, col=(30, 34, 52), tip=tip):
                    pd.beli -= price
                    if it['kind'] == 'mat':
                        pd.add_item(it)
                    elif it['kind'] == 'key' and it['id'] == 'eternal_pose':
                        pd.inventory.append(it)
                        pd.flags.add('eternal_pose')
                    else:
                        pd.inventory.append(make_item(it['id']) if not it['id'].startswith('fruit_') else fruit_item(it['fid']))
                    g.audio.play('coin', 0.8)
                    g.toast("Куплено: " + it['name'])
                draw_item_icon(scr, (r.x + 30, r.centery), 22, it)
                draw_text(scr, it['name'], (r.x + 62, r.y + 8), 17, RARITY_COLORS[it['rarity']], "topleft", 2)
                draw_text(scr, f"฿ {fmt_num(price)}", (r.right - 12, r.y + 8), 16, (255, 220, 90) if ok else (150, 120, 90), "topright", 2)
                draw_text(scr, it.get('desc', '')[:60], (r.x + 62, r.y + 32), 12, (180, 190, 210), "topleft", 1)
        else:
            sellable = [it for it in pd.inventory]
            mats = [(k, v) for k, v in pd.mats.items() if v > 0]
            for i, it in enumerate(sellable):
                r = pygame.Rect(x0 + (i % 2) * 520, y + (i // 2) * 64 - self.scroll, 510, 58)
                if r.top < y - 4 or r.bottom > area.bottom - 70:
                    continue
                price = int(max(50, it.get('price', 100) or (500 * (it['rarity'] + 1) ** 3)) * 0.4)
                if ui_button(scr, g, r, "", col=(30, 34, 52), tip=PauseMenu.item_tip(None, it)):
                    pd.inventory.remove(it)
                    pd.beli += price
                    g.audio.play('coin', 0.8)
                    break
                draw_item_icon(scr, (r.x + 30, r.centery), 22, it)
                draw_text(scr, it['name'], (r.x + 62, r.y + 8), 17, RARITY_COLORS[it['rarity']], "topleft", 2)
                draw_text(scr, f"+฿ {fmt_num(price)}", (r.right - 12, r.y + 8), 16, (120, 255, 140), "topright", 2)
            my = y + (len(sellable) + 1) // 2 * 64 + 10 - self.scroll
            for i, (k, v) in enumerate(mats):
                r = pygame.Rect(x0 + (i % 4) * 258, my + (i // 4) * 44, 250, 38)
                if r.top < y - 4 or r.bottom > area.bottom - 70:
                    continue
                price = int(ITEMS[k]['price'] * 0.4)
                if ui_button(scr, g, r, f"{ITEMS[k]['name']} ×{v}  (+{fmt_num(price)})", size=13, col=(30, 34, 52)):
                    pd.mats[k] -= 1
                    pd.beli += price

    def draw_smith(self, scr, area):
        g = self.game
        pd = g.pd
        x0, y0 = area.x + 24, area.y + 70
        draw_text(scr, "Улучшение экипировки (до +10):", (x0, y0), 19, (255, 230, 150), "topleft", 2)
        for i, slot in enumerate(['weapon', 'outfit', 'acc1', 'acc2']):
            it = pd.equip.get(slot)
            r = pygame.Rect(x0, y0 + 34 + i * 70, 560, 62)
            if not it:
                panel(scr, r, (25, 28, 40), 200, (80, 80, 90), 8)
                draw_text(scr, "— пусто —", (r.x + 20, r.y + 20), 15, (120, 120, 130), "topleft", 1)
                continue
            plus = it.get('plus', 0)
            cost = int((plus + 1) ** 2 * 1500 * (it['rarity'] + 1))
            mat = 'iron' if plus < 4 else ('steel' if plus < 7 else ('tamahagane' if it['kind'] == 'sword' else 'kairoseki'))
            nmat = plus + 1
            ok = plus < 10 and pd.beli >= cost and pd.mats.get(mat, 0) >= nmat
            tip = f"Стоимость: {fmt_num(cost)} ฿ + {ITEMS[mat]['name']} ×{nmat}. Каждый + даёт +12% к характеристикам."
            if ui_button(scr, g, r, "", enabled=ok, col=(30, 34, 52), tip=tip):
                pd.beli -= cost
                pd.mats[mat] -= nmat
                it['plus'] = plus + 1
                g.audio.play('block', 1.0)
                g.toast(f"{it['name']} улучшен до +{plus + 1}!")
            draw_item_icon(scr, (r.x + 30, r.centery), 22, it)
            draw_text(scr, f"{it['name']} +{plus}", (r.x + 62, r.y + 8), 17, RARITY_COLORS[it['rarity']], "topleft", 2)
            draw_text(scr, f"→ +{plus + 1}: {fmt_num(cost)} ฿, {ITEMS[mat]['name']} ×{nmat} (есть {pd.mats.get(mat, 0)})" if plus < 10 else "Максимум!", (r.x + 62, r.y + 34), 13, (190, 200, 220), "topleft", 1)
        cx = area.x + 620
        draw_text(scr, "Ковка:", (cx, y0), 19, (255, 230, 150), "topleft", 2)
        recipes = [('scale_armor', {'sea_king_scale': 6, 'steel': 4}, 30000), ('wapometal_armor', {'wapometal': 5, 'steel': 5}, 60000),
                   ('kairoseki_knuckles', {'kairoseki': 4, 'steel': 3}, 50000), ('impact_dial', {'dial_shell': 3}, 10000),
                   ('reject_dial_acc', {'dial_shell': 8, 'gold': 4}, 200000), ('named', {'tamahagane': 5, 'kairoseki': 2, 'gold': 3}, 500000)]
        for i, (iid, need, cost) in enumerate(recipes):
            r = pygame.Rect(cx, y0 + 34 + i * 66, 560, 58)
            ok = pd.beli >= cost and all(pd.mats.get(k, 0) >= v for k, v in need.items())
            name = ITEMS[iid]['name'] if iid != 'named' else f"Именной клинок «{pd.name}»"
            needtxt = ", ".join(f"{ITEMS[k]['name']} ×{v}" for k, v in need.items())
            if ui_button(scr, g, r, "", enabled=ok, col=(30, 34, 52), tip=needtxt):
                pd.beli -= cost
                for k, v in need.items():
                    pd.mats[k] -= v
                if iid == 'named':
                    it = dict(id='named_blade', name=f"Клинок «{pd.name}»", kind='sword', rarity=4, atk=60, crit=0.08, haki=0.1, price=0, plus=0,
                              desc="Выкован специально для тебя. Растёт вместе с тобой.")
                else:
                    it = make_item(iid)
                pd.inventory.append(it)
                g.audio.play('levelup', 0.8)
                g.toast("Выковано: " + it['name'])
            draw_text(scr, name, (r.x + 14, r.y + 8), 17, (255, 230, 200) if ok else (150, 150, 160), "topleft", 2)
            draw_text(scr, f"{needtxt} + {fmt_num(cost)} ฿", (r.x + 14, r.y + 32), 12, (190, 200, 220), "topleft", 1)

    def draw_shipwright(self, scr, area):
        g = self.game
        pd = g.pd
        s = pd.ship
        tier = self.isl.get('shipwright', 1)
        x0, y0 = area.x + 24, area.y + 70
        disc = 0.8 if any(c['role'] == 'shipwright' for c in pd.crew) else 1.0
        draw_text(scr, f"Верфь (уровень мастерства {tier})", (x0, y0), 19, (255, 230, 150), "topleft", 2)
        opts = []
        cur_i = SHIP_ORDER.index(s['tier'])
        for ti, tid in enumerate(SHIP_ORDER):
            if ti <= cur_i or ti > tier + 1:
                continue
            T = SHIP_TIERS[tid]
            need = {}
            if tid == 'galleon':
                need = {'adam_wood': 3}
            if tid == 'warship':
                need = {'adam_wood': 4, 'kairoseki': 4} if pd.faction != 'marine' else {'steel': 10}
            opts.append(("Новый корабль: " + T['name'], int(T['cost'] * disc), need, ('tier', tid)))
        for key, nm_, mx, base in (('hull_lvl', "Корпус", 5, 15000), ('sail_lvl', "Паруса", 5, 12000), ('cannon_lvl', "Пушки", 6, 14000)):
            lv = s[key]
            if lv < mx and lv < tier * 2:
                opts.append((f"{nm_}: ур. {lv} → {lv + 1}", int(base * (lv + 1) ** 1.8 * disc), {'wood': 2 + lv, 'iron': 1 + lv}, ('up', key)))
        if tier >= 3 and not s.get('coup'):
            opts.append(("Установить Coup de Burst", int(400000 * disc), {'adam_wood': 1}, ('coup', None)))
        if tier >= 3 and not s.get('gaon') and SHIP_ORDER.index(s['tier']) >= 2:
            opts.append(("Установить Гаон-пушку", int(900000 * disc), {'steel': 6}, ('gaon', None)))
        if tier >= 2 and not s.get('kairo'):
            opts.append(("Корпус с Кайросеки (Морские Короли не нападают в Затишье)", int(600000 * disc), {'kairoseki': 8}, ('kairo', None)))
        rep = int((s['max_hp'] - s['hp']) * 4 * disc)
        opts.append((f"Ремонт корпуса", rep, {}, ('repair', None)))
        opts.append(("Купить колу ×10", 2000, {}, ('cola', None)))
        for i, (nm_, cost, need, act) in enumerate(opts):
            r = pygame.Rect(x0 + (i % 2) * 520, y0 + 36 + (i // 2) * 66, 510, 58)
            ok = pd.beli >= cost and all(pd.mats.get(k, 0) >= v for k, v in need.items())
            if act[0] == 'repair' and rep <= 0:
                ok = False
            needtxt = ", ".join(f"{ITEMS[k]['name']} ×{v}" for k, v in need.items())
            if ui_button(scr, g, r, "", enabled=ok, col=(30, 34, 52), tip=needtxt or None):
                pd.beli -= cost
                for k, v in need.items():
                    pd.mats[k] -= v
                a, b = act
                if a == 'tier':
                    old = dict(s)
                    ns = new_ship(b)
                    for k in ('hull_lvl', 'sail_lvl', 'cannon_lvl', 'coup', 'gaon', 'kairo', 'cola', 'sail_color', 'figure', 'flag', 'name'):
                        ns[k] = old.get(k, ns[k])
                    if old['name'] == SHIP_TIERS[old['tier']]['name']:
                        ns['name'] = SHIP_TIERS[b]['name']
                    pd.ship = ns
                    g.toast("Новый корабль: " + SHIP_TIERS[b]['name'] + "!")
                elif a == 'up':
                    s[b] += 1
                elif a in ('coup', 'gaon', 'kairo'):
                    s[a] = True
                elif a == 'repair':
                    s['hp'] = s['max_hp']
                elif a == 'cola':
                    s['cola'] += 10
                T = SHIP_TIERS[pd.ship['tier']]
                pd.ship['max_hp'] = int(T['hp'] * (1 + 0.3 * pd.ship['hull_lvl']))
                g.audio.play('block', 0.8)
                s = pd.ship
            draw_text(scr, nm_, (r.x + 14, r.y + 8), 16, (255, 240, 210) if ok else (140, 140, 150), "topleft", 2)
            draw_text(scr, f"฿ {fmt_num(cost)}" + (f"  + {needtxt}" if needtxt else ""), (r.x + 14, r.y + 32), 13, (200, 200, 210), "topleft", 1)

    def draw_tavern(self, scr, area):
        g = self.game
        pd = g.pd
        x0, y0 = area.x + 24, area.y + 70
        draw_text(scr, "Желающие присоединиться к команде:", (x0, y0), 19, (255, 230, 150), "topleft", 2)
        for i, c in enumerate(self.recruits):
            r = pygame.Rect(x0 + i * 350, y0 + 40, 330, 300)
            panel(scr, r, (30, 34, 52), 230, (150, 140, 110), 10)
            s = pygame.Surface((160, 160), pygame.SRCALPHA)
            draw_portrait(s, (0, 0, 160, 160), c['app'])
            scr.blit(s, (r.centerx - 80, r.y + 10))
            draw_text(scr, c['name'], (r.centerx, r.y + 176), 17, (255, 255, 255), "midtop", 2)
            role = CREW_ROLES[c['role']]
            draw_text(scr, f"{role['name']}, ур. {c['lvl']}", (r.centerx, r.y + 200), 15, (255, 220, 150), "midtop", 1)
            for k_, ln in enumerate(wrap_text(get_font(13), role['desc'], 300)[:2]):
                draw_text(scr, ln, (r.centerx, r.y + 222 + k_ * 17), 13, (190, 210, 230), "midtop", 1)
            ok = pd.beli >= c['price'] and len(pd.crew) < 8 and not c.get('hired')
            if ui_button(scr, g, (r.x + 30, r.bottom - 50, r.w - 60, 40), "Нанять: ฿ " + fmt_num(c['price']) if not c.get('hired') else "В команде!", enabled=ok, size=15):
                pd.beli -= c['price']
                c['hired'] = True
                pd.crew.append(dict(name=c['name'], role=c['role'], lvl=c['lvl'], app=c['app']))
                g.toast(f"{c['name']} теперь в команде!")
        rumors = ["Говорят, в Потоке Нок-Ап у Джаи корабли улетают прямо в небо...", "Носитель фрукта тонет, как камень. Не лезь в воду, если съел фрукт!",
                  "Бочки с водой на островах — лучшее оружие против песчаной логии.", "Королевское хаки — у одного на миллион. Говорят, оно пробуждается на Сабаоди...",
                  "На Сабаоди в аукционном доме продают дьявольские фрукты. Дорого, но того стоит.", "Если вовремя нажать блок, можно парировать даже удар Адмирала!",
                  "Когда босс готовит ультимейт, ответь своим — и начнётся столкновение воль!", "Корабелы Вотер Севен ставят Coup de Burst — рывок через небо!"]
        rng = random.Random(int(self.t // 6) + stable_seed(self.scene.iid))
        draw_text(scr, "Слухи: " + rng.choice(rumors), (x0, area.bottom - 110), 16, (220, 210, 180), "topleft", 2)
        if ui_button(scr, g, (x0, area.bottom - 66, 300, 42), "Отдохнуть (полное лечение) — 500 ฿", enabled=pd.beli >= 500, size=14):
            pd.beli -= 500
            self.scene.player.hp = self.scene.player.max_hp
            self.scene.player.st = self.scene.player.max_st
            g.toast("Ты отлично отдохнул.")

class MentorOverlay(Overlay):
    def __init__(self, game, mid, scene):
        self.game = game
        self.mid = mid
        self.scene = scene
        self.t = 0

    def update(self, dt):
        self.t += dt
        if pygame.K_ESCAPE in self.game.kp:
            self.done = True

    def draw(self, scr):
        g = self.game
        pd = g.pd
        M = MENTORS[self.mid]
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((5, 8, 20, 190))
        scr.blit(dim, (0, 0))
        r = pygame.Rect(W / 2 - 480, 90, 960, H - 180)
        panel(scr, r, (22, 20, 32), 245, (230, 200, 130), 14, 3)
        pr = pygame.Rect(r.x + 24, r.y + 24, 260, 260)
        pygame.draw.rect(scr, (40, 36, 55), pr, border_radius=14)
        draw_portrait(scr, pr, M['app'], 'normal')
        draw_text(scr, M['name'], (r.x + 310, r.y + 30), 30, (255, 230, 150), "topleft", 2)
        for i, ln in enumerate(wrap_text(get_font(19), "«" + M['text'] + "»", 600)):
            draw_text(scr, ln, (r.x + 310, r.y + 80 + i * 26), 19, (240, 240, 240), "topleft", 2)
        teaches = []
        if M.get('style'):
            teaches.append("Стиль: " + STYLES[M['style']]['name'] + " — " + STYLES[M['style']]['desc'])
        if M.get('haki'):
            teaches.append("Тренировка Хаки: повышает пределы Вооружения и Наблюдения")
        if M.get('haki_ryou'):
            teaches.append("Рюо: внутреннее разрушение хаки (Вооружение до 10)")
        if self.mid == 'mihawk':
            teaches.append("+20 к мастерству всех стилей мечников")
        y = r.y + 230
        for t_ in teaches:
            for ln in wrap_text(get_font(17), "• " + t_, 600):
                draw_text(scr, ln, (r.x + 310, y), 17, (200, 230, 255), "topleft", 1)
                y += 24
        done = self.mid in pd.mentors_done
        req_lvl = M.get('lvl', 1)
        price = M.get('price', 0)
        reqs = []
        ok = True
        if pd.level < req_lvl:
            reqs.append(f"Нужен уровень {req_lvl}")
            ok = False
        if pd.beli < price:
            reqs.append(f"Нужно ฿ {fmt_num(price)}")
            ok = False
        if self.mid == 'garp' and pd.faction != 'marine' and not self.scene.ist.get('done'):
            reqs.append("Гарп учит только дозорных... или тех, кто победил в его Штабе")
            ok = False
        if self.mid == 'mihawk' and not (pd.island_state('kuraigana')['done'] or self.scene.iid == 'karai_bari' and pd.faction == 'hunter'):
            reqs.append("Сначала одолей Михоука на Курайгане")
            ok = False
        if self.mid == 'sabo_m' and pd.faction != 'revo':
            reqs.append("Только для революционеров")
            ok = False
        if self.mid == 'koala_m' and pd.faction != 'revo' and self.scene.iid != 'alabasta':
            pass
        if self.mid == 'hyogoro' and pd.haki_cap['arm'] <= 0:
            reqs.append("Нужно Хаки Вооружения")
            ok = False
        if done:
            draw_text(scr, "Обучение пройдено. Возвращайся за спаррингом ради опыта.", (r.x + 310, r.bottom - 150), 17, (130, 230, 130), "topleft", 2)
        for i, rq in enumerate(reqs):
            draw_text(scr, rq, (r.x + 310, r.bottom - 150 + i * 24), 16, (255, 150, 140), "topleft", 2)
        label = "Спарринг (тренировочный бой)" + (f" — ฿ {fmt_num(price)}" if price and not done else "")
        if ui_button(scr, g, (r.x + 310, r.bottom - 76, 400, 50), label, enabled=ok or done, col=(60, 90, 50)):
            if not done and price:
                pd.beli -= price
            self.done = True
            if self.mid == 'cp9_scroll':
                g.mentor_success(self.mid, self.scene)
            else:
                self.scene.start_spar(self.mid)
        if ui_button(scr, g, (r.right - 170, r.bottom - 76, 150, 50), "Уйти", col=(110, 50, 50)):
            self.done = True

# ==================================================================
#  ДОП. КОНТЕНТ ОСТРОВОВ: КОЛИЗЕЙ, ДОСКА РОЗЫСКА
# ==================================================================
COLO_WAVES = [
    ['gladiator', 'gladiator', 'gladiator'],
    ['gladiator', 'gladiator', 'toy_soldier', 'gladiator'],
    ['donquixote', 'gladiator', 'gladiator', 'donquixote'],
    ['boss:diamante'],
]

class IslandExtras:
    def colosseum_available(self):
        return 'colosseum' in self.isl['flags'] and self.deck is None

    def start_colosseum(self):
        if getattr(self, 'colo', None):
            return
        self.colo = dict(wave=-1, group=None)
        self.notify("КОРРИДА КОЛИЗЕЙ! Выдержи 4 волны. Приз — Мера Мера но Ми!", (255, 200, 90))
        self.game.audio.play_music('battle', fade=600)
        self.audio_play('gong', 1.0)
        self.next_colo_wave()

    def next_colo_wave(self):
        c = self.colo
        c['wave'] += 1
        if c['wave'] >= len(COLO_WAVES):
            self.finish_colosseum()
            return
        center = V(self.map.arena)
        grp = ('c', c['wave'])
        c['group'] = grp
        for i, et in enumerate(COLO_WAVES[c['wave']]):
            p = center + from_angle(i * 6.28 / max(1, len(COLO_WAVES[c['wave']])), 160)
            if et.startswith('boss:'):
                f = make_boss(self, et[5:], self.lvl + 2, p, elite_mode=True)
                f.max_hp *= 0.8
                f.hp = f.max_hp
            else:
                f = make_enemy(self, et, self.lvl, p, group=grp)
            f.group = grp
            f.ai.aggro = True
            f.colo = True
            self.fighters.append(f)
        self.notify(f"Волна {c['wave'] + 1} / {len(COLO_WAVES)}", (255, 220, 140))

    def update_colosseum(self):
        c = getattr(self, 'colo', None)
        if not c or c['group'] is None:
            return
        alive = [f for f in self.fighters if f.group == c['group'] and not f.dead]
        if not alive:
            c['group'] = None
            self.timers.append([1.2, self.next_colo_wave])

    def finish_colosseum(self):
        pd = self.pd
        self.colo = None
        self.game.audio.play_music(self.music)
        if 'colo_won' not in pd.flags:
            pd.flags.add('colo_won')
            pd.inventory.append(fruit_item('mera'))
            lines = [("Ты — чемпион Корриды Колизея!", (255, 230, 120)), ("Приз: Мера Мера но Ми — фрукт Огненного Кулака Эйса.", (255, 160, 80)),
                     "Съесть его можно в меню Снаряжение (если у тебя ещё нет фрукта)."]
        else:
            beli = 50000 * (1 + self.lvl // 10)
            pd.beli += beli
            lines = [("Снова победа в Колизее!", (255, 230, 120)), f"Приз: {fmt_num(beli)} ฿"]
        xp = 3000 * (1 + self.lvl // 10)
        if pd.add_xp(xp):
            self.on_levelup(1)
        lines.append(f"+{fmt_num(xp)} опыта")
        self.game.reward_rep(self.lvl * 300000, quiet=True)
        self.game.message("Чемпион Колизея!", lines, col=(255, 200, 90))

    # ---------------- доска розыска ----------------
    def board_available(self):
        return self.deck is None and self.pd.faction in ('hunter', 'marine') and 'no_combat' not in self.isl['flags']

    def make_contracts(self):
        pd = self.pd
        rng = random.Random(stable_seed(self.iid) + int(pd.playtime // 300))
        pool = [b for b, d in BOSSES.items() if d.get('bounty', 0) > 0 and b not in ('luffy_g5', 'luffy_g2', 'zoro_boss', 'shanks', 'blackbeard', 'whitebeard', 'big_mom', 'kaido', 'mihawk')]
        out = []
        for _ in range(3):
            bid = rng.choice(pool)
            lvl = max(1, self.lvl + rng.randint(-1, 3))
            reward = int(min(max(BOSSES[bid]['bounty'] * 0.003, 3000 * lvl), 20000 * lvl))
            out.append(dict(bid=bid, lvl=lvl, reward=reward))
        return out

    def accept_contract(self, c):
        if getattr(self, 'contract', None):
            self.notify("Сначала выполни текущий заказ!", (255, 200, 160))
            return
        camps = self.map.camps or [self.map.town_c]
        p = random.choice(camps)
        f = make_boss(self, c['bid'], c['lvl'], p, elite_mode=True)
        f.max_hp *= 0.75
        f.hp = f.max_hp
        f.contract = c
        f.group = ('k', 0)
        self.fighters.append(f)
        for _ in range(2):
            et = random.choice(self.enemy_pool())
            self.fighters.append(make_enemy(self, et, c['lvl'], p + V(random.uniform(-80, 80), random.uniform(-60, 60)), group=('k', 0)))
        self.contract = f
        self.notify(f"Заказ принят: {BOSSES[c['bid']]['name']} (ур. {c['lvl']}). Цель отмечена на карте.", (255, 220, 120))

    def check_contract(self):
        f = getattr(self, 'contract', None)
        if f is None or not f.dead:
            return
        c = f.contract
        self.contract = None
        pd = self.pd
        pd.beli += c['reward']
        if pd.faction == 'marine':
            pd.merit += 20 + c['lvl'] * 3
            txt = f"Преступник пойман! +{fmt_num(c['reward'])} ฿, +{20 + c['lvl'] * 3} заслуг"
        else:
            pd.merit += 15 + c['lvl'] * 2
            txt = f"Награда получена: +{fmt_num(c['reward'])} ฿"
        self.notify(txt, (120, 255, 150))
        self.audio_play('coin', 1.0)

for _k, _v in list(IslandExtras.__dict__.items()):
    if callable(_v) and not _k.startswith('__'):
        setattr(IslandScene, _k, _v)

_orig_spawn_npcs = IslandScene._spawn_npcs

def _spawn_npcs_ext(self):
    _orig_spawn_npcs(self)
    if self.deck is not None:
        return
    spots = [p for p in self.map.npc_spots if all(dist(p, n.pos) > 50 for n in self.npcs)]
    if self.colosseum_available() and spots:
        app = default_app(hair='slick', hair_col=(240, 210, 110), outfit='suit', top=(180, 40, 40), hat='top_hat', hat_col=(30, 30, 30), features=('mustache',))
        self.npcs.append(NPC(self, spots.pop(), app, 'colosseum', "Ведущий Корриды"))
    if self.board_available() and spots:
        app = default_app(outfit='marine' if self.pd.faction == 'marine' else 'coat', top=(240, 240, 240) if self.pd.faction == 'marine' else (120, 90, 60),
                          hat='marine_cap' if self.pd.faction == 'marine' else 'wide', hat_col=(90, 60, 40))
        self.npcs.append(NPC(self, spots.pop(), app, 'board', "Доска розыска"))

IslandScene._spawn_npcs = _spawn_npcs_ext

_orig_update = IslandScene.update

def _update_ext(self, dt):
    _orig_update(self, dt)
    if getattr(self, 'colo', None):
        self.update_colosseum()
    if getattr(self, 'contract', None) is not None:
        self.check_contract()

IslandScene.update = _update_ext

_orig_obj_target = IslandScene.objective_target

def _obj_target_ext(self):
    c = getattr(self, 'contract', None)
    if c is not None and not c.dead:
        return c.pos
    return _orig_obj_target(self)

IslandScene.objective_target = _obj_target_ext

_orig_interact = IslandScene.interact

def _interact_ext(self):
    bi = self.best_interaction()
    if bi and bi[0] == 'npc' and bi[1].role in ('colosseum', 'board'):
        n = bi[1]
        g = self.game
        if n.role == 'colosseum':
            if getattr(self, 'colo', None):
                return
            g.confirm("Выйти на арену Корриды Колизея? 4 волны бойцов, финал — Диаманте. Главный приз — Мера Мера но Ми!", self.start_colosseum)
        else:
            g.push(BoardOverlay(g, self))
        return
    _orig_interact(self)

IslandScene.interact = _interact_ext
ROLE_NAMES['colosseum'] = "Колизей Корриды"
ROLE_NAMES['board'] = "Доска розыска"

class BoardOverlay(Overlay):
    def __init__(self, game, scene):
        self.game = game
        self.scene = scene
        self.contracts = scene.make_contracts()

    def update(self, dt):
        if pygame.K_ESCAPE in self.game.kp:
            self.done = True

    def draw(self, scr):
        g = self.game
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((5, 8, 20, 190))
        scr.blit(dim, (0, 0))
        r = pygame.Rect(90, 70, W - 180, H - 140)
        panel(scr, r, (40, 30, 22), 245, (230, 200, 130), 14, 3)
        draw_text(scr, "ДОСКА РОЗЫСКА", (r.centerx, r.y + 14), 34, (255, 230, 150), "midtop", 3)
        for i, c in enumerate(self.contracts):
            B_ = BOSSES[c['bid']]
            x = r.x + 30 + i * 360
            poster = make_wanted_poster(B_['name'], max(B_['bounty'], c['reward'] * 100), B_['app'], B_['title'])
            ps = pygame.transform.smoothscale(poster, (240, 336))
            scr.blit(ps, (x + 30, r.y + 70))
            draw_text(scr, f"Ур. {c['lvl']}  ·  Награда охотнику: ฿ {fmt_num(c['reward'])}", (x + 150, r.y + 416), 14, (255, 230, 180), "midtop", 2)
            if ui_button(scr, g, (x + 40, r.y + 444, 220, 42), "Взять заказ", col=(90, 60, 30)):
                self.scene.accept_contract(c)
                self.done = True
        if ui_button(scr, g, (r.right - 160, r.bottom - 60, 140, 44), "Закрыть", col=(110, 50, 50)):
            self.done = True

# ==================================================================
#  СЦЕНЫ МЕНЮ, СОЗДАНИЕ ПЕРСОНАЖА, ИГРА
# ==================================================================
def draw_sea_backdrop(scr, t, night=0.0):
    if not hasattr(draw_sea_backdrop, 'sky'):
        draw_sea_backdrop.sky = vgradient(W, int(H * 0.55), (255, 190, 120), (120, 180, 230))
        draw_sea_backdrop.sea = vgradient(W, int(H * 0.45) + 2, (40, 120, 190), (15, 50, 110))
    scr.blit(draw_sea_backdrop.sky, (0, 0))
    hy = int(H * 0.55)
    draw_glow(scr, (W * 0.72, hy - 40), 160, (255, 220, 160), 0.9)
    pygame.draw.circle(scr, (255, 240, 200), (int(W * 0.72), hy - 40), 56)
    for i in range(6):
        cx = (i * 260 + t * 12) % (W + 300) - 150
        cy = 80 + (i * 37) % 140
        for k in range(4):
            pygame.draw.ellipse(scr, (255, 245, 240), (cx + k * 30, cy - (k % 2) * 14, 90, 40))
    scr.blit(draw_sea_backdrop.sea, (0, hy))
    for i in range(40):
        y = hy + 6 + (i * 13) % int(H * 0.45)
        x = (i * 97 + t * (20 + i % 5 * 10)) % (W + 100) - 50
        pygame.draw.line(scr, (180, 220, 255), (x, y), (x + 30 + i % 4 * 10, y), 2)
    pygame.draw.line(scr, (255, 230, 190), (W * 0.62, hy + 4), (W * 0.82, hy + 4), 3)
    sx = (t * 25) % (W + 400) - 200
    dummy = dict(tier='galleon', color=[200, 150, 80], sail_color=[245, 245, 240], cannons=4, figure='lion')
    draw_ship_sprite(scr, sx, hy + 70, -0.15, dummy, t, 1.4, 1.0)
    for i in range(5):
        gx = (i * 180 + t * 50) % (W + 200) - 100
        gy = 160 + math.sin(t * 2 + i) * 20 + i * 15
        w_ = 10 + math.sin(t * 8 + i) * 4
        pygame.draw.lines(scr, (40, 40, 50), False, [(gx - 14, gy - w_ * 0.5), (gx, gy), (gx + 14, gy - w_ * 0.5)], 2)

class LoadingScene:
    kind = 'loading'
    def __init__(self, game):
        self.game = game
        self.t = 0
        self.tips = ["Совет: нажми Shift ровно перед ударом врага — парирование оглушит его.",
                     "Совет: когда босс готовит ультимейт, нажми R — начнётся столкновение воль!",
                     "Совет: логию не ранят обычные удары. Ищи хаки, воду или стихию-противовес.",
                     "Совет: фруктовики тонут. Сбей врага-фруктовика в море!",
                     "Совет: мощные атаки разрушают дома. Пиратам это поднимает награду, дозорным — портит репутацию.",
                     "Совет: с Coup de Burst корабль перелетает через опасности.",
                     "Совет: Хаки Наблюдения (C) позволяет уклоняться от атак. Предвидение — контратаковать."]
        self.tip = random.choice(self.tips)

    def update(self, dt):
        self.t += dt
        a = self.game.audio
        if int(self.t / 5) != int((self.t - dt) / 5):
            self.tip = random.choice(self.tips)
        if a.music_ready or not a.ok:
            a.finalize()
            self.game.set_scene(TitleScene(self.game))

    def draw(self, scr):
        draw_sea_backdrop(scr, self.t)
        draw_title_logo(scr, self.t, H * 0.24)
        a = self.game.audio
        r = pygame.Rect(W / 2 - 300, H * 0.72, 600, 22)
        bar(scr, r, a.progress, (255, 200, 80))
        draw_text(scr, a.status, (W / 2, r.y - 34), 20, (255, 255, 255), "center", 3)
        draw_text(scr, "Первый запуск: оркестр синтезирует музыку (~30 сек). Потом — мгновенно.", (W / 2, r.bottom + 18), 15, (230, 230, 240), "center", 2)
        draw_text(scr, self.tip, (W / 2, H - 40), 16, (255, 240, 200), "center", 2)

def draw_title_logo(scr, t, y):
    wob = math.sin(t * 2) * 3
    for dx, dy in ((6, 6), (0, 0)):
        col = (60, 20, 10) if dx else (255, 215, 60)
        draw_text(scr, "ONE PIECE", (W / 2 + dx, y + dy + wob), 110, col, "center", 7 if not dx else 0, (90, 30, 10))
    draw_text(scr, "ВЕЛИКИЙ ПУТЬ", (W / 2, y + 86 + wob), 40, (255, 255, 255), "center", 5, (120, 30, 20))
    pygame.draw.circle(scr, (250, 250, 250), (int(W / 2 - 4), int(y - 6 + wob)), 0)

class TitleScene:
    kind = 'title'
    def __init__(self, game):
        self.game = game
        self.t = 0
        game.audio.play_music('title')
        game.audio.ambient_loop('waves', 0.3)

    def update(self, dt):
        self.t += dt

    def draw(self, scr):
        g = self.game
        draw_sea_backdrop(scr, self.t)
        draw_title_logo(scr, self.t, H * 0.22)
        bx = W / 2 - 160
        by = H * 0.5
        has = os.path.exists(os.path.join(SAVE_DIR, 'save.json'))
        if has and ui_button(scr, g, (bx, by, 320, 54), "Продолжить", size=22, col=(50, 90, 60)):
            g.load_game()
        if ui_button(scr, g, (bx, by + 66, 320, 54), "Новое путешествие", size=22, col=(60, 70, 120)):
            if has:
                g.confirm("Начать заново? Старое сохранение будет перезаписано после первого сохранения.", lambda: g.set_scene(CreationScene(g)))
            else:
                g.set_scene(CreationScene(g))
        if ui_button(scr, g, (bx, by + 132, 320, 54), "Выход", size=22, col=(110, 50, 50)):
            g.running = False
        draw_text(scr, "Фанатская игра. Вся графика, музыка и звуки созданы кодом.", (W / 2, H - 40), 14, (230, 230, 240), "center", 2)
        draw_text(scr, f"♪ «{TRACK_TITLES.get(g.audio.current, '')}»", (20, H - 30), 14, (255, 240, 200), "topleft", 2)

STARTING_STYLES = {
    'brawler': "Кулачный бой", 'sword1': "Иттору (один меч)", 'sword3': "Санторю (три меча)", 'sniper': "Снайпер",
    'blackleg': "Чёрная Нога (Длинноногие)", 'fishman_karate': "Карате рыболюдей (Рыболюди)", 'electro': "Электро (Минки)", 'rokushiki': "Рокусики (Дозор)",
}

class CreationScene:
    kind = 'create'
    def __init__(self, game):
        self.game = game
        self.t = 0
        self.step = 0
        self.faction = 'pirate'
        self.race = 'human'
        self.trait = 'king'
        self.name = ""
        self.style = 'brawler'
        self.opts = dict(skin=1, hair=0, hair_col=0, outfit=0, top=0, bottom=1, hat=1, hat_col=5, cape=0, feat=0)
        self.facing = math.pi / 2
        game.audio.play_music('island')
        pygame.key.start_text_input()

    FEATS = [(), ('scar_cheek',), ('scar_eye',), ('scars3',), ('beard',), ('mustache',), ('long_nose',), ('sunglasses',), ('cigar',), ('stitch',), ('grin',)]
    FEAT_NAMES = ["Нет", "Шрам под глазом", "Шрам через глаз", "Три шрама", "Борода", "Усы", "Длинный нос", "Тёмные очки", "Сигара", "Шов", "Ухмылка"]
    CAPES = [None, (30, 30, 35), (200, 40, 40), (245, 245, 245), (40, 60, 140), (110, 40, 130)]

    def app(self):
        o = self.opts
        a = default_app(skin=SKIN_TONES[o['skin'] % len(SKIN_TONES)], hair=HAIR_STYLES[o['hair'] % len(HAIR_STYLES)], hair_col=HAIR_COLORS[o['hair_col'] % len(HAIR_COLORS)],
                        outfit=OUTFITS[o['outfit'] % len(OUTFITS)], top=CLOTH_COLORS[o['top'] % len(CLOTH_COLORS)], bottom=CLOTH_COLORS[o['bottom'] % len(CLOTH_COLORS)],
                        hat=HAT_STYLES[o['hat'] % len(HAT_STYLES)], hat_col=CLOTH_COLORS[o['hat_col'] % len(CLOTH_COLORS)], cape=self.CAPES[o['cape'] % len(self.CAPES)],
                        features=self.FEATS[o['feat'] % len(self.FEATS)])
        if self.race == 'fishman':
            a['skin'] = (120, 170, 200) if o['skin'] < 6 else a['skin']
            a['features'] = tuple(a['features']) + ('fishman', 'fin')
        if self.race == 'mink':
            a['features'] = tuple(a['features']) + ('mink',)
            a['fur'] = a['hair_col']
        if self.race == 'lunarian':
            a['features'] = tuple(a['features']) + ('lunarian',)
            a['skin'] = (120, 90, 80) if o['skin'] < 4 else a['skin']
        if self.race == 'halfgiant':
            a['scale'] = 1.35
        if self.faction == 'marine' and a['outfit'] == 'marine':
            a['inner'] = (60, 90, 160)
        return a

    def handle_event(self, e):
        if self.step == 3:
            if e.type == pygame.TEXTINPUT:
                if len(self.name) < 18:
                    self.name += e.text
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_BACKSPACE:
                    self.name = self.name[:-1]

    def update(self, dt):
        self.t += dt
        self.facing += dt * 0.8

    def styles_allowed(self):
        s = ['brawler', 'sword1', 'sword3', 'sniper']
        if self.race == 'longleg':
            s.append('blackleg')
        if self.race == 'fishman':
            s.append('fishman_karate')
        if self.race == 'mink':
            s.append('electro')
        if self.faction == 'marine':
            s.append('rokushiki')
        return s

    def draw(self, scr):
        g = self.game
        scr.fill((18, 22, 38))
        for i in range(30):
            y = (i * 31 + self.t * 20) % H
            pygame.draw.line(scr, (24, 30, 52), (0, y), (W, y + 40), 2)
        steps = ["Путь", "Раса и черта", "Внешность", "Имя и стиль"]
        for i, s in enumerate(steps):
            c = (255, 220, 120) if i == self.step else ((140, 200, 140) if i < self.step else (110, 110, 130))
            draw_text(scr, f"{i + 1}. {s}", (60 + i * 220, 20), 20, c, "topleft", 2)
        # превью
        pv = pygame.Rect(40, 80, 380, 560)
        panel(scr, pv, (28, 32, 52), 230, (200, 170, 110), 14)
        app = self.app()
        st = dict(phase=self.t * 2, walk=0, pose='idle', pose_t=0, z=0, expr='normal')
        a2 = dict(app)
        a2['scale'] = 3.2 * app.get('scale', 1.0) / max(1.0, app.get('scale', 1.0))
        draw_character(scr, pv.centerx, pv.y + 330, a2, self.facing, st)
        pr = pygame.Rect(pv.centerx - 90, pv.y + 360, 180, 180)
        pygame.draw.rect(scr, (40, 36, 55), pr, border_radius=12)
        draw_portrait(scr, pr, app, 'normal')
        draw_text(scr, self.name or "???", (pv.centerx, pv.bottom - 14), 22, (255, 240, 200), "midbottom", 2)
        area = pygame.Rect(450, 70, W - 490, H - 150)
        getattr(self, 'step%d' % self.step)(scr, area)
        if self.step > 0 and ui_button(scr, g, (450, H - 66, 180, 48), "Назад", col=(80, 60, 60)):
            self.step -= 1
        if self.step < 3:
            if ui_button(scr, g, (W - 230, H - 66, 190, 48), "Далее", col=(60, 100, 60)):
                self.step += 1
        else:
            ok = len(self.name.strip()) > 0
            if ui_button(scr, g, (W - 330, H - 66, 290, 48), "В МОРЕ!", enabled=ok, col=(150, 90, 30), size=24):
                pygame.key.stop_text_input()
                g.new_game(self)

    def step0(self, scr, area):
        g = self.game
        draw_text(scr, "Кем ты станешь в этом море?", (area.x, area.y), 26, (255, 230, 150), "topleft", 2)
        for i, (fid, F) in enumerate(FACTIONS.items()):
            r = pygame.Rect(area.x + (i % 2) * (area.w // 2 + 4), area.y + 50 + (i // 2) * 250, area.w // 2 - 10, 236)
            if ui_button(scr, g, r, "", selected=self.faction == fid, col=mul_col(F['col'], 0.35)):
                self.faction = fid
                if fid != 'marine' and self.style == 'rokushiki':
                    self.style = 'brawler'
            draw_text(scr, F['name'], (r.x + 20, r.y + 16), 28, (255, 255, 255), "topleft", 3)
            for k_, ln in enumerate(wrap_text(get_font(16), F['desc'], r.w - 40)):
                draw_text(scr, ln, (r.x + 20, r.y + 62 + k_ * 22), 16, (230, 230, 240), "topleft", 1)
            start = ISLANDS[F['start']]['name']
            draw_text(scr, "Старт: " + start, (r.x + 20, r.bottom - 34), 14, (255, 230, 150), "topleft", 1)

    def step1(self, scr, area):
        g = self.game
        draw_text(scr, "Раса", (area.x, area.y), 24, (255, 230, 150), "topleft", 2)
        for i, (rid, R) in enumerate(RACES.items()):
            r = pygame.Rect(area.x, area.y + 40 + i * 52, 380, 46)
            if ui_button(scr, g, r, R['name'], selected=self.race == rid, size=17, tip=R['desc']):
                self.race = rid
        R = RACES[self.race]
        for k_, ln in enumerate(wrap_text(get_font(15), R['desc'], 380)):
            draw_text(scr, ln, (area.x, area.y + 420 + k_ * 20), 15, (210, 220, 240), "topleft", 1)
        tx = area.x + 420
        draw_text(scr, "Черта характера", (tx, area.y), 24, (255, 230, 150), "topleft", 2)
        for i, (tid, T) in enumerate(TRAITS.items()):
            r = pygame.Rect(tx, area.y + 40 + i * 92, area.w - 430, 82)
            if ui_button(scr, g, r, "", selected=self.trait == tid):
                self.trait = tid
            draw_text(scr, T['name'], (r.x + 16, r.y + 10), 20, (255, 255, 255), "topleft", 2)
            for k_, ln in enumerate(wrap_text(get_font(14), T['desc'], r.w - 30)[:2]):
                draw_text(scr, ln, (r.x + 16, r.y + 38 + k_ * 18), 14, (210, 220, 240), "topleft", 1)

    def step2(self, scr, area):
        g = self.game
        draw_text(scr, "Внешность", (area.x, area.y), 24, (255, 230, 150), "topleft", 2)
        rows = [('skin', "Кожа", len(SKIN_TONES)), ('hair', "Причёска", len(HAIR_STYLES)), ('hair_col', "Цвет волос", len(HAIR_COLORS)),
                ('outfit', "Одежда", len(OUTFITS)), ('top', "Цвет верха", len(CLOTH_COLORS)), ('bottom', "Цвет низа", len(CLOTH_COLORS)),
                ('hat', "Головной убор", len(HAT_STYLES)), ('hat_col', "Цвет убора", len(CLOTH_COLORS)), ('cape', "Плащ", len(self.CAPES)),
                ('feat', "Особенность", len(self.FEATS))]
        names = {'hair': HAIR_STYLES, 'outfit': OUTFITS, 'hat': HAT_STYLES}
        for i, (k, nm_, n) in enumerate(rows):
            y = area.y + 44 + i * 50
            draw_text(scr, nm_, (area.x, y + 8), 19, (240, 240, 240), "topleft", 2)
            if ui_button(scr, g, (area.x + 220, y, 44, 40), "<"):
                self.opts[k] = (self.opts[k] - 1) % n
            if ui_button(scr, g, (area.x + 480, y, 44, 40), ">"):
                self.opts[k] = (self.opts[k] + 1) % n
            v = self.opts[k] % n
            if k == 'feat':
                lab = self.FEAT_NAMES[v]
            elif k in names:
                lab = {'spiky': "Колючки", 'messy': "Растрёпанные", 'long': "Длинные", 'ponytail': "Хвост", 'buzz': "Ёжик", 'afro': "Афро", 'slick': "Зализанные",
                       'mohawk': "Ирокез", 'twin': "Два хвоста", 'bun': "Пучок", 'bald': "Лысый", 'wild': "Дикие", 'vest': "Жилет", 'coat': "Плащ-пальто",
                       'suit': "Костюм", 'kimono': "Кимоно", 'marine': "Форма Дозора", 'tank': "Майка", 'robe': "Мантия", 'armor': "Доспех", 'shirt': "Рубашка",
                       'jacket': "Куртка", 'none': "Нет", 'straw': "Соломенная шляпа", 'tricorn': "Треуголка", 'bandana': "Бандана", 'cap': "Кепка",
                       'marine_cap': "Фуражка Дозора", 'top_hat': "Цилиндр", 'wide': "Широкополая", 'headband': "Повязка", 'crown': "Корона",
                       'helmet': "Шлем", 'kasa': "Каса"}.get(names[k][v], names[k][v])
            elif k == 'cape':
                lab = "Нет" if v == 0 else f"Вариант {v}"
            else:
                col = (SKIN_TONES if k == 'skin' else (HAIR_COLORS if k == 'hair_col' else CLOTH_COLORS))[v]
                pygame.draw.rect(scr, col, (area.x + 280, y + 4, 180, 32), border_radius=6)
                pygame.draw.rect(scr, (255, 255, 255), (area.x + 280, y + 4, 180, 32), 2, border_radius=6)
                lab = None
            if lab:
                draw_text(scr, lab, (area.x + 372, y + 20), 17, (255, 255, 255), "center", 2)
        if ui_button(scr, g, (area.x + 560, area.y + 44, 220, 46), "Случайно!", col=(90, 60, 120)):
            for k, nm_, n in rows:
                self.opts[k] = random.randint(0, n - 1)

    def step3(self, scr, area):
        g = self.game
        draw_text(scr, "Имя (напиши с клавиатуры):", (area.x, area.y), 24, (255, 230, 150), "topleft", 2)
        r = pygame.Rect(area.x, area.y + 40, 520, 56)
        panel(scr, r, (30, 34, 52), 240, (230, 200, 130), 10, 3)
        cursor = "|" if int(self.t * 2) % 2 == 0 else ""
        draw_text(scr, self.name + cursor, (r.x + 16, r.y + 12), 28, (255, 255, 255), "topleft", 2)
        draw_text(scr, "Стартовый стиль боя:", (area.x, area.y + 130), 24, (255, 230, 150), "topleft", 2)
        for i, sid in enumerate(self.styles_allowed()):
            rr = pygame.Rect(area.x + (i % 2) * 380, area.y + 170 + (i // 2) * 60, 370, 52)
            if ui_button(scr, g, rr, STARTING_STYLES[sid], selected=self.style == sid, size=17, tip=STYLES[sid]['desc']):
                self.style = sid
        draw_text(scr, "Другие стили (Чёрная Нога, Рюо, Окама Кэмпо, Кулак Любви...) открываются у наставников по всему миру.", (area.x, area.bottom - 60), 15, (200, 210, 230), "topleft", 1)

class CinematicOverlay(Overlay):
    def __init__(self, game, kind, then):
        self.game = game
        self.kind = kind
        self.then = then
        self.t = 0
        self.dur = 3.2

    def update(self, dt):
        self.t += dt
        if self.t >= self.dur:
            self.done = True
            self.then()

    def draw(self, scr):
        t = self.t
        k = t / self.dur
        if self.kind == 'knockup':
            scr.blit(vgradient(W, H, (120, 180, 240), (230, 240, 255)), (0, 0))
            y = H - k * H * 1.3
            for i in range(30):
                x = W / 2 + math.sin(i * 1.7 + t * 5) * 120
                pygame.draw.circle(scr, (240, 250, 255), (int(x), int(y + 200 + i * 30)), 60)
            dummy = dict(self.game.pd.ship)
            draw_ship_sprite(scr, W / 2, y + 120, -math.pi / 2 + math.sin(t * 6) * 0.2, dummy, t, 1.8, 1.0)
            for i in range(10):
                cx = (i * 170 + t * 400) % (W + 200) - 100
                pygame.draw.ellipse(scr, (255, 255, 255), (cx, (i * 97) % H, 160, 60))
            draw_text(scr, "ПОТОК НОК-АП!", (W / 2, H * 0.15), 60, (255, 255, 255), "center", 5, (40, 80, 160))
            draw_text(scr, "10 000 метров вверх — к Небесному острову!", (W / 2, H * 0.24), 24, (255, 255, 255), "center", 3)
        else:
            c = lerp_col((40, 120, 200), (5, 15, 50), k)
            scr.fill(c)
            for i in range(40):
                bx = (i * 131) % W
                by = H - ((t * 200 + i * 47) % (H + 100))
                pygame.draw.circle(scr, (200, 230, 255), (int(bx), int(by)), 4 + i % 6, 1)
            dummy = dict(self.game.pd.ship)
            draw_ship_sprite(scr, W / 2, H * 0.4 + k * 160, -math.pi / 2, dummy, t, 1.6, 0.0)
            pygame.draw.circle(scr, (220, 240, 255), (int(W / 2), int(H * 0.4 + k * 160)), 170, 3)
            for i in range(6):
                fx = (i * 260 - t * 80) % (W + 200) - 100
                fy = H * 0.7 + math.sin(t + i) * 40
                pygame.draw.polygon(scr, (90, 160, 200), [(fx, fy), (fx + 40, fy - 12), (fx + 40, fy + 12)])
            draw_text(scr, "Погружение на 10 000 метров...", (W / 2, H * 0.12), 40, (220, 240, 255), "center", 4)
            if k > 0.7:
                draw_glow(scr, (W / 2, H * 0.95), 300 * (k - 0.7) * 3, (255, 220, 240), 0.8)

BOUNTY_AFTER = {'dawn': 2_000_000, 'shells': 5_000_000, 'orange': 8_000_000, 'syrup': 12_000_000, 'baratie': 17_000_000, 'arlong': 30_000_000,
                'loguetown': 36_000_000, 'whisky': 45_000_000, 'little_garden': 55_000_000, 'drum': 65_000_000, 'alabasta': 100_000_000,
                'jaya': 110_000_000, 'skypiea': 130_000_000, 'water7': 160_000_000, 'enies': 300_000_000, 'thriller': 330_000_000,
                'sabaody': 370_000_000, 'amazon': 380_000_000, 'impel': 400_000_000, 'marineford': 480_000_000, 'rusukaina': 500_000_000,
                'fishman': 550_000_000, 'punk': 600_000_000, 'dressrosa': 800_000_000, 'zou': 850_000_000, 'wci': 1_500_000_000,
                'wano': 3_000_000_000, 'egghead': 3_200_000_000, 'elbaf': 3_500_000_000}

class Game:
    def __init__(self):
        os.environ.setdefault('SDL_HINT_RENDER_SCALE_QUALITY', '1')
        pygame.init()
        flags = pygame.SCALED | pygame.RESIZABLE
        try:
            self.screen = pygame.display.set_mode((W, H), flags)
        except Exception:
            self.screen = pygame.display.set_mode((W, H))
        pygame.display.set_caption(GAME_TITLE)
        try:
            icon = pygame.Surface((32, 32), pygame.SRCALPHA)
            pygame.draw.circle(icon, (240, 210, 110), (16, 18), 14)
            pygame.draw.rect(icon, (200, 30, 30), (4, 14, 24, 4))
            pygame.display.set_icon(icon)
        except Exception:
            pass
        self.clock = pygame.time.Clock()
        self.audio = AudioManager()
        self.audio.start_generation()
        self.pd = None
        self.scene = LoadingScene(self)
        self.overlays = []
        self.running = True
        self.keys = pygame.key.get_pressed()
        self.kp = set()
        self.mb = (False, False, False)
        self.mbp = set()
        self.mouse = (0, 0)
        self.wheel = 0
        self.tooltip = None
        self.sea = None
        self.toasts = []
        self.fullscreen = False

    # ---------------- служебное ----------------
    def set_scene(self, s):
        self.scene = s

    def push(self, ov):
        self.overlays.append(ov)
        return ov

    def dialogue(self, lines, cb=None):
        self.push(DialogueOverlay(self, lines, cb))

    def confirm(self, text, yes, no=None):
        self.push(ConfirmOverlay(self, text, yes, no))

    def message(self, title, lines, on_done=None, poster=None, col=(230, 200, 130)):
        self.push(MessageOverlay(self, title, lines, on_done, poster, col))

    def toast(self, text):
        sc = self.scene
        if hasattr(sc, 'notify'):
            sc.notify(text, (255, 240, 200))
        self.toasts.append([text, 3.0])

    def toggle_fullscreen(self):
        try:
            pygame.display.toggle_fullscreen()
        except Exception:
            pass

    def tutorial_hint(self):
        self.message("Как сражаться", [
            ("WASD — движение, мышь — прицел. ЛКМ — комбо из 4 ударов.", (255, 255, 255)),
            ("ПКМ (держать) — заряженный удар: ломает защиту и здания.", (255, 255, 255)),
            ("Space — рывок. Рывок в момент удара врага = ИДЕАЛЬНОЕ УКЛОНЕНИЕ (замедление времени).", (200, 230, 255)),
            ("Shift — блок. Нажми Shift прямо перед ударом = ПАРИРОВАНИЕ (враг оглушён).", (200, 230, 255)),
            ("1-4 — приёмы (тратят выносливость). Новые приёмы открываются с мастерством.", (255, 230, 150)),
            ("Удары копят ДУХ. R — ультимейт (1 сегмент), F — пробуждение (2 сегмента).", (255, 220, 120)),
            ("Если босс начал ультимейт — нажми R для СТОЛКНОВЕНИЯ и жми ЛКМ!", (255, 180, 120)),
            ("Q/C/Z — Хаки (откроются по сюжету). X — съесть мясо. E — взаимодействие.", (220, 200, 255)),
            ("Tab — меню: распредели очки, выбери приёмы, экипировку, стиль.", (200, 255, 200)),
            ("Красные зоны на земле — атаки врагов. Уходи из них!", (255, 140, 140)),
        ])

    # ---------------- игра ----------------
    def new_game(self, cs):
        pd = PlayerData()
        pd.name = cs.name.strip()
        pd.app = cs.app()
        pd.race = cs.race
        pd.faction = cs.faction
        pd.trait = cs.trait
        pd.styles = {'brawler': 0.0}
        pd.styles[cs.style] = max(pd.styles.get(cs.style, 0.0), 0.0)
        r = RACES[cs.race]
        if r.get('style'):
            pd.styles[r['style']] = pd.styles.get(r['style'], 0.0)
        pd.style = cs.style
        if r.get('obs'):
            pd.unlock_haki('obs', 2)
        for _ in range(4):
            pd.inventory.append(make_item('meat'))
        pd.inventory.append(make_item('bento'))
        if cs.style in ('sword1', 'sword3'):
            pd.equip['weapon'] = make_item('katana')
            pd.styles.setdefault('sword1', 0.0)
        elif cs.style == 'sniper':
            pd.equip['weapon'] = make_item('flintlock')
        pd.equip['outfit'] = make_item('rags')
        if pd.faction == 'marine':
            pd.ship = new_ship('caravel')
            pd.ship['color'] = [235, 235, 240]
            pd.ship['sail_color'] = [245, 245, 250]
            pd.ship['figure'] = 'seagull'
            pd.ship['name'] = "Патрульный «Чайка»"
            pd.beli += 5000
        elif pd.faction == 'hunter':
            pd.beli += 4000
            pd.ship['name'] = "Шлюпка охотника"
        else:
            pd.ship['name'] = "Мечта" if pd.faction == 'pirate' else "Ветер Свободы"
        pd.ship['flag'] = FACTIONS[pd.faction]['flag']
        start = FACTIONS[pd.faction]['start']
        sp = ISLANDS[start]['pos']
        pd.sea_pos = [sp[0], sp[1] + 420]
        pd.fix_loadout()
        self.pd = pd
        self.sea = None
        self.enter_island(start)

    def save(self):
        if self.pd is None:
            return
        try:
            data = self.pd.to_json()
            data['_ver'] = 1
            tmp = os.path.join(SAVE_DIR, f'save.json.{os.getpid()}.tmp')
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, os.path.join(SAVE_DIR, 'save.json'))
        except Exception:
            traceback.print_exc()

    def load_game(self):
        try:
            with open(os.path.join(SAVE_DIR, 'save.json'), encoding='utf-8') as f:
                data = json.load(f)
            self.pd = PlayerData.from_json(data)
            self.pd.fix_loadout()
            self.sea = None
            self.go_sea()
        except Exception:
            traceback.print_exc()
            self.message("Ошибка", ["Не удалось загрузить сохранение."])

    def to_title(self):
        self.overlays = []
        self.sea = None
        self.set_scene(TitleScene(self))

    def go_sea(self, pos=None, heading=None):
        if self.sea is None:
            self.sea = SeaScene(self, pos, heading)
        else:
            if pos is not None:
                self.sea.ship.pos = V(pos)
            if heading is not None:
                self.sea.ship.heading = heading
            self.sea.ship.speed = 0
            self.sea.ship.sail_target = 0
            self.sea.apply_ship_stats()
            self.sea.ships = [self.sea.ship] + [s for s in self.sea.ships if s is not self.sea.ship and dist(s.pos, self.sea.ship.pos) > 1500]
            self.audio.play_music('sea')
            self.audio.ambient_loop('waves', 0.35)
        self.sea.apply_ship_stats()
        self.sea.buster_check()
        self.set_scene(self.sea)

    def enter_island(self, iid):
        pd = self.pd
        isl = ISLANDS[iid]
        pd.last_island = iid
        self.save()
        self.set_scene(IslandScene(self, iid))

    def leave_island(self, scene):
        pd = self.pd
        iid = scene.iid
        if scene.deck is not None:
            return
        isl = ISLANDS[iid]
        if iid == 'skypiea':
            pos = (KNOCKUP_POS[0], KNOCKUP_POS[1] + 500)
        elif iid == 'fishman':
            if pd.island_state('fishman')['done']:
                pos = (REDLINE2_X[1] + 1700, FISHMAN_GATE_POS[1] + 500)
            else:
                pos = (REDLINE2_X[0] - 700, FISHMAN_GATE_POS[1])
        else:
            R = 170 + min(120, isl['size'][0] * 1.2) if isl['theme'] != 'restaurant' else 120
            pos = (isl['pos'][0], isl['pos'][1] + R + 230)
        self.save()
        self.go_sea(pos, math.pi / 2)

    def cinematic_knockup(self):
        self.push(CinematicOverlay(self, 'knockup', lambda: self.enter_island('skypiea')))
        self.audio.play('splash', 1.0)

    def cinematic_dive(self):
        self.push(CinematicOverlay(self, 'dive', lambda: self.enter_island('fishman')))
        self.audio.play('splash', 1.0)

    def start_boarding(self, ship):
        isl = dict(name="Абордаж: " + ship.name, region='sea', pos=(0, 0), lvl=ship.level, theme='shipdeck', boss={'*': None},
                   enemies=ship.pool, intro={}, outro={}, size=(44, 30), mids={}, mentor=[], shop=[], flags=set(), companion={},
                   reward={}, groups=2, music='battle', weather=None, req=None, hidden=True, hub=None, fruit_shop=[], shipwright=0,
                   blacksmith=False, tavern=False, enemies_marine=None, desc="", extra_boss=None, chest_fruit=None)
        deck = dict(isl=isl, pool=ship.pool, lvl=ship.level, ship=ship)
        sc = IslandScene(self, 'deck_' + str(id(ship)), deck=deck)
        self.boarding_ship = ship
        self.set_scene(sc)

    def deck_victory(self, scene):
        pd = self.pd
        ship = getattr(self, 'boarding_ship', None)
        lvl = scene.lvl
        beli = int(2500 * (1 + lvl * 0.5))
        pd.beli += beli
        items = []
        for _ in range(2):
            iid = random.choice(['steel', 'iron', 'gold', 'cola', 'sea_king_meat', 'kairoseki' if lvl > 30 else 'wood'])
            pd.add_item(make_item(iid))
            items.append(ITEMS[iid]['name'])
        self.reward_rep(lvl * 60000, quiet=True, kind='ship')
        if ship is not None:
            ship.sink()
        def back():
            self.go_sea()
        self.message("Абордаж успешен!", [f"+{fmt_num(beli)} ฿", "Трофеи: " + ", ".join(items)], back)

    def reward_rep(self, amount, quiet=False, kind='boss'):
        pd = self.pd
        f = pd.faction
        before = pd.title()
        if f == 'pirate':
            pd.bounty += int(amount * 0.5)
        elif f == 'marine':
            pd.merit += max(1, int(amount / 400000))
        elif f == 'revo':
            pd.merit += max(1, int(amount / 500000))
            pd.bounty += int(amount * 0.25)
        elif f == 'hunter':
            pd.merit += max(1, int(amount / 450000))
            pd.beli += int(amount * 0.01)
        after = pd.title()
        if after != before:
            self.toast(f"Новое звание: {after}!")

    def on_destroyed(self, scene, s):
        pd = self.pd
        if scene.deck is not None:
            return
        pd.destroyed += 1
        big = s.kind in ('house', 'tower', 'hall', 'fort', 'palace', 'castle', 'colosseum', 'ruin')
        if not big:
            return
        lvl = scene.lvl
        if s.tag == 'landmark':
            scene.notify(f"Разрушено: {('Крепость' if s.kind == 'fort' else 'Главное здание')} острова!", (255, 160, 80))
            self.reward_rep(lvl * 400000, quiet=True, kind='destroy')
            if pd.faction in ('pirate', 'revo') and pd.bounty > 150_000_000 and random.random() < 0.6:
                pd.flags.add('buster_pending')
                scene.notify("Правительство объявило БАСТЕР КОЛЛ! Флот ждёт тебя в море...", (255, 90, 90))
            return
        if s.civil:
            if pd.faction == 'marine':
                pd.merit = max(0, pd.merit - 3)
                if random.random() < 0.3:
                    scene.notify("Дозор не одобряет разрушения гражданских построек! (−заслуги)", (255, 150, 150))
            elif pd.faction == 'pirate':
                pd.bounty += int(80000 * lvl)
                if random.random() < 0.25:
                    scene.notify("Разрушения поднимают твою награду!", (255, 200, 120))
            elif pd.faction == 'revo':
                pd.bounty += int(40000 * lvl)
                pd.merit = max(0, pd.merit - 1)
            elif pd.faction == 'hunter':
                fine = 300 * lvl
                pd.beli = max(0, pd.beli - fine)
                if random.random() < 0.3:
                    scene.notify(f"Штраф за разрушения: −{fmt_num(fine)} ฿", (255, 180, 150))

    def open_service(self, role, scene):
        self.push(ServiceOverlay(self, role, scene))

    def open_mentor(self, mid, scene):
        self.push(MentorOverlay(self, mid, scene))

    def mentor_success(self, mid, scene):
        pd = self.pd
        M = MENTORS[mid]
        lines = []
        first = mid not in pd.mentors_done
        pd.mentors_done.add(mid)
        st = M.get('style')
        if st and st not in pd.styles:
            pd.styles[st] = 1.0
            lines.append(("Новый стиль боя: " + STYLES[st]['name'] + "!", (255, 230, 120)))
            lines.append(STYLES[st]['desc'])
            if STYLES[st].get('weapon') == 'sword' and pd.weapon_kind() != 'sword':
                pd.inventory.append(make_item('katana'))
                lines.append("Наставник дарит тебе катану.")
            if st == 'clima' and pd.weapon_kind() != 'clima':
                pd.inventory.append(make_item('clima_tact'))
                lines.append("Получен Клима-Такт.")
        elif st:
            pd.styles[st] = min(100.0, pd.styles[st] + 3)
            lines.append(f"Мастерство стиля {STYLES[st]['name']} +3")
        if mid in ('rayleigh',):
            for k, cap in (('arm', 6), ('obs', 6)):
                if pd.unlock_haki(k, cap) or first:
                    lines.append((f"Хаки {'Вооружения' if k == 'arm' else 'Наблюдения'}: предел {pd.haki_cap[k]}", (200, 160, 255)))
            if pd.trait == 'king' and pd.haki_cap['conq'] > 0:
                pd.unlock_haki('conq', 5)
                lines.append(("Королевское Хаки: предел 5", (255, 100, 100)))
        if mid == 'sabo_m':
            pd.unlock_haki('arm', 5)
            pd.unlock_haki('obs', 5)
            lines.append(("Хаки Вооружения и Наблюдения: предел 5", (200, 160, 255)))
        if mid == 'garp':
            pd.unlock_haki('arm', 5)
            lines.append(("Хаки Вооружения: предел 5", (200, 160, 255)))
        if mid == 'hyogoro':
            pd.flags.add('ryou')
            pd.unlock_haki('arm', 10)
            lines.append(("РЮО освоено! Хаки Вооружения 8+ даёт внутреннее разрушение. Предел: 10", (255, 200, 120)))
        if mid == 'mihawk':
            for s_ in ('sword1', 'sword2', 'sword3'):
                pd.styles[s_] = min(100.0, pd.styles.get(s_, 0.0) + 20)
            lines.append(("Мастерство стилей мечников +20!", (255, 230, 150)))
        if mid == 'ivankov':
            pd.stats['vit'] += 3 if first else 0
            if first:
                lines.append("Гормоны Иванкова: +3 Живучести")
        if mid == 'minks' and first:
            pd.unlock_haki('obs', max(3, pd.haki_cap['obs']))
            lines.append("Минки научили тебя чувствовать врагов (Наблюдение).")
        xp = 200 * pd.level
        ups = pd.add_xp(xp)
        lines.append(f"+{fmt_num(xp)} опыта")
        pd.fix_loadout()
        self.apply_player_changes()
        self.dialogue([(mid, "Хорошо. Ты способный ученик.")], lambda: self.message("Тренировка завершена!", lines))
        if ups and hasattr(scene, 'on_levelup'):
            scene.on_levelup(ups)

    def apply_player_changes(self):
        sc = self.scene
        pd = self.pd
        if pd is None:
            return
        pd.fix_loadout()
        if isinstance(sc, IslandScene):
            sc.player.pd = pd
            sc.player.apply_stats()
        elif isinstance(sc, SeaScene):
            sc.apply_ship_stats()

    def island_complete(self, iid, boss_id):
        pd = self.pd
        isl = ISLANDS[iid]
        st = pd.island_state(iid)
        first = not st['done']
        st['done'] = True
        lines = []
        rw = isl['reward']
        xp = rw.get('xp', 0)
        beli = rw.get('beli', 0)
        if pd.trait == 'lucky':
            beli = int(beli * 1.25)
        pd.beli += beli
        ups = pd.add_xp(xp)
        lines.append((f"+{fmt_num(xp)} опыта   +{fmt_num(beli)} ฿", (255, 230, 120)))
        if ups:
            lines.append((f"Новый уровень: {pd.level}! (+{3 * ups} очков)", (255, 230, 90)))
        names = []
        for iid2 in rw.get('items', []):
            it = make_item(iid2)
            pd.add_item(it)
            names.append(it['name'])
        if names:
            lines.append("Получено: " + ", ".join(names))
        if boss_id:
            b = BOSSES[boss_id]
            if b.get('drop'):
                for d in b['drop']:
                    pd.add_item(make_item(d))
                    lines.append(("Трофей босса: " + ITEMS[d]['name'], RARITY_COLORS[ITEMS[d]['rarity']]))
        # репутация
        old_bounty = pd.bounty
        f = pd.faction
        lvl = isl['lvl']
        target = BOUNTY_AFTER.get(iid)
        if f == 'pirate':
            if target:
                pd.bounty = max(pd.bounty + int(target * 0.1), target)
            elif boss_id:
                pd.bounty += int(BOSSES[boss_id].get('bounty', 0) * 0.08 + lvl * 3_000_000)
            if pd.race == 'lunarian':
                pd.bounty = int(pd.bounty * 1.1)
        elif f == 'revo':
            pd.merit += 30 * lvl
            if target:
                pd.bounty = max(pd.bounty, int(target * 0.6))
        elif f == 'hunter':
            bb = BOSSES[boss_id]['bounty'] if boss_id else 0
            pd.merit += 30 * lvl + bb // 10_000_000
            reward = int(bb * 0.02)
            if reward:
                pd.beli += reward
                lines.append((f"Награда за голову: +{fmt_num(reward)} ฿", (120, 255, 140)))
            if target and lvl > 40:
                pd.bounty = max(pd.bounty, int(target * 0.25))
        elif f == 'marine':
            bb = BOSSES[boss_id]['bounty'] if boss_id else 0
            pd.merit += 40 * lvl + bb // 2_000_000
            lines.append((f"Заслуги перед Дозором: {fmt_num(pd.merit)} — звание: {pd.title()}", (150, 200, 255)))
            pd.beli += 500 * lvl
        if f != 'marine':
            lines.append((f"{FACTIONS[f]['rep_name']}: {('฿ ' + fmt_num(pd.bounty)) if f == 'pirate' else fmt_num(pd.merit)} — {pd.title()}", (255, 180, 180)))
        # флаги
        fl = isl['flags']
        if 'reverse_mountain' in fl:
            pd.flags.add('reverse')
            lines.append(("Путь на Гранд Лайн открыт: Ревёрс Маунтин (восток, в Ред Лайн).", (150, 220, 255)))
        if 'log_pose' in fl:
            pd.flags.add('log_pose')
        if 'knockup' in fl:
            pd.flags.add('knockup')
        if 'coating' in fl:
            pd.flags.add('coating')
        if 'haki_obs' in fl and pd.unlock_haki('obs', 3):
            lines.append(("ХАКИ НАБЛЮДЕНИЯ пробудилось! (C)", (200, 200, 255)))
        if 'haki_arm' in fl and pd.unlock_haki('arm', 3):
            lines.append(("ХАКИ ВООРУЖЕНИЯ пробудилось! (Q)", (200, 160, 255)))
        if 'marine_armament' in fl and f == 'marine' and pd.unlock_haki('arm', 2):
            lines.append(("Дозор научил тебя Хаки Вооружения! (Q)", (200, 160, 255)))
        if 'revo_armament' in fl and f == 'revo' and pd.unlock_haki('arm', 2):
            lines.append(("Сабо и Коала научили тебя Хаки Вооружения! (Q)", (200, 160, 255)))
        if 'hunter_observation' in fl and f == 'hunter' and pd.unlock_haki('obs', 2):
            lines.append(("Чутьё охотника: Хаки Наблюдения! (C)", (200, 200, 255)))
        if 'conq_awaken' in fl and pd.trait == 'king' and pd.unlock_haki('conq', 3):
            lines.append(("КОРОЛЕВСКОЕ ХАКИ ПРОБУДИЛОСЬ! (Z) — слабые враги теряют сознание.", (255, 90, 90)))
        if 'timeskip' in fl:
            pd.flags.add('timeskip')
            for k in ('arm', 'obs'):
                pd.unlock_haki(k, max(7, pd.haki_cap[k]))
            if pd.trait == 'king':
                pd.unlock_haki('conq', max(6, pd.haki_cap['conq']))
            pd.points += 6
            lines.append(("Два года тренировок: пределы хаки 7, +6 очков характеристик!", (255, 220, 120)))
        if 'future_sight' in fl:
            pd.flags.add('future_sight')
            pd.unlock_haki('obs', 10)
            lines.append(("Предвидение будущего: при Наблюдении 7+ хаки C даёт идеальные уклонения и контратаки.", (255, 150, 220)))
        if 'ryou' in fl:
            pd.flags.add('ryou')
            pd.unlock_haki('arm', 10)
        if 'conq_coat' in fl and pd.trait == 'king':
            pd.flags.add('conq_coat')
            pd.unlock_haki('conq', 10)
            lines.append(("Покрытие Королевским хаки: при уровне 5+ твои удары окутаны чёрными молниями!", (255, 80, 80)))
        if 'poneglyph' in fl:
            pd.poneglyphs = min(4, pd.poneglyphs + 1)
        if 'ship_caravel' in fl and pd.ship['tier'] == 'dinghy':
            old = pd.ship
            pd.ship = new_ship('caravel')
            pd.ship['name'] = "Гоинг Мэри?" if pd.faction == 'pirate' else old['name']
            pd.ship['figure'] = 'sheep' if pd.faction == 'pirate' else old.get('figure', 'lion')
            pd.ship['flag'] = old.get('flag', 'skull')
            lines.append(("Новый корабль: Каравелла!", (255, 230, 150)))
        if 'giant_blessing' in fl:
            pd.flags.add('giant_blessing')
            lines.append("Благословение воинов Эльбафа: +5% к силе атаки.")
        if iid == 'fishman':
            pd.flags.add('new_world')
            lines.append(("Путь в НОВЫЙ МИР открыт!", (150, 220, 255)))
        comp = isl['companion'].get(f) or isl['companion'].get('*')
        if comp and comp not in pd.companions:
            pd.companions.append(comp)
            if len(pd.active_comp) < 2:
                pd.active_comp.append(comp)
            lines.append((f"К тебе присоединился: {COMPANIONS[comp]['name']}!", (120, 255, 160)))
        if isl.get('hub') == f:
            lines.append("Здесь твоя база: тренировки и снабжение.")
        pd.fix_loadout()
        self.apply_player_changes()
        poster = None
        if pd.bounty > old_bounty and f in ('pirate', 'revo', 'hunter'):
            poster = make_wanted_poster(pd.name, pd.bounty, pd.app, pd.title())
            lines.insert(0, (f"НАГРАДА ЗА ГОЛОВУ: ฿ {fmt_num(old_bounty)} → ฿ {fmt_num(pd.bounty)}", (255, 120, 100)))
        elif f == 'marine':
            poster = make_wanted_poster(pd.name, pd.merit, pd.app, pd.title(), marine=True)
        self.save()
        def after():
            if 'finale' in fl:
                self.message("Продолжение следует...", [
                    ("Ты прошёл все арки до Эльбафа — до текущей главы истории.", (255, 230, 150)),
                    "Ласт-понеглифы: " + str(pd.poneglyphs) + " / 4. Путь к Лаф Тейл ждёт...",
                    "Тебя ещё ждут легенды этого моря: Михоук на Курайгане, Чёрная Борода на Хатиносу,",
                    "Адмирал Флота в Штабе Дозора и сам Шанкс. Сможешь ли ты одолеть Императоров?",
                    ("Спасибо, что играешь!", (200, 255, 200))], col=(255, 210, 100))
        self.message(("Остров освобождён!" if f != 'marine' else "Миссия выполнена!") + (" " if first else ""), lines, after, poster)

    # ---------------- главный цикл ----------------
    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            dt = min(dt, 0.05)
            self.kp = set()
            self.mbp = set()
            self.wheel = 0
            self.tooltip = None
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    if self.pd is not None and isinstance(self.scene, (IslandScene, SeaScene)):
                        self.save()
                    self.running = False
                elif e.type == pygame.KEYDOWN:
                    self.kp.add(e.key)
                    if e.key == pygame.K_F11:
                        self.toggle_fullscreen()
                elif e.type == pygame.MOUSEBUTTONDOWN:
                    if e.button in (1, 2, 3):
                        self.mbp.add(e.button if e.button != 2 else 2)
                        if e.button == 3:
                            self.mbp.add(3)
                elif e.type == pygame.MOUSEWHEEL:
                    self.wheel = e.y
                if self.overlays:
                    self.overlays[-1].handle_event(e)
                elif hasattr(self.scene, 'handle_event'):
                    self.scene.handle_event(e)
            self.keys = pygame.key.get_pressed()
            mb = pygame.mouse.get_pressed()
            self.mb = (mb[0], mb[1], mb[2])
            self.mouse = pygame.mouse.get_pos()
            self.step(dt)
            pygame.display.flip()
        pygame.quit()

    def step(self, dt):
        try:
            self._step(dt)
        except Exception:
            traceback.print_exc()
            self.err_count = getattr(self, 'err_count', 0) + 1
            try:
                with open(os.path.join(SAVE_DIR, 'error.log'), 'a', encoding='utf-8') as f:
                    f.write(traceback.format_exc() + "\n")
            except Exception:
                pass
            if self.overlays:
                self.overlays.pop()

    def _step(self, dt):
        if self.pd is not None and isinstance(self.scene, (IslandScene, SeaScene)):
            self.pd.playtime += dt
        if self.overlays:
            top = self.overlays[-1]
            top.update(dt)
            if top.done and top in self.overlays:
                self.overlays.remove(top)
            if not top.pauses:
                self.scene.update(dt)
        else:
            if isinstance(self.scene, (IslandScene, SeaScene)) and (pygame.K_TAB in self.kp or (pygame.K_ESCAPE in self.kp and not (isinstance(self.scene, IslandScene) and self.scene.defeat_t is not None))):
                if isinstance(self.scene, SeaScene) and self.scene.map_open:
                    self.scene.update(dt)
                else:
                    self.push(PauseMenu(self))
            else:
                self.scene.update(dt)
        try:
            self.scene.draw(self.screen)
        except Exception:
            traceback.print_exc()
        for ov in self.overlays:
            ov.draw(self.screen)
        for t in self.toasts:
            t[1] -= dt
        self.toasts = [t for t in self.toasts if t[1] > 0]
        if self.overlays and self.toasts:
            for i, (txt, tt) in enumerate(self.toasts[-3:]):
                draw_text(self.screen, txt, (W / 2, H - 40 - i * 26), 18, (255, 240, 200), "center", 3, alpha=int(255 * clamp(tt, 0, 1)))
        if DEBUG:
            draw_text(self.screen, f"FPS {self.clock.get_fps():.0f}", (W - 10, H - 10), 14, (255, 255, 0), "bottomright", 2)

def main():
    if HEADLESS_TEST:
        os.environ['SDL_VIDEODRIVER'] = 'dummy'
        os.environ['SDL_AUDIODRIVER'] = 'dummy'
    g = Game()
    try:
        g.run()
    except KeyboardInterrupt:
        pass
    except Exception:
        traceback.print_exc()
        try:
            g.save()
        except Exception:
            pass
        raise

if __name__ == "__main__":
    main()
