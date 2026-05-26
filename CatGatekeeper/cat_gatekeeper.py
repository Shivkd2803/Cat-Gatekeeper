import sys, threading, time, urllib.request, io, random
from PyQt5.QtWidgets import (QApplication, QWidget, QLabel, QPushButton,
    QSpinBox, QVBoxLayout, QHBoxLayout, QFrame, QProgressBar, QDesktopWidget)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
from PyQt5.QtGui import QFont, QPainter, QPen, QColor, QPixmap, QIcon, QPalette

CAT_URLS = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Cat_November_2010-1a.jpg/1280px-Cat_November_2010-1a.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bb/Kittyply_edit1.jpg/1280px-Kittyply_edit1.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/68/Orange_tabby_cat_sitting_on_fallen_leaves-Hisashi-01A.jpg/1280px-Orange_tabby_cat_sitting_on_fallen_leaves-Hisashi-01A.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Cat03.jpg/1280px-Cat03.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Siam_lilacpoint.jpg/1280px-Siam_lilacpoint.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Sleeping_cat_on_her_back.jpg/1280px-Sleeping_cat_on_her_back.jpg",
]
BREAK_MSGS = [
    "Step away from the screen",
    "Rest your eyes — look far away",
    "Stretch your hands and neck",
    "Get some water!",
    "The cat says: take a real break",
]

ORANGE = "#e8813a"
BG = "#141414"
SURFACE = "#1e1e1e"


