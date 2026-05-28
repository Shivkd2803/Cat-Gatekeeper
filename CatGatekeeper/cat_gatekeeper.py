import sys, threading, time, urllib.request, random
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QSpinBox,
    QVBoxLayout, QHBoxLayout, QFrame, QProgressBar, QDesktopWidget,
    QScrollArea, QSizePolicy, QStackedWidget
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, QRect
from PyQt5.QtGui import QFont, QPainter, QPen, QColor, QPixmap

try:
    import win32gui, win32process, win32con
    import psutil
    WIN32 = True
except ImportError:
    WIN32 = False

# ── Constants ─────────────────────────────────────────────────────────────────
ORANGE  = "#e8813a"
D_ORANGE= "#d07030"
BG      = "#141414"
SURFACE = "#1e1e1e"
BORDER  = "#2a2a2a"
WHITE   = "#ffffff"
GRAY    = "#888888"
DIM     = "#555555"
GREEN   = "#3ddc84"

CAT_URLS = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Cat_November_2010-1a.jpg/1280px-Cat_November_2010-1a.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bb/Kittyply_edit1.jpg/1280px-Kittyply_edit1.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/68/Orange_tabby_cat_sitting_on_fallen_leaves-Hisashi-01A.jpg/1280px-Orange_tabby_cat_sitting_on_fallen_leaves-Hisashi-01A.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/1280px-Cat03.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Siam_lilacpoint.jpg/1280px-Siam_lilacpoint.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Sleeping_cat_on_her_back.jpg/1280px-Sleeping_cat_on_her_back.jpg",
]
BREAK_MSGS = [
    "Step away — break time!",
    "Rest your eyes",
    "Stretch and breathe",
    "Get some water!",
    "The cat demands rest",
]

# ── Windows helpers ───────────────────────────────────────────────────────────

# Known apps that use multiple processes — map display name -> exe to watch
KNOWN_APPS = {
    "spotify.exe":          "Spotify",
    "code.exe":             "Visual Studio Code",
    "chrome.exe":           "Google Chrome",
    "firefox.exe":          "Mozilla Firefox",
    "msedge.exe":           "Microsoft Edge",
    "opera.exe":            "Opera",
    "brave.exe":            "Brave Browser",
    "notepad.exe":          "Notepad",
    "notepad++.exe":        "Notepad++",
    "vlc.exe":              "VLC",
    "discord.exe":          "Discord",
    "slack.exe":            "Slack",
    "telegram.exe":         "Telegram",
    "whatsapp.exe":         "WhatsApp",
    "teams.exe":            "Microsoft Teams",
    "zoom.exe":             "Zoom",
    "obs64.exe":            "OBS Studio",
    "obs32.exe":            "OBS Studio",
    "davinci resolve.exe":  "DaVinci Resolve",
    "resolve.exe":          "DaVinci Resolve",
    "openoffice.exe":       "OpenOffice",
    "soffice.exe":          "LibreOffice / OpenOffice",
    "winrar.exe":           "WinRAR",
    "explorer.exe":         "File Explorer",
    "wordpad.exe":          "WordPad",
    "mspaint.exe":          "Paint",
    "taskmgr.exe":          "Task Manager",
}

def get_running_apps():
    if not WIN32:
        return [
            {"exe": "chrome.exe",    "title": "Google Chrome",      "pid": 1},
            {"exe": "code.exe",      "title": "Visual Studio Code", "pid": 2},
            {"exe": "notepad++.exe", "title": "Notepad++",          "pid": 3},
            {"exe": "vlc.exe",       "title": "VLC Media Player",   "pid": 4},
            {"exe": "firefox.exe",   "title": "Mozilla Firefox",    "pid": 5},
            {"exe": "spotify.exe",   "title": "Spotify",            "pid": 6},
            {"exe": "discord.exe",   "title": "Discord",            "pid": 7},
            {"exe": "slack.exe",     "title": "Slack",              "pid": 8},
        ]

    found_exes = {}   # exe.lower() -> {"exe","title","pid"}
    skip = {"python.exe","python3.exe","pythonw.exe","catgatekeeper.exe",
            "conhost.exe","svchost.exe","csrss.exe","dwm.exe","wininit.exe",
            "services.exe","lsass.exe","smss.exe","fontdrvhost.exe",
            "sihost.exe","ctfmon.exe","searchhost.exe","runtimebroker.exe",
            "applicationframehost.exe","systemsettings.exe","textinputhost.exe",
            "shellexperiencehost.exe","startmenuexperiencehost.exe"}

    # Pass 1: visible top-level windows with titles
    def cb(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd): return
        title = win32gui.GetWindowText(hwnd)
        if not title or len(title) < 2: return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc  = psutil.Process(pid)
            exe   = proc.name()
            key   = exe.lower()
            if key in skip: return
            if key not in found_exes:
                display = KNOWN_APPS.get(key, title[:40])
                found_exes[key] = {"exe": exe, "title": display, "pid": pid}
        except: pass
    win32gui.EnumWindows(cb, None)

    # Pass 2: scan ALL running processes for known apps not caught by window enum
    # (Spotify, VSCode helpers, etc. often have no direct top-level window)
    try:
        for proc in psutil.process_iter(["pid","name"]):
            try:
                key = proc.info["name"].lower()
                if key in KNOWN_APPS and key not in found_exes and key not in skip:
                    found_exes[key] = {
                        "exe":   proc.info["name"],
                        "title": KNOWN_APPS[key],
                        "pid":   proc.info["pid"],
                    }
            except: pass
    except: pass

    return sorted(found_exes.values(), key=lambda x: x["title"].lower())

