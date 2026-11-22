#!/usr/bin/env python3
"""Pressure test: a soft circle grows with the press, and a Force Touch changes its colour."""
import sys, os, time, threading
import evdev
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QTimer, QPointF
from PyQt6.QtGui import QPainter, QRadialGradient, QColor

PARAM_DIR = "/sys/module/hid_magicmouse/parameters"
CONF_DIR = os.path.expanduser("~/.config/magic-trackpad-suite")
CONF_FILE = os.path.join(CONF_DIR, "control-center.conf")
PID_FILE = os.path.join(CONF_DIR, "pressure.pid")   # tells the gesture daemon to ignore Force Touch binds
MAX_P = 253
R_MIN_FRAC, R_MAX_FRAC = 0.10, 0.42
CALM = QColor("#0a84ff")
FORCE = QColor("#ff375f")

TEXT = {
    "ru": {"title": "Тест давления", "pressure": "Давление", "peak": "Максимум",
           "force": "Force Touch", "click": "Клик", "threshold": "порог Force",
           "on": "есть", "off": "нет", "nofind": "Трекпад не найден", "events": "Событий", "err": "Ошибка"},
    "en": {"title": "Pressure test", "pressure": "Pressure", "peak": "Peak",
           "force": "Force Touch", "click": "Click", "threshold": "Force threshold",
           "on": "yes", "off": "no", "nofind": "Trackpad not found", "events": "Events", "err": "Error"},
}

def ui_lang():
    try:
        with open(CONF_FILE) as f:
            for line in f:
                if line.startswith("lang="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return "ru"

def read_param(name, default):
    try:
        return int(open(f"{PARAM_DIR}/{name}").read().strip())
    except Exception:
        return default

def find_trackpad():
    fallback = None
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except Exception:
            continue
        if "Magic Trackpad" not in dev.name:
            continue
        if evdev.ecodes.ABS_MT_PRESSURE not in dev.capabilities(absinfo=False).get(evdev.ecodes.EV_ABS, []):
            continue
        if "proxy" not in (dev.phys or ""):
            return dev
        fallback = fallback or dev
    return fallback

class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.pressure = 0
        self.force = False
        self.peak = 0
        self.found = False
        self.events = 0
        self.error = None

def reader(state):
    while True:
        try:
            dev = find_trackpad()
        except Exception as e:
            with state.lock:
                state.error = str(e)
            time.sleep(2)
            continue
        with state.lock:
            state.found = dev is not None
        if dev is None:
            time.sleep(2)
            continue
        slots, slot = {}, 0
        try:
            for ev in dev.read_loop():
                with state.lock:
                    state.events += 1
                if ev.type == evdev.ecodes.EV_ABS:
                    if ev.code == evdev.ecodes.ABS_MT_SLOT:
                        slot = ev.value
                    elif ev.code == evdev.ecodes.ABS_MT_PRESSURE:
                        slots[slot] = ev.value
                        p = max(slots.values(), default=0)
                        with state.lock:
                            state.pressure = p
                            state.peak = max(state.peak, p)
                elif ev.type == evdev.ecodes.EV_KEY:
                    if ev.code == evdev.ecodes.BTN_TRIGGER_HAPPY1:
                        with state.lock:
                            state.force = ev.value == 1
                    elif ev.code == evdev.ecodes.BTN_TOUCH and ev.value == 0:
                        slots.clear()
                        with state.lock:
                            state.pressure = 0
                            state.force = False
        except Exception as e:
            with state.lock:
                state.error = f"{type(e).__name__}: {e}"
            time.sleep(1)

def lerp(a, b, t):
    return QColor(
        int(a.red() + (b.red() - a.red()) * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue() + (b.blue() - a.blue()) * t),
    )

class Blob(QWidget):
    """Soft circle: radius follows pressure smoothly, colour switches quickly on Force Touch."""
    def __init__(self, state, force_thr, parent=None):
        super().__init__(parent)
        self.state = state
        self.force_thr = force_thr
        self.radius = 0.0
        self.mix = 0.0
        self.simulated = None      # used only for offline screenshots
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.step)
        self.timer.start(16)

    def step(self):
        if self.simulated is not None:
            p, f = self.simulated
        else:
            with self.state.lock:
                p, f = self.state.pressure, self.state.force
        side = min(self.width(), self.height())
        r_min, r_max = side * R_MIN_FRAC, side * R_MAX_FRAC
        norm = min(p / MAX_P, 1.0)
        target = r_min + (r_max - r_min) * (norm ** 0.85)
        self.radius += (target - self.radius) * 0.18        # smooth growth
        goal = 1.0 if (f or p >= self.force_thr) else 0.0
        self.mix += (goal - self.mix) * 0.35                # quick colour change
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        base = lerp(CALM, FORCE, self.mix)
        r = max(self.radius, 1.0)
        grad = QRadialGradient(c, r)
        for stop, alpha in [(0.0, 235), (0.55, 205), (0.85, 70), (1.0, 0)]:
            col = QColor(base); col.setAlpha(alpha)
            grad.setColorAt(stop, col)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(c, r, r)
        p.end()