class CatLoader(QObject):
    loaded = pyqtSignal(QPixmap)
    def __init__(self, url): super().__init__(); self.url = url
    def run(self):
        try:
            req = urllib.request.Request(self.url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r: data = r.read()
            pix = QPixmap(); pix.loadFromData(data)
            self.loaded.emit(pix)
        except: self.loaded.emit(QPixmap())


class RingTimer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(180, 180)
        self._pct = 1.0
        self._label = "WORK"
        self._time_str = "25:00"

    def set_state(self, pct, label, time_str):
        self._pct = pct; self._label = label; self._time_str = time_str
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        cx, cy, r = 90, 90, 75
        p.setPen(QPen(QColor("#222222"), 8, Qt.SolidLine, Qt.RoundCap))
        p.drawEllipse(cx-r, cy-r, r*2, r*2)
        if self._pct > 0:
            p.setPen(QPen(QColor(ORANGE), 8, Qt.SolidLine, Qt.RoundCap))
            span = int(-self._pct * 360 * 16)
            p.drawArc(cx-r, cy-r, r*2, r*2, 90*16, span)
        p.setPen(QColor("#555555"))
        p.setFont(QFont("Segoe UI", 9)); p.drawText(0, 62, 180, 20, Qt.AlignCenter, self._label)
        p.setPen(QColor("#ffffff"))
        p.setFont(QFont("Segoe UI", 28, QFont.Bold)); p.drawText(0, 80, 180, 50, Qt.AlignCenter, self._time_str)
        p.end()


class TimerWindow(QWidget):
    show_break = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Cat Gatekeeper")
        self.setFixedSize(320, 470)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(f"background:{BG};")
        self._drag_pos = None
        self._running = False
        self._remaining = 0
        self._total = 0
        self._sessions = 0
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick)
        self._build()
        self._reset()
        screen = QDesktopWidget().availableGeometry()
        self.move((screen.width()-320)//2, (screen.height()-470)//2)

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # Titlebar
        tb = QWidget(); tb.setFixedHeight(38); tb.setStyleSheet(f"background:{SURFACE};")
        tb_lay = QHBoxLayout(tb); tb_lay.setContentsMargins(14,0,14,0)
        for color, action in [("#ff5f57", self.close), ("#febc2e", self.showMinimized), ("#28c840", None)]:
            btn = QPushButton(); btn.setFixedSize(13,13)
            btn.setStyleSheet(f"QPushButton{{background:{color};border-radius:6px;border:none;}} QPushButton:hover{{opacity:0.7;}}")
            if action: btn.clicked.connect(action)
            tb_lay.addWidget(btn)
        tb_lay.addSpacing(8)
        lbl = QLabel("Cat Gatekeeper"); lbl.setStyleSheet("color:#888888;"); lbl.setFont(QFont("Segoe UI",11))
        tb_lay.addWidget(lbl); tb_lay.addStretch()
        root.addWidget(tb)

        body = QWidget(); body.setStyleSheet(f"background:{BG};")
        lay = QVBoxLayout(body); lay.setContentsMargins(28,20,28,20); lay.setSpacing(14)

        self.ring = RingTimer(body); lay.addWidget(self.ring, 0, Qt.AlignCenter)

        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        self.start_btn = self._btn("Start", ORANGE, "#ffffff", self._start)
        self.pause_btn = self._btn("Pause", SURFACE, "#bbbbbb", self._pause); self.pause_btn.setEnabled(False)
        reset_btn = self._btn("Reset", SURFACE, "#bbbbbb", self._reset)
        for b in [self.start_btn, self.pause_btn, reset_btn]: btn_row.addWidget(b)
        lay.addLayout(btn_row)

        # Settings
        sg = QVBoxLayout(); sg.setSpacing(8)
        work_row = QHBoxLayout()
        work_row.addWidget(self._label("Work time (min)"))
        self.work_spin = self._spin(1, 120, 25); work_row.addWidget(self.work_spin)
        sg.addLayout(work_row)
        break_row = QHBoxLayout()
        break_row.addWidget(self._label("Break time (min)"))
        self.break_spin = self._spin(1, 60, 5); break_row.addWidget(self.break_spin)
        sg.addLayout(break_row)
        lay.addLayout(sg)

        self.prog = QProgressBar(); self.prog.setFixedHeight(4); self.prog.setTextVisible(False)
        self.prog.setStyleSheet(f"QProgressBar{{background:#222;border-radius:2px;}} QProgressBar::chunk{{background:{ORANGE};border-radius:2px;}}")
        lay.addWidget(self.prog)

        self.dots_row = QHBoxLayout(); self.dots_row.setSpacing(6)
        self.dots_widget = QWidget(); self.dots_widget.setLayout(self.dots_row)
        lay.addWidget(self.dots_widget, 0, Qt.AlignCenter)

        self.status_lbl = QLabel("Ready — press Start to begin")
        self.status_lbl.setStyleSheet("color:#555555;"); self.status_lbl.setFont(QFont("Segoe UI",9))
        self.status_lbl.setAlignment(Qt.AlignCenter); lay.addWidget(self.status_lbl)

        root.addWidget(body)

    def _btn(self, text, bg, fg, slot):
        b = QPushButton(text); b.setFont(QFont("Segoe UI",11,QFont.Medium))
        b.setStyleSheet(f"QPushButton{{background:{bg};color:{fg};border:none;border-radius:7px;padding:8px 16px;}} QPushButton:hover{{opacity:0.85;}} QPushButton:disabled{{opacity:0.35;}}")
        b.setCursor(Qt.PointingHandCursor); b.clicked.connect(slot); return b

    def _label(self, text):
        l = QLabel(text); l.setStyleSheet("color:#555555;"); l.setFont(QFont("Segoe UI",10)); return l

    def _spin(self, mn, mx, val):
        s = QSpinBox(); s.setRange(mn, mx); s.setValue(val)
        s.setFont(QFont("Segoe UI",12))
        s.setStyleSheet(f"QSpinBox{{background:{SURFACE};color:white;border:1px solid #2e2e2e;border-radius:6px;padding:5px 10px;width:60px;}} QSpinBox::up-button,QSpinBox::down-button{{width:16px;background:{SURFACE};}}")
        s.valueChanged.connect(self._reset); return s

    def _render_dots(self):
        while self.dots_row.count(): self.dots_row.takeAt(0).widget().deleteLater() if self.dots_row.takeAt(0) else None
        for w in self.dots_widget.findChildren(QWidget): w.deleteLater()
        for i in range(4):
            d = QLabel(); d.setFixedSize(10,10)
            color = ORANGE if i < (self._sessions % 4) else "#2a2a2a"
            d.setStyleSheet(f"background:{color};border-radius:5px;"); self.dots_row.addWidget(d)
        if self._sessions > 0:
            l = QLabel(f"  {self._sessions} done"); l.setStyleSheet("color:#444;"); l.setFont(QFont("Segoe UI",9))
            self.dots_row.addWidget(l)

    def _reset(self):
        self._timer.stop(); self._running = False
        self._total = self.work_spin.value() * 60
        self._remaining = self._total
        self.start_btn.setEnabled(True); self.pause_btn.setEnabled(False)
        self.prog.setValue(100)
        self.ring.set_state(1.0, "WORK", self._fmt(self._remaining))
        self.status_lbl.setText("Ready — press Start to begin")
        self._render_dots()

    def _start(self):
        if self._remaining <= 0: self._remaining = self.work_spin.value() * 60
        self._total = self.work_spin.value() * 60
        self._running = True
        self.start_btn.setEnabled(False); self.pause_btn.setEnabled(True)
        self.status_lbl.setText("Focus mode — stay on task!")
        self._timer.start(1000)

    def _pause(self):
        self._timer.stop(); self._running = False
        self.start_btn.setEnabled(True); self.pause_btn.setEnabled(False)
        self.status_lbl.setText("Paused — press Start to resume")

    def _tick(self):
        self._remaining -= 1
        pct = self._remaining / self._total if self._total > 0 else 0
        self.ring.set_state(pct, "WORK", self._fmt(self._remaining))
        self.prog.setValue(int(pct * 100))
        if self._remaining <= 0:
            self._timer.stop()
            self._sessions += 1
            self._render_dots()
            self.status_lbl.setText("Time's up! Cat incoming...")
            self.show_break.emit(self.break_spin.value() * 60)

    def _fmt(self, s): return f"{s//60}:{s%60:02d}"

    def on_break_done(self):
        self._reset(); self.status_lbl.setText("Break over! Start another session?")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self._drag_pos = e.globalPos() - self.pos()
    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.LeftButton: self.move(e.globalPos() - self._drag_pos)
    def mouseReleaseEvent(self, e): self._drag_pos = None


class OverlayWindow(QWidget):
    done = pyqtSignal()

    def __init__(self, break_secs):
        super().__init__()
        self._secs = break_secs; self._total = break_secs
        self._pix = None
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("background:black;")
        screen = QDesktopWidget().screenGeometry()
        self.setGeometry(screen)
        self.showFullScreen()
        self.activateWindow(); self.raise_()
        self._build()
        self._load_cat()
        self._timer = QTimer(self); self._timer.timeout.connect(self._tick); self._timer.start(1000)

    def _build(self):
        lay = QVBoxLayout(self); lay.setAlignment(Qt.AlignCenter); lay.setSpacing(16)
        self.title_lbl = QLabel("BREAK TIME"); self.title_lbl.setAlignment(Qt.AlignCenter)
        self.title_lbl.setFont(QFont("Segoe UI",16)); self.title_lbl.setStyleSheet("color:#cccccc;background:transparent;")
        self.time_lbl = QLabel(self._fmt(self._secs)); self.time_lbl.setAlignment(Qt.AlignCenter)
        self.time_lbl.setFont(QFont("Segoe UI",90,QFont.Bold)); self.time_lbl.setStyleSheet("color:white;background:transparent;")
        self.sub_lbl = QLabel(random.choice(BREAK_MSGS)); self.sub_lbl.setAlignment(Qt.AlignCenter)
        self.sub_lbl.setFont(QFont("Segoe UI",13)); self.sub_lbl.setStyleSheet("color:#aaaaaa;background:transparent;")
        self.bar = QProgressBar(); self.bar.setFixedSize(280,5); self.bar.setTextVisible(False)
        self.bar.setStyleSheet(f"QProgressBar{{background:#333;border-radius:2px;}} QProgressBar::chunk{{background:{ORANGE};border-radius:2px;}}")
        self.bar.setValue(100)
        skip = QPushButton("Skip break"); skip.setFont(QFont("Segoe UI",12))
        skip.setStyleSheet("QPushButton{background:rgba(30,30,30,180);color:#aaaaaa;border:1px solid #444;border-radius:7px;padding:9px 28px;} QPushButton:hover{background:rgba(255,255,255,40);color:white;}")
        skip.setCursor(Qt.PointingHandCursor); skip.clicked.connect(self._end)
        for w in [self.title_lbl, self.time_lbl, self.sub_lbl, self.bar, skip]: lay.addWidget(w, 0, Qt.AlignCenter)

    def _load_cat(self):
        self._thread = QThread()
        self._loader = CatLoader(random.choice(CAT_URLS))
        self._loader.moveToThread(self._thread)
        self._thread.started.connect(self._loader.run)
        self._loader.loaded.connect(self._on_cat); self._thread.start()

    def _on_cat(self, pix):
        if not pix.isNull():
            screen = QDesktopWidget().screenGeometry()
            self._pix = pix.scaled(screen.width(), screen.height(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self.update()
        self._thread.quit()

    def paintEvent(self, e):
        p = QPainter(self)
        if self._pix:
            p.drawPixmap(0, 0, self._pix)
            p.fillRect(self.rect(), QColor(0,0,0,120))
        else:
            p.fillRect(self.rect(), QColor(0,0,0))
        p.end()

    def _tick(self):
        self._secs -= 1
        self.time_lbl.setText(self._fmt(self._secs))
        self.bar.setValue(int(self._secs / self._total * 100) if self._total else 0)
        if self._secs <= 0: self._end()

    def _end(self):
        self._timer.stop(); self.close(); self.done.emit()

    def _fmt(self, s): return f"{s//60}:{s%60:02d}"


class App:
    def __init__(self):
        self.qapp = QApplication(sys.argv)
        self.qapp.setStyle("Fusion")
        self.timer_win = TimerWindow()
        self.timer_win.show_break.connect(self._start_break)
        self.timer_win.show()
        self.overlay = None

    def _start_break(self, secs):
        self.overlay = OverlayWindow(secs)
        self.overlay.done.connect(self._break_done)

    def _break_done(self):
        self.overlay = None
        self.timer_win.on_break_done()
        self.timer_win.raise_(); self.timer_win.activateWindow()

    def run(self): sys.exit(self.qapp.exec_())


if __name__ == "__main__":
    App().run()
