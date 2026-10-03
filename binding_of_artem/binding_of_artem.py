#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================
            СВЯЗЫВАНИЕ  АРТЁМА   (The Binding of Artem)
==========================================================================
Рогалик в духе The Binding of Isaac по сюжету про Артёма, Костяна,
Валерия, Дымка, Серёгу Головко и Иисуса.

ЗАПУСК:   python binding_of_artem.py
Нужны pygame и numpy - скрипт сам попробует их поставить через pip.
Вся графика и вся музыка генерируются кодом (музыка кешируется в
папку ~/.binding_of_artem при первом запуске).

УПРАВЛЕНИЕ
  WASD ........... ходьба
  Стрелки ........ стрельба
  ПРОБЕЛ ......... активный предмет
  E / Shift ...... бомба
  ENTER .......... поговорить / выбрать
  TAB ............ статы и полная карта
  ESC ............ пауза
  M .............. вкл/выкл музыку
  F11 ............ полный экран
  (в диалогах: W/S или стрелки - выбор, ENTER/Z - далее, X - промотать)
==========================================================================
"""
import sys
import os
import subprocess
import importlib

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def _bootstrap():
    need = []
    for mod, pkg in (("pygame", "pygame"), ("numpy", "numpy")):
        try:
            importlib.import_module(mod)
        except ImportError:
            need.append(pkg)
    if not need:
        return
    print("[СВЯЗЫВАНИЕ АРТЁМА] Ставлю библиотеки:", ", ".join(need))
    for extra in ([], ["--user"]):
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", *extra, *need])
            break
        except Exception as e:  # noqa
            print("   не получилось:", e)
    else:
        print("Поставь вручную:  pip install pygame numpy")
        try:
            input("Нажми Enter...")
        except Exception:
            pass
        sys.exit(1)
    # перезапуск, чтобы подхватились свежие пакеты
    sys.exit(subprocess.call([sys.executable] + sys.argv))


if __name__ == "__main__":
    _bootstrap()

import math
import random
import json
import time
import threading
import hashlib
import wave
import io
from collections import deque

import numpy as np
import pygame

# ============================================================================
#                                 КОНСТАНТЫ
# ============================================================================
GAME_TITLE = "СВЯЗЫВАНИЕ АРТЁМА"
VERSION = "1.0"
WW, WH = 480, 288            # "пиксельное" разрешение мира
SW, SH = 960, 576            # разрешение окна (мир масштабируется x2)
TILE = 32
COLS, ROWS = 13, 7
RX0, RY0 = 32, 40            # левый верхний угол пола комнаты
RX1, RY1 = RX0 + COLS * TILE, RY0 + ROWS * TILE   # 448, 264
RCX, RCY = (RX0 + RX1) / 2, (RY0 + RY1) / 2
FPS = 60
DT = 1.0 / FPS
SAVE_DIR = os.path.join(os.path.expanduser("~"), ".binding_of_artem")
DIRS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
OPP = {"up": "down", "down": "up", "left": "right", "right": "left"}
DOOR_TILE = {"up": (6, -1), "down": (6, ROWS), "left": (-1, 3), "right": (COLS, 3)}


# ============================================================================
#                                 УТИЛИТЫ
# ============================================================================
def clamp(v, a, b):
    return a if v < a else b if v > b else v


def lerp(a, b, t):
    return a + (b - a) * t


def dist(ax, ay, bx, by):
    return math.hypot(bx - ax, by - ay)


def norm(x, y):
    l = math.hypot(x, y)
    if l < 1e-9:
        return 0.0, 0.0
    return x / l, y / l


def from_ang(a, s=1.0):
    return math.cos(a) * s, math.sin(a) * s


def ang_to(ax, ay, bx, by):
    return math.atan2(by - ay, bx - ax)


def approach(v, t, d):
    if v < t:
        return min(v + d, t)
    return max(v - d, t)


def col_mul(c, k):
    return (clamp(int(c[0] * k), 0, 255), clamp(int(c[1] * k), 0, 255), clamp(int(c[2] * k), 0, 255))


def col_mix(a, b, t):
    return (int(lerp(a[0], b[0], t)), int(lerp(a[1], b[1], t)), int(lerp(a[2], b[2], t)))


def ease_out(t):
    t = clamp(t, 0, 1)
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    t = clamp(t, 0, 1)
    return t * t * (3 - 2 * t)


def tile_center(c, r):
    return RX0 + c * TILE + TILE / 2, RY0 + r * TILE + TILE / 2


def pos_tile(x, y):
    return int((x - RX0) // TILE), int((y - RY0) // TILE)


def circle_rect_push(cx, cy, r, rx, ry, rw, rh):
    """Возвращает вектор выталкивания круга из прямоугольника (или None)."""
    nx = clamp(cx, rx, rx + rw)
    ny = clamp(cy, ry, ry + rh)
    dx, dy = cx - nx, cy - ny
    d2 = dx * dx + dy * dy
    if d2 >= r * r:
        return None
    if d2 < 1e-9:
        # центр внутри - выталкиваем по наименьшей оси
        left = cx - rx
        right = rx + rw - cx
        top = cy - ry
        bot = ry + rh - cy
        m = min(left, right, top, bot)
        if m == left:
            return (-(left + r), 0)
        if m == right:
            return (right + r, 0)
        if m == top:
            return (0, -(top + r))
        return (0, bot + r)
    d = math.sqrt(d2)
    k = (r - d) / d
    return (dx * k, dy * k)


# ============================================================================
#                                СОХРАНЕНИЕ
# ============================================================================
class SaveData:
    DEFAULT = {
        "endings": [],
        "kostya_deaths": 0,
        "kostya_ckpt": None,
        "chars": ["artem"],
        "music": 0.65,
        "sfx": 0.8,
        "fullscreen": False,
        "runs": 0,
        "deaths": 0,
        "wins": 0,
        "prologue_seen": False,
        "items_seen": [],
    }

    def __init__(self):
        self.path = os.path.join(SAVE_DIR, "save.json")
        self.data = json.loads(json.dumps(self.DEFAULT))
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict):
                self.data.update(d)
        except Exception:
            pass

    def save(self):
        try:
            os.makedirs(SAVE_DIR, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except Exception as e:
            print("save error:", e)

    def __getitem__(self, k):
        return self.data.get(k, self.DEFAULT.get(k))

    def __setitem__(self, k, v):
        self.data[k] = v

    def unlock_ending(self, eid):
        if eid not in self.data["endings"]:
            self.data["endings"].append(eid)
            self.save()
            return True
        return False

    def unlock_char(self, cid):
        if cid not in self.data["chars"]:
            self.data["chars"].append(cid)
            self.save()
            return True
        return False


SAVE = SaveData()

# ============================================================================
#                          ЗВУК: СИНТЕЗАТОР
# ============================================================================
SR = 32000
TABN = 2048
_TBL = {}
_NH_STEPS = (1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 48, 64)


def _wavetable(kind, nh):
    key = (kind, nh)
    t = _TBL.get(key)
    if t is not None:
        return t
    ph = np.arange(TABN, dtype=np.float64) / TABN
    y = np.zeros(TABN)
    if kind == "sine":
        y = np.sin(2 * np.pi * ph)
    elif kind == "tri":
        for k in range(1, nh + 1, 2):
            y += ((-1) ** ((k - 1) // 2)) * np.sin(2 * np.pi * k * ph) / (k * k)
    elif kind == "saw":
        for k in range(1, nh + 1):
            y += np.sin(2 * np.pi * k * ph) / k
    elif kind.startswith("pulse"):
        d = float(kind[5:]) / 100.0
        for k in range(1, nh + 1):
            y += np.sin(np.pi * k * d) / k * np.cos(2 * np.pi * k * (ph - d / 2))
    elif kind == "organ":
        for k, a in ((1, 1.0), (2, 0.7), (3, 0.45), (4, 0.35), (6, 0.22), (8, 0.18), (10, 0.08)):
            if k <= nh:
                y += a * np.sin(2 * np.pi * k * ph)
    elif kind == "choir":
        # грубая "аа"-форманта
        for k in range(1, min(nh, 24) + 1):
            f = k
            amp = (1.0 / k) * (1.0 + 2.2 * math.exp(-((f - 3.2) ** 2) / 1.8) + 1.2 * math.exp(-((f - 7.5) ** 2) / 4.0))
            y += amp * np.sin(2 * np.pi * k * ph + k * 0.7)
    elif kind == "brass":
        for k in range(1, nh + 1):
            y += np.sin(2 * np.pi * k * ph) / (k ** 0.85) * (1.0 if k < 9 else 0.5)
    elif kind == "reed":
        for k in range(1, nh + 1):
            a = (1.0 / k) if k % 2 else (0.35 / k)
            y += a * np.sin(2 * np.pi * k * ph)
    else:
        y = np.sin(2 * np.pi * ph)
    y -= y.mean()
    m = np.max(np.abs(y))
    if m > 0:
        y /= m
    t = y.astype(np.float32)
    _TBL[key] = t
    return t


def _nh_for(f, bright):
    lim = int((SR * 0.45) / max(f, 1.0))
    lim = max(1, min(lim, bright))
    best = 1
    for s in _NH_STEPS:
        if s <= lim:
            best = s
    return best


def osc(kind, f, n, bright=64, fm=None, phase0=0.0):
    nh = _nh_for(f, bright)
    tbl = _wavetable(kind, nh)
    if fm is None:
        ph = phase0 + np.arange(n, dtype=np.float64) * (f / SR)
    else:
        ph = phase0 + np.cumsum(f * fm) / SR
    idx = (ph * TABN).astype(np.int64) & (TABN - 1)
    return tbl[idx]


def noise(n, seed=None):
    rs = np.random.RandomState(seed) if seed is not None else np.random
    return rs.uniform(-1, 1, n).astype(np.float32)


def smooth(x, k):
    if k <= 1:
        return x
    ker = np.ones(int(k), dtype=np.float32) / k
    return np.convolve(x, ker, mode="same").astype(np.float32)


def env_adsr(n_on, a, d, s, r):
    a_n = max(1, int(a * SR))
    d_n = max(1, int(d * SR))
    r_n = max(1, int(r * SR))
    n = n_on + r_n
    idx = np.arange(n, dtype=np.float64)
    xs = [0, a_n, a_n + d_n]
    ys = [0.0, 1.0, s]
    e = np.interp(np.minimum(idx, n_on), xs, ys)
    off = float(np.interp(n_on, xs, ys))
    rel = idx >= n_on
    e[rel] = off * (1.0 - (idx[rel] - n_on) / r_n)
    return np.clip(e, 0, 1).astype(np.float32)


def midi_freq(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


_NOTE_BASE = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}


def note_midi(s):
    s = s.strip().lower()
    n = _NOTE_BASE[s[0]]
    i = 1
    while i < len(s) and s[i] in "#b":
        n += 1 if s[i] == "#" else -1
        i += 1
    octv = int(s[i:])
    return 12 * (octv + 1) + n


# ---------------------------------------------------------------- инструменты
INST = {
    "lead":    dict(w="pulse25", a=0.006, d=0.14, s=0.62, r=0.09, vib=(5.6, 0.010, 0.18), bright=22),
    "lead50":  dict(w="pulse50", a=0.006, d=0.12, s=0.6, r=0.08, vib=(5.0, 0.010, 0.2), bright=18),
    "lead12":  dict(w="pulse12.5", a=0.004, d=0.1, s=0.55, r=0.06, vib=(6.0, 0.009, 0.15), bright=26),
    "saw":     dict(w="saw", a=0.01, d=0.2, s=0.6, r=0.12, vib=(5.2, 0.008, 0.2), bright=14, det=(0.996, 1.004)),
    "brass":   dict(w="brass", a=0.035, d=0.2, s=0.75, r=0.12, vib=(5.0, 0.008, 0.25), bright=12, det=(0.997, 1.003)),
    "bass":    dict(w="tri", a=0.003, d=0.08, s=0.85, r=0.04, bright=16),
    "sqbass":  dict(w="pulse50", a=0.003, d=0.09, s=0.7, r=0.04, bright=7),
    "sawbass": dict(w="saw", a=0.003, d=0.12, s=0.6, r=0.05, bright=8),
    "arp":     dict(w="pulse12.5", a=0.002, d=0.07, s=0.25, r=0.04, bright=18),
    "arp25":   dict(w="pulse25", a=0.002, d=0.09, s=0.2, r=0.04, bright=14),
    "pluck":   dict(w="saw", a=0.002, d=0.28, s=0.0, r=0.06, bright=10),
    "pad":     dict(w="saw", a=0.35, d=0.4, s=0.75, r=0.5, bright=6, det=(0.993, 1.007)),
    "strings": dict(w="saw", a=0.18, d=0.3, s=0.8, r=0.35, bright=9, det=(0.995, 1.005), vib=(5.0, 0.006, 0.3)),
    "choir":   dict(w="choir", a=0.28, d=0.3, s=0.85, r=0.45, bright=24, det=(0.996, 1.004), vib=(5.2, 0.012, 0.15)),
    "organ":   dict(w="organ", a=0.02, d=0.1, s=0.9, r=0.12, bright=12, det=(0.998, 1.002)),
    "bell":    dict(w="bell"),
    "piano":   dict(w="piano"),
    "sine":    dict(w="sine", a=0.01, d=0.2, s=0.7, r=0.15, bright=1),
    "flute":   dict(w="tri", a=0.05, d=0.1, s=0.8, r=0.12, vib=(5.0, 0.012, 0.25), bright=6),
    "reed":    dict(w="reed", a=0.02, d=0.1, s=0.75, r=0.08, vib=(5.5, 0.01, 0.2), bright=16),
    "glitch":  dict(w="pulse12.5", a=0.001, d=0.05, s=0.5, r=0.02, bright=40),
}


def render_note(inst_name, midi, dur_s, vel=1.0):
    ins = INST[inst_name]
    f = midi_freq(midi)
    n_on = max(1, int(dur_s * SR))
    w = ins["w"]
    if w == "bell":
        n = n_on + int(1.2 * SR)
        t = np.arange(n) / SR
        y = (np.sin(2 * np.pi * f * t) * np.exp(-t * 3.0)
             + 0.45 * np.sin(2 * np.pi * f * 2.0 * t) * np.exp(-t * 5.0)
             + 0.25 * np.sin(2 * np.pi * f * 3.01 * t) * np.exp(-t * 8.0)
             + 0.18 * np.sin(2 * np.pi * f * 5.43 * t) * np.exp(-t * 11.0))
        y *= np.minimum(1.0, t * 400)
        return (y * 0.6 * vel).astype(np.float32)
    if w == "piano":
        n = n_on + int(0.6 * SR)
        t = np.arange(n) / SR
        dec = np.exp(-t * (1.6 + f / 900.0))
        y = (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 2)
             + 0.25 * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t * 4) + 0.12 * np.sin(2 * np.pi * 4.01 * f * t) * np.exp(-t * 6))
        rel = np.ones(n)
        if n_on < n:
            rel[n_on:] = np.exp(-(t[n_on:] - t[n_on]) * 9)
        y = y * dec * rel * np.minimum(1.0, t * 600)
        return (y * 0.55 * vel).astype(np.float32)
    env = env_adsr(n_on, ins["a"], ins["d"], ins["s"], ins["r"])
    n = len(env)
    fm = None
    if "vib" in ins:
        rate, depth, delay = ins["vib"]
        t = np.arange(n) / SR
        ramp = np.clip((t - delay) / 0.15, 0, 1)
        fm = 1.0 + depth * ramp * np.sin(2 * np.pi * rate * t)
    bright = ins.get("bright", 32)
    if "det" in ins:
        y = np.zeros(n, dtype=np.float32)
        for k, dt in enumerate(ins["det"]):
            y += osc(w, f * dt, n, bright, fm, phase0=k * 0.31)
        y *= 0.6
    else:
        y = osc(w, f, n, bright, fm)
    return (y * env * vel).astype(np.float32)


# ---------------------------------------------------------------- ударные
_DRUMS = {}


def _mk_drums():
    if _DRUMS:
        return _DRUMS
    def t_(sec):
        return np.arange(int(sec * SR)) / SR
    t = t_(0.35)
    f = 48 + 120 * np.exp(-t * 32)
    ph = np.cumsum(f) / SR
    kick = np.sin(2 * np.pi * ph) * np.exp(-t * 8.5)
    kick[:60] += np.linspace(0.6, 0, 60)
    _DRUMS["k"] = (np.tanh(kick * 1.6) * 0.95).astype(np.float32)
    t = t_(0.25)
    nz = smooth(noise(len(t), 1), 2)
    sn = nz * np.exp(-t * 20) * 0.75 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 28) * 0.5
    _DRUMS["s"] = sn.astype(np.float32)
    t = t_(0.06)
    hn = noise(len(t), 2)
    hn = np.diff(hn, prepend=0)
    _DRUMS["h"] = (hn * np.exp(-t * 85) * 0.35).astype(np.float32)
    t = t_(0.3)
    hn = np.diff(noise(len(t), 3), prepend=0)
    _DRUMS["o"] = (hn * np.exp(-t * 12) * 0.25).astype(np.float32)
    t = t_(0.3)
    cl = np.zeros(len(t))
    nz = smooth(noise(len(t), 4), 3)
    for off in (0.0, 0.011, 0.022):
        m = t >= off
        cl[m] += nz[m] * np.exp(-(t[m] - off) * 60)
    cl += nz * np.exp(-t * 14) * 0.4
    _DRUMS["c"] = (cl * 0.5).astype(np.float32)
    for name, fr in (("t", 110), ("T", 80)):
        t = t_(0.35)
        f = fr + 60 * np.exp(-t * 20)
        _DRUMS[name] = (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) * 0.7).astype(np.float32)
    t = t_(1.6)
    cr = np.diff(noise(len(t), 5), prepend=0) * 0.6 + smooth(noise(len(t), 6), 2) * 0.3
    _DRUMS["x"] = (cr * np.exp(-t * 2.6) * 0.32).astype(np.float32)
    # "сердцебиение"
    t = t_(0.3)
    f = 40 + 40 * np.exp(-t * 25)
    _DRUMS["b"] = (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11) * 0.9).astype(np.float32)
    # "тик часов"
    t = t_(0.04)
    _DRUMS["i"] = (np.sin(2 * np.pi * 2400 * t) * np.exp(-t * 160) * 0.3).astype(np.float32)
    return _DRUMS


# ---------------------------------------------------------------- аккорды
_QUAL = {
    "": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "m7": (0, 3, 7, 10), "maj7": (0, 4, 7, 11),
    "dim": (0, 3, 6), "aug": (0, 4, 8), "sus4": (0, 5, 7), "sus2": (0, 2, 7), "5": (0, 7),
    "m6": (0, 3, 7, 9), "6": (0, 4, 7, 9), "dim7": (0, 3, 6, 9), "add9": (0, 4, 7, 14), "madd9": (0, 3, 7, 14),
}


def parse_chord(name):
    name = name.strip()
    root = _NOTE_BASE[name[0].lower()]
    i = 1
    if i < len(name) and name[i] in "#b":
        root += 1 if name[i] == "#" else -1
        i += 1
    q = name[i:]
    bass = None
    if "/" in q:
        q, b = q.split("/")
        bass = _NOTE_BASE[b[0].lower()] + (1 if b[1:2] == "#" else -1 if b[1:2] == "b" else 0)
    ivs = _QUAL.get(q, (0, 4, 7))
    return root % 12, ivs, (bass % 12 if bass is not None else root % 12)


def chord_bar_list(chords):
    """'Am F | C G' -> список (на каждый такт) списков (аккорд, доля_старт, доля_длина)"""
    out = []
    for bar in chords.split("|"):
        bar = bar.strip()
        if not bar:
            continue
        for b in bar.split():
            parts = b.split(",")
            seg = []
            for k, p in enumerate(parts):
                seg.append((parse_chord(p), k * 16 // len(parts), 16 // len(parts)))
            out.append(seg)
    return out


# ---------------------------------------------------------------- рендер трека
DRUM_STYLES = {
    "none": {},
    "basic": {"k": "x.......x.......", "s": "....x.......x...", "h": "x.x.x.x.x.x.x.x."},
    "rock":  {"k": "x.....x.x.......", "s": "....x.......x...", "h": "x.x.x.x.x.x.x.x."},
    "drive": {"k": "x...x...x...x...", "s": "....x.......x...", "h": "xxxxxxxxxxxxxxxx"},
    "fast":  {"k": "x..x..x.x..x..x.", "s": "....x.......x..x", "h": "x.x.x.x.x.x.x.x.", "o": "..............x."},
    "metal": {"k": "xxxxxxxxxxxxxxxx", "s": "....x.......x...", "h": "x.x.x.x.x.x.x.x."},
    "halftime": {"k": "x.........x.....", "s": "........x.......", "h": "x...x...x...x..."},
    "shuffle": {"k": "x.....x.x.....x.", "s": "....x.......x...", "h": "x..x.xx..x.xx..x"},
    "disco": {"k": "x...x...x...x...", "c": "....x.......x...", "o": "..x...x...x...x."},
    "heart": {"b": "x..x............"},
    "tick":  {"i": "x...x...x...x...", "k": "x.......x......."},
    "march": {"k": "x...x...x...x...", "s": "..x...x..xx.x.x.", "h": "x.x.x.x.x.x.x.x."},
    "trap":  {"k": "x......x..x.....", "c": "....x.......x...", "h": "x.xxx.x.x.xxx.xx"},
    "breaks": {"k": "x.........x.....", "s": "....x..x.x..x...", "h": "x.x.x.x.x.x.x.x."},
    "waltz": {"k": "x...........", "h": "....x...x..."},
    "softhat": {"h": "..x...x...x...x."},
    "pumpk": {"k": "x...x...x...x...", "h": "..x...x...x...x."},
}


def _parse_track_line(line):
    """Строка-трекер: ноты по шагам. '-' продлить, '.' пауза."""
    toks = line.split()
    events = []  # (step_idx, len_steps, midi)
    cur = None
    for i, tk in enumerate(toks):
        if tk == "-":
            if cur is not None:
                cur[1] += 1
            continue
        if cur is not None:
            events.append(tuple(cur))
            cur = None
        if tk == "." or tk == "r":
            continue
        cur = [i, 1, note_midi(tk)]
    if cur is not None:
        events.append(tuple(cur))
    return events, len(toks)


def _echo(buf, d, fb, mix, taps=4):
    out = buf.copy()
    if d <= 0:
        return out
    n = len(buf)
    g = mix
    for k in range(1, taps + 1):
        sh = d * k
        if sh >= n:
            break
        out[sh:] += buf[:-sh] * g
        g *= fb
    return out


def expand_spec(spec):
    """Форма песни: A, A' (с "блеском" сверху), брейкдаун на пол-куплета."""
    if not spec.get("expand", True) or not spec.get("chords"):
        return spec
    bars = len(chord_bar_list(spec["chords"]))
    half = max(2, bars // 2)
    chs = [c.strip() for c in spec["chords"].split("|") if c.strip()]
    new = dict(spec)
    new["chords"] = " | ".join(chs + chs + chs[:half])
    new["bars"] = bars * 2 + half
    parts = []
    first_lead = True
    for p in spec["parts"]:
        b0, b1 = p.get("bars", (0, bars))
        t = p["type"]
        if t == "notes":
            a = dict(p); a["bars"] = (b0, b1); parts.append(a)
            b = dict(p); b["bars"] = (bars + b0, bars + b1); parts.append(b)
            if first_lead:
                first_lead = False
                c = dict(p); c["bars"] = (bars + b0, bars + b1)
                c["inst"] = "bell" if p.get("inst") != "bell" else "lead12"
                c["tr"] = p.get("tr", 0) + 12
                c["vol"] = p.get("vol", 0.3) * 0.38
                c["pan"] = -p.get("pan", 0.0) - 0.25
                parts.append(c)
        elif t == "drums":
            a = dict(p); a["bars"] = (b0, b1); parts.append(a)
            b = dict(p); b["bars"] = (bars + b0, bars + b1); parts.append(b)
            st = p.get("style", "basic")
            if st not in ("none",):
                c = dict(p); c["bars"] = (2 * bars, 2 * bars + half)
                c["style"] = st if st in ("heart", "tick", "softhat") else "softhat"
                c["crash"] = False
                parts.append(c)
        else:
            a = dict(p); a["bars"] = (b0, b1); parts.append(a)
            b = dict(p); b["bars"] = (bars + b0, bars + b1); parts.append(b)
            if t != "stab":
                lo, hi = max(b0, 0), min(b1, half)
                if hi > lo:
                    c = dict(p); c["bars"] = (2 * bars + lo, 2 * bars + hi)
                    if t == "arp":
                        c["vol"] = p.get("vol", 0.1) * 1.5
                    parts.append(c)
    new["parts"] = parts
    return new


def render_track(spec):
    """spec: dict(bpm, chords, bars, parts=[...]) -> int16 stereo"""
    spec = expand_spec(spec)
    drums = _mk_drums()
    bpm = spec["bpm"]
    step_s = 60.0 / bpm / 4.0
    steps_per_bar = spec.get("spb", 16)
    chords = chord_bar_list(spec["chords"]) if spec.get("chords") else []
    bars = spec.get("bars", len(chords))
    if chords and len(chords) < bars:
        chords = (chords * (bars // len(chords) + 1))[:bars]
    total_steps = bars * steps_per_bar
    N = int(round(total_steps * step_s * SR))
    tail = int(SR * 2.5)
    L = np.zeros(N + tail, dtype=np.float32)
    R = np.zeros(N + tail, dtype=np.float32)
    swing = spec.get("swing", 0.0)

    def step_t(st):
        s = st * step_s
        if swing and st % 2 == 1:
            s += swing * step_s
        return int(s * SR)

    for part in spec["parts"]:
        kind = part["type"]
        buf = np.zeros(N + tail, dtype=np.float32)
        vol = part.get("vol", 0.3)
        b0, b1 = part.get("bars", (0, bars))
        events = []  # (step, len, midi, vel)
        if kind == "notes":
            lines = part["notes"]
            if isinstance(lines, str):
                lines = [lines]
            step = part.get("step", 1)
            pos = b0 * steps_per_bar
            rep = part.get("repeat", 1)
            for _ in range(rep):
                for ln in lines:
                    evs, ln_len = _parse_track_line(ln)
                    for (si, sl, m) in evs:
                        events.append((pos + si * step, sl * step, m + part.get("tr", 0), 1.0))
                    pos += ln_len * step
        elif kind in ("bass", "arp", "pad", "stab", "counter"):
            style = part.get("style", "pump")
            octv = part.get("oct", 2 if kind == "bass" else 4)
            for bi in range(b0, min(b1, bars)):
                if not chords:
                    break
                for (root, ivs, bassn), st0, slen in chords[bi]:
                    base = 12 * (octv + 1) + root
                    bstep = bi * steps_per_bar + st0
                    if kind == "bass":
                        bn = 12 * (octv + 1) + bassn
                        if style == "long":
                            events.append((bstep, slen, bn, 1.0))
                        elif style == "pump":
                            for s in range(0, slen, 2):
                                events.append((bstep + s, 2, bn + (12 if s % 8 == 6 else 0), 0.9 if s % 4 else 1.0))
                        elif style == "drive":
                            for s in range(0, slen):
                                events.append((bstep + s, 1, bn + (12 if s % 4 == 2 else 0), 0.75 if s % 2 else 1.0))
                        elif style == "octave":
                            for s in range(0, slen, 2):
                                events.append((bstep + s, 2, bn + (12 if (s // 2) % 2 else 0), 1.0))
                        elif style == "walk":
                            seq = [0, ivs[1], ivs[2], ivs[1] if len(ivs) < 4 else ivs[3]]
                            for k, s in enumerate(range(0, slen, 4)):
                                events.append((bstep + s, 4, bn + seq[k % 4] - (12 if seq[k % 4] > 9 else 0), 1.0))
                        elif style == "gallop":
                            for s in range(0, slen, 4):
                                events.append((bstep + s, 2, bn, 1.0))
                                events.append((bstep + s + 2, 1, bn, 0.8))
                                events.append((bstep + s + 3, 1, bn + 12, 0.8))
                        elif style == "sync":
                            for s in (0, 3, 6, 10, 12):
                                if s < slen:
                                    events.append((bstep + s, 2, bn + (7 if s == 10 else 0), 1.0))
                        elif style == "half":
                            for s in range(0, slen, 8):
                                events.append((bstep + s, 6, bn, 1.0))
                        elif style == "heart":
                            events.append((bstep, 2, bn, 1.0))
                            if slen > 3:
                                events.append((bstep + 3, 3, bn, 0.7))
                    elif kind == "arp":
                        tones = [base + iv for iv in ivs] + [base + 12 + iv for iv in ivs]
                        if style == "up16":
                            seq = tones
                            for s in range(slen):
                                events.append((bstep + s, 1, seq[s % len(seq)], 1.0 if s % 4 == 0 else 0.75))
                        elif style == "updown":
                            seq = tones + tones[-2:0:-1]
                            for s in range(slen):
                                events.append((bstep + s, 1, seq[s % len(seq)], 1.0 if s % 4 == 0 else 0.7))
                        elif style == "alberti":
                            seq = [base, base + ivs[2], base + ivs[1], base + ivs[2]]
                            for s in range(0, slen, 2):
                                events.append((bstep + s, 2, seq[(s // 2) % 4] + 12, 0.9))
                        elif style == "up8":
                            for k, s in enumerate(range(0, slen, 2)):
                                events.append((bstep + s, 2, tones[k % len(tones)], 0.9))
                        elif style == "broken":
                            seq = [tones[0], tones[2], tones[1], tones[3 % len(tones)], tones[2], tones[1]]
                            for k, s in enumerate(range(0, slen, 2)):
                                events.append((bstep + s, 3, seq[k % len(seq)], 0.85))
                        elif style == "waltz":
                            for k, s in enumerate(range(0, slen, 4)):
                                if k % 3 == 0:
                                    continue
                                for iv in ivs[:3]:
                                    events.append((bstep + s, 3, base + iv + 12, 0.5))
                    elif kind == "pad":
                        for iv in ivs[:4]:
                            m = base + iv
                            events.append((bstep, slen, m, 0.8))
                    elif kind == "stab":
                        pat = part.get("pat", "..x...x...x...x.")
                        for s in range(slen):
                            if pat[(st0 + s) % len(pat)] == "x":
                                for iv in ivs[:3]:
                                    events.append((bstep + s, 1, base + iv, 0.8))
        elif kind == "drums":
            style = DRUM_STYLES[part.get("style", "basic")]
            fills = part.get("fill", True)
            for bi in range(b0, min(b1, bars)):
                patt = style
                if fills and (bi % 4 == 3) and part.get("style") not in ("heart", "tick", "none", "softhat"):
                    patt = dict(style)
                    patt["s"] = style.get("s", "....x.......x...")[:8] + "x.xxx.xx"[:8]
                    patt["t"] = "............x..."
                    patt["T"] = "..............x."
                for dn, pat in patt.items():
                    for s, ch in enumerate(pat):
                        if ch == "x" and s < steps_per_bar:
                            st = bi * steps_per_bar + s
                            p = step_t(st)
                            smp = drums[dn]
                            e = min(len(buf), p + len(smp))
                            buf[p:e] += smp[:e - p] * (0.9 if dn != "h" or s % 4 == 0 else 0.65)
                if part.get("crash", True) and bi % 8 == 0:
                    p = step_t(bi * steps_per_bar)
                    smp = drums["x"]
                    e = min(len(buf), p + len(smp))
                    buf[p:e] += smp[:e - p]
        # отрисовка нот
        if events:
            inst = part.get("inst", "lead")
            gate = part.get("gate", 0.92)
            for (st, ln, m, v) in events:
                if st >= total_steps:
                    continue
                p = step_t(st)
                y = render_note(inst, m, ln * step_s * gate, v)
                e = min(len(buf), p + len(y))
                buf[p:e] += y[:e - p]
        buf *= vol
        if "echo" in part:
            ds, fb, mx = part["echo"]
            buf = _echo(buf, int(ds * step_s * SR), fb, mx)
        pan = part.get("pan", 0.0)
        lg = math.cos((pan + 1) * math.pi / 4) * 1.414
        rg = math.sin((pan + 1) * math.pi / 4) * 1.414
        if part.get("wide"):
            d = int(0.013 * SR)
            L += buf * lg
            R[d:] += buf[:-d] * rg
        else:
            L += buf * lg
            R += buf * rg
    # "комната"
    rv = spec.get("reverb", 0.18)
    if rv > 0:
        for d_ms, g in ((29, 0.5), (43, 0.4), (61, 0.33), (83, 0.27), (113, 0.2), (151, 0.14), (197, 0.1)):
            d = int(d_ms / 1000 * SR)
            L2 = np.zeros_like(L)
            R2 = np.zeros_like(R)
            L2[d:] = R[:-d] * g
            R2[d:] = L[:-d] * g
            L += L2 * rv
            R += R2 * rv
    # бесшовный луп: хвост на начало
    L[:tail] += L[N:N + tail]
    R[:tail] += R[N:N + tail]
    L = L[:N]
    R = R[:N]
    st = np.stack([L, R], axis=1)
    peak = np.percentile(np.abs(st), 99.9) + 1e-6
    st = st / peak * 0.8
    st = np.tanh(st * 1.15) / np.tanh(1.15)
    st *= spec.get("gain", 0.85)
    return (np.clip(st, -1, 1) * 32000).astype(np.int16)


# ============================================================================
#                          ЗВУКОВЫЕ ЭФФЕКТЫ
# ============================================================================
def _t(sec):
    return np.arange(int(sec * SR)) / SR


def _sweep(f0, f1, sec, kind="sine", curve=1.0, bright=12):
    n = int(sec * SR)
    k = np.linspace(0, 1, n) ** curve
    f = f0 * (f1 / f0) ** k
    ph = np.cumsum(f) / SR
    nh = _nh_for(max(f0, f1), bright)
    tbl = _wavetable(kind, nh)
    return tbl[(ph * TABN).astype(np.int64) & (TABN - 1)]


def make_sfx():
    S = {}
    t = _t(0.12)
    S["shoot"] = _sweep(520, 210, 0.12, "sine") * np.exp(-t * 26) * 0.6 + smooth(noise(len(t), 7), 6) * np.exp(-t * 60) * 0.25
    t = _t(0.16)
    S["splash"] = smooth(noise(len(t), 8), 4) * np.exp(-t * 30) * 0.45 + _sweep(300, 120, 0.16, "sine") * np.exp(-t * 25) * 0.2
    t = _t(0.32)
    gr = _sweep(330, 140, 0.32, "saw", bright=10) * (1 + 0.4 * np.sin(2 * np.pi * 32 * t))
    S["hurt"] = np.tanh(gr * 1.4) * np.exp(-t * 6) * 0.5 + smooth(noise(len(t), 9), 3) * np.exp(-t * 25) * 0.25
    t = _t(0.08)
    S["hit"] = smooth(noise(len(t), 10), 2) * np.exp(-t * 60) * 0.35 + np.sin(2 * np.pi * 180 * t) * np.exp(-t * 50) * 0.3
    t = _t(0.35)
    S["die"] = smooth(noise(len(t), 11), 5) * np.exp(-t * 12) * 0.5 + _sweep(240, 50, 0.35, "tri") * np.exp(-t * 8) * 0.45
    t = _t(1.1)
    ex = smooth(noise(len(t), 12), 3) * np.exp(-t * 4.5) + np.sin(2 * np.pi * np.cumsum(40 + 80 * np.exp(-t * 10)) / SR) * np.exp(-t * 5) * 1.2
    S["explode"] = np.tanh(ex * 1.5) * 0.75
    a = _sweep(1976, 1976, 0.06, "pulse50", bright=6) * 0.3
    b = _sweep(2637, 2637, 0.22, "pulse50", bright=6) * np.exp(-_t(0.22) * 12) * 0.3
    S["coin"] = np.concatenate([a, b])
    t = _t(0.35)
    S["key"] = (np.sin(2 * np.pi * 2200 * t) + 0.5 * np.sin(2 * np.pi * 3310 * t)) * np.exp(-t * 14) * 0.3
    S["heart"] = np.concatenate([_sweep(440, 660, 0.08, "tri") * 0.4, _sweep(660, 880, 0.18, "tri") * np.exp(-_t(0.18) * 10) * 0.4])
    t = _t(0.18)
    S["bombpick"] = _sweep(200, 400, 0.18, "pulse25", bright=8) * np.exp(-t * 9) * 0.35
    t = _t(0.25)
    S["door"] = np.sin(2 * np.pi * np.cumsum(90 * np.exp(-t * 3)) / SR) * np.exp(-t * 14) * 0.6 + smooth(noise(len(t), 13), 6) * np.exp(-t * 30) * 0.3
    S["unlock"] = np.concatenate([S["key"][:2000], _sweep(800, 1600, 0.1, "pulse25", bright=6) * 0.2])
    # предмет: светлый хоровой аккорд
    t = _t(1.6)
    ch = np.zeros(len(t))
    for i, m in enumerate((60, 64, 67, 72, 76)):
        f = midi_freq(m + 12)
        ch += osc("choir", f, len(t), 24, 1 + 0.01 * np.sin(2 * np.pi * 5 * t)) * np.clip((t - i * 0.06) * 6, 0, 1)
    S["item"] = ch / 5 * np.exp(-t * 1.6) * 0.55
    t = _t(0.7)
    S["bad"] = (osc("saw", 110, len(t), 8) + osc("saw", 116.5, len(t), 8)) * np.exp(-t * 3) * 0.3
    t = _t(0.5)
    S["fuse"] = np.diff(noise(len(t), 14), prepend=0) * 0.12 * (0.6 + 0.4 * np.sin(2 * np.pi * 30 * t))
    t = _t(0.05)
    S["menu"] = np.sin(2 * np.pi * 900 * t) * np.exp(-t * 60) * 0.3
    t = _t(0.12)
    S["select"] = np.concatenate([np.sin(2 * np.pi * 700 * _t(0.05)) * 0.3, np.sin(2 * np.pi * 1050 * t) * np.exp(-t * 25) * 0.3])
    t = _t(0.9)
    S["roar"] = np.tanh((osc("saw", 70, len(t), 10, 1 + 0.15 * np.sin(2 * np.pi * 9 * t)) + smooth(noise(len(t), 15), 8)) * 1.8) * np.exp(-t * 2.2) * 0.5
    t = _t(0.6)
    S["laser"] = (osc("saw", 160, len(t), 24, 1 + 0.05 * np.sin(2 * np.pi * 60 * t)) * 0.5 + smooth(noise(len(t), 16), 2) * 0.2) * np.clip(t * 30, 0, 1) * np.exp(-t * 3) * 0.45
    t = _t(0.35)
    S["warn"] = osc("pulse50", 880, len(t), 6) * (np.sin(2 * np.pi * 14 * t) > 0) * np.exp(-t * 3) * 0.18
    t = _t(2.2)
    dm = np.zeros(len(t))
    for m in (36, 43, 48, 55, 60, 63):
        dm += osc("saw", midi_freq(m), len(t), 10)
    S["domain"] = np.tanh((dm / 3 * np.clip(t * 4, 0, 1) * np.exp(-t * 1.2) + smooth(noise(len(t), 17), 4) * np.exp(-t * 3) * 0.6) * 1.4) * 0.6
    t = _t(0.45)
    mf = 1 + 0.35 * np.sin(np.clip(t / 0.45, 0, 1) * np.pi) + 0.02 * np.sin(2 * np.pi * 7 * t)
    S["meow"] = osc("reed", 620, len(t), 10, mf) * np.sin(np.clip(t / 0.45, 0, 1) * np.pi) * 0.4
    t = _t(0.5)
    S["fire"] = smooth(noise(len(t), 18), 3) * (0.5 + 0.5 * np.abs(np.sin(2 * np.pi * 11 * t))) * np.exp(-t * 4) * 0.35
    S["teleport"] = _sweep(200, 2000, 0.5, "pulse25", curve=2, bright=10) * np.exp(-_t(0.5) * 2) * 0.25
    t = _t(1.2)
    sh = np.zeros(len(t))
    rs = np.random.RandomState(19)
    for _ in range(14):
        st = rs.uniform(0, 0.4)
        f = rs.uniform(2500, 6000)
        m = t >= st
        sh[m] += np.sin(2 * np.pi * f * (t[m] - st)) * np.exp(-(t[m] - st) * 18) * 0.25
    sh += np.diff(noise(len(t), 20), prepend=0) * np.exp(-t * 7) * 0.4
    S["shatter"] = sh * 0.6
    t = _t(0.5)
    S["gun"] = np.tanh((smooth(noise(len(t), 21), 2) * np.exp(-t * 18) * 2 + np.sin(2 * np.pi * np.cumsum(120 * np.exp(-t * 8)) / SR) * np.exp(-t * 10)) * 2) * 0.7
    t = _t(2.0)
    an = np.zeros(len(t))
    for m in (72, 76, 79, 84, 88):
        an += osc("choir", midi_freq(m), len(t), 24, 1 + 0.008 * np.sin(2 * np.pi * 5.5 * t))
    S["angel"] = an / 5 * np.clip(t * 2, 0, 1) * np.exp(-t * 1.0) * 0.6
    t = _t(0.25)
    S["sword"] = smooth(noise(len(t), 22), 2) * np.sin(np.clip(t / 0.25, 0, 1) * np.pi) * 0.4 + _sweep(900, 300, 0.25, "saw", bright=6) * np.exp(-t * 10) * 0.12
    t = _t(0.4)
    S["charge"] = np.concatenate([_sweep(523, 523, 0.08, "pulse25", bright=8) * 0.25, _sweep(784, 784, 0.08, "pulse25", bright=8) * 0.25, _sweep(1046, 1046, 0.2, "pulse25", bright=8) * np.exp(-_t(0.2) * 8) * 0.25])
    t = _t(0.3)
    S["shrink"] = _sweep(1500, 300, 0.3, "tri") * 0.35
    S["grow"] = _sweep(300, 1500, 0.3, "tri") * 0.35
    t = _t(0.18)
    S["pickup"] = _sweep(600, 1200, 0.18, "pulse25", bright=8) * np.exp(-t * 8) * 0.25
    t = _t(0.6)
    S["dodge"] = smooth(noise(len(t), 23), 3) * np.exp(-t * 14) * 0.3 + _sweep(1200, 600, 0.6, "sine") * np.exp(-t * 9) * 0.15
    t = _t(0.15)
    S["blip"] = np.sin(2 * np.pi * 1300 * t) * np.exp(-t * 40) * 0.2
    t = _t(1.4)
    S["rays"] = np.tanh((osc("saw", 55, len(t), 12) + osc("saw", 82.5, len(t), 12) + smooth(noise(len(t), 24), 2) * 0.8) * 1.2) * np.clip(t * 3, 0, 1) * np.exp(-t * 1.5) * 0.5
    t = _t(0.7)
    S["slam"] = np.tanh((np.sin(2 * np.pi * np.cumsum(55 + 60 * np.exp(-t * 12)) / SR) * 1.5 + smooth(noise(len(t), 25), 6) * 0.6) * np.exp(-t * 6) * 1.5) * 0.7
    S["boss_die"] = np.concatenate([S["roar"], S["explode"]])
    t = _t(0.6)
    S["card"] = smooth(noise(len(t), 26), 2) * np.exp(-t * 30) * 0.3 + _sweep(400, 1600, 0.6, "pulse12.5", bright=8) * np.exp(-t * 4) * 0.15
    t = _t(0.3)
    S["poop"] = smooth(noise(len(t), 27), 10) * np.exp(-t * 15) * 0.6 + _sweep(160, 70, 0.3, "sine") * np.exp(-t * 12) * 0.4
    t = _t(0.25)
    S["rock"] = smooth(noise(len(t), 28), 4) * np.exp(-t * 18) * 0.6
    t = _t(1.0)
    S["heartbeat"] = np.zeros(len(t))
    # джинглы
    S["fanfare"] = _jingle([(67, 0.12), (72, 0.12), (76, 0.12), (79, 0.3), (76, 0.12), (79, 0.6)], "lead")
    S["gameover"] = _jingle([(64, 0.35), (63, 0.35), (62, 0.35), (61, 1.2)], "lead50", slow=True)
    S["secret"] = _jingle([(79, 0.1), (78, 0.1), (75, 0.1), (69, 0.1), (68, 0.1), (76, 0.1), (80, 0.1), (84, 0.4)], "lead12")
    S["ending"] = _jingle([(60, 0.3), (64, 0.3), (67, 0.3), (72, 1.4)], "bell")
    out = {}
    for k, v in S.items():
        out[k] = np.asarray(v, dtype=np.float32)
    return out


def _jingle(notes, inst, slow=False):
    parts = []
    for m, d in notes:
        y = render_note(inst, m, d * 0.9, 0.8)
        parts.append((y, int(d * SR)))
    total = sum(p[1] for p in parts) + SR
    buf = np.zeros(total, dtype=np.float32)
    pos = 0
    for y, d in parts:
        e = min(total, pos + len(y))
        buf[pos:e] += y[:e - pos]
        pos += d
    return buf * 0.5


VOICES = {
    # имя: (волна, частота, разброс)
    "artem": ("pulse25", 520, 40), "kostya": ("pulse50", 420, 30), "valerii": ("saw", 180, 20),
    "dymok": ("reed", 700, 120), "jesus": ("choir", 330, 15), "sergei": ("pulse25", 300, 30),
    "john": ("saw", 150, 15), "unknown": ("sine", 240, 60), "ellen": ("tri", 620, 50),
    "gaster": ("pulse12.5", 140, 200), "daniil": ("pulse50", 260, 20), "narr": ("tri", 400, 0),
    "rak": ("pulse12.5", 900, 100), "item": ("tri", 700, 20),
}


def make_voice(kind, f):
    t = _t(0.055)
    y = osc(kind, f, len(t), 10 if kind != "sine" else 1) * np.exp(-t * 35) * np.clip(t * 900, 0, 1)
    return y * 0.25


class Audio:
    def __init__(self):
        self.ok = False
        self.sfx = {}
        self.voices = {}
        self.music_name = None
        self.pending = None
        self.pending_t = 0
        self.music_on = True
        self.ready = set()
        self.rendering = set()
        self.lock = threading.Lock()
        self.cache_dir = os.path.join(SAVE_DIR, "music_cache")
        self._mem = {}
        self.progress = (0, 1)
        self.last_play = {}
        try:
            pygame.mixer.pre_init(SR, -16, 2, 512)
            pygame.mixer.init(SR, -16, 2, 512)
            pygame.mixer.set_num_channels(40)
            self.ok = True
        except Exception as e:
            print("Нет звука:", e)

    def init_sfx(self):
        if not self.ok:
            return
        raw = make_sfx()
        for k, v in raw.items():
            self.sfx[k] = self._mk(v)
        for name, (kind, f, spread) in VOICES.items():
            arr = []
            for i in range(4):
                ff = f + (i - 1.5) * spread / 2
                arr.append(self._mk(make_voice(kind, max(60, ff))))
            self.voices[name] = arr

    def _mk(self, mono):
        a = np.clip(mono, -1, 1)
        st = np.stack([a, a], axis=1)
        return pygame.sndarray.make_sound((st * 30000).astype(np.int16).copy(order="C"))

    def play(self, name, vol=1.0, cool=0.03):
        if not self.ok:
            return
        s = self.sfx.get(name)
        if s is None:
            return
        now = time.time()
        if now - self.last_play.get(name, 0) < cool:
            return
        self.last_play[name] = now
        ch = s.play()
        if ch:
            ch.set_volume(vol * SAVE["sfx"])

    def voice(self, name):
        if not self.ok:
            return
        arr = self.voices.get(name) or self.voices["narr"]
        ch = random.choice(arr).play()
        if ch:
            ch.set_volume(0.7 * SAVE["sfx"])

    # ---------------- музыка
    def _spec_hash(self, name):
        spec = MUSIC.get(name)
        h = hashlib.md5((repr(spec) + "v3").encode("utf-8")).hexdigest()[:10]
        return h

    def _path(self, name):
        return os.path.join(self.cache_dir, "%s_%s.wav" % (name, self._spec_hash(name)))

    def _render_to_file(self, name):
        arr = render_track(MUSIC[name])
        bio = io.BytesIO()
        with wave.open(bio, "wb") as w:
            w.setnchannels(2)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(arr.tobytes())
        data = bio.getvalue()
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            p = self._path(name)
            with open(p + ".tmp", "wb") as f:
                f.write(data)
            os.replace(p + ".tmp", p)
        except Exception:
            self._mem[name] = data
        return True

    def ensure(self, name):
        if name in self.ready:
            return True
        if os.path.exists(self._path(name)) or name in self._mem:
            self.ready.add(name)
            return True
        while True:
            with self.lock:
                if name in self.ready:
                    return True
                if name not in self.rendering:
                    self.rendering.add(name)
                    break
            time.sleep(0.02)
        try:
            self._render_to_file(name)
        finally:
            with self.lock:
                self.rendering.discard(name)
                self.ready.add(name)
        return True

    def prefetch_all(self, first=()):
        if not self.ok:
            return
        names = list(first) + [n for n in MUSIC if n not in first]

        def work():
            done = 0
            for n in names:
                try:
                    self.ensure(n)
                except Exception as e:
                    print("music err", n, e)
                done += 1
                self.progress = (done, len(names))
        th = threading.Thread(target=work, daemon=True)
        th.start()

    def music(self, name, fade=600):
        if not self.ok:
            return
        if name == self.music_name and self.pending is None:
            return
        if name == self.pending:
            return
        self.music_name = name
        self.pending = name
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.fadeout(250)
            self.pending_t = time.time() + 0.26
        else:
            self.pending_t = 0

    def stop_music(self, fade=500):
        self.music_name = None
        self.pending = None
        if self.ok:
            pygame.mixer.music.fadeout(fade)

    def update(self):
        if not self.ok or self.pending is None:
            return
        if time.time() < self.pending_t:
            return
        name = self.pending
        self.pending = None
        if name is None or name not in MUSIC:
            return
        try:
            self.ensure(name)
            if name in self._mem:
                pygame.mixer.music.load(io.BytesIO(self._mem[name]))
            else:
                try:
                    pygame.mixer.music.load(self._path(name))
                except Exception:
                    with open(self._path(name), "rb") as f:
                        self._mem[name] = f.read()
                    pygame.mixer.music.load(io.BytesIO(self._mem[name]))
            pygame.mixer.music.set_volume(SAVE["music"] if self.music_on else 0)
            pygame.mixer.music.play(-1, fade_ms=500)
        except Exception as e:
            print("music play err", e)

    def toggle_music(self):
        self.music_on = not self.music_on
        if self.ok:
            pygame.mixer.music.set_volume(SAVE["music"] if self.music_on else 0)

# ============================================================================
#                            МУЗЫКА (композиции)
#  Мелодии записаны "трекером": каждый токен - шаг (по умолч. восьмая),
#  "-" продлить ноту, "." пауза.
# ============================================================================
def P(type_, **kw):
    kw["type"] = type_
    return kw


MUSIC = {}

# ---------------------------------------------------------------- Титульная
MUSIC["title"] = dict(bpm=76, reverb=0.3, expand=False, chords="Am | F | C | G | Am | F | E | E | Am | F | C | G | Dm | Am | E7 | Am", parts=[
    P("notes", inst="bell", vol=0.42, step=2, echo=(3, 0.45, 0.35), pan=0.1, notes=[
        "a4 - c5 e5 a5 - g5 e5", "f5 - e5 c5 a4 - c5 -", "e5 - d5 c5 g4 - c5 e5", "d5 - - - b4 - g4 -",
        "a4 - c5 e5 a5 - b5 c6", "b5 - a5 f5 c5 - f5 a5", "g#5 - - - e5 - b4 -", "e5 - - - - - . .",
        "c6 - b5 a5 e5 - a5 -", "a5 - g5 f5 c5 - f5 -", "g5 - f5 e5 c5 - e5 g5", "g5 - f5 d5 b4 - d5 -",
        "f5 - e5 d5 a4 - d5 f5", "e5 - c5 a4 e4 - a4 c5", "b4 - d5 g#4 b4 - e5 -", "a4 - - - - - - -"]),
    P("pad", inst="strings", vol=0.13, oct=3, wide=True),
    P("bass", inst="bass", style="long", oct=2, vol=0.3, bars=(8, 16)),
    P("arp", inst="pluck", style="broken", oct=3, vol=0.12, bars=(8, 16), pan=-0.3),
    P("pad", inst="choir", vol=0.08, oct=4, bars=(8, 16), wide=True),
    P("drums", style="softhat", vol=0.25, bars=(8, 16), crash=False),
])

# ---------------------------------------------------------------- Звонок / пролог
MUSIC["home"] = dict(bpm=96, swing=0.28, chords="C | Am | F | G | C | Am | Dm7 | G7", parts=[
    P("notes", inst="lead50", vol=0.24, step=2, echo=(3, 0.35, 0.3), notes=[
        "e5 - g5 - c6 - g5 e5", "a5 - - g5 e5 - c5 -", "f5 - a5 - c6 - a5 f5", "g5 - - - d5 - b4 -",
        "e5 - g5 - c6 - d6 e6", "e6 - d6 c6 a5 - c6 -", "d6 - c6 a5 f5 - a5 c6", "b5 - g5 - f5 - d5 -"]),
    P("bass", inst="bass", style="walk", oct=2, vol=0.42),
    P("arp", inst="pluck", style="alberti", oct=3, vol=0.14, pan=-0.35),
    P("stab", inst="piano", vol=0.12, oct=4, pat="..x...x...x...x.", pan=0.3),
    P("drums", style="shuffle", vol=0.3),
])

# ---------------------------------------------------------------- Этаж 1: Квартира
MUSIC["floor1"] = dict(bpm=112, reverb=0.25, chords="Dm | Dm | Bb | A | Dm | Dm | Gm | A | Bb | C | Dm | Dm | Bb | C | A | A", parts=[
    P("notes", inst="lead", vol=0.22, step=2, echo=(3, 0.4, 0.33), pan=0.15, notes=[
        "d5 - - a4 d5 - e5 f5", "e5 - d5 - a4 - - -", "f5 - - d5 f5 - g5 a5", "g5 - f5 - e5 - c#5 -",
        "d5 - - a4 d5 - e5 f5", "a5 - g5 f5 e5 - d5 -", "bb4 - d5 g5 f5 - e5 d5", "c#5 - - - e5 - a4 -",
        "f5 - - - d5 - bb4 -", "e5 - - - c5 - g4 -", "a5 - - - f5 - d5 -", "e5 f5 e5 d5 a4 - - -",
        "d6 - - - bb5 - f5 -", "c6 - - - g5 - e5 -", "a5 - g5 f5 e5 - c#5 -", "e5 - - - a4 - . ."]),
    P("bass", inst="sqbass", style="drive", oct=2, vol=0.3),
    P("arp", inst="arp", style="up16", oct=4, vol=0.08, echo=(3, 0.3, 0.3), pan=-0.4),
    P("pad", inst="pad", vol=0.09, oct=3, wide=True),
    P("drums", style="rock", vol=0.32),
])

# ---------------------------------------------------------------- Общий босс
MUSIC["boss"] = dict(bpm=150, chords="Em | C | D | B | Em | C | Am | B7", parts=[
    P("notes", inst="saw", vol=0.2, step=2, notes=[
        "e5 - e5 g5 b5 - a5 g5", "e5 - - g5 e5 - c5 -", "d5 - f#5 a5 d6 - c6 a5", "b5 - - - d#5 - f#5 -",
        "e6 - d6 b5 g5 - b5 d6", "c6 - b5 g5 e5 - g5 c6", "a5 - c6 a5 e5 - a5 c6", "b5 - a5 - f#5 - d#5 -"]),
    P("notes", inst="lead50", vol=0.1, step=2, tr=-12, pan=-0.3, notes=[
        "e5 - e5 g5 b5 - a5 g5", "e5 - - g5 e5 - c5 -", "d5 - f#5 a5 d6 - c6 a5", "b5 - - - d#5 - f#5 -",
        "e6 - d6 b5 g5 - b5 d6", "c6 - b5 g5 e5 - g5 c6", "a5 - c6 a5 e5 - a5 c6", "b5 - a5 - f#5 - d#5 -"]),
    P("bass", inst="sawbass", style="gallop", oct=2, vol=0.3),
    P("stab", inst="brass", vol=0.08, oct=4, pat="x..x..x...x..x..", pan=0.3),
    P("drums", style="fast", vol=0.35),
])

# ---------------------------------------------------------------- Валерий (ERII)
MUSIC["valerii"] = dict(bpm=164, chords="Cm | Ab | Bb | G | Cm | Ab | Fm | G", parts=[
    P("notes", inst="saw", vol=0.19, step=1, notes=[
        "c5 c5 c5 c5 eb5 - g5 - c6 - bb5 - g5 - eb5 -", "ab4 ab4 ab4 ab4 c5 - eb5 - ab5 - g5 - eb5 - c5 -",
        "bb4 bb4 bb4 bb4 d5 - f5 - bb5 - ab5 - f5 - d5 -", "b4 b4 b4 b4 d5 - g5 - b5 - - - g5 - d5 -",
        "g5 g5 g5 g5 c6 - - - bb5 - ab5 - g5 - eb5 -", "ab5 ab5 ab5 ab5 c6 - - - eb6 - c6 - ab5 - eb5 -",
        "f5 f5 f5 f5 ab5 - c6 - f6 - eb6 - c6 - ab5 -", "g5 - - - f5 - - - d5 - - - b4 - - -"]),
    P("bass", inst="sawbass", style="drive", oct=2, vol=0.3),
    P("pad", inst="brass", vol=0.1, oct=3, wide=True),
    P("drums", style="fast", vol=0.38),
])

# ---------------------------------------------------------------- Домейн Дымка
MUSIC["domain"] = dict(bpm=138, reverb=0.3, chords="Em | F | Em | F | Em | Dm | C | B", parts=[
    P("notes", inst="bell", vol=0.35, step=2, echo=(3, 0.4, 0.3), notes=[
        "e5 - b4 - e5 f5 e5 -", "f5 - c5 - f5 g5 f5 -", "g5 - f5 e5 b4 - - -", "a5 - g5 f5 c5 - - -",
        "e6 - - b5 - - g5 -", "f5 - - d5 - - a4 -", "e5 - - c5 - - g4 -", "f#5 - d#5 - b4 - a4 -"]),
    P("notes", inst="lead12", vol=0.1, step=2, tr=-12, pan=0.3, notes=[
        "e5 - b4 - e5 f5 e5 -", "f5 - c5 - f5 g5 f5 -", "g5 - f5 e5 b4 - - -", "a5 - g5 f5 c5 - - -",
        "e6 - - b5 - - g5 -", "f5 - - d5 - - a4 -", "e5 - - c5 - - g4 -", "f#5 - d#5 - b4 - a4 -"]),
    P("bass", inst="sqbass", style="drive", oct=2, vol=0.26),
    P("arp", inst="arp", style="updown", oct=4, vol=0.08, echo=(2, 0.3, 0.3), pan=-0.4),
    P("drums", style="trap", vol=0.33),
])

# ---------------------------------------------------------------- Рай
MUSIC["heaven"] = dict(bpm=84, reverb=0.4, chords="C | G/B | Am | Em/G | F | C/E | Dm7 | G", parts=[
    P("notes", inst="bell", vol=0.32, step=2, echo=(3, 0.4, 0.3), notes=[
        "e5 - - - g5 - c6 -", "b5 - - - d6 - g5 -", "c6 - b5 - a5 - e5 -", "g5 - - - - - . .",
        "a5 - - - c6 - f6 -", "e6 - - - c6 - g5 -", "f5 - e5 - d5 - a5 -", "g5 - - - - - . ."]),
    P("pad", inst="choir", vol=0.2, oct=4, wide=True),
    P("arp", inst="organ", style="broken", oct=3, vol=0.08, pan=-0.3),
    P("bass", inst="bass", style="long", oct=2, vol=0.3),
])

# ---------------------------------------------------------------- Школа
MUSIC["school"] = dict(bpm=128, chords="F | Dm | Bb | C | F | Dm | Gm7 | C7", parts=[
    P("notes", inst="lead12", vol=0.2, step=2, gate=0.55, echo=(3, 0.3, 0.25), notes=[
        "c5 f5 a5 f5 c6 - a5 -", "d5 f5 a5 f5 d6 - a5 -", "bb4 d5 f5 d5 bb5 - f5 -", "c5 e5 g5 e5 c6 - - -",
        "a5 - g5 f5 c5 - f5 a5", "a5 - g5 f5 d5 - f5 a5", "bb5 - a5 g5 d5 - f5 g5", "e5 - g5 - c6 - bb5 -"]),
    P("bass", inst="bass", style="octave", oct=2, vol=0.4),
    P("stab", inst="arp25", vol=0.1, oct=4, pat="..x...x...x...x.", pan=0.3),
    P("drums", style="disco", vol=0.3),
])

# ---------------------------------------------------------------- Лёгкие Серёги
MUSIC["lungs"] = dict(bpm=92, reverb=0.35, chords="Fm | Db | Bbm | C | Fm | Db | Bbm | C7", parts=[
    P("notes", inst="reed", vol=0.2, step=2, echo=(3, 0.45, 0.3), notes=[
        "c5 - - - - - ab4 -", "f5 - - - - - db5 -", "f5 - - - db5 - bb4 -", "c5 - - - e5 - - -",
        "ab5 - - - g5 - f5 -", "f5 - - - ab5 - db6 -", "c6 - - bb5 - - f5 -", "g5 - - - e5 - c5 -"]),
    P("bass", inst="bass", style="heart", oct=1, vol=0.5),
    P("pad", inst="pad", vol=0.12, oct=3, wide=True),
    P("arp", inst="lead12", style="up8", oct=4, vol=0.06, echo=(3, 0.5, 0.4), pan=-0.5),
    P("drums", style="heart", vol=0.5, crash=False),
])

# ---------------------------------------------------------------- Тёмная квартира
MUSIC["dark"] = dict(bpm=120, reverb=0.3, chords="Cm | Ab | Fm | G | Cm | Ab | Db | G", parts=[
    P("notes", inst="lead12", vol=0.2, step=2, echo=(3, 0.4, 0.3), notes=[
        "c5 - - eb5 g5 - - c6", "c6 - bb5 ab5 eb5 - - -", "f5 - ab5 c6 f6 - eb6 c6", "b5 - - - g5 - d5 -",
        "g5 - - - eb6 - - d6", "c6 - - - ab5 - eb5 -", "f5 - ab5 - db6 - c6 ab5", "b5 - g5 - d5 - b4 -"]),
    P("bass", inst="sqbass", style="pump", oct=2, vol=0.3),
    P("arp", inst="arp", style="up16", oct=4, vol=0.06, pan=-0.4),
    P("pad", inst="pad", vol=0.1, oct=3, wide=True),
    P("drums", style="tick", vol=0.35, crash=False),
])

# ---------------------------------------------------------------- Финал с отцом
MUSIC["final"] = dict(bpm=152, chords="Am | F | G | Em | Am | F | G | E | F | G | Am | Am | F | G | E | E", parts=[
    P("notes", inst="saw", vol=0.2, step=2, notes=[
        "a4 - c5 - e5 - a5 -", "c6 - - b5 a5 - f5 -", "g5 - - d5 g5 - b5 -", "e5 - - - b4 - e5 -",
        "a5 - - - e6 - - c6", "a5 - - - f5 - a5 c6", "d6 - c6 b5 g5 - b5 d6", "e6 - - - g#5 - b5 -",
        "c6 - - - a5 - f5 -", "d6 - - - b5 - g5 -", "e6 - - d6 c6 - b5 -", "a5 - - - - - e5 -",
        "f5 - a5 c6 f6 - e6 -", "d6 - b5 g5 d6 - e6 f6", "e6 - - - d6 - b5 -", "g#5 - - - b5 - e6 -"]),
    P("notes", inst="brass", vol=0.09, step=2, tr=-12, pan=-0.3, notes=[
        "a4 - c5 - e5 - a5 -", "c6 - - b5 a5 - f5 -", "g5 - - d5 g5 - b5 -", "e5 - - - b4 - e5 -",
        "a5 - - - e6 - - c6", "a5 - - - f5 - a5 c6", "d6 - c6 b5 g5 - b5 d6", "e6 - - - g#5 - b5 -",
        "c6 - - - a5 - f5 -", "d6 - - - b5 - g5 -", "e6 - - d6 c6 - b5 -", "a5 - - - - - e5 -",
        "f5 - a5 c6 f6 - e6 -", "d6 - b5 g5 d6 - e6 f6", "e6 - - - d6 - b5 -", "g#5 - - - b5 - e6 -"]),
    P("bass", inst="sawbass", style="gallop", oct=2, vol=0.3),
    P("pad", inst="choir", vol=0.1, oct=4, wide=True),
    P("arp", inst="arp", style="up16", oct=4, vol=0.06, pan=0.4),
    P("drums", style="fast", vol=0.36),
])

# ---------------------------------------------------------------- Тема отца
MUSIC["histheme"] = dict(bpm=70, reverb=0.4, chords="C | G/B | Am | Em/G | F | C/E | F | G", parts=[
    P("notes", inst="piano", vol=0.45, step=2, notes=[
        "e5 - - d5 c5 - g4 -", "d5 - - c5 b4 - g4 -", "c5 - b4 c5 e5 - a5 -", "g5 - - - - - e5 -",
        "f5 - - e5 d5 - c5 -", "e5 - - d5 c5 - g4 -", "a4 - c5 - f5 - e5 d5", "d5 - - - - - . ."]),
    P("arp", inst="piano", style="broken", oct=3, vol=0.22),
    P("pad", inst="strings", vol=0.12, oct=3, wide=True),
    P("bass", inst="bass", style="long", oct=2, vol=0.25),
])

# ---------------------------------------------------------------- Музыкальная шкатулка
MUSIC["musicbox"] = dict(bpm=88, reverb=0.35, chords="C | F | C | G | Am | F | G | C", parts=[
    P("notes", inst="bell", vol=0.45, step=2, echo=(3, 0.35, 0.25), notes=[
        "g5 - e5 - c5 - e5 g5", "a5 - - - f5 - a5 c6", "g5 - e5 - c5 - e5 g5", "d5 - - - . . . .",
        "e5 - a5 - c6 - b5 a5", "a5 - g5 - f5 - c5 -", "d5 - g5 - b5 - d6 -", "c6 - - - - - . ."]),
    P("arp", inst="bell", style="broken", oct=4, vol=0.14, pan=-0.3),
    P("bass", inst="sine", style="long", oct=3, vol=0.18),
])

# ---------------------------------------------------------------- Иисус
MUSIC["jesus"] = dict(bpm=140, reverb=0.3, chords="Dm | Bb | C | A | Dm | Bb | Gm | A7", parts=[
    P("notes", inst="organ", vol=0.22, step=2, notes=[
        "d5 - f5 a5 d6 - c6 a5", "bb5 - - - f5 - d5 f5", "g5 - c6 - e6 - d6 c6", "c#6 - - - a5 - e5 -",
        "f6 - e6 d6 a5 - d6 f6", "f6 - d6 bb5 f5 - bb5 d6", "d6 - c6 bb5 g5 - bb5 d6", "c#6 - - - e6 - g6 -"]),
    P("pad", inst="choir", vol=0.16, oct=4, wide=True),
    P("bass", inst="sawbass", style="drive", oct=2, vol=0.3),
    P("stab", inst="brass", vol=0.08, oct=3, pat="x.....x.....x...", pan=-0.3),
    P("drums", style="march", vol=0.34),
])

# ---------------------------------------------------------------- Костян
MUSIC["kostya"] = dict(bpm=122, chords="Dm | Dm | C | C | Bb | Bb | A | A", parts=[
    P("notes", inst="lead", vol=0.22, step=1, notes=[
        "d5 d5 a5 . g5 . f5 . d5 . f5 g5 a5 . c6 .", "a5 . g5 . f5 g5 f5 d5 e5 . f5 . e5 . d5 .",
        "c5 c5 g5 . f5 . e5 . c5 . e5 f5 g5 . bb5 .", "g5 . f5 . e5 f5 e5 c5 d5 . e5 . d5 . c5 .",
        "bb4 bb4 f5 . e5 . d5 . bb4 . d5 e5 f5 . a5 .", "f5 . e5 . d5 e5 d5 bb4 c5 . d5 . c5 . bb4 .",
        "a4 a4 e5 . d5 . c#5 . a4 . c#5 d5 e5 . g5 .", "a5 . g5 . e5 . c#5 . e5 . a5 . c#6 . e6 ."]),
    P("bass", inst="sqbass", style="drive", oct=2, vol=0.3),
    P("arp", inst="arp", style="up16", oct=4, vol=0.05, pan=-0.4),
    P("drums", style="fast", vol=0.34),
])

# ---------------------------------------------------------------- Таск (2 фаза)
MUSIC["tusk"] = dict(bpm=176, chords="Gm | Eb | F | D | Gm | Eb | Cm | D7", parts=[
    P("notes", inst="saw", vol=0.2, step=1, notes=[
        "g5 - d5 - g5 a5 bb5 - a5 g5 d5 - bb4 - d5 -", "eb5 - bb4 - eb5 f5 g5 - f5 eb5 bb4 - g4 - bb4 -",
        "f5 - c5 - f5 g5 a5 - c6 - a5 - f5 - c5 -", "d5 - a4 - d5 e5 f#5 - a5 - f#5 - d5 - a4 -",
        "d6 - - - bb5 - - - g5 - a5 - bb5 - d6 -", "eb6 - - - bb5 - - - g5 - bb5 - eb6 - g6 -",
        "f6 - eb6 - d6 - c6 - bb5 - a5 - g5 - eb5 -", "d5 - f#5 - a5 - c6 - d6 - - - . . . ."]),
    P("bass", inst="sawbass", style="drive", oct=2, vol=0.3),
    P("pad", inst="brass", vol=0.1, oct=3, wide=True),
    P("drums", style="metal", vol=0.34),
])

# ---------------------------------------------------------------- Гастер
MUSIC["gaster"] = dict(bpm=60, reverb=0.5, chords="Cm | Cm | Gb | Gb | Am | Am | Eb | D", parts=[
    P("notes", inst="sine", vol=0.35, step=2, echo=(3, 0.55, 0.45), notes=[
        "c6 - - - - - - -", ". . . . g5 - - -", "bb5 - - - - - - -", ". . . . db6 - - -",
        "e6 - - - - - - -", ". . . . c6 - - -", "g5 - - - - - - -", ". . . . f#5 - - -"]),
    P("pad", inst="choir", vol=0.12, oct=3, wide=True),
    P("arp", inst="glitch", style="up16", oct=5, vol=0.025, echo=(3, 0.5, 0.4), pan=0.5),
    P("bass", inst="sine", style="long", oct=2, vol=0.3),
])

# ---------------------------------------------------------------- Истинное зло
MUSIC["evil"] = dict(bpm=72, reverb=0.4, chords="Bm | G | Em | F# | Bm | G | C | F#", parts=[
    P("notes", inst="piano", vol=0.45, step=2, notes=[
        "b4 - - d5 f#5 - - b5", "a5 - - g5 d5 - - -", "e5 - - g5 b5 - - e6", "c#6 - - - a#5 - f#5 -",
        "b5 - - - f#5 - d5 -", "g5 - - f#5 e5 - d5 -", "e5 - - g5 c6 - - b5", "a#5 - - - f#5 - - -"]),
    P("pad", inst="strings", vol=0.13, oct=3, wide=True),
    P("bass", inst="bass", style="long", oct=1, vol=0.35),
    P("drums", style="halftime", vol=0.22),
])

# ---------------------------------------------------------------- Реабилитация (физрук... физик)
MUSIC["rehab"] = dict(bpm=136, chords="F | C7 | F | Bb | F | C7 | Bb,C7 | F", parts=[
    P("notes", inst="lead12", vol=0.2, step=2, gate=0.6, notes=[
        "c5 f5 a5 c6 a5 f5 c5 f5", "e5 g5 bb5 c6 bb5 g5 e5 c5", "f5 a5 c6 f6 c6 a5 f5 a5", "d6 - bb5 - f5 - d5 -",
        "a5 a5 g5 f5 c6 - a5 -", "g5 g5 f5 e5 bb5 - g5 -", "f5 - d5 - e5 - g5 -", "f5 - c5 - f4 - . ."]),
    P("bass", inst="bass", style="octave", oct=2, vol=0.42),
    P("stab", inst="arp25", vol=0.1, oct=4, pat="..x...x...x...x."),
    P("drums", style="march", vol=0.26),
])

# ---------------------------------------------------------------- Мир (Hunter)
MUSIC["peace"] = dict(bpm=100, reverb=0.3, chords="G | D/F# | Em | C | G | D | C | D", parts=[
    P("notes", inst="flute", vol=0.3, step=2, echo=(3, 0.35, 0.3), notes=[
        "d5 - g5 - b5 - a5 g5", "a5 - - - f#5 - d5 -", "e5 - g5 - b5 - d6 b5", "c6 - - - g5 - e5 -",
        "d5 - g5 - b5 - d6 -", "f#5 - a5 - d6 - c6 -", "b5 - a5 g5 e5 - g5 -", "a5 - - - - - . ."]),
    P("arp", inst="pluck", style="broken", oct=3, vol=0.16, pan=-0.3),
    P("bass", inst="bass", style="walk", oct=2, vol=0.35),
    P("drums", style="softhat", vol=0.25),
])

# ---------------------------------------------------------------- Цифровые корни
MUSIC["digital"] = dict(bpm=118, reverb=0.3, chords="Em | Em | C | D | Em | Em | Am | B", parts=[
    P("notes", inst="glitch", vol=0.2, step=1, echo=(3, 0.4, 0.35), notes=[
        "e5 . e6 . b5 . g5 . e5 . . . b4 . . .", "e5 . g5 . b5 . e6 . d6 . b5 . g5 . . .",
        "e5 . c6 . g5 . e5 . c5 . . . g4 . . .", "f#5 . a5 . d6 . f#6 . e6 . d6 . a5 . . .",
        "e5 . e6 . b5 . g5 . e5 . . . b4 . . .", "e5 . g5 . b5 . e6 . d6 . b5 . g5 . . .",
        "a5 . c6 . e6 . a6 . g6 . e6 . c6 . . .", "b5 . d#6 . f#6 . b6 . a6 . f#6 . d#6 . . ."]),
    P("bass", inst="sawbass", style="drive", oct=2, vol=0.28),
    P("pad", inst="pad", vol=0.1, oct=3, wide=True),
    P("drums", style="trap", vol=0.32),
])

# ---------------------------------------------------------------- Магазин
MUSIC["shop"] = dict(bpm=104, swing=0.3, chords="Cmaj7 | Am7 | Dm7 | G7 | Em7 | A7 | Dm7 | G7", parts=[
    P("notes", inst="lead50", vol=0.2, step=2, echo=(3, 0.3, 0.25), notes=[
        "e5 - g5 b5 - - a5 g5", "c6 - - a5 e5 - - -", "f5 - a5 c6 - - b5 a5", "g5 - - f5 d5 - b4 -",
        "e5 - g5 b5 d6 - b5 g5", "c#6 - - a5 e5 - g5 -", "f5 - e5 d5 a5 - c6 -", "b5 - - - g5 - . ."]),
    P("bass", inst="bass", style="walk", oct=2, vol=0.4),
    P("stab", inst="piano", vol=0.15, oct=4, pat="..x...x...x...x."),
    P("drums", style="shuffle", vol=0.22),
])

# ---------------------------------------------------------------- Тюрьма
MUSIC["prison"] = dict(bpm=92, swing=0.33, chords="E7 | A7 | E7 | E7 | A7 | A7 | E7 | B7", parts=[
    P("notes", inst="reed", vol=0.22, step=2, notes=[
        "e5 - g5 e5 a5 - a#5 b5", "c#6 - b5 - a5 - g5 e5", "g5 - e5 - d5 - e5 -", ". . b4 d5 e5 - g5 -",
        "a5 - c6 a5 d6 - c6 a5", "c#6 - a5 - g5 - e5 -", "e5 - g5 - b5 - d6 -", "d#6 - - - b5 - f#5 -"]),
    P("bass", inst="bass", style="walk", oct=2, vol=0.42),
    P("stab", inst="piano", vol=0.14, oct=4, pat="..x...x...x...x."),
    P("drums", style="shuffle", vol=0.28),
])

# ---------------------------------------------------------------- Ангельские лучи
MUSIC["rays"] = dict(bpm=70, reverb=0.45, expand=False, chords="Cm | Db | Cm | B", parts=[
    P("notes", inst="brass", vol=0.3, step=2, notes=["g5 - - - - - - -", "ab5 - - - - - - -", "g5 - - - eb5 - - -", "f#5 - - - - - - -"]),
    P("pad", inst="choir", vol=0.22, oct=4, wide=True),
    P("bass", inst="sawbass", style="half", oct=1, vol=0.35),
    P("drums", style="tick", vol=0.3, crash=False),
])

# ============================================================================
#                               ГРАФИКА
# ============================================================================
OUTLINE = (24, 14, 16)
_SPR = {}


def cached(key, fn):
    s = _SPR.get(key)
    if s is None:
        s = fn()
        _SPR[key] = s
    return s


def outline(surf, col=OUTLINE, th=1):
    w, h = surf.get_size()
    out = pygame.Surface((w + 2 * th, h + 2 * th), pygame.SRCALPHA)
    m = pygame.mask.from_surface(surf, 40)
    sil = m.to_surface(setcolor=tuple(col) + (255,), unsetcolor=(0, 0, 0, 0))
    for dx in range(-th, th + 1):
        for dy in range(-th, th + 1):
            if (dx or dy) and abs(dx) + abs(dy) <= th + (1 if th > 1 else 0):
                out.blit(sil, (th + dx, th + dy))
    out.blit(surf, (th, th))
    return out


def tinted(surf, col, alpha=255):
    s = surf.copy()
    m = pygame.mask.from_surface(s, 40)
    sil = m.to_surface(setcolor=tuple(col) + (alpha,), unsetcolor=(0, 0, 0, 0))
    return sil


def flash_white(surf):
    return cached(("white", id(surf)), lambda: tinted(surf, (255, 255, 255)))


def flash_red(surf):
    return cached(("red", id(surf)), lambda: _red(surf))


def _red(surf):
    s = surf.copy()
    s.fill((255, 90, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return s


class Pen:
    """Рисование в 'юнитах' с масштабом u."""

    def __init__(self, s, u, ox=0, oy=0):
        self.s, self.u, self.ox, self.oy = s, u, ox, oy

    def P(self, x, y):
        return (int(round((x + self.ox) * self.u)), int(round((y + self.oy) * self.u)))

    def r(self, v):
        return max(1, int(round(v * self.u)))

    def circ(self, col, x, y, r, w=0):
        pygame.draw.circle(self.s, col, self.P(x, y), self.r(r), self.r(w) if w else 0)

    def ell(self, col, x, y, w, h, wd=0):
        u = self.u
        rect = pygame.Rect(int(round((x - w / 2 + self.ox) * u)), int(round((y - h / 2 + self.oy) * u)),
                           max(1, int(round(w * u))), max(1, int(round(h * u))))
        pygame.draw.ellipse(self.s, col, rect, self.r(wd) if wd else 0)

    def rect(self, col, x, y, w, h, rad=0, wd=0):
        u = self.u
        rect = pygame.Rect(int(round((x + self.ox) * u)), int(round((y + self.oy) * u)),
                           max(1, int(round(w * u))), max(1, int(round(h * u))))
        pygame.draw.rect(self.s, col, rect, self.r(wd) if wd else 0, border_radius=int(rad * u))

    def poly(self, col, pts, wd=0):
        pygame.draw.polygon(self.s, col, [self.P(*p) for p in pts], self.r(wd) if wd else 0)

    def line(self, col, a, b, w=1):
        pygame.draw.line(self.s, col, self.P(*a), self.P(*b), self.r(w))

    def lines(self, col, pts, w=1):
        pygame.draw.lines(self.s, col, False, [self.P(*p) for p in pts], self.r(w))

    def arc(self, col, x, y, w, h, a0, a1, wd=1):
        u = self.u
        rect = pygame.Rect(int(round((x - w / 2 + self.ox) * u)), int(round((y - h / 2 + self.oy) * u)),
                           max(1, int(round(w * u))), max(1, int(round(h * u))))
        pygame.draw.arc(self.s, col, rect, a0, a1, self.r(wd))


# ---------------------------------------------------------------- люди
PERSONS = {
    "artem": dict(skin=(250, 214, 184), hair=(96, 58, 32), hair_style="messy", shirt=(64, 112, 196), pants=(52, 52, 74), shoes=(40, 30, 30)),
    "artem_dark": dict(skin=(214, 196, 196), hair=(30, 22, 30), hair_style="messy", shirt=(40, 30, 56), pants=(24, 20, 30), shoes=(20, 16, 20), evil=True),
    "artemosha": dict(skin=(252, 220, 192), hair=(150, 96, 48), hair_style="messy", shirt=(240, 200, 80), pants=(60, 90, 160), shoes=(40, 30, 30), blush=True),
    "valerii": dict(skin=(236, 192, 160), hair=(150, 150, 152), hair_style="bald_side", mustache=(112, 100, 96), glasses=True,
                    shirt=(44, 110, 72), stripes=(235, 235, 235), pants=(40, 44, 96), shoes=(30, 30, 30), tall=True),
    "jesus": dict(skin=(232, 190, 152), hair=(110, 70, 40), hair_style="long", beard=(100, 64, 36), robe=(246, 246, 240), sash=(196, 52, 60),
                  halo=True, tall=True, shoes=(160, 110, 70)),
    "kostya": dict(skin=(245, 212, 182), hair=(42, 34, 32), hair_style="short", shirt=(70, 122, 206), hood=(70, 122, 206), pants=(34, 34, 44),
                   shoes=(240, 240, 240), smile=True),
    "sergei": dict(skin=(242, 202, 172), hair=(226, 196, 120), hair_style="buzz", shirt=(222, 44, 44), stripes=(255, 255, 255),
                   pants=(245, 245, 245), shoes=(30, 30, 30), cigarette=True),
    "ellen": dict(skin=(252, 224, 210), hair=(34, 30, 40), tips=(214, 44, 60), hair_style="bob", dress=(32, 32, 44), apron=(246, 246, 246),
                  shoes=(30, 30, 30), shark=True, headband=True, blush=True),
    "gaster": dict(skin=(242, 242, 242), hair_style="none", robe=(22, 22, 28), tall=True, gaster=True, shoes=(22, 22, 28)),
    "daniil": dict(skin=(240, 206, 176), hair=(72, 52, 42), hair_style="short", glasses=True, beard=(72, 52, 42), short_beard=True,
                   shirt=(112, 82, 144), pants=(60, 60, 72), shoes=(40, 30, 30), book=True),
    "john": dict(skin=(222, 182, 152), hair_style="bald", shirt=(232, 232, 232), stripes2=(40, 40, 40), pants=(232, 232, 232), shoes=(40, 40, 40), tattoo=True),
    "unknown": dict(skin=(56, 30, 80), hair=(36, 18, 52), hair_style="hood", shirt=(36, 18, 52), pants=(30, 14, 44), shoes=(20, 10, 30), unknown=True),
    "botik": dict(skin=(176, 204, 156), hair=(30, 30, 30), hair_style="short", shirt=(92, 92, 104), pants=(50, 50, 60), shoes=(30, 30, 30), headphones=True, zombie=True),
    "dvoechnik": dict(skin=(240, 206, 176), hair=(150, 92, 42), hair_style="messy", shirt=(34, 52, 112), pants=(30, 30, 40), shoes=(30, 30, 30), angry=True),
    "shadow": dict(skin=(20, 16, 26), hair=(12, 10, 16), hair_style="short", shirt=(16, 12, 20), pants=(12, 10, 16), shoes=(10, 8, 12), shadow=True),
    "angel": dict(skin=(252, 226, 200), hair=(250, 214, 110), hair_style="buzz", robe=(250, 250, 250), sash=(120, 170, 250), halo=True, wings=True, shoes=(250, 250, 250)),
}


def draw_person(spec, facing="down", frame=0, u=1, pose=None, extras=()):
    ex = set(extras)
    tall = spec.get("tall", False)
    W, H = 26, (33 if tall else 30)
    s = pygame.Surface((int(W * u) + 2, int(H * u) + 2), pygame.SRCALPHA)
    p = Pen(s, u)
    dy = 3 if tall else 0
    hx, hy, hr = 13, 10, 8.7
    by = 17.5 + dy
    walk = (0, 1, 0, -1)[frame % 4]
    skin = spec["skin"]
    shirt = spec.get("shirt", (120, 120, 120))
    pants = spec.get("pants", (60, 60, 60))
    shoes = spec.get("shoes", (30, 30, 30))
    hair = spec.get("hair", (60, 40, 30))
    side = facing in ("left", "right")
    sgn = 1 if facing == "right" else -1
    front = facing == "down"
    back = facing == "up"
    shadowy = spec.get("shadow") or spec.get("unknown")
    # --- задние элементы
    if spec.get("wings") or "wings" in ex:
        wc = (250, 250, 255)
        for d in (-1, 1):
            p.poly(wc, [(hx + d * 3, by + 1), (hx + d * 13, by - 6 + walk * 0.5), (hx + d * 12, by + 1), (hx + d * 13, by + 5), (hx + d * 4, by + 6)])
            p.line((200, 210, 230), (hx + d * 5, by + 2), (hx + d * 11, by - 3), 0.6)
    if spec.get("shark"):
        tc = (90, 104, 130)
        d = -sgn if side else 1
        p.poly(tc, [(hx + d * 2, by + 6), (hx + d * 9, by + 9), (hx + d * 12, by + 5), (hx + d * 11, by + 11), (hx + d * 3, by + 9)])
        p.poly((230, 230, 236), [(hx + d * 4, by + 8.5), (hx + d * 10, by + 9.5), (hx + d * 4, by + 9.5)])
    if spec.get("hair_style") == "long" and not back:
        p.ell(hair, hx, hy + 5, hr * 2 + 2, hr * 2 + 9)
    if spec.get("hair_style") == "bob" and not back:
        p.ell(hair, hx, hy + 2, hr * 2 + 3, hr * 2 + 3)
    if spec.get("hood"):
        p.ell(spec["hood"], hx, hy + 3, hr * 2 + 3, hr * 2 + 2)
    # --- ноги
    robe = spec.get("robe")
    dress = spec.get("dress")
    if not robe:
        ly = by + 7
        l1 = walk if not side else 0
        if side:
            fx = (walk * 1.5)
            p.rect(pants, hx - 2.5 + fx, ly, 2.6, 4)
            p.rect(pants, hx + 0 - fx, ly, 2.6, 4)
            p.ell(shoes, hx - 1.2 + fx + sgn, ly + 4, 3.6, 2)
            p.ell(shoes, hx + 1.3 - fx + sgn, ly + 4, 3.6, 2)
        else:
            p.rect(pants, hx - 4, ly - l1 * 0.5, 3, 4 + l1 * 0.5)
            p.rect(pants, hx + 1, ly + l1 * 0.5, 3, 4 - l1 * 0.5)
            p.ell(shoes, hx - 2.5, ly + 4 - l1 * 0.3, 3.8, 2)
            p.ell(shoes, hx + 2.5, ly + 4 + l1 * 0.3, 3.8, 2)
    # --- тело
    if robe:
        p.poly(robe, [(hx - 4.5, by - 1), (hx + 4.5, by - 1), (hx + 7, by + 12), (hx - 7, by + 12)])
        if spec.get("sash"):
            p.line(spec["sash"], (hx - 4, by), (hx + 5, by + 8), 1.4)
        p.ell(shoes, hx - 3, by + 12, 3.5, 1.6)
        p.ell(shoes, hx + 3, by + 12, 3.5, 1.6)
    elif dress:
        p.poly(dress, [(hx - 4.5, by - 1), (hx + 4.5, by - 1), (hx + 7.5, by + 8), (hx - 7.5, by + 8)])
        if spec.get("apron") and not back:
            p.poly(spec["apron"], [(hx - 3, by + 1), (hx + 3, by + 1), (hx + 4.5, by + 7), (hx - 4.5, by + 7)])
            p.line(spec["apron"], (hx - 4, by - 0.5), (hx + 4, by - 0.5), 0.8)
    else:
        p.rect(shirt, hx - 5, by - 1, 10, 8.5, rad=2.5)
        if spec.get("stripes"):
            p.line(spec["stripes"], (hx - 4.6, by + 1), (hx - 4.6, by + 7), 0.7)
            p.line(spec["stripes"], (hx + 4.4, by + 1), (hx + 4.4, by + 7), 0.7)
        if spec.get("stripes2"):
            for k in range(3):
                p.line(spec["stripes2"], (hx - 4.8, by + 1 + k * 2.5), (hx + 4.8, by + 1 + k * 2.5), 0.8)
        if spec.get("hood") and front:
            p.line((240, 240, 240), (hx - 1, by), (hx - 1.2, by + 3), 0.5)
            p.line((240, 240, 240), (hx + 1, by), (hx + 1.2, by + 3), 0.5)
    # --- руки
    arm_c = robe or dress or shirt
    if pose == "hold":
        for d in (-1, 1):
            p.ell(arm_c, hx + d * 6, by - 1, 3, 4)
            p.circ(skin, hx + d * 7.5, by - 4.5, 1.6)
    elif not back or True:
        if side:
            p.ell(arm_c, hx - sgn * 0.5, by + 3 + walk * 0.4, 3.2, 5)
            p.circ(skin, hx - sgn * 0.5 + walk * 0.5 * sgn, by + 6, 1.5)
        else:
            sw = walk * 0.6
            p.ell(arm_c, hx - 6, by + 2.5 + sw, 3, 5)
            p.ell(arm_c, hx + 6, by + 2.5 - sw, 3, 5)
            p.circ(skin, hx - 6.3, by + 5.3 + sw, 1.5)
            p.circ(skin, hx + 6.3, by + 5.3 - sw, 1.5)
            if spec.get("book") and front:
                p.rect((180, 40, 40), hx + 4.8, by + 3.4 - sw, 4, 4.5)
                p.rect((240, 230, 200), hx + 5.4, by + 4 - sw, 3, 3.5)
    # --- голова
    if spec.get("headphones"):
        p.arc((40, 40, 46), hx, hy - 1, hr * 2 + 3, hr * 2 + 3, 0.1, math.pi - 0.1, 1.4)
    p.circ(skin, hx, hy, hr)
    if not back and not side and spec.get("hair_style") not in ("long", "hood", "bob"):
        p.circ(skin, hx - hr + 0.4, hy + 1.5, 1.8)
        p.circ(skin, hx + hr - 0.4, hy + 1.5, 1.8)
    # тень на голове
    if not shadowy:
        p.arc(col_mul(skin, 0.86), hx, hy + 0.5, hr * 2 - 1, hr * 2 - 1, math.pi * 1.1, math.pi * 1.9, 1.2)
    # --- лицо
    if not back:
        _draw_face(p, spec, facing, hx, hy, hr, ex, pose)
    # --- волосы
    _draw_hair(p, spec, facing, hx, hy, hr)
    # --- аксессуары
    if spec.get("headphones"):
        for d in (-1, 1):
            p.ell((40, 40, 46), hx + d * (hr + 0.5), hy + 1, 3, 5)
            p.ell((220, 60, 60), hx + d * (hr + 0.5), hy + 1, 1.5, 3)
    if spec.get("headband") and not back:
        p.arc((246, 246, 246), hx, hy + 1, hr * 2 + 1, hr * 2 + 1, math.pi * 0.25, math.pi * 0.75, 1.6)
        for k in (-4, -1.4, 1.4, 4):
            p.circ((246, 246, 246), hx + k, hy - hr + 0.8 + abs(k) * 0.25, 1.0)
    if spec.get("halo") or "halo" in ex:
        p.ell((255, 224, 90), hx, hy - hr - 2.2, 13, 4, 1.1)
    if "cat_ears" in ex:
        ec = hair if spec.get("hair_style") not in ("none", "bald") else (150, 150, 150)
        for d in (-1, 1):
            p.poly(ec, [(hx + d * 3, hy - hr + 1.5), (hx + d * 7.5, hy - hr - 4), (hx + d * 7.5, hy - hr + 3)])
            p.poly((240, 150, 170), [(hx + d * 4.5, hy - hr + 1.5), (hx + d * 6.8, hy - hr - 1.8), (hx + d * 6.8, hy - hr + 2)])
    if "wizard" in ex:
        p.poly((96, 56, 170), [(hx - 9, hy - hr + 3.5), (hx + 9, hy - hr + 3.5), (hx + 2, hy - hr - 10), (hx + 5, hy - hr - 12)])
        p.ell((80, 40, 150), hx, hy - hr + 3.3, 20, 3.4)
        p.circ((255, 230, 100), hx + 1, hy - hr - 2, 0.9)
        p.circ((255, 230, 100), hx - 3, hy - hr + 1, 0.6)
    if "horns" in ex or spec.get("evil"):
        for d in (-1, 1):
            p.poly((140, 20, 30), [(hx + d * 3, hy - hr + 2), (hx + d * 6.5, hy - hr - 4.5), (hx + d * 6, hy - hr + 2.5)])
    if "thorns" in ex:
        for k in range(9):
            a = math.pi * (1.05 + k * 0.1)
            x0, y0 = hx + math.cos(a) * (hr - 0.5), hy - 2 + math.sin(a) * (hr - 2.5)
            p.line((110, 90, 50), (x0 - 1, y0), (x0 + 1, y0 - 1.6), 0.7)
        p.arc((110, 90, 50), hx, hy - 2, hr * 2, hr * 1.2, math.pi * 1.05, math.pi * 1.95, 0.9)
    return s


def _draw_face(p, spec, facing, hx, hy, hr, ex, pose):
    eye = (26, 20, 28)
    if spec.get("evil") or "evil" in ex:
        eye = (220, 20, 30)
    side = facing in ("left", "right")
    sgn = 1 if facing == "right" else -1
    if spec.get("unknown"):
        for d in (-1, 1):
            p.circ((200, 120, 255), hx + d * 3.2, hy + 1, 1.5)
            p.circ((255, 255, 255), hx + d * 3.2, hy + 1, 0.6)
        return
    if spec.get("shadow"):
        for d in (-1, 1):
            p.ell((240, 240, 240), hx + d * 3.2 + (sgn * 2 if side else 0), hy + 1, 2.2, 3)
        return
    if spec.get("gaster"):
        p.circ((10, 10, 10), hx - 3.4, hy, 2.4)
        p.circ((10, 10, 10), hx + 3.4, hy, 2.4)
        p.circ((255, 255, 255), hx - 3.4, hy, 0.7)
        p.lines((30, 30, 30), [(hx - 3.4, hy - 2.5), (hx - 2.5, hy - 5), (hx - 3.5, hy - 7.5)], 0.6)
        p.lines((30, 30, 30), [(hx + 3.4, hy + 2.5), (hx + 4.4, hy + 5), (hx + 3.6, hy + 7)], 0.6)
        p.arc((20, 20, 20), hx, hy + 3.2, 5, 3, math.pi * 1.15, math.pi * 1.85, 0.6)
        return
    if side:
        ex_ = hx + sgn * 4.2
        if pose == "shoot":
            p.line(eye, (ex_ - 1.2, hy + 1), (ex_ + 1.2, hy + 1), 0.9)
        else:
            p.ell(eye, ex_, hy + 1, 2.6, 3.3)
            p.circ((255, 255, 255), ex_ - 0.5 * sgn + 0.2, hy, 0.6)
        if spec.get("glasses"):
            p.rect((30, 30, 34), ex_ - 2, hy - 1, 4, 3.6, wd=0.6)
        p.line((120, 50, 50), (hx + sgn * 5.5, hy + 5), (hx + sgn * 7, hy + 4.7), 0.7)
        if spec.get("mustache"):
            p.ell(spec["mustache"], hx + sgn * 6, hy + 3.8, 4, 1.6)
        if spec.get("beard") and not spec.get("short_beard"):
            p.poly(spec["beard"], [(hx + sgn * 2, hy + 3), (hx + sgn * 8.5, hy + 3), (hx + sgn * 5, hy + hr + 3)])
        if spec.get("cigarette"):
            p.line((250, 250, 250), (hx + sgn * 6.5, hy + 5), (hx + sgn * 10, hy + 5), 0.9)
            p.circ((255, 120, 40), hx + sgn * 10.3, hy + 5, 0.6)
        if spec.get("blush"):
            p.ell((250, 150, 160), hx + sgn * 2.5, hy + 4, 2.5, 1.2)
        return
    # анфас
    if spec.get("beard"):
        if spec.get("short_beard"):
            p.arc(spec["beard"], hx, hy + 2, hr * 2 - 1, hr * 2 - 0.5, math.pi * 1.1, math.pi * 1.9, 1.6)
        else:
            p.poly(spec["beard"], [(hx - hr + 1.4, hy + 1), (hx + hr - 1.4, hy + 1), (hx + 4, hy + hr + 2), (hx, hy + hr + 4.5), (hx - 4, hy + hr + 2)])
    for d in (-1, 1):
        ex_ = hx + d * 3.4
        if pose == "shoot":
            p.line(eye, (ex_ - 1.3, hy + 1.2), (ex_ + 1.3, hy + 1.2), 0.9)
        else:
            p.ell(eye, ex_, hy + 1, 2.7, 3.4)
            p.circ((255, 255, 255), ex_ - 0.5, hy + 0.1, 0.65)
        if spec.get("evil") or "evil" in ex:
            p.circ((255, 90, 90), ex_, hy + 1.2, 0.5)
        if spec.get("angry") or "angry" in ex:
            p.line((40, 26, 20), (ex_ - d * 1.8, hy - 2.6), (ex_ + d * 1.4, hy - 1.4), 0.8)
        if spec.get("glasses"):
            p.rect((30, 30, 34), ex_ - 2.2, hy - 1.2, 4.4, 4.2, wd=0.6)
    if spec.get("glasses"):
        p.line((30, 30, 34), (hx - 1.2, hy + 0.5), (hx + 1.2, hy + 0.5), 0.5)
    if spec.get("blush"):
        p.ell((250, 150, 160), hx - 5, hy + 3.6, 2.5, 1.2)
        p.ell((250, 150, 160), hx + 5, hy + 3.6, 2.5, 1.2)
    if spec.get("mustache"):
        p.ell(spec["mustache"], hx, hy + 4, 6.5, 1.8)
    if spec.get("smile"):
        p.arc((90, 40, 40), hx, hy + 3.4, 5, 3, math.pi * 1.1, math.pi * 1.9, 0.6)
    elif spec.get("zombie"):
        p.line((60, 30, 30), (hx - 2, hy + 5), (hx + 2, hy + 4.4), 0.7)
    elif "grin" in ex:
        p.arc((60, 10, 10), hx, hy + 3, 7, 4, math.pi * 1.05, math.pi * 1.95, 0.9)
    else:
        p.line((120, 50, 50), (hx - 1.3, hy + 5), (hx + 1.3, hy + 5), 0.6)
    if spec.get("cigarette"):
        p.line((250, 250, 250), (hx + 1, hy + 5), (hx + 5, hy + 5.5), 0.9)
        p.circ((255, 120, 40), hx + 5.3, hy + 5.6, 0.6)
    if spec.get("tattoo"):
        p.line((60, 80, 140), (hx - 4, hy + 6.5), (hx - 2, hy + 7.2), 0.5)


def _draw_hair(p, spec, facing, hx, hy, hr):
    st = spec.get("hair_style", "short")
    hair = spec.get("hair", (60, 40, 30))
    side = facing in ("left", "right")
    sgn = 1 if facing == "right" else -1
    back = facing == "up"
    if st in ("none", "bald"):
        if st == "bald":
            p.ell(col_mul(spec["skin"], 1.12), hx - 2.5, hy - 5, 4, 2)
        return
    if st == "hood":
        p.arc(hair, hx, hy + 1, hr * 2 + 3, hr * 2 + 4, 0, math.pi, 2.6)
        if back:
            p.circ(hair, hx, hy, hr + 0.5)
        return
    if back and st == "bald_side":
        p.arc(hair, hx, hy + 1, hr * 2, hr * 2, math.pi * 1.05, math.pi * 1.95, 2.4)
        return
    if back:
        p.circ(hair, hx, hy - 0.3, hr + 0.4)
        if st == "messy":
            for k in (-5, -1, 3, 6):
                p.poly(hair, [(hx + k - 2, hy - hr + 2), (hx + k + 0.5, hy - hr - 2.5), (hx + k + 2, hy - hr + 2)])
        if st in ("long", "bob"):
            p.ell(hair, hx, hy + 5, hr * 2 + 2, hr * 2 + (9 if st == "long" else 3))
            if st == "bob":
                p.ell(spec.get("tips", hair), hx, hy + hr + 1.5, hr * 2, 3)
        return
    if st == "bald_side":
        if not side:
            p.ell(hair, hx - hr + 0.8, hy - 0.5, 3.2, 6)
            p.ell(hair, hx + hr - 0.8, hy - 0.5, 3.2, 6)
        else:
            p.ell(hair, hx - sgn * 3, hy - 0.5, 5, 6)
        p.ell(col_mul(spec["skin"], 1.12), hx - 2.5, hy - 5, 4, 2)
        return
    # верхняя "шапка"
    pts = []
    rr = hr + 0.6
    for k in range(0, 13):
        a = math.pi + k * math.pi / 12
        pts.append((hx + math.cos(a) * rr, hy + math.sin(a) * rr))
    if st == "messy":
        if side:
            fr = [(hx + sgn * rr, hy - 1), (hx + sgn * 5, hy - 4.5), (hx + sgn * 3.5, hy - 2.8), (hx + sgn * 1, hy - 5),
                  (hx - sgn * 1, hy - 1.5), (hx - sgn * 4, hy + 2.5), (hx - sgn * rr, hy + 1.5)]
        else:
            fr = [(hx + rr, hy - 0.5), (hx + 5.5, hy - 4.6), (hx + 3.6, hy - 2.2), (hx + 1.2, hy - 5.4), (hx - 0.8, hy - 2.6),
                  (hx - 3, hy - 5.4), (hx - 5.2, hy - 2.4), (hx - rr, hy - 0.5)]
        if sgn < 0 and side:
            fr = fr[::-1]
        p.poly(hair, pts + fr)
        for k in (-6, -2, 2.5, 6):
            p.poly(hair, [(hx + k - 2, hy - hr + 1.5), (hx + k + 0.6 * (1 if k > 0 else -1), hy - hr - 2.6), (hx + k + 2, hy - hr + 1.5)])
        p.line(col_mul(hair, 1.4), (hx - 3, hy - hr + 1.6), (hx + 1, hy - hr + 1.2), 0.6)
    elif st == "short":
        if side:
            fr = [(hx + sgn * rr, hy - 2), (hx + sgn * 2, hy - 4), (hx - sgn * 3, hy - 1), (hx - sgn * rr, hy + 2)]
        else:
            fr = [(hx + rr, hy - 1), (hx + 4, hy - 3.6), (hx, hy - 4.4), (hx - 4, hy - 3.6), (hx - rr, hy - 1)]
        if sgn < 0 and side:
            fr = fr[::-1]
        p.poly(hair, pts + fr)
        p.line(col_mul(hair, 1.5), (hx - 3, hy - hr + 1.6), (hx + 1, hy - hr + 1.2), 0.6)
    elif st == "buzz":
        fr = [(hx + rr - 0.6, hy - 3), (hx, hy - 5.6), (hx - rr + 0.6, hy - 3)]
        p.poly(hair, pts[1:-1] + fr)
    elif st == "long":
        p.poly(hair, pts + [(hx + rr, hy - 1), (hx + 2, hy - 5.5), (hx, hy - 4.5), (hx - 2, hy - 5.5), (hx - rr, hy - 1)])
        p.line(col_mul(hair, 0.7), (hx, hy - hr), (hx, hy - 4.5), 0.6)
    elif st == "bob":
        p.poly(hair, pts + [(hx + rr, hy + 1), (hx + 5, hy - 3), (hx - 5, hy - 3), (hx - rr, hy + 1)])
        tips = spec.get("tips", hair)
        if not side:
            for d in (-1, 1):
                p.poly(hair, [(hx + d * (rr - 0.5), hy - 2), (hx + d * (rr + 0.8), hy + 6), (hx + d * (rr - 2.5), hy + 6.5)])
                p.poly(tips, [(hx + d * (rr + 0.8), hy + 5), (hx + d * (rr + 0.9), hy + 7.5), (hx + d * (rr - 2.6), hy + 7)])
        p.poly(tips, [(hx - 1, hy - 3.2), (hx + 1.5, hy - 3.2), (hx + 0.5, hy - 1)])


def person_frames(key, facing, frame, u=1, pose=None, extras=()):
    k = ("person", key, facing, frame, u, pose, tuple(sorted(extras)))

    def build():
        sp = PERSONS[key]
        s = draw_person(sp, facing, frame, u, pose, extras)
        if facing == "left" and False:
            s = pygame.transform.flip(s, True, False)
        return outline(s, th=max(1, int(u * 0.75)) if u >= 2 else 1)
    return cached(k, build)


def portrait(key, extras=()):
    def build():
        u = 4
        sp = PERSONS[key]
        s = draw_person(sp, "down", 0, u, None, extras)
        crop = s.subsurface(pygame.Rect(0, 0, s.get_width(), int(23 * u))).copy()
        return outline(crop, th=3)
    return cached(("portrait", key, tuple(sorted(extras))), build)


# ---------------------------------------------------------------- кот Дымок
def draw_cat(u=1, frame=0, angry=False, pose="sit"):
    s = pygame.Surface((int(30 * u) + 2, int(26 * u) + 2), pygame.SRCALPHA)
    p = Pen(s, u)
    fur = (150, 150, 158)
    dark = (96, 96, 104)
    tw = math.sin(frame * 0.8) * 2
    p.lines(fur, [(22, 20), (27, 17 + tw), (27, 10 + tw), (25, 7 + tw)], 2.6)
    p.ell(fur, 15, 18, 16, 10)
    p.ell((200, 200, 206), 15, 20, 8, 5)
    for x in (9, 12.5, 17.5, 21):
        p.ell(fur, x, 23, 3.4, 3)
    p.circ(fur, 15, 10, 7.5)
    for d in (-1, 1):
        p.poly(fur, [(15 + d * 2.5, 4.5), (15 + d * 7.5, -0.5), (15 + d * 7, 7)])
        p.poly((236, 150, 170), [(15 + d * 3.8, 4.8), (15 + d * 6.6, 1.8), (15 + d * 6.2, 6)])
    p.line(dark, (12.5, 4), (13, 7), 0.8)
    p.line(dark, (15, 3.5), (15, 6.8), 0.8)
    p.line(dark, (17.5, 4), (17, 7), 0.8)
    eye = (255, 60, 50) if angry else (190, 230, 90)
    for d in (-1, 1):
        ex_ = 15 + d * 3.2
        p.ell(eye, ex_, 9.5, 3.2, 3.6)
        p.ell((20, 20, 20), ex_, 9.5, 0.9, 3.2)
        p.circ((255, 80, 80), 15 + d * 2.6, 12.6, 0.9)
        p.line((30, 26, 30), (15 + d * 1.6, 13.8), (15 + d * 5.5, 12.4), 0.6)
        p.line((230, 230, 230), (15 + d * 4, 13.5), (15 + d * 9, 12.8), 0.35)
        p.line((230, 230, 230), (15 + d * 4, 14.2), (15 + d * 9, 14.6), 0.35)
    p.poly((236, 140, 160), [(14.2, 12.6), (15.8, 12.6), (15, 13.6)])
    p.arc((40, 30, 30), 14, 14.4, 2, 1.6, math.pi, math.pi * 2, 0.5)
    p.arc((40, 30, 30), 16, 14.4, 2, 1.6, math.pi, math.pi * 2, 0.5)
    return outline(s, th=max(1, int(u * 0.6)))


# ---------------------------------------------------------------- рак (синий лобстер)
def draw_lobster(u=1, frame=0, angry=False):
    s = pygame.Surface((int(34 * u) + 2, int(32 * u) + 2), pygame.SRCALPHA)
    p = Pen(s, u)
    c1 = (64, 118, 228) if not angry else (200, 70, 80)
    c2 = col_mul(c1, 0.72)
    c3 = col_mul(c1, 1.25)
    sn = math.sin(frame * 0.9)
    for d in (-1, 1):
        p.lines(c2, [(17 + d * 2, 4), (17 + d * 7, -0.0), (17 + d * 13, 1 + sn)], 0.6)
        for k in range(3):
            p.line(c2, (17 + d * 5, 12 + k * 2.5), (17 + d * 9.5, 14 + k * 2.8 + sn * d * 0.6), 0.8)
    for k, (w, h) in enumerate(((10, 4), (9, 4), (8, 3.6), (6.5, 3.4))):
        p.ell(c2 if k % 2 else c1, 17, 19 + k * 3.2, w, h)
    p.poly(c1, [(17, 30), (12, 32), (14, 28.5), (20, 28.5), (22, 32)])
    p.ell(c1, 17, 11, 12, 13)
    p.ell(c3, 15, 8.5, 4, 5)
    for d in (-1, 1):
        cx = 17 + d * (10 + sn * 0.8)
        p.lines(c1, [(17 + d * 5, 9), (17 + d * 8, 7), cx and (cx, 4)], 2.2)
        p.ell(c1, cx, 2.5, 6, 6.5)
        p.poly(col_mul(c1, 0.9), [(cx - 2.6, 0), (cx - 0.4 * d, 4), (cx + 2.6, 0), (cx, -2.8 - sn)])
        p.ell(c3, cx - d, 2, 2, 2.5)
        p.circ((20, 20, 24), 17 + d * 2.6, 6, 1.3)
        p.circ((255, 255, 255), 17 + d * 2.3, 5.6, 0.45)
    if angry:
        p.line((20, 10, 10), (13.5, 3.8), (16, 5.2), 0.7)
        p.line((20, 10, 10), (20.5, 3.8), (18, 5.2), 0.7)
    return outline(s, th=max(1, int(u * 0.6)))


# ---------------------------------------------------------------- облако дыма
def draw_cloud(u=1, frame=0, face=True, col=(160, 160, 166), angry=False, cig=False, w=24, h=18):
    s = pygame.Surface((int(w * u) + 4, int(h * u) + 4), pygame.SRCALPHA)
    p = Pen(s, u)
    rs = random.Random(7)
    puffs = []
    for i in range(9):
        a = i / 9 * math.pi * 2
        puffs.append((w / 2 + math.cos(a) * w * 0.28 + rs.uniform(-1, 1), h / 2 + math.sin(a) * h * 0.22 + rs.uniform(-1, 1), min(w, h) * rs.uniform(0.2, 0.28)))
    for (x, y, r) in puffs:
        p.circ(col_mul(col, 0.8), x, y + 1, r + math.sin(frame * 0.7 + x) * 0.4)
    for (x, y, r) in puffs:
        p.circ(col, x, y, r)
    p.circ(col, w / 2, h / 2, min(w, h) * 0.32)
    p.circ(col_mul(col, 1.15), w / 2 - w * 0.12, h / 2 - h * 0.15, min(w, h) * 0.14)
    if face:
        ec = (200, 30, 30) if angry else (30, 30, 34)
        for d in (-1, 1):
            p.ell(ec, w / 2 + d * w * 0.13, h / 2 - h * 0.02, max(1.6, w * 0.07), max(2, h * 0.11))
            if angry:
                p.line((30, 30, 30), (w / 2 + d * w * 0.22, h / 2 - h * 0.18), (w / 2 + d * w * 0.06, h / 2 - h * 0.1), max(0.6, w * 0.02))
        p.arc((40, 40, 44), w / 2, h / 2 + h * 0.16, w * 0.2, h * 0.14, 0, math.pi, max(0.6, w * 0.02))
        if cig:
            p.line((250, 250, 250), (w / 2 + w * 0.06, h / 2 + h * 0.2), (w / 2 + w * 0.32, h / 2 + h * 0.24), max(1, w * 0.04))
            p.circ((255, 120, 40), w / 2 + w * 0.33, h / 2 + h * 0.24, max(0.8, w * 0.025))
    return outline(s, col=(60, 60, 66), th=1)


# ---------------------------------------------------------------- Таск (дух)
def draw_tusk(u=1, frame=0):
    s = pygame.Surface((int(28 * u) + 2, int(34 * u) + 2), pygame.SRCALPHA)
    p = Pen(s, u)
    body = (236, 160, 210)
    gold = (255, 214, 90)
    bob = math.sin(frame * 0.6) * 1
    p.poly(body, [(8, 14 + bob), (20, 14 + bob), (17, 30 + bob), (14, 34), (11, 30 + bob)])
    p.ell(body, 14, 16 + bob, 16, 8)
    for d in (-1, 1):
        p.circ(gold, 14 + d * 8, 14 + bob, 3)
        p.circ(body, 14 + d * 8, 14 + bob, 1.6)
        p.lines(body, [(14 + d * 7, 16 + bob), (14 + d * 11, 22 + bob), (14 + d * 10, 26 + bob)], 1.8)
    p.circ(body, 14, 8 + bob, 6)
    p.poly(gold, [(9, 4 + bob), (14, 0 + bob), (19, 4 + bob), (14, 6 + bob)])
    for d in (-1, 1):
        p.ell((40, 20, 60), 14 + d * 2.5, 8.5 + bob, 2.2, 3)
        p.circ((255, 255, 255), 14 + d * 2.5, 8 + bob, 0.5)
    for k in range(4):
        a = frame * 0.3 + k * math.pi / 2
        x, y = 14 + math.cos(a) * 3, 22 + bob + math.sin(a) * 2
        _star(p, gold, x, y, 1.6)
    return outline(s, col=(120, 60, 110))


def _star(p, col, x, y, r):
    pts = []
    for k in range(10):
        a = -math.pi / 2 + k * math.pi / 5
        rr = r if k % 2 == 0 else r * 0.45
        pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
    p.poly(col, pts)


# ---------------------------------------------------------------- враги (мелкие)
def enemy_sprite(kind, frame=0, flag=False):
    return cached(("en", kind, frame % 4, flag), lambda: _enemy_build(kind, frame % 4, flag))


def _enemy_build(kind, f, flag):
    if kind in PERSONS:
        return person_frames(kind, "down", f)
    s = pygame.Surface((30, 30), pygame.SRCALPHA)
    p = Pen(s, 1)
    c = 15
    wing = (f % 2)
    if kind in ("fly", "nicotine", "afly"):
        body = (30, 30, 30) if kind == "fly" else (150, 120, 40) if kind == "nicotine" else (60, 10, 10)
        wc = (230, 230, 240, 200)
        if wing:
            p.ell(wc, c - 5, c - 3, 7, 4)
            p.ell(wc, c + 5, c - 3, 7, 4)
        else:
            p.ell(wc, c - 5, c - 5, 5, 6)
            p.ell(wc, c + 5, c - 5, 5, 6)
        p.circ(body, c, c, 4.4)
        p.circ((220, 40, 40) if kind != "fly" else (200, 200, 200), c - 1.6, c - 0.8, 1.1)
        p.circ((220, 40, 40) if kind != "fly" else (200, 200, 200), c + 1.6, c - 0.8, 1.1)
    elif kind == "roach":
        for k in range(3):
            o = (1 if (k + f) % 2 else -1)
            p.line((60, 34, 20), (c - 2, c - 2 + k * 2.5), (c - 8, c - 4 + k * 3 + o), 0.8)
            p.line((60, 34, 20), (c + 2, c - 2 + k * 2.5), (c + 8, c - 4 + k * 3 - o), 0.8)
        p.ell((122, 70, 34), c, c + 1, 9, 13)
        p.ell((90, 50, 24), c, c - 5, 6, 5)
        p.line((160, 100, 60), (c, c - 3), (c, c + 6), 0.6)
        p.line((60, 34, 20), (c - 1, c - 7), (c - 4, c - 12), 0.6)
        p.line((60, 34, 20), (c + 1, c - 7), (c + 4, c - 12), 0.6)
    elif kind == "vacuum":
        p.circ((70, 70, 78), c, c, 11)
        p.circ((150, 150, 160), c, c, 9.5)
        p.circ((110, 110, 120), c, c, 6)
        p.circ((255, 40, 40) if flag else (60, 220, 90), c, c - 6.5, 1.4)
        p.line((70, 70, 78), (c - 6, c + 5), (c + 6, c + 5), 0.8)
    elif kind == "sock":
        h = -2 if f % 2 else 0
        p.poly((236, 236, 236), [(c - 4, c - 9 + h), (c + 3, c - 9 + h), (c + 3, c + 3 + h), (c + 8, c + 5 + h), (c + 8, c + 9 + h), (c - 4, c + 9 + h)])
        p.rect((220, 70, 70), c - 4, c - 9 + h, 7, 3)
        p.line((20, 20, 20), (c - 2.5, c - 3 + h), (c - 0.5, c - 2 + h), 0.8)
        p.line((20, 20, 20), (c + 2, c - 3 + h), (c + 0, c - 2 + h), 0.8)
        p.circ((20, 20, 20), c - 1.4, c - 1 + h, 0.8)
        p.circ((20, 20, 20), c + 1.2, c - 1 + h, 0.8)
    elif kind == "cactus":
        p.poly((160, 92, 50), [(c - 7, c + 4), (c + 7, c + 4), (c + 5, c + 12), (c - 5, c + 12)])
        p.rect((130, 72, 40), c - 8, c + 3, 16, 2.5)
        p.rect((70, 160, 70), c - 4, c - 10, 8, 15, rad=4)
        p.rect((70, 160, 70), c - 9, c - 5, 5, 3, rad=1)
        p.rect((70, 160, 70), c - 9, c - 9, 3, 6, rad=1)
        p.rect((70, 160, 70), c + 4, c - 4, 5, 3, rad=1)
        p.rect((70, 160, 70), c + 6, c - 8, 3, 6, rad=1)
        p.circ((20, 30, 20), c - 1.6, c - 4, 1)
        p.circ((20, 30, 20), c + 1.6, c - 4, 1)
        p.rect((20, 30, 20), c - 1.5, c - 1 + (1 if flag else 0), 3, 1.4 + (1.5 if flag else 0))
    elif kind == "mold":
        for k in range(7):
            a = k / 7 * math.pi * 2 + f * 0.2
            p.circ((80, 150, 70), c + math.cos(a) * 6, c + math.sin(a) * 5, 3.5)
        p.circ((100, 170, 80), c, c, 6)
        p.circ((40, 90, 40), c - 2, c - 1, 1.3)
        p.circ((40, 90, 40), c + 2, c - 1, 1.3)
        p.circ((40, 90, 40), c, c + 2.5, 1.5 if flag else 1)
    elif kind == "plane":
        a = f * 0.0
        p.poly((246, 246, 246), [(c - 10, c + 6), (c + 10, c - 6), (c - 2, c + 9)])
        p.poly((210, 210, 214), [(c - 2, c + 9), (c + 10, c - 6), (c + 1, c + 4)])
        p.line((150, 150, 160), (c - 4, c + 6), (c + 9, c - 5), 0.5)
    elif kind == "smoke":
        return outline(draw_cloud(0.6, f, True, (176, 176, 180), angry=True), (70, 70, 74), 0)
    elif kind == "journal":
        p.rect((40, 90, 160), c - 9, c - 8, 18, 16, rad=2)
        p.rect((236, 236, 220), c - 8, c - 7, 16, 14)
        p.line((180, 180, 170), (c, c - 7), (c, c + 7), 0.8)
        p.circ((20, 20, 20), c - 4, c - 2, 1.4)
        p.circ((20, 20, 20), c + 4, c - 2, 1.4)
        f2 = pygame.font.Font(None, 14)
        s.blit(f2.render("2", False, (220, 30, 30)), (c - 7, c + 1))
        s.blit(f2.render("2", False, (220, 30, 30)), (c + 3, c + 1))
        if flag:
            p.ell((100, 20, 20), c, c + 4, 4, 3)
    elif kind == "chalk":
        p.rect((246, 246, 240), c - 3, c - 9, 6, 18, rad=2)
        p.circ((20, 20, 20), c - 1.3, c - 4, 0.9)
        p.circ((20, 20, 20), c + 1.3, c - 4, 0.9)
        p.line((20, 20, 20), (c - 1.5, c - 1), (c + 1.5, c - 1), 0.6)
        if flag:
            p.line((220, 30, 30), (c - 3, c - 6.5), (c - 0.5, c - 5.5), 0.6)
            p.line((220, 30, 30), (c + 3, c - 6.5), (c + 0.5, c - 5.5), 0.6)
    elif kind == "butt":
        h = -2 if f % 2 else 0
        p.rect((240, 240, 236), c - 2, c - 6 + h, 4, 7)
        p.rect((220, 150, 70), c - 2, c + 1 + h, 4, 6)
        p.circ((60, 60, 60), c, c - 6 + h, 2)
        p.circ((20, 20, 20), c - 0.9, c + 3 + h, 0.6)
        p.circ((20, 20, 20), c + 0.9, c + 3 + h, 0.6)
    elif kind in ("tar", "tar_s"):
        r = 9 if kind == "tar" else 6
        wob = math.sin(f * 1.5) * 0.8
        p.ell((30, 26, 30), c, c + 1, r * 2 + wob, r * 1.7 - wob)
        p.ell((70, 66, 74), c - r * 0.35, c - r * 0.3, r * 0.6, r * 0.4)
        p.circ((240, 200, 60), c - r * 0.3, c, max(1, r * 0.15))
        p.circ((240, 200, 60), c + r * 0.3, c, max(1, r * 0.15))
    elif kind == "rachok":
        return enemy_lobster_small(f, flag)
    elif kind == "bronch":
        p.circ((180, 80, 100), c, c + 2, 10)
        p.circ((210, 110, 130), c, c, 8)
        p.circ((120, 30, 50), c, c, 4 + (1.5 if flag else 0))
        p.circ((60, 10, 20), c, c, 2 + (1 if flag else 0))
    elif kind == "cell":
        h = -2 if f % 2 else 0
        p.ell((230, 150, 170), c, c + h, 18, 16)
        p.ell((170, 70, 110), c + 1, c + h, 7, 6)
        p.circ((30, 20, 30), c - 4, c - 3 + h, 1)
        p.circ((30, 20, 30), c + 4, c - 3 + h, 1)
    elif kind == "ghost":
        wv = math.sin(f * 1.2) * 1.5
        p.poly((230, 230, 246), [(c - 8, c), (c + 8, c), (c + 8, c + 10), (c + 5, c + 8 + wv), (c + 2, c + 10), (c - 1, c + 8 - wv), (c - 4, c + 10), (c - 8, c + 8)])
        p.circ((230, 230, 246), c, c - 2, 8)
        p.circ((20, 20, 40), c - 3, c - 3, 1.6)
        p.circ((20, 20, 40), c + 3, c - 3, 1.6)
        f2 = pygame.font.Font(None, 16)
        s.blit(f2.render("П", False, (60, 20, 30)), (c - 4, c - 1))
    elif kind == "wisp":
        fl = (255, 150, 40) if not flag else (120, 200, 255)
        fl2 = (255, 230, 120) if not flag else (230, 250, 255)
        p.poly(fl, [(c - 6, c + 4), (c, c - 10 - (f % 2) * 2), (c + 6, c + 4), (c, c + 8)])
        p.circ(fl, c, c + 3, 6)
        p.circ(fl2, c, c + 3, 3.5)
        p.circ((40, 20, 10), c - 1.6, c + 2, 0.8)
        p.circ((40, 20, 10), c + 1.6, c + 2, 0.8)
    elif kind == "phone":
        sh = (1 if f % 2 else -1) if flag else 0
        p.rect((40, 40, 46), c - 9 + sh, c - 4, 18, 11, rad=3)
        p.rect((30, 30, 34), c - 10 + sh, c - 8, 20, 4, rad=2)
        p.circ((200, 200, 200), c + sh, c + 1.5, 3.5)
        p.circ((40, 40, 46), c + sh, c + 1.5, 1.5)
        if flag:
            p.arc((255, 230, 80), c, c - 9, 22, 12, 0.3, math.pi - 0.3, 0.8)
    elif kind == "bluecat":
        s2 = pygame.Surface((14, 12), pygame.SRCALPHA)
        q = Pen(s2, 1)
        q.ell((120, 170, 255), 7, 8, 10, 6)
        q.circ((120, 170, 255), 7, 4.5, 3.6)
        q.poly((120, 170, 255), [(4, 3), (4.5, 0), (6.5, 2)])
        q.poly((120, 170, 255), [(10, 3), (9.5, 0), (7.5, 2)])
        q.circ((255, 255, 255), 5.8, 4.5, 0.7)
        q.circ((255, 255, 255), 8.2, 4.5, 0.7)
        return outline(s2, (40, 60, 140))
    elif kind == "minikostya":
        return person_frames("kostya", "down", f, 0.6)
    elif kind == "fairy":
        p.circ((255, 240, 160), c, c, 3.6)
        p.ell((200, 240, 255, 200), c - 4, c - 3 + (f % 2), 5, 4)
        p.ell((200, 240, 255, 200), c + 4, c - 3 + (f % 2), 5, 4)
    else:
        p.circ((200, 0, 200), c, c, 8)
    return outline(s)


def enemy_lobster_small(f, angry):
    s = draw_lobster(0.62, f, angry)
    return s


# ---------------------------------------------------------------- снаряды
def tear_sprite(col, r, kind="tear"):
    r = max(2, int(r))
    return cached(("tear", col, r, kind), lambda: _tear_build(col, r, kind))


def _tear_build(col, r, kind):
    s = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
    c = r + 2
    if kind == "ball":
        pygame.draw.circle(s, (30, 30, 30), (c, c), r + 1)
        pygame.draw.circle(s, (250, 250, 250), (c, c), r)
        for a in range(5):
            x, y = from_ang(a * 1.25, r * 0.55)
            pygame.draw.circle(s, (30, 30, 30), (int(c + x), int(c + y)), max(1, r // 4))
        return s
    if kind == "axe":
        pygame.draw.line(s, (120, 80, 40), (c - r, c + r), (c + r, c - r), 2)
        pygame.draw.polygon(s, (200, 200, 210), [(c + r - 2, c - r), (c + r + 1, c - r + 4), (c + 1, c - 2)])
        return s
    if kind == "bullet":
        pygame.draw.circle(s, (120, 90, 20), (c, c), r)
        pygame.draw.circle(s, col, (c, c), max(1, r - 1))
        return s
    dark = col_mul(col, 0.55)
    pygame.draw.circle(s, dark, (c, c), r + 1)
    pygame.draw.circle(s, col, (c, c), r)
    pygame.draw.circle(s, col_mul(col, 1.3), (c - r // 3, c - r // 3), max(1, r // 2))
    pygame.draw.circle(s, (255, 255, 255), (c - r // 3, c - r // 3), max(1, r // 4))
    return s


def bullet_sprite(kind, col, r):
    return cached(("blt", kind, col, int(r)), lambda: _bullet_build(kind, col, int(r)))


_SMALL_FONT = None


def _sfont(sz):
    return pygame.font.Font(None, sz)


def _bullet_build(kind, col, r):
    sz = r * 2 + 6
    s = pygame.Surface((sz, sz), pygame.SRCALPHA)
    c = sz // 2
    if kind == "letter":
        f = _sfont(int(r * 3.2))
        t = f.render("П", False, col)
        o = f.render("П", False, (30, 0, 0))
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            s.blit(o, (c - t.get_width() // 2 + dx, c - t.get_height() // 2 + dy + 1))
        s.blit(t, (c - t.get_width() // 2, c - t.get_height() // 2 + 1))
        return s
    if kind == "cross":
        w = max(2, r // 2)
        pygame.draw.rect(s, (90, 70, 20), (c - w // 2 - 1, c - r - 1, w + 2, r * 2 + 2))
        pygame.draw.rect(s, (90, 70, 20), (c - r * 2 // 3 - 1, c - r // 2 - 1, r * 4 // 3 + 2, w + 2))
        pygame.draw.rect(s, col, (c - w // 2, c - r, w, r * 2))
        pygame.draw.rect(s, col, (c - r * 2 // 3, c - r // 2, r * 4 // 3, w))
        return s
    if kind == "nail":
        pygame.draw.polygon(s, (90, 60, 80), [(c - r - 1, c), (c, c - r // 2 - 1), (c + r + 1, c), (c, c + r // 2 + 1)])
        pygame.draw.polygon(s, col, [(c - r, c), (c, c - r // 2), (c + r, c), (c, c + r // 2)])
        pygame.draw.circle(s, (255, 255, 255), (c - 1, c - 1), 1)
        return s
    if kind == "dice":
        pygame.draw.rect(s, (30, 30, 30), (c - r - 1, c - r - 1, r * 2 + 2, r * 2 + 2), border_radius=2)
        pygame.draw.rect(s, col, (c - r, c - r, r * 2, r * 2), border_radius=2)
        for (dx, dy) in ((-0.5, -0.5), (0.5, 0.5), (0, 0), (0.5, -0.5), (-0.5, 0.5)):
            pygame.draw.circle(s, (30, 30, 30), (int(c + dx * r), int(c + dy * r)), max(1, r // 4))
        return s
    if kind == "pencil":
        pygame.draw.rect(s, (40, 30, 10), (c - 2, c - r - 1, 5, r * 2 + 2))
        pygame.draw.rect(s, col, (c - 1, c - r, 3, r * 2 - 3))
        pygame.draw.polygon(s, (240, 200, 160), [(c - 1, c + r - 3), (c + 1, c + r), (c + 2, c + r - 3)])
        return s
    if kind == "fire":
        pygame.draw.circle(s, (180, 40, 0), (c, c), r + 1)
        pygame.draw.circle(s, col, (c, c), r)
        pygame.draw.circle(s, (255, 240, 150), (c, c), max(1, r // 2))
        return s
    if kind == "feather":
        pygame.draw.ellipse(s, (120, 120, 140), (c - r - 1, c - r // 2 - 1, r * 2 + 2, r + 2))
        pygame.draw.ellipse(s, col, (c - r, c - r // 2, r * 2, r))
        pygame.draw.line(s, (180, 180, 200), (c - r, c), (c + r, c), 1)
        return s
    if kind == "fish":
        pygame.draw.ellipse(s, (40, 40, 60), (c - r - 1, c - r // 2 - 1, r * 2 + 2, r + 2))
        pygame.draw.ellipse(s, col, (c - r, c - r // 2, r * 2, r))
        pygame.draw.polygon(s, col, [(c - r, c), (c - r - 3, c - 3), (c - r - 3, c + 3)])
        pygame.draw.circle(s, (20, 20, 20), (c + r // 2, c - 1), 1)
        return s
    if kind == "bubble":
        pygame.draw.circle(s, (40, 80, 160), (c, c), r + 1)
        pygame.draw.circle(s, col, (c, c), r)
        pygame.draw.circle(s, (255, 255, 255), (c - r // 3, c - r // 3), max(1, r // 3))
        return s
    if kind == "claw":
        pygame.draw.arc(s, (60, 0, 0), (c - r - 1, c - r - 1, r * 2 + 2, r * 2 + 2), 0.3, 2.8, 4)
        pygame.draw.arc(s, col, (c - r, c - r, r * 2, r * 2), 0.3, 2.8, 2)
        return s
    if kind == "star":
        pts = []
        for k in range(10):
            a = -math.pi / 2 + k * math.pi / 5
            rr = r if k % 2 == 0 else r * 0.45
            pts.append((c + math.cos(a) * rr, c + math.sin(a) * rr))
        pygame.draw.polygon(s, (120, 80, 0), [(x + 1, y + 1) for x, y in pts])
        pygame.draw.polygon(s, col, pts)
        return s
    # обычная "кровавая" пуля
    dark = col_mul(col, 0.45)
    pygame.draw.circle(s, dark, (c, c), r + 1)
    pygame.draw.circle(s, col, (c, c), r)
    pygame.draw.circle(s, col_mul(col, 1.4), (c - r // 3, c - r // 3), max(1, r // 3))
    return s


# ---------------------------------------------------------------- пикапы
def pickup_sprite(kind, frame=0):
    return cached(("pk", kind, frame % 8), lambda: _pickup_build(kind, frame % 8))


def heart_shape(p, col, x, y, sc=1.0, half=False, outline_c=None):
    pts = []
    for k in range(40):
        t = k / 40 * math.pi * 2
        hx_ = 16 * math.sin(t) ** 3
        hy_ = -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t))
        pts.append((x + hx_ * sc / 3, y + hy_ * sc / 3))
    if half:
        pts = [pt for pt in pts if pt[0] <= x + 0.01] + [(x, y + 5 * sc)]
    p.poly(col, pts)


def _pickup_build(kind, f):
    s = pygame.Surface((18, 18), pygame.SRCALPHA)
    p = Pen(s, 1)
    if kind in ("coin", "nickel"):
        col = (250, 200, 50) if kind == "coin" else (200, 210, 220)
        w = [10, 8, 4, 2, 4, 8, 10, 10][f]
        p.ell(col_mul(col, 0.7), 9, 9.5, w, 10)
        p.ell(col, 9, 9, max(1, w - 2), 8)
        if w > 4:
            p.line(col_mul(col, 1.3), (8, 6), (8, 11), 0.7)
    elif kind == "key":
        p.circ((230, 190, 40), 9, 5, 3.4)
        p.circ((0, 0, 0, 0), 9, 5, 1.3)
        p.rect((230, 190, 40), 8, 7, 2.2, 9)
        p.rect((230, 190, 40), 10, 12, 3, 1.6)
        p.rect((230, 190, 40), 10, 14.5, 2, 1.4)
    elif kind == "bomb":
        p.circ((40, 40, 46), 9, 10, 6)
        p.circ((100, 100, 110), 7, 8, 1.8)
        p.rect((120, 90, 60), 8, 2, 2, 3)
        p.circ((255, 200, 60) if f % 2 else (255, 120, 40), 9.5, 2, 1.2)
    elif kind == "heart":
        heart_shape(p, (220, 30, 40), 9, 9, 0.85)
        p.circ((255, 140, 140), 6, 6.5, 1.3)
    elif kind == "half":
        heart_shape(p, (220, 30, 40), 9, 9, 0.85, half=True)
    elif kind == "soul":
        heart_shape(p, (90, 140, 230), 9, 9, 0.85)
        p.circ((200, 220, 255), 6, 6.5, 1.3)
    elif kind == "battery":
        p.rect((60, 200, 90), 5, 4, 8, 12, rad=1)
        p.rect((200, 200, 200), 7, 2, 4, 2)
        p.line((255, 255, 255), (9, 7), (9, 13), 1)
    return outline(s)


def hud_heart(kind):
    def build():
        s = pygame.Surface((13, 12), pygame.SRCALPHA)
        p = Pen(s, 1)
        if kind == "empty":
            heart_shape(p, (60, 20, 24), 6.5, 6, 0.65)
        elif kind == "full":
            heart_shape(p, (226, 34, 44), 6.5, 6, 0.65)
            p.circ((255, 150, 150), 4, 4, 1)
        elif kind == "half":
            heart_shape(p, (60, 20, 24), 6.5, 6, 0.65)
            heart_shape(p, (226, 34, 44), 6.5, 6, 0.65, half=True)
        elif kind == "soul":
            heart_shape(p, (96, 146, 236), 6.5, 6, 0.65)
            p.circ((210, 230, 255), 4, 4, 1)
        elif kind == "soulhalf":
            heart_shape(p, (96, 146, 236), 6.5, 6, 0.65, half=True)
        return outline(s)
    return cached(("hh", kind), build)


# ---------------------------------------------------------------- предметы (иконки 16x16)
def item_icon(iid):
    return cached(("item", iid), lambda: outline(_item_build(iid)))


def _item_build(iid):
    s = pygame.Surface((18, 18), pygame.SRCALPHA)
    p = Pen(s, 1)
    fn = ICON_FN.get(iid)
    if fn:
        fn(p)
    else:
        p.circ((200, 200, 200), 9, 9, 6)
        f = _sfont(16)
        s.blit(f.render("?", False, (40, 40, 40)), (6, 3))
    return s


def _i_soap(p):
    p.rect((250, 200, 220), 3, 6, 12, 7, rad=3)
    p.ell((255, 240, 250), 7, 8, 4, 2)
    p.circ((200, 230, 255), 13, 4, 1.6)
    p.circ((200, 230, 255), 15, 2, 1)


def _i_food(p):
    p.rect((250, 220, 90), 3, 3, 12, 13, rad=1)
    p.rect((220, 60, 60), 3, 3, 12, 3)
    p.circ((150, 150, 160), 9, 11, 3)
    p.poly((150, 150, 160), [(6.5, 9), (7, 6.5), (8.5, 8.5)])
    p.poly((150, 150, 160), [(11.5, 9), (11, 6.5), (9.5, 8.5)])


def _i_card(p):
    p.rect((240, 230, 200), 4, 2, 10, 14, rad=1)
    p.rect((200, 160, 40), 5, 3, 8, 12, wd=0.8)
    p.poly((220, 180, 40), [(6, 9), (7, 6), (9, 8), (11, 6), (12, 9)])
    p.rect((220, 180, 40), 6, 9, 6, 2)


def _i_shard(p):
    p.poly((180, 40, 60), [(9, 1), (14, 7), (11, 16), (6, 14), (4, 6)])
    p.poly((255, 110, 140), [(9, 2), (12, 7), (9, 13), (6, 7)])
    p.line((255, 220, 230), (8, 4), (7, 8), 0.7)


def _i_rifle(p):
    p.rect((60, 60, 66), 1, 7, 15, 3)
    p.rect((120, 80, 40), 1, 8, 5, 5)
    p.rect((60, 60, 66), 8, 10, 2, 5)
    p.rect((40, 40, 44), 10, 10, 3, 3)


def _i_cup(p):
    p.poly((250, 200, 50), [(4, 2), (14, 2), (12, 9), (6, 9)])
    p.rect((250, 200, 50), 8, 9, 2, 4)
    p.rect((200, 150, 40), 5, 13, 8, 3)
    p.arc((250, 200, 50), 4, 5, 5, 6, 1.5, 4.7, 1)
    p.arc((250, 200, 50), 14, 5, 5, 6, -1.6, 1.6, 1)


def _i_cig(p):
    p.rect((245, 245, 245), 2, 8, 11, 3)
    p.rect((220, 150, 70), 2, 8, 4, 3)
    p.rect((255, 120, 40), 13, 8, 2, 3)
    p.circ((180, 180, 180), 15, 5, 1.6)
    p.circ((200, 200, 200), 14, 2, 1.2)


def _i_ball(p):
    p.circ((250, 250, 250), 9, 9, 7)
    p.poly((30, 30, 30), [(9, 6), (11.5, 8), (10.5, 11), (7.5, 11), (6.5, 8)])
    p.circ((30, 30, 30), 4, 6, 1.2)
    p.circ((30, 30, 30), 14, 6, 1.2)
    p.circ((30, 30, 30), 9, 15, 1.2)


def _i_sheet(p):
    p.rect((240, 230, 200), 3, 2, 12, 14)
    for k in range(4):
        p.line((150, 120, 90), (5, 5 + k * 3), (13, 5 + k * 3), 0.6)
    p.circ((200, 40, 40), 12, 13, 1.4)


def _i_robe(p):
    p.poly((90, 50, 160), [(9, 1), (15, 16), (3, 16)])
    p.circ((255, 220, 90), 9, 9, 1.3)
    p.circ((255, 220, 90), 7, 13, 0.8)
    p.circ((255, 220, 90), 11, 12, 0.8)


def _i_apple(p):
    p.circ((220, 40, 40), 7, 10, 5)
    p.circ((220, 40, 40), 11, 10, 5)
    p.line((100, 70, 30), (9, 5), (10, 2), 1)
    p.ell((80, 170, 60), 12, 3, 4, 2)
    p.circ((255, 150, 150), 6, 8, 1.2)


def _i_belt(p):
    p.arc((90, 60, 30), 9, 9, 14, 14, 0.5, 5.8, 2)
    p.rect((220, 200, 120), 12, 6, 4, 5, wd=1)


def _i_stutter(p):
    f = _sfont(15)
    for k, x in enumerate((1, 6, 11)):
        p.s.blit(f.render("П", False, (220 - k * 40, 60, 60)), (x, 2 + k * 2))


def _i_claws(p):
    for k in range(3):
        p.arc((230, 230, 230), 6 + k * 3, 9, 6, 14, 1.6, 3.6, 1)
    p.ell((150, 150, 158), 9, 14, 10, 5)


def _i_finger(p):
    p.rect((180, 150, 140), 6, 2, 6, 14, rad=3)
    p.line((40, 30, 30), (7, 6), (11, 6), 0.8)
    p.line((40, 30, 30), (7, 10), (11, 10), 0.8)
    p.rect((60, 40, 40), 7, 2, 4, 3, rad=1)


def _i_catnip(p):
    p.ell((80, 170, 70), 6, 8, 6, 9)
    p.ell((80, 170, 70), 12, 8, 6, 9)
    p.line((50, 110, 40), (9, 16), (9, 4), 1)


def _i_fur(p):
    for k in range(6):
        a = k * 1.05
        p.circ((170, 170, 178), 9 + math.cos(a) * 4, 9 + math.sin(a) * 4, 3)
    p.circ((190, 190, 198), 9, 9, 4)


def _i_halo(p):
    p.ell((255, 220, 90), 9, 9, 15, 8, 2)


def _i_thorns(p):
    p.ell((120, 90, 40), 9, 9, 14, 10, 1.5)
    for k in range(8):
        a = k * math.pi / 4
        x, y = 9 + math.cos(a) * 7, 9 + math.sin(a) * 5
        p.line((120, 90, 40), (x, y), (x + math.cos(a) * 2, y + math.sin(a) * 2), 0.7)


def _i_cross(p):
    p.rect((250, 220, 120), 7.5, 1, 3, 16)
    p.rect((250, 220, 120), 3, 5, 12, 3)


def _i_wings(p):
    p.poly((250, 250, 255), [(9, 9), (1, 3), (2, 10), (4, 14)])
    p.poly((250, 250, 255), [(9, 9), (17, 3), (16, 10), (14, 14)])


def _i_holywater(p):
    p.rect((180, 210, 255), 5, 6, 8, 10, rad=2)
    p.rect((200, 200, 200), 7, 3, 4, 3)
    p.rect((250, 250, 255), 8, 9, 2, 5)
    p.rect((250, 250, 255), 6.5, 10.5, 5, 1.6)


def _i_lens(p):
    p.circ((180, 220, 250), 7, 7, 5)
    p.circ((60, 60, 70), 7, 7, 5, 1.2)
    p.line((90, 60, 30), (11, 11), (16, 16), 2)


def _i_physbook(p):
    p.rect((40, 110, 180), 3, 3, 12, 13, rad=1)
    p.rect((240, 240, 230), 4, 4, 2, 11)
    f = _sfont(12)
    p.s.blit(f.render("E=mc", False, (255, 255, 255)), (5, 6))


def _i_energy(p):
    p.rect((40, 200, 90), 5, 2, 8, 14, rad=2)
    p.poly((20, 20, 20), [(10, 4), (6, 10), (9, 10), (8, 15), (12, 8), (9, 8)])


def _i_shawarma(p):
    p.poly((230, 200, 140), [(3, 15), (8, 2), (15, 12)])
    p.poly((200, 80, 60), [(6, 10), (8, 5), (11, 10)])
    p.circ((90, 170, 70), 9, 9, 1.2)


def _i_doshik(p):
    p.rect((240, 70, 50), 3, 5, 12, 10, rad=1)
    p.rect((250, 230, 150), 4, 3, 10, 3)
    p.lines((250, 230, 150), [(5, 2), (6, 0), (7, 2), (8, 0)], 0.7)


def _i_dachakey(p):
    p.circ((190, 190, 200), 6, 6, 4)
    p.circ((0, 0, 0, 0), 6, 6, 1.5)
    p.line((190, 190, 200), (8, 8), (15, 15), 2)
    p.line((190, 190, 200), (12, 12), (14, 10), 1.5)
    p.rect((90, 160, 80), 1, 1, 4, 3)


def _i_phone(p):
    p.rect((30, 30, 36), 5, 1, 8, 16, rad=2)
    p.rect((90, 150, 230), 6, 3, 6, 10)
    p.circ((200, 200, 200), 9, 15, 0.8)


def _i_axe(p):
    p.line((120, 80, 40), (4, 16), (12, 3), 2)
    p.poly((200, 200, 210), [(10, 1), (17, 4), (14, 9), (11, 6)])


def _i_fireball(p):
    p.circ((255, 120, 20), 9, 10, 6)
    p.poly((255, 120, 20), [(4, 9), (9, 0), (14, 9)])
    p.circ((255, 230, 120), 9, 11, 3)


def _i_ring(p):
    p.ell((230, 230, 240), 9, 10, 12, 10, 1.6)
    p.circ((250, 120, 200), 9, 5, 2)


def _i_glasses(p):
    p.rect((220, 40, 40), 1, 6, 7, 5, rad=1)
    p.rect((40, 120, 230), 10, 6, 7, 5, rad=1)
    p.rect((30, 30, 30), 1, 6, 16, 1.2)


def _i_triple(p):
    for k, x in enumerate((4, 9, 14)):
        p.circ((120, 180, 255), x, 9 - (2 if k == 1 else 0), 2.5)


def _i_magnet(p):
    p.arc((220, 40, 40), 9, 7, 12, 12, math.pi, 2 * math.pi, 3)
    p.rect((220, 40, 40), 3, 7, 3, 6)
    p.rect((220, 40, 40), 12, 7, 3, 6)
    p.rect((220, 220, 220), 3, 12, 3, 3)
    p.rect((220, 220, 220), 12, 12, 3, 3)


def _i_gum(p):
    p.circ((255, 140, 200), 9, 9, 6)
    p.circ((255, 200, 230), 7, 7, 2)


def _i_backpack(p):
    p.rect((150, 90, 50), 3, 4, 12, 12, rad=3)
    p.rect((120, 70, 40), 5, 9, 8, 5, rad=1)
    p.arc((90, 60, 30), 9, 5, 6, 6, 0, math.pi, 1)


def _i_dicebag(p):
    p.ell((130, 60, 160), 9, 11, 12, 10)
    p.rect((130, 60, 160), 6, 3, 6, 4)
    p.line((255, 220, 90), (6, 6), (12, 6), 0.8)


def _i_shark(p):
    p.poly((250, 250, 250), [(4, 3), (14, 3), (9, 16)])
    p.line((200, 200, 210), (9, 5), (9, 13), 0.6)


def _i_chalk(p):
    p.rect((250, 250, 245), 3, 7, 12, 4, rad=1)
    p.line((200, 200, 200), (6, 7), (6, 11), 0.5)


def _i_jersey(p):
    p.poly((220, 44, 44), [(4, 3), (7, 2), (11, 2), (14, 3), (16, 7), (13, 8), (13, 16), (5, 16), (5, 8), (2, 7)])
    f = _sfont(12)
    p.s.blit(f.render("10", False, (255, 255, 255)), (5, 6))


def _i_mentos(p):
    p.rect((60, 30, 20), 5, 4, 8, 12, rad=2)
    p.rect((40, 20, 10), 7, 1, 4, 3)
    p.circ((250, 250, 250), 14, 13, 2.5)


def _i_brim(p):
    p.ell((250, 250, 250), 9, 9, 14, 9)
    p.circ((180, 20, 20), 9, 9, 3.6)
    p.circ((20, 0, 0), 9, 9, 1.6)
    p.line((200, 30, 30), (2, 9), (5, 7), 0.6)


def _i_pointer(p):
    p.rect((60, 60, 70), 2, 8, 9, 3, rad=1)
    p.line((255, 40, 40), (11, 9.5), (17, 9.5), 1)
    p.circ((255, 120, 120), 16, 9.5, 1.3)


def _i_pentagram(p):
    pts = [(9 + math.cos(-math.pi / 2 + k * 4 * math.pi / 5) * 7, 9 + math.sin(-math.pi / 2 + k * 4 * math.pi / 5) * 7) for k in range(6)]
    p.lines((200, 30, 30), pts, 1)


def _i_sock(p):
    p.poly((250, 230, 100), [(5, 2), (11, 2), (11, 11), (15, 12), (15, 16), (5, 16)])
    p.circ((60, 160, 60), 8, 12, 1.3)


def _i_heartc(p):
    heart_shape(p, (226, 34, 44), 9, 9, 0.9)


def _i_compass(p):
    p.circ((200, 200, 210), 9, 9, 7)
    p.poly((220, 40, 40), [(9, 3), (11, 9), (7, 9)])
    p.poly((60, 60, 70), [(9, 15), (11, 9), (7, 9)])


def _i_map(p):
    p.rect((230, 210, 160), 2, 3, 14, 12)
    p.rect((140, 100, 60), 5, 6, 3, 3)
    p.rect((140, 100, 60), 8, 9, 3, 3)
    p.rect((140, 100, 60), 11, 6, 3, 3)


def _i_boot(p):
    p.poly((30, 30, 30), [(4, 2), (10, 2), (10, 11), (16, 12), (16, 16), (4, 16)])
    p.line((250, 250, 250), (5, 15), (15, 15), 0.6)


def _i_mirror(p):
    p.ell((180, 220, 240), 9, 7, 10, 12)
    p.ell((120, 80, 40), 9, 7, 10, 12, 1)
    p.rect((120, 80, 40), 8, 13, 2, 4)


def _i_d20(p):
    p.poly((240, 60, 60), [(9, 1), (16, 5), (16, 13), (9, 17), (2, 13), (2, 5)])
    p.poly((255, 120, 120), [(9, 4), (13, 11), (5, 11)])
    f = _sfont(11)
    p.s.blit(f.render("20", False, (255, 255, 255)), (5, 7))


def _i_shrink(p):
    p.circ((200, 200, 255), 9, 9, 7, 1)
    p.circ((120, 120, 255), 9, 9, 2.5)
    for a in range(4):
        x, y = from_ang(a * math.pi / 2 + math.pi / 4, 6)
        p.line((120, 120, 255), (9 + x, 9 + y), (9 + x * 0.5, 9 + y * 0.5), 1)


def _i_domain(p):
    p.line((200, 200, 220), (3, 15), (13, 3), 1.6)
    p.line((140, 90, 40), (3, 15), (5, 13), 2)
    p.rect((250, 220, 120), 11, 6, 2.5, 10)
    p.rect((250, 220, 120), 8.5, 9, 7.5, 2.2)


def _i_rulebook(p):
    p.rect((120, 30, 30), 3, 2, 12, 14, rad=1)
    p.poly((255, 220, 90), [(9, 4), (10.5, 8), (14, 8), (11, 10.5), (12, 14), (9, 11.5), (6, 14), (7, 10.5), (4, 8), (7.5, 8)])


def _i_firecrackers(p):
    for k, x in enumerate((4, 8, 12)):
        p.rect((220, 40, 40), x, 5 + k, 3, 10)
        p.line((250, 220, 90), (x + 1.5, 5 + k), (x + 2.5, 2 + k), 0.7)


def _i_call(p):
    p.rect((240, 240, 240), 4, 2, 10, 14, rad=2)
    p.rect((90, 200, 120), 5, 4, 8, 9)
    p.poly((255, 255, 255), [(7, 6), (11, 8.5), (7, 11)])


def _i_bread(p):
    p.ell((220, 170, 100), 9, 10, 15, 10)
    p.ell((240, 200, 140), 9, 9, 11, 6)


def _i_anubis(p):
    p.line((230, 230, 240), (3, 15), (15, 3), 2)
    p.line((120, 80, 40), (2, 16), (5, 13), 2.4)
    p.line((250, 200, 60), (4, 11), (7, 14), 1.4)


def _i_lucky(p):
    for a in range(4):
        x, y = from_ang(a * math.pi / 2, 3.5)
        p.circ((80, 190, 80), 9 + x, 8 + y, 3)
    p.line((60, 140, 60), (9, 10), (11, 16), 1)


def _i_tooth(p):
    _i_shark(p)


ICON_FN = {
    "soap": _i_soap, "food": _i_food, "card": _i_card, "shard": _i_shard, "rifle": _i_rifle, "cup": _i_cup, "cig": _i_cig,
    "ball": _i_ball, "sheet": _i_sheet, "robe": _i_robe, "apple": _i_apple, "belt": _i_belt, "stutter": _i_stutter,
    "claws": _i_claws, "finger": _i_finger, "catnip": _i_catnip, "fur": _i_fur, "halo": _i_halo, "thorns": _i_thorns,
    "cross": _i_cross, "wings": _i_wings, "holywater": _i_holywater, "lens": _i_lens, "physbook": _i_physbook,
    "energy": _i_energy, "shawarma": _i_shawarma, "doshik": _i_doshik, "dachakey": _i_dachakey, "phone": _i_phone,
    "axe": _i_axe, "fireball": _i_fireball, "ring": _i_ring, "glasses": _i_glasses, "triple": _i_triple, "magnet": _i_magnet,
    "gum": _i_gum, "backpack": _i_backpack, "dicebag": _i_dicebag, "shark": _i_shark, "chalk": _i_chalk, "jersey": _i_jersey,
    "mentos": _i_mentos, "brim": _i_brim, "pointer": _i_pointer, "pentagram": _i_pentagram, "sock": _i_sock,
    "heartc": _i_heartc, "compass": _i_compass, "map": _i_map, "boot": _i_boot, "mirror": _i_mirror,
    "d20": _i_d20, "shrink": _i_shrink, "domain": _i_domain, "rulebook": _i_rulebook, "firecrackers": _i_firecrackers,
    "call": _i_call, "bread": _i_bread, "anubis": _i_anubis, "lucky": _i_lucky,
}


# ---------------------------------------------------------------- шрифты/текст
class Fonts:
    def __init__(self):
        self.cache = {}

    def get(self, size, bold=False):
        k = (size, bold)
        f = self.cache.get(k)
        if f is None:
            f = pygame.font.Font(None, size)
            f.set_bold(bold)
            self.cache[k] = f
        return f


FONTS = None


def text(s, size=28, col=(255, 255, 255), outline_col=(0, 0, 0), ow=2, bold=False):
    key = ("txt", s, size, col, outline_col, ow, bold)
    r = _SPR.get(key)
    if r is not None:
        return r
    f = FONTS.get(size, bold)
    t = f.render(s, True, col)
    if outline_col is None:
        out = t
    else:
        o = f.render(s, True, outline_col)
        out = pygame.Surface((t.get_width() + ow * 2, t.get_height() + ow * 2), pygame.SRCALPHA)
        for dx in range(-ow, ow + 1):
            for dy in range(-ow, ow + 1):
                if dx * dx + dy * dy <= ow * ow + 1 and (dx or dy):
                    out.blit(o, (ow + dx, ow + dy))
        out.blit(t, (ow, ow))
    if len(_SPR) < 60000:
        _SPR[key] = out
    return out


def blit_center(dst, surf, x, y):
    dst.blit(surf, (int(x - surf.get_width() / 2), int(y - surf.get_height() / 2)))


# --- эмодзи
EMOJI = {
    "😈": "devil", "😊": "smile", "😃": "smile", "😄": "smile", "🙂": "smile", "😌": "smile", "😭": "cry", "😢": "cry",
    "💀": "skull", "🤩": "star", "😧": "shock", "😨": "shock", "😱": "shock", "🙏": "pray", "😜": "tongue", "😝": "tongue",
    "😋": "tongue", "🤪": "tongue", "😍": "love", "🤫": "shh", "👍": "thumb", "🔥": "fire",
}


def emoji_icon(name, h):
    def build():
        sz = max(10, h)
        s = pygame.Surface((sz, sz), pygame.SRCALPHA)
        u = sz / 16.0
        p = Pen(s, u)
        if name == "skull":
            p.circ((240, 240, 240), 8, 7, 6.5)
            p.rect((240, 240, 240), 5, 10, 6, 5, rad=1)
            p.circ((20, 20, 20), 5.5, 7, 1.8)
            p.circ((20, 20, 20), 10.5, 7, 1.8)
            p.poly((20, 20, 20), [(8, 9), (7, 11), (9, 11)])
        elif name == "pray":
            p.poly((250, 210, 150), [(8, 1), (4, 9), (5, 15), (8, 13), (11, 15), (12, 9)])
            p.line((200, 150, 100), (8, 2), (8, 13), 0.7)
        elif name == "thumb":
            p.rect((250, 210, 150), 3, 7, 10, 8, rad=2)
            p.rect((250, 210, 150), 5, 1, 4, 8, rad=2)
        elif name == "fire":
            p.poly((255, 120, 30), [(3, 11), (8, 0), (13, 11), (8, 16)])
            p.circ((255, 220, 100), 8, 11, 3)
        else:
            face = (250, 200, 40) if name != "devil" else (150, 60, 200)
            if name == "devil":
                p.poly(face, [(2, 6), (2, 0), (6, 3)])
                p.poly(face, [(14, 6), (14, 0), (10, 3)])
            p.circ(face, 8, 8.5, 7)
            e = (40, 20, 10)
            if name == "star":
                _star(p, (255, 255, 255), 5, 7, 2.4)
                _star(p, (255, 255, 255), 11, 7, 2.4)
                _star(p, (240, 60, 40), 5, 7, 1.8)
                _star(p, (240, 60, 40), 11, 7, 1.8)
                p.arc(e, 8, 10, 8, 5, math.pi, 2 * math.pi, 1)
            elif name == "love":
                heart_shape(p, (230, 30, 50), 5, 7, 0.25)
                heart_shape(p, (230, 30, 50), 11, 7, 0.25)
                p.arc(e, 8, 10, 8, 5, math.pi, 2 * math.pi, 1)
            elif name == "cry":
                p.line(e, (3.5, 6.5), (6.5, 7), 1)
                p.line(e, (12.5, 6.5), (9.5, 7), 1)
                p.rect((80, 160, 250), 4, 7, 2, 7)
                p.rect((80, 160, 250), 10, 7, 2, 7)
                p.ell(e, 8, 12, 5, 3)
            elif name == "shock":
                p.circ(e, 5.5, 7, 1.2)
                p.circ(e, 10.5, 7, 1.2)
                p.ell(e, 8, 12, 3.4, 4)
            elif name == "tongue":
                p.line(e, (4, 6), (7, 7.5), 1)
                p.circ(e, 10.5, 6.5, 1.3)
                p.arc(e, 8, 10, 8, 5, math.pi, 2 * math.pi, 1)
                p.ell((240, 90, 110), 9, 13, 3.6, 3.4)
            elif name == "shh":
                p.circ(e, 5.5, 7, 1.2)
                p.circ(e, 10.5, 7, 1.2)
                p.rect((250, 210, 150), 7, 9, 2.5, 7)
            elif name == "devil":
                p.line(e, (4, 5), (7, 7), 1)
                p.line(e, (12, 5), (9, 7), 1)
                p.circ(e, 6, 7.5, 1)
                p.circ(e, 10, 7.5, 1)
                p.arc(e, 8, 9.5, 9, 6, math.pi, 2 * math.pi, 1)
            else:
                p.circ(e, 5.5, 7, 1.2)
                p.circ(e, 10.5, 7, 1.2)
                p.arc(e, 8, 9.5, 8, 6, math.pi, 2 * math.pi, 1)
        return s
    return cached(("emoji", name, h), build)


def _tokenize(txt):
    """-> список токенов: ('w', слово) ('e', emoji) ('s', пробел) ('n', перенос)"""
    toks = []
    cur = ""
    i = 0
    while i < len(txt):
        ch = txt[i]
        if ch in "️‍":
            i += 1
            continue
        if ch in EMOJI:
            if cur:
                toks.append(("w", cur))
                cur = ""
            toks.append(("e", EMOJI[ch]))
        elif ord(ch) > 0xFFFF or (0x2600 <= ord(ch) <= 0x27BF):
            # неизвестный эмодзи -> смайлик
            if cur:
                toks.append(("w", cur))
                cur = ""
            toks.append(("e", "smile"))
        elif ch == " ":
            if cur:
                toks.append(("w", cur))
                cur = ""
            toks.append(("s", " "))
        elif ch == "\n":
            if cur:
                toks.append(("w", cur))
                cur = ""
            toks.append(("n", ""))
        else:
            cur += ch
        i += 1
    if cur:
        toks.append(("w", cur))
    return toks


_LAYOUT = {}


def layout_text(txt, size, width):
    key = (txt, size, width)
    lay = _LAYOUT.get(key)
    if lay is not None:
        return lay
    f = FONTS.get(size)
    lh = f.get_linesize()
    space = f.size(" ")[0]
    lines = [[]]
    x = 0
    n_chars = 0
    for kind, val in _tokenize(txt):
        if kind == "n":
            lines.append([])
            x = 0
            continue
        if kind == "s":
            if x > 0:
                x += space
            n_chars += 1
            continue
        if kind == "e":
            w = lh
        else:
            w = f.size(val)[0]
        if x + w > width and x > 0:
            # длинное слово режем
            lines.append([])
            x = 0
        if kind == "w" and w > width:
            # очень длинное слово (ААААА) - режем по буквам
            chunk = ""
            for chh in val:
                if f.size(chunk + chh)[0] > width - x:
                    lines[-1].append(("w", chunk, x, n_chars))
                    n_chars += len(chunk)
                    lines.append([])
                    x = 0
                    chunk = ""
                chunk += chh
            val = chunk
            w = f.size(val)[0]
        lines[-1].append((kind, val, x, n_chars))
        n_chars += len(val) if kind == "w" else 1
        x += w
    lay = (lines, lh, n_chars)
    _LAYOUT[key] = lay
    return lay


def draw_rich(dst, txt, size, x, y, width, col=(255, 255, 255), reveal=None, shake=0.0, t=0.0, wave=False):
    lines, lh, total = layout_text(txt, size, width)
    f = FONTS.get(size)
    for li, line in enumerate(lines):
        for (kind, val, lx, start) in line:
            if reveal is not None and start >= reveal:
                return total
            if kind == "e":
                ic = emoji_icon(val, int(lh * 0.9))
                dst.blit(ic, (x + lx, y + li * lh + 1))
            else:
                v = val
                if reveal is not None and start + len(val) > reveal:
                    v = val[:max(0, int(reveal - start))]
                if not v:
                    continue
                if shake or wave:
                    cx = x + lx
                    for k, ch in enumerate(v):
                        ox = oy = 0
                        if shake:
                            ox = random.uniform(-shake, shake)
                            oy = random.uniform(-shake, shake)
                        if wave:
                            oy += math.sin(t * 6 + (start + k) * 0.5) * 2
                        g = f.render(ch, True, (0, 0, 0))
                        dst.blit(g, (cx + ox + 1, y + li * lh + oy + 2))
                        g = f.render(ch, True, col)
                        dst.blit(g, (cx + ox, y + li * lh + oy))
                        cx += f.size(ch)[0]
                else:
                    sh = f.render(v, True, (0, 0, 0))
                    dst.blit(sh, (x + lx + 1, y + li * lh + 2))
                    dst.blit(f.render(v, True, col), (x + lx, y + li * lh))
    return total


# --- крошечный пиксельный шрифт для HUD
_DIG = {
    "0": "111101101101111", "1": "010110010010111", "2": "111001111100111", "3": "111001111001111", "4": "101101111001001",
    "5": "111100111001111", "6": "111100111101111", "7": "111001010010010", "8": "111101111101111", "9": "111101111001111",
    "x": "000101010101000", "/": "001001010100100", "-": "000000111000000", "+": "000010111010000", "?": "111001011000010",
}


def draw_digits(dst, s, x, y, col=(255, 255, 255), sc=1):
    for ch in s:
        pat = _DIG.get(ch)
        if pat:
            for i, b in enumerate(pat):
                if b == "1":
                    px, py = i % 3, i // 3
                    pygame.draw.rect(dst, (0, 0, 0), (x + px * sc + 1, y + py * sc + 1, sc, sc))
            for i, b in enumerate(pat):
                if b == "1":
                    px, py = i % 3, i // 3
                    pygame.draw.rect(dst, col, (x + px * sc, y + py * sc, sc, sc))
        x += 4 * sc


# ---------------------------------------------------------------- фоны / биомы
BIOMES = {
    "apartment": dict(floor="parquet", fc=(150, 104, 70), wall="wallpaper", wc=(136, 128, 92), door=(110, 70, 40), rock="box", vign=0.55, parts="dust"),
    "school": dict(floor="tiles", fc=(176, 172, 150), fc2=(128, 136, 124), wall="paint", wc=(84, 136, 110), door=(120, 90, 60), rock="desk", vign=0.45, parts="dust"),
    "lungs": dict(floor="flesh", fc=(168, 70, 82), wall="fleshwall", wc=(118, 38, 54), door=(150, 50, 70), rock="lump", vign=0.6, parts="smoke"),
    "dark": dict(floor="parquet", fc=(74, 46, 56), wall="wallpaper", wc=(60, 40, 64), door=(70, 40, 40), rock="box", vign=0.8, parts="ember"),
    "heaven": dict(floor="clouds", fc=(222, 230, 250), wall="cloudwall", wc=(240, 226, 170), door=(240, 210, 120), rock="cloudrock", vign=0.2, parts="sparkle"),
    "throne": dict(floor="marble", fc=(236, 226, 200), wall="gold", wc=(200, 160, 70), door=(220, 180, 80), rock="cloudrock", vign=0.35, parts="sparkle"),
    "catdomain": dict(floor="scratch", fc=(70, 20, 26), wall="temple", wc=(30, 14, 18), door=(90, 20, 20), rock="box", vign=0.7, parts="ember"),
    "hall": dict(floor="hall", fc=(232, 202, 112), wall="pillars", wc=(206, 170, 90), door=(160, 120, 60), rock="box", vign=0.35, parts="sparkle"),
    "void": dict(floor="void", fc=(10, 10, 14), wall="void", wc=(4, 4, 6), door=(30, 30, 30), rock="box", vign=0.5, parts="none"),
    "prison": dict(floor="concrete", fc=(118, 116, 112), wall="bricks", wc=(90, 84, 80), door=(80, 80, 86), rock="box", vign=0.6, parts="dust"),
    "home": dict(floor="parquet", fc=(176, 124, 84), wall="wallpaper", wc=(186, 170, 130), door=(130, 84, 50), rock="box", vign=0.35, parts="dust"),
}


def _np_noise(w, h, cell, seed):
    rs = np.random.RandomState(seed)
    gw, gh = max(2, w // cell + 2), max(2, h // cell + 2)
    g = rs.rand(gw, gh).astype(np.float32)
    small = pygame.surfarray.make_surface(np.dstack([g * 255] * 3).astype(np.uint8))
    big = pygame.transform.smoothscale(small, (w + cell * 2, h + cell * 2))
    a = pygame.surfarray.array3d(big)[cell:cell + w, cell:cell + h, 0].astype(np.float32) / 255.0
    return a


def make_background(biome_name, seed=0):
    b = BIOMES[biome_name]
    W, H = WW, WH
    X, Y = np.meshgrid(np.arange(W), np.arange(H), indexing="ij")
    img = np.zeros((W, H, 3), dtype=np.float32)
    n1 = _np_noise(W, H, 24, seed + 1)
    n2 = _np_noise(W, H, 6, seed + 2)
    n3 = _np_noise(W, H, 60, seed + 3)
    fc = np.array(b["fc"], dtype=np.float32)
    fl = b["floor"]
    shade = np.ones((W, H), dtype=np.float32)
    if fl == "parquet":
        ph = 8
        row = (Y // ph)
        rs = np.random.RandomState(seed + 5)
        offs = rs.randint(0, 40, size=H // ph + 2)
        plank_len = 40
        pid = ((X + offs[row]) // plank_len) + row * 37
        var = (np.sin(pid * 12.9898) * 43758.5453) % 1.0
        shade = 0.82 + var * 0.28
        seam = ((Y % ph) == 0) | (((X + offs[row]) % plank_len) == 0)
        shade = np.where(seam, 0.62, shade)
        grain = np.sin((X * 0.35 + n2 * 6 + var * 30)) * 0.04
        shade = shade + grain
    elif fl == "tiles":
        t = 16
        chk = ((X // t) + (Y // t)) % 2
        c2 = np.array(b["fc2"], dtype=np.float32)
        img[...] = np.where(chk[..., None] == 0, fc, c2)
        grout = ((X % t) == 0) | ((Y % t) == 0)
        shade = np.where(grout, 0.75, 1.0)
        fc = None
    elif fl == "flesh":
        v = np.abs(np.sin(X * 0.08 + n1 * 9 + Y * 0.03))
        vein = (v < 0.06).astype(np.float32)
        shade = 0.85 + n1 * 0.3 - vein * 0.35 + (n2 - 0.5) * 0.15
    elif fl == "clouds":
        shade = 0.88 + n1 * 0.18 + n3 * 0.08
    elif fl == "marble":
        v = np.abs(np.sin(X * 0.05 + n1 * 8 + Y * 0.02))
        shade = 0.9 + n3 * 0.1 - (v < 0.04) * 0.2
        tiles = ((X % 48) == 0) | ((Y % 48) == 0)
        shade = np.where(tiles, 0.8, shade)
        carpet = (np.abs(X - W / 2) < 40) & (Y > RY0)
        img[...] = fc
        img[carpet] = np.array((150, 30, 40), dtype=np.float32)
        edge = (np.abs(np.abs(X - W / 2) - 38) < 2) & (Y > RY0)
        img[edge] = np.array((230, 190, 80), dtype=np.float32)
        fc = None
    elif fl == "scratch":
        shade = 0.8 + n1 * 0.4
        for k in range(14):
            rs = np.random.RandomState(seed + 100 + k)
            x0, y0 = rs.randint(RX0, RX1), rs.randint(RY0, RY1)
            a = rs.uniform(0, math.pi)
            for j in range(3):
                d = (X - x0 - j * 5) * math.sin(a) - (Y - y0) * math.cos(a)
                along = (X - x0) * math.cos(a) + (Y - y0) * math.sin(a)
                m = (np.abs(d) < 1.0) & (np.abs(along) < 30)
                shade = np.where(m, 0.35, shade)
    elif fl == "hall":
        t = 32
        chk = ((X // t) + (Y // t)) % 2
        shade = np.where(chk == 0, 1.0, 0.86)
        shade = shade + (n3 - 0.5) * 0.08
        light = np.clip(1 - np.abs(((X + Y * 0.5) % 120) - 60) / 60.0, 0, 1)
        shade = shade + light * 0.06
    elif fl == "void":
        shade = 1.0 + ((X % 32 == 0) | (Y % 32 == 0)) * 1.8
    elif fl == "concrete":
        shade = 0.82 + n1 * 0.25 + (n2 - 0.5) * 0.12
        crack = np.abs(np.sin(X * 0.03 + n1 * 12)) < 0.015
        shade = np.where(crack, 0.6, shade)
    if fc is not None:
        img[...] = fc
    img *= shade[..., None]
    img *= (0.94 + n2[..., None] * 0.1)
    # --- стены
    wc = np.array(b["wc"], dtype=np.float32)
    wall = (X < RX0) | (X >= RX1) | (Y < RY0) | (Y >= RY1)
    wt = b["wall"]
    ws = 0.9 + n1 * 0.15
    if wt == "wallpaper":
        ws = ws + (np.sin(X * 0.8) > 0.6) * 0.06 + (((X + Y) % 12 == 0) & ((X - Y) % 12 == 0)) * 0.15
    elif wt == "paint":
        ws = ws + ((Y % 10) == 0) * -0.12
    elif wt == "fleshwall":
        ws = ws + np.sin(Y * 0.4 + n1 * 5) * 0.08
    elif wt in ("gold", "pillars"):
        ws = ws + ((X % 40) < 8) * 0.15 - ((X % 40) == 8) * 0.25
    elif wt == "bricks":
        rowb = Y // 8
        br = (((X + (rowb % 2) * 8) % 16) == 0) | ((Y % 8) == 0)
        ws = np.where(br, 0.65, ws)
    elif wt == "temple":
        ws = ws + ((X % 48) < 4) * 0.4
    elif wt == "cloudwall":
        ws = 0.92 + n1 * 0.2
    elif wt == "void":
        ws = np.ones_like(n1)
    wimg = wc[None, None, :] * ws[..., None]
    img = np.where(wall[..., None], wimg, img)
    # перспектива: верх стены темнее, к полу светлее
    dtop = np.clip((RY0 - Y) / RY0, 0, 1)
    img = np.where(((Y < RY0) & (X >= 0))[..., None], img * (1 - dtop[..., None] * 0.45), img)
    # плинтус
    edge = ((Y >= RY0 - 3) & (Y < RY0) & (X >= RX0 - 3) & (X < RX1 + 3)) | ((X >= RX0 - 3) & (X < RX0) & (Y >= RY0) & (Y < RY1)) | \
           ((X >= RX1) & (X < RX1 + 3) & (Y >= RY0) & (Y < RY1)) | ((Y >= RY1) & (Y < RY1 + 3) & (X >= RX0 - 3) & (X < RX1 + 3))
    img = np.where(edge[..., None], img * 0.55, img)
    # тень от стен на полу
    sh = np.zeros((W, H), dtype=np.float32)
    sh += np.clip(1 - (Y - RY0) / 14.0, 0, 1) * ((Y >= RY0) & (Y < RY1))
    sh += np.clip(1 - (X - RX0) / 10.0, 0, 1) * ((X >= RX0) & (X < RX1)) * 0.6
    sh += np.clip(1 - (RX1 - X) / 10.0, 0, 1) * ((X >= RX0) & (X < RX1)) * 0.6
    img = img * (1 - np.clip(sh, 0, 1)[..., None] * 0.35 * (~wall)[..., None])
    # угловые стыки стен
    for (cx, cy) in ((RX0, RY0), (RX1, RY0), (RX0, RY1), (RX1, RY1)):
        d = (np.abs((X - cx)) - np.abs((Y - cy)))
        m = (np.abs(d) < 1) & wall & (np.abs(X - cx) < 40) & (np.abs(Y - cy) < 40)
        img = np.where(m[..., None], img * 0.7, img)
    img = np.clip(img, 0, 255).astype(np.uint8)
    surf = pygame.surfarray.make_surface(img)
    return surf


def make_vignette(strength):
    def build():
        X, Y = np.meshgrid(np.arange(WW), np.arange(WH), indexing="ij")
        dx = (X - WW / 2) / (WW / 2)
        dy = (Y - WH / 2) / (WH / 2)
        d = np.sqrt(dx * dx * 0.9 + dy * dy * 1.1)
        a = np.clip((d - 0.55) / 0.75, 0, 1) ** 1.6 * 255 * strength
        s = pygame.Surface((WW, WH), pygame.SRCALPHA)
        arr = pygame.surfarray.pixels_alpha(s)
        arr[...] = a.astype(np.uint8)
        del arr
        rgb = pygame.surfarray.pixels3d(s)
        rgb[...] = 0
        del rgb
        return s
    return cached(("vign", round(strength, 2)), build)


# ---------------------------------------------------------------- препятствия
def rock_sprite(style, variant=0, tinted_=False):
    return cached(("rock", style, variant, tinted_), lambda: _rock_build(style, variant, tinted_))


def _rock_build(style, v, tinted_):
    s = pygame.Surface((32, 32), pygame.SRCALPHA)
    p = Pen(s, 1)
    rs = random.Random(v * 13 + 5)
    if style == "box":
        c = (186, 140, 90) if not tinted_ else (150, 170, 210)
        p.rect(col_mul(c, 0.7), 3, 6, 26, 24, rad=2)
        p.rect(c, 3, 4, 26, 22, rad=2)
        p.rect(col_mul(c, 0.85), 3, 4, 26, 6)
        p.rect((220, 200, 150), 14, 4, 4, 22)
        if v % 2:
            p.rect((140, 100, 60), 7, 16, 6, 4)
    elif style == "desk":
        c = (150, 110, 70) if not tinted_ else (150, 170, 210)
        p.rect((60, 60, 70), 5, 18, 3, 12)
        p.rect((60, 60, 70), 24, 18, 3, 12)
        p.rect(col_mul(c, 0.7), 2, 10, 28, 10, rad=2)
        p.rect(c, 2, 7, 28, 10, rad=2)
        p.line((100, 70, 40), (6, 10), (14, 12), 0.6)
    elif style == "lump":
        c = (196, 96, 112) if not tinted_ else (160, 170, 220)
        p.ell(col_mul(c, 0.65), 16, 20, 28, 20)
        p.ell(c, 16, 17, 26, 20)
        p.ell(col_mul(c, 1.2), 11, 12, 8, 5)
        p.circ(col_mul(c, 0.6), 20, 20, 2)
    elif style == "cloudrock":
        c = (250, 250, 255) if not tinted_ else (200, 220, 255)
        for (x, y, r) in ((10, 18, 8), (22, 18, 8), (16, 12, 9), (16, 21, 9)):
            p.circ(col_mul(c, 0.8), x, y + 2, r)
        for (x, y, r) in ((10, 18, 8), (22, 18, 8), (16, 12, 9), (16, 21, 9)):
            p.circ(c, x, y, r)
    else:
        c = (130, 130, 136) if not tinted_ else (120, 150, 210)
        pts = []
        for k in range(9):
            a = k / 9 * math.pi * 2
            r = rs.uniform(11, 14)
            pts.append((16 + math.cos(a) * r, 17 + math.sin(a) * r * 0.85))
        p.poly(col_mul(c, 0.6), [(x, y + 2) for x, y in pts])
        p.poly(c, pts)
        p.ell(col_mul(c, 1.25), 12, 12, 8, 5)
    if tinted_:
        p.line((60, 60, 120), (10, 12), (22, 22), 1.4)
        p.line((60, 60, 120), (22, 12), (10, 22), 1.4)
    return outline(s, th=1)


def block_sprite():
    def build():
        s = pygame.Surface((32, 32), pygame.SRCALPHA)
        p = Pen(s, 1)
        p.rect((70, 74, 84), 1, 3, 30, 28, rad=2)
        p.rect((120, 126, 140), 1, 1, 30, 26, rad=2)
        p.rect((150, 156, 170), 4, 4, 24, 20, rad=1)
        for (x, y) in ((6, 6), (26, 6), (6, 22), (26, 22)):
            p.circ((80, 84, 96), x, y, 1.3)
        return outline(s)
    return cached(("block",), build)


def poop_sprite(stage, gold=False):
    def build():
        s = pygame.Surface((32, 32), pygame.SRCALPHA)
        p = Pen(s, 1)
        c = (126, 78, 40) if not gold else (230, 190, 60)
        k = 1 - stage * 0.22
        layers = [(16, 26, 24 * k, 9 * k), (16, 20, 18 * k, 8 * k), (16, 14.5, 12 * k, 7 * k), (16, 10, 6 * k, 5 * k)]
        for i, (x, y, w, h) in enumerate(layers[:4 - stage] if stage < 3 else layers[:1]):
            p.ell(col_mul(c, 0.75), x, y + 1.5, w, h)
            p.ell(c, x, y, w, h)
            p.ell(col_mul(c, 1.25), x - w * 0.2, y - h * 0.2, w * 0.3, h * 0.3)
        if stage < 2:
            p.circ((255, 255, 255), 13, 17, 1.6)
            p.circ((255, 255, 255), 19, 17, 1.6)
            p.circ((20, 20, 20), 13, 17.4, 0.8)
            p.circ((20, 20, 20), 19, 17.4, 0.8)
        return outline(s)
    return cached(("poop", stage, gold), build)


def fire_sprite(frame, blue=False, small=1.0):
    def build():
        s = pygame.Surface((32, 32), pygame.SRCALPHA)
        p = Pen(s, 1)
        p.rect((90, 60, 30), 7, 24, 18, 4, rad=2)
        p.line((70, 40, 20), (8, 26), (24, 28), 2)
        c1 = (255, 120, 30) if not blue else (80, 140, 255)
        c2 = (255, 220, 100) if not blue else (200, 230, 255)
        h = 16 + (frame % 3) * 2
        k = small
        p.poly(c1, [(16 - 9 * k, 25), (16 - 4 * k, 25 - h * 0.6 * k), (16, 25 - h * k), (16 + 4 * k, 25 - h * 0.55 * k), (16 + 9 * k, 25)])
        p.poly(c2, [(16 - 5 * k, 25), (16, 25 - h * 0.6 * k), (16 + 5 * k, 25)])
        return outline(s, (90, 30, 0))
    return cached(("fire", frame % 3, blue, round(small, 1)), build)


def shadow_surf(w, h, a=90):
    def build():
        s = pygame.Surface((max(2, w), max(2, h)), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, a), s.get_rect())
        return s
    return cached(("shadow", w, h, a), build)


# ---------------------------------------------------------------- двери
def door_sprite(kind, d, state, biome):
    """state: 'open' | 'closed' | 'locked' | 'hidden' | 'bombed'"""
    return cached(("door", kind, d, state, biome), lambda: _door_build(kind, d, state, biome))


def _door_build(kind, d, state, biome):
    W, H = 40, 34
    s = pygame.Surface((W, H), pygame.SRCALPHA)
    p = Pen(s, 1)
    b = BIOMES[biome]
    fc = b["door"]
    if kind == "boss":
        fc = (120, 20, 24)
    elif kind == "treasure":
        fc = (230, 180, 50)
    elif kind == "shop":
        fc = (80, 140, 200)
    elif kind == "story":
        fc = (120, 70, 170)
    elif kind == "secret":
        fc = col_mul(b["wc"], 0.6)
    if state == "hidden":
        return s
    if kind == "secret":
        p.ell((20, 12, 12), 20, 22, 26, 22)
        p.poly(col_mul(b["wc"], 0.5), [(6, 22), (10, 12), (14, 16), (20, 9), (26, 15), (30, 11), (34, 22)], 2)
        return s
    p.rect(col_mul(fc, 0.6), 4, 4, 32, 30, rad=4)
    p.rect(fc, 6, 2, 28, 30, rad=4)
    p.rect((14, 8, 10), 11, 9, 18, 25, rad=3)
    if kind == "boss":
        for k in (-1, 1):
            p.poly((230, 220, 200), [(20 + k * 10, 6), (20 + k * 17, -1), (20 + k * 13, 9)])
        p.circ((230, 220, 200), 20, 6, 4)
        p.circ((20, 10, 10), 18.5, 6, 1)
        p.circ((20, 10, 10), 21.5, 6, 1)
    elif kind == "treasure":
        p.poly((255, 230, 120), [(14, 6), (17, 2), (20, 6), (23, 2), (26, 6)])
    elif kind == "shop":
        f = _sfont(14)
        s.blit(f.render("$", False, (255, 255, 255)), (17, 1))
    elif kind == "story":
        p.circ((230, 200, 255), 20, 5, 2.4)
    if state in ("closed", "locked"):
        p.rect(col_mul(fc, 0.8), 11, 9, 9, 25)
        p.rect(col_mul(fc, 0.7), 20, 9, 9, 25)
        p.line(col_mul(fc, 0.5), (20, 9), (20, 34), 1)
        if state == "locked":
            p.rect((230, 190, 40), 16, 18, 8, 7, rad=1)
            p.arc((230, 190, 40), 20, 18, 6, 7, 0, math.pi, 1.4)
            p.circ((60, 40, 10), 20, 21, 1)
    return outline(s, th=1)


def trapdoor_sprite(open_=True):
    def build():
        s = pygame.Surface((36, 30), pygame.SRCALPHA)
        p = Pen(s, 1)
        p.ell((60, 40, 30), 18, 16, 34, 26)
        p.ell((8, 6, 6), 18, 16, 28, 20)
        p.rect((80, 56, 36), 4, 2, 28, 5, rad=2)
        return s
    return cached(("trap", open_), build)


def pedestal_sprite():
    def build():
        s = pygame.Surface((26, 18), pygame.SRCALPHA)
        p = Pen(s, 1)
        p.rect((120, 120, 128), 3, 6, 20, 11, rad=2)
        p.rect((170, 170, 178), 1, 2, 24, 6, rad=2)
        p.rect((150, 150, 158), 5, 9, 16, 2)
        return outline(s)
    return cached(("pedestal",), build)


def light_glow(r, col, a=120):
    """Премультиплицированное свечение для BLEND_RGB_ADD."""
    r = max(2, int(r) // 2 * 2)
    a = max(0, min(255, int(a) // 16 * 16))

    def build():
        n = r * 2
        X, Y = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        d = np.sqrt((X - r + 0.5) ** 2 + (Y - r + 0.5) ** 2) / max(1, r)
        k = np.clip(1 - d, 0, 1) ** 1.8 * (a / 255.0)
        arr = np.zeros((n, n, 3), dtype=np.float32)
        for i in range(3):
            arr[..., i] = col[i] * k
        s = pygame.surfarray.make_surface(arr.astype(np.uint8))
        return s
    return cached(("glow", r, col, a), build)

# ============================================================================
#                               ДИАЛОГИ
#  Каждый диалог: who (портрет/голос), name, layers {n: dict(t=[строки], a=[ответы])}
#  Ответ: A(текст, go=следующий_слой|None, do=действие(я), cond=условие)
# ============================================================================
def A(t, go=None, do=None, cond=None):
    return dict(t=t, go=go, do=do, cond=cond)


def L(lines, answers, who=None):
    d = dict(t=lines if isinstance(lines, list) else [lines], a=answers)
    if who:
        d["who"] = who
    return d


SPEAKERS = {
    "kostya": ("Костян", "kostya"), "valerii": ("Валерий", "valerii"), "dymok": ("Дымок", "dymok"), "jesus": ("Иисус", "jesus"),
    "john": ("Джон", "john"), "sergei": ("Серёга Головко", "sergei"), "rak": ("???", "rak"), "ellen": ("Эллен Джо", "ellen"),
    "unknown": ("Неизвестный", "unknown"), "gaster": ("В.Д. Гастер", "gaster"), "daniil": ("Даниил Митрофанов", "daniil"),
    "artem": ("Артём", "artem"), "narr": ("", "narr"), "item": ("", "item"), "papa": ("Папа", "valerii"),
}
LINE_PREFIX = {"Гастер": "gaster", "Даниил": "daniil", "Артём": "artem", "Костян": "kostya", "Иисус": "jesus", "Валерий": "valerii"}

DLG = {}

# ---------------------------------------------------------------- пролог: звонок
DLG["kostik"] = dict(who="kostya", layers={
    1: L(["Ну до скорого, братуха", "Кстати, ДНД когда?"], [
        A("Ну, можно через 15 минут у меня, как раз никого нету.", 2),
        A("Давай у Леры", 3),
        A("Давай у Егора", 4),
        A("Мб без ДНД седня? Я как-то устал...", 5)]),
    2: L(["Давай, дружище! До скорого, бро! Я выхожу", "(kostet114 заходит в Блю Лок Оверлок Эго Ривалс)"], [
        A("Что-то это не к добру...", None, "start_f1")]),
    3: L(["А давай😈😈😋😍😝😜😜", "Я уже вышел, ключи у меня есть, не переживай😈😈😈🤫🤪"], [
        A("Что-то я передумал... Лучше у меня", None, "start_f1"),
        A("Пошли🤩", None, "ending:lera")]),
    4: L(["Давай😊", "А, блин, он написал, что не получится..."], [
        A("😭😭😭. Ну, у меня тогда", None, "start_f1")]),
    5: L(["Нет.", "Сегодня же моя игра. Я придумал самый гениальный шедевральный прекрасный чюдесный мир в ДНД, который ты видел. Если не будет ДНД, я буду забивать в Локе так же, как и ты. Специально"], [
        A("Нет лол", None, "ending:no_dnd"),
        A("😭😭😭. Ну, у меня тогда", None, "start_f1")]),
})

DLG["kostik_talked"] = dict(who="narr", layers={
    1: L(["(Костян играет в Блю Лок Оверлок Оверблю Эго Ривалс... уже 50 голов забил...)"], [
        A("Ладно, пойду, пожалуй, стол накрою, чтобы они его потом убирали😈")]),
})

# ---------------------------------------------------------------- Валерий (первая встреча)
DLG["valerii"] = dict(who="valerii", layers={
    1: L(["П-п-п-п-п-п-п-п-п-п-п-п-п-п-приветик, сыночек...", "Я решил не ехать на дачу, потому что там п-п-п-п-п-п-п-п-п-",
          "П-п-п-п-п-п-почему ты так на м-м-м-м-меня смотришь?"], [
        A("Брах, я уже на ДНД друзей позвал...", 2),
        A("Просто ты же говорил, что на дачу поедешь, вот я и позвал друзей...", 2)]),
    2: L(["А ч-ч-ч-ч-ч-чем я вам м-м-м-мешаю?", "Я точно не буду вмешиваться в вашу игру и п-п-п-п-подслушивать в-в-в-ваши тупые шутки",
          "Или м-м-м-можете у кого-то другого собраться?"], [
        A("Да нафиг пошёл, Папуня, глупенький ботик, урод!!!!", 4),
        A("А ты не можешь просто уйти? Ну, на дачу или на работу там...", 3)]),
    3: L(["Ты как с отцом разговариваешь, мелкий?", "А знаешь... Сегодня же т-т-т-т-твой день р-р-р-рождения", "Я дам т-т-т-тебе маленький шанс"], [
        A("И что мне нужно сделать?", 5)]),
    5: L(["Т-т-т-тебе нужно победить меня. Не бойся, я буду сдерживаться...", "Хотя даже так на п-п-п-п-победу у тебя очень маленький шанс", "Г-г-г-готов?"], [
        A("Готов...", None, "fight:val1"),
        A("Щас, я Дымка покормлю", None, "npckey:valerii_ready")]),
    4: L(["И КОГО Я ВЫРАСТИЛ!!! ТАК ГРУБИШЬ РОДИТЕЛЯМ, П-П-П-П-ПАСКУДА!!!", "НУ, Я ТЕБЯ П-П-П-П-ПОРОДИЛ, Я ТЕБЯ И УБЬЮ",
          "ЕСЛИ КОЕ-КАК ПОБЕДИШЬ, ТО Я СВАЛЮ ОТ ТЕБЯ!!!!"], [
        A("П-почему я слышу музыку босса?😧😧", None, "fight:val1")]),
})
DLG["valerii_ready"] = dict(who="valerii", layers={
    1: L(["Г-г-готов?"], [A("Да, Отец.", None, "fight:val1"), A("Ещё секунду...")]),
})

# ---------------------------------------------------------------- Дымок
DLG["sukuna"] = dict(who="dymok", layers={
    1: L(["Мяу мяу мяу... мяу мяу мяу мяу мяу мяу... (Как ты посмел потревожить мой покой, жалкий человечишка? Мне тебя убить, я не понял?)",
          "мяу мяу мяу (Ладно, за то, что ты такой терпила, я могу снизойти и пощадить тебя. Сгинь с глаз моих долой, ничтожество)"], [
        A("Дымок, нафиг пошёл, урод тупой", 2),
        A("Нифига, а как я понимаю язык котов нафиг", 3),
        A("Л-л-л-л-ладно, Господин...")]),
    2: L(["МЯУ МЯУ МЯУ МЯУМ МЯЯУУ МЯУ ГАВ МЯУ!!!!!! (ТЫ ЧЁ СКАЗАЛ, УРОДЕЦ ТУПОЙ?! Я ТВОЮ МАМУ ЦАРАПАЛ, КАРЛИК ТУПОЙ! МНЕ НАДОЕЛО НАФИГ!!!!)"], [
        A("Что-то это не к добру...", 4, "sfx:meow")]),
    3: L(["Мяу мяу мяу... мяу мяу мяу мяяяяяу мяу (Просто мне настолько не хочется видеть твоё лицо, особенно неисцарапанным, что я снизошёл до низшего существа вроде тебя и передал свои мысли тебе в голову)",
          "мяу мяу мяу, мяу мяу мяяяяу. (А теперь потеряйся, слабак...)"], [
        A("Я слабак? А не пойти ли тебе НАФИГ?!", 2),
        A("С-слушаюсь, босс...")]),
    4: L(["МЯУ МЯУ МЯУ: (РАСШИРЕНИЕ ТЕРРИТОРИИ:)", "МЯУ МЯУ МЯЯЯУ МЯУ!!! (ГРОБНИЦА ЦАРАПАНИЙ!!!)"], [
        A("Ой ой ой💀💀💀", None, "fight:dymok")]),
})
DLG["sukunacat"] = dict(who="dymok", layers={
    1: L(["Мяу мяу мяу... мяу мяу мяу... (КАК??? ТЫ СМОГ ПЕРЕЖИТЬ МОЙ ДОМЕЙН?!?!)", "мяу мяу мяу (Ладно, возможно, ты не так слаб...)"], [
        A("Дымок, нафиг пошёл, урод тупой, выпусти на волю, урод", 2),
        A("Спасибо😊", 3),
        A("Хм... А ведь если я тебя щас убью, то этих царапаний больше не будет...", 4)]),
    4: L(["МЯУ МЯУ???? М-МЯУ МЯУМ МЯЯУУ МЯУ МЯУ!!!!!! (Ч-ЧЕГО??? ТЫ НЕ МОЖЕШЬ ТАК ПОСТУПИТЬ!!! Я ДАМ ТЕБЕ ВСЁ, ЧТО ЗАХОЧЕШЬ!!! Держи... Это осколок моего ДОМЕЙНА)",
          "мяу мяу мяу (Я отпускаю тебя)", "МЯУ МЯУ МЯЯЯУ МЯУ!!! (Целый день даже царапать не буду)"], [
        A("Ладно... я прощаю тебя..", None, ["give:shard", "dymok:spared"]),
        A("Ты слишком много сделал, чтобы оставить тебя в живых, Дымок.", None, ["give:shard", "kill:dymok"])]),
    2: L(["Мяу мяу мяу мяу мяумяу (Ну ладно... Я могу убить тебя и перерезать всё... но твою силу воли мне не сломить... Держи в награду этот кристалл... Это осколок моего домейна)"], [
        A("ОЙ ОЙ ОЙ, Я СМОГУ ЕГО ЗАТРЕЙДИТЬ НА СТОЛЬКО КОТИКОВ!!!! СПС, ДЫМОК", 4, "give:shard")]),
    3: L(["Да не за что, хозяин😊. Но завтра покормишь меня, пожалуйста... Ты доказал свою силу и доброту... Возьми в награду этот ДОМЕЙН-осколок"], [
        A("Пока, Дымок, котик мой", None, ["give:shard", "dymok:spared"])]),
})
DLG["dymok_spared"] = dict(who="dymok", layers={1: L(["Мур. (Завтра покормишь, не забудь.)"], [A("Ага")])})

# ---------------------------------------------------------------- Неизвестный
DLG["unknown"] = dict(who="unknown", layers={
    1: L(["Не доверяй ему...", "Он лишь манипулирует тобой, чтобы не марать руки..."], [A("Тебя ударить?", 2)]),
    2: L(["Моё тело неосязаемо...", "Короче, ты поможешь мне?", "Только я могу помочь тебе получить истинный счастливый финал..."], [
        A("Чё?", 3), A("Ну ок", 3)]),
    3: L(["Короче, держи...", "Это карта ИМПЕРАТОРА... Она позволяет телепортироваться сразу к НАСТОЯЩЕМУ боссу... Но используй её, когда придёт время..."], [
        A("Ок", None, "give:card"), A("ОТСЫЛКА НА АЙЗЕКА!!!!", None, "give:card"), A("Лол, нет")]),
})
DLG["unknown_after"] = dict(who="unknown", layers={1: L(["...", "Когда придёт время — ты поймёшь."], [A("...")])})

# ---------------------------------------------------------------- предметы-находки
DLG["food"] = dict(who="item", layers={
    1: L(["Это корм. Коты его не едят, но едят раки", "Кот нарисован на упаковке, потому что так корм для раков покупают больше"], [
        A("Хм. Во урод на производителе. Возьму-ка.", None, "give:food"), A("Не, не надо")]),
})
DLG["milo"] = dict(who="item", layers={
    1: L(["Ты поднял мыло! Нафига?"], [A("Да понадобится в будущем наверняка, а теперь бежим нафиг", None, "give:soap")]),
})

# ---------------------------------------------------------------- Рай
DLG["jesus"] = dict(who="jesus", layers={
    1: L(["Да вы задолбали уже конкретно",
          "Один, значит, школу затопил, второй то же самое сделал. А потом они вместе убили Гринча, который ничего плохого в жизни не сделал. А сейчас какой-то грешный отца захотел убить. Но отец оказался сильнее"], [
        A("Здравствуйте, Господи Боже🙏🙏", 7),
        A("ЧЁ, Я УМЕР???", 6),
        A("Я атеист", 4),
        A("Вы... Вы поможете мне?", 5)]),
    5: L(["Давай😊", "Тебе никак не победить своего отца... Есть только один способ превзойти Валерия... Сделать невозможное... Ты же знаешь, какой праздник сегодня?"], [
        A("Мой день рождения!!!", 2), A("День Блю Лока", 2)]),
    2: L(["Неверно. Сегодня день отказа от курения", "Поэтому... чтобы справиться с отцом и получить силу... нужно заставить Сергея Головко отказаться от курения..."], [
        A("Это же невозможно...", 3)]),
    3: L(["Я дам тебе силу, которая поможет справиться с этим", "Удачи, воин"], [
        A("Она тут понадобится", None, ["give:shrink", "goto:school"])]),
    4: L(["Перед тобой буквально Иисус Христос стоит, а ты говоришь, что атеист", "Ну что, веришь в меня?"], [
        A("Ты ИИ", None, "goto:prison"), A("Да, верю", 6)]),
    6: L(["Твой отец убил тебя... у тебя не было ни шанса... Но я не хочу, чтобы ты умирал", "У тебя есть потенциал победить Валерия"], [
        A("Ты поможешь мне?", 5)]),
    7: L(["Здравствуй, сын мой... Я воскресил тебя, дабы ты искупил свои грехи...",
          "Валерий — самый опасный преступник мультивселенной... И только у тебя есть шансы победить его"], [
        A("Ты поможешь мне?", 5)]),
})
DLG["jesus_back"] = dict(who="jesus", layers={
    1: L(["Хм. Ты выбрался из небесной тюрьмы?..", "...С мылом?", "Ладно. Уважаю. Слушай сюда."], [A("Слушаю", None, "dlg:jesus:5")]),
})

# ---------------------------------------------------------------- Небесная тюрьма
DLG["john"] = dict(who="john", layers={
    1: L(["Ну что, мальчик?", "За что сидишь?"], [
        A("Д-д-д-да я папу не смог убить...", 3), A("Я Иисуса оскорбил", 3), A("Я забивать не умею", 3), A("Яна Цист", 3)]),
    3: L(["Ну... Неважно...", "Важно то, что отсюда ещё никто не выходил... Сидеть тебе тут вечно, малой."], [
        A("(Смириться...)", 2),
        A("Достать своё мыло!!!", 5, cond="has:soap")]),
    2: L(["(Проходят годы. Джон научил тебя играть в домино.)", "Ну что, Артём... ещё партейку?"], [A("Плохая концовка...", 4)]),
    4: L(["(Ты просыпаешься)", "Это был всего лишь сон... Но вещий ли он?"], [
        A("Надеюсь, что нет, пойду с Костиком поиграю", None, "ending:dream")], who="narr"),
    5: L(["ЧТО???? У ТЕБЯ БЫЛО СВОЁ МЫЛО!!!", "ПРОСТИТЕ, БОСС!!! ВЫ ОБЪЯВЛЯЕТЕСЬ БЛАТНЫМ!!! Дверь открыта, проходите, уважаемый!"], [
        A("Хорошая концовка!!!", None, "goto:heaven_back")]),
})

# ---------------------------------------------------------------- Школа: Серёга
_BROSAY = A("Бросай курить", 5)
DLG["sergei"] = dict(who="sergei", layers={
    1: L(["Здарова, Артемон, чё пришёл?"], [A("Капец тут дыма нафиг", 2), A("Здарова, брат", 3), _BROSAY]),
    2: L(["Моя работа"], [A("Круто"), A("А ты думаешь, как это на здоровье отразится?", 4), _BROSAY]),
    3: L(["Здарова, Артём"], [A("Здарова, Серёга", 3), A("Как ты думаешь, как курение отразится на твоём здоровье?", 4), _BROSAY]),
    4: L(["Ну, я сколько курю — особых проблем нету"], [A("А в 30 появятся!", 7), A("(Какую же способность мне дал Иисус?...)", 6), _BROSAY]),
    5: L(["Нет лол"], [A("Как ты думаешь, как курение отразится на твоём здоровье?", 4)]),
    6: L(["(Ты уменьшаться умеешь, лошара.) Чё молчишь, Артемон?"], [
        A("Как ты думаешь, как дышится с чистыми лёгкими?", 8), A("(Чё-то не понял...)", 6), _BROSAY]),
    7: L(["Ну а кубок мира я до 30 получу, а после уже пофиг"], [A("💀", 6), A("(Какую же способность мне дал Иисус?...)", 6), _BROSAY]),
    8: L(["Ну, кажется, ничё не изменится. Э ЭЭЭЭ ЭЭЭЭЭ."], [
        A("(Пока он делает это — уменьшиться и прыгнуть в рот)", None, "goto:lungs"), _BROSAY]),
})

# ---------------------------------------------------------------- раки
DLG["rak"] = dict(who="rak", layers={1: L(["Это рак. Убить?"], [A("Да", None, "rak_killed")])})
DLG["rak2"] = dict(who="rak", layers={1: L(["Это ПОСЛЕДНИЙ рак. Убить?"], [A("Да", None, "sergei:saved")])})
DLG["rak3"] = dict(who="rak", layers={1: L(["Это ПОСЛЕДНИЙ рак. Убить?"], [A("Да", None, "sergei:saved"), A("Накормить его😈", None, "sergei:killed")])})
DLG["sergei2"] = dict(who="sergei", layers={
    1: L(["Что это за чувство... Так чисто в горле... Я чувствую себя человеком... Спасибо тебе, Артём... Мне кажется, я понял, каково это — не курить..."], [
        A("Я рад, что ты понял это😊", None, ["give:jersey", "goto:heaven2"])]),
})
DLG["sergei3"] = dict(who="sergei", layers={
    1: L(["КХ КАХАХ КХХХХ", "Я... Кх... Не могу... Кх... Дышать....", "Я... Не смогу стать лучшим футболистом...?"], [
        A("Я рад, что ты понял это😈", None, ["kill:sergei", "goto:heaven2"])]),
})

# ---------------------------------------------------------------- Рай 2
DLG["jesus2"] = dict(who="jesus", layers={
    1: L(["Невероятно... Ты и вправду справился... Я очень рад за тебя, Артёмоша! Теперь ты удостоишься награды",
          "Я даровал тебе силу. Силу расширения территории... Пока ты не способен её закрывать, только открывать... В ней отец будет куда слабее... И у тебя будут шансы!",
          "Победи, Артём"], [A("Пришло время финальной схватки...", None, ["give:domain", "goto:f4"])]),
})
DLG["jesus3"] = dict(who="jesus", layers={
    1: L(["Эм... Ты... Ну ладно, по факту ты заставил его бросить курить...",
          "Я даровал тебе силу. Силу расширения территории... Пока ты не способен её закрывать, только открывать... В ней отец будет куда слабее... И у тебя будут шансы!",
          "Победи, Артём..."], [A("Пришло время убивать...", None, ["give:domain", "goto:f4"])]),
})

# ---------------------------------------------------------------- Валерий: финальная битва
DLG["val2"] = dict(who="valerii", layers={
    1: L(["Сынок? Так т-т-т-ты выжил? Какая радость!!!", "ВЕДЬ ТЕ-П-П-П-П-П-ПЕРЬ Я МОГУ УБИТЬ ТЕБЯ ВО ВТ-Т-Т-Т-ОРОЙ РАЗ!!!", "ПРОЩАЙ!!!"], [
        A("Расширение территории", 2)]),
    2: L(["ЧТО?? Р-Р-Р-Р-РАСШИРЕНИЕ ТЕРРИТОРИИ??? Т-Т-Т-Т-ТЫ ВРЁШЬ!!!"], [
        A("Кресты и мечи какие-то, ну как у Юты...", None, "fight:val2", cond="!geno"),
        A("Кресты и мечи как у Юты...", None, "fight:val2", cond="geno")]),
})


def _otec_dialog(shard, card, geno):
    lay = {}
    if geno:
        lay[1] = L(["Кхе... Ты... Смог... Я горжусь тобой...", "Знаешь, почему я остался дома?", "Я хотел подготовить тебе подарок на твой, кхе, день рождения..."], [
            A("...", 2, "music:histheme")])
        lay[2] = L(["Что это за странный взгляд? Хотя я это и увидел...", "Тебя манят приключения и битвы.",
                    "Поэтому я ни разу так и не убил тебя... Иисус не смог бы спасти тебя, убей я тебя сразу..."], [
            A("Понятно. Ты хотел умереть.", 3)])
    else:
        lay[1] = L(["Кхе... Ты... Смог... Я горжусь тобой...", "Знаешь, почему я остался дома?", "Я хотел подготовить тебе подарок на твой, кхе, день рождения..."], [
            A("Что?", 2, "music:histheme")])
        lay[2] = L(["Но я увидел огонь в твоих глазах и понял, что не обычные вещи манят, кхе, тебя...", "Тебя манят приключения и битвы.",
                    "Поэтому я ни разу так и не убил тебя... Иисус не смог бы спасти тебя, убей я тебя сразу..."], [
            A("Но тогда почему ты это делаешь? Ты думаешь, что, убив отца, я буду счастлив?!", 3)])
    lay[3] = L(["Нет... Я не ожидал, что ты получишь расширение территории... и потому я надеялся сдаться в конце... Но теперь тебе не выбраться... Если не убить меня...",
                "Можешь сказать напоследок...", "Ты прощаешь меня?"], [A("Я прощаю тебя...", 4), A("Я не прощаю тебя.", 5)])
    after_kill = 6 if card else None
    kill_do = ["kill:dad"] + ([] if card else ["goto:home_neutral"])
    if shard:
        lay[4] = L(["Я... Очень рад слышать это... Спасибо тебе, что был таким хорошим сыном", "Добей меня...",
                    "Иначе умрём и ты, и я... Эх... Даже яблочка перед смертью не поем..."], [A("???", 7, "music:musicbox")])
        lay[5] = L(["Ну... Видимо, таково моё наказание...", "Убей меня...", "Иначе умрём мы оба..."], [A("???", 7, "music:musicbox")])
        if geno:
            lay[7] = L(["У тебя в кармане... Что это сияет?", "Не может быть! Это же осколок домейна!!!", "Благодаря нему мы сможем сбежать даже вдвоём!!!"], [
                A("В каком смысле вдвоём?😈 (добить врага)", 9, ["kill:dad", "music:evil"])])
        else:
            lay[7] = L(["У тебя в кармане... Что это сияет?", "Не может быть! Это же осколок домейна!!!", "Благодаря нему мы сможем сбежать даже вдвоём!!!"], [
                A("В каком смысле вдвоём?😈 (добить папулю)", after_kill, kill_do),
                A("Я... Я должен спасти нас обоих!!!", 8)])
        lay[8] = L(["Да... Для этого тебе, кхе... нужно сильно сжать его в руке", "Он расколется... И мы вернёмся домой...", "Ты достаточно силён, чтобы сделать это!"], [
            A("Расколоть кристалл...", 10 if card else None, ["break_shard"] + ([] if card else ["goto:home_pacifist"]))])
        lay[10] = L(["Есть ещё одно невыполненное дело...", "Эта карта... Мне кажется, я понимаю, куда она меня приведёт...",
                     "Настоящий злодей в этой истории — это ты, Иисус!"], [A("(Использовать карту Императора)", None, "goto:throne")], who="artem")
    else:
        if geno:
            lay[4] = L(["Я... Очень рад слышать это... Спасибо тебе, что был таким хорошим сыном", "Добей меня...",
                        "Иначе умрём и ты, и я... Эх... Даже яблочка перед смертью не поем..."], [A("(Добить)", 9, ["kill:dad", "music:evil"])])
            lay[5] = L(["Ну... Видимо, таково моё наказание...", "Убей меня...", "Иначе умрём мы оба..."], [A("(Добить)", 9, ["kill:dad", "music:evil"])])
        else:
            lay[4] = L(["Я... Очень рад слышать это... Спасибо тебе, что был таким хорошим сыном", "Добей меня...",
                        "Иначе умрём и ты, и я... Эх... Даже яблочка перед смертью не поем..."], [A("Пока, папа...", after_kill, kill_do)])
            lay[5] = L(["Ну... Видимо, таково моё наказание...", "Убей меня...", "Иначе умрём мы оба..."], [A("(Добить)", after_kill, kill_do)])
    lay[6] = L(["Есть ещё одно невыполненное дело...", "Эта карта... Мне кажется, я понимаю, куда она меня приведёт...", "Я отомщу за папу... Иисус!!!!"], [
        A("(Использовать карту Императора)", None, "goto:throne")], who="artem")
    if card:
        lay[9] = L(["Я... Могу убить ещё больше...", "Хм. Эта карта...", "Мне кажется, скоро начнётся божественная трагедия😈"], [
            A("(Использовать карту Императора)", None, "goto:throne")], who="artem")
    else:
        lay[9] = L(["Я... Могу убить ещё больше...", "Хм. Чёрт... Видимо... Сейчас у меня нету доступа к другим врагам...", "Придётся начинать всё заново"], [
            A("(перезайди)", None, "ending:geno_abort")], who="artem")
    return dict(who="valerii", layers=lay)


# ---------------------------------------------------------------- Престол
DLG["jesusevil"] = dict(who="jesus", layers={
    1: L(["Хм. Кто ты?", "Как ты попал сюда?", "Твоя аура довольно сильна, похожа на ту, которая была у того жалкого ничтожества, что уже наверняка убил своего отца"], [
        A("Э, УРОД ТУПОЙ", 2)]),
    2: L(["ЧЁ???7", "Ты чё тут забыл нафиг?!", "Чёрт, надо было убить тебя сразу, как ты убил Валерия... К счастью, у тебя КД на домейне"], [
        A("Эй. Я тебя и без домейна уделаю. Видишь автомат?", 3, "give:rifle")]),
    3: L(["Хех...", "БУГАГАГАГАГАГАГАГАГА!!!", "ТЫ ДУМАЕШЬ, ЧТО СМОЖЕШЬ ПОБЕДИТЬ МЕНЯ?!?!"], [A("Конечно же.", 4), A("Очевидно же.", 4)]),
    4: L(["Ты вообще уродище!", "Ну всё...", "Мне надоело... НАЧНЁМ ЭТО!!!!"], [
        A("Прости, Айзек...", None, "fight:jesus"),
        A("Ну... Я мегасатану убил... Поэтому вроде карму очистил, чтобы мегаиисуса убить", None, "fight:jesus")]),
})
_JD1 = L(["Кх... ух... Невозможно...", "Как обычный человек может быть настолько силён?", "Ты... Точно человек?"], [A("Я хороший человек! Тот, что спасёт мир!", 2)])
_JD2 = L(["Валерий... Единственный, кто сдерживал меня от уничтожения вашего мира... Я думал, что его смерть или его ослабление поможет в осуществлении моего плана...",
          "Но его наследие... Ты...", "Ты превзошёл все мои ожидания..."], [A("Уя.", 3)])
DLG["jesusdead"] = dict(who="jesus", layers={
    1: _JD1, 2: _JD2,
    3: L(["Ну...", "Видимо, придётся оставить этот мир в покое", "Удачи тебе"], [
        A("Спасибо😃", None, ["kill:jesus", "goto:home_tn"]), A("А чё, то есть папа рил умер...", 4)]),
    4: L(["Ну... конечно же да", "Ты его добил нафиг", "Ну короче, зато мир жив будет"], [
        A("Блин.", None, ["kill:jesus", "goto:home_tn"]), A("Пупупу...", None, ["kill:jesus", "goto:home_tn"])]),
})
DLG["jesusdead3"] = dict(who="jesus", layers={
    1: _JD1, 2: _JD2,
    3: L(["Ну...", "Видимо, придётся оставить этот мир в покое", "Удачи тебе"], [
        A("Спасибо😃", None, ["kill:jesus", "goto:home_tp"]), A("Ну, главное, что теперь всё будет хорошо!", None, ["kill:jesus", "goto:home_tp"])]),
})
DLG["jesusdead2"] = dict(who="jesus", layers={
    1: L(["Кх... ух... Невозможно...", "Как обычный человек может быть настолько силён?", "Ты... Точно человек?"], [A("Не знаю", 2)]),
    2: L(["В твоих глазах... Ты уже не человек...", "Валерий... Твой сын...", "Видимо... Задачу по уничтожению мира я передам тебе..."], [
        A("Уя...", None, ["kill:jesus", "goto:home_geno"])]),
})

# ---------------------------------------------------------------- Дом
DLG["papulia"] = dict(who="valerii", layers={
    1: L(["Мы... Вернулись домой!", "Я так т-т-т-т-тобой горжусь", "Я через п-п-п-п-пять минут пойду."], [A("Правда?", 2)]),
    2: L(["И кстати...", "Ко мне должна была прийти дочь моей подруги", "Она в той комнате, проходи"], [A("Спасибо!!", 3, "open_door")]),
    3: L(["Ну, а п-п-п-пока. Я п-п-п-п-поздравляю тебя с днём рождения! Желаю тебе самого лучшего!"], [A("Спасибо, Папуля!"), A("Ага...")]),
})
DLG["papulia2"] = dict(who="valerii", layers={
    1: L(["Мы... Вернулись домой!", "Я так т-т-т-т-тобой горжусь", "Я через п-п-п-п-пять минут пойду."], [A("Я Иисуса грохнул...", 2)]),
    2: L(["Емаё", "Ты и вправду мой сын, Артём.", "Горжусь тобой. Как раз там одна девочка хотела поговорить с тобой, если ты п-п-п-п-понимаешь, о чём я..."], [
        A("Спасибо!!", 3, "open_door")]),
    3: L(["Ну, а п-п-п-пока. Я п-п-п-п-поздравляю тебя с днём рождения! Желаю тебе самого лучшего!"], [A("Спасибо, Папуля!"), A("Ага...")]),
})
_ELLEN = {
    1: L(["Ты же сын дяди Валеры?", "Не думала, что ты будешь... Настолько милым...", "ХМП! Я ничего такого не имела в виду, просто говорю, что вижу!"], [A("ЭТО ЖЕ ЭЛЛЕН ДЖО!!!!", 2)]),
    2: L(["Да. Я Эллен Джо!", "Знаешь...", "Д-давай будем друзьями"], [A("ДА!", 3), A("КОНЕЧНО ДА!", 3)]),
    3: L(["Ну, тогда давай... Прогуляемся?"], [A("ДАДАДАДАДАДАДАДДАДАДАДАДАДАД", None, "walk_out"), A("Ага...", None, "walk_out")]),
}
DLG["ellen"] = dict(who="ellen", layers=_ELLEN)
DLG["ellen2"] = dict(who="ellen", layers={
    1: L(["Т-ты... Убил их...", "Ты... Монстр...", "Я тебя... Унич..."], [A("...", 2)]),
    2: L(["Пожалуйста...", "Не убивай... Меня...", "Я сделаю... Что угодно... Только не убивай меня..."], [A("😜 (добить)", 3, "kill:ellen")]),
    3: L(["Тут уже все мертвы..", "Но я хочу большего!!!", "Хммм... Костя и остальные должны были подойти..."], [
        A("Я отомщу ему за призывателя и Сол...", None, "goto:hall")], who="artem"),
})
DLG["kostik2"] = dict(who="kostya", layers={
    1: L(["Я подошёл, выходи", "Ау", "Ответь, ботик"], [A("Я папу убил...", 2)]),
    2: L(["Да не боись, мы в любом случае лишь строчки кода", "Твой папа жив", "И в одной из комнат нету Эллен Джо"], [A("Чё?", 3), A("Тебя ударить, я не понял?", 3)]),
    3: L(["Ну ладно, открывай"], [A("Ок", None, "angel_rays"), A("Я лифтер", None, "angel_rays")]),
})
DLG["kostik3"] = dict(who="kostya", layers={
    1: L(["Я подошёл, выходи", "Ау", "Ответь, ботик"], [A("Я папу убил... И Иисуса!!!", 2)]),
    2: L(["Да не боись, мы в любом случае лишь строчки кода", "Твой папа жив, и Иисус", "И в одной из комнат нету Эллен Джо"], [A("Чё?", 3), A("Тебя ударить, я не понял?", 3)]),
    3: L(["Ну ладно, открывай"], [A("Ок", None, "ending:true_neutral"), A("Я лифтер", None, "ending:true_neutral")]),
})

# ---------------------------------------------------------------- Костян (геноцид)
DLG["sans"] = dict(who="kostya", layers={
    1: L(["Хм...", "Это правда ты, Артём?", "Да... Видимо, мне и вправду придётся сделать это..."], [
        A("(Использовать домейн)", 2), A("(Напасть)", None, "fight:kostya")]),
    2: L(["Хех... ", "Ты не заметил, что мы не в твоём подъезде?", "Или, кроме бесчисленных жертв, ты перед собой ничего не видишь?"], [
        A("Константин... Я убью тебя...", 3)]),
    3: L(["Бро думает, он главный герой💀", "Ну... Повезло, что я успел подняться и использовать домейн...", "Егор и Лера уже внизу... Я не дам тебе убить и их!"], [
        A("(Напасть)", None, "fight:kostya")]),
})
SANS_RETRY = [
    (["Хм, это плавда ты, Артём?", "Емаё, язык прикусил", "Ладно, давай заново"], ["..."]),
    (["Какой прекрасный денёк снаружи...", "Птички поют, цветочки благоухают", "В такие дни такие Артёмки, как ты,", "Должны сливаться уже в третий раз"], ["Да заколебал, уродище"]),
    (["Здравствуйте, сэр.", "Я пришёл... С докладом.", "А где твой напарник, Витя?"], ["Вити нет. Я его убил."]),
    (["Обиделся, обиделся на Таска, на призыв", "Обиделся, обиделся...", "Да нафиг оно пошло, я забыл"], ["Начнём, Гунер Кинг..."]),
    (["Хм. Это правда ты, Артём?", "Я знаю, как проверить", "Кто хуже: Гитлер или Эрен Йегер?"], ["Я."]),
    (["Боже, такой немощ", "Уже в 6 раз умер.", "Мемемемеме"], ["..."]),
    (["Чё ты так на меня смотришь?", "Словно я тебя убил 7 раз, лол", "Да шучу, как я могу тебя 7 раз убить"], ["Хватит уже."]),
    (["А ведь могли спокойно пойти в Иннополис...", "У тебя был бы свой Блю Лок...", "А у меня свой гарем.."], ["Не потрогаешь ты в жизни своей девушку, Костянчик."]),
    (["Бро, я б за это время уже Дымка успел бы грохнуть", "...", "Ну ты понял, типа уже 9 раз умер, у котов 9 жизней"], ["Да я тебя в десятый раз точно..."]),
    (["Вот подумай, зачем тебе убивать весь мир?", "Ты же знаешь...", "Кто будет смотреть Ламберджек Тайкун?"], ["Я и не хотел его выпускать, я просто надурил разрабов."]),
    (["Вот скажи честно.", "Надо оно тебе?", "Ты не сможешь победить, го просто жить мирно?"], ["Кстати, можно, если так подумать.", "Нет, одноклассник."]),
    (["Ты слабейший, потому что ты Артём Ромашко?", "Или ты Артём Ромашко, потому что ты слабейший?", "Ладно, у меня идеи кончились."], ["Да заколебал уже, читы выруби."]),
    (["И Сол, и леопард — такой у них азарт...", "Ля-ля-ля...", "О, ты вернулся.", "Продолжим?"], ["Щас точно получится."]),
]


def sans_retry_dialog(deaths):
    i = clamp(deaths - 1, 0, len(SANS_RETRY) - 1)
    lines, answers = SANS_RETRY[i]
    ans = []
    for a in answers:
        if a.startswith("Кстати, можно"):
            ans.append(A(a, None, "ending:peace"))
        else:
            ans.append(A(a, None, "fight:kostya"))
    return dict(who="kostya", layers={1: L(lines, ans)})


DLG["sans2"] = dict(who="kostya", layers={
    1: L(["Хе...", "Не можешь теперь попасть, ботик?", "Давай закончим всё это по-мужски!"], [A("Закончим это, Костет!", None, "kostya_phase2")]),
})
DLG["kostya_dead"] = dict(who="kostya", layers={
    1: L(["Кхе... Ну ты и ботик...", "Таск... Прости...", "Егор... Лера... бегите..."], [A("...", None, ["kill:kostya", "goto:void"])]),
})

# ---------------------------------------------------------------- Гастер и Даниил
DLG["gaster"] = dict(who="gaster", layers={
    1: L(["Ну чё, фраерок", "Понравилась моя сила?", "Наверняка понравилась, не так ли?"], [A("Кто ты?", 2), A("Очень", 3)]),
    2: L(["Моё имя...", "В И Н Г   Д И Н Г   Г А С Т Е Р", "Ну так что, понравилось?"], [A("Очень", 3), A("Да не особо как-то...", 3)]),
    3: L(["Интересно...", "Очень интересно...", "В определённый момент ты не мог противиться желанию убивать, я прав?"], [A("Ну да...", 4)]),
    4: L(["Значит, мой эксперимент не был провальным.", "Ты не чувствуешь вины за собой, не так ли?", "Иначе ты попытался бы убить меня."], [
        A("Нет. И я хочу убить ещё больше.", 5)]),
    5: L(["Идеально.", "Эксперимент №52 идёт полным ходом.", "Отныне ты будешь моим Доходягой."], [
        A("Да, Мистер Винг Динг", 6), A("(Сопротивляться)", 7, "sfx:warn")]),
    6: L(["Молодец.", "Теперь ты исполнишь мой план.", "Артём Ромашко, вместе мы уничтожим весь мир."], [
        A("Да, Господин Гастер.", None, "ending:gaster")]),
    7: L(["Хм?", "Почему ты молчишь?", "Не смей перечить мне, пешка."], [A("Простите, Мистер Винг Динг", 6), A("(Сопротивляться)", 8, "sfx:warn")]),
    8: L(["Что с тобой не так?!", "Почему ты молчишь, жалкое отребье?!", "СОГЛАШАЙСЯ СО МНОЙ, ИЛИ ТЫ БУДЕШЬ УНИЧТОЖЕН."], [
        A("Простите, Мистер Винг Динг", 6), A("(Сопротивляться)", 9, "shake")]),
    9: L(["...", "Ты думаешь, ты самый умный, не так ли?",
          "ВСЁ, ДЛЯ ЧЕГО ТЫ МНЕ НУЖЕН — ЭТО ДЛЯ СВОЕЙ ЖЕРТВЫ. ТЫ ЖАЛКИЙ РАБ, КОТОРОГО Я ИСПОЛЬЗУЮ ВО ИМЯ ТОГО, ЧТОБЫ ВЕРНУТЬСЯ ИЗ ЭТОЙ ЖАЛКОЙ ИГРЫ НА ПИТОНЕ В РЕАЛЬНЫЙ МИР!!!! У ТЕБЯ НЕТУ ВЫБОРА!!! ТЫ НЕ СМОЖЕШЬ ВЫЙТИ НА ХОРОШУЮ КОНЦОВКУ!!!!! ТЫ УЖЕ УБИЛ ВСЕХ!!! ТЫ. МОЙ. ДОХОДЯГА!!!! ТЫ ПОДЧИНЯЕШЬСЯ ЛИШЬ МНЕ!!! ТЫ ДАЖЕ НЕ СМОЖЕШЬ СБЕЖАТЬ ОТСЮДА!!!!!"], [
        A("... (принять судьбу)", 6), A("(Позвать на помощь)", 10)]),
    10: L(["Чего?..", "Ты... правда считаешь, что кто-то поможет тебе?...", "АХАХААХАХАХАХАХАХХАХАХАХАХА!!!!!!", "ТЫ САМЫЙ ГЛУПЫЙ ИЗ ВСЕХ ДОХОДЯГ, КОТОРЫЕ У МЕНЯ БЫЛИ!!!",
           "ДАЖЕ С ТОЧКИ ЗРЕНИЯ ФИЗИКИ ЭТО НЕВОЗМОЖНО!"], [A("...", None, "daniil_appears")]),
})
DLG["daniil"] = dict(who="daniil", layers={
    1: L(["Кто-то сказал слово «физика»?!", "Артём Ромашко, что ты делаешь рядом с этим зеленоватым типом?", "В «Голодных играх» тоже был зелёный персонаж, и он был злодеем."], [
        A("Даниил Митрофанов????", 2), A("(Выстрелить в него)", None, "kill:daniil")]),
    2: L(["Гастер: Чего???", "Гастер: Как ты попал в моё пространство???", "Даниил: Туннельный эффект, бро."], [A("Логично", 3)]),
    3: L(["Гастер: Ладно, валим отсюда! Я не готов к этому!!!", "Даниил: Хм. А я уж думал, подерусь...", "Даниил: Ну что, Артём, куда пойдём?"], [
        A("Я... Я не знаю... Я убил стольких людей...", 4, "gaster_flee")]),
    4: L(["Да и пофиг, если честно.", "Главное, что дз сделал", "Уже скоро урок начнётся"], [A("Так сегодня ж воскресенье...", None, "ending:rehab")]),
})
DLG["gaster2"] = dict(who="gaster", layers={
    1: L(["Ч... Чего?..", "Доходяга, ты убил его?...", "АХАХАХАХАХАХАХАХА! Ладно, прости меня! Ты умнейший из всех моих доходяг! Я планировал предать тебя, но после такого!!!"], [
        A("(Выстрелить в него)", None, "kill:gaster")]),
})
DLG["artem_mono"] = dict(who="artem", layers={
    1: L(["Хех...", "Они оба выбешивали меня", "Наконец-то... "], [A("Мухахахахахаха!", 2)]),
    2: L(["Теперь я убью всех... ВСЕХ... Всех людей, что встанут у меня на пути!!!", "Я становлюсь сильнее с каждым убийством...", "Расширение территории от Отца...",
          "Её усиление от Иисуса...", "Анубис от Костяна..."], [A("Я стану богом, если продолжу убивать!", None, "ending:true_evil")]),
})

# ---------------------------------------------------------------- описания концовок
ENDINGS = {
    "no_dnd":       ("БЕЗ ДНД", "Костян расширил территорию прямо по телефону. Ты умер, даже не начав.", "jokes"),
    "lera":         ("ДНД У ЛЕРЫ", "Ты ушёл на ДНД к Лере. Папа так и остался дома. Мир так и не узнал о твоём подвиге.", "jokes"),
    "dream":        ("ВЕЩИЙ СОН", "Небесная тюрьма оказалась сном. Наверное. Не говори Иисусу, что он ИИ.", "jokes"),
    "neutral":      ("НЕЙТРАЛЬНАЯ", "Папа погиб. Без него никто не сдерживал Иисуса. Ангельские лучи стёрли город вместе с ДНД.", "main"),
    "pacifist":     ("ПАЦИФИСТ", "Осколок домейна спас вас обоих. Но ослабленный Валерий не смог остановить ангельские лучи...", "main"),
    "true_neutral": ("ИСТИННАЯ НЕЙТРАЛЬНАЯ", "Иисус повержен, мир спасён. Ты вернулся домой. Уже один.", "main"),
    "true_pacifist": ("ИСТИННЫЙ ПАЦИФИСТ", "Папа жив, Иисус повержен, Эллен Джо зовёт гулять. С днём рождения, Артём.", "main"),
    "geno_abort":   ("ГЕНОЦИД ПРЕРВАН", "Ты хотел убить больше. Но врагов не осталось... Придётся начинать всё заново.", "geno"),
    "peace":        ("ПЕРЕМИРИЕ", "Вы с Костяном решили просто жить мирно. Возможно, это самая разумная концовка.", "geno"),
    "gaster":       ("ДОХОДЯГА ГАСТЕРА", "Эксперимент №52 завершён успешно. Мир будет уничтожен. Вашими руками.", "geno"),
    "rehab":        ("РЕАБИЛИТАЦИЯ", "Даниил Митрофанов спас тебя туннельным эффектом. Сегодня воскресенье, но урок всё равно будет.", "geno"),
    "true_evil":    ("ИСТИННОЕ ЗЛО", "Расширение территории, усиление Иисуса, Анубис Костяна. Ты стал богом. Богом пустого мира.", "geno"),
}
ENDING_ORDER = ["neutral", "pacifist", "true_neutral", "true_pacifist", "geno_abort", "peace", "gaster", "rehab", "true_evil", "no_dnd", "lera", "dream"]

# ============================================================================
#                               ПРЕДМЕТЫ
# ============================================================================
def IT(name, desc, kind="passive", pools=("treasure",), **kw):
    d = dict(name=name, desc=desc, kind=kind, pools=tuple(pools))
    d.update(kw)
    d.setdefault("flags", ())
    d.setdefault("tags", ())
    return d


ITEMS = {
    # --- сюжетные
    "soap": IT("Мыло", "Скользкие слёзы", pools=("story",), speed=0.15, flags=("bounce",)),
    "food": IT("Корм для раков", "Коты не едят. Раки едят.", pools=("story",), dmg=0.5, luck=1),
    "card": IT("Карта Императора", "Используй, когда придёт время", pools=("story",), luck=1),
    "shard": IT("Осколок домейна", "Светится в кармане", pools=("story",), dmg=0.5, tears=0.2),
    "jersey": IT("Футболка Серёги", "Чистые лёгкие!", pools=("story",), hearts=2, heal=4, speed=0.2, tears=0.3),
    "rifle": IT("Автомат", "Видишь автомат?", pools=("story",), tears_x=2.3, dmg_x=0.6, sspeed=0.35, flags=("bullet",)),
    "anubis": IT("Анубис", "Меч Костяна. Режет всё.", pools=("story",), dmg=2, flags=("sword",)),
    # --- пассивные
    "cup": IT("Кубок мира", "До 30 получу", pools=("treasure", "boss"), hearts=2, heal=99, speed=0.2),
    "cig": IT("Сигарета", "Курение убивает... врагов", pools=("treasure", "shop"), dmg=0.3, flags=("poison",)),
    "ball": IT("Мяч Блю Лока", "ЭГО!!!", pools=("treasure",), dmg=0.6, sspeed=-0.1, flags=("ball", "knock", "bounce")),
    "sheet": IT("Лист персонажа", "Все статы вверх", pools=("treasure", "shop"), dmg=0.4, tears=0.2, speed=0.1, range=24, luck=1, tags=("dnd",)),
    "robe": IT("Мантия Мастера", "Сквозь стены", pools=("treasure",), range=60, flags=("spectral",), tags=("dnd",)),
    "apple": IT("Яблочко", "Даже яблочка перед смертью...", pools=("treasure", "boss", "shop"), hearts=2, heal=99),
    "belt": IT("Папин ремень", "Я тебя породил...", pools=("treasure", "boss"), dmg=1.0, flags=("knock",)),
    "stutter": IT("Заикание", "П-п-п-пиу!", pools=("treasure",), flags=("burst",)),
    "claws": IT("Когти Дымка", "Царап!", pools=("treasure",), dmg=0.5, flags=("pierce",), tags=("cat",)),
    "finger": IT("Палец Сукуны", "Мяу (с силой)", pools=("treasure", "boss"), dmg=1.0, dmg_x=1.25, tags=("cat",)),
    "catnip": IT("Кошачья мята", "Мурр", pools=("treasure", "shop"), speed=0.25, tears=0.4, tags=("cat",)),
    "fur": IT("Шерсть Дымка", "Аллергия у врагов", pools=("treasure",), familiar="orbital_fur", tags=("cat",)),
    "halo": IT("Нимб", "Все статы вверх", pools=("treasure", "angel"), dmg=0.5, tears=0.3, speed=0.15, range=30, tags=("angel",)),
    "thorns": IT("Терновый венец", "Самонаводящиеся слёзы", pools=("treasure", "angel"), dmg=0.3, flags=("homing",), tags=("angel",)),
    "cross": IT("Крест", "Защитник", pools=("treasure", "angel"), familiar="orbital_cross", tags=("angel",)),
    "wings": IT("Крылья ангела", "Полёт!", pools=("treasure", "angel"), speed=0.25, flags=("flight",), tags=("angel",)),
    "holywater": IT("Святая вода", "Защита свыше", pools=("treasure", "angel", "shop"), soul=4, flags=("holycreep",), tags=("angel",)),
    "lens": IT("Лупа", "Большие слёзы", pools=("treasure",), dmg=1.5, dmg_x=1.15, tears_x=0.8, flags=("big",)),
    "physbook": IT("Учебник физики", "Туннельный эффект", pools=("treasure", "shop"), sspeed=0.4, range=40, flags=("spectral",)),
    "energy": IT("Энергетик", "Скорость и слёзы вверх", pools=("treasure", "shop"), speed=0.3, tears=0.5),
    "shawarma": IT("Шаурма", "Сытно!", pools=("treasure", "boss", "shop"), hearts=2, heal=4),
    "doshik": IT("Доширак", "Студенческий завтрак", pools=("shop", "boss"), heal=99, speed=0.15),
    "dachakey": IT("Ключ от дачи", "На дачу так и не уехал", pools=("treasure", "shop"), keys=3, luck=1),
    "phone": IT("Телефон Костяна", "Мини-Костик стреляет за тебя", pools=("treasure",), familiar="minikostya"),
    "axe": IT("Топор дровосека", "Ламберджек Тайкун", pools=("treasure",), dmg=0.7, range=40, flags=("pierce", "axe")),
    "fireball": IT("Огненный шар", "Горящие слёзы", pools=("treasure", "boss"), dmg=0.5, flags=("burn",)),
    "ring": IT("Кольцо Юты", "Копирование!", pools=("treasure",), flags=("split",)),
    "glasses": IT("Очки 3D", "Двойное зрение", pools=("treasure",), flags=("double",)),
    "triple": IT("Тройник", "Три слезы сразу", pools=("treasure",), tears_x=0.65, flags=("triple",)),
    "magnet": IT("Магнит", "Всё ко мне!", pools=("treasure", "shop"), flags=("magnet",)),
    "gum": IT("Жвачка", "Липкие слёзы", pools=("treasure", "shop"), range=40, flags=("slow",)),
    "backpack": IT("Рюкзак ДНД", "Феечка-помощник", pools=("treasure",), familiar="fairy", tags=("dnd",)),
    "dicebag": IT("Мешочек кубиков", "Каждый бросок — сюрприз", pools=("treasure",), luck=2, flags=("crit",), tags=("dnd",)),
    "shark": IT("Акулий зуб", "Крит-укус", pools=("treasure",), dmg=0.5, flags=("crit",)),
    "chalk": IT("Мел", "Дальнобойность", pools=("treasure", "shop"), range=80, sspeed=0.2),
    "mentos": IT("Газировка с ментосом", "БАБАХ!", pools=("treasure",), dmg_x=1.6, tears_x=0.45, flags=("explode",)),
    "brim": IT("Гнев Отца", "Зажми — и жги!", pools=("boss", "treasure"), dmg_x=1.0, flags=("brim",)),
    "pointer": IT("Лазерная указка", "Слёзы — лучи", pools=("treasure",), flags=("laser",)),
    "pentagram": IT("Пентаграмма ДНД", "Урон вверх", pools=("treasure", "boss"), dmg=1.0, tags=("dnd",)),
    "sock": IT("Счастливый носок", "Удача вверх", pools=("treasure", "shop"), luck=2, speed=0.1),
    "heartc": IT("Сердечко", "+1 контейнер", pools=("shop", "boss"), hearts=2, heal=2),
    "compass": IT("Компас", "Видишь особые комнаты", pools=("shop",), flags=("compass",)),
    "map": IT("Карта района", "Видишь весь этаж", pools=("shop",), flags=("map",)),
    "boot": IT("Бутса", "Скорость и полёт слёз", pools=("treasure", "shop"), speed=0.2, sspeed=0.3),
    "mirror": IT("Глаза на затылке", "Стреляешь и назад", pools=("treasure",), flags=("back",)),
    "lucky": IT("Клевер", "Удача!", pools=("shop", "treasure"), luck=3),
    # --- активные
    "d20": IT("Кубик Д20", "Перебросить судьбу", kind="active", pools=("treasure", "shop"), charges=6, use="reroll", tags=("dnd",)),
    "shrink": IT("Уменьшение", "Стань крошечным", kind="active", pools=("story",), charges=2, use="shrink", timed=8.0),
    "domain": IT("Расширение территории", "Мечи и кресты, как у Юты", kind="active", pools=("story",), charges=4, use="domain", timed=14.0),
    "rulebook": IT("Книга правил ДНД", "Молния по всем врагам", kind="active", pools=("treasure", "shop"), charges=3, use="lightning", tags=("dnd",)),
    "firecrackers": IT("Петарды", "Бах-бах-бах", kind="active", pools=("treasure", "shop"), charges=2, use="bombs"),
    "call": IT("Звонок другу", "Костян поможет... наверное", kind="active", pools=("treasure", "shop"), charges=3, use="call"),
    "bread": IT("Мамин бутер", "Подлечиться", kind="active", pools=("shop", "treasure"), charges=4, use="heal"),
}

TRANSFORMS = {
    "angel": ("СЕРАФИМ", "Полёт и святая сила!"),
    "cat": ("ДЫМОК", "Котики-призраки!"),
    "dnd": ("МАСТЕР ПОДЗЕМЕЛИЙ", "Крит на 20!"),
}

CHARACTERS = {
    "artem": dict(name="Артём", desc="Обычный парень. Хотел просто поиграть в ДНД.", spec="artem", hearts=6, soul=0, items=(), bombs=1,
                  stats=dict()),
    "artemosha": dict(name="Артёмоша", desc="Любимчик Иисуса. Кубик Д20 и удача.", spec="artemosha", hearts=4, soul=2, items=("d20",), bombs=1,
                      stats=dict(luck=2, speed=0.1), unlock="Пройди любую истинную концовку"),
    "artem_dark": dict(name="Тёмный Артём", desc="Помнит всё. Сильный, но хрупкий.", spec="artem_dark", hearts=2, soul=4, items=("finger",), bombs=0,
                       stats=dict(dmg_x=1.3, speed=0.15), unlock="Пройди любую концовку геноцида"),
}


class Stats:
    def __init__(self):
        self.damage = 3.5
        self.tears = 2.7
        self.range = 210.0
        self.sspeed = 1.0
        self.speed = 1.0
        self.luck = 0.0
        self.flags = set()

    @property
    def fire_delay(self):
        return 1.0 / max(0.4, self.tears)


# ============================================================================
#                                ЧАСТИЦЫ
# ============================================================================
class Particles:
    def __init__(self):
        self.p = []

    def add(self, x, y, vx, vy, life, col, size=2, grav=0.0, kind="sq", drag=0.9):
        if len(self.p) > 900:
            return
        self.p.append([x, y, vx, vy, life, life, col, size, grav, kind, drag])

    def burst(self, x, y, n, col, speed=80, life=0.5, size=2, grav=0.0, kind="sq", spread=math.pi * 2, ang=0.0):
        for _ in range(n):
            a = ang + random.uniform(-spread / 2, spread / 2)
            s = random.uniform(0.3, 1.0) * speed
            self.add(x, y, math.cos(a) * s, math.sin(a) * s, life * random.uniform(0.6, 1.2), col, size, grav, kind)

    def update(self, dt):
        alive = []
        for q in self.p:
            q[4] -= dt
            if q[4] <= 0:
                continue
            q[2] *= q[10] ** (dt * 60)
            q[3] *= q[10] ** (dt * 60)
            q[3] += q[8] * dt
            q[0] += q[2] * dt
            q[1] += q[3] * dt
            alive.append(q)
        self.p = alive

    def draw(self, surf, ox=0, oy=0):
        for (x, y, vx, vy, life, ml, col, size, grav, kind, drag) in self.p:
            t = life / ml
            if kind == "sq":
                sz = max(1, int(size * (0.4 + 0.6 * t)))
                surf.fill(col, (int(x + ox) - sz // 2, int(y + oy) - sz // 2, sz, sz))
            elif kind == "circ":
                pygame.draw.circle(surf, col, (int(x + ox), int(y + oy)), max(1, int(size * t)))
            elif kind == "ring":
                r = int(size * (1 - t) + 2)
                pygame.draw.circle(surf, col, (int(x + ox), int(y + oy)), r, 1)
            elif kind == "glow":
                g = light_glow(max(2, int(size * t)), col[:3], 160)
                surf.blit(g, (int(x + ox - g.get_width() / 2), int(y + oy - g.get_height() / 2)), special_flags=pygame.BLEND_RGB_ADD)
            elif kind == "spark":
                pygame.draw.line(surf, col, (int(x + ox), int(y + oy)), (int(x + ox - vx * 0.03), int(y + oy - vy * 0.03)), 1)


# ============================================================================
#                                СУЩНОСТИ
# ============================================================================
class Ent:
    r = 6
    dead = False
    flying = False
    solid = False

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.t = 0.0

    def update(self, g, dt):
        self.t += dt

    def draw(self, surf, g):
        pass

    @property
    def sort_y(self):
        return self.y


def move_circle(e, dx, dy, g, flying=False, bounce=False, use_walls=True):
    """Двигает сущность с учётом стен и препятствий. Возвращает (hit_x, hit_y)."""
    hx = hy = False
    room = g.room
    r = e.r
    e.x += dx
    if not flying:
        for (rx, ry, rw, rh) in room.solid_rects_near(e.x, e.y, r):
            pv = circle_rect_push(e.x, e.y, r, rx, ry, rw, rh)
            if pv and abs(pv[0]) >= abs(pv[1]):
                e.x += pv[0]
                hx = True
    if use_walls:
        if e.x < RX0 + r:
            e.x = RX0 + r
            hx = True
        elif e.x > RX1 - r:
            e.x = RX1 - r
            hx = True
    e.y += dy
    if not flying:
        for (rx, ry, rw, rh) in room.solid_rects_near(e.x, e.y, r):
            pv = circle_rect_push(e.x, e.y, r, rx, ry, rw, rh)
            if pv:
                if abs(pv[1]) >= abs(pv[0]):
                    e.y += pv[1]
                    hy = True
                else:
                    e.x += pv[0]
                    hx = True
    if use_walls:
        if e.y < RY0 + r:
            e.y = RY0 + r
            hy = True
        elif e.y > RY1 - r:
            e.y = RY1 - r
            hy = True
    return hx, hy


# ---------------------------------------------------------------- слёзы игрока
class Tear(Ent):
    def __init__(self, x, y, vx, vy, dmg, st, g, r=None, col=None, life_range=None, h=9.0):
        super().__init__(x, y)
        self.vx, self.vy = vx, vy
        self.dmg = dmg
        self.flags = set(st.flags)
        base_r = 3.2 + min(4.0, dmg * 0.25)
        if "big" in self.flags:
            base_r *= 1.5
        self.r = r if r else base_r
        self.range = life_range if life_range else st.range
        self.traveled = 0.0
        self.h = h
        self.vh = 0.0
        self.hit = set()
        self.bounces = 0
        self.kind = "tear"
        if "ball" in self.flags:
            self.kind = "ball"
        elif "axe" in self.flags:
            self.kind = "axe"
        elif "bullet" in self.flags:
            self.kind = "bullet"
        if col:
            self.col = col
        elif "poison" in self.flags:
            self.col = (110, 210, 90)
        elif "burn" in self.flags:
            self.col = (255, 140, 40)
        elif "slow" in self.flags:
            self.col = (255, 150, 210)
        elif "homing" in self.flags:
            self.col = (200, 120, 250)
        elif "bullet" in self.flags:
            self.col = (250, 220, 90)
        elif "spectral" in self.flags:
            self.col = (190, 220, 255)
        else:
            self.col = (120, 170, 255)
        self.crit = False
        if "crit" in self.flags and random.random() < 0.12 + st.luck * 0.02:
            self.crit = True
            self.dmg *= 3.0
            self.col = (255, 60, 60)
            self.r *= 1.3
        self.explode = "explode" in self.flags
        if self.explode:
            self.vh = 120
            self.col = (90, 220, 90)
        self.spin = 0.0

    def update(self, g, dt):
        self.t += dt
        if "homing" in self.flags:
            tgt = g.nearest_enemy(self.x, self.y, 160)
            if tgt:
                sp = math.hypot(self.vx, self.vy)
                a1 = math.atan2(self.vy, self.vx)
                a2 = ang_to(self.x, self.y, tgt.x, tgt.y)
                da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
                a1 += clamp(da, -5 * dt, 5 * dt)
                self.vx, self.vy = from_ang(a1, sp)
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.spin += dt * 14
        sp = math.hypot(self.vx, self.vy)
        self.traveled += sp * dt
        if self.explode:
            self.h += self.vh * dt
            self.vh -= 420 * dt
            if self.h <= 0:
                self.die(g)
                return
        elif self.traveled > self.range:
            self.vh -= 260 * dt
            self.h += self.vh * dt
            if self.h <= 0:
                self.die(g)
                return
        # стены
        if self.x < RX0 + 2 or self.x > RX1 - 2 or self.y < RY0 + 2 or self.y > RY1 - 2:
            if "bounce" in self.flags and self.bounces < 3:
                self.bounces += 1
                if self.x < RX0 + 2 or self.x > RX1 - 2:
                    self.vx = -self.vx
                    self.x = clamp(self.x, RX0 + 3, RX1 - 3)
                else:
                    self.vy = -self.vy
                    self.y = clamp(self.y, RY0 + 3, RY1 - 3)
            else:
                self.die(g)
                return
        # препятствия
        if "spectral" not in self.flags and not self.explode:
            ob = g.room.obstacle_at_px(self.x, self.y)
            if ob is not None:
                if ob.kind in ("poop", "fire"):
                    ob.hurt(g, 1)
                    self.die(g)
                    return
                elif ob.kind != "pit":
                    if "bounce" in self.flags and self.bounces < 3:
                        self.bounces += 1
                        self.vx, self.vy = -self.vx, -self.vy
                    else:
                        self.die(g)
                        return
        # враги
        for e in g.room.enemies:
            if e.dead or not e.hittable or id(e) in self.hit:
                continue
            if (e.x - self.x) ** 2 + (e.y - self.y) ** 2 < (e.r + self.r) ** 2:
                self.on_hit(g, e)
                if "pierce" not in self.flags:
                    self.die(g, splash=True)
                    return
                self.hit.add(id(e))

    def on_hit(self, g, e):
        nx, ny = norm(self.vx, self.vy)
        kb = 70 if ("knock" in self.flags) else 25
        if self.explode:
            return
        e.hurt(g, self.dmg, nx * kb, ny * kb, self)
        if self.crit:
            g.floater(e.x, e.y - 14, "КРИТ!", (255, 80, 80))
        if "poison" in self.flags:
            e.poison = 3.0
            e.poison_dmg = max(1.0, self.dmg * 0.25)
        if "burn" in self.flags:
            e.burn = 2.5
            e.burn_dmg = max(1.0, self.dmg * 0.3)
        if "slow" in self.flags:
            e.slow = 2.5
        if "split" in self.flags and self.r > 2.5:
            a = math.atan2(self.vy, self.vx)
            for da in (math.pi / 2, -math.pi / 2):
                vx, vy = from_ang(a + da, 200)
                t = Tear(self.x, self.y, vx, vy, self.dmg * 0.5, g.player.stats, g, r=self.r * 0.6, life_range=60, h=self.h)
                t.flags.discard("split")
                t.hit.add(id(e))
                g.tears.append(t)
        if g.player.form("cat") and random.random() < 0.15:
            g.spawn_bluecat(e.x, e.y)

    def die(self, g, splash=True):
        if self.dead:
            return
        self.dead = True
        if self.explode:
            g.explode(self.x, self.y, 40, self.dmg * 1.4, friendly=True, small=True)
            return
        if splash:
            g.parts.burst(self.x, self.y - self.h, 6, self.col, 50, 0.3, 2)
            g.audio_splash()

    def draw(self, surf, g):
        sh = shadow_surf(int(self.r * 2), max(2, int(self.r)), 70)
        surf.blit(sh, (self.x - sh.get_width() / 2, self.y - sh.get_height() / 2 + 2))
        if self.kind == "axe":
            s = tear_sprite(self.col, self.r + 2, "axe")
            s = pygame.transform.rotate(s, -self.spin * 57)
        else:
            s = tear_sprite(self.col, self.r, self.kind)
        surf.blit(s, (self.x - s.get_width() / 2, self.y - self.h - s.get_height() / 2))


# ---------------------------------------------------------------- снаряды врагов
class EShot(Ent):
    def __init__(self, x, y, vx, vy, kind="blood", col=(210, 30, 30), r=4, dmg=1, life=6.0, accel=0.0, homing=0.0,
                 wave=0.0, spectral=False, grav=0.0, delay=0.0, spin=0.0, friendly=False, maxspeed=400,
                 pop=0, pop_speed=100, pop_kind=None, bounce=0, creep=None):
        super().__init__(x, y)
        self.pop, self.pop_speed, self.pop_kind = pop, pop_speed, pop_kind
        self.bounce = bounce
        self.creep_on_pop = creep
        self.vx, self.vy = vx, vy
        self.kind, self.col, self.r, self.dmg = kind, col, r, dmg
        self.life = life
        self.accel = accel
        self.homing = homing
        self.wave = wave
        self.spectral = spectral
        self.grav = grav
        self.delay = delay
        self.spin = spin
        self.friendly = friendly
        self.maxspeed = maxspeed
        self.ang = 0.0
        self.h = 6.0

    def update(self, g, dt):
        if self.delay > 0:
            self.delay -= dt
            return
        self.t += dt
        self.life -= dt
        if self.life <= 0:
            self.dead = True
            if self.pop:
                off = random.uniform(0, math.pi)
                for k in range(self.pop):
                    vx, vy = from_ang(off + k * math.pi * 2 / self.pop, self.pop_speed)
                    g.eshots.append(EShot(self.x, self.y, vx, vy, self.pop_kind or self.kind, self.col, max(3, self.r * 0.6), self.dmg, life=4))
                g.parts.burst(self.x, self.y, 10, self.col, 80, 0.4, 3)
                g.sfx("fire", 0.5)
            if self.creep_on_pop:
                g.creep.append(Creep(self.x, self.y, self.creep_on_pop[0], self.creep_on_pop[1], self.creep_on_pop[2], 1))
            return
        sc = g.bullet_time_scale()
        if self.accel:
            sp = math.hypot(self.vx, self.vy)
            if sp > 0:
                nsp = clamp(sp + self.accel * dt, 10, self.maxspeed)
                self.vx *= nsp / sp
                self.vy *= nsp / sp
        if self.homing and g.player:
            sp = math.hypot(self.vx, self.vy)
            a1 = math.atan2(self.vy, self.vx)
            a2 = ang_to(self.x, self.y, g.player.x, g.player.y)
            da = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
            a1 += clamp(da, -self.homing * dt, self.homing * dt)
            self.vx, self.vy = from_ang(a1, sp)
        if self.spin:
            a = math.atan2(self.vy, self.vx) + self.spin * dt
            sp = math.hypot(self.vx, self.vy)
            self.vx, self.vy = from_ang(a, sp)
        self.vy += self.grav * dt
        mx, my = self.vx * dt * sc, self.vy * dt * sc
        if self.wave:
            nx, ny = norm(-self.vy, self.vx)
            w = math.cos(self.t * 8) * self.wave * dt * 8
            mx += nx * w
            my += ny * w
        self.x += mx
        self.y += my
        self.ang += dt * 6
        if self.bounce > 0 and (self.x < RX0 + self.r or self.x > RX1 - self.r or self.y < RY0 + self.r or self.y > RY1 - self.r):
            self.bounce -= 1
            if self.x < RX0 + self.r or self.x > RX1 - self.r:
                self.vx = -self.vx
                self.x = clamp(self.x, RX0 + self.r, RX1 - self.r)
            if self.y < RY0 + self.r or self.y > RY1 - self.r:
                self.vy = -self.vy
                self.y = clamp(self.y, RY0 + self.r, RY1 - self.r)
        if self.x < RX0 - 6 or self.x > RX1 + 6 or self.y < RY0 - 6 or self.y > RY1 + 6:
            self.dead = True
            return
        if not self.spectral:
            ob = g.room.obstacle_at_px(self.x, self.y)
            if ob is not None and ob.kind not in ("pit", "fire"):
                self.dead = True
                g.parts.burst(self.x, self.y, 4, self.col, 40, 0.25, 2)
                return
        if self.friendly:
            for e in g.room.enemies:
                if not e.dead and e.hittable and (e.x - self.x) ** 2 + (e.y - self.y) ** 2 < (e.r + self.r) ** 2:
                    e.hurt(g, self.dmg, 0, 0, self)
                    self.dead = True
                    return
            return
        p = g.player
        # орбитальные защитники
        for f in g.familiars:
            if f.blocks and (f.x - self.x) ** 2 + (f.y - self.y) ** 2 < (f.r + self.r) ** 2:
                self.dead = True
                g.parts.burst(self.x, self.y, 4, self.col, 40, 0.25, 2)
                return
        if p and not p.dead and (p.x - self.x) ** 2 + (p.y - self.y) ** 2 < (p.hr + self.r * 0.85) ** 2:
            if p.hurt(g, self.dmg, self):
                self.dead = True

    def draw(self, surf, g):
        if self.delay > 0:
            if int(self.delay * 20) % 2 == 0:
                pygame.draw.circle(surf, self.col, (int(self.x), int(self.y)), 2)
            return
        s = bullet_sprite(self.kind, self.col, self.r)
        if self.kind in ("nail", "pencil", "fish", "feather", "claw"):
            a = -math.degrees(math.atan2(self.vy, self.vx))
            if self.kind == "pencil":
                a -= 90
            s = pygame.transform.rotate(s, a)
        elif self.kind in ("cross", "star", "dice"):
            s = pygame.transform.rotate(s, math.degrees(self.ang) * 1.5)
        surf.blit(s, (self.x - s.get_width() / 2, self.y - s.get_height() / 2))


# ---------------------------------------------------------------- лучи
class Beam(Ent):
    def __init__(self, x, y, ang, length=600, width=10, warm=0.8, dur=0.6, dmg=2, col=(255, 240, 160), friendly=False,
                 follow=None, rot=0.0, src_off=0.0):
        super().__init__(x, y)
        self.ang, self.length, self.width = ang, length, width
        self.warm, self.dur, self.dmg, self.col = warm, dur, dmg, col
        self.friendly = friendly
        self.follow = follow
        self.rot = rot
        self.tick = 0.0
        self.src_off = src_off
        self.started = False

    def ends(self):
        x0 = self.x + math.cos(self.ang) * self.src_off
        y0 = self.y + math.sin(self.ang) * self.src_off
        return x0, y0, x0 + math.cos(self.ang) * self.length, y0 + math.sin(self.ang) * self.length

    def update(self, g, dt):
        self.t += dt
        if self.follow is not None:
            if getattr(self.follow, "dead", False):
                self.dead = True
                return
            self.x, self.y = self.follow.x, self.follow.y - 4
        self.ang += self.rot * dt * (1 if self.t > self.warm else 0.2)
        if self.t < self.warm:
            return
        if not self.started:
            self.started = True
            g.sfx("laser")
            g.shake(3)
        if self.t > self.warm + self.dur:
            self.dead = True
            return
        x0, y0, x1, y1 = self.ends()
        if self.friendly:
            self.tick -= dt
            if self.tick <= 0:
                self.tick = 0.1
                for e in g.room.enemies:
                    if e.dead or not e.hittable:
                        continue
                    if seg_dist(e.x, e.y, x0, y0, x1, y1) < e.r + self.width / 2:
                        e.hurt(g, self.dmg, 0, 0, self)
        else:
            p = g.player
            if p and not p.dead and seg_dist(p.x, p.y, x0, y0, x1, y1) < p.hr + self.width * 0.4:
                p.hurt(g, self.dmg, self)

    def draw(self, surf, g):
        x0, y0, x1, y1 = self.ends()
        if self.t < self.warm:
            k = self.t / self.warm
            c = self.col if int(self.t * 16) % 2 == 0 else (255, 255, 255)
            pygame.draw.line(surf, c, (x0, y0), (x1, y1), 1 if k < 0.7 else 2)
            return
        w = self.width * (1.0 if self.t < self.warm + self.dur - 0.15 else max(0.1, (self.warm + self.dur - self.t) / 0.15))
        w2 = max(1, int(w))
        pygame.draw.line(surf, col_mul(self.col, 0.7), (x0, y0), (x1, y1), w2 + 4)
        pygame.draw.line(surf, self.col, (x0, y0), (x1, y1), w2)
        pygame.draw.line(surf, (255, 255, 255), (x0, y0), (x1, y1), max(1, w2 // 3))


def seg_dist(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    l2 = dx * dx + dy * dy
    if l2 < 1e-6:
        return math.hypot(px - x0, py - y0)
    t = clamp(((px - x0) * dx + (py - y0) * dy) / l2, 0, 1)
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


# ---------------------------------------------------------------- лужи (creep)
class Creep(Ent):
    def __init__(self, x, y, r, life, col, dmg=1, friendly=False):
        super().__init__(x, y)
        self.r, self.life, self.max_life, self.col, self.dmg, self.friendly = r, life, life, col, dmg, friendly
        self.tick = 0
        self.seed = random.random() * 10

    def update(self, g, dt):
        self.t += dt
        self.life -= dt
        if self.life <= 0:
            self.dead = True
            return
        if self.friendly:
            self.tick -= dt
            if self.tick <= 0:
                self.tick = 0.25
                for e in g.room.enemies:
                    if not e.dead and e.hittable and not e.flying and (e.x - self.x) ** 2 + (e.y - self.y) ** 2 < (e.r + self.r) ** 2:
                        e.hurt(g, self.dmg, 0, 0, self)
        else:
            p = g.player
            if p and not p.flight and (p.x - self.x) ** 2 + (p.y - self.y) ** 2 < (self.r * 0.85) ** 2:
                p.hurt(g, self.dmg, self)

    def draw(self, surf, g):
        a = int(170 * min(1.0, self.life / 0.6))
        k = ("creep", int(self.r), self.col, a // 20)

        def build():
            s = pygame.Surface((int(self.r * 2 + 4), int(self.r * 1.4 + 4)), pygame.SRCALPHA)
            pygame.draw.ellipse(s, self.col + (a // 20 * 20,), s.get_rect())
            pygame.draw.ellipse(s, col_mul(self.col, 1.3) + (a // 20 * 12,), s.get_rect().inflate(-self.r * 0.6, -self.r * 0.5))
            return s
        s = cached(k, build)
        surf.blit(s, (self.x - s.get_width() / 2, self.y - s.get_height() / 2))

    @property
    def sort_y(self):
        return -1000


# ---------------------------------------------------------------- пикапы
PICKUP_INFO = {"coin": 1, "nickel": 5}


class Pickup(Ent):
    def __init__(self, kind, x, y, vx=0.0, vy=0.0, price=0):
        super().__init__(x, y)
        self.kind = kind
        self.vx, self.vy = vx, vy
        self.r = 6
        self.price = price
        self.h = 0.0
        self.vh = 60.0 if (vx or vy) else 0.0
        self.anim = random.random() * 8
        self.cool = 0.3

    def update(self, g, dt):
        self.t += dt
        self.anim += dt * 10
        self.cool -= dt
        if self.vh or self.h > 0:
            self.h += self.vh * dt
            self.vh -= 300 * dt
            if self.h <= 0:
                self.h = 0
                self.vh = -self.vh * 0.35 if abs(self.vh) > 30 else 0
        if self.price == 0:
            p = g.player
            if p and "magnet" in p.stats.flags and self.kind in ("coin", "nickel", "key", "bomb"):
                d = dist(self.x, self.y, p.x, p.y)
                if d < 140:
                    nx, ny = norm(p.x - self.x, p.y - self.y)
                    self.vx += nx * 300 * dt
                    self.vy += ny * 300 * dt
        self.vx *= 0.9 ** (dt * 60)
        self.vy *= 0.9 ** (dt * 60)
        hx, hy = move_circle(self, self.vx * dt, self.vy * dt, g)
        if hx:
            self.vx = -self.vx * 0.5
        if hy:
            self.vy = -self.vy * 0.5
        p = g.player
        if p and self.cool <= 0 and (p.x - self.x) ** 2 + (p.y - self.y) ** 2 < (p.r + self.r + 2) ** 2:
            if g.try_collect(self):
                self.dead = True

    def draw(self, surf, g):
        sh = shadow_surf(12, 5, 70)
        surf.blit(sh, (self.x - 6, self.y + 3))
        s = pickup_sprite(self.kind, int(self.anim) if self.kind in ("coin", "nickel", "bomb") else 0)
        surf.blit(s, (self.x - s.get_width() / 2, self.y - s.get_height() / 2 - self.h - 2))
        if self.price:
            draw_digits(surf, str(self.price), int(self.x - 6), int(self.y + 8), (255, 255, 255))


class Pedestal(Ent):
    def __init__(self, item, x, y, price=0, on_take=None):
        super().__init__(x, y)
        self.item = item
        self.r = 10
        self.price = price
        self.on_take = on_take
        self.solid = True
        self.cool = 0.0

    def update(self, g, dt):
        self.t += dt
        self.cool -= dt
        p = g.player
        if self.item and p and self.cool <= 0 and (p.x - self.x) ** 2 + (p.y - self.y) ** 2 < (p.r + self.r + 3) ** 2:
            g.take_pedestal(self)

    def draw(self, surf, g):
        ps = pedestal_sprite()
        surf.blit(ps, (self.x - ps.get_width() / 2, self.y - 4))
        if self.item:
            ic = item_icon(self.item)
            bob = math.sin(self.t * 3) * 2
            gl = light_glow(14, (255, 240, 200), 70)
            surf.blit(gl, (self.x - 14, self.y - 26 + bob), special_flags=pygame.BLEND_RGB_ADD)
            surf.blit(ic, (self.x - ic.get_width() / 2, self.y - 22 + bob))
            if self.price:
                draw_digits(surf, str(self.price), int(self.x - 6), int(self.y + 14), (255, 255, 120))


# ---------------------------------------------------------------- бомбы
class Bomb(Ent):
    def __init__(self, x, y, fuse=1.5, friendly=True, dmg=60, radius=48, big=False):
        super().__init__(x, y)
        self.fuse = fuse
        self.friendly = friendly
        self.dmg = dmg
        self.radius = radius
        self.r = 7
        self.big = big

    def update(self, g, dt):
        self.t += dt
        self.fuse -= dt
        self.vx *= 0.85
        self.vy *= 0.85
        move_circle(self, self.vx * dt, self.vy * dt, g)
        if random.random() < 0.5:
            g.parts.add(self.x + 1, self.y - 9, random.uniform(-20, 20), random.uniform(-40, -10), 0.3, (255, 200, 80), 1)
        if self.fuse <= 0:
            self.dead = True
            g.explode(self.x, self.y, self.radius, self.dmg, friendly=self.friendly, hurt_player=getattr(self, "hurt_player", True))

    def draw(self, surf, g):
        k = 1.0 + (0.15 * math.sin(self.t * (10 + (1.5 - self.fuse) * 20)) if self.fuse < 1.0 else 0)
        s = pickup_sprite("bomb", int(self.t * 8))
        if self.big:
            k *= 1.6
        if k != 1.0:
            s = pygame.transform.scale(s, (int(s.get_width() * k), int(s.get_height() * k)))
        if self.fuse < 0.8 and int(self.t * 14) % 2 == 0:
            s = flash_red(s)
        surf.blit(shadow_surf(14, 5, 80), (self.x - 7, self.y + 4))
        surf.blit(s, (self.x - s.get_width() / 2, self.y - s.get_height() / 2))


# ---------------------------------------------------------------- препятствия
class Obstacle:
    def __init__(self, kind, c, r, style="rock", variant=0):
        self.kind = kind  # rock, tinted, poop, gpoop, block, fire, bfire
        self.c, self.r = c, r
        self.style = style
        self.variant = variant
        self.hp = 4 if kind in ("poop", "gpoop", "fire", "bfire") else 1
        self.dead = False
        self.anim = random.random() * 3

    @property
    def solid(self):
        return not self.dead and self.kind != "fire" and self.kind != "bfire" or (self.kind in ("fire", "bfire") and False)

    def rect(self):
        x, y = RX0 + self.c * TILE, RY0 + self.r * TILE
        if self.kind in ("fire", "bfire"):
            return (x + 8, y + 10, 16, 16)
        return (x + 2, y + 3, 28, 26)

    def hurt(self, g, d):
        if self.dead or self.kind not in ("poop", "gpoop", "fire", "bfire"):
            return
        self.hp -= d
        x, y = tile_center(self.c, self.r)
        if self.kind in ("poop", "gpoop"):
            g.parts.burst(x, y, 4, (110, 70, 40), 50, 0.3, 2)
        else:
            g.parts.burst(x, y - 6, 4, (255, 160, 60), 40, 0.3, 2)
        if self.hp <= 0:
            self.destroy(g)

    def destroy(self, g):
        if self.dead or self.kind == "block":
            return
        self.dead = True
        x, y = tile_center(self.c, self.r)
        if self.kind in ("poop", "gpoop"):
            g.sfx("poop")
            g.parts.burst(x, y, 12, (110, 70, 40), 80, 0.5, 3)
            if self.kind == "gpoop":
                for _ in range(random.randint(3, 6)):
                    g.drop("coin", x, y)
            elif random.random() < 0.18:
                g.drop(random.choice(["coin", "coin", "heart", "bomb", "key"]), x, y)
        elif self.kind in ("fire", "bfire"):
            g.sfx("fire")
            g.parts.burst(x, y, 10, (90, 90, 90), 40, 0.8, 3, grav=-40)
            if random.random() < 0.15:
                g.drop("coin", x, y)
        else:
            g.sfx("rock")
            g.parts.burst(x, y, 14, (140, 130, 120), 90, 0.5, 3)
            if self.kind == "tinted":
                for _ in range(random.randint(1, 3)):
                    g.drop(random.choice(["soul", "bomb", "key", "coin"]), x, y)
        g.room.decal_rubble(x, y, self.kind)
        g.room.dirty = True


# ---------------------------------------------------------------- фамильяры
class Familiar(Ent):
    blocks = False

    def __init__(self, kind, idx=0):
        super().__init__(0, 0)
        self.kind = kind
        self.idx = idx
        self.r = 6
        self.blocks = kind in ("orbital_cross", "orbital_fur")
        self.cool = 0
        self.trail_i = 12 + idx * 10

    def update(self, g, dt):
        self.t += dt
        p = g.player
        if self.kind in ("orbital_cross", "orbital_fur", "fairy"):
            n = max(1, sum(1 for f in g.familiars if f.kind in ("orbital_cross", "orbital_fur", "fairy")))
            k = [f for f in g.familiars if f.kind in ("orbital_cross", "orbital_fur", "fairy")].index(self)
            a = self.t * 2.6 + k * math.pi * 2 / n
            rad = 26 if self.kind != "fairy" else 34
            self.x = p.x + math.cos(a) * rad
            self.y = p.y + math.sin(a) * rad * 0.8
            self.cool -= dt
            if self.cool <= 0:
                for e in g.room.enemies:
                    if not e.dead and e.hittable and (e.x - self.x) ** 2 + (e.y - self.y) ** 2 < (e.r + self.r + 2) ** 2:
                        e.hurt(g, 3.0 if self.kind != "fairy" else 2.0, 0, 0, self)
                        self.cool = 0.3
                        break
        elif self.kind == "minikostya":
            tr = g.player.trail
            if len(tr) > self.trail_i:
                tx, ty = tr[-self.trail_i]
            else:
                tx, ty = p.x, p.y + 14
            self.x += (tx - self.x) * min(1, dt * 8)
            self.y += (ty - self.y) * min(1, dt * 8)
            self.cool -= dt
            if p.shoot_dir and self.cool <= 0:
                self.cool = 0.5
                dx, dy = DIRS[p.shoot_dir]
                t = Tear(self.x, self.y, dx * 240, dy * 240, 3.0, p.stats, g, r=3, col=(120, 170, 255))
                t.flags = set()
                g.tears.append(t)

    def draw(self, surf, g):
        if self.kind == "orbital_cross":
            s = item_icon("cross")
        elif self.kind == "orbital_fur":
            s = item_icon("fur")
        elif self.kind == "fairy":
            s = enemy_sprite("fairy", int(self.t * 10))
        else:
            s = enemy_sprite("minikostya", int(self.t * 6) if g.player.moving else 0)
        surf.blit(s, (self.x - s.get_width() / 2, self.y - s.get_height() / 2))


class BlueCat(Ent):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.r = 4
        self.life = 8

    def update(self, g, dt):
        self.t += dt
        self.life -= dt
        if self.life <= 0:
            self.dead = True
            return
        tgt = g.nearest_enemy(self.x, self.y, 400)
        if tgt:
            nx, ny = norm(tgt.x - self.x, tgt.y - self.y)
            self.vx += nx * 500 * dt
            self.vy += ny * 500 * dt
            if (tgt.x - self.x) ** 2 + (tgt.y - self.y) ** 2 < (tgt.r + 5) ** 2:
                tgt.hurt(g, 6, 0, 0, self)
                self.dead = True
                g.parts.burst(self.x, self.y, 8, (120, 170, 255), 60, 0.4, 2)
        else:
            self.vx += math.cos(self.t * 3) * 100 * dt
            self.vy += math.sin(self.t * 2.3) * 100 * dt
        self.vx *= 0.9
        self.vy *= 0.9
        self.x = clamp(self.x + self.vx * dt, RX0, RX1)
        self.y = clamp(self.y + self.vy * dt, RY0, RY1)

    def draw(self, surf, g):
        s = enemy_sprite("bluecat", 0)
        surf.blit(s, (self.x - s.get_width() / 2, self.y - s.get_height() / 2 - 4))


# ============================================================================
#                                  ИГРОК
# ============================================================================
class Player(Ent):
    def __init__(self, char_id="artem"):
        super().__init__(RCX, RCY + 40)
        ch = CHARACTERS[char_id]
        self.char = char_id
        self.spec = ch["spec"]
        self.r = 7
        self.hr = 5.5
        self.red_max = ch["hearts"]
        self.red = ch["hearts"]
        self.soul = ch["soul"]
        self.coins = 0
        self.bombs = ch["bombs"]
        self.keys = 0
        self.items = []
        self.active = None
        self.charge = 0
        self.timed_charge = 0.0
        self.base_mods = dict(ch["stats"])
        self.stats = Stats()
        self.facing = "down"
        self.shoot_dir = None
        self.fire_cool = 0.0
        self.eye = 0
        self.inv = 0.0
        self.hold_t = 0.0
        self.hold_item = None
        self.shoot_pose = 0.0
        self.walk_t = 0.0
        self.moving = False
        self.trail = deque(maxlen=60)
        self.shrink_t = 0.0
        self.domain_t = 0.0
        self.burst_q = 0
        self.burst_t = 0.0
        self.brim_charge = 0.0
        self.sword_t = 0.0
        self.sword_dir = "down"
        self.dead = False
        self.flight = False
        self.forms = set()
        self.evil = 0
        self.no_shoot = False
        self.lock_input = False
        self.dmg_taken_room = False
        for it in ch["items"]:
            self.add_item(it, silent=True)
        self.recalc()

    # ------------------------------------------------ предметы/статы
    def form(self, name):
        return name in self.forms

    def recalc(self):
        st = Stats()
        dmg_add = 0.0
        dmg_x = 1.0
        tears_add = 0.0
        tears_x = 1.0
        mods = [self.base_mods] + [ITEMS[i] for i in self.items]
        for m in mods:
            dmg_add += m.get("dmg", 0)
            dmg_x *= m.get("dmg_x", 1.0)
            tears_add += m.get("tears", 0)
            tears_x *= m.get("tears_x", 1.0)
            st.range += m.get("range", 0)
            st.sspeed += m.get("sspeed", 0)
            st.speed += m.get("speed", 0)
            st.luck += m.get("luck", 0)
            for f in m.get("flags", ()):
                st.flags.add(f)
        # трансформации
        tags = {}
        for i in self.items:
            for t in ITEMS[i]["tags"]:
                tags[t] = tags.get(t, 0) + 1
        self.forms = {t for t, n in tags.items() if n >= 3}
        if "angel" in self.forms:
            st.flags.add("flight")
            dmg_add += 1.0
        if "dnd" in self.forms:
            st.flags.add("crit")
            st.luck += 2
        if "cat" in self.forms:
            st.speed += 0.15
        if self.evil:
            dmg_x *= 1.0 + 0.15 * self.evil
        if "burst" in st.flags:
            tears_x *= 0.55
        st.damage = max(0.5, (3.5 + dmg_add) * dmg_x)
        st.tears = clamp((2.7 + tears_add) * tears_x, 0.6, 9.0)
        if "burst" in st.flags:
            st.tears = clamp(st.tears, 0.6, 3.0)
        st.speed = clamp(st.speed, 0.5, 2.0)
        st.sspeed = clamp(st.sspeed, 0.5, 2.5)
        if self.domain_t > 0:
            st.damage *= 1.3
        if self.shrink_t > 0:
            st.speed += 0.3
            st.damage *= 1.2
        self.stats = st
        self.flight = "flight" in st.flags

    def add_item(self, iid, silent=False):
        it = ITEMS[iid]
        if it["kind"] == "active":
            old = self.active
            self.active = iid
            self.charge = it["charges"]
            return old
        if iid not in self.items:
            self.items.append(iid)
        before = set(self.forms)
        self.red_max = min(24, self.red_max + it.get("hearts", 0))
        self.red = min(self.red_max, self.red + it.get("hearts", 0) + it.get("heal", 0))
        self.soul = min(24, self.soul + it.get("soul", 0))
        self.keys += it.get("keys", 0)
        self.bombs += it.get("bombs", 0)
        self.coins += it.get("coins", 0)
        self.recalc()
        return [f for f in self.forms if f not in before]

    def has(self, iid):
        return iid in self.items or self.active == iid

    def heal(self, halves):
        if self.red >= self.red_max:
            return False
        self.red = min(self.red_max, self.red + halves)
        return True

    # ------------------------------------------------ урон
    def hurt(self, g, dmg, src=None):
        if self.dead or self.inv > 0 or g.god or self.hold_t > 0.5:
            return False
        dmg = int(max(1, dmg))
        if self.soul > 0:
            take = min(self.soul, dmg)
            self.soul -= take
            dmg -= take
        self.red = max(0, self.red - dmg)
        self.inv = 1.0
        self.dmg_taken_room = True
        g.sfx("hurt")
        g.shake(4)
        g.hurt_flash = 0.25
        g.parts.burst(self.x, self.y - 6, 10, (200, 20, 30), 90, 0.5, 2, grav=200)
        if "holycreep" in self.stats.flags:
            g.creep.append(Creep(self.x, self.y + 4, 22, 3.0, (240, 240, 200), dmg=3, friendly=True))
        if self.red <= 0 and self.soul <= 0:
            g.player_died(src)
        return True

    # ------------------------------------------------ обновление
    def update(self, g, dt, keys):
        self.t += dt
        self.inv = max(0.0, self.inv - dt)
        self.hold_t = max(0.0, self.hold_t - dt)
        self.shoot_pose = max(0.0, self.shoot_pose - dt)
        self.sword_t = max(0.0, self.sword_t - dt)
        if self.shrink_t > 0:
            self.shrink_t -= dt
            if self.shrink_t <= 0:
                g.sfx("grow")
                self.recalc()
        if self.domain_t > 0:
            self.domain_t -= dt
            if self.domain_t <= 0:
                self.recalc()
        # активка с таймером
        if self.active and ITEMS[self.active].get("timed"):
            mx = ITEMS[self.active]["charges"]
            if self.charge < mx and g.room and not g.room.cleared:
                self.timed_charge += dt
                if self.timed_charge >= ITEMS[self.active]["timed"] / mx:
                    self.timed_charge = 0
                    self.charge += 1
                    if self.charge == mx:
                        g.sfx("charge")
        st = self.stats
        mvx = mvy = 0.0
        sdir = None
        if not self.lock_input and self.hold_t <= 0.3:
            if keys[pygame.K_a]:
                mvx -= 1
            if keys[pygame.K_d]:
                mvx += 1
            if keys[pygame.K_w]:
                mvy -= 1
            if keys[pygame.K_s]:
                mvy += 1
            for k, d in ((pygame.K_LEFT, "left"), (pygame.K_RIGHT, "right"), (pygame.K_UP, "up"), (pygame.K_DOWN, "down")):
                if keys[k]:
                    if sdir is None or g.last_arrow == d:
                        sdir = d
        if mvx and mvy:
            mvx *= 0.7071
            mvy *= 0.7071
        maxs = 118 * st.speed
        acc = 1400
        tvx, tvy = mvx * maxs, mvy * maxs
        self.vx = approach(self.vx, tvx, acc * dt)
        self.vy = approach(self.vy, tvy, acc * dt)
        self.moving = abs(self.vx) + abs(self.vy) > 15
        if self.moving:
            self.walk_t += dt * (6 + st.speed * 4)
            if abs(self.vx) > abs(self.vy):
                self.facing = "right" if self.vx > 0 else "left"
            else:
                self.facing = "down" if self.vy > 0 else "up"
        g.move_player(self, self.vx * dt, self.vy * dt)
        self.trail.append((self.x, self.y))
        # стрельба
        self.shoot_dir = sdir
        self.fire_cool -= dt
        if self.burst_q > 0:
            self.burst_t -= dt
            if self.burst_t <= 0 and self.last_dir:
                self.burst_t = 0.06
                self.burst_q -= 1
                self.fire(g, self.last_dir, burst_child=True)
        if "brim" in st.flags and "sword" not in st.flags:
            if sdir and not self.no_shoot:
                self.brim_charge = min(1.0, self.brim_charge + dt / max(0.5, st.fire_delay * 2.6))
                self.last_dir = sdir
            elif self.brim_charge > 0:
                if self.brim_charge >= 1.0 and self.last_dir:
                    dx, dy = DIRS[self.last_dir]
                    g.beams.append(Beam(self.x, self.y - 6, math.atan2(dy, dx), 500, 12, 0.0, 0.45, st.damage * 0.75,
                                        (220, 30, 30), friendly=True, follow=self, src_off=6))
                    g.shake(3)
                self.brim_charge = 0.0
        elif sdir and self.fire_cool <= 0 and not self.no_shoot:
            self.last_dir = sdir
            self.fire(g, sdir)
            self.fire_cool = st.fire_delay
            if "burst" in st.flags:
                self.burst_q = 2
                self.burst_t = 0.07
        if sdir:
            self.facing = sdir

    last_dir = None

    def fire(self, g, d, burst_child=False):
        st = self.stats
        dx, dy = DIRS[d]
        self.shoot_pose = 0.12
        if "sword" in st.flags:
            self.swing(g, d)
            return
        sp = 230 * st.sspeed
        self.eye ^= 1
        side = (4 if self.eye else -4)
        ox, oy = (side if dy else 0), (side * 0.5 if dx else 0)
        if self.shrink_t > 0:
            ox *= 0.5
            oy *= 0.5
        if "laser" in st.flags:
            g.beams.append(Beam(self.x + ox, self.y - 6 + oy, math.atan2(dy, dx), st.range * 1.6, 3, 0.0, 0.08, st.damage,
                                (255, 60, 60), friendly=True, src_off=4))
            g.sfx("shoot", 0.4)
            return
        dirs = [(0.0, 0.0)]
        if "double" in st.flags:
            dirs = [(-4, 0.0), (4, 0.0)]
        if "triple" in st.flags:
            dirs = [(0, -0.18), (0, 0.0), (0, 0.18)]
            if "double" in st.flags:
                dirs = [(0, -0.24), (0, -0.08), (0, 0.08), (0, 0.24)]
        if "dnd" in self.forms:
            self.d20_count = getattr(self, "d20_count", 0) + 1
        base_a = math.atan2(dy, dx)
        for (off, da) in dirs:
            a = base_a + da
            vx, vy = from_ang(a, sp)
            vx += self.vx * 0.35
            vy += self.vy * 0.35
            px = self.x + ox + (-dy) * off
            py = self.y - 2 + oy + dx * off
            dmg = st.damage * (0.9 if len(dirs) > 2 else 1.0)
            t = Tear(px, py, vx, vy, dmg, st, g)
            if "dnd" in self.forms and self.d20_count % 10 == 0:
                t.dmg *= 3
                t.col = (255, 120, 30)
                t.r *= 1.5
                t.flags.add("burn")
            if self.shrink_t > 0:
                t.r *= 0.7
            g.tears.append(t)
        if "back" in st.flags:
            vx, vy = from_ang(base_a + math.pi, sp)
            g.tears.append(Tear(self.x, self.y - 2, vx, vy, st.damage, st, g))
        g.sfx("shoot", 0.5)

    def swing(self, g, d):
        self.sword_t = 0.18
        self.sword_dir = d
        g.sfx("sword")
        dx, dy = DIRS[d]
        cx, cy = self.x + dx * 18, self.y - 4 + dy * 18
        for e in g.room.enemies:
            if not e.dead and e.hittable and dist(e.x, e.y, cx, cy) < e.r + 20:
                e.hurt(g, self.stats.damage * 2.2, dx * 80, dy * 80, self)
        for es in g.eshots:
            if not es.friendly and dist(es.x, es.y, cx, cy) < 20:
                es.dead = True
        # волна меча при полном здоровье
        if True:
            sp = 300
            t = Tear(self.x, self.y - 4, dx * sp, dy * sp, self.stats.damage * 1.2, self.stats, g, r=6, col=(250, 230, 120), life_range=260)
            t.flags = {"pierce", "spectral"}
            g.tears.append(t)

    # ------------------------------------------------ отрисовка
    def draw(self, surf, g):
        if self.inv > 0 and int(self.inv * 16) % 2 == 0 and self.hold_t <= 0:
            return
        ex = set()
        if "angel" in self.forms:
            ex |= {"halo", "wings"}
        if "cat" in self.forms:
            ex.add("cat_ears")
        if "dnd" in self.forms:
            ex.add("wizard")
        if self.evil >= 2:
            ex.add("evil")
        if self.evil >= 3:
            ex.add("horns")
        if self.has("halo") and "halo" not in ex:
            ex.add("halo")
        if self.has("thorns"):
            ex.add("thorns")
        if self.has("wings"):
            ex.add("wings")
        pose = None
        if self.hold_t > 0:
            pose = "hold"
        elif self.shoot_pose > 0:
            pose = "shoot"
        fr = int(self.walk_t) % 4 if self.moving else 0
        s = person_frames(self.spec, "down" if pose == "hold" else self.facing, fr, 1, pose, tuple(sorted(ex)))
        k = 0.55 if self.shrink_t > 0 else 1.0
        if k != 1.0:
            s = pygame.transform.scale(s, (int(s.get_width() * k), int(s.get_height() * k)))
        if self.evil >= 1:
            gl = light_glow(18, (160, 0, 20), 70)
            surf.blit(gl, (self.x - 18, self.y - 24), special_flags=pygame.BLEND_RGB_ADD)
        sh = shadow_surf(int(16 * k), int(6 * k), 90)
        surf.blit(sh, (self.x - sh.get_width() / 2, self.y + 4 * k))
        fly = (math.sin(self.t * 4) * 2 - 3) if self.flight else 0
        bx = self.x - s.get_width() / 2
        by = self.y - s.get_height() + 9 * k + fly
        if g.hurt_flash > 0.15:
            s = flash_red(s)
        surf.blit(s, (bx, by))
        if self.hold_t > 0 and self.hold_item:
            ic = item_icon(self.hold_item)
            surf.blit(ic, (self.x - ic.get_width() / 2, by - 12))
        if self.brim_charge > 0:
            r = int(3 + self.brim_charge * 6)
            col = (255, 40, 40) if self.brim_charge >= 1 and int(self.t * 12) % 2 else (200, 30, 30)
            pygame.draw.circle(surf, col, (int(self.x), int(by + 8)), r, 1)
        if self.sword_t > 0:
            dx, dy = DIRS[self.sword_dir]
            a0 = math.atan2(dy, dx)
            prog = 1 - self.sword_t / 0.18
            for k2 in range(5):
                a = a0 - 1.2 + prog * 2.4 - k2 * 0.12
                x1, y1 = self.x + math.cos(a) * 6, self.y - 4 + math.sin(a) * 6
                x2, y2 = self.x + math.cos(a) * 26, self.y - 4 + math.sin(a) * 26
                c = (255, 255, 255) if k2 == 0 else (200, 200, 230)
                pygame.draw.line(surf, c, (x1, y1), (x2, y2), 3 if k2 == 0 else 1)

# ============================================================================
#                                  ВРАГИ
# ============================================================================
ENEMY_DEFS = {
    # --- квартира
    "fly":      dict(name="Муха", hp=4, r=5, speed=45, flying=True, beh="fly", spr="fly"),
    "afly":     dict(name="Злая муха", hp=6, r=5, speed=70, flying=True, beh="chase_fly", spr="afly"),
    "roach":    dict(name="Таракан", hp=7, r=6, speed=100, beh="scuttle", spr="roach"),
    "vacuum":   dict(name="Робот-пылесос", hp=20, r=10, speed=35, beh="charger", spr="vacuum", charge=230),
    "sock":     dict(name="Злой носок", hp=11, r=7, beh="hopper", spr="sock"),
    "cactus":   dict(name="Кактус", hp=14, r=9, beh="turret_aim", spr="cactus", rate=1.9, solid=True),
    "botik":    dict(name="Ботик", hp=15, r=8, speed=38, beh="walker", spr="botik"),
    "mold":     dict(name="Плесень", hp=13, r=9, beh="turret4", spr="mold", rate=2.3, solid=True),
    # --- школа
    "dvoechnik": dict(name="Двоечник", hp=17, r=8, speed=48, beh="walker", spr="dvoechnik"),
    "plane":    dict(name="Самолётик", hp=8, r=7, speed=85, flying=True, beh="bouncer", spr="plane"),
    "smoke":    dict(name="Дымок-облачко", hp=12, r=8, speed=30, flying=True, beh="drift_shoot", spr="smoke", rate=2.6, shot="ash", creep=True),
    "journal":  dict(name="Журнал", hp=20, r=9, beh="turret8", spr="journal", rate=2.6, solid=True),
    "chalk":    dict(name="Мелок", hp=14, r=7, speed=40, beh="charger", spr="chalk", charge=250),
    "butt":     dict(name="Бычок", hp=9, r=6, beh="hopper", spr="butt", fire=True),
    # --- лёгкие
    "tar":      dict(name="Смола", hp=22, r=9, speed=32, beh="walker", spr="tar", split="tar_s", creep=True),
    "tar_s":    dict(name="Капля смолы", hp=8, r=6, speed=48, beh="walker", spr="tar_s"),
    "rachok":   dict(name="Рачок", hp=16, r=9, speed=40, beh="charger", spr="rachok", charge=240),
    "nicotine": dict(name="Никотиновая муха", hp=8, r=5, speed=75, flying=True, beh="chase_fly", spr="nicotine"),
    "bronch":   dict(name="Бронх", hp=24, r=10, beh="turret_ring", spr="bronch", rate=2.4, solid=True),
    "cell":     dict(name="Клетка", hp=15, r=8, beh="hopper", spr="cell"),
    # --- тёмная квартира
    "ghost":    dict(name="П-п-призрак", hp=17, r=8, speed=35, flying=True, beh="drift_shoot", spr="ghost", rate=2.2, shot="letter"),
    "wisp":     dict(name="Огонёк", hp=11, r=6, speed=70, flying=True, beh="chase_fly", spr="wisp", fire=True),
    "shadow":   dict(name="Тень", hp=22, r=8, speed=62, beh="walker", spr="shadow"),
    "phone":    dict(name="Телефон с дачи", hp=18, r=9, beh="turret_aim", spr="phone", rate=2.4, burst=3, solid=True),
    # --- рай
    "angel":    dict(name="Ангелочек", hp=26, r=8, speed=40, flying=True, beh="drift_shoot", spr="angel", rate=2.0, shot="feather"),
}

FLOOR_ENEMIES = {
    "apartment": ["fly", "afly", "roach", "vacuum", "sock", "cactus", "botik", "mold"],
    "school": ["dvoechnik", "plane", "smoke", "journal", "chalk", "butt", "afly"],
    "lungs": ["tar", "rachok", "nicotine", "bronch", "cell", "smoke"],
    "dark": ["ghost", "wisp", "shadow", "phone", "vacuum", "roach"],
}

SHOT_STYLE = {
    "blood": dict(kind="blood", col=(210, 30, 30), r=4),
    "ash": dict(kind="blood", col=(120, 120, 124), r=4),
    "letter": dict(kind="letter", col=(255, 80, 80), r=5),
    "feather": dict(kind="feather", col=(250, 250, 255), r=5),
    "tar": dict(kind="blood", col=(40, 34, 40), r=4),
    "fire": dict(kind="fire", col=(255, 140, 40), r=5),
}


class Enemy(Ent):
    is_boss = False
    hittable = True

    def __init__(self, kind, x, y, g):
        super().__init__(x, y)
        d = ENEMY_DEFS.get(kind, {})
        self.kind = kind
        self.d = d
        self.name = d.get("name", kind)
        self.max_hp = self.hp = d.get("hp", 10) * g.hp_scale
        self.r = d.get("r", 7)
        self.speed = d.get("speed", 40)
        self.flying = d.get("flying", False)
        self.beh = d.get("beh", "walker")
        self.spr = d.get("spr", kind)
        self.contact = g.contact_dmg
        self.spawn_t = 0.45
        self.flash = 0.0
        self.poison = self.burn = self.slow = 0.0
        self.poison_dmg = self.burn_dmg = 1.0
        self.dot_t = 0.0
        self.state = "idle"
        self.st_t = random.uniform(0.3, 1.2)
        self.cool = d.get("rate", 2.0) * random.uniform(0.6, 1.2)
        self.h = 0.0
        self.air = False
        self.cdir = (0, 0)
        self.anim = random.random() * 4
        self.mass = 1.0
        self.solid_e = d.get("solid", False)
        self.kvx = self.kvy = 0.0
        self.no_contact = False
        self.invuln = False
        self.ang = random.uniform(0, math.pi * 2)
        if self.beh == "bouncer":
            a = random.choice([0.785, 2.356, 3.927, 5.498])
            self.vx, self.vy = from_ang(a, self.speed)

    # -------------------------------------------- урон
    def hurt(self, g, dmg, kx=0.0, ky=0.0, src=None):
        if self.dead or self.spawn_t > 0 or self.invuln:
            if self.invuln and self.is_boss:
                self.on_invuln_hit(g, src)
            return
        self.hp -= dmg
        self.flash = 0.1
        self.kvx += kx / self.mass
        self.kvy += ky / self.mass
        g.sfx("hit", 0.35)
        if self.hp <= 0:
            self.die(g)

    def on_invuln_hit(self, g, src):
        pass

    def die(self, g):
        if self.dead:
            return
        self.dead = True
        g.sfx("die", 0.6)
        col = (200, 20, 30) if self.kind not in ("tar", "tar_s", "smoke", "ghost", "plane", "journal", "chalk") else (60, 60, 70)
        if self.kind in ("smoke", "ghost", "plane", "angel"):
            col = (220, 220, 230)
        g.parts.burst(self.x, self.y, 16, col, 110, 0.5, 3, grav=150)
        g.room.decal_splat(self.x, self.y, col, self.r)
        split = self.d.get("split")
        if split:
            for k in (-1, 1):
                e = Enemy(split, self.x + k * 6, self.y, g)
                e.spawn_t = 0.0
                e.kvx = k * 100
                g.room.enemies.append(e)
        if self.d.get("creep") and not self.flying:
            g.creep.append(Creep(self.x, self.y + 3, 16, 3.0, (40, 36, 44), 1))
        g.on_enemy_killed(self)

    # -------------------------------------------- обновление
    def update(self, g, dt):
        self.t += dt
        self.anim += dt * 8
        if self.spawn_t > 0:
            self.spawn_t -= dt
            return
        self.flash = max(0.0, self.flash - dt)
        if self.poison > 0 or self.burn > 0:
            self.dot_t -= dt
            if self.dot_t <= 0:
                self.dot_t = 0.5
                if self.poison > 0:
                    self.hp -= self.poison_dmg
                    g.parts.burst(self.x, self.y, 3, (110, 210, 90), 30, 0.3, 2)
                if self.burn > 0:
                    self.hp -= self.burn_dmg
                    g.parts.burst(self.x, self.y - 4, 3, (255, 140, 40), 30, 0.3, 2, grav=-60)
                self.flash = 0.05
                if self.hp <= 0:
                    self.die(g)
                    return
            self.poison = max(0, self.poison - dt)
            self.burn = max(0, self.burn - dt)
        self.slow = max(0, self.slow - dt)
        sc = 0.5 if (self.slow > 0) else 1.0
        sc *= g.enemy_time_scale()
        getattr(self, "b_" + self.beh, self.b_walker)(g, dt * sc)
        # отбрасывание
        if self.kvx or self.kvy:
            move_circle(self, self.kvx * dt, self.kvy * dt, g, self.flying or self.air)
            self.kvx *= 0.82 ** (dt * 60)
            self.kvy *= 0.82 ** (dt * 60)
            if abs(self.kvx) + abs(self.kvy) < 3:
                self.kvx = self.kvy = 0.0
        # контакт с игроком
        p = g.player
        if not self.no_contact and not self.air and p and not p.dead:
            rr = (self.r + p.hr) * 0.9
            if (p.x - self.x) ** 2 + (p.y - self.y) ** 2 < rr * rr:
                p.hurt(g, self.contact, self)

    def mv(self, g, vx, vy, dt):
        return move_circle(self, vx * dt, vy * dt, g, self.flying or self.air)

    # -------------------------------------------- поведения
    def b_fly(self, g, dt):
        p = g.player
        self.ang += random.uniform(-4, 4) * dt
        nx, ny = norm(p.x - self.x, p.y - self.y)
        vx = math.cos(self.ang) * self.speed + nx * self.speed * 0.4
        vy = math.sin(self.ang) * self.speed + ny * self.speed * 0.4
        self.mv(g, vx, vy, dt)

    def b_chase_fly(self, g, dt):
        p = g.player
        nx, ny = norm(p.x - self.x, p.y - self.y)
        wob = math.sin(self.t * 6 + self.ang) * 0.5
        vx = (nx - ny * wob) * self.speed
        vy = (ny + nx * wob) * self.speed
        self.mv(g, vx, vy, dt)
        if self.d.get("fire") and random.random() < dt * 1.2:
            g.parts.add(self.x, self.y, 0, -30, 0.5, (255, 150, 50), 2)

    def b_scuttle(self, g, dt):
        p = g.player
        self.st_t -= dt
        if self.st_t <= 0:
            self.st_t = random.uniform(0.25, 0.7)
            a = ang_to(self.x, self.y, p.x, p.y) + random.uniform(-1.3, 1.3)
            self.cdir = from_ang(a, 1)
        hx, hy = self.mv(g, self.cdir[0] * self.speed, self.cdir[1] * self.speed, dt)
        if hx or hy:
            self.st_t = 0

    def b_walker(self, g, dt):
        p = g.player
        dx, dy = g.flow_dir(self.x, self.y)
        if dx == 0 and dy == 0:
            dx, dy = norm(p.x - self.x, p.y - self.y)
        d = dist(self.x, self.y, p.x, p.y)
        if d < 40:
            dx, dy = norm(p.x - self.x, p.y - self.y)
        self.mv(g, dx * self.speed, dy * self.speed, dt)

    def b_charger(self, g, dt):
        p = g.player
        if self.state == "charge":
            hx, hy = self.mv(g, self.cdir[0] * self.d.get("charge", 220), self.cdir[1] * self.d.get("charge", 220), dt)
            if random.random() < 0.5:
                g.parts.add(self.x - self.cdir[0] * 8, self.y - self.cdir[1] * 8, 0, 0, 0.3, (200, 200, 200), 2)
            if hx or hy:
                self.state = "stun"
                self.st_t = 0.7
                g.shake(1.5)
            return
        if self.state == "stun":
            self.st_t -= dt
            if self.st_t <= 0:
                self.state = "idle"
            return
        self.st_t -= dt
        if self.st_t <= 0:
            self.st_t = random.uniform(0.6, 1.5)
            self.cdir = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        self.mv(g, self.cdir[0] * self.speed, self.cdir[1] * self.speed, dt)
        if abs(p.y - self.y) < 9 and abs(p.x - self.x) < 220:
            self.cdir = (1 if p.x > self.x else -1, 0)
            self.state = "charge"
            g.sfx("warn", 0.3)
        elif abs(p.x - self.x) < 9 and abs(p.y - self.y) < 220:
            self.cdir = (0, 1 if p.y > self.y else -1)
            self.state = "charge"
            g.sfx("warn", 0.3)

    def b_hopper(self, g, dt):
        p = g.player
        if self.state == "jump":
            self.st_t += dt
            k = self.st_t / 0.55
            self.h = math.sin(min(1, k) * math.pi) * 22
            self.mv(g, self.cdir[0], self.cdir[1], dt)
            if k >= 1:
                self.state = "idle"
                self.air = False
                self.h = 0
                self.st_t = random.uniform(0.5, 1.1)
                g.parts.burst(self.x, self.y + 4, 5, (160, 150, 140), 40, 0.3, 2)
                if self.d.get("fire"):
                    for a in range(4):
                        vx, vy = from_ang(a * math.pi / 2, 110)
                        g.eshot(self.x, self.y, vx, vy, **SHOT_STYLE["fire"])
            return
        self.st_t -= dt
        if self.st_t <= 0:
            tx = p.x + random.uniform(-50, 50)
            ty = p.y + random.uniform(-50, 50)
            d = dist(self.x, self.y, tx, ty)
            d2 = min(d, 110)
            nx, ny = norm(tx - self.x, ty - self.y)
            self.cdir = (nx * d2 / 0.55, ny * d2 / 0.55)
            self.state = "jump"
            self.air = True
            self.st_t = 0

    def shoot_style(self):
        return SHOT_STYLE.get(self.d.get("shot", "blood"))

    def b_turret_aim(self, g, dt):
        p = g.player
        self.cool -= dt
        if self.cool <= 0:
            self.cool = self.d.get("rate", 2.0) * random.uniform(0.85, 1.15)
            a = ang_to(self.x, self.y, p.x, p.y)
            n = self.d.get("burst", 1)
            for k in range(n):
                vx, vy = from_ang(a, 130)
                g.eshot(self.x, self.y - 4, vx, vy, delay=k * 0.15, **self.shoot_style())
            self.flash_shot = 0.2

    def b_turret4(self, g, dt):
        self.cool -= dt
        if self.cool <= 0:
            self.cool = self.d.get("rate", 2.0)
            off = (math.pi / 4) if int(self.t / 2) % 2 else 0
            for k in range(4):
                vx, vy = from_ang(off + k * math.pi / 2, 115)
                g.eshot(self.x, self.y, vx, vy, **SHOT_STYLE["blood"])

    def b_turret8(self, g, dt):
        self.cool -= dt
        if self.cool <= 0:
            self.cool = self.d.get("rate", 2.5)
            for k in range(8):
                vx, vy = from_ang(k * math.pi / 4, 100)
                g.eshot(self.x, self.y, vx, vy, kind="blood", col=(220, 40, 40), r=4)

    def b_turret_ring(self, g, dt):
        self.cool -= dt
        if self.cool <= 0:
            self.cool = self.d.get("rate", 2.4)
            off = self.t * 0.7
            for k in range(6):
                vx, vy = from_ang(off + k * math.pi / 3, 95)
                g.eshot(self.x, self.y, vx, vy, kind="blood", col=(150, 30, 60), r=4, spin=0.6)

    def b_bouncer(self, g, dt):
        hx, hy = self.mv(g, self.vx, self.vy, dt)
        if hx:
            self.vx = -self.vx
        if hy:
            self.vy = -self.vy

    def b_drift_shoot(self, g, dt):
        p = g.player
        self.st_t -= dt
        if self.st_t <= 0:
            self.st_t = random.uniform(1.0, 2.0)
            tx = clamp(p.x + random.uniform(-120, 120), RX0 + 20, RX1 - 20)
            ty = clamp(p.y + random.uniform(-90, 90), RY0 + 20, RY1 - 20)
            self.cdir = norm(tx - self.x, ty - self.y)
        self.mv(g, self.cdir[0] * self.speed, self.cdir[1] * self.speed, dt)
        self.cool -= dt
        if self.cool <= 0:
            self.cool = self.d.get("rate", 2.0) * random.uniform(0.8, 1.2)
            a = ang_to(self.x, self.y, p.x, p.y)
            stl = self.shoot_style()
            if self.kind == "angel":
                for da in (-0.25, 0, 0.25):
                    vx, vy = from_ang(a + da, 125)
                    g.eshot(self.x, self.y, vx, vy, **stl)
            else:
                vx, vy = from_ang(a, 120)
                g.eshot(self.x, self.y, vx, vy, **stl)
        if self.d.get("creep") and random.random() < dt * 0.5:
            g.creep.append(Creep(self.x, self.y + 6, 10, 2.5, (110, 110, 116), 1))

    # -------------------------------------------- отрисовка
    def sprite(self):
        flag = False
        if self.beh == "charger":
            flag = self.state == "charge"
        elif self.beh in ("turret_aim", "turret4", "turret8", "turret_ring"):
            flag = self.cool < 0.35
        return enemy_sprite(self.spr, int(self.anim), flag)

    def draw(self, surf, g):
        s = self.sprite()
        if self.spawn_t > 0:
            k = 1 - self.spawn_t / 0.45
            if k < 0.05:
                return
            s = pygame.transform.scale(s, (max(1, int(s.get_width() * k)), max(1, int(s.get_height() * k))))
        if self.flash > 0:
            s = flash_white(s) if int(self.flash * 40) % 2 == 0 else flash_red(s)
        elif self.poison > 0 and int(self.t * 8) % 2 == 0:
            s = tinted(s, (120, 220, 100), 200) if False else s
        sw = max(8, int(self.r * 2))
        sh = shadow_surf(sw, max(3, sw // 3), 80)
        surf.blit(sh, (self.x - sw / 2, self.y + self.r * 0.5))
        lift = (8 if self.flying else 0) + self.h
        if self.flying:
            lift += math.sin(self.t * 5 + self.ang) * 2
        surf.blit(s, (self.x - s.get_width() / 2, self.y - s.get_height() / 2 - lift - (s.get_height() / 2 - self.r) * 0.6))
        if self.slow > 0:
            pygame.draw.circle(surf, (255, 150, 210), (int(self.x), int(self.y - lift)), int(self.r + 2), 1)

# ============================================================================
#                                  БОССЫ
# ============================================================================
class Marker(Ent):
    """Предупреждающий круг/линия на полу."""

    def __init__(self, x, y, r, dur, col=(255, 40, 40)):
        super().__init__(x, y)
        self.r, self.dur, self.col = r, dur, col

    def update(self, g, dt):
        self.t += dt
        if self.t >= self.dur:
            self.dead = True

    def draw(self, surf, g):
        k = self.t / self.dur
        c = self.col if int(self.t * 14) % 2 == 0 else (255, 255, 255)
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), int(self.r), 1)
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), max(1, int(self.r * k)), 1)

    @property
    def sort_y(self):
        return -999


class Boss(Enemy):
    is_boss = True
    sprite_u = 2
    bar_color = (200, 30, 40)

    def __init__(self, g, x, y, name, hp, r=14):
        Enemy.__init__(self, "boss", x, y, g)
        self.name = name
        self.max_hp = self.hp = hp
        self.r = r
        self.spawn_t = 0.0
        self.mass = 8.0
        self.contact = 2
        self.co = None
        self.wait = 0.0
        self.idle_t = 1.6
        self.phase = 1
        self.facing = "down"
        self.move_mode = "hover"
        self.tx, self.ty = x, y
        self.defeated = False
        self.flying = False
        self.last_attack = None
        self.bubble_txt = None
        self.bubble_t = 0.0
        self.hidden = False
        self.show_bar = True
        self.bar_text = None
        self.walk_anim = 0.0

    def say(self, txt, dur=2.0):
        self.bubble_txt = txt
        self.bubble_t = dur

    def attacks(self, g):
        return []

    def idle_time(self):
        return 0.9 if self.phase == 1 else 0.6

    def pick_attack(self, g):
        opts = self.attacks(g)
        if not opts:
            return None
        if len(opts) > 1 and self.last_attack in opts:
            opts = [o for o in opts if o != self.last_attack] or opts
        a = random.choice(opts)
        self.last_attack = a
        return a(g)

    def hurt(self, g, dmg, kx=0.0, ky=0.0, src=None):
        if self.defeated:
            return
        Enemy.hurt(self, g, dmg, kx * 0.2, ky * 0.2, src)

    def die(self, g):
        if self.defeated:
            return
        self.hp = 0
        self.defeated = True
        self.co = None
        self.invuln = True
        self.no_contact = True
        g.boss_defeated(self)

    def update(self, g, dt):
        self.t += dt
        self.anim += dt * 8
        self.flash = max(0.0, self.flash - dt)
        self.bubble_t = max(0.0, self.bubble_t - dt)
        if self.poison > 0 or self.burn > 0:
            self.dot_t -= dt
            if self.dot_t <= 0:
                self.dot_t = 0.5
                if self.poison > 0:
                    self.hp -= self.poison_dmg
                if self.burn > 0:
                    self.hp -= self.burn_dmg
                if self.hp <= 0:
                    self.die(g)
            self.poison = max(0, self.poison - dt)
            self.burn = max(0, self.burn - dt)
        self.slow = max(0, self.slow - dt)
        if self.defeated:
            self.on_defeated_update(g, dt)
            return
        sc = (0.7 if self.slow > 0 else 1.0) * g.enemy_time_scale()
        dts = dt * sc
        self.check_phase(g)
        if self.co is None:
            self.idle_t -= dts
            self.idle_move(g, dts)
            if self.idle_t <= 0:
                self.co = self.pick_attack(g)
                self.wait = 0.0
                self.move_mode = "hover"
        else:
            self.wait -= dts
            self.attack_move(g, dts)
            guard = 0
            while self.co is not None and self.wait <= 0 and guard < 50:
                guard += 1
                try:
                    self.wait += next(self.co)
                except StopIteration:
                    self.co = None
                    self.idle_t = self.idle_time()
        if self.kvx or self.kvy:
            move_circle(self, self.kvx * dt, self.kvy * dt, g, self.flying)
            self.kvx *= 0.8
            self.kvy *= 0.8
        p = g.player
        if not self.no_contact and not self.hidden and p and not p.dead:
            rr = (self.r + p.hr) * 0.85
            if (p.x - self.x) ** 2 + (p.y - self.y) ** 2 < rr * rr:
                p.hurt(g, self.contact, self)

    def check_phase(self, g):
        pass

    def on_defeated_update(self, g, dt):
        pass

    def idle_move(self, g, dt):
        p = g.player
        d = dist(self.x, self.y, p.x, p.y)
        if d > 90:
            nx, ny = norm(p.x - self.x, p.y - self.y)
            self.walk(g, nx * self.speed, ny * self.speed, dt)
        else:
            a = self.t * 0.8
            self.walk(g, math.cos(a) * self.speed * 0.6, math.sin(a) * self.speed * 0.6, dt)

    def attack_move(self, g, dt):
        if self.move_mode == "to":
            nx, ny = norm(self.tx - self.x, self.ty - self.y)
            d = dist(self.x, self.y, self.tx, self.ty)
            if d > 3:
                sp = min(self.speed * 2.2, d / dt)
                self.walk(g, nx * sp, ny * sp, dt)
        elif self.move_mode == "dash":
            hx, hy = self.walk(g, self.vx, self.vy, dt)
            if hx or hy:
                self.on_wall_hit(g)
                self.move_mode = "still"
        elif self.move_mode == "chase":
            self.idle_move(g, dt)

    def on_wall_hit(self, g):
        pass

    def walk(self, g, vx, vy, dt):
        if abs(vx) + abs(vy) > 5:
            self.walk_anim += dt * 7
            if abs(vx) > abs(vy):
                self.facing = "right" if vx > 0 else "left"
            else:
                self.facing = "down" if vy > 0 else "up"
        return move_circle(self, vx * dt, vy * dt, g, self.flying)

    # ---- общие паттерны
    def ring(self, g, n, sp, off=0.0, **kw):
        for k in range(n):
            vx, vy = from_ang(off + k * math.pi * 2 / n, sp)
            g.eshot(self.x, self.y - 6, vx, vy, **kw)

    def aimed(self, g, n, arc, sp, **kw):
        p = g.player
        a = ang_to(self.x, self.y, p.x, p.y)
        for k in range(n):
            da = 0 if n == 1 else -arc / 2 + arc * k / (n - 1)
            vx, vy = from_ang(a + da, sp)
            g.eshot(self.x, self.y - 6, vx, vy, **kw)

    def body_sprite(self):
        return None

    def draw(self, surf, g):
        if self.hidden:
            return
        s = self.body_sprite()
        if s is None:
            return
        if self.flash > 0:
            s = flash_white(s) if int(self.flash * 40) % 2 == 0 else flash_red(s)
        sw = int(self.r * 2.4)
        sh = shadow_surf(sw, max(4, sw // 3), 90)
        lift = 6 + math.sin(self.t * 2.5) * 3 if self.flying else 0
        surf.blit(sh, (self.x - sw / 2, self.y + self.r * 0.45))
        surf.blit(s, (self.x - s.get_width() / 2, self.y - s.get_height() + self.r * 0.9 - lift))

    def draw_bubble(self, scr, g):
        if self.bubble_t > 0 and self.bubble_txt and not self.hidden:
            x = (self.x) * 2
            y = (self.y - 50) * 2
            txt = text(self.bubble_txt, 26, (255, 255, 255), (0, 0, 0), 2)
            w = txt.get_width() + 16
            r = pygame.Rect(0, 0, w, txt.get_height() + 10)
            r.center = (int(clamp(x, w / 2 + 4, SW - w / 2 - 4)), int(max(30, y)))
            pygame.draw.rect(scr, (20, 16, 24), r, border_radius=8)
            pygame.draw.rect(scr, (255, 255, 255), r, 2, border_radius=8)
            scr.blit(txt, (r.x + 8, r.y + 5))


# ---------------------------------------------------------------- Валерий
class BossValerii(Boss):
    def __init__(self, g, x, y, final=False):
        hp = 720 if final else 4000
        super().__init__(g, x, y, "ВАЛЕРИЙ" if final else "ВАЛЕРИЙ (сдерживается)", hp, 13)
        self.final = final
        self.speed = 42 if final else 36
        self.fight_t = 0.0
        self.finale = False
        self.adds = 0
        if not final:
            self.bar_text = "∞"

    def body_sprite(self):
        fr = int(self.walk_anim) % 4
        return person_frames("valerii", self.facing if not self.finale else "down", fr, 2, None, ("angry",) if self.phase > 1 else ())

    def check_phase(self, g):
        if self.final and self.phase == 1 and self.hp < self.max_hp * 0.5:
            self.phase = 2
            self.say("Т-Т-ТЕПЕРЬ Я СЕРЬЁЗНО!!!", 2.5)
            g.sfx("roar")
            g.shake(6)

    def update(self, g, dt):
        self.fight_t += dt
        if not self.final and not self.finale and self.fight_t > 21.0:
            self.finale = True
            self.co = self.a_finale(g)
            self.wait = 0
            self.invuln = True
        if not self.final:
            self.hp = max(self.hp, self.max_hp * 0.93)
        super().update(g, dt)
        if self.final and self.phase == 2 and self.co is not None and random.random() < dt * 2:
            g.creep.append(Creep(self.x, self.y + 6, 12, 2.5, (255, 120, 40), 1))

    def attacks(self, g):
        if self.finale:
            return []
        a = [self.a_stutter, self.a_fireballs, self.a_charge, self.a_belt]
        if self.final:
            a.append(self.a_summon)
            if self.phase == 2:
                a += [self.a_spiral, self.a_spiral]
        return a

    def a_stutter(self, g):
        self.move_mode = "still"
        self.say(random.choice(["П-п-п-п-п!", "П-П-ПАСКУДА!", "С-с-сынок!"]), 1.5)
        n = 4 if not self.final else (5 if self.phase == 1 else 6)
        for b in range(n):
            p = g.player
            a = ang_to(self.x, self.y, p.x, p.y)
            for k in range(5):
                vx, vy = from_ang(a + random.uniform(-0.12, 0.12), 150 + k * 6)
                g.eshot(self.x, self.y - 10, vx, vy, kind="letter", col=(255, 80, 80), r=5, dmg=1)
                g.sfx("blip", 0.3, cool=0.0)
                yield 0.07
            yield 0.35
        yield 0.3

    def a_fireballs(self, g):
        self.move_mode = "still"
        g.sfx("fire")
        n = 3 if self.phase == 1 else 4
        for k in range(n):
            p = g.player
            a = ang_to(self.x, self.y, p.x, p.y) + random.uniform(-0.3, 0.3)
            vx, vy = from_ang(a, 90)
            g.eshot(self.x, self.y - 10, vx, vy, kind="fire", col=(255, 130, 30), r=9, dmg=2, life=1.4, pop=8 if self.phase == 1 else 10, pop_speed=110,
                    pop_kind="fire")
            yield 0.45
        yield 0.6

    def a_charge(self, g):
        self.move_mode = "still"
        p = g.player
        a = ang_to(self.x, self.y, p.x, p.y)
        g.markers.append(Marker(p.x, p.y, 14, 0.7))
        g.sfx("warn")
        self.say("ЩАС ПОЛУЧИШЬ!", 1.0)
        for _ in range(7):
            self.kvx += random.uniform(-30, 30)
            yield 0.1
        self.vx, self.vy = from_ang(a, 300 if self.final else 260)
        self.move_mode = "dash"
        yield 1.4
        self.move_mode = "still"
        yield 0.4

    def on_wall_hit(self, g):
        g.shake(7)
        g.sfx("slam")
        self.ring(g, 12 if self.phase == 1 else 16, 120, kind="blood", col=(220, 60, 40), r=4)

    def a_belt(self, g):
        self.move_mode = "still"
        self.say("РЕМЕНЬ!", 1.0)
        p = g.player
        a0 = ang_to(self.x, self.y, p.x, p.y)
        n = 14 if self.phase == 1 else 20
        for k in range(n):
            a = a0 - 1.1 + 2.2 * k / (n - 1)
            vx, vy = from_ang(a, 170)
            g.eshot(self.x, self.y - 8, vx, vy, kind="blood", col=(140, 90, 50), r=4, dmg=1)
            yield 0.035
        yield 0.5

    def a_spiral(self, g):
        self.move_mode = "still"
        self.say("ОГОНЬ!!!", 1.0)
        off = random.uniform(0, 6)
        for k in range(28):
            for arm in range(3):
                vx, vy = from_ang(off + k * 0.27 + arm * math.pi * 2 / 3, 115)
                g.eshot(self.x, self.y - 8, vx, vy, kind="fire", col=(255, 140, 40), r=4)
            yield 0.09
        yield 0.5

    def a_summon(self, g):
        if self.adds >= 2 or sum(1 for e in g.room.enemies if not e.dead and not e.is_boss) >= 2:
            self.last_attack = None
            yield 0.1
            return
        self.say("Алло, дача?", 1.5)
        for pos in ((RX0 + 40, RY0 + 30), (RX1 - 40, RY0 + 30)):
            e = Enemy("phone", pos[0], pos[1], g)
            g.room.enemies.append(e)
        self.adds += 2
        yield 1.0

    def a_finale(self, g):
        self.move_mode = "still"
        self.co_finale = True
        g.clear_bullets()
        self.say("Х-х-хватит игр.", 2.5)
        yield 1.6
        self.tx, self.ty = RCX, RY0 + 40
        self.move_mode = "to"
        yield 1.2
        self.move_mode = "still"
        self.say("ОГНЕННЫЙ ШАР!!!", 3)
        g.sfx("roar")
        fb = BigFireball(self.x, self.y - 40)
        g.effects.append(fb)
        for _ in range(30):
            fb.grow += 0.06
            g.shake(2)
            yield 0.1
        fb.falling = True
        g.sfx("fire")
        yield 4.0


class BigFireball(Ent):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.grow = 0.3
        self.falling = False
        self.hit = False

    def update(self, g, dt):
        self.t += dt
        p = g.player
        if self.falling:
            nx, ny = norm(p.x - self.x, p.y - self.y)
            self.x += nx * 140 * dt
            self.y += ny * 140 * dt
            self.grow += dt * 1.2
            if not self.hit and dist(self.x, self.y, p.x, p.y) < 30 * self.grow:
                self.hit = True
                g.story.val1_death()
        if random.random() < 0.8:
            a = random.uniform(0, math.pi * 2)
            r = 30 * self.grow
            g.parts.add(self.x + math.cos(a) * r, self.y + math.sin(a) * r, 0, -40, 0.5, (255, random.randint(100, 220), 30), 3)

    def draw(self, surf, g):
        r = int(30 * self.grow)
        gl = light_glow(max(4, r * 2), (255, 140, 40), 140)
        surf.blit(gl, (self.x - gl.get_width() / 2, self.y - gl.get_height() / 2), special_flags=pygame.BLEND_RGB_ADD)
        pygame.draw.circle(surf, (200, 60, 0), (int(self.x), int(self.y)), r + 2)
        pygame.draw.circle(surf, (255, 140, 30), (int(self.x), int(self.y)), r)
        pygame.draw.circle(surf, (255, 230, 140), (int(self.x - r * 0.2), int(self.y - r * 0.2)), max(2, int(r * 0.5)))

    @property
    def sort_y(self):
        return 9999


# ---------------------------------------------------------------- Дымок (домейн)
class BossDymok(Boss):
    def __init__(self, g, x, y):
        super().__init__(g, x, y, "ГРОБНИЦА ЦАРАПАНИЙ", 1, 16)
        self.invuln = True
        self.survive = 24.0
        self.total = 24.0
        self.speed = 60
        self.flying = True
        self.no_contact = True
        self.bar_text = "продержись!"

    def body_sprite(self):
        return cached(("catboss", int(self.anim) % 4), lambda: draw_cat(2, int(self.anim) % 4, True))

    def update(self, g, dt):
        if not self.defeated:
            self.survive -= dt
            self.hp = max(0.001, self.survive / self.total)
            self.max_hp = 1.0
            if self.survive <= 0:
                self.defeated = True
                self.co = None
                g.clear_bullets()
                g.story.dymok_survived(self)
                return
        super().update(g, dt)

    def on_invuln_hit(self, g, src):
        if random.random() < 0.08:
            g.floater(self.x + random.uniform(-10, 10), self.y - 40, "мяу.", (255, 200, 200))

    def idle_move(self, g, dt):
        tx = RCX + math.sin(self.t * 0.7) * 120
        ty = RY0 + 50
        nx, ny = norm(tx - self.x, ty - self.y)
        self.walk(g, nx * self.speed, ny * self.speed, dt)

    def idle_time(self):
        return 0.5

    def attacks(self, g):
        return [self.a_slashes, self.a_paws, self.a_hair, self.a_slashes]

    def a_slashes(self, g):
        p = g.player
        n = 4 if self.survive > 12 else 6
        for k in range(n):
            a = random.uniform(0, math.pi)
            cx, cy = p.x + random.uniform(-30, 30), p.y + random.uniform(-30, 30)
            x0, y0 = cx - math.cos(a) * 500, cy - math.sin(a) * 500
            g.beams.append(Beam(x0, y0, a, 1000, 7, 0.75, 0.22, 1, (255, 40, 60)))
            g.sfx("warn", 0.4)
            yield 0.28
        yield 0.6

    def a_paws(self, g):
        for k in range(3):
            p = g.player
            x, y = p.x, p.y
            g.markers.append(Marker(x, y, 18, 0.6))
            for j in range(10):
                vx, vy = from_ang(j * math.pi / 5, 105)
                g.eshot(x, y, vx, vy, kind="claw", col=(255, 70, 70), r=5, delay=0.6)
            yield 0.55
        yield 0.5

    def a_hair(self, g):
        self.move_mode = "still"
        off = random.uniform(0, 6)
        for k in range(22):
            for arm in range(4):
                vx, vy = from_ang(off + k * 0.22 + arm * math.pi / 2, 100)
                g.eshot(self.x, self.y - 10, vx, vy, kind="nail", col=(200, 200, 210), r=4)
            yield 0.1
        yield 0.4


# ---------------------------------------------------------------- Табачное облако
class BossSmoke(Boss):
    def __init__(self, g, x, y):
        super().__init__(g, x, y, "ТАБАЧНОЕ ОБЛАКО", 320, 22)
        self.flying = True
        self.speed = 32
        self.adds = 0

    def body_sprite(self):
        return cached(("smokeboss", int(self.anim) % 4, self.phase), lambda: draw_cloud(2.4, int(self.anim) % 4, True, (150, 150, 158) if self.phase == 1 else (120, 110, 115),
                                                                                         angry=self.phase > 1, cig=True))

    def check_phase(self, g):
        if self.phase == 1 and self.hp < self.max_hp * 0.5:
            self.phase = 2
            g.sfx("roar")
            self.say("КХА-КХА!!! ЗАТЯЖКА!!!", 2)

    def attacks(self, g):
        a = [self.a_ash, self.a_ring, self.a_creep, self.a_puff]
        if self.phase == 2:
            a += [self.a_spiral, self.a_ring]
        return a

    def a_ash(self, g):
        for k in range(3 if self.phase == 1 else 4):
            self.aimed(g, 5, 0.9, 130, kind="blood", col=(120, 120, 126), r=5)
            yield 0.45
        yield 0.4

    def a_ring(self, g):
        for k in range(2 if self.phase == 1 else 3):
            self.ring(g, 14, 60, off=k * 0.2, kind="blood", col=(150, 150, 160), r=5, accel=60)
            yield 0.6
        yield 0.3

    def a_creep(self, g):
        self.move_mode = "chase"
        self.speed = 70
        for k in range(14):
            g.creep.append(Creep(self.x, self.y + 10, 16, 4.0, (100, 110, 90), 1))
            yield 0.15
        self.speed = 32
        yield 0.3

    def a_puff(self, g):
        if sum(1 for e in g.room.enemies if not e.dead and not e.is_boss) >= 3:
            yield 0.1
            return
        self.say("Пфф...", 1)
        for k in range(2):
            e = Enemy("smoke", self.x + (k * 2 - 1) * 24, self.y, g)
            g.room.enemies.append(e)
        yield 0.8

    def a_spiral(self, g):
        self.move_mode = "still"
        off = random.uniform(0, 6)
        for k in range(30):
            for arm in range(2):
                vx, vy = from_ang(off + k * 0.3 + arm * math.pi, 105)
                g.eshot(self.x, self.y, vx, vy, kind="blood", col=(130, 130, 140), r=4)
            yield 0.08
        yield 0.4


# ---------------------------------------------------------------- Раки
class BossRak(Boss):
    def __init__(self, g, x, y, big=False):
        if big:
            super().__init__(g, x, y, "ПОСЛЕДНИЙ РАК", 520, 26)
        else:
            super().__init__(g, x, y, "РАК", 110 * g.hp_scale, 13)
        self.big = big
        self.speed = 40 if big else 50
        self.u = 2.6 if big else 1.3
        self.adds = 0
        self.lying = 0.0

    def body_sprite(self):
        angry = self.phase > 1
        fr = int(self.anim) % 4 if not self.defeated else 0
        return cached(("rakboss", self.u, fr, angry, self.defeated), lambda: self._spr(fr, angry))

    def _spr(self, fr, angry):
        s = draw_lobster(self.u, fr, angry)
        if self.defeated:
            s = pygame.transform.rotate(s, 180)
        return s

    def check_phase(self, g):
        if self.big and self.phase == 1 and self.hp < self.max_hp * 0.45:
            self.phase = 2
            g.sfx("roar")
            g.shake(5)
            self.say("ЩЁЛК-ЩЁЛК!!!", 2)

    def attacks(self, g):
        if self.big:
            a = [self.a_slam, self.a_bubbles, self.a_charge, self.a_summon, self.a_spiral]
            if self.phase == 2:
                a += [self.a_slam, self.a_spiral]
            return a
        return [self.a_charge, self.a_bubbles, self.a_snap]

    def a_charge(self, g):
        self.move_mode = "still"
        for k in range(2 if self.big else 1):
            p = g.player
            a = ang_to(self.x, self.y, p.x, p.y)
            g.sfx("warn", 0.4)
            for _ in range(5):
                self.kvx += random.uniform(-25, 25)
                yield 0.08
            self.vx, self.vy = from_ang(a, 280 if self.big else 240)
            self.move_mode = "dash"
            yield 1.2
            self.move_mode = "still"
            yield 0.3
        yield 0.3

    def on_wall_hit(self, g):
        g.shake(5 if self.big else 3)
        g.sfx("slam", 0.6)
        self.ring(g, 10 if not self.big else 14, 110, kind="bubble", col=(120, 180, 255), r=4)

    def a_bubbles(self, g):
        for k in range(3 if not self.big else 5):
            self.aimed(g, 3 if not self.big else 5, 0.5, 140, kind="bubble", col=(130, 190, 255), r=5)
            yield 0.4
        yield 0.3

    def a_snap(self, g):
        self.say("Щёлк!", 0.8)
        self.ring(g, 8, 120, kind="claw", col=(80, 140, 255), r=5)
        yield 0.3
        self.ring(g, 8, 120, off=math.pi / 8, kind="claw", col=(80, 140, 255), r=5)
        yield 0.5

    def a_slam(self, g):
        for k in range(2 if self.phase == 1 else 3):
            p = g.player
            x, y = p.x, p.y
            g.markers.append(Marker(x, y, 22, 0.7))
            yield 0.7
            g.shake(6)
            g.sfx("slam")
            for j in range(16):
                vx, vy = from_ang(j * math.pi / 8, 120)
                g.eshot(x, y, vx, vy, kind="bubble", col=(80, 130, 230), r=4)
            g.creep.append(Creep(x, y, 22, 4, (40, 36, 44), 1))
            yield 0.3
        yield 0.4

    def a_summon(self, g):
        if sum(1 for e in g.room.enemies if not e.dead and not e.is_boss) >= 3:
            yield 0.1
            return
        self.say("Дети мои!", 1.2)
        for k in (-1, 1):
            e = Enemy("rachok", self.x + k * 40, self.y + 20, g)
            g.room.enemies.append(e)
        yield 1.0

    def a_spiral(self, g):
        self.move_mode = "still"
        off = random.uniform(0, 6)
        for k in range(26):
            for arm in range(2 if self.phase == 1 else 3):
                vx, vy = from_ang(off + k * 0.25 + arm * math.pi * 2 / (2 if self.phase == 1 else 3), 110)
                g.eshot(self.x, self.y, vx, vy, kind="bubble", col=(120, 180, 255), r=4)
            yield 0.09
        yield 0.4


# ---------------------------------------------------------------- Иисус
class BossJesus(Boss):
    def __init__(self, g, x, y):
        super().__init__(g, x, y, "ИИСУС", 1150, 14)
        self.flying = True
        self.speed = 45
        self.alpha = 255
        self.no_contact = False

    def body_sprite(self):
        return person_frames("jesus", "down", 0, 2, None, ("grin",) if self.phase > 1 else ())

    def draw(self, surf, g):
        if not self.hidden:
            gl = light_glow(46, (255, 230, 150), 90)
            surf.blit(gl, (self.x - 46, self.y - 70), special_flags=pygame.BLEND_RGB_ADD)
        super().draw(surf, g)

    def check_phase(self, g):
        if self.phase == 1 and self.hp < self.max_hp * 0.55:
            self.phase = 2
            self.say("БУГАГАГАГАГАГА!!!", 2.5)
            g.sfx("angel")
            g.shake(6)
        elif self.phase == 2 and self.hp < self.max_hp * 0.2:
            self.phase = 3
            self.say("Я — ВЕЧЕН!!!", 2)
            g.sfx("roar")

    def idle_move(self, g, dt):
        tx = RCX + math.sin(self.t * 0.5) * 140
        ty = RY0 + 55 + math.sin(self.t * 0.9) * 20
        nx, ny = norm(tx - self.x, ty - self.y)
        self.walk(g, nx * self.speed, ny * self.speed, dt)

    def attacks(self, g):
        a = [self.a_crosses, self.a_rays, self.a_fish, self.a_angels, self.a_teleport]
        if self.phase >= 2:
            a += [self.a_laser_cross, self.a_rays]
        if self.phase >= 3:
            a += [self.a_rays, self.a_crosses]
        return a

    def a_crosses(self, g):
        for k in range(3 if self.phase == 1 else 4):
            self.ring(g, 10 + self.phase * 2, 85, off=k * 0.3, kind="cross", col=(255, 225, 120), r=6, spin=0.4 * (1 if k % 2 else -1))
            g.sfx("angel", 0.4)
            yield 0.65
        yield 0.3

    def a_rays(self, g):
        self.say(random.choice(["ЛУЧИ!", "Аллилуйя!", "Свет!"]), 1)
        for wv in range(2 if self.phase < 3 else 3):
            p = g.player
            xs = [p.x] + [random.uniform(RX0 + 10, RX1 - 10) for _ in range(2 + self.phase)]
            for x in xs:
                g.beams.append(Beam(x, RY0 - 10, math.pi / 2, 300, 16, 0.85, 0.35, 2, (255, 240, 170)))
            g.sfx("rays", 0.5)
            yield 1.2
        yield 0.2

    def a_fish(self, g):
        self.say("Хлеба и рыбы!", 1.2)
        for k in range(8):
            a = -math.pi / 2 + (k - 3.5) * 0.35
            vx, vy = from_ang(a, 120)
            g.eshot(self.x, self.y - 10, vx, vy, kind="fish", col=(160, 210, 255), r=5, homing=1.4, life=5)
            yield 0.08
        yield 1.0

    def a_angels(self, g):
        if sum(1 for e in g.room.enemies if not e.dead and not e.is_boss) >= 2:
            yield 0.1
            return
        self.say("Ангелы, ко мне!", 1.2)
        for k in (-1, 1):
            e = Enemy("angel", self.x + k * 50, self.y + 10, g)
            g.room.enemies.append(e)
        yield 1.0

    def a_teleport(self, g):
        g.sfx("teleport")
        self.hidden = True
        self.invuln = True
        yield 0.5
        p = g.player
        for _ in range(10):
            nx = random.uniform(RX0 + 40, RX1 - 40)
            ny = random.uniform(RY0 + 30, RY1 - 40)
            if dist(nx, ny, p.x, p.y) > 110:
                break
        self.x, self.y = nx, ny
        self.hidden = False
        self.invuln = False
        g.parts.burst(self.x, self.y - 20, 20, (255, 240, 180), 100, 0.6, 3)
        self.ring(g, 16, 100, kind="cross", col=(255, 225, 120), r=5)
        yield 0.6

    def a_laser_cross(self, g):
        self.move_mode = "to"
        self.tx, self.ty = RCX, RCY - 10
        yield 1.0
        self.move_mode = "still"
        self.say("КРЕСТ!!!", 1.5)
        rot = random.choice([-0.55, 0.55])
        for k in range(4):
            g.beams.append(Beam(self.x, self.y - 10, k * math.pi / 2 + 0.3, 520, 12, 1.0, 3.6, 2, (255, 230, 140), rot=rot, follow=None))
        yield 1.2
        for k in range(10):
            self.ring(g, 8, 90, off=k * 0.4, kind="blood", col=(255, 240, 190), r=4)
            yield 0.35
        yield 0.5


# ---------------------------------------------------------------- Костян
class BossKostya(Boss):
    def __init__(self, g, x, y):
        super().__init__(g, x, y, "КОСТЯН", 1, 12)
        self.invuln = True
        self.speed = 70
        self.fatigue = 0.0
        self.need = 62.0
        self.script_i = 0
        self.dodge_cd = 0.0
        self.bar_text = "устаёт..."
        self.max_hp = 1.0
        self.hp = 1.0
        self.done = False

    def body_sprite(self):
        fr = int(self.walk_anim) % 4
        ex = ("grin",) if self.fatigue < self.need * 0.5 else ()
        return person_frames("kostya", self.facing, fr, 2, None, ex)

    def update(self, g, dt):
        if not self.done:
            self.fatigue += dt
            self.hp = max(0.001, 1 - self.fatigue / self.need)
            if self.fatigue >= self.need and self.co is None:
                self.done = True
                g.clear_bullets()
                g.story.kostya_tired(self)
                return
            # уклонение
            self.dodge_cd -= dt
            if self.dodge_cd <= 0:
                for t in g.tears:
                    if not t.dead and dist(t.x, t.y, self.x, self.y) < self.r + 26:
                        nx, ny = norm(-t.vy, t.vx)
                        if random.random() < 0.5:
                            nx, ny = -nx, -ny
                        ox, oy = self.x, self.y
                        move_circle(self, nx * 34, ny * 34, g, True)
                        g.parts.burst(ox, oy - 20, 8, (90, 140, 220), 60, 0.3, 2)
                        g.floater(self.x, self.y - 46, "*уклон*", (150, 200, 255))
                        g.sfx("dodge", 0.4)
                        self.dodge_cd = 0.25
                        break
        if self.done:
            return
        super().update(g, dt)

    def on_invuln_hit(self, g, src):
        pass

    def pick_attack(self, g):
        seq = [self.a_pencils, self.a_blasters, self.a_balls, self.a_rain, self.a_dice_spiral, self.a_blaster_circle, self.a_pencils,
               self.a_blasters, self.a_rain, self.a_blaster_circle, self.a_dice_spiral, self.a_balls]
        f = seq[self.script_i % len(seq)]
        self.script_i += 1
        if self.fatigue >= self.need:
            return None
        return f(g)

    def idle_time(self):
        return 0.45

    def idle_move(self, g, dt):
        tx = RCX + math.sin(self.t * 0.6) * 60
        ty = RY0 + 50
        nx, ny = norm(tx - self.x, ty - self.y)
        if dist(self.x, self.y, tx, ty) > 4:
            self.walk(g, nx * 50, ny * 50, dt)

    def a_pencils(self, g):
        self.say(random.choice(["Карандаши!", "Удачи, ботик.", "хе."]), 1.2)
        for wv in range(4):
            gap = random.randint(1, ROWS - 3)
            from_left = wv % 2 == 0
            x = RX0 + 4 if from_left else RX1 - 4
            vx = 150 if from_left else -150
            for r in range(ROWS * 2):
                if gap * 2 <= r <= gap * 2 + 3:
                    continue
                y = RY0 + 8 + r * 16
                g.eshot(x, y, vx, 0, kind="pencil", col=(250, 200, 60), r=7, dmg=2, spectral=True, life=4)
            yield 0.95
        yield 0.3

    def a_blasters(self, g):
        for k in range(4):
            p = g.player
            side = random.choice(["l", "r", "t"])
            if side == "l":
                x, y = RX0 - 6, p.y + random.uniform(-10, 10)
            elif side == "r":
                x, y = RX1 + 6, p.y + random.uniform(-10, 10)
            else:
                x, y = p.x + random.uniform(-10, 10), RY0 - 6
            a = ang_to(x, y, p.x, p.y)
            g.beams.append(Beam(x, y, a, 700, 20, 0.7, 0.35, 2, (230, 240, 255)))
            g.effects.append(Blaster(x, y, a, 1.05))
            g.sfx("warn", 0.5)
            yield 0.45
        yield 0.7

    def a_balls(self, g):
        self.say("БЛЮ ЛОК!", 1.2)
        for k in range(5):
            p = g.player
            a = ang_to(self.x, self.y, p.x, p.y) + random.uniform(-0.5, 0.5)
            vx, vy = from_ang(a, 170)
            g.eshot(self.x, self.y, vx, vy, kind="blood", col=(250, 250, 250), r=6, dmg=2, bounce=4, life=6)
            yield 0.3
        yield 0.8

    def a_rain(self, g):
        for wv in range(5):
            gap = random.randint(0, COLS - 3)
            for c in range(COLS * 2):
                if gap * 2 <= c <= gap * 2 + 4:
                    continue
                x = RX0 + 8 + c * 16
                g.eshot(x, RY0 + 2, 0, 140, kind="pencil", col=(255, 120, 120), r=7, dmg=2, spectral=True, life=3)
            yield 0.8
        yield 0.4

    def a_dice_spiral(self, g):
        self.move_mode = "still"
        off = random.uniform(0, 6)
        for k in range(34):
            for arm in range(3):
                vx, vy = from_ang(off + k * 0.21 * (1 if self.script_i % 2 else -1) + arm * math.pi * 2 / 3, 120)
                g.eshot(self.x, self.y - 10, vx, vy, kind="dice", col=(250, 250, 250), r=5, dmg=2)
            yield 0.08
        yield 0.4

    def a_blaster_circle(self, g):
        self.say("Д20-бластеры.", 1.4)
        p = g.player
        n = 6
        off = random.uniform(0, 6)
        for k in range(n):
            a = off + k * math.pi * 2 / n
            x, y = p.x + math.cos(a) * 110, p.y + math.sin(a) * 110
            aa = ang_to(x, y, p.x, p.y)
            g.beams.append(Beam(x, y, aa, 260, 16, 0.9 + k * 0.18, 0.3, 2, (230, 240, 255)))
            g.effects.append(Blaster(x, y, aa, 1.2 + k * 0.18))
        g.sfx("warn")
        yield 2.4


class Blaster(Ent):
    def __init__(self, x, y, a, life):
        super().__init__(x, y)
        self.a = a
        self.life = life

    def update(self, g, dt):
        self.t += dt
        if self.t > self.life:
            self.dead = True

    def draw(self, surf, g):
        s = bullet_sprite("dice", (250, 250, 250), 8)
        s = pygame.transform.rotate(s, -math.degrees(self.a) + self.t * 200)
        surf.blit(s, (self.x - s.get_width() / 2, self.y - s.get_height() / 2))
        pygame.draw.circle(surf, (20, 20, 30), (int(self.x - 3), int(self.y - 2)), 2)
        pygame.draw.circle(surf, (20, 20, 30), (int(self.x + 3), int(self.y - 2)), 2)

    @property
    def sort_y(self):
        return 9998


class BossKostya2(Boss):
    def __init__(self, g, x, y):
        super().__init__(g, x, y, "КОСТЯН", 420, 12)
        self.speed = 60
        self.tusk = None

    def body_sprite(self):
        fr = int(self.walk_anim) % 4
        return person_frames("kostya", self.facing, fr, 2, None, ("angry",))

    def attacks(self, g):
        return [self.a_blasters, self.a_pencils, self.a_dice]

    def idle_time(self):
        return 1.1 if (self.tusk and not self.tusk.dead) else 0.6

    def a_blasters(self, g):
        for k in range(3):
            p = g.player
            x, y = random.choice([(RX0 - 6, p.y), (RX1 + 6, p.y), (p.x, RY0 - 6)])
            a = ang_to(x, y, p.x, p.y)
            g.beams.append(Beam(x, y, a, 700, 18, 0.75, 0.3, 2, (230, 240, 255)))
            g.effects.append(Blaster(x, y, a, 1.05))
            yield 0.5
        yield 0.5

    def a_pencils(self, g):
        gap = random.randint(1, ROWS - 3)
        from_left = random.random() < 0.5
        x = RX0 + 4 if from_left else RX1 - 4
        for r in range(ROWS * 2):
            if gap * 2 <= r <= gap * 2 + 3:
                continue
            g.eshot(x, RY0 + 8 + r * 16, 150 if from_left else -150, 0, kind="pencil", col=(250, 200, 60), r=7, dmg=2, spectral=True, life=4)
        yield 1.0

    def a_dice(self, g):
        for k in range(3):
            self.aimed(g, 3, 0.5, 150, kind="dice", col=(250, 250, 250), r=5, dmg=2)
            yield 0.35
        yield 0.4

    def die(self, g):
        if self.tusk and not self.tusk.dead and not self.tusk.defeated:
            self.hp = 1
            self.invuln = True
            self.say("Таск ещё жив!", 1.5)
            return
        super().die(g)


class BossTusk(Boss):
    def __init__(self, g, owner):
        super().__init__(g, owner.x, owner.y - 30, "ТАСК", 380, 12)
        self.owner = owner
        self.flying = True
        self.no_contact = True
        self.orb = 0.0

    def body_sprite(self):
        return cached(("tusk", int(self.anim) % 8), lambda: draw_tusk(2, int(self.anim) % 8))

    def idle_move(self, g, dt):
        self.orb += dt * 1.2
        o = self.owner
        tx, ty = o.x + math.cos(self.orb) * 60, o.y - 10 + math.sin(self.orb) * 40
        self.x += (tx - self.x) * min(1, dt * 3)
        self.y += (ty - self.y) * min(1, dt * 3)

    def attack_move(self, g, dt):
        self.idle_move(g, dt)

    def attacks(self, g):
        return [self.a_nails, self.a_holes, self.a_act4, self.a_nails]

    def a_nails(self, g):
        self.say("Ногтевые пули!", 1)
        for k in range(10):
            p = g.player
            a = ang_to(self.x, self.y, p.x, p.y) + random.uniform(-0.2, 0.2)
            vx, vy = from_ang(a, 200)
            g.eshot(self.x, self.y - 10, vx, vy, kind="nail", col=(255, 190, 230), r=5, dmg=2)
            yield 0.12
        yield 0.5

    def a_holes(self, g):
        self.say("Act 2!", 1)
        g.effects.append(SpinHole(g.player.x + 60, g.player.y))
        g.effects.append(SpinHole(g.player.x - 60, g.player.y))
        yield 2.0

    def a_act4(self, g):
        self.say("АКТ 4!!!", 1.5)
        off = random.uniform(0, 6)
        for k in range(30):
            for arm in range(4):
                vx, vy = from_ang(off + k * 0.18 + arm * math.pi / 2, 95)
                g.eshot(self.x, self.y - 10, vx, vy, kind="star", col=(255, 215, 90), r=5, dmg=2, spin=0.35)
            yield 0.09
        yield 0.6

    def die(self, g):
        if self.defeated:
            return
        self.defeated = True
        self.dead = True
        g.sfx("boss_die")
        g.parts.burst(self.x, self.y - 10, 40, (255, 200, 230), 160, 0.8, 3)
        self.owner.invuln = False
        self.owner.say("ТАСК!!! Т-ты... заплатишь!", 2)


class SpinHole(Ent):
    def __init__(self, x, y):
        super().__init__(clamp(x, RX0 + 20, RX1 - 20), clamp(y, RY0 + 20, RY1 - 20))
        self.r = 12
        self.life = 7.0

    def update(self, g, dt):
        self.t += dt
        self.life -= dt
        if self.life <= 0:
            self.dead = True
            return
        p = g.player
        nx, ny = norm(p.x - self.x, p.y - self.y)
        sp = 55 if self.t > 0.8 else 0
        self.x += nx * sp * dt
        self.y += ny * sp * dt
        if self.t > 0.8 and dist(self.x, self.y, p.x, p.y) < self.r + p.hr * 0.5:
            p.hurt(g, 2, self)

    def draw(self, surf, g):
        c = (255, 210, 90) if self.t > 0.8 else (255, 255, 255)
        for k in range(3):
            a = self.t * 6 + k * 2.1
            pygame.draw.arc(surf, c, (self.x - self.r, self.y - self.r * 0.6, self.r * 2, self.r * 1.2), a, a + 1.4, 2)
        pygame.draw.ellipse(surf, (40, 20, 30), (self.x - self.r * 0.6, self.y - self.r * 0.35, self.r * 1.2, self.r * 0.7))

    @property
    def sort_y(self):
        return -998

# ============================================================================
#                           NPC (разговорные)
# ============================================================================
class NPC(Ent):
    hittable = False

    def __init__(self, who, x, y, dlg, kind="person", tag=None):
        super().__init__(x, y)
        self.who = who
        self.dlg = dlg
        self.kind = kind
        self.r = 10
        self.tag = tag or who
        self.talked = 0
        self.hidden = False
        self.facing = "down"
        self.alpha = 255

    def update(self, g, dt):
        self.t += dt
        p = g.player
        if p and not self.hidden:
            d = dist(self.x, self.y, p.x, p.y)
            if d < self.r + p.r + 1:
                nx, ny = norm(p.x - self.x, p.y - self.y)
                p.x = self.x + nx * (self.r + p.r + 1)
                p.y = self.y + ny * (self.r + p.r + 1)

    def near(self, g):
        p = g.player
        return p and not self.hidden and self.dlg and dist(self.x, self.y, p.x, p.y) < self.r + p.r + 16

    def sprite(self):
        if self.kind == "cat":
            return cached(("npccat", int(self.t * 3) % 4), lambda: draw_cat(1, int(self.t * 3) % 4, False))
        if self.kind == "item":
            return item_icon(self.who)
        if self.kind == "lobster":
            return cached(("npclob",), lambda: pygame.transform.rotate(draw_lobster(2.0, 0, False), 180))
        return person_frames(self.who, self.facing, 0, 1 if self.kind != "big" else 2)

    def draw(self, surf, g):
        if self.hidden:
            return
        s = self.sprite()
        sh = shadow_surf(18, 6, 90)
        surf.blit(sh, (self.x - 9, self.y + 4))
        bob = 0
        if self.kind == "item":
            ps = pedestal_sprite()
            surf.blit(ps, (self.x - ps.get_width() / 2, self.y - 4))
            bob = math.sin(self.t * 3) * 2 + 16
        if self.who == "unknown":
            s = s.copy()
            s.set_alpha(150 + int(60 * math.sin(self.t * 3)))
        if self.who in ("jesus",):
            gl = light_glow(30, (255, 230, 150), 80)
            surf.blit(gl, (self.x - 30, self.y - 40), special_flags=pygame.BLEND_RGB_ADD)
        surf.blit(s, (self.x - s.get_width() / 2, self.y - s.get_height() + 9 - bob + math.sin(self.t * 2) * (1 if self.kind == "person" else 0)))
        if self.near(g):
            yy = self.y - s.get_height() - 4 - bob + math.sin(self.t * 6) * 2
            pygame.draw.polygon(surf, (255, 255, 255), [(self.x - 4, yy - 6), (self.x + 4, yy - 6), (self.x, yy)])
            pygame.draw.polygon(surf, (20, 20, 20), [(self.x - 4, yy - 6), (self.x + 4, yy - 6), (self.x, yy)], 1)


# ============================================================================
#                           КОМНАТЫ И ЭТАЖИ
# ============================================================================
class Door:
    def __init__(self, d, target, kind="normal"):
        self.d = d
        self.target = target
        self.kind = kind
        self.locked = False
        self.hidden = False
        self.sealed = False

    def center(self):
        if self.d == "up":
            return RCX, RY0 - 6
        if self.d == "down":
            return RCX, RY1 + 6
        if self.d == "left":
            return RX0 - 6, RCY
        return RX1 + 6, RCY


class Room:
    def __init__(self, gx, gy, kind="normal"):
        self.gx, self.gy = gx, gy
        self.kind = kind
        self.doors = {}
        self.grid = [[None] * ROWS for _ in range(COLS)]
        self.enemies = []
        self.pickups = []
        self.pedestals = []
        self.npcs = []
        self.misc = []
        self.spawn = []
        self.cleared = kind not in ("normal", "boss")
        self.visited = False
        self.seen = False
        self.bg = None
        self.dirty = True
        self.decals = []
        self.story = None
        self.boss_kind = None
        self.trapdoor = False
        self.biome = "apartment"
        self.seed = random.randint(0, 99999)
        self.icon = None
        self.locked_note = None
        self._solid_cache = None

    # ---- сетка препятствий
    def obstacle_at(self, c, r):
        if 0 <= c < COLS and 0 <= r < ROWS:
            o = self.grid[c][r]
            if o is not None and not o.dead:
                return o
        return None

    def obstacle_at_px(self, x, y):
        c, r = pos_tile(x, y)
        o = self.obstacle_at(c, r)
        if o is None:
            return None
        rx, ry, rw, rh = o.rect()
        if rx <= x <= rx + rw and ry <= y <= ry + rh:
            return o
        return None

    def solid_rects_near(self, x, y, r):
        out = []
        c0, r0 = pos_tile(x - r - 2, y - r - 2)
        c1, r1 = pos_tile(x + r + 2, y + r + 2)
        for c in range(max(0, c0), min(COLS, c1 + 1)):
            for rr in range(max(0, r0), min(ROWS, r1 + 1)):
                o = self.grid[c][rr]
                if o is not None and not o.dead and o.kind not in ("fire", "bfire"):
                    out.append(o.rect())
        for pd in self.pedestals:
            if pd.solid and abs(pd.x - x) < 30 and abs(pd.y - y) < 30:
                out.append((pd.x - 9, pd.y - 2, 18, 10))
        return out

    def walkable(self, c, r):
        o = self.obstacle_at(c, r)
        return o is None or o.kind in ("fire", "bfire")

    def all_obstacles(self):
        for c in range(COLS):
            for r in range(ROWS):
                o = self.grid[c][r]
                if o is not None and not o.dead:
                    yield o

    # ---- декали (кровь, обломки)
    def decal_splat(self, x, y, col, r):
        self.decals.append(("splat", x, y, col, r, random.randint(0, 999)))
        if len(self.decals) > 120:
            self.decals.pop(0)
        self.dirty = True

    def decal_rubble(self, x, y, kind):
        self.decals.append(("rubble", x, y, kind, 0, random.randint(0, 999)))
        self.dirty = True

    def decal_scorch(self, x, y, r):
        self.decals.append(("scorch", x, y, (0, 0, 0), r, random.randint(0, 999)))
        self.dirty = True

    def get_bg(self):
        if self.bg is None or self.dirty:
            if self.bg is None:
                self.base_bg = make_background(self.biome, self.seed % 7).copy()
                self._decorate(self.base_bg)
            bg = self.base_bg.copy()
            for d in self.decals:
                kind, x, y, col, r, seed = d
                rs = random.Random(seed)
                if kind == "splat":
                    s = pygame.Surface((40, 30), pygame.SRCALPHA)
                    for _ in range(6):
                        rr = rs.uniform(2, max(3, r * 0.7))
                        pygame.draw.circle(s, col_mul(col, 0.7) + (150,), (int(20 + rs.uniform(-r, r)), int(15 + rs.uniform(-r * 0.6, r * 0.6))), int(rr))
                    bg.blit(s, (x - 20, y - 15))
                elif kind == "rubble":
                    for _ in range(5):
                        c = (110, 70, 40) if col in ("poop", "gpoop") else (90, 90, 90) if col not in ("fire", "bfire") else (40, 40, 40)
                        pygame.draw.circle(bg, c, (int(x + rs.uniform(-10, 10)), int(y + rs.uniform(-8, 8))), rs.randint(1, 3))
                elif kind == "scorch":
                    s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                    pygame.draw.circle(s, (0, 0, 0, 90), (r, r), r)
                    pygame.draw.circle(s, (0, 0, 0, 70), (r, r), int(r * 0.6))
                    bg.blit(s, (x - r, y - r))
            self.bg = bg
            self.dirty = False
        return self.bg

    def _decorate(self, bg):
        rs = random.Random(self.seed)
        b = self.biome
        n = rs.randint(2, 6)
        for _ in range(n):
            x = rs.uniform(RX0 + 10, RX1 - 10)
            y = rs.uniform(RY0 + 10, RY1 - 10)
            if b in ("apartment", "home", "dark"):
                if rs.random() < 0.3:
                    w, h = rs.randint(50, 90), rs.randint(30, 50)
                    c = rs.choice([(140, 40, 50), (60, 80, 140), (150, 120, 60)])
                    if b == "dark":
                        c = col_mul(c, 0.5)
                    rug = pygame.Rect(0, 0, w, h)
                    rug.center = (int(x), int(y))
                    pygame.draw.rect(bg, col_mul(c, 0.7), rug.inflate(4, 4), border_radius=4)
                    pygame.draw.rect(bg, c, rug, border_radius=4)
                    pygame.draw.rect(bg, col_mul(c, 1.3), rug.inflate(-8, -8), 1, border_radius=3)
                else:
                    pygame.draw.circle(bg, col_mul(BIOMES[b]["fc"], 0.8), (int(x), int(y)), rs.randint(3, 8))
            elif b == "school":
                if rs.random() < 0.5:
                    s = pygame.Surface((20, 14), pygame.SRCALPHA)
                    pygame.draw.rect(s, (245, 245, 240), (0, 0, 14, 10))
                    pygame.draw.line(s, (120, 140, 200), (2, 3), (12, 3))
                    pygame.draw.line(s, (120, 140, 200), (2, 6), (10, 6))
                    bg.blit(pygame.transform.rotate(s, rs.uniform(0, 360)), (x, y))
            elif b == "lungs":
                pygame.draw.circle(bg, (90, 30, 40), (int(x), int(y)), rs.randint(4, 10))
                pygame.draw.circle(bg, (60, 50, 50), (int(x + 2), int(y + 1)), rs.randint(2, 5))
            elif b in ("heaven",):
                pygame.draw.circle(bg, (255, 255, 255), (int(x), int(y)), rs.randint(6, 14))
        # украшения на стенах
        wc = BIOMES[b]["wc"]
        for k in range(rs.randint(1, 3)):
            x = rs.choice([rs.uniform(RX0 + 20, RCX - 40), rs.uniform(RCX + 40, RX1 - 40)])
            if b in ("apartment", "home", "dark"):
                if rs.random() < 0.5:
                    fr = pygame.Rect(int(x), 8, 26, 20)
                    pygame.draw.rect(bg, (90, 60, 30), fr)
                    pygame.draw.rect(bg, col_mul((120, 160, 210) if b != "dark" else (40, 40, 70), 1.0), fr.inflate(-6, -6))
                    pygame.draw.line(bg, (90, 60, 30), (fr.centerx, fr.y + 3), (fr.centerx, fr.bottom - 3), 2)
                else:
                    fr = pygame.Rect(int(x), 10, 18, 16)
                    pygame.draw.rect(bg, (60, 40, 25), fr)
                    pygame.draw.rect(bg, rs.choice([(200, 80, 60), (80, 160, 90), (220, 200, 90)]), fr.inflate(-4, -4))
            elif b == "school":
                if k == 0:
                    fr = pygame.Rect(int(RCX + 30), 6, 70, 26)
                    pygame.draw.rect(bg, (90, 60, 40), fr)
                    pygame.draw.rect(bg, (40, 70, 50), fr.inflate(-4, -4))
                    for j in range(3):
                        pygame.draw.line(bg, (220, 220, 210), (fr.x + 8, fr.y + 8 + j * 5), (fr.x + 8 + rs.randint(20, 50), fr.y + 8 + j * 5), 1)
                else:
                    fr = pygame.Rect(int(x), 6, 14, 28)
                    pygame.draw.rect(bg, (70, 90, 130), fr)
                    pygame.draw.line(bg, (40, 50, 80), (fr.x + 2, fr.y + 6), (fr.right - 3, fr.y + 6), 1)
            elif b == "lungs":
                pygame.draw.line(bg, col_mul(wc, 0.6), (x, 0), (x + rs.uniform(-20, 20), RY0), 2)
            elif b in ("heaven", "throne", "hall"):
                fr = pygame.Rect(int(x), 4, 12, 34)
                pygame.draw.rect(bg, col_mul(wc, 1.15), fr)
                pygame.draw.rect(bg, col_mul(wc, 0.8), fr, 1)
            elif b == "prison":
                for j in range(5):
                    pygame.draw.line(bg, (50, 50, 56), (x + j * 6, 6), (x + j * 6, 34), 2)
        # трещина-подсказка для секретной комнаты
        for d, door in self.doors.items():
            if door.hidden:
                cx, cy = door.center()
                for k in range(6):
                    a = rs.uniform(0, math.pi * 2)
                    l = rs.uniform(4, 10)
                    pygame.draw.line(bg, (20, 14, 14), (cx, cy), (cx + math.cos(a) * l, cy + math.sin(a) * l * 0.6), 1)
        if self.kind == "boss" and b in ("apartment", "dark", "school", "lungs"):
            pygame.draw.circle(bg, col_mul(BIOMES[b]["fc"], 0.75), (int(RCX), int(RCY)), 46, 2)


ROOM_ICONS = {"boss": "skull", "treasure": "crown", "shop": "dollar", "secret": "q", "dymok": "cat", "food": "food",
              "rak": "rak", "story": "excl"}


class Floor:
    GW, GH = 9, 8

    def __init__(self, fid, rng):
        self.fid = fid
        self.cfg = FLOORS[fid]
        self.rooms = {}
        self.rng = rng
        self.start = None
        self.biome = self.cfg["biome"]
        if self.cfg.get("single"):
            self._make_single()
        else:
            self._generate()

    # -------------------------------------------- одиночные арены
    def _make_single(self):
        cfg = self.cfg
        r = Room(4, 4, "arena")
        r.biome = cfg["biome"]
        r.cleared = True
        self.rooms[(4, 4)] = r
        self.start = r
        extra = cfg.get("extra_room")
        if extra:
            r2 = Room(4, 3, "arena")
            r2.biome = cfg["biome"]
            r2.cleared = True
            self.rooms[(4, 3)] = r2
            d1 = Door("up", r2, "story")
            d1.locked = False
            d1.sealed = True
            r.doors["up"] = d1
            r2.doors["down"] = Door("down", r, "normal")
            self.extra = r2

    # -------------------------------------------- генерация (алгоритм как в Айзеке)
    def _generate(self):
        cfg = self.cfg
        specials = list(cfg.get("specials", []))
        need_dead = sum(1 for s in specials if not s.startswith("secret")) + 1
        target = cfg["rooms"]
        for attempt in range(400):
            cells = {(4, 4)}
            q = deque([(4, 4)])
            while q and len(cells) < target:
                cx, cy = q.popleft()
                dirs = list(DIRS.values())
                self.rng.shuffle(dirs)
                for dx, dy in dirs:
                    nx, ny = cx + dx, cy + dy
                    if not (0 <= nx < self.GW and 0 <= ny < self.GH) or (nx, ny) in cells:
                        continue
                    if len(cells) >= target:
                        break
                    if self.rng.random() < 0.5:
                        continue
                    nb = sum(1 for ddx, ddy in DIRS.values() if (nx + ddx, ny + ddy) in cells)
                    if nb > 1:
                        continue
                    cells.add((nx, ny))
                    q.append((nx, ny))
                if not q and len(cells) < target:
                    q.append(self.rng.choice(sorted(cells)))
            if len(cells) < target:
                continue
            dead = [c for c in cells if c != (4, 4) and sum(1 for dx, dy in DIRS.values() if (c[0] + dx, c[1] + dy) in cells) == 1]
            if len(dead) >= need_dead:
                break
        self.cells = cells
        # расстояния
        distm = {(4, 4): 0}
        q = deque([(4, 4)])
        while q:
            c = q.popleft()
            for dx, dy in DIRS.values():
                n = (c[0] + dx, c[1] + dy)
                if n in cells and n not in distm:
                    distm[n] = distm[c] + 1
                    q.append(n)
        dead.sort(key=lambda c: -distm.get(c, 0))
        for c in cells:
            self.rooms[c] = Room(c[0], c[1], "normal")
            self.rooms[c].biome = self.biome
        self.start = self.rooms[(4, 4)]
        self.start.kind = "start"
        self.start.cleared = True
        boss_cell = dead[0] if dead else max(cells, key=lambda c: distm.get(c, 0))
        self.rooms[boss_cell].kind = "boss"
        self.rooms[boss_cell].cleared = False
        self.boss_room = self.rooms[boss_cell]
        rest = dead[1:]
        self.rng.shuffle(rest)
        secret_specs = []
        for sp in specials:
            if sp.startswith("secret"):
                secret_specs.append(sp)
                continue
            if not rest:
                # нет тупиков - берём любую обычную
                cand = [c for c in cells if self.rooms[c].kind == "normal"]
                if not cand:
                    break
                cell = self.rng.choice(cand)
            else:
                cell = rest.pop()
            room = self.rooms[cell]
            if ":" in sp:
                room.kind = "story"
                room.story = sp.split(":", 1)[1]
                room.cleared = room.story != "rak"
                if room.story == "rak":
                    room.kind = "story"
            else:
                room.kind = sp
                room.cleared = True
        # двери
        for c, room in self.rooms.items():
            for d, (dx, dy) in DIRS.items():
                n = (c[0] + dx, c[1] + dy)
                if n in self.rooms:
                    other = self.rooms[n]
                    kind = "normal"
                    for rr in (room, other):
                        if rr.kind in ("boss", "treasure", "shop"):
                            kind = rr.kind
                        elif rr.kind == "story":
                            kind = "story"
                    door = Door(d, other, kind)
                    if other.kind in ("treasure", "shop") and cfg.get("locked_specials") and room.kind not in ("treasure", "shop"):
                        door.locked = True
                    if room.kind in ("treasure", "shop") and cfg.get("locked_specials") and other.kind not in ("treasure", "shop"):
                        door.locked = True
                    room.doors[d] = door
        # секретная
        for sp in secret_specs:
            best = None
            best_n = 0
            for x in range(self.GW):
                for y in range(self.GH):
                    if (x, y) in self.rooms:
                        continue
                    nbs = [(x + dx, y + dy) for dx, dy in DIRS.values() if (x + dx, y + dy) in self.rooms]
                    nbs = [n for n in nbs if self.rooms[n].kind not in ("boss", "secret")]
                    if len(nbs) > best_n or (len(nbs) == best_n and best_n > 0 and self.rng.random() < 0.3):
                        best, best_n = (x, y), len(nbs)
            if best is None:
                continue
            room = Room(best[0], best[1], "secret")
            room.biome = self.biome
            room.cleared = True
            if ":" in sp:
                room.story = sp.split(":", 1)[1]
            self.rooms[best] = room
            for d, (dx, dy) in DIRS.items():
                n = (best[0] + dx, best[1] + dy)
                if n in self.rooms and self.rooms[n].kind not in ("boss",) and self.rooms[n] is not room:
                    other = self.rooms[n]
                    dd = Door(d, other, "secret")
                    room.doors[d] = dd
                    od = Door(OPP[d], room, "secret")
                    od.hidden = True
                    other.doors[OPP[d]] = od
        # наполнение
        for c, room in self.rooms.items():
            populate_room(room, self, self.rng)

    def all_rooms(self):
        return self.rooms.values()


# ---------------------------------------------------------------- наполнение комнат
def gen_layout(room, rng, biome):
    style = BIOMES[biome]["rock"]
    grid = [[None] * ROWS for _ in range(COLS)]
    pat = rng.choice(["empty", "pillars", "center", "scatter", "rows", "corners", "poops", "cross", "scatter", "pillars", "ring"])

    def put(c, r, kind="rock"):
        for (cc, rr) in ((c, r), (COLS - 1 - c, r), (c, ROWS - 1 - r), (COLS - 1 - c, ROWS - 1 - r)):
            if 0 <= cc < COLS and 0 <= rr < ROWS:
                grid[cc][rr] = kind
    if pat == "pillars":
        for (c, r) in ((2, 1), (4, 2)):
            put(c, r, "rock")
    elif pat == "center":
        for c in range(5, 8):
            put(c, 3, "rock")
        put(6, 2, "rock")
    elif pat == "scatter":
        for _ in range(rng.randint(2, 4)):
            put(rng.randint(1, 5), rng.randint(0, 2), rng.choice(["rock", "rock", "poop"]))
    elif pat == "rows":
        for c in range(2, 5):
            put(c, 1, "rock")
    elif pat == "corners":
        for (c, r) in ((0, 0), (1, 0), (0, 1)):
            put(c, r, "rock")
    elif pat == "poops":
        for _ in range(rng.randint(2, 4)):
            put(rng.randint(1, 5), rng.randint(0, 2), "poop")
    elif pat == "cross":
        put(3, 3, "rock")
        put(6, 1, "rock")
    elif pat == "ring":
        for (c, r) in ((4, 1), (5, 1), (4, 2)):
            put(c, r, "rock")
    # особые
    if rng.random() < 0.12:
        put(rng.randint(1, 4), rng.randint(0, 2), "fire")
    if rng.random() < 0.08:
        c, r = rng.randint(1, 5), rng.randint(0, 2)
        grid[c][r] = "tinted"
    if rng.random() < 0.05:
        put(rng.randint(1, 4), rng.randint(0, 2), "block")
    if rng.random() < 0.03:
        grid[rng.randint(1, 11)][rng.randint(1, 5)] = "gpoop"
    # проходы к дверям
    for (c, r) in ((6, 0), (6, 1), (0, 3), (1, 3), (12, 3), (11, 3), (6, 6), (6, 5), (6, 3)):
        grid[c][r] = None
    # проверка связности
    def ok():
        start = (6, 3)
        seen = {start}
        q = deque([start])
        while q:
            c, r = q.popleft()
            for dx, dy in DIRS.values():
                n = (c + dx, r + dy)
                if 0 <= n[0] < COLS and 0 <= n[1] < ROWS and n not in seen and grid[n[0]][n[1]] in (None, "fire"):
                    seen.add(n)
                    q.append(n)
        for t in ((6, 0), (0, 3), (12, 3), (6, 6)):
            if t not in seen:
                return False
        free = sum(1 for c in range(COLS) for r in range(ROWS) if grid[c][r] in (None, "fire"))
        return len(seen) >= free * 0.9
    if not ok():
        grid = [[None] * ROWS for _ in range(COLS)]
    for c in range(COLS):
        for r in range(ROWS):
            k = grid[c][r]
            if k:
                room.grid[c][r] = Obstacle(k, c, r, style, rng.randint(0, 3))


def populate_room(room, floor, rng):
    cfg = floor.cfg
    biome = floor.biome
    depth = cfg.get("depth", 0)
    if room.kind == "normal":
        gen_layout(room, rng, biome)
        n = rng.randint(2, 4) + min(3, depth)
        table = FLOOR_ENEMIES.get(biome, ["fly"])
        groupk = rng.choice(table)
        for i in range(n):
            k = groupk if rng.random() < 0.5 else rng.choice(table)
            if k in ("fly", "afly", "nicotine") and rng.random() < 0.6:
                room.spawn.append(k)
            room.spawn.append(k)
        if rng.random() < 0.15:
            room.pickups.append(Pickup(rng.choice(["coin", "coin", "bomb", "key", "heart"]), RCX + rng.uniform(-60, 60), RCY + rng.uniform(-30, 30)))
    elif room.kind == "treasure":
        it = pick_item(rng, "treasure")
        room.pedestals.append(Pedestal(it, RCX, RCY))
        if rng.random() < 0.4:
            for (c, r) in ((4, 2), (8, 2), (4, 4), (8, 4)):
                room.grid[c][r] = Obstacle("rock", c, r, BIOMES[biome]["rock"], rng.randint(0, 3))
    elif room.kind == "shop":
        its = [pick_item(rng, "shop"), pick_item(rng, "shop")]
        room.pedestals.append(Pedestal(its[0], RCX - 50, RCY - 10, price=15))
        room.pedestals.append(Pedestal(its[1], RCX + 50, RCY - 10, price=15))
        goods = rng.sample(["heart", "bomb", "key", "soul", "heart", "bomb"], 3)
        prices = {"heart": 3, "bomb": 5, "key": 5, "soul": 5}
        for i, gk in enumerate(goods):
            room.pickups.append(Pickup(gk, RCX - 60 + i * 60, RCY + 50, price=prices[gk]))
        room.npcs.append(NPC("botik", RCX, RY0 + 22, None, tag="shopkeeper"))
    elif room.kind == "secret":
        if room.story == "unknown":
            room.npcs.append(NPC("unknown", RCX, RCY - 20, "unknown"))
        else:
            if rng.random() < 0.5:
                room.pedestals.append(Pedestal(pick_item(rng, "treasure"), RCX, RCY))
            else:
                for k in range(rng.randint(3, 5)):
                    room.pickups.append(Pickup(rng.choice(["coin", "coin", "nickel", "bomb", "key", "soul"]), RCX + rng.uniform(-50, 50), RCY + rng.uniform(-30, 30)))
    elif room.kind == "story":
        st = room.story
        if st == "dymok":
            room.npcs.append(NPC("dymok", RCX, RCY - 20, "sukuna", kind="cat"))
            for (c, r) in ((2, 1), (10, 1), (2, 5), (10, 5)):
                room.grid[c][r] = Obstacle("poop", c, r)
        elif st == "food":
            room.npcs.append(NPC("food", RCX, RCY, "food", kind="item"))
        elif st == "rak":
            room.boss_kind = "rak"
            room.cleared = False
    elif room.kind == "boss":
        room.boss_kind = cfg.get("boss")
    elif room.kind == "start":
        pass


def pick_item(rng, pool, exclude=()):
    taken = GAME_TAKEN
    cands = [k for k, v in ITEMS.items() if pool in v["pools"] and k not in taken and k not in exclude]
    if not cands:
        cands = [k for k, v in ITEMS.items() if "treasure" in v["pools"]]
    it = rng.choice(cands)
    taken.add(it)
    return it


GAME_TAKEN = set()

FLOORS = {
    "f1": dict(title="КВАРТИРА", sub="Этаж 1", biome="apartment", music="floor1", rooms=10, depth=0,
               specials=["treasure", "shop", "story:dymok", "story:food", "secret:unknown"], boss="npc_valerii", soap=True),
    "f2": dict(title="ШКОЛА №52", sub="Этаж 2", biome="school", music="school", rooms=12, depth=1,
               specials=["treasure", "shop", "secret"], boss="smoke", locked_specials=True),
    "f3": dict(title="ЛЁГКИЕ СЕРЁГИ", sub="Этаж 3", biome="lungs", music="lungs", rooms=12, depth=2,
               specials=["treasure", "shop", "secret", "story:rak", "story:rak", "story:rak"], boss="bigrak", locked_specials=True),
    "f4": dict(title="ТЁМНАЯ КВАРТИРА", sub="Этаж 4", biome="dark", music="dark", rooms=12, depth=3,
               specials=["treasure", "shop", "secret"], boss="val2", locked_specials=True),
    "heaven": dict(title="РАЙ", sub="", biome="heaven", music="heaven", single=True),
    "heaven2": dict(title="РАЙ", sub="", biome="heaven", music="heaven", single=True),
    "prison": dict(title="НЕБЕСНАЯ ТЮРЬМА", sub="", biome="prison", music="prison", single=True),
    "throne": dict(title="НЕБЕСНЫЙ ПРЕСТОЛ", sub="", biome="throne", music="jesus", single=True),
    "home": dict(title="ДОМ", sub="", biome="home", music="musicbox", single=True, extra_room=True),
    "hall": dict(title="ДОМЕЙН КОСТЯНА", sub="", biome="hall", music="kostya", single=True),
    "void": dict(title="???", sub="", biome="void", music="gaster", single=True),
    "catdomain": dict(title="ГРОБНИЦА ЦАРАПАНИЙ", sub="", biome="catdomain", music="domain", single=True),
}

# ============================================================================
#                              ДИАЛОГОВОЕ ОКНО
# ============================================================================
def speaker_portrait(key):
    if key == "dymok":
        return cached(("portrait", "dymok"), lambda: outline(draw_cat(3, 0, False).subsurface((0, 0, 92, 70)).copy(), th=2))
    if key == "rak":
        return cached(("portrait", "rak"), lambda: draw_lobster(2.6, 0, True))
    if key in ("narr", "item", None):
        return None
    if key == "artem_dark":
        return portrait("artem_dark")
    if key in PERSONS:
        return portrait(key)
    return None


class DialogBox:
    CPS = 48.0

    def __init__(self, scene, dlg, start=1, npc=None, on_end=None):
        self.g = scene
        self.dlg = dlg
        self.layer_id = start
        self.npc = npc
        self.on_end = on_end
        self.line_i = 0
        self.reveal = 0.0
        self.choosing = False
        self.sel = 0
        self.done = False
        self.blip_acc = 0
        self.t = 0.0
        self.pending = None
        self._prep()

    def layer(self):
        return self.dlg["layers"][self.layer_id]

    def _prep(self):
        self.reveal = 0.0
        self.choosing = False
        self.sel = 0
        self.blip_acc = 0

    def cur(self):
        lay = self.layer()
        txt = lay["t"][self.line_i]
        who = lay.get("who", self.dlg.get("who", "narr"))
        for pref, key in LINE_PREFIX.items():
            if txt.startswith(pref + ": "):
                return key, txt[len(pref) + 2:], pref
        if who == "artem" and self.g.player.evil >= 2:
            who = "artem_dark"
        name = SPEAKERS.get(who if who != "artem_dark" else "artem", ("", who))[0]
        if who == "valerii" and self.dlg.get("papa"):
            name = "Папа"
        return who, txt, name

    def answers(self):
        out = []
        for a in self.layer()["a"]:
            c = a.get("cond")
            if c and not self.g.story.cond(c):
                continue
            out.append(a)
        return out

    def full(self):
        _, txt, _ = self.cur()
        return self.reveal >= len(txt) + 1

    def update(self, dt):
        self.t += dt
        if self.choosing:
            return
        who, txt, _ = self.cur()
        before = int(self.reveal)
        sp = self.CPS * (3.0 if pygame.key.get_pressed()[pygame.K_x] else 1.0)
        self.reveal = min(len(txt) + 1, self.reveal + dt * sp)
        after = int(self.reveal)
        if after > before and after <= len(txt):
            ch = txt[after - 1:after]
            if ch.strip() and after % 2 == 0:
                AUDIO.voice({"artem_dark": "artem"}.get(who, who) if who in VOICES or who == "artem_dark" else "narr")
        if self.full() and self.line_i == len(self.layer()["t"]) - 1:
            if self.answers():
                self.choosing = True

    def key(self, ev):
        k = ev.key
        if self.choosing:
            ans = self.answers()
            if k in (pygame.K_UP, pygame.K_w):
                self.sel = (self.sel - 1) % len(ans)
                AUDIO.play("menu")
            elif k in (pygame.K_DOWN, pygame.K_s):
                self.sel = (self.sel + 1) % len(ans)
                AUDIO.play("menu")
            elif k in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_e):
                AUDIO.play("select")
                self.choose(ans[self.sel])
            return
        if k in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE, pygame.K_KP_ENTER, pygame.K_e, pygame.K_x):
            if not self.full():
                self.reveal = 9999
                return
            if self.line_i < len(self.layer()["t"]) - 1:
                self.line_i += 1
                self._prep()
            else:
                if not self.answers():
                    self.close()

    def choose(self, a):
        acts = a.get("do")
        if acts is None:
            acts = []
        elif isinstance(acts, str):
            acts = [acts]
        go = a.get("go")
        if go is not None:
            self.layer_id = go
            self.line_i = 0
            self._prep()
            for act in acts:
                self.g.story.do(act, self)
        else:
            self.close()
            for act in acts:
                self.g.story.do(act, self)

    def close(self):
        if self.done:
            return
        self.done = True
        if self.on_end:
            self.on_end()

    def draw(self, scr):
        who, txt, name = self.cur()
        box = pygame.Rect(30, SH - 196, SW - 60, 180)
        s = pygame.Surface(box.size, pygame.SRCALPHA)
        s.fill((14, 10, 16, 236))
        scr.blit(s, box.topleft)
        pygame.draw.rect(scr, (240, 236, 226), box, 3, border_radius=6)
        pygame.draw.rect(scr, (90, 80, 70), box.inflate(-8, -8), 1, border_radius=4)
        tx = box.x + 22
        por = speaker_portrait(who)
        if por is not None:
            pr = pygame.Rect(box.x + 14, box.y + 16, 120, 120)
            pygame.draw.rect(scr, (36, 28, 34), pr, border_radius=6)
            pygame.draw.rect(scr, (200, 190, 170), pr, 2, border_radius=6)
            ps = por
            if ps.get_width() > 116 or ps.get_height() > 116:
                k = min(116 / ps.get_width(), 116 / ps.get_height())
                ps = pygame.transform.scale(ps, (int(ps.get_width() * k), int(ps.get_height() * k)))
            bob = math.sin(self.t * 8) * 1.5 if not self.full() else 0
            scr.blit(ps, (pr.centerx - ps.get_width() // 2, pr.bottom - ps.get_height() - 2 + bob))
            tx = pr.right + 18
        if name:
            nt = text(name, 30, (255, 230, 140), (0, 0, 0), 2)
            scr.blit(nt, (tx, box.y + 10))
        width = box.right - tx - 24
        sz = 30 if len(txt) < 260 else 26
        if len(txt) > 420:
            sz = 21
        caps = sum(1 for c in txt if c.isupper()) > len(txt) * 0.6 and len(txt) > 8
        draw_rich(scr, txt, sz, tx, box.y + 44, width, (255, 255, 255), reveal=int(self.reveal), shake=1.2 if caps else 0.0)
        if self.full() and not self.choosing:
            if int(self.t * 3) % 2 == 0:
                pygame.draw.polygon(scr, (255, 255, 255), [(box.right - 30, box.bottom - 24), (box.right - 18, box.bottom - 24), (box.right - 24, box.bottom - 16)])
        if self.choosing:
            ans = self.answers()
            lines = []
            total_h = 0
            ow = 560
            for a in ans:
                lay = layout_text(a["t"], 27, ow - 50)
                h = len(lay[0]) * lay[1] + 8
                lines.append((a, h))
                total_h += h
            ob = pygame.Rect(SW - ow - 40, box.y - total_h - 26, ow, total_h + 18)
            s2 = pygame.Surface(ob.size, pygame.SRCALPHA)
            s2.fill((10, 8, 12, 240))
            scr.blit(s2, ob.topleft)
            pygame.draw.rect(scr, (240, 236, 226), ob, 3, border_radius=6)
            y = ob.y + 10
            for i, (a, h) in enumerate(lines):
                col = (255, 240, 120) if i == self.sel else (220, 220, 220)
                if i == self.sel:
                    ts = tear_sprite((120, 170, 255), 6)
                    scr.blit(pygame.transform.scale(ts, (18, 18)), (ob.x + 12, y + 4 + math.sin(self.t * 8) * 2))
                draw_rich(scr, a["t"], 27, ob.x + 38, y, ow - 50, col)
                y += h


# ============================================================================
#                              ИГРОВАЯ СЦЕНА
# ============================================================================
class GameScene:
    def __init__(self, app, char_id="artem", start="prologue", ckpt=None):
        self.app = app
        self.char_id = char_id
        self.seed = random.randint(0, 10 ** 9)
        self.rng = random.Random(self.seed)
        GAME_TAKEN.clear()
        self.player = Player(char_id)
        self.flags = dict(shard=False, card=False, food=False, soap=False, dymok=None, sergei=None, dad=None, jesus=None,
                          raki=0, kills=0, ellen=None, kostya=None, kostya_phase=1)
        self.floor = None
        self.room = None
        self.saved_floor = None
        self.world = pygame.Surface((WW, WH))
        self.tears, self.eshots, self.beams, self.creep = [], [], [], []
        self.effects, self.markers, self.familiars, self.bluecats, self.bombs = [], [], [], [], []
        self.floaters = []
        self.parts = Particles()
        self.shake_amt = 0.0
        self.hurt_flash = 0.0
        self.white = 0.0
        self.fade = 0.0
        self.fade_to = 0.0
        self.fade_speed = 2.0
        self.dialog = None
        self.dialog_queue = []
        self.banner = None
        self.item_banner = None
        self.vs = None
        self.paused = False
        self.pause_sel = 0
        self.transition = None
        self.scripts = []
        self.time = 0.0
        self.god = False
        self.last_arrow = None
        self.hp_scale = 1.0
        self.contact_dmg = 1
        self.domain_vis = 0.0
        self.domain_blades = 0.0
        self.flow = {}
        self.flow_tile = None
        self.dead_screen = None
        self.ending = None
        self.show_map = False
        self.pending_drop = None
        self.boss_ref = []
        self.killer = None
        self.sky_dark = 0.0
        self.overlay_text = None
        self.big_text = None
        self.cinematic = 0.0
        self.story = Story(self)
        SAVE["runs"] = SAVE["runs"] + 1
        SAVE.save()
        if ckpt:
            self.story.load_ckpt(ckpt)
        else:
            self.story.start(start)

    # ------------------------------------------------ утилиты для сущностей
    def sfx(self, name, vol=1.0, cool=0.03):
        AUDIO.play(name, vol, cool)

    def audio_splash(self):
        AUDIO.play("splash", 0.35, 0.05)

    def shake(self, a):
        self.shake_amt = max(self.shake_amt, a)

    def floater(self, x, y, txt, col=(255, 255, 255)):
        self.floaters.append([x, y, txt, col, 1.0])

    def eshot(self, x, y, vx, vy, **kw):
        kw.setdefault("dmg", self.contact_dmg)
        self.eshots.append(EShot(x, y, vx, vy, **kw))

    def clear_bullets(self):
        for e in self.eshots:
            if not e.friendly:
                self.parts.burst(e.x, e.y, 2, e.col, 30, 0.3, 2)
        self.eshots = [e for e in self.eshots if e.friendly]
        self.beams = [b for b in self.beams if b.friendly]
        self.markers = []

    def nearest_enemy(self, x, y, maxd=9999):
        best, bd = None, maxd * maxd
        for e in self.room.enemies:
            if e.dead or not e.hittable or getattr(e, "invuln", False) or getattr(e, "hidden", False):
                continue
            d = (e.x - x) ** 2 + (e.y - y) ** 2
            if d < bd:
                best, bd = e, d
        return best

    def spawn_bluecat(self, x, y):
        if len(self.bluecats) < 6:
            self.bluecats.append(BlueCat(x, y))

    def bullet_time_scale(self):
        return 0.6 if self.player.domain_t > 0 else 1.0

    def enemy_time_scale(self):
        return 0.55 if self.player.domain_t > 0 else 1.0

    def drop(self, kind, x, y):
        a = random.uniform(0, math.pi * 2)
        self.room.pickups.append(Pickup(kind, x, y, math.cos(a) * 80, math.sin(a) * 80))

    def random_pickup(self):
        p = self.player
        r = random.random() - p.stats.luck * 0.02
        if r < 0.38:
            return "coin"
        if r < 0.55:
            return "heart" if random.random() < 0.6 else "half"
        if r < 0.7:
            return "bomb"
        if r < 0.84:
            return "key"
        if r < 0.92:
            return "soul"
        if r < 0.96:
            return "nickel"
        return "battery"

    def explode(self, x, y, radius, dmg, friendly=True, small=False, hurt_player=True):
        self.sfx("explode", 0.7 if small else 1.0)
        self.shake(3 if small else 7)
        self.parts.burst(x, y, 10 if small else 26, (255, 200, 80), 140, 0.4, 4, kind="circ")
        self.parts.burst(x, y, 8 if small else 18, (80, 80, 80), 90, 0.9, 4, grav=-30, kind="circ")
        self.parts.add(x, y, 0, 0, 0.3, (255, 240, 200), radius, kind="ring")
        self.effects.append(Flash(x, y, radius))
        for e in self.room.enemies:
            if not e.dead and e.hittable and dist(e.x, e.y, x, y) < radius + e.r:
                nx, ny = norm(e.x - x, e.y - y)
                e.hurt(self, dmg, nx * 120, ny * 120, None)
        p = self.player
        if hurt_player and not small and dist(p.x, p.y, x, y) < radius + p.r:
            p.hurt(self, 2, "bomb")
        if not small:
            for o in list(self.room.all_obstacles()):
                ox, oy = tile_center(o.c, o.r)
                if dist(ox, oy, x, y) < radius + 14:
                    o.destroy(self)
            for d, door in self.room.doors.items():
                cx, cy = door.center()
                if door.hidden and dist(cx, cy, x, y) < radius + 18:
                    door.hidden = False
                    other = door.target
                    od = other.doors.get(OPP[d])
                    if od:
                        od.hidden = False
                    self.room.dirty = True
                    self.room.bg = None
                    self.sfx("secret")
            for pk in self.room.pickups:
                if dist(pk.x, pk.y, x, y) < radius + 10 and not pk.price:
                    nx, ny = norm(pk.x - x, pk.y - y)
                    pk.vx += nx * 200
                    pk.vy += ny * 200
            self.room.decal_scorch(x, y, int(radius * 0.6))
        self.flow_tile = None

    # ------------------------------------------------ подбор
    def try_collect(self, pk):
        p = self.player
        if pk.price:
            if p.coins < pk.price:
                return False
        k = pk.kind
        ok = True
        if k in ("coin", "nickel"):
            p.coins = min(99, p.coins + PICKUP_INFO[k])
            self.sfx("coin")
        elif k == "key":
            p.keys = min(99, p.keys + 1)
            self.sfx("key")
        elif k == "bomb":
            p.bombs = min(99, p.bombs + 1)
            self.sfx("bombpick")
        elif k == "heart":
            ok = p.heal(2)
            if ok:
                self.sfx("heart")
        elif k == "half":
            ok = p.heal(1)
            if ok:
                self.sfx("heart")
        elif k == "soul":
            if p.red_max + p.soul >= 24:
                ok = False
            else:
                p.soul += 2
                self.sfx("heart")
        elif k == "battery":
            if p.active:
                p.charge = ITEMS[p.active]["charges"]
                self.sfx("charge")
            else:
                ok = False
        if ok and pk.price:
            p.coins -= pk.price
            self.sfx("coin")
        if ok:
            self.parts.burst(pk.x, pk.y, 6, (255, 255, 200), 50, 0.3, 2)
        return ok

    def take_pedestal(self, ped):
        p = self.player
        if ped.price:
            if p.coins < ped.price:
                return
            p.coins -= ped.price
            ped.price = 0
        iid = ped.item
        it = ITEMS[iid]
        new_forms = []
        if it["kind"] == "active":
            old = p.add_item(iid)
            ped.item = old
            ped.cool = 1.2
        else:
            new_forms = p.add_item(iid) or []
            ped.item = None
        self.on_item_gained(iid, new_forms)
        if ped.on_take:
            ped.on_take()

    def give_item(self, iid, banner=True):
        p = self.player
        if p.has(iid):
            return
        it = ITEMS[iid]
        new_forms = []
        if it["kind"] == "active":
            old = p.add_item(iid)
            if old and old != iid:
                self.pending_drop = old
        else:
            new_forms = p.add_item(iid) or []
        self.on_item_gained(iid, new_forms, banner)

    def on_item_gained(self, iid, new_forms=(), banner=True):
        p = self.player
        it = ITEMS[iid]
        if banner:
            p.hold_t = 1.0
            p.hold_item = iid
            self.sfx("item")
            self.item_banner = [it["name"], it["desc"], 3.0]
        seen = SAVE["items_seen"]
        if iid not in seen:
            seen.append(iid)
        fam = it.get("familiar")
        if fam:
            self.familiars.append(Familiar(fam, len(self.familiars)))
        if iid in ("food", "soap", "card", "shard"):
            self.flags[iid] = True
        for f in new_forms:
            nm, ds = TRANSFORMS[f]
            self.big_text = [nm + "!", ds, 3.0]
            self.sfx("fanfare")

    def on_enemy_killed(self, e):
        self.flags["kills"] += 1

    # ------------------------------------------------ двери и движение
    def door_open(self, door):
        if door.hidden or door.locked or door.sealed:
            return False
        return self.room.cleared and not self.room_has_enemies()

    def room_has_enemies(self):
        return any(not e.dead for e in self.room.enemies)

    def move_player(self, p, dx, dy):
        move_circle(p, dx, dy, self, p.flight, use_walls=False)
        r = p.r
        doors = self.room.doors
        gap = 13

        def handle(d, cond_out, clamp_fn, go_fn):
            door = doors.get(d)
            if door is None:
                clamp_fn()
                return
            if door.locked and self.room.cleared and not self.room_has_enemies():
                if p.keys > 0:
                    p.keys -= 1
                    door.locked = False
                    od = door.target.doors.get(OPP[d])
                    if od:
                        od.locked = False
                    self.sfx("unlock")
                clamp_fn()
                return
            if self.door_open(door):
                go_fn()
            else:
                clamp_fn()

        if p.y < RY0 + r:
            if abs(p.x - RCX) < gap:
                def c1():
                    p.y = RY0 + r

                def g1():
                    p.x = clamp(p.x, RCX - gap + 3, RCX + gap - 3)
                    if p.y < RY0 - 3:
                        self.go_door("up")
                handle("up", None, c1, g1)
            else:
                p.y = RY0 + r
        if p.y > RY1 - r:
            if abs(p.x - RCX) < gap:
                def c2():
                    p.y = RY1 - r

                def g2():
                    p.x = clamp(p.x, RCX - gap + 3, RCX + gap - 3)
                    if p.y > RY1 + 3:
                        self.go_door("down")
                handle("down", None, c2, g2)
            else:
                p.y = RY1 - r
        if p.x < RX0 + r:
            if abs(p.y - RCY) < gap:
                def c3():
                    p.x = RX0 + r

                def g3():
                    p.y = clamp(p.y, RCY - gap + 3, RCY + gap - 3)
                    if p.x < RX0 - 3:
                        self.go_door("left")
                handle("left", None, c3, g3)
            else:
                p.x = RX0 + r
        if p.x > RX1 - r:
            if abs(p.y - RCY) < gap:
                def c4():
                    p.x = RX1 - r

                def g4():
                    p.y = clamp(p.y, RCY - gap + 3, RCY + gap - 3)
                    if p.x > RX1 + 3:
                        self.go_door("right")
                handle("right", None, c4, g4)
            else:
                p.x = RX1 - r

    def go_door(self, d):
        if self.transition:
            return
        door = self.room.doors[d]
        old_img = self.render_room(hud=False)
        self.enter_room(door.target, d)
        new_img = self.render_room(hud=False)
        self.transition = [d, 0.0, old_img, new_img]

    # ------------------------------------------------ поток для ходоков
    def flow_dir(self, x, y):
        p = self.player
        pt = pos_tile(p.x, p.y)
        if pt != self.flow_tile:
            self.flow_tile = pt
            self.flow = {}
            if 0 <= pt[0] < COLS and 0 <= pt[1] < ROWS:
                self.flow[pt] = 0
                q = deque([pt])
                while q:
                    c = q.popleft()
                    for dx, dy in DIRS.values():
                        n = (c[0] + dx, c[1] + dy)
                        if 0 <= n[0] < COLS and 0 <= n[1] < ROWS and n not in self.flow and self.room.walkable(*n):
                            self.flow[n] = self.flow[c] + 1
                            q.append(n)
        t = pos_tile(x, y)
        if t not in self.flow:
            return 0, 0
        best = None
        bd = self.flow[t]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not dx and not dy:
                    continue
                n = (t[0] + dx, t[1] + dy)
                if n in self.flow and self.flow[n] < bd:
                    if dx and dy and ((t[0] + dx, t[1]) not in self.flow or (t[0], t[1] + dy) not in self.flow):
                        continue
                    bd = self.flow[n]
                    best = n
        if best is None:
            return 0, 0
        cx, cy = tile_center(*best)
        return norm(cx - x, cy - y)

    # ------------------------------------------------ этажи и комнаты
    def load_floor(self, fid, banner=True):
        self.floor = Floor(fid, self.rng)
        cfg = self.floor.cfg
        depth = cfg.get("depth", 0)
        self.hp_scale = 1.0 + depth * 0.28
        self.contact_dmg = 1 if depth < 2 else 2
        if fid in ("throne", "hall"):
            self.contact_dmg = 2
        if cfg.get("soap") and not self.flags["soap"]:
            cand = [r for r in self.floor.all_rooms() if r.kind == "normal"]
            if cand:
                rm = self.rng.choice(cand)
                ped = Pedestal("soap", RCX, RCY)
                ped.on_take = lambda: self.queue_dialog("milo")
                rm.pedestals.append(ped)
                for c in range(5, 8):
                    for rr in range(2, 5):
                        rm.grid[c][rr] = None
        self.enter_room(self.floor.start, None)
        if self.pending_drop:
            self.room.pedestals.append(Pedestal(self.pending_drop, RCX + 60, RCY))
            self.pending_drop = None
        if cfg.get("music"):
            AUDIO.music(cfg["music"])
        if banner and cfg.get("title"):
            self.banner = [cfg.get("sub", ""), cfg["title"], 3.0]

    def enter_room(self, room, from_dir):
        self.room = room
        room.visited = True
        room.seen = True
        if self.floor and not self.floor.cfg.get("single"):
            for d, door in room.doors.items():
                if not door.hidden:
                    door.target.seen = True
        self.tears, self.eshots, self.beams, self.creep = [], [], [], []
        self.effects, self.markers, self.bluecats = [], [], []
        self.parts.p = []
        self.flow_tile = None
        p = self.player
        if from_dir == "up":
            p.x, p.y = RCX, RY1 - 14
        elif from_dir == "down":
            p.x, p.y = RCX, RY0 + 14
        elif from_dir == "left":
            p.x, p.y = RX1 - 14, RCY
        elif from_dir == "right":
            p.x, p.y = RX0 + 14, RCY
        else:
            p.x, p.y = RCX, RCY + 50
        p.vx = p.vy = 0
        p.trail.clear()
        for f in self.familiars:
            f.x, f.y = p.x, p.y
        p.dmg_taken_room = False
        if not room.cleared and room.spawn and not room.enemies:
            for k in room.spawn:
                for _ in range(30):
                    c, r = self.rng.randint(0, COLS - 1), self.rng.randint(0, ROWS - 1)
                    x, y = tile_center(c, r)
                    if room.walkable(c, r) and dist(x, y, p.x, p.y) > 90:
                        break
                room.enemies.append(Enemy(k, x + self.rng.uniform(-6, 6), y + self.rng.uniform(-6, 6), self))
            room.spawn = []
            self.sfx("door", 0.5)
        self.story.on_enter_room(room)

    def room_cleared(self):
        room = self.room
        room.cleared = True
        self.sfx("door")
        p = self.player
        if p.active and not ITEMS[p.active].get("timed"):
            mx = ITEMS[p.active]["charges"]
            if p.charge < mx:
                p.charge += 1
                if p.charge == mx:
                    self.sfx("charge")
        elif p.active:
            p.charge = ITEMS[p.active]["charges"]
        if room.kind == "normal" and random.random() < 0.55 + p.stats.luck * 0.03:
            for _ in range(10):
                c, r = self.rng.randint(4, 8), self.rng.randint(2, 4)
                if room.walkable(c, r):
                    break
            x, y = tile_center(c, r)
            k = self.random_pickup()
            room.pickups.append(Pickup(k, x, y, 0, 0))

    # ------------------------------------------------ активки и бомбы
    def use_active(self):
        p = self.player
        if not p.active or self.dialog or self.script_blocking():
            return
        it = ITEMS[p.active]
        if p.charge < it["charges"]:
            self.sfx("bad", 0.4)
            return
        u = it["use"]
        if u == "reroll":
            if not self.room.pedestals:
                self.sfx("bad", 0.4)
                return
            for ped in self.room.pedestals:
                if ped.item and ITEMS[ped.item]["pools"] != ("story",):
                    ped.item = pick_item(self.rng, "treasure")
                    self.parts.burst(ped.x, ped.y - 16, 12, (255, 255, 255), 80, 0.4, 2)
            self.sfx("card")
        elif u == "shrink":
            p.shrink_t = 7.0
            self.sfx("shrink")
            self.floater(p.x, p.y - 20, "*уменьшился*", (180, 180, 255))
        elif u == "domain":
            p.domain_t = 9.0
            self.domain_vis = 9.0
            self.sfx("domain")
            self.white = 0.7
            self.shake(8)
            self.big_text = ["РАСШИРЕНИЕ ТЕРРИТОРИИ", "Мечи и кресты!", 2.2]
        elif u == "lightning":
            self.white = 0.6
            self.sfx("explode")
            for e in self.room.enemies:
                if not e.dead and e.hittable:
                    e.hurt(self, 40, 0, 0, None)
                    self.parts.burst(e.x, e.y - 10, 10, (255, 255, 160), 120, 0.4, 2, kind="spark")
        elif u == "bombs":
            for k in range(3):
                a = k * math.pi * 2 / 3
                b = Bomb(p.x + math.cos(a) * 30, p.y + math.sin(a) * 30, fuse=0.9)
                b.hurt_player = False
                self.bombs.append(b)
        elif u == "call":
            r = random.random()
            if r < 0.45:
                p.heal(2) or setattr(p, "soul", p.soul + 1)
                self.floater(p.x, p.y - 24, "Костян: держи шаурму!", (150, 200, 255))
                self.sfx("heart")
            elif r < 0.75:
                for _ in range(3):
                    self.drop("coin", p.x, p.y)
                self.floater(p.x, p.y - 24, "Костян: скинул на карту", (150, 200, 255))
            else:
                self.white = 0.5
                for e in self.room.enemies:
                    if not e.dead and e.hittable:
                        e.hurt(self, 30, 0, 0, None)
                self.floater(p.x, p.y - 24, "Костян расширил территорию!", (150, 200, 255))
                self.sfx("domain", 0.6)
        elif u == "heal":
            if not p.heal(2):
                p.soul = min(24, p.soul + 1)
            self.sfx("heart")
        p.charge = 0
        p.timed_charge = 0
        p.recalc()

    def place_bomb(self):
        p = self.player
        if p.bombs <= 0 or self.dialog or self.script_blocking() or p.lock_input:
            return
        p.bombs -= 1
        self.bombs.append(Bomb(p.x, p.y + 2))
        self.sfx("fuse", 0.5)

    # ------------------------------------------------ диалоги и скрипты
    def start_dialog(self, dlg, npc=None, start=1, on_end=None):
        if isinstance(dlg, str):
            d = DLG[dlg]
        else:
            d = dlg
        self.dialog = DialogBox(self, d, start, npc, on_end)

    def queue_dialog(self, dlg, start=1):
        self.dialog_queue.append((dlg, start))

    def run_script(self, gen, bg=False):
        self.scripts.append({"gen": gen, "wait": 0.0, "cond": None, "bg": bg})

    def script_blocking(self):
        return any(not s["bg"] for s in self.scripts)

    def _step_scripts(self, dt):
        snap = list(self.scripts)
        alive = []
        for s in snap:
            if s["wait"] > 0:
                s["wait"] -= dt
                alive.append(s)
                continue
            if s["cond"] is not None:
                if not s["cond"]():
                    alive.append(s)
                    continue
                s["cond"] = None
            try:
                y = next(s["gen"])
            except StopIteration:
                continue
            if isinstance(y, (int, float)):
                s["wait"] = float(y)
            elif y == "dialog":
                s["cond"] = (lambda: self.dialog is None and not self.dialog_queue)
            elif isinstance(y, tuple) and y[0] == "until":
                s["cond"] = y[1]
            alive.append(s)
        added = [s for s in self.scripts if not any(s is o for o in snap)]
        self.scripts = alive + added

    def say_dialog(self, dlg, start=1):
        """для использования в скриптах: yield from g.say_dialog(...)"""
        self.start_dialog(dlg, start=start)
        yield "dialog"

    def fade_out(self, speed=2.0):
        self.fade_to = 1.0
        self.fade_speed = speed
        yield ("until", lambda: self.fade >= 0.99)

    def fade_in(self, speed=2.0):
        self.fade_to = 0.0
        self.fade_speed = speed
        yield ("until", lambda: self.fade <= 0.01)

    # ------------------------------------------------ смерть
    def player_died(self, src):
        p = self.player
        if p.dead:
            return
        if self.story.on_player_death(src):
            return
        p.dead = True
        self.killer = src
        SAVE["deaths"] = SAVE["deaths"] + 1
        SAVE.save()
        AUDIO.stop_music(300)
        self.sfx("gameover")
        self.dead_screen = 0.0

    def killer_name(self):
        s = self.killer
        if s is None:
            return "???"
        if s == "bomb":
            return "своя бомба"
        if isinstance(s, Enemy):
            return s.name
        if isinstance(s, (EShot, Beam, Creep)):
            bs = [b for b in self.room.enemies if b.is_boss]
            if bs:
                return bs[0].name.capitalize() if bs[0].name.isupper() else bs[0].name
            es = [e for e in self.room.enemies if not e.dead]
            return es[0].name if es else "снаряд"
        return "???"

    def boss_defeated(self, b):
        self.sfx("boss_die")
        self.shake(10)
        self.white = 0.5
        self.parts.burst(b.x, b.y - 10, 40, (220, 30, 40), 180, 0.9, 3, grav=200)
        self.clear_bullets()
        self.story.on_boss_defeated(b)

    def finish(self, eid):
        self.ending = eid

    # ------------------------------------------------ события ввода
    def handle(self, ev):
        if self.dead_screen is not None:
            if ev.type == pygame.KEYDOWN and self.dead_screen > 1.5 and ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_z):
                self.app.to_title()
            return
        if ev.type == pygame.KEYDOWN:
            if ev.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                self.last_arrow = {pygame.K_LEFT: "left", pygame.K_RIGHT: "right", pygame.K_UP: "up", pygame.K_DOWN: "down"}[ev.key]
            if self.paused:
                self.pause_key(ev)
                return
            if self.dialog:
                self.dialog.key(ev)
                return
            if ev.key == pygame.K_ESCAPE:
                self.paused = True
                self.pause_sel = 0
                AUDIO.play("menu")
                return
            if self.vs or self.transition:
                return
            if ev.key == pygame.K_SPACE:
                self.use_active()
            elif ev.key in (pygame.K_e, pygame.K_LSHIFT, pygame.K_RSHIFT):
                self.place_bomb()
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_f):
                if not self.script_blocking():
                    for n in self.room.npcs:
                        if n.near(self):
                            self.story.talk(n)
                            break
            elif ev.key == pygame.K_F8 and pygame.key.get_mods() & pygame.KMOD_CTRL:
                self.god = not self.god
                self.floater(self.player.x, self.player.y - 30, "GOD " + ("ON" if self.god else "OFF"))
        elif ev.type == pygame.KEYUP:
            if ev.key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                ks = pygame.key.get_pressed()
                self.last_arrow = None
                for k, d in ((pygame.K_LEFT, "left"), (pygame.K_RIGHT, "right"), (pygame.K_UP, "up"), (pygame.K_DOWN, "down")):
                    if ks[k]:
                        self.last_arrow = d

    PAUSE_ITEMS = ["Продолжить", "Музыка: ", "Громкость звуков", "Выйти в меню"]

    def pause_key(self, ev):
        if ev.key in (pygame.K_UP, pygame.K_w):
            self.pause_sel = (self.pause_sel - 1) % 4
            AUDIO.play("menu")
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.pause_sel = (self.pause_sel + 1) % 4
            AUDIO.play("menu")
        elif ev.key == pygame.K_ESCAPE:
            self.paused = False
        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d):
            AUDIO.play("select")
            if self.pause_sel == 0:
                self.paused = False
            elif self.pause_sel == 1:
                AUDIO.toggle_music()
            elif self.pause_sel == 2:
                v = SAVE["sfx"]
                v = 0.0 if v >= 1.0 else round(v + 0.2, 1)
                SAVE["sfx"] = v
                SAVE.save()
            elif self.pause_sel == 3:
                self.app.to_title()

    # ------------------------------------------------ обновление
    def update(self, dt):
        self.time += dt
        if self.ending:
            self.app.show_ending(self.ending, self)
            return
        self.fade = approach(self.fade, self.fade_to, dt * self.fade_speed)
        if self.dead_screen is not None:
            self.dead_screen += dt
            self.parts.update(dt)
            return
        if self.paused:
            return
        if self.banner:
            self.banner[2] -= dt
            if self.banner[2] <= 0:
                self.banner = None
        if self.item_banner:
            self.item_banner[2] -= dt
            if self.item_banner[2] <= 0:
                self.item_banner = None
        if self.big_text:
            self.big_text[2] -= dt
            if self.big_text[2] <= 0:
                self.big_text = None
        self.shake_amt = max(0.0, self.shake_amt - dt * 20)
        self.hurt_flash = max(0.0, self.hurt_flash - dt)
        self.white = max(0.0, self.white - dt * 1.5)
        for f in self.floaters:
            f[1] -= 20 * dt
            f[4] -= dt
        self.floaters = [f for f in self.floaters if f[4] > 0]
        self._step_scripts(dt)
        if self.dialog:
            self.dialog.update(dt)
            if self.dialog.done:
                self.dialog = None
        if self.dialog is None and self.dialog_queue:
            d, st = self.dialog_queue.pop(0)
            self.start_dialog(d, start=st)
        if self.transition:
            self.transition[1] += dt / 0.25
            if self.transition[1] >= 1:
                self.transition = None
            return
        if self.vs:
            self.vs[1] += dt
            if self.vs[1] > 2.4:
                self.vs = None
            return
        if self.dialog:
            self.parts.update(dt)
            return
        self.step_world(dt)

    def step_world(self, dt):
        p = self.player
        keys = pygame.key.get_pressed()
        blocking = self.script_blocking()
        if blocking or p.lock_input:
            p.lock_input = True
            keys = _NoKeys()
        if not p.dead:
            p.update(self, dt, keys)
        if not blocking:
            p.lock_input = False
        room = self.room
        for f in self.familiars:
            f.update(self, dt)
        for lst in (self.tears, self.eshots, self.beams, self.creep, self.effects, self.markers, self.bluecats, self.bombs):
            for e in lst:
                if not e.dead:
                    e.update(self, dt)
        for lst in (room.enemies, room.pickups, room.pedestals, room.npcs, room.misc):
            for e in list(lst):
                if not e.dead:
                    e.update(self, dt)
        self.tears = [t for t in self.tears if not t.dead]
        self.eshots = [t for t in self.eshots if not t.dead]
        self.beams = [t for t in self.beams if not t.dead]
        self.creep = [t for t in self.creep if not t.dead]
        self.effects = [t for t in self.effects if not t.dead]
        self.markers = [t for t in self.markers if not t.dead]
        self.bluecats = [t for t in self.bluecats if not t.dead]
        self.bombs = [t for t in self.bombs if not t.dead]
        room.enemies = [e for e in room.enemies if not e.dead]
        room.pickups = [e for e in room.pickups if not e.dead]
        self.parts.update(dt)
        # огонь
        for o in room.all_obstacles():
            if o.kind in ("fire", "bfire"):
                x, y = tile_center(o.c, o.r)
                if dist(p.x, p.y, x, y + 4) < 11 + p.hr and not p.flight:
                    p.hurt(self, 1, "fire")
                for e in room.enemies:
                    pass
        # домейн игрока
        if p.domain_t > 0:
            self.domain_blades -= dt
            if self.domain_blades <= 0:
                self.domain_blades = 0.22
                tgts = [e for e in room.enemies if not e.dead and e.hittable]
                if tgts:
                    e = random.choice(tgts)
                    self.effects.append(DomainBlade(e.x + random.uniform(-6, 6), e.y + random.uniform(-4, 4), p.stats.damage * 1.2 + 4))
                else:
                    self.effects.append(DomainBlade(random.uniform(RX0, RX1), random.uniform(RY0, RY1), 0))
        self.domain_vis = max(0.0, self.domain_vis - dt)
        # зачистка
        if not room.cleared and not self.room_has_enemies() and room.kind in ("normal",) and not room.boss_kind:
            self.room_cleared()
        self.story.update(dt)

    # ------------------------------------------------ отрисовка
    def render_room(self, hud=True):
        w = self.world
        room = self.room
        w.blit(room.get_bg(), (0, 0))
        biome = room.biome
        if self.domain_vis > 0:
            k = min(1.0, self.domain_vis / 1.0) * 0.6
            ov = cached(("domov",), lambda: _domain_overlay())
            ov.set_alpha(int(255 * k))
            w.blit(ov, (0, 0))
        # двери
        for d, door in room.doors.items():
            st = "hidden" if door.hidden else ("locked" if door.locked else ("closed" if not self.door_open(door) else "open"))
            if door.sealed:
                st = "closed"
            spr = door_sprite(door.kind, d, st, biome)
            if d == "up":
                w.blit(spr, (RCX - spr.get_width() / 2, RY0 - 33))
            elif d == "down":
                s2 = pygame.transform.rotate(spr, 180)
                w.blit(s2, (RCX - s2.get_width() / 2, RY1 - 2))
            elif d == "left":
                s2 = pygame.transform.rotate(spr, 90)
                w.blit(s2, (RX0 - 33, RCY - s2.get_height() / 2))
            else:
                s2 = pygame.transform.rotate(spr, -90)
                w.blit(s2, (RX1 - 2, RCY - s2.get_height() / 2))
        for c in self.creep:
            c.draw(w, self)
        for m in self.markers:
            m.draw(w, self)
        # препятствия
        rstyle = BIOMES[biome]["rock"]
        draw_list = []
        for o in room.all_obstacles():
            x, y = RX0 + o.c * TILE, RY0 + o.r * TILE
            if o.kind == "rock":
                s = rock_sprite(rstyle, o.variant)
            elif o.kind == "tinted":
                s = rock_sprite(rstyle, o.variant, True)
            elif o.kind in ("poop", "gpoop"):
                s = poop_sprite(min(3, 4 - o.hp), o.kind == "gpoop")
            elif o.kind == "block":
                s = block_sprite()
            elif o.kind in ("fire", "bfire"):
                o.anim += 0.15
                s = fire_sprite(int(o.anim), o.kind == "bfire", max(0.4, o.hp / 4))
                gl = light_glow(24, (255, 160, 60), 50)
                w.blit(gl, (x - 8, y - 12), special_flags=pygame.BLEND_RGB_ADD)
            else:
                continue
            draw_list.append((y + 16, 0, lambda s=s, x=x, y=y: w.blit(s, (x - 1, y - 1))))
        if room.trapdoor:
            ts = trapdoor_sprite()
            w.blit(ts, (RCX - 18, RCY - 15))
        ents = []
        for lst in (room.pickups, room.pedestals, room.npcs, room.enemies, room.misc, self.bombs, self.familiars, self.bluecats, self.effects, self.tears, self.eshots):
            for e in lst:
                ents.append(e)
        if not self.player.dead or self.dead_screen is None:
            ents.append(self.player)
        for e in ents:
            draw_list.append((e.sort_y, 1, e))
        draw_list.sort(key=lambda t: (t[0], t[1]))
        for (_, kind, e) in draw_list:
            if kind == 0:
                e()
            else:
                e.draw(w, self)
        for b in self.beams:
            b.draw(w, self)
        self.parts.draw(w)
        vg = make_vignette(BIOMES[biome]["vign"])
        w.blit(vg, (0, 0))
        if self.sky_dark > 0:
            ov = cached(("skyov",), lambda: _solid((40, 0, 10), 255))
            ov.set_alpha(int(170 * self.sky_dark))
            w.blit(ov, (0, 0))
        if hud:
            self.draw_hud(w)
        return w.copy() if not hud else w

    def draw_hud(self, w):
        p = self.player
        # активка
        x0 = 6
        if p.active:
            box = pygame.Rect(4, 4, 26, 26)
            pygame.draw.rect(w, (20, 16, 20), box, border_radius=3)
            pygame.draw.rect(w, (200, 190, 170), box, 1, border_radius=3)
            ic = item_icon(p.active)
            w.blit(ic, (box.centerx - ic.get_width() / 2, box.centery - ic.get_height() / 2))
            mx = ITEMS[p.active]["charges"]
            bar = pygame.Rect(31, 4, 5, 26)
            pygame.draw.rect(w, (20, 16, 20), bar)
            fh = int(24 * p.charge / mx)
            col = (90, 230, 110) if p.charge >= mx else (220, 200, 60)
            if p.charge >= mx and int(self.time * 4) % 2:
                col = (200, 255, 200)
            pygame.draw.rect(w, col, (bar.x + 1, bar.bottom - 1 - fh, 3, fh))
            for k in range(1, mx):
                yy = bar.bottom - 1 - int(24 * k / mx)
                pygame.draw.line(w, (20, 16, 20), (bar.x, yy), (bar.right - 1, yy))
            pygame.draw.rect(w, (200, 190, 170), bar, 1)
            x0 = 42
        # сердца
        hx, hy = x0, 5
        slots = []
        for i in range(0, p.red_max, 2):
            v = p.red - i
            slots.append("full" if v >= 2 else "half" if v == 1 else "empty")
        for i in range(0, p.soul, 2):
            v = p.soul - i
            slots.append("soul" if v >= 2 else "soulhalf")
        for i, k in enumerate(slots):
            xx = hx + (i % 6) * 12
            yy = hy + (i // 6) * 11
            sp = hud_heart(k)
            if k in ("full", "half") and p.red <= 2 and int(self.time * 5) % 2 == 0:
                yy -= 1
            w.blit(sp, (xx, yy))
        # счётчики
        y = 32
        for kind, val in (("coin", p.coins), ("bomb", p.bombs), ("key", p.keys)):
            ic = pickup_sprite(kind, 0)
            ic = pygame.transform.scale(ic, (12, 12))
            w.blit(ic, (4, y))
            draw_digits(w, "%02d" % val, 17, y + 3)
            y += 13
        # статы
        if self.show_map or pygame.key.get_pressed()[pygame.K_TAB]:
            st = p.stats
            vals = [("СК", st.speed), ("СЛ", st.tears), ("УР", st.damage), ("ДЛ", st.range / 40), ("ПЛ", st.sspeed), ("УД", st.luck)]
            yy = 76
            for nm, v in vals:
                t = text(nm, 14, (220, 220, 220), (0, 0, 0), 1)
                w.blit(t, (4, yy))
                w.blit(text("%.2f" % v, 14, (255, 255, 255), (0, 0, 0), 1), (22, yy))
                yy += 11
        self.draw_minimap(w)

    def draw_minimap(self, w):
        fl = self.floor
        if fl is None or fl.cfg.get("single"):
            return
        big = pygame.key.get_pressed()[pygame.K_TAB]
        cw, ch = (8, 6) if not big else (16, 12)
        gx0 = WW - fl.GW * (cw + 1) - 6 if not big else WW // 2 - fl.GW * (cw + 1) // 2
        gy0 = 4 if not big else WH // 2 - fl.GH * (ch + 1) // 2
        bgr = pygame.Rect(gx0 - 3, gy0 - 3, fl.GW * (cw + 1) + 5, fl.GH * (ch + 1) + 5)
        s = pygame.Surface(bgr.size, pygame.SRCALPHA)
        s.fill((0, 0, 0, 110 if not big else 190))
        w.blit(s, bgr.topleft)
        has_map = "map" in self.player.stats.flags
        has_comp = "compass" in self.player.stats.flags
        for (x, y), r in fl.rooms.items():
            vis = r.visited or r.seen or (has_map and r.kind != "secret")
            icon_only = has_comp and r.kind in ("boss", "treasure", "shop", "story")
            if not vis and not icon_only:
                continue
            rx = gx0 + x * (cw + 1)
            ry = gy0 + y * (ch + 1)
            if r is self.room:
                col = (255, 255, 255)
            elif r.visited:
                col = (150, 150, 160)
            else:
                col = (70, 70, 80)
            pygame.draw.rect(w, col, (rx, ry, cw, ch))
            icon = None
            if r.kind in ("boss", "treasure", "shop", "secret"):
                icon = r.kind
            elif r.kind == "story":
                icon = r.story
            if icon and (r.visited or r.seen or has_comp):
                _mini_icon(w, icon, rx + cw // 2, ry + ch // 2, big)

    def draw_world_to(self, scr):
        if self.transition:
            d, t, old, new = self.transition
            k = ease_in_out(t)
            dx, dy = DIRS[d]
            ox, oy = -dx * WW * k, -dy * WH * k
            tmp = self.world
            tmp.fill((0, 0, 0))
            tmp.blit(old, (ox, oy))
            tmp.blit(new, (ox + dx * WW, oy + dy * WH))
            self.draw_hud(tmp)
        else:
            self.render_room(hud=True)
        sx = sy = 0
        if self.shake_amt > 0:
            sx = random.uniform(-self.shake_amt, self.shake_amt)
            sy = random.uniform(-self.shake_amt, self.shake_amt)
        big = pygame.transform.scale(self.world, (SW, SH))
        scr.fill((0, 0, 0))
        scr.blit(big, (int(sx * 2), int(sy * 2)))

    def draw(self, scr):
        self.draw_world_to(scr)
        p = self.player
        # пузыри боссов
        for e in self.room.enemies:
            if e.is_boss:
                e.draw_bubble(scr, self)
        # подсказка
        for n in self.room.npcs:
            if n.near(self) and not self.dialog and not self.script_blocking():
                t = text("ENTER — говорить", 22, (255, 255, 255), (0, 0, 0), 2)
                scr.blit(t, (n.x * 2 - t.get_width() / 2, (n.y + 14) * 2))
                break
        # плавающий текст
        for (x, y, txt, col, life) in self.floaters:
            t = text(txt, 24, col, (0, 0, 0), 2)
            t.set_alpha(int(255 * min(1, life * 2)))
            scr.blit(t, (x * 2 - t.get_width() / 2, y * 2))
        # полоска босса
        bosses = [e for e in self.room.enemies if e.is_boss and e.show_bar and not e.defeated]
        if bosses:
            for i, b in enumerate(bosses[:2]):
                bw = 460
                bx = SW / 2 - bw / 2
                by = SH - 44 - i * 40
                if self.dialog:
                    break
                pygame.draw.rect(scr, (10, 6, 8), (bx - 4, by - 4, bw + 8, 22), border_radius=4)
                k = clamp(b.hp / max(1e-6, b.max_hp), 0, 1)
                col = b.bar_color if not b.bar_text else (230, 200, 80)
                pygame.draw.rect(scr, col_mul(col, 0.4), (bx, by, bw, 14), border_radius=3)
                pygame.draw.rect(scr, col, (bx, by, int(bw * k), 14), border_radius=3)
                pygame.draw.rect(scr, (240, 230, 220), (bx - 4, by - 4, bw + 8, 22), 2, border_radius=4)
                nm = b.name + ("  —  " + b.bar_text if b.bar_text else "")
                t = text(nm, 22, (255, 255, 255), (0, 0, 0), 2)
                scr.blit(t, (SW / 2 - t.get_width() / 2, by - 24))
        # раки
        if self.floor and self.floor.fid == "f3" and self.flags["raki"] < 3:
            t = text("Раков в лёгких: %d" % (3 - self.flags["raki"]), 22, (160, 200, 255), (0, 0, 0), 2)
            scr.blit(t, (SW - t.get_width() - 12, 128))
        # баннеры
        if self.banner:
            sub, title, tl = self.banner
            a = clamp(min(3.0 - tl, tl) * 2, 0, 1)
            yoff = (1 - ease_out(min(1, (3.0 - tl) * 2))) * -40
            bg = pygame.Rect(0, 0, 560, 110)
            bg.center = (SW // 2, int(SH // 2 - 70 + yoff))
            s = pygame.Surface(bg.size, pygame.SRCALPHA)
            s.fill((236, 226, 196, int(230 * a)))
            scr.blit(s, bg.topleft)
            pygame.draw.rect(scr, (60, 40, 30), bg, 3)
            if sub:
                t1 = text(sub, 28, (80, 50, 40), None)
                t1.set_alpha(int(255 * a))
                blit_center(scr, t1, SW // 2, bg.y + 26)
            t2 = text(title, 56, (40, 24, 20), None, bold=True)
            t2.set_alpha(int(255 * a))
            blit_center(scr, t2, SW // 2, bg.y + (68 if sub else 55))
        if self.item_banner:
            nm, ds, tl = self.item_banner
            a = clamp(min(3.0 - tl, tl) * 3, 0, 1)
            t1 = text(nm, 52, (255, 255, 255), (0, 0, 0), 3, bold=True)
            t2 = text(ds, 30, (230, 230, 230), (0, 0, 0), 2)
            t1.set_alpha(int(255 * a))
            t2.set_alpha(int(255 * a))
            bar = pygame.Surface((SW, 100), pygame.SRCALPHA)
            bar.fill((0, 0, 0, int(120 * a)))
            scr.blit(bar, (0, 70))
            blit_center(scr, t1, SW // 2, 102)
            blit_center(scr, t2, SW // 2, 146)
        if self.big_text:
            nm, ds, tl = self.big_text
            a = clamp(tl * 2, 0, 1)
            k = 1 + max(0, (tl - 1.7)) * 0.8
            t1 = text(nm, 64, (255, 230, 120), (60, 0, 0), 4, bold=True)
            if k != 1:
                t1 = pygame.transform.smoothscale(t1, (int(t1.get_width() * k), int(t1.get_height() * k)))
            t1.set_alpha(int(255 * a))
            blit_center(scr, t1, SW // 2, SH // 2 - 40)
            t2 = text(ds, 32, (255, 255, 255), (0, 0, 0), 2)
            t2.set_alpha(int(255 * a))
            blit_center(scr, t2, SW // 2, SH // 2 + 14)
        if self.vs:
            self.draw_vs(scr)
        if self.dialog:
            self.dialog.draw(scr)
        if self.white > 0:
            ov = cached(("whiteov",), lambda: _solid((255, 255, 255), 255, (SW, SH)))
            ov.set_alpha(int(255 * clamp(self.white, 0, 1)))
            scr.blit(ov, (0, 0))
        if self.hurt_flash > 0:
            ov = cached(("redov",), lambda: _solid((200, 0, 0), 255, (SW, SH)))
            ov.set_alpha(int(90 * self.hurt_flash / 0.25))
            scr.blit(ov, (0, 0))
        if self.fade > 0:
            ov = cached(("blackov",), lambda: _solid((0, 0, 0), 255, (SW, SH)))
            ov.set_alpha(int(255 * self.fade))
            scr.blit(ov, (0, 0))
        if self.overlay_text:
            txt, col = self.overlay_text
            t = text(txt, 34, col, (0, 0, 0), 3)
            blit_center(scr, t, SW // 2, SH // 2 - 120 if self.fade < 0.5 else SH // 2)
        if self.cinematic > 0:
            h = int(60 * self.cinematic)
            scr.fill((0, 0, 0), (0, 0, SW, h))
            scr.fill((0, 0, 0), (0, SH - h, SW, h))
        if self.paused:
            self.draw_pause(scr)
        if self.dead_screen is not None:
            self.draw_death(scr)

    def draw_vs(self, scr):
        name, t = self.vs[0], self.vs[1]
        k = ease_out(min(1, t * 3))
        out = clamp((t - 2.0) * 3, 0, 1)
        ov = pygame.Surface((SW, SH), pygame.SRCALPHA)
        ov.fill((0, 0, 0, int(200 * (1 - out))))
        scr.blit(ov, (0, 0))
        band = pygame.Rect(0, SH // 2 - 110, SW, 220)
        pygame.draw.rect(scr, (30, 10, 14), band)
        pygame.draw.line(scr, (200, 40, 50), band.topleft, band.topright, 4)
        pygame.draw.line(scr, (200, 40, 50), band.bottomleft, band.bottomright, 4)
        pp = portrait(self.player.spec)
        scr.blit(pp, (int(-200 + k * 300), band.y + 14))
        bp = self.vs[2]
        if bp is not None:
            scr.blit(bp, (int(SW + 100 - k * 400), band.y + 14))
        t1 = text("АРТЁМ", 46, (255, 255, 255), (0, 0, 0), 3, bold=True)
        scr.blit(t1, (int(-200 + k * 300) + 10, band.bottom - 56))
        t2 = text(name, 46, (255, 120, 120), (0, 0, 0), 3, bold=True)
        scr.blit(t2, (int(SW + 80 - k * 400) - t2.get_width() + 280, band.bottom - 56))
        vs = text("VS", 90, (255, 220, 80), (80, 0, 0), 5, bold=True)
        blit_center(scr, vs, SW // 2, SH // 2 + math.sin(t * 20) * 3 * (1 - k))

    def draw_pause(self, scr):
        ov = pygame.Surface((SW, SH), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 170))
        scr.blit(ov, (0, 0))
        paper = pygame.Rect(0, 0, 420, 330)
        paper.center = (SW // 2, SH // 2)
        pygame.draw.rect(scr, (230, 220, 190), paper, border_radius=8)
        pygame.draw.rect(scr, (60, 40, 30), paper, 4, border_radius=8)
        blit_center(scr, text("ПАУЗА", 54, (50, 30, 20), None, bold=True), SW // 2, paper.y + 44)
        labels = ["Продолжить", "Музыка: " + ("вкл" if AUDIO.music_on else "выкл"), "Звуки: %d%%" % int(SAVE["sfx"] * 100), "Выйти в меню"]
        for i, l in enumerate(labels):
            col = (180, 30, 30) if i == self.pause_sel else (60, 40, 30)
            blit_center(scr, text(l, 36, col, None), SW // 2, paper.y + 110 + i * 48)
        # предметы
        x = paper.x - 20
        y = paper.bottom + 16
        its = self.player.items
        for i, it in enumerate(its[:20]):
            ic = pygame.transform.scale(item_icon(it), (36, 36))
            scr.blit(ic, (SW // 2 - min(len(its), 20) * 20 + i * 40, y))

    def draw_death(self, scr):
        t = self.dead_screen
        a = clamp(t * 1.5, 0, 1)
        ov = pygame.Surface((SW, SH), pygame.SRCALPHA)
        ov.fill((0, 0, 0, int(190 * a)))
        scr.blit(ov, (0, 0))
        k = ease_out(clamp(t * 1.2, 0, 1))
        paper = pygame.Rect(0, 0, 520, 400)
        paper.center = (SW // 2, int(SH // 2 + (1 - k) * 400))
        pygame.draw.rect(scr, (232, 222, 194), paper, border_radius=6)
        for i in range(8):
            pygame.draw.line(scr, (190, 180, 160), (paper.x + 20, paper.y + 90 + i * 34), (paper.right - 20, paper.y + 90 + i * 34), 1)
        pygame.draw.rect(scr, (70, 50, 40), paper, 4, border_radius=6)
        blit_center(scr, text("ЗАПИСКА", 30, (90, 60, 50), None), paper.centerx, paper.y + 28)
        blit_center(scr, text("ТЫ УМЕР", 64, (150, 20, 20), None, bold=True), paper.centerx, paper.y + 72)
        fl = self.floor.cfg.get("title", "?") if self.floor else "?"
        blit_center(scr, text("Где: " + fl, 32, (50, 30, 20), None), paper.centerx, paper.y + 140)
        blit_center(scr, text("Убийца: " + self.killer_name(), 32, (50, 30, 20), None), paper.centerx, paper.y + 180)
        pp = person_frames(self.player.spec, "down", 0, 3)
        pp = pygame.transform.rotate(pp, 90)
        scr.blit(pp, (paper.centerx - pp.get_width() // 2, paper.y + 210))
        its = self.player.items
        for i, it in enumerate(its[:12]):
            ic = pygame.transform.scale(item_icon(it), (30, 30))
            scr.blit(ic, (paper.centerx - min(12, len(its)) * 17 + i * 34, paper.bottom - 64))
        if t > 1.5:
            blit_center(scr, text("ENTER — в меню", 28, (255, 255, 255), (0, 0, 0), 2), SW // 2, SH - 30)


class _NoKeys:
    def __getitem__(self, k):
        return False


def _solid(col, a, size=(WW, WH)):
    s = pygame.Surface(size, pygame.SRCALPHA)
    s.fill(col + (a,))
    return s


def _domain_overlay():
    s = pygame.Surface((WW, WH), pygame.SRCALPHA)
    s.fill((30, 0, 40, 120))
    rs = random.Random(5)
    for _ in range(26):
        x, y = rs.uniform(RX0, RX1), rs.uniform(RY0, RY1)
        if rs.random() < 0.5:
            pygame.draw.line(s, (190, 190, 210, 230), (x, y), (x + 3, y - 16), 2)
            pygame.draw.line(s, (120, 80, 40, 230), (x + 2, y - 12), (x + 6, y - 15), 2)
        else:
            pygame.draw.rect(s, (240, 220, 140, 220), (x, y - 14, 3, 14))
            pygame.draw.rect(s, (240, 220, 140, 220), (x - 3, y - 10, 9, 3))
    return s


def _mini_icon(w, icon, x, y, big):
    k = 2 if big else 1
    col = {"boss": (230, 40, 40), "treasure": (250, 210, 60), "shop": (90, 200, 120), "secret": (150, 150, 255),
           "dymok": (200, 200, 200), "food": (250, 150, 60), "rak": (90, 140, 255), "unknown": (180, 100, 255)}.get(icon, (255, 255, 255))
    if icon == "boss":
        pygame.draw.circle(w, col, (x, y), 2 * k)
    elif icon == "treasure":
        pygame.draw.polygon(w, col, [(x - 2 * k, y + 1 * k), (x - 2 * k, y - 2 * k), (x, y), (x + 2 * k, y - 2 * k), (x + 2 * k, y + 1 * k)])
    elif icon == "shop":
        pygame.draw.rect(w, col, (x - 1 * k, y - 2 * k, 2 * k, 4 * k))
    else:
        pygame.draw.rect(w, col, (x - 1 * k, y - 1 * k, 3 * k, 3 * k))


class Flash(Ent):
    def __init__(self, x, y, r):
        super().__init__(x, y)
        self.r = r

    def update(self, g, dt):
        self.t += dt
        if self.t > 0.25:
            self.dead = True

    def draw(self, surf, g):
        k = self.t / 0.25
        gl = light_glow(int(self.r * (0.6 + k)), (255, 200, 120), int(200 * (1 - k)))
        surf.blit(gl, (self.x - gl.get_width() / 2, self.y - gl.get_height() / 2), special_flags=pygame.BLEND_RGB_ADD)

    @property
    def sort_y(self):
        return 9999


class DomainBlade(Ent):
    def __init__(self, x, y, dmg):
        super().__init__(x, y)
        self.dmg = dmg
        self.kind = random.choice(["sword", "cross"])
        self.hit = False

    def update(self, g, dt):
        self.t += dt
        if self.t > 0.18 and not self.hit:
            self.hit = True
            if self.dmg > 0:
                for e in g.room.enemies:
                    if not e.dead and e.hittable and dist(e.x, e.y, self.x, self.y) < e.r + 12:
                        e.hurt(g, self.dmg, 0, 0, None)
            g.parts.burst(self.x, self.y, 5, (230, 220, 255), 50, 0.3, 2)
        if self.t > 0.7:
            self.dead = True

    def draw(self, surf, g):
        k = min(1, self.t / 0.18)
        y = self.y - 60 * (1 - k)
        a = 1 if self.t < 0.5 else max(0, 1 - (self.t - 0.5) / 0.2)
        if a <= 0:
            return
        if self.kind == "sword":
            pygame.draw.line(surf, (220, 220, 240), (self.x, y - 20), (self.x, y), 3)
            pygame.draw.line(surf, (120, 80, 40), (self.x - 5, y - 16), (self.x + 5, y - 16), 2)
        else:
            pygame.draw.rect(surf, (250, 220, 120), (self.x - 1, y - 20, 3, 20))
            pygame.draw.rect(surf, (250, 220, 120), (self.x - 6, y - 15, 13, 3))

    @property
    def sort_y(self):
        return self.y

# ============================================================================
#                           СЮЖЕТНЫЙ РЕЖИССЁР
# ============================================================================
class Story:
    def __init__(self, g):
        self.g = g
        self.dymok_ret = None
        self.f1_intro_done = False

    # ------------------------------------------------ условия
    def is_geno(self):
        f = self.g.flags
        return f["dymok"] == "killed" and f["sergei"] == "killed"

    def cond(self, c):
        neg = c.startswith("!")
        c = c.lstrip("!")
        if c.startswith("has:"):
            k = c[4:]
            v = bool(self.g.flags.get(k)) or self.g.player.has(k)
        elif c == "geno":
            v = self.is_geno()
        else:
            v = bool(self.g.flags.get(c))
        return (not v) if neg else v

    # ------------------------------------------------ старт
    def start(self, stage):
        g = self.g
        if stage == "prologue":
            g.load_floor("home", banner=False)
            AUDIO.music("home")
            g.run_script(self.s_prologue())

    def s_prologue(self):
        g = self.g
        g.fade = 1.0
        g.player.x, g.player.y = RCX, RCY + 20
        yield from g.fade_in(1.2)
        yield 0.5
        for _ in range(3):
            g.floater(g.player.x, g.player.y - 30, "*дзынь-дзынь*", (255, 255, 160))
            g.sfx("coin")
            yield 0.5
        g.big_text = ["СВЯЗЫВАНИЕ АРТЁМА", "Звонит Костян...", 2.5]
        yield 1.4
        yield from g.say_dialog("kostik")

    def save_ckpt(self):
        g = self.g
        p = g.player
        SAVE["kostya_ckpt"] = dict(char=g.char_id, items=list(p.items), active=p.active, red_max=p.red_max, red=max(2, p.red),
                                   soul=p.soul, coins=p.coins, bombs=p.bombs, keys=p.keys, flags=dict(g.flags), evil=p.evil)
        SAVE.save()

    def load_ckpt(self, ck):
        g = self.g
        p = g.player
        for it in ck.get("items", []):
            if it not in p.items:
                p.add_item(it, silent=True)
                fam = ITEMS[it].get("familiar")
                if fam:
                    g.familiars.append(Familiar(fam, len(g.familiars)))
        if ck.get("active"):
            p.add_item(ck["active"], silent=True)
        p.red_max = ck.get("red_max", 6)
        p.red = ck.get("red", p.red_max)
        p.soul = ck.get("soul", 0)
        p.coins, p.bombs, p.keys = ck.get("coins", 0), ck.get("bombs", 0), ck.get("keys", 0)
        g.flags.update(ck.get("flags", {}))
        p.evil = ck.get("evil", 3)
        p.recalc()
        self.goto("hall")

    # ------------------------------------------------ события мира
    def talk(self, npc):
        g = self.g
        if npc.tag == "shopkeeper":
            g.floater(npc.x, npc.y - 30, random.choice(["Покупай давай", "Скидок нет", "52"]), (255, 255, 200))
            return
        if not npc.dlg:
            return
        g.start_dialog(npc.dlg, npc=npc)

    def on_enter_room(self, room):
        g = self.g
        fl = g.floor
        if fl is None:
            return
        fid = fl.fid
        if room.kind == "boss" and not getattr(room, "setup", False):
            room.setup = True
            bk = room.boss_kind
            if bk == "npc_valerii":
                room.cleared = True
                room.npcs.append(NPC("valerii", RCX, RCY - 30, "valerii"))
            elif bk == "smoke":
                room.cleared = False
                b = BossSmoke(g, RCX, RCY - 30)
                room.enemies.append(b)
                self.vs("ТАБАЧНОЕ ОБЛАКО", lambda: draw_cloud(3, 0, True, angry=True, cig=True))
                AUDIO.music("boss")
            elif bk == "bigrak":
                room.cleared = False
                b = BossRak(g, RCX, RCY - 30, big=True)
                room.enemies.append(b)
                self.vs("ПОСЛЕДНИЙ РАК", lambda: draw_lobster(2.4, 0, True))
                AUDIO.music("boss")
            elif bk == "val2":
                room.cleared = True
                room.npcs.append(NPC("valerii", RCX, RCY - 30, "val2"))
                g.run_script(self.s_auto_dialog("val2", 0.6))
        if room.kind == "story" and room.story == "rak" and not room.cleared and not getattr(room, "setup", False):
            room.setup = True
            room.enemies.append(BossRak(g, RCX, RCY - 20, big=False))
            g.sfx("roar", 0.6)
            g.banner = ["", "РАК!", 1.6]
        if any(d.hidden for d in room.doors.values()) and not getattr(room, "whispered", False):
            room.whispered = True
            g.floater(RCX, RY0 + 30, "*кто-то шепчет за стеной...*", (200, 170, 255))
        if fid == "f1" and room is fl.start and not self.f1_intro_done:
            self.f1_intro_done = True
            g.run_script(self.s_auto_dialog("kostik_talked", 2.6))

    def s_auto_dialog(self, d, delay=0.5, start=1):
        yield delay
        yield from self.g.say_dialog(d, start)

    def vs(self, name, portrait_fn):
        sp = cached(("vsport", name), portrait_fn)
        self.g.vs = [name, 0.0, sp]
        self.g.sfx("roar", 0.7)

    def update(self, dt):
        pass

    def on_player_death(self, src):
        g = self.g
        if any(isinstance(e, BossValerii) and not e.final for e in g.room.enemies):
            if not getattr(self, "val1_dying", False):
                self.val1_dying = True
                g.player.red = 1
                self.val1_death()
            return True
        if g.floor and g.floor.fid == "hall" and not getattr(self, "kostya_won", False):
            if getattr(self, "retrying", False):
                return True
            self.retrying = True
            SAVE["kostya_deaths"] = SAVE["kostya_deaths"] + 1
            SAVE.save()
            g.run_script(self.s_kostya_retry())
            return True
        return False

    def on_boss_defeated(self, b):
        g = self.g
        b.dead = True
        room = g.room
        if isinstance(b, BossValerii) and b.final:
            AUDIO.stop_music(800)
            room.npcs.append(NPC("valerii", b.x, b.y, None))
            g.run_script(self.s_after_val2())
        elif isinstance(b, BossSmoke):
            room.cleared = True
            g.sfx("door")
            room.pedestals.append(Pedestal(pick_item(g.rng, "boss"), RCX + 70, RCY))
            n = NPC("sergei", b.x, b.y + 10, "sergei")
            room.npcs.append(n)
            g.parts.burst(b.x, b.y, 40, (180, 180, 180), 120, 1.0, 4)
            AUDIO.music("school")
            g.floater(n.x, n.y - 40, "*кхе-кхе*", (220, 220, 220))
        elif isinstance(b, BossRak) and not b.big:
            room.npcs.append(NPC("rak", b.x, b.y, None, kind="lobster"))
            g.run_script(self.s_rak_small(room))
        elif isinstance(b, BossRak) and b.big:
            room.npcs.append(NPC("rak", b.x, b.y, None, kind="lobster"))
            g.run_script(self.s_auto_dialog("rak3" if (g.flags["food"] or g.player.has("food")) else "rak2", 1.0))
        elif isinstance(b, BossJesus):
            AUDIO.stop_music(800)
            room.npcs.append(NPC("jesus", b.x, b.y, None))
            d = "jesusdead2" if self.is_geno() else ("jesusdead3" if g.flags["dad"] == "saved" else "jesusdead")
            g.run_script(self.s_auto_dialog(d, 1.5))
        elif isinstance(b, BossKostya2):
            self.kostya_won = True
            AUDIO.stop_music(800)
            room.npcs.append(NPC("kostya", b.x, b.y, None))
            g.run_script(self.s_auto_dialog("kostya_dead", 1.5))

    def s_rak_small(self, room):
        g = self.g
        yield 0.8
        yield from g.say_dialog("rak")
        for n in list(room.npcs):
            if n.kind == "lobster":
                room.npcs.remove(n)
                g.parts.burst(n.x, n.y, 30, (80, 130, 230), 120, 0.6, 3)
        room.cleared = True
        g.sfx("door")
        for _ in range(2):
            g.drop(g.random_pickup(), RCX, RCY)

    def s_after_val2(self):
        g = self.g
        yield 1.5
        f = g.flags
        d = _otec_dialog(bool(f["shard"]), bool(f["card"]), self.is_geno())
        d["papa"] = True
        yield from g.say_dialog(d)

    # ------------------------------------------------ сюжетные коллбеки
    def val1_death(self):
        if getattr(self, "val1_started", False):
            return
        self.val1_started = True
        self.g.run_script(self.s_val1_death())

    def s_val1_death(self):
        g = self.g
        g.god = True
        g.clear_bullets()
        g.sfx("explode")
        g.shake(14)
        AUDIO.stop_music(200)
        for _ in range(40):
            g.white = 1.2
            yield 0.03
        g.fade = 1.0
        g.fade_to = 1.0
        g.overlay_text = ("Ты умер...", (220, 220, 220))
        yield 2.2
        g.overlay_text = ("...но это ещё не конец.", (255, 230, 150))
        yield 2.0
        g.overlay_text = None
        p = g.player
        p.red = p.red_max
        g.load_floor("heaven")
        g.room.npcs.append(NPC("jesus", RCX, RY0 + 60, "jesus"))
        g.room.pedestals.append(Pedestal(pick_item(g.rng, "angel"), RCX + 110, RCY + 10))
        p.x, p.y = RCX, RY1 - 40
        g.god = False
        yield from g.fade_in(1.0)
        yield 1.0
        yield from g.say_dialog("jesus")

    def dymok_survived(self, b):
        self.g.run_script(self.s_dymok_after(b))

    def s_dymok_after(self, b):
        g = self.g
        b.dead = True
        g.sfx("meow")
        cat = NPC("dymok", b.x, b.y + 20, None, kind="cat")
        g.room.npcs.append(cat)
        AUDIO.music("floor1")
        yield 1.0
        yield from g.say_dialog("sukunacat")
        if g.flags["dymok"] == "killed":
            g.parts.burst(cat.x, cat.y, 40, (160, 160, 170), 140, 0.8, 3)
            if cat in g.room.npcs:
                g.room.npcs.remove(cat)
            yield 1.0
        yield from g.fade_out(2.0)
        floor, room = self.dymok_ret
        g.floor = floor
        g.enter_room(room, None)
        g.hp_scale = 1.0
        g.contact_dmg = 1
        for n in list(room.npcs):
            if n.who == "dymok":
                if g.flags["dymok"] == "killed":
                    room.npcs.remove(n)
                elif g.flags["dymok"] == "spared":
                    n.dlg = "dymok_spared"
        g.player.x, g.player.y = RCX, RCY + 40
        AUDIO.music("floor1")
        yield from g.fade_in(2.0)

    def kostya_tired(self, b):
        self.g.run_script(self.s_kostya_tired(b))

    def s_kostya_tired(self, b):
        g = self.g
        yield 0.8
        yield from g.say_dialog("sans2")

    # ------------------------------------------------ действия из диалогов
    def do(self, act, box=None):
        g = self.g
        if isinstance(act, (list, tuple)):
            for a in act:
                self.do(a, box)
            return
        name, _, arg = act.partition(":")
        npc = box.npc if box else None
        if name == "start_f1":
            g.run_script(self.s_goto_floor("f1"))
        elif name == "ending":
            g.run_script(self.s_ending(arg))
        elif name == "fight":
            self.fight(arg, npc)
        elif name == "npckey":
            if npc:
                npc.dlg = arg
        elif name == "give":
            g.give_item(arg)
            if arg in g.flags:
                g.flags[arg] = True
            if npc and npc.kind == "item":
                if npc in g.room.npcs:
                    g.room.npcs.remove(npc)
            if arg == "card" and npc:
                npc.dlg = "unknown_after"
        elif name == "dymok":
            g.flags["dymok"] = arg
        elif name == "kill":
            self.kill(arg)
        elif name == "goto":
            self.goto(arg)
        elif name == "dlg":
            d, l = arg.split(":")
            g.queue_dialog(d, int(l))
        elif name == "sfx":
            g.sfx(arg)
        elif name == "music":
            AUDIO.music(arg)
        elif name == "shake":
            g.shake(10)
            g.sfx("roar")
        elif name == "rak_killed":
            g.flags["raki"] += 1
            g.sfx("die")
            if g.flags["raki"] >= 3:
                for r in g.floor.all_rooms():
                    for d in r.doors.values():
                        if d.target.kind == "boss" or r.kind == "boss":
                            d.sealed = False
                g.big_text = ["ПУТЬ ОТКРЫТ", "Последний рак ждёт...", 2.5]
                g.sfx("secret")
        elif name == "sergei":
            g.flags["sergei"] = arg
            for n in list(g.room.npcs):
                if n.kind == "lobster":
                    g.room.npcs.remove(n)
                    g.parts.burst(n.x, n.y, 40, (80, 130, 230), 140, 0.7, 3)
            g.queue_dialog("sergei2" if arg == "saved" else "sergei3")
        elif name == "break_shard":
            g.sfx("shatter")
            g.white = 1.0
            g.flags["dad"] = "saved"
            g.flags["shard"] = False
            if "shard" in g.player.items:
                g.player.items.remove("shard")
                g.player.recalc()
        elif name == "open_door":
            for r in g.floor.all_rooms():
                for d in r.doors.values():
                    d.sealed = False
            g.sfx("door")
        elif name == "walk_out":
            if g.flags["jesus"] == "killed":
                g.run_script(self.s_ending("true_pacifist", walk=True))
            else:
                g.run_script(self.s_angel_rays("pacifist"))
        elif name == "angel_rays":
            g.run_script(self.s_angel_rays("neutral"))
        elif name == "kostya_phase2":
            g.run_script(self.s_kostya_phase2())
        elif name == "daniil_appears":
            g.run_script(self.s_daniil())
        elif name == "gaster_flee":
            for n in list(g.room.npcs):
                if n.who == "gaster":
                    g.room.npcs.remove(n)
                    g.parts.burst(n.x, n.y - 10, 40, (40, 40, 40), 120, 0.8, 3)
                    g.sfx("teleport")

    def kill(self, who):
        g = self.g
        p = g.player
        evil_up = False
        if who == "dymok":
            g.flags["dymok"] = "killed"
            evil_up = True
        elif who == "sergei":
            g.flags["sergei"] = "killed"
            evil_up = True
        elif who == "dad":
            g.flags["dad"] = "killed"
            evil_up = self.is_geno()
            self._remove_npc("valerii", (220, 30, 40))
            g.sfx("die")
        elif who == "jesus":
            g.flags["jesus"] = "killed"
            self._remove_npc("jesus", (255, 240, 180))
            evil_up = self.is_geno()
        elif who == "ellen":
            g.flags["ellen"] = "killed"
            self._remove_npc("ellen", (220, 30, 40))
            evil_up = True
        elif who == "kostya":
            g.flags["kostya"] = "killed"
            self._remove_npc("kostya", (90, 140, 220))
            evil_up = True
        elif who == "daniil":
            g.sfx("gun")
            g.white = 0.6
            self._remove_npc("daniil", (220, 30, 40))
            g.queue_dialog("gaster2")
        elif who == "gaster":
            g.sfx("gun")
            g.white = 0.6
            self._remove_npc("gaster", (30, 30, 30))
            g.queue_dialog("artem_mono")
            AUDIO.music("evil")
        if evil_up:
            p.evil = min(4, p.evil + 1)
            p.recalc()
            g.floater(p.x, p.y - 30, "LV UP", (255, 60, 60))
            g.sfx("bad", 0.6)

    def _remove_npc(self, who, col):
        g = self.g
        for n in list(g.room.npcs):
            if n.who == who:
                g.room.npcs.remove(n)
                g.parts.burst(n.x, n.y - 8, 40, col, 140, 0.8, 3, grav=100)
                g.room.decal_splat(n.x, n.y, col, 10)

    # ------------------------------------------------ бои
    def fight(self, kind, npc=None):
        g = self.g
        room = g.room
        if kind == "val1":
            x, y = (npc.x, npc.y) if npc else (RCX, RCY - 30)
            for n in list(room.npcs):
                if n.who == "valerii":
                    room.npcs.remove(n)
            room.cleared = False
            room.enemies.append(BossValerii(g, x, y, final=False))
            self.vs("ВАЛЕРИЙ", lambda: portrait("valerii"))
            AUDIO.music("valerii")
        elif kind == "dymok":
            g.run_script(self.s_dymok_fight())
        elif kind == "val2":
            g.run_script(self.s_val2_start())
        elif kind == "jesus":
            for n in list(room.npcs):
                if n.who == "jesus":
                    room.npcs.remove(n)
            room.cleared = False
            room.enemies.append(BossJesus(g, RCX, RY0 + 60))
            self.vs("ИИСУС", lambda: portrait("jesus"))
            AUDIO.music("jesus")
        elif kind == "kostya":
            g.run_script(self.s_kostya_start())

    def s_dymok_fight(self):
        g = self.g
        yield from g.fade_out(3.0)
        self.dymok_ret = (g.floor, g.room)
        g.load_floor("catdomain", banner=False)
        g.contact_dmg = 1
        g.room.cleared = False
        g.room.enemies.append(BossDymok(g, RCX, RY0 + 50))
        g.player.x, g.player.y = RCX, RY1 - 30
        g.big_text = ["РАСШИРЕНИЕ ТЕРРИТОРИИ", "ГРОБНИЦА ЦАРАПАНИЙ", 2.5]
        g.sfx("domain")
        yield from g.fade_in(3.0)

    def s_val2_start(self):
        g = self.g
        room = g.room
        g.cinematic = 1.0
        g.sfx("domain")
        g.white = 1.0
        g.shake(12)
        g.big_text = ["РАСШИРЕНИЕ ТЕРРИТОРИИ", "Кресты и мечи, как у Юты", 3.0]
        g.player.domain_t = 12.0
        g.domain_vis = 12.0
        g.player.recalc()
        yield 1.6
        x, y = RCX, RCY - 30
        for n in list(room.npcs):
            if n.who == "valerii":
                x, y = n.x, n.y
                room.npcs.remove(n)
        room.cleared = False
        b = BossValerii(g, x, y, final=True)
        room.enemies.append(b)
        b.say("Я... НЕ МОГУ ДАЖЕ П-П-ПОДВИНУТЬСЯ!!!", 3.0)
        b.idle_t = 2.5
        g.cinematic = 0.0
        AUDIO.music("final")
        self.vs("ВАЛЕРИЙ", lambda: portrait("valerii"))
        p = g.player
        if p.active == "domain":
            p.charge = 0

    def s_kostya_start(self):
        g = self.g
        room = g.room
        for n in list(room.npcs):
            if n.who == "kostya":
                room.npcs.remove(n)
        room.cleared = False
        if g.flags.get("kostya_phase", 1) >= 2:
            self._spawn_kostya2()
            AUDIO.music("tusk")
            self.vs("КОСТЯН и ТАСК", lambda: draw_tusk(3, 0))
        else:
            room.enemies.append(BossKostya(g, RCX, RY0 + 50))
            AUDIO.music("kostya")
            self.vs("КОСТЯН", lambda: portrait("kostya"))
        yield 0.1

    def _spawn_kostya2(self):
        g = self.g
        if not g.player.has("anubis"):
            g.give_item("anubis", banner=False)
        k = BossKostya2(g, RCX, RY0 + 50)
        k.invuln = True
        t = BossTusk(g, k)
        k.tusk = t
        g.room.enemies.append(k)
        g.room.enemies.append(t)

    def s_kostya_phase2(self):
        g = self.g
        g.flags["kostya_phase"] = 2
        self.save_ckpt()
        g.room.enemies = []
        g.give_item("anubis")
        g.big_text = ["АНУБИС", "Особый меч. Режет даже Таска.", 3.0]
        g.white = 0.8
        yield 2.0
        self._spawn_kostya2()
        AUDIO.music("tusk")
        self.vs("КОСТЯН и ТАСК", lambda: draw_tusk(3, 0))

    def s_kostya_retry(self):
        g = self.g
        p = g.player
        g.god = True
        g.clear_bullets()
        g.room.enemies = []
        AUDIO.stop_music(300)
        g.sfx("gameover")
        g.white = 1.0
        yield 0.6
        yield from g.fade_out(3.0)
        ck = SAVE["kostya_ckpt"] or {}
        p.red_max = ck.get("red_max", p.red_max)
        p.red = ck.get("red", p.red_max)
        p.soul = ck.get("soul", p.soul)
        p.dead = False
        p.inv = 2.0
        p.x, p.y = RCX, RY1 - 40
        g.room.npcs.append(NPC("kostya", RCX, RY0 + 50, None))
        g.god = False
        self.retrying = False
        yield from g.fade_in(3.0)
        d = SAVE["kostya_deaths"]
        yield from g.say_dialog(sans_retry_dialog(d))

    def s_daniil(self):
        g = self.g
        g.sfx("teleport")
        g.white = 0.8
        yield 0.5
        g.room.npcs.append(NPC("daniil", RCX + 70, RCY - 10, None))
        g.parts.burst(RCX + 70, RCY - 20, 40, (150, 200, 255), 120, 0.7, 3)
        AUDIO.music("rehab")
        yield 0.8
        yield from g.say_dialog("daniil")

    # ------------------------------------------------ переходы
    def s_goto_floor(self, fid, after=None):
        g = self.g
        yield from g.fade_out(2.0)
        g.load_floor(fid)
        if fid == "f3":
            for r in g.floor.all_rooms():
                for d in r.doors.values():
                    if d.target.kind == "boss" or r.kind == "boss":
                        d.sealed = True
        yield from g.fade_in(2.0)
        if after:
            yield from after()

    def s_arena(self, fid, npcs=(), dlg=None, delay=0.8, music=None, ppos=None):
        g = self.g
        yield from g.fade_out(2.0)
        g.load_floor(fid, banner=fid not in ("home",))
        for n in npcs:
            g.room.npcs.append(n)
        if ppos:
            g.player.x, g.player.y = ppos
        if music:
            AUDIO.music(music)
        yield from g.fade_in(2.0)
        if dlg:
            yield delay
            yield from g.say_dialog(dlg)

    def goto(self, where):
        g = self.g
        p = g.player
        if where == "prison":
            g.run_script(self.s_arena("prison", [NPC("john", RCX, RCY - 30, "john")], "john", ppos=(RCX, RY1 - 40)))
        elif where == "heaven_back":
            g.run_script(self.s_arena("heaven", [NPC("jesus", RCX, RY0 + 60, "jesus")], "jesus_back", ppos=(RCX, RY1 - 40)))
        elif where == "school":
            g.run_script(self.s_goto_floor("f2"))
        elif where == "lungs":
            g.run_script(self.s_to_lungs())
        elif where == "heaven2":
            d = "jesus3" if g.flags["sergei"] == "killed" else "jesus2"
            g.run_script(self.s_arena("heaven2", [NPC("jesus", RCX, RY0 + 60, d)], d, ppos=(RCX, RY1 - 40)))
            g.run_script(self.s_gift(), bg=True)
        elif where == "f4":
            g.run_script(self.s_goto_floor("f4"))
        elif where == "throne":
            g.run_script(self.s_arena("throne", [NPC("jesus", RCX, RY0 + 60, "jesusevil")], "jesusevil", ppos=(RCX, RY1 - 40), delay=1.2))
        elif where == "home_neutral":
            g.run_script(self.s_home("neutral"))
        elif where == "home_pacifist":
            g.run_script(self.s_home("pacifist"))
        elif where == "home_tn":
            g.run_script(self.s_home("tn"))
        elif where == "home_tp":
            g.run_script(self.s_home("tp"))
        elif where == "home_geno":
            g.run_script(self.s_home("geno"))
        elif where == "hall":
            g.run_script(self.s_hall())
        elif where == "void":
            g.run_script(self.s_arena("void", [NPC("gaster", RCX, RCY - 30, "gaster")], "gaster", ppos=(RCX, RY1 - 40), delay=1.5))

    def s_gift(self):
        g = self.g
        yield ("until", lambda: g.floor is not None and g.floor.fid == "heaven2")
        g.room.pedestals.append(Pedestal(pick_item(g.rng, "angel"), RCX + 110, RCY + 10))

    def s_to_lungs(self):
        g = self.g
        p = g.player
        g.sfx("shrink")
        p.shrink_t = 2.5
        g.floater(p.x, p.y - 20, "*уменьшился*", (180, 180, 255))
        yield 1.0
        g.white = 1.0
        yield 0.3
        yield from self.s_goto_floor("f3")

    def s_home(self, kind):
        g = self.g
        yield from g.fade_out(1.5)
        g.load_floor("home", banner=False)
        g.player.x, g.player.y = RCX, RCY + 40
        main = g.floor.start
        bed = getattr(g.floor, "extra", None)
        if kind == "pacifist":
            main.npcs.append(NPC("valerii", RCX - 60, RCY - 20, "papulia"))
            if bed:
                bed.npcs.append(NPC("ellen", RCX, RCY - 20, "ellen"))
            AUDIO.music("musicbox")
        elif kind == "tp":
            main.npcs.append(NPC("valerii", RCX - 60, RCY - 20, "papulia2"))
            if bed:
                bed.npcs.append(NPC("ellen", RCX, RCY - 20, "ellen"))
            AUDIO.music("musicbox")
        elif kind == "geno":
            main.npcs.append(NPC("ellen", RCX, RCY - 30, "ellen2"))
            AUDIO.music("evil")
        else:
            AUDIO.music("histheme" if kind == "neutral" else "musicbox")
        yield from g.fade_in(1.5)
        if kind == "neutral":
            yield 1.5
            g.sfx("coin")
            g.floater(RCX, RY0 + 10, "*звонок в дверь*", (255, 255, 160))
            yield 1.0
            yield from g.say_dialog("kostik2")
        elif kind == "tn":
            yield 1.5
            g.sfx("coin")
            g.floater(RCX, RY0 + 10, "*звонок в дверь*", (255, 255, 160))
            yield 1.0
            yield from g.say_dialog("kostik3")
        elif kind == "geno":
            yield 0.8
            yield from g.say_dialog("ellen2")

    def s_hall(self):
        g = self.g
        yield from g.fade_out(1.5)
        g.load_floor("hall")
        g.player.x, g.player.y = RCX, RY1 - 40
        g.room.npcs.append(NPC("kostya", RCX, RY0 + 50, None))
        self.save_ckpt()
        yield from g.fade_in(1.5)
        yield 1.2
        d = SAVE["kostya_deaths"]
        yield from g.say_dialog("sans" if d == 0 else sans_retry_dialog(d))

    def s_angel_rays(self, ending):
        g = self.g
        g.god = True
        g.cinematic = 1.0
        AUDIO.music("rays")
        for k in range(20):
            g.sky_dark = k / 20
            yield 0.05
        g.overlay_text = ("Иисус: Валерий больше не сдерживает меня...", (255, 230, 150))
        g.sfx("angel")
        yield 3.0
        g.overlay_text = ("Иисус: Прощайте, грешники.", (255, 230, 150))
        yield 2.0
        g.overlay_text = None
        for k in range(16):
            x = random.uniform(RX0, RX1) if k % 3 else g.player.x
            g.beams.append(Beam(x, RY0 - 10, math.pi / 2, 300, 26, 0.5, 0.6, 0, (255, 240, 170)))
            g.sfx("rays", 0.6)
            g.shake(6)
            yield 0.22
        yield 0.6
        for _ in range(30):
            g.white = 1.3
            yield 0.04
        g.finish(ending)

    def s_ending(self, eid, walk=False):
        g = self.g
        g.god = True
        if eid == "no_dnd":
            g.sfx("domain")
            g.big_text = ["РАСШИРЕНИЕ ТЕРРИТОРИИ", "(Костян по телефону)", 2.5]
            g.white = 1.0
            yield 1.5
            g.player.hurt(g, 0, None)
            g.parts.burst(g.player.x, g.player.y, 60, (200, 20, 30), 160, 1.0, 3, grav=200)
            yield 1.5
        if walk:
            yield 0.5
        yield from g.fade_out(1.0)
        yield 0.5
        g.finish(eid)


# ============================================================================
#                             МЕНЮ И ЭКРАНЫ
# ============================================================================
def draw_title_bg(scr, t, biome="apartment"):
    bg = cached(("titlebg", biome), lambda: _title_bg(biome))
    scr.blit(bg, (0, 0))


def _title_bg(biome):
    w = make_background(biome, 2).copy()
    w.blit(make_vignette(0.8), (0, 0))
    return pygame.transform.scale(w, (SW, SH))


class TitleScene:
    def __init__(self, app):
        self.app = app
        self.t = 0.0
        self.sel = 0
        AUDIO.music("title")

    def items(self):
        its = ["Новая игра"]
        if SAVE["kostya_ckpt"]:
            its.append("Продолжить: Костян ждёт...")
        its += ["Концовки (%d/%d)" % (len(SAVE["endings"]), len(ENDINGS)), "Управление", "Выход"]
        return its

    def handle(self, ev):
        if ev.type != pygame.KEYDOWN:
            return
        its = self.items()
        if ev.key in (pygame.K_UP, pygame.K_w):
            self.sel = (self.sel - 1) % len(its)
            AUDIO.play("menu")
        elif ev.key in (pygame.K_DOWN, pygame.K_s):
            self.sel = (self.sel + 1) % len(its)
            AUDIO.play("menu")
        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z, pygame.K_KP_ENTER):
            AUDIO.play("select")
            it = its[self.sel]
            if it.startswith("Новая"):
                self.app.state = CharSelectScene(self.app)
            elif it.startswith("Продолжить"):
                ck = SAVE["kostya_ckpt"]
                self.app.state = GameScene(self.app, ck.get("char", "artem"), ckpt=ck)
            elif it.startswith("Концовки"):
                self.app.state = EndingsScene(self.app)
            elif it.startswith("Управление"):
                self.app.state = HelpScene(self.app)
            elif it.startswith("Выход"):
                self.app.running = False
        elif ev.key == pygame.K_ESCAPE:
            pass

    def update(self, dt):
        self.t += dt

    def draw(self, scr):
        draw_title_bg(scr, self.t)
        # плачущий Артём
        sp = person_frames("artem", "down", 0, 5)
        bob = math.sin(self.t * 2) * 4
        blit_center(scr, sp, SW // 2, 300 + bob)
        for k in range(2):
            ph = (self.t * 1.3 + k * 0.5) % 1.0
            x = SW // 2 + (-17 if k == 0 else 17) * 1
            y = 300 - 20 + ph * 60
            ts = pygame.transform.scale(tear_sprite((120, 170, 255), 4), (14, 14))
            ts.set_alpha(int(255 * (1 - ph)))
            scr.blit(ts, (x - 7 + (-10 if k == 0 else 10) * ph, y))
        t1 = text("СВЯЗЫВАНИЕ", 84, (230, 220, 200), (40, 10, 10), 5, bold=True)
        t2 = text("АРТЁМА", 110, (220, 40, 40), (40, 0, 0), 6, bold=True)
        blit_center(scr, t1, SW // 2, 70 + math.sin(self.t) * 2)
        blit_center(scr, t2, SW // 2, 145 + math.sin(self.t + 1) * 2)
        its = self.items()
        y0 = 400
        for i, it in enumerate(its):
            col = (255, 230, 120) if i == self.sel else (220, 210, 200)
            ts = text(it, 36 if i == self.sel else 32, col, (0, 0, 0), 3)
            blit_center(scr, ts, SW // 2, y0 + i * 34)
            if i == self.sel:
                tr = pygame.transform.scale(tear_sprite((120, 170, 255), 5), (18, 18))
                scr.blit(tr, (SW // 2 - ts.get_width() // 2 - 30, y0 + i * 34 - 9))
        d, n = AUDIO.progress
        if d < n:
            ts = text("Сочиняю музыку... %d/%d" % (d, n), 22, (180, 180, 180), (0, 0, 0), 2)
            scr.blit(ts, (10, SH - 30))
        ts = text("v" + VERSION + "  •  F11 полный экран  •  M музыка", 20, (150, 140, 130), (0, 0, 0), 1)
        scr.blit(ts, (SW - ts.get_width() - 10, SH - 26))


class CharSelectScene:
    def __init__(self, app):
        self.app = app
        self.keys = list(CHARACTERS.keys())
        self.sel = 0
        self.t = 0.0

    def unlocked(self, k):
        return k in SAVE["chars"]

    def handle(self, ev):
        if ev.type != pygame.KEYDOWN:
            return
        if ev.key in (pygame.K_LEFT, pygame.K_a):
            self.sel = (self.sel - 1) % len(self.keys)
            AUDIO.play("menu")
        elif ev.key in (pygame.K_RIGHT, pygame.K_d):
            self.sel = (self.sel + 1) % len(self.keys)
            AUDIO.play("menu")
        elif ev.key in (pygame.K_ESCAPE,):
            self.app.to_title()
        elif ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_z, pygame.K_KP_ENTER):
            k = self.keys[self.sel]
            if self.unlocked(k):
                AUDIO.play("select")
                self.app.state = GameScene(self.app, k)
            else:
                AUDIO.play("bad")

    def update(self, dt):
        self.t += dt

    def draw(self, scr):
        draw_title_bg(scr, self.t)
        blit_center(scr, text("КТО ТЫ?", 64, (230, 220, 200), (40, 10, 10), 4, bold=True), SW // 2, 60)
        n = len(self.keys)
        for i, k in enumerate(self.keys):
            ch = CHARACTERS[k]
            cx = SW // 2 + (i - self.sel) * 300
            sel = i == self.sel
            card = pygame.Rect(0, 0, 260, 360)
            card.center = (cx, 300)
            pygame.draw.rect(scr, (232, 222, 194) if sel else (150, 140, 120), card, border_radius=10)
            pygame.draw.rect(scr, (70, 50, 40), card, 4, border_radius=10)
            if self.unlocked(k):
                sp = person_frames(ch["spec"], "down", int(self.t * 6) % 4 if sel else 0, 4)
                blit_center(scr, sp, cx, card.y + 110)
                blit_center(scr, text(ch["name"], 36, (40, 24, 20), None, bold=True), cx, card.y + 200)
                lay_y = card.y + 230
                draw_rich(scr, ch["desc"], 22, card.x + 16, lay_y, card.w - 32, (40, 30, 30))
                hx = cx - (ch["hearts"] // 2 + ch["soul"] // 2) * 16
                for j in range(ch["hearts"] // 2):
                    scr.blit(pygame.transform.scale(hud_heart("full"), (26, 24)), (hx + j * 30, card.bottom - 50))
                for j in range(ch["soul"] // 2):
                    scr.blit(pygame.transform.scale(hud_heart("soul"), (26, 24)), (hx + (ch["hearts"] // 2 + j) * 30, card.bottom - 50))
            else:
                blit_center(scr, text("???", 80, (60, 50, 40), None, bold=True), cx, card.y + 120)
                draw_rich(scr, ch.get("unlock", ""), 24, card.x + 16, card.y + 220, card.w - 32, (60, 40, 30))
        blit_center(scr, text("← →  выбор     ENTER  начать     ESC  назад", 26, (230, 230, 230), (0, 0, 0), 2), SW // 2, SH - 40)


class EndingsScene:
    def __init__(self, app):
        self.app = app
        self.t = 0.0

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE, pygame.K_z):
            AUDIO.play("select")
            self.app.to_title()

    def update(self, dt):
        self.t += dt

    def draw(self, scr):
        draw_title_bg(scr, self.t)
        blit_center(scr, text("КОНЦОВКИ", 64, (230, 220, 200), (40, 10, 10), 4, bold=True), SW // 2, 46)
        got = SAVE["endings"]
        for i, eid in enumerate(ENDING_ORDER):
            nm, ds, cat = ENDINGS[eid]
            col = i % 2
            row = i // 2
            r = pygame.Rect(30 + col * 455, 92 + row * 76, 445, 70)
            ok = eid in got
            pygame.draw.rect(scr, (232, 222, 194) if ok else (90, 80, 70), r, border_radius=6)
            pygame.draw.rect(scr, (70, 50, 40), r, 3, border_radius=6)
            tc = {"main": (40, 60, 140), "geno": (150, 20, 20), "jokes": (90, 60, 20)}[cat]
            if ok:
                scr.blit(text(nm, 28, tc, None, bold=True), (r.x + 10, r.y + 6))
                draw_rich(scr, ds, 19, r.x + 10, r.y + 32, r.w - 20, (50, 40, 30))
            else:
                scr.blit(text("???", 28, (50, 40, 30), None, bold=True), (r.x + 10, r.y + 6))
        ts = text("Смертей: %d   Забегов: %d   Смертей от Костяна: %d" % (SAVE["deaths"], SAVE["runs"], SAVE["kostya_deaths"]), 22,
                  (220, 220, 220), (0, 0, 0), 2)
        blit_center(scr, ts, SW // 2, SH - 20)


class HelpScene:
    LINES = [
        ("WASD", "ходьба"), ("Стрелки", "стрельба слезами"), ("ПРОБЕЛ", "активный предмет"), ("E / Shift", "бомба"),
        ("ENTER", "говорить с персонажем"), ("TAB", "большая карта и статы"), ("ESC", "пауза"), ("M / F11", "музыка / полный экран"),
        ("", ""), ("Диалоги", "W/S выбор, ENTER далее, X промотать"),
        ("Совет", "Бомбы открывают секретные комнаты. Ищи трещины в стенах!"),
        ("Совет", "Твои выборы в диалогах решают, какая будет концовка."),
    ]

    def __init__(self, app):
        self.app = app
        self.t = 0

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN:
            self.app.to_title()

    def update(self, dt):
        self.t += dt

    def draw(self, scr):
        draw_title_bg(scr, self.t)
        paper = pygame.Rect(80, 40, SW - 160, SH - 80)
        pygame.draw.rect(scr, (232, 222, 194), paper, border_radius=8)
        pygame.draw.rect(scr, (70, 50, 40), paper, 4, border_radius=8)
        blit_center(scr, text("УПРАВЛЕНИЕ", 54, (50, 30, 20), None, bold=True), SW // 2, paper.y + 40)
        y = paper.y + 84
        for i, (k, v) in enumerate(self.LINES):
            scr.blit(text(k, 28, (150, 30, 30), None, bold=True), (paper.x + 40, y))
            draw_rich(scr, v, 26, paper.x + 220, y + 2, paper.w - 250, (50, 30, 20))
            lines, lh, _ = layout_text(v, 26, paper.w - 250) if v else ([[]], 20, 0)
            y += max(26, len(lines) * lh) + 5


ENDING_MUSIC = {"no_dnd": "domain", "lera": "home", "dream": "prison", "neutral": "histheme", "pacifist": "histheme",
                "true_neutral": "musicbox", "true_pacifist": "musicbox", "geno_abort": "evil", "peace": "peace", "gaster": "digital",
                "rehab": "rehab", "true_evil": "evil"}


class EndingScene:
    def __init__(self, app, eid, game):
        self.app = app
        self.eid = eid
        self.t = 0.0
        self.new = SAVE.unlock_ending(eid)
        self.char_unlock = None
        if eid in ("true_neutral", "true_pacifist") and SAVE.unlock_char("artemosha"):
            self.char_unlock = "Артёмоша"
        if eid in ("gaster", "rehab", "true_evil", "peace", "geno_abort") and SAVE.unlock_char("artem_dark"):
            self.char_unlock = "Тёмный Артём"
        if ENDINGS[eid][2] == "geno" or eid in ("peace",):
            SAVE["kostya_ckpt"] = None
        SAVE["wins"] = SAVE["wins"] + (1 if ENDINGS[eid][2] != "jokes" else 0)
        SAVE.save()
        AUDIO.music(ENDING_MUSIC.get(eid, "musicbox"))
        AUDIO.play("ending")
        self.scene = pygame.transform.scale(self.make_scene(), (SW, SH))

    def make_scene(self):
        s = pygame.Surface((WW, WH))
        eid = self.eid
        cat = ENDINGS[eid][2]
        top, bot = (40, 30, 60), (200, 120, 80)
        if eid in ("true_pacifist", "true_neutral", "peace", "lera"):
            top, bot = (90, 120, 200), (250, 190, 120)
        elif eid in ("neutral", "pacifist"):
            top, bot = (60, 10, 20), (250, 220, 150)
        elif cat == "geno":
            top, bot = (10, 0, 0), (90, 0, 10)
        elif eid == "dream":
            top, bot = (40, 40, 50), (100, 100, 110)
        elif eid == "rehab":
            top, bot = (120, 170, 230), (230, 230, 200)
        for y in range(WH):
            k = y / WH
            pygame.draw.line(s, col_mix(top, bot, k), (0, y), (WW, y))
        rs = random.Random(hash(eid) % 1000)
        # город
        for i in range(14):
            x = i * 36 + rs.randint(-6, 6)
            h = rs.randint(40, 110)
            c = col_mul(top, 0.6)
            pygame.draw.rect(s, c, (x, WH - 60 - h, 32, h + 10))
            for wy in range(WH - 60 - h + 6, WH - 60, 12):
                for wx in (x + 5, x + 18):
                    if rs.random() < 0.5:
                        pygame.draw.rect(s, (250, 220, 120) if cat != "geno" else (120, 0, 0), (wx, wy, 6, 6))
        pygame.draw.rect(s, col_mul(bot, 0.45), (0, WH - 60, WW, 60))
        if eid in ("neutral", "pacifist"):
            for k in range(6):
                x = 40 + k * 80
                pygame.draw.rect(s, (255, 250, 210), (x, 0, 18, WH - 60))
                pygame.draw.rect(s, (255, 255, 255), (x + 5, 0, 8, WH - 60))
        chars = {"true_pacifist": ["artem", "valerii", "ellen"], "true_neutral": ["artem"], "neutral": ["artem", "kostya"],
                 "pacifist": ["artem", "valerii", "ellen"], "geno_abort": ["artem_dark"], "peace": ["artem_dark", "kostya"],
                 "gaster": ["gaster", "artem_dark"], "rehab": ["artem_dark", "daniil"], "true_evil": ["artem_dark"],
                 "no_dnd": ["kostya"], "lera": ["artem", "kostya"], "dream": ["john", "artem"]}.get(eid, ["artem"])
        n = len(chars)
        for i, c in enumerate(chars):
            ex = ("evil", "horns") if c == "artem_dark" and eid == "true_evil" else ()
            sp = person_frames(c, "down", 0, 2, None, ex)
            x = WW / 2 + (i - (n - 1) / 2) * 60
            s.blit(shadow_surf(30, 8, 100), (x - 15, WH - 66))
            s.blit(sp, (x - sp.get_width() / 2, WH - 62 - sp.get_height() + 10))
        if eid == "true_evil":
            for k in range(5):
                pygame.draw.circle(s, (120, 0, 0), (rs.randint(20, WW - 20), rs.randint(WH - 50, WH - 10)), rs.randint(6, 14))
        s.blit(make_vignette(0.6), (0, 0))
        return s

    def handle(self, ev):
        if ev.type == pygame.KEYDOWN and self.t > 2.5 and ev.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_z):
            AUDIO.play("select")
            self.app.to_title()

    def update(self, dt):
        self.t += dt

    def draw(self, scr):
        scr.blit(self.scene, (0, 0))
        a = clamp(self.t * 0.8, 0, 1)
        nm, ds, cat = ENDINGS[self.eid]
        band = pygame.Surface((SW, 190), pygame.SRCALPHA)
        band.fill((0, 0, 0, int(170 * a)))
        scr.blit(band, (0, 30))
        t1 = text("КОНЦОВКА", 34, (220, 210, 200), (0, 0, 0), 2)
        t1.set_alpha(int(255 * a))
        blit_center(scr, t1, SW // 2, 60)
        col = {"main": (255, 230, 140), "geno": (255, 70, 70), "jokes": (200, 220, 255)}[cat]
        t2 = text(nm, 70, col, (0, 0, 0), 4, bold=True)
        t2.set_alpha(int(255 * clamp(self.t * 0.8 - 0.3, 0, 1)))
        blit_center(scr, t2, SW // 2, 115)
        if self.t > 1.0:
            draw_rich(scr, ds, 28, 80, 160, SW - 160, (240, 240, 240), reveal=int((self.t - 1.0) * 40))
        if self.t > 2.5:
            y = SH - 110
            band2 = pygame.Surface((SW, 110), pygame.SRCALPHA)
            band2.fill((0, 0, 0, 150))
            scr.blit(band2, (0, SH - 130))
            if self.new:
                blit_center(scr, text("Новая концовка!  %d / %d" % (len(SAVE["endings"]), len(ENDINGS)), 30, (255, 255, 150), (0, 0, 0), 2), SW // 2, y)
            if self.char_unlock:
                blit_center(scr, text("Открыт персонаж: " + self.char_unlock, 30, (150, 255, 150), (0, 0, 0), 2), SW // 2, y + 34)
            if int(self.t * 2) % 2 == 0:
                blit_center(scr, text("ENTER", 28, (255, 255, 255), (0, 0, 0), 2), SW // 2, SH - 30)


# ============================================================================
#                                ПРИЛОЖЕНИЕ
# ============================================================================
AUDIO = None


class App:
    def __init__(self):
        global FONTS, AUDIO
        AUDIO = Audio()
        pygame.init()
        flags = pygame.SCALED | pygame.RESIZABLE
        try:
            self.screen = pygame.display.set_mode((SW, SH), flags, vsync=1)
        except Exception:
            self.screen = pygame.display.set_mode((SW, SH), flags)
        pygame.display.set_caption(GAME_TITLE)
        FONTS = Fonts()
        try:
            ic = person_frames("artem", "down", 0, 1)
            icon = pygame.Surface((32, 32), pygame.SRCALPHA)
            icon.blit(ic, (16 - ic.get_width() // 2, 0))
            pygame.display.set_icon(icon)
        except Exception:
            pass
        AUDIO.init_sfx()
        AUDIO.prefetch_all(first=["title", "home", "floor1", "valerii", "heaven", "school"])
        if SAVE["fullscreen"]:
            try:
                pygame.display.toggle_fullscreen()
            except Exception:
                pass
        self.clock = pygame.time.Clock()
        self.running = True
        self.state = TitleScene(self)

    def to_title(self):
        self.state = TitleScene(self)

    def show_ending(self, eid, game):
        self.state = EndingScene(self, eid, game)

    def run(self, max_frames=None, script=None):
        acc = 0.0
        frames = 0
        while self.running:
            ms = self.clock.tick(FPS)
            dtr = min(0.1, ms / 1000.0)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.running = False
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                    try:
                        pygame.display.toggle_fullscreen()
                        SAVE["fullscreen"] = not SAVE["fullscreen"]
                        SAVE.save()
                    except Exception:
                        pass
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_m and not isinstance(self.state, GameScene) or \
                        (ev.type == pygame.KEYDOWN and ev.key == pygame.K_m and isinstance(self.state, GameScene) and not self.state.dialog):
                    AUDIO.toggle_music()
                else:
                    self.state.handle(ev)
            if script:
                script(self, frames)
            acc += dtr
            steps = 0
            while acc >= DT and steps < 5:
                self.state.update(DT)
                acc -= DT
                steps += 1
            AUDIO.update()
            self.state.draw(self.screen)
            pygame.display.flip()
            frames += 1
            if max_frames and frames >= max_frames:
                break
        SAVE.save()


def main():
    app = App()
    app.run()
    pygame.quit()


if __name__ == "__main__":
    main()