class PressureWindow(QWidget):
    def __init__(self, state):
        super().__init__()
        self.state = state
        self.t = TEXT.get(ui_lang(), TEXT["ru"])
        self.force_thr = read_param("force_down", 208)
        self.setWindowTitle(self.t["title"])
        self.resize(760, 480)
        self.setStyleSheet("""
            QLabel#Caption { color: #8e8e93; font-size: 12px; }
            QLabel#Big { font-size: 40px; font-weight: 700; }
            QLabel#Small { font-size: 13px; }
            QProgressBar { background: rgba(128,128,128,0.18); border: none; border-radius: 3px; height: 6px; }
            QProgressBar::chunk { background: #0a84ff; border-radius: 3px; }
        """)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 28, 0)
        root.setSpacing(0)
        self.blob = Blob(state, self.force_thr)
        root.addWidget(self.blob, 1)

        panel = QVBoxLayout()
        panel.setContentsMargins(0, 36, 0, 36)
        panel.setSpacing(6)
        self.cap_p = QLabel(self.t["pressure"]); self.cap_p.setObjectName("Caption")
        self.big = QLabel("0"); self.big.setObjectName("Big")
        self.bar = QProgressBar(); self.bar.setRange(0, MAX_P); self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.peak = QLabel(); self.peak.setObjectName("Small")
        self.force_lbl = QLabel(); self.force_lbl.setObjectName("Small")
        self.click_lbl = QLabel(); self.click_lbl.setObjectName("Small")
        self.thr_lbl = QLabel(); self.thr_lbl.setObjectName("Caption")
        self.status = QLabel(); self.status.setObjectName("Caption"); self.status.setWordWrap(True)
        self.debug = QLabel(); self.debug.setObjectName("Caption"); self.debug.setWordWrap(True)
        panel.addSpacing(10)
        panel.addWidget(self.cap_p); panel.addWidget(self.big); panel.addWidget(self.bar)
        panel.addSpacing(14)
        panel.addWidget(self.peak); panel.addWidget(self.force_lbl); panel.addWidget(self.click_lbl)
        panel.addSpacing(14)
        panel.addWidget(self.thr_lbl); panel.addWidget(self.status); panel.addWidget(self.debug)
        panel.addStretch(1)
        root.addLayout(panel)

        self.pid_written = False
        os.makedirs(CONF_DIR, exist_ok=True)
        with open(PID_FILE, "w") as f:
            f.write(str(os.getpid()))
        self.pid_written = True

        self.refresh = QTimer(self)
        self.refresh.timeout.connect(self.update_panel)
        self.refresh.start(50)

    def closeEvent(self, event):
        try:
            if self.pid_written:
                os.remove(PID_FILE)
        except Exception:
            pass
        super().closeEvent(event)

    def update_panel(self):
        with self.state.lock:
            p, f, peak, found = self.state.pressure, self.state.force, self.state.peak, self.state.found
            events, error = self.state.events, self.state.error
        self.big.setText(f"{round(p / MAX_P * 100)}%")
        self.bar.setValue(p)
        self.peak.setText(f"{self.t['peak']}: {round(peak / MAX_P * 100)}%")
        self.force_lbl.setText(f"{self.t['force']}: {self.t['on'] if f else self.t['off']}")
        self.click_lbl.setText(f"{self.t['click']}: {self.t['on'] if p >= read_param('click1_down', 120) else self.t['off']}")
        self.thr_lbl.setText(f"{self.t['threshold']}: {self.force_thr} / {MAX_P}")
        self.status.setText("" if found else self.t["nofind"])
        self.debug.setText(f"{self.t['events']}: {events}" + (f"\n{self.t['err']}: {error}" if error else ""))

def main():
    app = QApplication(sys.argv)
    state = State()
    threading.Thread(target=reader, args=(state,), daemon=True).start()
    w = PressureWindow(state)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