def get_foreground_exe():
    """Return the exe name of the currently focused window, or '' on failure."""
    if not WIN32:
        return ""
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return psutil.Process(pid).name().lower()
    except:
        return ""

def is_any_app_active(exe_list):
    """Return True if any of the given exe names is the current foreground window."""
    fg = get_foreground_exe()
    return any(fg == e.lower() for e in exe_list)

def get_window_rect(exe_name):
    if not WIN32:
        s = QDesktopWidget().availableGeometry()
        return QRect(s.x()+100, s.y()+100, s.width()-200, s.height()-200)

    # Collect all pids for this exe (handles multi-process apps like Spotify, VSCode)
    target_pids = set()
    try:
        for proc in psutil.process_iter(["pid","name"]):
            if proc.info["name"].lower() == exe_name.lower():
                target_pids.add(proc.info["pid"])
    except: pass

    best = None   # pick the largest visible non-minimized window
    def cb(hwnd, _):
        nonlocal best
        if not win32gui.IsWindowVisible(hwnd): return
        # Skip minimized windows
        if win32gui.IsIconic(hwnd): return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid not in target_pids: return
            l, t, r, b = win32gui.GetWindowRect(hwnd)
            w, h = r - l, b - t
            if w < 50 or h < 50: return
            if best is None or (w * h) > (best.width() * best.height()):
                best = QRect(l, t, w, h)
        except: pass
    win32gui.EnumWindows(cb, None)
    return best

# ── Cat loader ────────────────────────────────────────────────────────────────

class CatLoader(QObject):
    loaded = pyqtSignal(QPixmap)
    def __init__(self, url): super().__init__(); self.url = url
    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r: data = r.read()
            pix = QPixmap(); pix.loadFromData(data); self.loaded.emit(pix)
        except: self.loaded.emit(QPixmap())

# ── Ring widget ───────────────────────────────────────────────────────────────

