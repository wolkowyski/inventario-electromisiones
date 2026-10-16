#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Interfaz gráfica Tkinter para Inventario Electro Misiones.
Incluye buscador en vivo en la vista previa y comparador de diferencias.
"""
import ctypes
import json
import math
import os
import queue
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlparse

core = None


def _importar_core():
    global core
    import inventario_electromisiones as _c
    core = _c


ACCENT = "#F97316"
CLAVES = ("BG", "PANEL", "PANEL2", "BORDER", "TEXT", "MUTED", "OK", "WARN", "ERR")
OSCURO = dict(BG="#0E1014", PANEL="#161A21", PANEL2="#1E232C", BORDER="#2B313D", TEXT="#E9ECF2",
              MUTED="#8A93A6", OK="#34D399", WARN="#FBBF24", ERR="#F87171", ACC_TXT="#F97316")
CLARO = dict(BG="#F2F3F7", PANEL="#FFFFFF", PANEL2="#EDEFF4", BORDER="#D3D8E2", TEXT="#171A21",
             MUTED="#667085", OK="#059669", WARN="#B45309", ERR="#DC2626", ACC_TXT="#C2410C")
TEMA = "oscuro"
BG = PANEL = PANEL2 = BORDER = TEXT = MUTED = OK = WARN = ERR = ACC_TXT = ""
PAPEL, PAPEL_TXT, PAPEL_LINEA, PAPEL_HEAD = "#FFFFFF", "#1C1C20", "#C9C9CF", "#E4E4E8"


def aplicar_paleta(nombre):
    global TEMA, BG, PANEL, PANEL2, BORDER, TEXT, MUTED, OK, WARN, ERR, ACC_TXT
    p = OSCURO if nombre == "oscuro" else CLARO
    BG, PANEL, PANEL2, BORDER = p["BG"], p["PANEL"], p["PANEL2"], p["BORDER"]
    TEXT, MUTED, OK, WARN, ERR, ACC_TXT = p["TEXT"], p["MUTED"], p["OK"], p["WARN"], p["ERR"], p["ACC_TXT"]
    TEMA = nombre


def mapa_colores(desde, hasta):
    a, b = (OSCURO if desde == "oscuro" else CLARO), (OSCURO if hasta == "oscuro" else CLARO)
    return {a[k].lower(): b[k] for k in CLAVES}


aplicar_paleta("oscuro")

FONT_UI = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")
FONT_SM = ("Segoe UI", 9)
FONT_H = ("Segoe UI", 17, "bold")
FONT_NUM = ("Segoe UI", 19, "bold")
FONT_CAP = ("Segoe UI", 8, "bold")
FONT_ROW = ("Segoe UI", 8)
FONT_ROWB = ("Segoe UI", 8, "bold")
FONT_MONO = ("Consolas", 9)

ETAPAS = ["Detectar", "Listados", "Fichas", "Exportar"]
PESOS = [(0.00, 0.03), (0.03, 0.78), (0.78, 0.92), (0.92, 1.00)]
FILAS_PAGINA = 52
DEFAULT_URL = "https://www.electromisiones.com.ar"
CONFIG = os.path.join(os.path.expanduser("~"), ".inventario_electromisiones.json")
BOLT = [(.57, .12), (.27, .56), (.47, .56), (.40, .89), (.73, .42), (.53, .42)]
K = 1.0


def P(n):
    return int(round(n * K))


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    ra, rb = hex_rgb(a), hex_rgb(b)
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * t) for x, y in zip(ra, rb))


def on_color(h):
    r, g, b = hex_rgb(h)
    return "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 165 else "#FFFFFF"


def rrect(c, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(pts, smooth=True, **kw)


def fmt_n(n):
    return f"{int(n):,}".replace(",", ".")


def fmt_t(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def normalizar_url(u):
    u = (u or "").strip()
    if not u:
        return None
    if "://" not in u:
        u = "https://" + u
    p = urlparse(u)
    if p.scheme not in ("http", "https") or "." not in p.netloc:
        return None
    return f"{p.scheme}://{p.netloc}{p.path.rstrip('/')}"


def cargar_cfg():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def guardar_cfg(d):
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(d, f)
    except OSError:
        pass


def hacer_icono(n=64):
    img = tk.PhotoImage(width=n, height=n)
    r = n * 0.28
    pts = [(x * n, y * n) for x, y in BOLT]

    def en_poligono(px, py):
        dentro, j = False, len(pts) - 1
        for i in range(len(pts)):
            xi, yi = pts[i]
            xj, yj = pts[j]
            if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                dentro = not dentro
            j = i
        return dentro

    for y in range(n):
        fila, x0 = [], None
        for x in range(n):
            cx, cy = min(max(x + .5, r), n - r), min(max(y + .5, r), n - r)
            if (x + .5 - cx) ** 2 + (y + .5 - cy) ** 2 <= r * r:
                if x0 is None:
                    x0 = x
                fila.append("#ffffff" if en_poligono(x + .5, y + .5) else ACCENT)
        if fila:
            img.put("{" + " ".join(fila) + "}", to=(x0, y))
    return img


class Logo(tk.Canvas):
    def __init__(self, master, size=46):
        self.s = P(size)
        super().__init__(master, width=self.s, height=self.s, bg=BG, highlightthickness=0)
        self.draw()

    def refresh(self):
        self.draw()

    def draw(self):
        self.delete("all")
        s = self.s
        rrect(self, 1, 1, s - 1, s - 1, int(s * .28), fill=ACCENT, outline="")
        self.create_polygon([v * s for p in BOLT for v in p], fill=on_color(ACCENT), outline="")


class IconBtn(tk.Canvas):
    def __init__(self, master, kind, command):
        self.s = P(38)
        super().__init__(master, width=self.s, height=self.s, bg=BG, highlightthickness=0, cursor="hand2")
        self.kind, self.cmd, self.hover = kind, command, False
        self.bind("<Enter>", lambda e: self._h(True))
        self.bind("<Leave>", lambda e: self._h(False))
        self.bind("<Button-1>", lambda e: self.cmd())
        self.draw()

    def _h(self, v):
        self.hover = v
        self.draw()

    def refresh(self):
        self.draw()

    def draw(self):
        self.delete("all")
        s = self.s
        c = s / 2
        fill = mix(PANEL2, TEXT, .08) if self.hover else PANEL2
        self.create_oval(1, 1, s - 1, s - 1, fill=fill, outline=ACCENT if self.hover else BORDER)
        col = ACC_TXT if self.hover else TEXT
        if self.kind == "gear":
            pts = []
            for i in range(8):
                a0 = i * math.pi / 4
                for rad, da in ((P(6.6), -.40), (P(9.2), -.22), (P(9.2), .22), (P(6.6), .40)):
                    pts += [c + rad * math.cos(a0 + da), c + rad * math.sin(a0 + da)]
            self.create_polygon(pts, fill=col, outline=col)
            self.create_oval(c - P(3.2), c - P(3.2), c + P(3.2), c + P(3.2), fill=fill, outline=fill)
        elif TEMA == "oscuro":
            r = P(4.2)
            self.create_oval(c - r, c - r, c + r, c + r, fill=col, outline=col)
            for i in range(8):
                a = i * math.pi / 4
                self.create_line(c + P(7) * math.cos(a), c + P(7) * math.sin(a),
                                 c + P(9.4) * math.cos(a), c + P(9.4) * math.sin(a),
                                 fill=col, width=P(2), capstyle="round")
        else:
            r = P(7.5)
            self.create_oval(c - r, c - r, c + r, c + r, fill=col, outline=col)
            self.create_oval(c - r + P(5), c - r - P(3.5), c + r + P(5), c + r - P(3.5), fill=fill, outline=fill)


class Btn(tk.Canvas):
    def __init__(self, master, text, command, primary=False, w=150, h=40):
        self.w, self.h = P(w), P(h)
        super().__init__(master, width=self.w, height=self.h, bg=BG, highlightthickness=0, cursor="hand2")
        self.text, self.cmd, self.primary = text, command, primary
        self.enabled, self.hover, self.down = True, False, False
        self.bind("<Enter>", lambda e: self._set(hover=True))
        self.bind("<Leave>", lambda e: self._set(hover=False, down=False))
        self.bind("<ButtonPress-1>", lambda e: self._set(down=True))
        self.bind("<ButtonRelease-1>", self._release)
        self.draw()

    def _set(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)
        self.draw()

    def _release(self, e):
        was = self.down
        self._set(down=False)
        if was and self.enabled and 0 <= e.x <= self.w and 0 <= e.y <= self.h:
            self.cmd()

    def set_enabled(self, on):
        self.enabled = on
        self.configure(cursor="hand2" if on else "arrow")
        self.draw()

    def refresh(self):
        self.draw()

    def draw(self):
        self.delete("all")
        if not self.enabled:
            fill, line, fg = PANEL, BORDER, mix(MUTED, BG, .4)
        elif self.primary:
            fill = mix(ACCENT, "#000000", .18) if self.down else (
                mix(ACCENT, "#FFFFFF", .14) if self.hover else ACCENT)
            line, fg = fill, on_color(ACCENT)
        else:
            fill = mix(PANEL2, TEXT, .14) if self.down else (mix(PANEL2, TEXT, .07) if self.hover else PANEL2)
            line, fg = (ACCENT if self.hover else BORDER), TEXT
        rrect(self, 1, 1, self.w - 1, self.h - 1, P(11), fill=fill, outline=line)
        self.create_text(self.w / 2, self.h / 2, text=self.text, fill=fg, font=FONT_B)


class Toggle(tk.Canvas):
    def __init__(self, master, value, command=None):
        self.w, self.h = P(44), P(24)
        super().__init__(master, width=self.w, height=self.h, bg=BG, highlightthickness=0, cursor="hand2")
        self.value, self.pos, self.command = bool(value), 1.0 if value else 0.0, command
        self.bind("<Button-1>", self._click)
        self.draw()

    def _click(self, _):
        self.value = not self.value
        self._anim()
        if self.command:
            self.command(self.value)

    def _anim(self):
        t = 1.0 if self.value else 0.0
        self.pos += (t - self.pos) * 0.38
        if abs(t - self.pos) < 0.03:
            self.pos = t
        self.draw()
        if self.pos != t:
            self.after(16, self._anim)

    def refresh(self):
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.w, self.h
        rrect(self, 1, 1, w - 1, h - 1, h // 2, fill=mix(BORDER, ACCENT, self.pos), outline="")
        r = h / 2 - P(3)
        cx = h / 2 + self.pos * (w - h)
        self.create_oval(cx - r, h / 2 - r, cx + r, h / 2 + r, fill="#FFFFFF", outline="")


class Seg(tk.Canvas):
    def __init__(self, master, opciones, sel, command, w=96, h=32):
        self.n, self.sw, self.h = len(opciones), P(w), P(h)
        self.W = self.sw * self.n + P(6)
        super().__init__(master, width=self.W, height=self.h, bg=BG, highlightthickness=0, cursor="hand2")
        self.op, self.sel, self.cmd = opciones, sel, command
        self.bind("<Button-1>", self._click)
        self.draw()

    def _click(self, e):
        i = int((e.x - P(3)) // self.sw)
        if 0 <= i < self.n and i != self.sel:
            self.sel = i
            self.draw()
            self.cmd(i)

    def refresh(self):
        self.draw()

    def draw(self):
        self.delete("all")
        rrect(self, 1, 1, self.W - 1, self.h - 1, P(11), fill=PANEL2, outline=BORDER)
        for i, t in enumerate(self.op):
            x = P(3) + i * self.sw
            if i == self.sel:
                rrect(self, x, P(3), x + self.sw, self.h - P(3), P(8), fill=ACCENT, outline="")
            self.create_text(x + self.sw / 2, self.h / 2, text=t, font=FONT_B,
                             fill=on_color(ACCENT) if i == self.sel else MUTED)


class Card(tk.Canvas):
    def __init__(self, master, title):
        super().__init__(master, height=P(76), bg=BG, highlightthickness=0)
        self.title, self.text, self.color = title, "0", None
        self.target, self.shown = None, 0.0
        self.bind("<Configure>", lambda e: self.draw())

    def refresh(self):
        self.draw()

    def reset(self, text="0"):
        self.target, self.shown, self.text, self.color = None, 0.0, text, None
        self.draw()

    def set_text(self, t, color=None):
        if t != self.text or color != self.color:
            self.text, self.color = t, color
            self.draw()

    def set_number(self, n):
        self.target, self.color = n, None

    def tick(self):
        if self.target is None:
            return
        d = self.target - self.shown
        if d == 0:
            return
        step = d * 0.22
        if abs(step) < 1:
            step = math.copysign(min(1, abs(d)), d)
        self.shown += step
        self.text = fmt_n(self.shown)
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        rrect(self, 1, 1, w - 1, h - 1, P(14), fill=PANEL, outline=BORDER)
        self.create_text(P(16), P(22), text=self.title, anchor="w", fill=MUTED, font=FONT_CAP)
        col = {"ok": OK, "err": ERR}.get(self.color, TEXT)
        self.create_text(P(16), P(49), text=self.text, anchor="w", fill=col, font=FONT_NUM)


class PathBox(tk.Canvas):
    def __init__(self, master, path, command):
        super().__init__(master, height=P(40), bg=BG, highlightthickness=0, cursor="hand2")
        self.path, self.cmd, self.hover = path, command, False
        self.font = tkfont.Font(font=FONT_UI)
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Enter>", lambda e: self._h(True))
        self.bind("<Leave>", lambda e: self._h(False))
        self.bind("<Button-1>", lambda e: self.cmd())

    def _h(self, v):
        self.hover = v
        self.draw()

    def set(self, p):
        self.path = p
        self.draw()

    def refresh(self):
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        rrect(self, 1, 1, w - 1, h - 1, P(11), fill=mix(PANEL2, TEXT, .06) if self.hover else PANEL2,
              outline=ACCENT if self.hover else BORDER)
        x, y = P(14), h / 2
        self.create_polygon(x, y - P(6), x + P(7), y - P(6), x + P(9), y - P(3), x + P(17), y - P(3),
                            x + P(17), y + P(7), x, y + P(7), fill=ACCENT, outline="")
        t, maxw = self.path, w - P(60)
        if self.font.measure(t) > maxw:
            while len(t) > 4 and self.font.measure("…" + t) > maxw:
                t = t[1:]
            t = "…" + t
        self.create_text(x + P(28), y, text=t, anchor="w", fill=TEXT, font=FONT_UI)


class Dash(tk.Canvas):
    def __init__(self, master):
        super().__init__(master, height=P(160), bg=BG, highlightthickness=0)
        self.current, self.done, self.finished = -1, set(), False
        self.target, self.shown, self.indet, self.running = 0.0, 0.0, False, False
        self.status, self.detail, self.dirty = "Listo para empezar.", "", True
        self.bind("<Configure>", lambda e: setattr(self, "dirty", True))

    def refresh(self):
        self.dirty = True

    def reset(self):
        self.current, self.done, self.finished = -1, set(), False
        self.target = self.shown = 0.0
        self.indet = self.running = False
        self.status, self.detail, self.dirty = "Listo para empezar.", "", True

    def tick(self, now):
        moving = abs(self.target - self.shown) > 0.0005
        if moving:
            self.shown += (self.target - self.shown) * 0.16
            if abs(self.target - self.shown) < 0.0005:
                self.shown = self.target
        if self.dirty or moving or self.running:
            self.dirty = False
            self.draw(now)

    def draw(self, now):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 50:
            return
        rrect(self, 1, 1, w - 1, h - 1, P(16), fill=PANEL, outline=BORDER)

        n, m = len(ETAPAS), P(64)
        xs = [m + i * (w - 2 * m) / (n - 1) for i in range(n)]
        y, r = P(36), P(12)
        for i in range(n - 1):
            lit = self.finished or i in self.done
            self.create_line(xs[i] + r + P(8), y, xs[i + 1] - r - P(8), y,
                             fill=ACCENT if lit else BORDER, width=P(2))
        for i, x in enumerate(xs):
            done = self.finished or i in self.done
            active = i == self.current and not self.finished
            if done:
                self.create_oval(x - r, y - r, x + r, y + r, fill=ACCENT, outline="")
                self.create_line(x - P(5), y, x - P(1), y + P(4), x + P(6), y - P(5),
                                 fill=on_color(ACCENT), width=P(2))
            elif active:
                pulse = (math.sin(now * 4.2) + 1) / 2
                rr = r + P(2) + pulse * P(5)
                self.create_oval(x - rr, y - rr, x + rr, y + rr, outline=mix(ACCENT, PANEL, .45 + .4 * pulse),
                                 width=P(2))
                self.create_oval(x - r, y - r, x + r, y + r, fill=PANEL, outline=ACCENT, width=P(2))
                self.create_oval(x - P(4), y - P(4), x + P(4), y + P(4), fill=ACCENT, outline="")
            else:
                self.create_oval(x - r, y - r, x + r, y + r, fill=PANEL, outline=BORDER, width=P(2))
                self.create_text(x, y, text=str(i + 1), fill=MUTED, font=FONT_SM)
            self.create_text(x, y + P(28), text=ETAPAS[i], fill=TEXT if (done or active) else MUTED,
                             font=FONT_B if active else FONT_SM)

        x1, x2, by, bh = P(26), w - P(26), P(90), P(10)
        cy, rad = by + bh / 2, bh / 2
        self.create_line(x1 + rad, cy, x2 - rad, cy, fill=PANEL2 if TEMA == "oscuro" else BORDER,
                         width=bh, capstyle="round")
        fw = (x2 - x1) * max(0.0, min(1.0, self.shown))
        if self.indet and self.running:
            fw = max(fw, P(26))
        if fw > bh:
            fa, fb = x1 + rad, x1 + fw - rad
            self.create_line(fa, cy, fb, cy, fill=ACCENT, width=bh, capstyle="round")
            if self.running and fb - fa > P(10):
                band = P(60)
                pos = fa + ((now * 0.9) % 1.5 - 0.25) * (fb - fa + band) - band / 2
                a, b = max(fa, pos), min(fb, pos + band)
                if b - a > P(4):
                    self.create_line(a, cy, b, cy, fill=mix(ACCENT, "#FFFFFF", .45), width=bh - P(4),
                                     capstyle="round")

        pct = "100%" if self.finished else ("" if (self.indet and self.shown < .005) else f"{int(self.shown * 100)}%")
        self.create_text(x1, P(120), text=self.status, anchor="w", fill=TEXT, font=FONT_B)
        self.create_text(x2, P(120), text=pct, anchor="e", fill=ACC_TXT, font=FONT_B)
        self.create_text(x1, P(140), text=self.detail, anchor="w", fill=MUTED, font=FONT_SM)


class Preview(tk.Canvas):
    def __init__(self, master):
        super().__init__(master, bg=BG, highlightthickness=0)
        self.f, self.fb = tkfont.Font(font=FONT_ROW), tkfont.Font(font=FONT_ROWB)
        self.cache = {}
        self.filtro = ""
        self.reset()
        self.bind("<Configure>", lambda e: setattr(self, "dirty", True))

    def reset(self):
        self.rows = []
        self.titulo = "Inventario Electro Misiones"
        self.caption = "La vista previa aparece cuando empieza el escaneo."
        self.frac = None
        self.mode = "idle"
        self.dirty = True

    def set_filtro(self, query):
        self.filtro = query.strip().lower()
        self.dirty = True

    def show(self, rows, caption, frac=None, mode="live", titulo=None):
        self.rows, self.caption, self.frac, self.mode = rows, caption, frac, mode
        if titulo:
            self.titulo = titulo
        self.dirty = True

    def refresh(self):
        self.dirty = True

    def tick(self):
        if self.dirty:
            self.dirty = False
            self.draw()

    def _fit(self, t, maxw, font):
        key = (t, maxw, font is self.fb)
        r = self.cache.get(key)
        if r is None:
            if font.measure(t) <= maxw:
                r = t
            else:
                lo, hi = 0, len(t)
                while lo < hi:
                    mid = (lo + hi + 1) // 2
                    if font.measure(t[:mid] + "…") <= maxw:
                        lo = mid
                    else:
                        hi = mid - 1
                r = t[:lo] + "…"
            if len(self.cache) > 3000:
                self.cache.clear()
            self.cache[key] = r
        return r

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 120 or h < 120:
            return
        rrect(self, 1, 1, w - 1, h - 1, P(14), fill=PANEL, outline=BORDER)
        foot = P(48)
        pw = min(w - P(48), P(680))
        px, py = (w - pw) / 2, P(14)
        ph = h - py - foot
        sh = mix(PANEL, "#000000", .22 if TEMA == "oscuro" else .09)
        rrect(self, px + P(2), py + P(4), px + pw + P(2), py + ph + P(4), P(5), fill=sh, outline="")
        self.create_rectangle(px, py, px + pw, py + ph, fill=PAPEL, outline=PAPEL_LINEA)

        self.create_text(px + pw / 2, py + P(13), text=self.titulo, fill=PAPEL_TXT, font=FONT_ROWB)
        hy, rh, refw = py + P(26), P(17), pw * 0.22
        self.create_rectangle(px, hy, px + refw, hy + rh, fill=PAPEL_HEAD, outline=PAPEL_LINEA)
        self.create_rectangle(px + refw, hy, px + pw, hy + rh, fill=PAPEL_HEAD, outline=PAPEL_LINEA)
        self.create_text(px + P(6), hy + rh / 2, text="Referencia", anchor="w", fill=PAPEL_TXT, font=FONT_ROWB)
        self.create_text(px + refw + P(6), hy + rh / 2, text="Nombre del artículo", anchor="w",
                         fill=PAPEL_TXT, font=FONT_ROWB)

        n_fit = max(1, int((ph - P(26) - rh - P(6)) // rh))
        filas_mostrar = self.rows
        if self.filtro:
            filas_mostrar = [r for r in self.rows if self.filtro in (r[0] or "").lower() or self.filtro in (r[1] or "").lower()]

        if self.mode == "idle" or not filas_mostrar:
            anchos = (.62, .85, .48, .74, .9, .55, .7, .41, .8, .6)
            for k in range(n_fit):
                y = hy + rh * (k + 1)
                self.create_rectangle(px, y, px + refw, y + rh, fill=PAPEL, outline=PAPEL_LINEA)
                self.create_rectangle(px + refw, y, px + pw, y + rh, fill=PAPEL, outline=PAPEL_LINEA)
                self.create_rectangle(px + P(6), y + P(6), px + P(6) + refw * .5, y + rh - P(6),
                                      fill="#EEEEF1", outline="")
                bw = (pw - refw - P(14)) * anchos[k % len(anchos)]
                self.create_rectangle(px + refw + P(6), y + P(6), px + refw + P(6) + bw, y + rh - P(6),
                                      fill="#EEEEF1", outline="")
        else:
            vis = filas_mostrar[-n_fit:]
            for k, (cod, nom) in enumerate(vis):
                y = hy + rh * (k + 1)
                last = (k == len(vis) - 1) and self.mode in ("live", "export") and not self.filtro
                fill = mix(PAPEL, ACCENT, .17) if last else PAPEL
                self.create_rectangle(px, y, px + refw, y + rh, fill=fill, outline=PAPEL_LINEA)
                self.create_rectangle(px + refw, y, px + pw, y + rh, fill=fill, outline=PAPEL_LINEA)
                if last:
                    self.create_rectangle(px, y, px + P(3), y + rh, fill=ACCENT, outline="")
                self.create_text(px + P(7), y + rh / 2, text=self._fit(cod or "…", refw - P(12), self.f),
                                 anchor="w", fill=PAPEL_TXT, font=FONT_ROW)
                self.create_text(px + refw + P(6), y + rh / 2,
                                 text=self._fit(nom or "…", pw - refw - P(12), self.f),
                                 anchor="w", fill=PAPEL_TXT, font=FONT_ROW)

        caption_txt = self.caption
        if self.filtro:
            caption_txt = f"Filtrando: '{self.filtro}' — {len(filas_mostrar)} coincidencias encontradas"
        self.create_text(px, h - P(31), text=caption_txt, anchor="w", fill=MUTED, font=FONT_SM)

        if self.frac is not None and not self.filtro:
            bx1, bx2, by = px + P(4), px + pw - P(4), h - P(14)
            self.create_line(bx1, by, bx2, by, fill=PANEL2 if TEMA == "oscuro" else BORDER, width=P(6),
                             capstyle="round")
            if self.frac > 0.005:
                self.create_line(bx1, by, bx1 + (bx2 - bx1) * min(1, self.frac), by, fill=ACCENT,
                                 width=P(6), capstyle="round")


class Splash(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        W, H = P(460), P(270)
        sx, sy = master.winfo_screenwidth(), master.winfo_screenheight()
        self.geometry(f"{W}x{H}+{(sx - W) // 2}+{(sy - H) // 2}")
        self.configure(bg=BORDER)
        self.W, self.H = W - 2, H - 2
        self.c = tk.Canvas(self, width=self.W, height=self.H, bg=BG, highlightthickness=0)
        self.c.pack(padx=1, pady=1)
        self.t0, self.alive = time.time(), True
        self._anim()

    def _anim(self):
        if not self.alive:
            return
        t = time.time() - self.t0
        c, cx, cy = self.c, self.W / 2, P(96)
        c.delete("all")
        for k in range(2):
            ph = (t * 0.8 + k * 0.5) % 1.0
            r = P(37) + ph * P(32)
            c.create_oval(cx - r, cy - r, cx + r, cy + r, outline=mix(ACCENT, BG, .3 + .7 * ph), width=P(2))
        s = P(64)
        x0, y0 = cx - s / 2, cy - s / 2
        rrect(c, x0, y0, x0 + s, y0 + s, int(s * .28), fill=ACCENT, outline="")
        c.create_polygon([x0 + vx * s if i % 2 == 0 else y0 + vx * s
                          for p in BOLT for i, vx in enumerate(p)], fill=on_color(ACCENT), outline="")
        c.create_text(cx, P(170), text="Inventario Electro Misiones", fill=TEXT, font=("Segoe UI", 15, "bold"))
        c.create_text(cx, P(196), text="Cargando" + "." * (int(t * 3) % 4), fill=MUTED, font=FONT_SM)
        bx1, bx2, by = cx - P(90), cx + P(90), P(228)
        c.create_line(bx1, by, bx2, by, fill=PANEL2 if TEMA == "oscuro" else BORDER, width=P(6), capstyle="round")
        pos = ((t * 0.9) % 1.4) - 0.2
        a, b = bx1 + max(0, pos) * (bx2 - bx1), bx1 + min(1, pos + .35) * (bx2 - bx1)
        if b - a > P(6):
            c.create_line(a, by, b, by, fill=ACCENT, width=P(6), capstyle="round")
        self.after(33, self._anim)

    def cerrar(self):
        self.alive = False
        self.destroy()


class Ajustes(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.withdraw()
        self.title("Configuración")
        self.configure(bg=BG)
        self.resizable(False, False)
        self.transient(app)
        self.n = app.workers
        self.lock = app.running
        self.var = tk.StringVar(value=app.url)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=P(26), pady=P(22))
        tk.Label(body, text="Configuración", font=FONT_H, fg=TEXT, bg=BG).pack(anchor="w")

        self._sec(body, "APARIENCIA")
        r = tk.Frame(body, bg=BG)
        r.pack(fill="x", pady=P(4))
        tk.Label(r, text="Tema", font=FONT_UI, fg=TEXT, bg=BG).pack(side="left")
        self.seg = Seg(r, ["Oscuro", "Claro"], 0 if TEMA == "oscuro" else 1,
                       lambda i: app.set_tema("oscuro" if i == 0 else "claro"))
        self.seg.pack(side="right")

        self._sec(body, "CONEXIÓN")
        r = tk.Frame(body, bg=BG)
        r.pack(fill="x", pady=P(4))
        tk.Label(r, text="Conexiones simultáneas", font=FONT_UI, fg=TEXT, bg=BG).pack(side="left")
        self.b_plus = Btn(r, "+", lambda: self._w(1), w=34, h=34)
        self.b_plus.pack(side="right")
        self.lbl = tk.Label(r, text=str(self.n), font=FONT_B, fg=TEXT, bg=BG, width=3)
        self.lbl.pack(side="right")
        self.b_minus = Btn(r, "−", lambda: self._w(-1), w=34, h=34)
        self.b_minus.pack(side="right")
        tk.Label(body, text="Bajá este número si el sitio devuelve errores 429 / 403.", font=FONT_SM,
                 fg=MUTED, bg=BG).pack(anchor="w", pady=(0, P(10)))

        tk.Label(body, text="URL del sitio", font=FONT_UI, fg=TEXT, bg=BG).pack(anchor="w")
        r = tk.Frame(body, bg=BG)
        r.pack(fill="x", pady=(P(6), 0))
        ef = tk.Frame(r, bg=BORDER)
        ef.pack(side="left", fill="x", expand=True)
        inner = tk.Frame(ef, bg=PANEL2)
        inner.pack(fill="x", padx=1, pady=1)
        self.ent = tk.Entry(inner, textvariable=self.var, font=FONT_UI, bg=PANEL2, fg=TEXT,
                            insertbackground=TEXT, relief="flat", bd=0, highlightthickness=0,
                            disabledbackground=PANEL2, disabledforeground=MUTED)
        self.ent.pack(fill="x", padx=P(10), pady=P(9))
        self.b_probar = Btn(r, "Probar", self._probar, w=90, h=38)
        self.b_probar.pack(side="left", padx=(P(10), 0))
        self.status = tk.Label(body, text="", font=FONT_SM, fg=MUTED, bg=BG, anchor="w", justify="left",
                               wraplength=P(440))
        self.status.pack(fill="x", pady=(P(6), 0))

        if self.lock:
            self.ent.configure(state="disabled")
            for b in (self.b_plus, self.b_minus, self.b_probar):
                b.set_enabled(False)
            self.status.configure(text="Hay una corrida en curso: la conexión se puede cambiar cuando termine.",
                                  fg=WARN)

        foot = tk.Frame(body, bg=BG)
        foot.pack(fill="x", pady=(P(22), 0))
        self.b_ok = Btn(foot, "Guardar", self._guardar, primary=True, w=120, h=40)
        self.b_ok.pack(side="right")
        self.b_rst = Btn(foot, "Restablecer", self._reset, w=120, h=40)
        self.b_rst.pack(side="right", padx=P(10))
        if self.lock:
            self.b_rst.set_enabled(False)

        self.update_idletasks()
        W, H = self.winfo_reqwidth(), self.winfo_reqheight()
        W = max(W, P(520))
        x = app.winfo_rootx() + (app.winfo_width() - W) // 2
        y = app.winfo_rooty() + (app.winfo_height() - H) // 3
        self.geometry(f"{W}x{H}+{max(0, x)}+{max(0, y)}")
        self.deiconify()
        self.after(80, lambda: app._titlebar(self))
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.cerrar)

    def _sec(self, parent, txt):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", pady=(P(18), P(6)))
        tk.Label(f, text=txt, font=FONT_CAP, fg=MUTED, bg=BG).pack(side="left")
        tk.Frame(f, bg=BORDER, height=1).pack(side="left", fill="x", expand=True, padx=(P(10), 0), pady=P(1))

    def _w(self, d):
        self.n = max(1, min(16, self.n + d))
        self.lbl.configure(text=str(self.n))

    def _reset(self):
        self.n = 8
        self.lbl.configure(text="8")
        self.var.set(DEFAULT_URL)
        self.status.configure(text="", fg=MUTED)

    def _probar(self):
        url = normalizar_url(self.var.get())
        if not url:
            self.status.configure(text="URL inválida. Ejemplo: https://www.sitio.com.ar", fg=ERR)
            return
        self.status.configure(text="Probando conexión…", fg=MUTED)
        self.b_probar.set_enabled(False)

        def trabajo():
            r = core.get(url)
            if r is None:
                self.app.q.put(("probe", False, "No se pudo conectar. Revisá la URL y tu internet."))
            elif r.status_code != 200:
                self.app.q.put(("probe", False, f"El sitio respondió HTTP {r.status_code}."))
            elif "prestashop" in r.text.lower():
                self.app.q.put(("probe", True, "Sitio accesible · PrestaShop detectado."))
            else:
                self.app.q.put(("probe", None, "Sitio accesible, pero no se detectó PrestaShop."))
        threading.Thread(target=trabajo, daemon=True).start()

    def set_probe(self, ok, txt):
        self.b_probar.set_enabled(not self.lock)
        self.status.configure(text=txt, fg=OK if ok else (WARN if ok is None else ERR))

    def _guardar(self):
        if not self.lock:
            url = normalizar_url(self.var.get())
            if not url:
                self.status.configure(text="URL inválida. Ejemplo: https://www.sitio.com.ar", fg=ERR)
                return
            self.app.aplicar_config(self.n, url)
        self.cerrar()

    def cerrar(self):
        self.grab_release()
        self.app.ajustes = None
        self.destroy()


class Cancelado(Exception):
    pass


def correr(fn, items, workers, on_result, q, idx, stop, prods, reciente):
    total = len(items)
    if not total:
        return
    ex = ThreadPoolExecutor(max_workers=workers)
    futs = {ex.submit(fn, it): it for it in items}
    hechos, ultimo = 0, 0.0
    try:
        for fut in as_completed(futs):
            if stop.is_set():
                raise Cancelado()
            hechos += 1
            try:
                on_result(futs[fut], fut.result())
            except Exception as e:
                core.ERRORES.append(f"{type(e).__name__}: {e}")
            ahora = time.time()
            if ahora - ultimo > 0.15 or hechos == total:
                ultimo = ahora
                q.put(("prog", idx, hechos, total, len(prods), len(core.ERRORES), list(reciente)))
    finally:
        ex.shutdown(wait=False, cancel_futures=True)


def pipeline(carpeta, workers, reiniciar, q, stop):
    prods, reciente = {}, deque(maxlen=48)

    def log(nivel, txt):
        q.put(("log", nivel, txt))

    try:
        core.ERRORES.clear()
        core.configurar_sesion(workers)
        core.PROGRESO = os.path.join(carpeta, "progreso_inventario.json")
        ruta_historico = os.path.join(carpeta, "inventario_anterior.json")
        anterior = core.cargar(ruta_historico)

        if reiniciar and os.path.exists(core.PROGRESO):
            os.remove(core.PROGRESO)
        prods = core.cargar(core.PROGRESO)
        if prods:
            log("info", f"Retomando con {len(prods)} productos guardados")

        q.put(("paso", 0, "Detectando categorías del sitio…", True))
        cats = core.descubrir_categorias()
        if len(cats) <= 1:
            raise RuntimeError("No pude leer el menú del sitio. ¿Hay conexión o la URL es correcta?")
        log("ok", f"{len(cats)} categorías detectadas")
        if stop.is_set():
            raise Cancelado()

        def on_cat(it, res):
            for pid, d in res.items():
                if pid not in prods:
                    reciente.append((d["codigo"], d["nombre"]))
            core.fusionar(prods, res)

        q.put(("paso", 1, "Escaneando listados de productos…", False))
        correr(core.escanear_categoria, list(cats.values()), workers, on_cat, q, 1, stop, prods, reciente)
        core.guardar(prods, core.PROGRESO)
        log("ok", f"{len(prods)} productos únicos encontrados")

        q.put(("paso", 2, "Buscando URLs extra en el sitemap…", True))
        extra = core.urls_desde_sitemap()
        core.fusionar(prods, {pid: {"url": u, "nombre": "", "codigo": ""} for pid, u in extra.items()})
        core.guardar(prods, core.PROGRESO)
        pend = [(pid, d["url"]) for pid, d in prods.items() if not d.get("codigo")]
        if pend:
            log("info", f"{len(pend)} productos sin referencia en el listado: leyendo fichas")
            q.put(("paso", 2, "Leyendo fichas individuales…", False))
            n = {"v": 0}

            def on_ficha(it, res):
                if res:
                    core.fusionar(prods, {it[0]: {"url": it[1], **res}})
                    reciente.append((res["codigo"], res["nombre"] or prods[it[0]]["nombre"]))
                n["v"] += 1
                if n["v"] % 200 == 0:
                    core.guardar(prods, core.PROGRESO)

            correr(lambda it: core.extraer_ficha(it[1]), pend, workers, on_ficha, q, 2, stop, prods, reciente)
            core.guardar(prods, core.PROGRESO)
        else:
            log("ok", "Todas las referencias vinieron en los listados")

        if stop.is_set():
            raise Cancelado()
        for d in prods.values():
            if not d["nombre"]:
                d["nombre"] = os.path.basename(urlparse(d["url"]).path).split("-", 1)[-1] \
                    .replace(".html", "").replace("_", " ")
        lista = sorted(prods.values(), key=lambda d: d["nombre"].lower())
        sin_ref = sum(1 for d in lista if not d["codigo"])
        total = len(lista)
        pdf = os.path.join(carpeta, "inventario_electromisiones.pdf")

        q.put(("paso", 3, "Generando el PDF…", False))
        q.put(("export", total, -(-total // FILAS_PAGINA)))

        def cb(i, tot, pagina):
            ventana = [(p["codigo"] or "S/REF", p["nombre"]) for p in lista[max(0, i - 48):i]]
            q.put(("pdf", i, tot, pagina, ventana))

        paginas = core.generar_pdf(lista, pdf, progreso=cb)
        core.generar_csv(lista, os.path.join(carpeta, "inventario_electromisiones.csv"))

        diff = core.calcular_diferencias(anterior, prods)
        core.guardar(prods, ruta_historico)

        todas_las_filas = [(p["codigo"] or "S/REF", p["nombre"]) for p in lista]
        q.put(("fin", total, sin_ref, len(core.ERRORES), pdf, list(core.ERRORES[-3:]), paginas, todas_las_filas, diff))

    except Cancelado:
        try:
            core.guardar(prods, core.PROGRESO)
        except Exception:
            pass
        q.put(("cancelado", len(prods)))
    except Exception as e:
        q.put(("error", f"{type(e).__name__}: {e}"))


class App(tk.Tk):
    def __init__(self):
        global K
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        super().__init__()
        K = self.winfo_fpixels("1i") / 96.0
        self.cfg = cargar_cfg()
        aplicar_paleta("claro" if self.cfg.get("tema") == "claro" else "oscuro")
        self.configure(bg=BG)
        self.withdraw()
        try:
            self.iconphoto(True, hacer_icono())
        except Exception:
            pass
        self.splash = Splash(self)
        self.update()
        self.t_splash = time.time()
        threading.Thread(target=_importar_core, daemon=True).start()

        self.workers = int(self.cfg.get("workers", 8))
        self.url = normalizar_url(self.cfg.get("url")) or DEFAULT_URL
        self.q, self.stop = queue.Queue(), threading.Event()
        self.running, self.t0, self.samples, self.last_pdf = False, 0.0, deque(maxlen=40), ""
        self.ajustes = None
        self.export_total, self.export_pages = 0, 0
        self.after(40, self._esperar)

    def _esperar(self):
        if core is None or time.time() - self.t_splash < 1.3:
            self.after(40, self._esperar)
            return
        self.title("Inventario Electro Misiones")
        self.geometry(f"{P(850)}x{P(950)}")
        self.minsize(P(760), P(820))
        self._estilos()
        self._build()
        self.attributes("-alpha", 0.0)
        self.deiconify()
        self.update()
        self._titlebar(self)
        self.splash.cerrar()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self._fade(0.0)
        self.after(33, self._tick)
        self.after(50, self._poll)

    def _fade(self, a):
        a = min(1.0, a + 0.12)
        self.attributes("-alpha", a)
        if a < 1.0:
            self.after(16, lambda: self._fade(a))

    def _estilos(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.layout("Dark.Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {
            "sticky": "ns", "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        st.configure("Dark.Vertical.TScrollbar", background=BORDER, troughcolor=PANEL, bordercolor=PANEL,
                     lightcolor=BORDER, darkcolor=BORDER, relief="flat", width=P(8))
        st.map("Dark.Vertical.TScrollbar", background=[("active", MUTED)])

    def _titlebar(self, win):
        try:
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
            v = ctypes.c_int(1 if TEMA == "oscuro" else 0)
            for attr in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), 4)
            r, g, b = hex_rgb(BG)
            col = ctypes.c_int(r | (g << 8) | (b << 16))
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 35, ctypes.byref(col), 4)
        except Exception:
            pass

    def _build(self):
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True, padx=P(24), pady=P(20))

        hdr = tk.Frame(root, bg=BG)
        hdr.pack(fill="x")
        Logo(hdr).pack(side="left")
        tf = tk.Frame(hdr, bg=BG)
        tf.pack(side="left", padx=P(14))
        tk.Label(tf, text="Inventario Electro Misiones", font=FONT_H, fg=TEXT, bg=BG).pack(anchor="w")
        tk.Label(tf, text="Catálogo web  →  PDF y CSV con referencias", font=FONT_SM, fg=MUTED, bg=BG).pack(anchor="w")
        self.b_gear = IconBtn(hdr, "gear", self._abrir_ajustes)
        self.b_gear.pack(side="right")
        self.b_tema = IconBtn(hdr, "tema", lambda: self.set_tema("claro" if TEMA == "oscuro" else "oscuro"))
        self.b_tema.pack(side="right", padx=(0, P(8)))

        cards = tk.Frame(root, bg=BG)
        cards.pack(fill="x", pady=(P(18), 0))
        self.cards = {}
        for i, (k, t, v) in enumerate([("prod", "PRODUCTOS", "0"), ("vel", "VELOCIDAD", "—"),
                                       ("time", "TIEMPO", "0:00"), ("err", "ERRORES", "0")]):
            cards.columnconfigure(i, weight=1, uniform="c")
            c = Card(cards, t)
            c.text = v
            c.grid(row=0, column=i, sticky="ew", padx=(0, P(10)) if i < 3 else 0)
            self.cards[k] = c

        self.dash = Dash(root)
        self.dash.pack(fill="x", pady=(P(12), 0))

        row = tk.Frame(root, bg=BG)
        row.pack(fill="x", pady=(P(14), 0))
        tk.Label(row, text="Guardar en", font=FONT_SM, fg=MUTED, bg=BG).pack(side="left", padx=(0, P(10)))
        self.pathbox = PathBox(row, self.cfg.get("carpeta") or self._carpeta_default(), self._elegir)
        self.pathbox.pack(side="left", fill="x", expand=True)

        opt = tk.Frame(root, bg=BG)
        opt.pack(fill="x", pady=(P(12), 0))
        self.toggle = Toggle(opt, self.cfg.get("reiniciar", True))
        self.toggle.pack(side="left")
        tk.Label(opt, text="Empezar de cero", font=FONT_UI, fg=TEXT, bg=BG).pack(side="left", padx=P(10))
        tk.Label(opt, text="(si lo apagás, retoma el progreso guardado)", font=FONT_SM, fg=MUTED, bg=BG).pack(side="left")

        act = tk.Frame(root, bg=BG)
        act.pack(fill="x", pady=(P(14), 0))
        self.b_start = Btn(act, "Generar inventario", self._iniciar, primary=True, w=210, h=44)
        self.b_start.pack(side="left")
        self.b_cancel = Btn(act, "Cancelar", self._cancelar, w=110, h=44)
        self.b_cancel.pack(side="left", padx=P(10))
        self.b_cancel.set_enabled(False)
        self.b_folder = Btn(act, "Abrir carpeta", self._abrir_carpeta, w=130, h=44)
        self.b_folder.pack(side="right")
        self.b_pdf = Btn(act, "Abrir PDF", self._abrir_pdf, w=110, h=44)
        self.b_pdf.pack(side="right", padx=P(10))
        self.b_pdf.set_enabled(False)

        trow = tk.Frame(root, bg=BG)
        trow.pack(fill="x", pady=(P(16), P(8)))
        self.tabs = Seg(trow, ["Vista previa del PDF", "Registro"], 0, self._tab, w=172)
        self.tabs.pack(side="left")

        # Buscador instantáneo integrado
        self.f_search = tk.Frame(trow, bg=BORDER)
        self.f_search.pack(side="right")
        inner_s = tk.Frame(self.f_search, bg=PANEL2)
        inner_s.pack(padx=1, pady=1)
        self.var_search = tk.StringVar()
        self.var_search.trace_add("write", lambda *_: self.preview.set_filtro(self.var_search.get()))
        self.ent_search = tk.Entry(inner_s, textvariable=self.var_search, font=FONT_SM, bg=PANEL2, fg=TEXT,
                                   insertbackground=TEXT, relief="flat", bd=0, highlightthickness=0, width=24)
        self.ent_search.pack(side="left", padx=P(8), pady=P(4))
        tk.Label(inner_s, text="🔍", bg=PANEL2, fg=MUTED, font=FONT_SM).pack(side="right", padx=(0, P(6)))

        box = tk.Frame(root, bg=BG)
        box.pack(fill="both", expand=True)
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        self.f_prev = tk.Frame(box, bg=BG)
        self.f_prev.grid(row=0, column=0, sticky="nsew")
        self.preview = Preview(self.f_prev)
        self.preview.pack(fill="both", expand=True)

        self.f_log = tk.Frame(box, bg=BORDER)
        self.f_log.grid(row=0, column=0, sticky="nsew")
        inner = tk.Frame(self.f_log, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.txt = tk.Text(inner, bg=PANEL, fg=TEXT, font=FONT_MONO, bd=0, highlightthickness=0, wrap="word",
                           padx=P(12), pady=P(10), state="disabled", insertwidth=0, height=6, spacing1=P(2))
        sb = ttk.Scrollbar(inner, style="Dark.Vertical.TScrollbar", command=self.txt.yview)
        self.txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt.pack(side="left", fill="both", expand=True)
        self._tags()
        self.f_prev.tkraise()
        self._log("info", "Listo. Elegí la carpeta y tocá «Generar inventario».")

    def _tags(self):
        for tag, col in (("ts", MUTED), ("info", TEXT), ("ok", OK), ("warn", WARN), ("err", ERR)):
            self.txt.tag_configure(tag, foreground=col)

    def _tab(self, i):
        (self.f_prev if i == 0 else self.f_log).tkraise()

    def _carpeta_default(self):
        for c in ("Desktop", "Escritorio", "Documents"):
            p = os.path.join(os.path.expanduser("~"), c)
            if os.path.isdir(p):
                return p
        return os.path.expanduser("~")

    def _log(self, nivel, txt):
        self.txt.configure(state="normal")
        self.txt.insert("end", time.strftime("%H:%M:%S  "), "ts")
        self.txt.insert("end", txt + "\n", nivel)
        self.txt.see("end")
        self.txt.configure(state="disabled")

    def _recolor(self, w, m):
        for opt in ("bg", "background", "fg", "foreground", "highlightbackground", "insertbackground",
                    "disabledbackground", "disabledforeground", "activebackground"):
            try:
                v = str(w.cget(opt)).lower()
            except tk.TclError:
                continue
            if v in m:
                try:
                    w.configure(**{opt: m[v]})
                except tk.TclError:
                    pass
        if hasattr(w, "refresh"):
            w.refresh()
        for c in w.winfo_children():
            self._recolor(c, m)

    def set_tema(self, nombre):
        if nombre == TEMA:
            return
        m = mapa_colores(TEMA, nombre)
        aplicar_paleta(nombre)
        raices = [self] + ([self.ajustes] if self.ajustes is not None else [])
        for r in raices:
            self._recolor(r, m)
        self._estilos()
        self._tags()
        if self.ajustes is not None:
            self.ajustes.seg.sel = 0 if nombre == "oscuro" else 1
            self.ajustes.seg.draw()
        for r in raices:
            self._titlebar(r)
        self._guardar_cfg()

    def aplicar_config(self, n, url):
        self.workers, self.url = n, url
        self._guardar_cfg()

    def _guardar_cfg(self):
        guardar_cfg({"tema": TEMA, "carpeta": self.pathbox.path, "workers": self.workers,
                     "reiniciar": self.toggle.value, "url": self.url})

    def _abrir_ajustes(self):
        if self.ajustes is None:
            self.ajustes = Ajustes(self)

    def _elegir(self):
        if self.running:
            return
        d = filedialog.askdirectory(initialdir=self.pathbox.path)
        if d:
            self.pathbox.set(os.path.normpath(d))

    def _abrir(self, p):
        try:
            os.startfile(p)
        except (AttributeError, OSError):
            pass

    def _abrir_carpeta(self):
        self._abrir(self.pathbox.path)

    def _abrir_pdf(self):
        if self.last_pdf and os.path.exists(self.last_pdf):
            self._abrir(self.last_pdf)

    def _estado_botones(self, corriendo):
        self.running = corriendo
        self.b_start.set_enabled(not corriendo)
        self.b_cancel.set_enabled(corriendo)
        self.b_pdf.set_enabled(False if corriendo else bool(self.last_pdf))

    def _iniciar(self):
        carpeta = self.pathbox.path
        if not os.path.isdir(carpeta):
            messagebox.showerror("Carpeta inválida", "Elegí una carpeta que exista.")
            return
        core.BASE = self.url
        core.DOMINIO = urlparse(self.url).netloc.lower().replace("www.", "")
        self._guardar_cfg()
        self.stop.clear()
        self.last_pdf = ""
        self.samples.clear()
        self.dash.reset()
        self.dash.running = True
        self.dash.status = "Iniciando…"
        for c in self.cards.values():
            c.reset()
        self.cards["vel"].reset("—")
        self.cards["time"].reset("0:00")
        self.var_search.set("")
        self.preview.reset()
        self.preview.show([], "Esperando los primeros productos…", mode="idle")
        self.t0 = time.time()
        self._estado_botones(True)
        self._log("info", f"Inicio · {self.workers} conexiones · {self.url}")
        threading.Thread(target=pipeline, daemon=True,
                         args=(carpeta, self.workers, self.toggle.value, self.q, self.stop)).start()

    def _cancelar(self):
        self.stop.set()
        self.dash.status = "Cancelando…"
        self.b_cancel.set_enabled(False)

    def _cerrar(self):
        self.stop.set()
        self._guardar_cfg()
        os._exit(0)

    def _tick(self):
        now = time.time()
        self.dash.tick(now)
        self.preview.tick()
        for c in self.cards.values():
            c.tick()
        if self.running:
            self.cards["time"].set_text(fmt_t(now - self.t0))
        self.after(33, self._tick)

    def _poll(self):
        try:
            while True:
                self._msg(self.q.get_nowait())
        except queue.Empty:
            pass
        self.after(50, self._poll)

    def _msg(self, m):
        k, d = m[0], self.dash
        if k == "log":
            self._log(m[1], m[2])
        elif k == "probe":
            if self.ajustes is not None:
                self.ajustes.set_probe(m[1], m[2])
        elif k == "paso":
            _, i, txt, indet = m
            d.current, d.done = i, set(range(i))
            d.indet, d.status, d.detail = indet, txt, ""
            d.target = max(d.target, PESOS[i][0])
            self.samples.clear()
        elif k == "prog":
            _, i, hechos, total, prods, errs, rows = m
            a, b = PESOS[i]
            d.indet = False
            d.target = a + (b - a) * hechos / total
            now = time.time()
            self.samples.append((now, hechos))
            rate = 0.0
            if len(self.samples) > 1:
                t1, h1 = self.samples[0]
                rate = (hechos - h1) / max(now - t1, 0.001)
            unidad = "categorías" if i == 1 else "fichas"
            d.status = f"{ETAPAS[i]}  ·  {fmt_n(hechos)} / {fmt_n(total)} {unidad}"
            d.detail = f"{rate:.1f} {unidad}/s" + (
                f"  ·  ~{fmt_t((total - hechos) / rate)} restante" if rate > 0.05 else "")
            self.cards["prod"].set_number(prods)
            self.cards["vel"].set_text(f"{rate:.1f}/s")
            self.cards["err"].set_text(fmt_n(errs), "err" if errs else None)
            self.preview.show(rows, f"En vivo · {fmt_n(prods)} productos encontrados", mode="live")
        elif k == "export":
            _, total, pages = m
            self.export_total, self.export_pages = total, pages
            self.cards["prod"].set_number(total)
            self.cards["vel"].set_text("—")
            self.preview.show([], f"Preparando {fmt_n(total)} artículos…", frac=0.0, mode="export",
                              titulo=f"Inventario Electro Misiones - {fmt_n(total)} artículos")
            d.indet = False
            d.detail = f"~{fmt_n(pages)} páginas"
        elif k == "pdf":
            _, i, tot, pagina, rows = m
            d.indet = False
            d.target = PESOS[3][0] + (PESOS[3][1] - PESOS[3][0]) * 0.92 * i / tot
            d.status = f"Exportar  ·  página {fmt_n(pagina)} de ~{fmt_n(self.export_pages)}"
            d.detail = f"{fmt_n(i)} / {fmt_n(tot)} artículos escritos"
            self.preview.show(rows, f"Escribiendo el PDF · página {fmt_n(pagina)} de ~{fmt_n(self.export_pages)}",
                              frac=i / tot, mode="export")
        elif k == "fin":
            _, n, sin_ref, errs, pdf, ult, paginas, todas_las_filas, diff = m
            seg = time.time() - self.t0
            self.last_pdf = pdf
            d.finished, d.running, d.indet, d.target, d.current = True, False, False, 1.0, -1
            d.status = f"Listo  ·  {fmt_n(n)} artículos en {fmt_t(seg)}"

            if diff.get("hay_anterior"):
                d.detail = (f"{fmt_n(paginas)} págs · Cambios vs corrida anterior: "
                            f"+{diff['nuevos']} nuevos, -{diff['bajas']} bajas, ~{diff['modificados']} editados")
                self._log("info", f"Comparativa con anterior: +{diff['nuevos']} altas, "
                                  f"-{diff['bajas']} bajas, {diff['modificados']} modificados.")
            else:
                d.detail = f"{fmt_n(paginas)} páginas · PDF y CSV guardados en la carpeta elegida"

            self.cards["prod"].set_number(n)
            self.cards["vel"].set_text("—")
            self.cards["time"].set_text(fmt_t(seg), "ok")
            self.preview.show(todas_las_filas, f"PDF listo · {fmt_n(paginas)} páginas (podés buscar arriba a la derecha)",
                              frac=1.0, mode="done", titulo=f"Inventario Electro Misiones - {fmt_n(n)} artículos")
            self._log("ok", f"Listo: {fmt_n(n)} artículos, {fmt_n(paginas)} páginas en {fmt_t(seg)}")
            if sin_ref:
                self._log("warn", f"{sin_ref} artículos sin referencia (salen como S/REF en el PDF)")
            if errs:
                self._log("warn", f"{errs} errores de red. Últimos: {ult}")
            self._estado_botones(False)
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception:
                pass
        elif k == "cancelado":
            d.running, d.indet, d.current = False, False, -1
            d.status = "Cancelado"
            d.detail = f"Progreso guardado ({fmt_n(m[1])} productos)."
            self.preview.caption = "Cancelado."
            self.preview.dirty = True
            self._log("warn", f"Cancelado. Progreso guardado ({m[1]} productos).")
            self._estado_botones(False)
        elif k == "error":
            d.running, d.indet, d.current = False, False, -1
            d.status, d.detail = "Error", m[1]
            self._log("err", m[1])
            self._estado_botones(False)
            messagebox.showerror("Error", m[1])
        d.dirty = True


if __name__ == "__main__":
    App().mainloop()