class RingTimer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(160, 160)
        self._pct = 1.0; self._label = "WORK"; self._time_str = "25:00"

    def set_state(self, pct, label, time_str):
        self._pct = pct; self._label = label; self._time_str = time_str; self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        cx = cy = 80; r = 66
        p.setPen(QPen(QColor("#222"), 7, Qt.SolidLine, Qt.RoundCap))
        p.drawEllipse(cx-r, cy-r, r*2, r*2)
        if self._pct > 0:
            p.setPen(QPen(QColor(ORANGE), 7, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(cx-r, cy-r, r*2, r*2, 90*16, int(-self._pct*360*16))
        p.setPen(QColor(DIM)); p.setFont(QFont("Segoe UI", 8))
        p.drawText(0, 54, 160, 20, Qt.AlignCenter, self._label)
        p.setPen(QColor(WHITE)); p.setFont(QFont("Segoe UI", 24, QFont.Bold))
        p.drawText(0, 72, 160, 46, Qt.AlignCenter, self._time_str)
        p.end()

# ── App card (shown in picker) ────────────────────────────────────────────────

class AppCard(QWidget):
    selected = pyqtSignal(dict)   # emits app info dict

    def __init__(self, app_info, parent=None):
        super().__init__(parent)
        self.app = app_info
        self.setFixedHeight(56)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"""
            AppCard {{ background:{SURFACE}; border-radius:10px; border:1.5px solid {BORDER}; }}
            AppCard:hover {{ border:1.5px solid {ORANGE}; background:#222; }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 0, 14, 0)

        # Icon letter
        icon = QLabel(app_info["exe"][0].upper())
        icon.setFixedSize(34, 34)
        icon.setAlignment(Qt.AlignCenter)
        icon.setFont(QFont("Segoe UI", 14, QFont.Bold))
        icon.setStyleSheet(f"background:{BORDER};border-radius:8px;color:{ORANGE};")
        lay.addWidget(icon)
        lay.addSpacing(10)

        col = QVBoxLayout(); col.setSpacing(2)
        name = QLabel(app_info["exe"])
        name.setFont(QFont("Segoe UI", 10, QFont.Medium))
        name.setStyleSheet(f"color:{WHITE};")
        title = QLabel(app_info["title"][:40] + ("…" if len(app_info["title"])>40 else ""))
        title.setFont(QFont("Segoe UI", 8))
        title.setStyleSheet(f"color:{DIM};")
        col.addWidget(name); col.addWidget(title)
        lay.addLayout(col); lay.addStretch()

        arrow = QLabel("→")
        arrow.setFont(QFont("Segoe UI", 14))
        arrow.setStyleSheet(f"color:{DIM};")
        lay.addWidget(arrow)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.selected.emit(self.app)

# ── Selected app badge ────────────────────────────────────────────────────────

class AppBadge(QWidget):
    removed = pyqtSignal(str)   # exe

    def __init__(self, app_info, parent=None):
        super().__init__(parent)
        self.app = app_info
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 5, 8, 5)
        lay.setSpacing(6)
        self.setStyleSheet(f"background:{BORDER};border-radius:8px;")

        lbl = QLabel(app_info["exe"])
        lbl.setFont(QFont("Segoe UI", 10))
        lbl.setStyleSheet(f"color:{WHITE};background:transparent;")
        lay.addWidget(lbl)

        rm = QPushButton("✕")
        rm.setFixedSize(18, 18)
        rm.setFont(QFont("Segoe UI", 9))
        rm.setStyleSheet(
            f"QPushButton{{background:transparent;color:{DIM};border:none;}}"
            f"QPushButton:hover{{color:{WHITE};}}"
        )
        rm.setCursor(Qt.PointingHandCursor)
        rm.clicked.connect(lambda: self.removed.emit(app_info["exe"]))
        lay.addWidget(rm)

# ── Screen 1 — App picker ─────────────────────────────────────────────────────

class AppPickerScreen(QWidget):
    proceed = pyqtSignal(list)   # list of app dicts

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{BG};")
        self._selected = {}   # exe -> app_info
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(12)

        # Header
        h_row = QHBoxLayout()
        title = QLabel("Choose apps to gate")
        title.setFont(QFont("Segoe UI", 13, QFont.Bold))
        title.setStyleSheet(f"color:{WHITE};")
        h_row.addWidget(title); h_row.addStretch()
        refresh = QPushButton("⟳  Refresh")
        refresh.setFont(QFont("Segoe UI", 9))
        refresh.setCursor(Qt.PointingHandCursor)
        refresh.setStyleSheet(
            f"QPushButton{{background:{SURFACE};color:{GRAY};border:1px solid {BORDER};"
            f"border-radius:6px;padding:5px 12px;}}"
            f"QPushButton:hover{{color:{WHITE};}}"
        )
        refresh.clicked.connect(self._load_apps)
        h_row.addWidget(refresh)
        root.addLayout(h_row)

        sub = QLabel("Select one or more running apps. The cat will cover them during your break.")
        sub.setFont(QFont("Segoe UI", 9)); sub.setStyleSheet(f"color:{DIM};"); sub.setWordWrap(True)
        root.addWidget(sub)

        # Scroll list
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFixedHeight(240)
        scroll.setStyleSheet(
            f"QScrollArea{{background:transparent;border:none;}}"
            f"QScrollBar:vertical{{background:{SURFACE};width:5px;border-radius:3px;}}"
            f"QScrollBar::handle:vertical{{background:{BORDER};border-radius:3px;}}"
        )
        self._list_container = QWidget(); self._list_container.setStyleSheet(f"background:{BG};")
        self._list_lay = QVBoxLayout(self._list_container)
        self._list_lay.setContentsMargins(0,0,4,0); self._list_lay.setSpacing(6)
        self._list_lay.addStretch()
        scroll.setWidget(self._list_container)
        root.addWidget(scroll)

        # Selected badges
        sel_label = QLabel("Selected:")
        sel_label.setFont(QFont("Segoe UI", 9)); sel_label.setStyleSheet(f"color:{DIM};")
        root.addWidget(sel_label)

        self._badges_row = QHBoxLayout(); self._badges_row.setSpacing(6); self._badges_row.addStretch()
        self._badges_w = QWidget(); self._badges_w.setStyleSheet(f"background:{BG};")
        self._badges_w.setLayout(self._badges_row)
        root.addWidget(self._badges_w)

        self._none_label = QLabel("None selected yet")
        self._none_label.setFont(QFont("Segoe UI", 9))
        self._none_label.setStyleSheet(f"color:{DIM};font-style:italic;")
        root.addWidget(self._none_label)

        # Proceed button
        self._proceed_btn = QPushButton("Set Timer  →")
        self._proceed_btn.setFont(QFont("Segoe UI", 11, QFont.Medium))
        self._proceed_btn.setEnabled(False)
        self._proceed_btn.setCursor(Qt.PointingHandCursor)
        self._proceed_btn.setStyleSheet(
            f"QPushButton{{background:{ORANGE};color:{WHITE};border:none;"
            f"border-radius:8px;padding:10px 0;}}"
            f"QPushButton:hover{{background:{D_ORANGE};}}"
            f"QPushButton:disabled{{opacity:0.35;}}"
        )
        self._proceed_btn.clicked.connect(lambda: self.proceed.emit(list(self._selected.values())))
        root.addWidget(self._proceed_btn)

        self._load_apps()

    def _load_apps(self):
        while self._list_lay.count() > 1:
            item = self._list_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        apps = get_running_apps()
        if not apps:
            lbl = QLabel("No running apps found — try Refresh")
            lbl.setFont(QFont("Segoe UI", 10)); lbl.setStyleSheet(f"color:{DIM};")
            lbl.setAlignment(Qt.AlignCenter)
            self._list_lay.insertWidget(0, lbl)
            return

        for i, app in enumerate(apps):
            card = AppCard(app)
            card.selected.connect(self._add_app)
            self._list_lay.insertWidget(i, card)

    def _add_app(self, app):
        key = app["exe"].lower()
        if key in self._selected: return
        self._selected[key] = app
        self._refresh_badges()
        self._proceed_btn.setEnabled(True)

    def _remove_app(self, exe):
        self._selected.pop(exe.lower(), None)
        self._refresh_badges()
        self._proceed_btn.setEnabled(bool(self._selected))

    def _refresh_badges(self):
        for w in self._badges_w.findChildren(AppBadge): w.deleteLater()
        self._none_label.setVisible(not self._selected)
        for app in self._selected.values():
            badge = AppBadge(app)
            badge.removed.connect(self._remove_app)
            self._badges_row.insertWidget(0, badge)

# ── Screen 2 — Timer ──────────────────────────────────────────────────────────

class TimerScreen(QWidget):
    go_back   = pyqtSignal()
    start_break = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{BG};")
        self._apps          = []
        self._running       = False
        self._auto_paused   = False
        self._remaining     = 0
        self._total         = 0
        self._sessions      = 0
        self._timer         = QTimer(self); self._timer.timeout.connect(self._tick)
        self._watcher       = QTimer(self); self._watcher.timeout.connect(self._watch_focus)
        self._build()

    def load_apps(self, apps):
        self._apps = apps
        names = ", ".join(a["exe"] for a in apps)
        self._apps_label.setText(f"Gating: {names}")
        self._reset()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 16, 24, 16)
        root.setSpacing(12)

        # Back button + app name
        top = QHBoxLayout()
        back = QPushButton("← Back")
        back.setFont(QFont("Segoe UI", 9)); back.setCursor(Qt.PointingHandCursor)
        back.setStyleSheet(
            f"QPushButton{{background:{SURFACE};color:{GRAY};border:1px solid {BORDER};"
            f"border-radius:6px;padding:5px 12px;}}"
            f"QPushButton:hover{{color:{WHITE};}}"
        )
        back.clicked.connect(self._on_back)
        top.addWidget(back); top.addStretch()
        root.addLayout(top)

        self._apps_label = QLabel("")
        self._apps_label.setFont(QFont("Segoe UI", 9))
        self._apps_label.setStyleSheet(f"color:{ORANGE};")
        self._apps_label.setWordWrap(True)
        root.addWidget(self._apps_label)

        # Ring
        self.ring = RingTimer()
        root.addWidget(self.ring, 0, Qt.AlignCenter)

        # Buttons
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        self.start_btn = self._btn("Start",  ORANGE,  WHITE,     self._start)
        self.pause_btn = self._btn("Pause",  SURFACE, "#bbbbbb", self._pause)
        self.pause_btn.setEnabled(False)
        reset_btn = self._btn("Reset", SURFACE, "#bbbbbb", self._reset)
        for b in [self.start_btn, self.pause_btn, reset_btn]: btn_row.addWidget(b)
        root.addLayout(btn_row)

        # Settings
        sg = QVBoxLayout(); sg.setSpacing(8)
        for label, attr, mn, mx, val in [
            ("Work time (min)", "work_spin", 1, 120, 25),
            ("Break time (min)", "break_spin", 1, 60, 5),
        ]:
            row = QHBoxLayout()
            row.addWidget(self._lbl(label)); row.addStretch()
            spin = self._spin(mn, mx, val)
            setattr(self, attr, spin)
            row.addWidget(spin); sg.addLayout(row)
        root.addLayout(sg)

        # Progress
        self.prog = QProgressBar(); self.prog.setFixedHeight(4); self.prog.setTextVisible(False)
        self.prog.setStyleSheet(
            f"QProgressBar{{background:#222;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{ORANGE};border-radius:2px;}}"
        )
        root.addWidget(self.prog)

        # Session dots
        self._dots_lay = QHBoxLayout(); self._dots_lay.setSpacing(6)
        dots_w = QWidget(); dots_w.setLayout(self._dots_lay)
        root.addWidget(dots_w, 0, Qt.AlignCenter)

        self.status_lbl = QLabel("Ready — press Start")
        self.status_lbl.setFont(QFont("Segoe UI", 9))
        self.status_lbl.setStyleSheet(f"color:{DIM};")
        self.status_lbl.setAlignment(Qt.AlignCenter)
        root.addWidget(self.status_lbl)

    def _btn(self, text, bg, fg, slot):
        b = QPushButton(text); b.setFont(QFont("Segoe UI", 11, QFont.Medium))
        b.setStyleSheet(
            f"QPushButton{{background:{bg};color:{fg};border:none;border-radius:7px;padding:8px 0;}}"
            f"QPushButton:disabled{{opacity:0.35;}}"
        )
        b.setCursor(Qt.PointingHandCursor); b.clicked.connect(slot); return b

    def _lbl(self, t):
        l = QLabel(t); l.setFont(QFont("Segoe UI", 10)); l.setStyleSheet(f"color:{DIM};"); return l

    def _spin(self, mn, mx, val):
        s = QSpinBox(); s.setRange(mn, mx); s.setValue(val); s.setFont(QFont("Segoe UI", 12))
        s.setStyleSheet(
            f"QSpinBox{{background:{SURFACE};color:white;border:1px solid {BORDER};"
            f"border-radius:6px;padding:5px 10px;width:60px;}}"
            f"QSpinBox::up-button,QSpinBox::down-button{{width:16px;background:{SURFACE};}}"
        )
        s.valueChanged.connect(self._reset); return s

    def _render_dots(self):
        for w in list(self.findChildren(QLabel)):
            if w.parent() and w.parent().layout() == self._dots_lay: w.deleteLater()
        while self._dots_lay.count():
            item = self._dots_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for i in range(4):
            d = QLabel(); d.setFixedSize(10,10)
            d.setStyleSheet(f"background:{'#e8813a' if i < self._sessions%4 else '#2a2a2a'};border-radius:5px;")
            self._dots_lay.addWidget(d)
        if self._sessions:
            l = QLabel(f"  {self._sessions} done"); l.setFont(QFont("Segoe UI",9)); l.setStyleSheet(f"color:#444;")
            self._dots_lay.addWidget(l)

    def _reset(self):
        self._timer.stop(); self._watcher.stop()
        self._running = False; self._auto_paused = False
        self._total = self.work_spin.value() * 60
        self._remaining = self._total
        self.start_btn.setEnabled(True); self.pause_btn.setEnabled(False)
        self.prog.setValue(100)
        self.ring.set_state(1.0, "WORK", self._fmt(self._remaining))
        self.status_lbl.setText("Ready — press Start")
        self._render_dots()

    def _start(self):
        if self._remaining <= 0: self._remaining = self.work_spin.value() * 60
        self._total = self.work_spin.value() * 60
        self._running = True; self._auto_paused = False
        self.start_btn.setEnabled(False); self.pause_btn.setEnabled(True)
        self.status_lbl.setText("Focus mode — stay on task!")
        self._timer.start(1000)
        self._watcher.start(1000)

    def _pause(self):
        self._timer.stop(); self._watcher.stop()
        self._running = False; self._auto_paused = False
        self.start_btn.setEnabled(True); self.pause_btn.setEnabled(False)
        self.status_lbl.setText("Paused")

    def _watch_focus(self):
        """Auto-pause when none of the gated apps are in focus; resume when one is."""
        if not self._apps:
            return
        exe_names = [a["exe"] for a in self._apps]
        app_active = is_any_app_active(exe_names)

        if not app_active and not self._auto_paused:
            # App lost focus → pause timer silently
            self._timer.stop()
            self._auto_paused = True
            self.status_lbl.setText("⏸  App not in use — timer paused")
            self.ring.set_state(
                self._remaining / self._total if self._total else 0,
                "PAUSED", self._fmt(self._remaining)
            )

        elif app_active and self._auto_paused:
            # App back in focus → resume timer
            self._timer.start(1000)
            self._auto_paused = False
            self.status_lbl.setText("▶  Focus mode — stay on task!")
            self.ring.set_state(
                self._remaining / self._total if self._total else 0,
                "WORK", self._fmt(self._remaining)
            )

    def _tick(self):
        self._remaining -= 1
        if self._remaining < 0:
            self._remaining = 0
        pct = self._remaining / self._total if self._total else 0
        self.ring.set_state(pct, "WORK", self._fmt(self._remaining))
        self.prog.setValue(int(pct * 100))
        if self._remaining <= 0:
            self._timer.stop()
            self._watcher.stop()
            self._sessions += 1
            self._render_dots()
            self.status_lbl.setText("Time's up! Cat incoming...")
            self.start_break.emit()

    def on_break_done(self):
        # Full reset then auto-restart next work session
        self._timer.stop(); self._watcher.stop()
        self._running = False; self._auto_paused = False
        self._total     = self.work_spin.value() * 60
        self._remaining = self._total
        self._render_dots()
        self.prog.setValue(100)
        self.ring.set_state(1.0, "WORK", self._fmt(self._remaining))
        self.start_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.status_lbl.setText("Break over! Restarting work session...")
        # Defer by 1.5s so user sees the restart message before timer kicks in
        QTimer.singleShot(1500, self._auto_restart)

    def _auto_restart(self):
        # Don't restart if timer already running (safety against double-fire)
        if self._timer.isActive():
            return
        self._running = True
        self._auto_paused = False
        self.status_lbl.setText("Focus mode — stay on task!")
        self._timer.start(1000)
        self._watcher.start(1000)

    def _on_back(self):
        self._timer.stop(); self._watcher.stop()
        self._running = False; self._auto_paused = False
        self.go_back.emit()

    def _fmt(self, s): return f"{s//60}:{s%60:02d}"

    def get_break_secs(self): return self.break_spin.value() * 60
    def get_apps(self): return self._apps

# ── App overlay (covers target app window) ────────────────────────────────────

class AppOverlay(QWidget):
    """Overlay that sits on top of one app window. Timer is driven externally by BreakSession."""

    def __init__(self, exe, total_secs, pix):
        super().__init__()
        self._exe      = exe
        self._total    = total_secs
        self._pix      = pix
        self._scaled   = None
        self._target_hwnd = None   # cached hwnd of the target app window
        # NO WindowStaysOnTopHint — we manage Z-order manually via win32
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.NoDropShadowWindowHint)
        self.setStyleSheet("background:black;")
        self._build()
        self._reposition()
        self.show()
        self._pos_t = QTimer(self)
        self._pos_t.timeout.connect(self._reposition)
        self._pos_t.start(200)

    def _build(self):
        lay = QVBoxLayout(self); lay.setAlignment(Qt.AlignCenter); lay.setSpacing(12)

        self._title = QLabel("BREAK TIME")
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setFont(QFont("Segoe UI", 13))
        self._title.setStyleSheet("color:#cccccc;background:transparent;")

        self._time = QLabel(self._fmt(self._total))
        self._time.setAlignment(Qt.AlignCenter)
        self._time.setFont(QFont("Segoe UI", 52, QFont.Bold))
        self._time.setStyleSheet("color:white;background:transparent;")

        self._sub = QLabel(random.choice(BREAK_MSGS))
        self._sub.setAlignment(Qt.AlignCenter)
        self._sub.setFont(QFont("Segoe UI", 10))
        self._sub.setStyleSheet("color:#aaaaaa;background:transparent;")

        self._bar = QProgressBar()
        self._bar.setFixedSize(200, 4)
        self._bar.setTextVisible(False)
        self._bar.setValue(100)
        self._bar.setStyleSheet(
            f"QProgressBar{{background:#333;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{ORANGE};border-radius:2px;}}"
        )

        # Skip button — signals the BreakSession to end everything
        self._skip_btn = QPushButton("Skip break")
        self._skip_btn.setFont(QFont("Segoe UI", 10))
        self._skip_btn.setCursor(Qt.PointingHandCursor)
        self._skip_btn.setStyleSheet(
            "QPushButton{background:rgba(30,30,30,200);color:#aaaaaa;"
            "border:1px solid #555;border-radius:7px;padding:7px 24px;}"
            "QPushButton:hover{background:rgba(255,255,255,30);color:white;}"
        )
        # Connected externally by BreakSession
        for w in [self._title, self._time, self._sub, self._bar, self._skip_btn]:
            lay.addWidget(w, 0, Qt.AlignCenter)

    def update_time(self, secs):
        """Called every second by BreakSession with the shared remaining time."""
        self._time.setText(self._fmt(secs))
        self._bar.setValue(int(secs / self._total * 100) if self._total else 0)

    def _get_target_hwnd(self):
        """Find the main visible hwnd for the target exe."""
        if not WIN32:
            return None
        target_pids = set()
        try:
            for proc in psutil.process_iter(["pid","name"]):
                if proc.info["name"].lower() == self._exe.lower():
                    target_pids.add(proc.info["pid"])
        except: pass
        best_hwnd = None
        best_area = 0
        def cb(hwnd, _):
            nonlocal best_hwnd, best_area
            if not win32gui.IsWindowVisible(hwnd): return
            if win32gui.IsIconic(hwnd): return
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid not in target_pids: return
                l,t,r,b = win32gui.GetWindowRect(hwnd)
                area = (r-l)*(b-t)
                if area > best_area:
                    best_area = area
                    best_hwnd = hwnd
            except: pass
        win32gui.EnumWindows(cb, None)
        return best_hwnd

    def _reposition(self):
        target_hwnd = self._get_target_hwnd() if WIN32 else None

        # Check if target app is minimized / not visible
        if WIN32:
            if target_hwnd is None or win32gui.IsIconic(target_hwnd):
                if self.isVisible():
                    self.hide()
                return
            l, t, r, b = win32gui.GetWindowRect(target_hwnd)
        else:
            avail = QDesktopWidget().availableGeometry()
            l, t = avail.x()+100, avail.y()+100
            r, b = avail.right()-100, avail.bottom()-100

        # Clamp to available screen (excludes taskbar)
        avail = QDesktopWidget().availableGeometry()
        x = max(l, avail.x())
        y = max(t, avail.y())
        rr = min(r, avail.right())
        bb = min(b, avail.bottom())
        w = max(rr - x, 0)
        h = max(bb - y, 0)

        if w < 10 or h < 10:
            if self.isVisible():
                self.hide()
            return

        self.setGeometry(x, y, w, h)
        if self._pix and not self._pix.isNull():
            self._scaled = self._pix.scaled(
                w, h,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation)
        self.update()

        if not self.isVisible():
            self.show()

        # Place overlay JUST above the target app window in Z-order
        # This means it covers the app but NOT other windows on top of it
        if WIN32 and target_hwnd:
            my_hwnd = int(self.winId())
            try:
                # Step 1: Get the window that is ABOVE the target in Z-order
                hwnd_above = win32gui.GetWindow(target_hwnd, win32con.GW_HWNDPREV)
                if hwnd_above and hwnd_above != my_hwnd:
                    # Insert our overlay just below hwnd_above (= just above target)
                    win32gui.SetWindowPos(
                        my_hwnd,
                        hwnd_above,
                        x, y, w, h,
                        win32con.SWP_NOACTIVATE | win32con.SWP_NOSIZE | win32con.SWP_NOMOVE
                    )
                else:
                    # Nothing above target — just move/resize, keep current Z
                    win32gui.SetWindowPos(
                        my_hwnd,
                        win32con.HWND_TOP,
                        x, y, w, h,
                        win32con.SWP_NOACTIVATE
                    )
                    # Then push back down to sit just above target
                    win32gui.SetWindowPos(
                        target_hwnd,
                        my_hwnd,
                        0, 0, 0, 0,
                        win32con.SWP_NOACTIVATE | win32con.SWP_NOSIZE | win32con.SWP_NOMOVE
                    )
            except:
                pass

    def paintEvent(self, _):
        p = QPainter(self)
        if self._scaled:
            p.drawPixmap(0, 0, self._scaled)
            p.fillRect(self.rect(), QColor(0, 0, 0, 130))
        else:
            p.fillRect(self.rect(), QColor(20, 20, 20))
        p.end()

    def stop_reposition(self):
        self._pos_t.stop()

    def _fmt(self, s): return f"{s//60}:{s%60:02d}"


class BreakSession(QObject):
    """
    Single source of truth for the break countdown.
    Owns ONE QTimer, updates ALL overlays in sync, fires all_done once.
    """
    all_done = pyqtSignal()

    def __init__(self, secs, overlays, parent=None):
        super().__init__(parent)
        self._secs     = secs
        self._total    = secs
        self._overlays = overlays
        self._finished = False

        # Wire skip button on every overlay to the same end_break slot
        for ov in overlays:
            ov._skip_btn.clicked.connect(self.end_break)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

    def _tick(self):
        self._secs -= 1
        for ov in self._overlays:
            ov.update_time(self._secs)
        if self._secs <= 0:
            self.end_break()

    def end_break(self):
        if self._finished:
            return          # ← guard: only fire once no matter how many overlays
        self._finished = True
        self._timer.stop()
        for ov in self._overlays:
            ov.stop_reposition()
            ov.close()
        self._overlays.clear()
        self.all_done.emit()

# ── Main window ───────────────────────────────────────────────────────────────

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cat Gatekeeper")
        self.setFixedSize(360, 580)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_AlwaysShowToolTips)
        self.setStyleSheet(f"background:{BG};")
        self._drag_pos = None
        self._overlays = []
        self._build()
        s = QDesktopWidget().availableGeometry()
        self.move((s.width()-360)//2, (s.height()-580)//2)

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # Titlebar
        tb = QWidget(); tb.setFixedHeight(40); tb.setStyleSheet(f"background:{SURFACE};")
        tbl = QHBoxLayout(tb); tbl.setContentsMargins(14,0,14,0)
        for color, fn in [("#ff5f57", self.close), ("#febc2e", self.showMinimized), ("#28c840", None)]:
            b = QPushButton(); b.setFixedSize(13,13)
            b.setStyleSheet(f"QPushButton{{background:{color};border-radius:6px;border:none;}}")
            if fn: b.clicked.connect(fn)
            tbl.addWidget(b)
        tbl.addSpacing(10)
        tl = QLabel("Cat Gatekeeper"); tl.setFont(QFont("Segoe UI",11)); tl.setStyleSheet(f"color:{GRAY};")
        tbl.addWidget(tl); tbl.addStretch()
        root.addWidget(tb)

        # Stacked screens
        self._stack = QStackedWidget()
        self._stack.setStyleSheet(f"background:{BG};")

        self._picker = AppPickerScreen()
        self._picker.proceed.connect(self._on_apps_chosen)

        self._timer_screen = TimerScreen()
        self._timer_screen.go_back.connect(self._show_picker)
        self._timer_screen.start_break.connect(self._launch_break)

        self._stack.addWidget(self._picker)       # index 0
        self._stack.addWidget(self._timer_screen) # index 1
        root.addWidget(self._stack)

    def _on_apps_chosen(self, apps):
        self._timer_screen.load_apps(apps)
        self._stack.setCurrentIndex(1)

    def _show_picker(self):
        self._stack.setCurrentIndex(0)

    def _launch_break(self):
        # Guard: if a break session is already running, don't start another
        if getattr(self, '_break_session', None) is not None:
            return

        apps = self._timer_screen.get_apps()
        secs = self._timer_screen.get_break_secs()

        # Clean up any previous thread
        if hasattr(self, '_cat_thread') and self._cat_thread is not None:
            try:
                self._cat_thread.quit()
                self._cat_thread.wait(500)
            except: pass

        self._cat_thread  = QThread()
        self._cat_loader  = CatLoader(random.choice(CAT_URLS))
        self._cat_loader.moveToThread(self._cat_thread)
        self._cat_thread.started.connect(self._cat_loader.run)
        # Use a one-shot lambda with disconnect to prevent duplicate firing
        def on_loaded(pix):
            try: self._cat_loader.loaded.disconnect(on_loaded)
            except: pass
            self._spawn_overlays(apps, secs, pix)
        self._cat_loader.loaded.connect(on_loaded)
        self._cat_thread.start()

    def _spawn_overlays(self, apps, secs, pix):
        try:
            self._cat_thread.quit()
            self._cat_thread.wait(500)
        except: pass

        # Safety: destroy any existing session first
        if getattr(self, '_break_session', None) is not None:
            try:
                self._break_session.all_done.disconnect()
                self._break_session._timer.stop()
            except: pass
            self._break_session = None

        self._overlays = []
        for app in apps:
            ov = AppOverlay(app["exe"], secs, pix)
            self._overlays.append(ov)

        self._break_session = BreakSession(secs, self._overlays, parent=self)
        self._break_session.all_done.connect(self._on_break_all_done)

    def _on_break_all_done(self):
        self._break_session = None   # clear so next cycle can start fresh
        self._timer_screen.on_break_done()
        self.raise_(); self.activateWindow()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self._drag_pos = e.globalPos() - self.pos()
    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.LeftButton: self.move(e.globalPos() - self._drag_pos)
    def mouseReleaseEvent(self, e): self._drag_pos = None

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
