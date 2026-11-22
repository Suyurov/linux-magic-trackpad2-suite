#!/usr/bin/env python3
"""Pressure test: a soft circle grows with the press, and a Force Touch changes its colour."""
import sys, os, time, threading, math, json
import evdev
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QPainter, QRadialGradient, QColor, QPen, QPainterPath, QPixmap

PARAM_DIR = "/sys/module/hid_magicmouse/parameters"
CONF_DIR = os.path.expanduser("~/.config/magic-trackpad-suite")
CONF_FILE = os.path.join(CONF_DIR, "control-center.conf")
PID_FILE = os.path.join(CONF_DIR, "pressure.pid")   # tells the gesture daemon to ignore Force Touch binds
GESTURES_FILE = os.path.join(CONF_DIR, "gestures.json")
PULSE_PARAM = "/sys/module/hid_magicmouse/parameters/pulse"
FORCE_HOLD_S = 0.225     # hold this long past Force Touch before the two taps
TAP_GAP_S = 0.100        # gap between the two taps
TAP_LOOK_S = 0.03        # width of each tap in the animation
MAX_P = 253
RING_FRAC = 0.36                 # progress ring radius, fixed
SPRITE_UNIT = 150                # pixel radius of the pre-rendered bubble
BUBBLE_MIN, BUBBLE_MAX = 0.22, 0.70   # bubble radius as a share of the ring
# three stages, each going from a dim shade (just entered) to a bright one (near the next stage)
GREEN_DIM, GREEN_BRIGHT = QColor("#c2f29c"), QColor("#2fc548")    # salad green -> grass green
ORANGE_DIM, ORANGE_BRIGHT = QColor("#ffd29a"), QColor("#ff9500")  # pale orange -> vivid orange
RED_DIM, RED_BRIGHT = QColor("#ffb8b0"), QColor("#ff2d20")        # pale red -> vivid red

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

def load_gestures_file():
    try:
        with open(GESTURES_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def force_tap_strength():
    data = load_gestures_file()
    if "force_feedback_strength" in data:
        return int(data["force_feedback_strength"])
    return max(1, int(read_param("force_vib", 63) * 0.75))

def haptic_pulse(strength):
    try:
        with open(PULSE_PARAM, "w") as f:
            f.write(str(strength))
    except Exception:
        pass

def fire_force_taps(strength):
    haptic_pulse(strength)
    time.sleep(TAP_GAP_S)
    haptic_pulse(strength)

def read_param(name, default):
    try:
        return int(open(f"{PARAM_DIR}/{name}").read().strip())
    except Exception:
        return default

def find_trackpad():
    """Prefer the proxy device: linux-3-finger-drag grabs the real one, so its events
    never reach other readers. The gesture daemon reads the proxy too."""
    proxy, real = None, None
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
        except Exception:
            continue
        if "Magic Trackpad" not in dev.name:
            continue
        if evdev.ecodes.ABS_MT_PRESSURE not in dev.capabilities(absinfo=False).get(evdev.ecodes.EV_ABS, []):
            continue
        if "proxy" in (dev.phys or ""):
            proxy = proxy or dev
        else:
            real = real or dev
    return proxy or real

class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.pressure = 0
        self.force = False
        self.peak = 0
        self.found = False
        self.events = 0
        self.error = None
        self.device = None
        self.click_seq = 0     # increases on every physical click
        self.force_seq = 0     # increases on every Force Touch

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
            state.device = f"{dev.path} ({dev.phys})" if dev else None
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
                    if ev.code == evdev.ecodes.BTN_LEFT and ev.value == 1:
                        with state.lock:
                            state.click_seq += 1
                    elif ev.code == evdev.ecodes.BTN_TRIGGER_HAPPY1:
                        with state.lock:
                            state.force = ev.value == 1
                            if ev.value == 1:
                                state.force_seq += 1
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

def _rgbf(c):
    return (c.redF() * 255, c.greenF() * 255, c.blueF() * 255)

def _mixf(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))

def target_rgb(p, click_thr, force_thr):
    """Colour as float RGB (0-255) so the ramp is continuous, not stepped."""
    if p < click_thr:
        t = min(1.0, max(0.0, p / max(1.0, click_thr)))
        return _mixf(_rgbf(GREEN_DIM), _rgbf(GREEN_BRIGHT), t)
    if p < force_thr:
        t = min(1.0, max(0.0, (p - click_thr) / max(1.0, force_thr - click_thr)))
        return _mixf(_rgbf(ORANGE_DIM), _rgbf(ORANGE_BRIGHT), t)
    t = min(1.0, max(0.0, (p - force_thr) / max(1.0, MAX_P - force_thr)))
    return _mixf(_rgbf(RED_DIM), _rgbf(RED_BRIGHT), t)

def beat_curve(t):
    """Heartbeat shape on t in [0, 1]: a sharp first beat and a softer second one."""
    first = math.exp(-((t - 0.12) / 0.10) ** 2)
    second = 0.6 * math.exp(-((t - 0.42) / 0.13) ** 2)
    return first + second

class Blob(QWidget):
    """Soft circle: radius follows pressure smoothly, colour switches quickly on Force Touch."""
    def __init__(self, state, click_thr, force_thr, parent=None):
        super().__init__(parent)
        self.state = state
        self.click_thr = click_thr
        self.force_thr = force_thr
        self.radius = 0.0
        self.rgb = _rgbf(GREEN_DIM)
        self.colour = QColor(GREEN_DIM)
        self.sprite = None         # bubble image, redrawn only when its colour changes
        self.sprite_rgb = None
        self.norm = 0.0
        self.last_step = time.monotonic()
        self.ripples = []          # start times of Force Touch ripples
        self.beat = None           # (start time, duration, amplitude)
        self.force_t0 = None       # when a Force Touch started (only while it is held)
        self.force_fired = False
        self.force_strength = 40
        self.seen_click = 0
        self.seen_force = 0
        self.simulated = None      # used only for offline screenshots
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.step)
        self.timer.start(16)

    def step(self):
        now = time.monotonic()
        dt = min(0.1, now - self.last_step)
        self.last_step = now
        k = 1.0 - math.exp(-dt * 8.0)     # ~ the old 0.12 per 16 ms, but tied to real time
        if self.simulated is not None:
            p, f = self.simulated
            click_seq = force_seq = 0
        else:
            with self.state.lock:
                p, f = self.state.pressure, self.state.force
                click_seq, force_seq = self.state.click_seq, self.state.force_seq
        # heartbeat in time with the physical click and with Force Touch
        if click_seq != self.seen_click:
            self.seen_click = click_seq
            self.beat = (now, 0.34, 0.10)
        if force_seq != self.seen_force:
            self.seen_force = force_seq
            self.ripples.append(now)
            if load_gestures_file().get("feedback", True):
                self.force_t0 = now
                self.force_fired = False
                self.force_strength = force_tap_strength()
        if not f:
            self.force_t0 = None          # released early: no confirmation taps
        if self.force_t0 is not None and not self.force_fired and now - self.force_t0 >= FORCE_HOLD_S:
            self.force_fired = True
            threading.Thread(target=fire_force_taps, args=(self.force_strength,), daemon=True).start()
        side = min(self.width(), self.height())
        base_ring = side * RING_FRAC
        r_min, r_max = base_ring * BUBBLE_MIN, base_ring * BUBBLE_MAX
        norm = min(p / MAX_P, 1.0)
        self.norm += (norm - self.norm) * k                 # smooth the raw sensor values
        target = r_min + (r_max - r_min) * (self.norm ** 0.85)
        self.radius += (target - self.radius) * (1.0 - math.exp(-dt * 11.0))   # smooth growth
        goal = target_rgb(self.norm * MAX_P, self.click_thr, self.force_thr)
        self.rgb = _mixf(self.rgb, goal, 1.0 - math.exp(-dt * 11.0))   # smooth colour change, no jumps
        self.colour = QColor(int(self.rgb[0]), int(self.rgb[1]), int(self.rgb[2]))
        self.beat_scale = 1.0
        if self.beat:
            t0, dur, amp = self.beat
            t = (now - t0) / dur
            if t >= 1.0:
                self.beat = None
            else:
                self.beat_scale = 1.0 + amp * beat_curve(t)
        if self.force_t0 is not None:
            # two bumps exactly where the two taps are sent
            rel = now - self.force_t0
            tap = (math.exp(-((rel - FORCE_HOLD_S) / TAP_LOOK_S) ** 2)
                   + 0.8 * math.exp(-((rel - FORCE_HOLD_S - TAP_GAP_S) / TAP_LOOK_S) ** 2))
            self.beat_scale += 0.12 * tap
        self.update()

    def make_sprite(self, rgb):
        size = int(SPRITE_UNIT * 2.4)
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        q = QPainter(pix)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = size / 2
        q.setPen(Qt.PenStyle.NoPen)
        q.setBrush(QColor(int(rgb[0]), int(rgb[1]), int(rgb[2])))
        q.setOpacity(1.0)
        q.drawEllipse(QPointF(c, c), SPRITE_UNIT, SPRITE_UNIT)     # solid, flat circle
        q.end()
        self.sprite = pix
        self.sprite_rgb = tuple(rgb)

    def paintEvent(self, _):
        now = time.monotonic()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        cx, cy = self.width() / 2, self.height() / 2
        R = max(self.radius * getattr(self, "beat_scale", 1.0), 1.0)
        base = QColor(self.colour)
        p.setPen(Qt.PenStyle.NoPen)

        # liquid body: a flat circle, drawn from the cached image
        # bubble: pre-rendered once per colour change, then only scaled each frame
        if self.sprite is None or max(abs(a - b) for a, b in zip(self.sprite_rgb or (0, 0, 0), self.rgb)) > 2:
            self.make_sprite(self.rgb)
        a = 0.08 * self.norm                       # liquid breathing: squash and stretch
        sx = 1 + a * math.sin(now * 2.1)
        sy = 1 + a * math.sin(now * 2.1 + 1.6)
        k = R / SPRITE_UNIT
        p.save()
        p.translate(cx, cy)
        p.scale(k * sx, k * sy)
        p.drawPixmap(QPointF(-self.sprite.width() / 2, -self.sprite.height() / 2), self.sprite)
        p.restore()

        # progress ring with the pressure percentage
        side = min(self.width(), self.height())
        rr = max(side * 0.20, R * 1.5)          # grows with the bubble
        rect = QRectF(cx - rr, cy - rr, 2 * rr, 2 * rr)
        track = QPen(QColor(128, 128, 128, 45), 3)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(track); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)
        arc = QPen(base, 3)
        arc.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc)
        p.drawArc(rect, 90 * 16, -int(self.norm * 360 * 16))

        # short ripple on Force Touch
        alive = []
        for t0 in self.ripples:
            age = (now - t0) / 0.7
            if age >= 1.0:
                continue
            alive.append(t0)
            rp = R * (1.1 + 1.5 * age)
            col = QColor(base); col.setAlpha(int(170 * (1 - age)))
            p.setPen(QPen(col, 2.0)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), rp, rp)
        self.ripples = alive
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
        self.click_thr = read_param("click1_down", 120)
        self.blob = Blob(state, self.click_thr, self.force_thr)
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
            events, error, device = self.state.events, self.state.error, self.state.device
        self.big.setText(f"{round(p / MAX_P * 100)}%")
        self.bar.setValue(p)
        self.peak.setText(f"{self.t['peak']}: {round(peak / MAX_P * 100)}%")
        self.force_lbl.setText(f"{self.t['force']}: {self.t['on'] if f else self.t['off']}")
        self.click_lbl.setText(f"{self.t['click']}: {self.t['on'] if p >= read_param('click1_down', 120) else self.t['off']}")
        self.thr_lbl.setText(f"{self.t['threshold']}: {self.force_thr} / {MAX_P}")
        self.status.setText("" if found else self.t["nofind"])
        self.debug.setText(f"{device or ''}\n{self.t['events']}: {events}" + (f"\n{self.t['err']}: {error}" if error else ""))

def main():
    app = QApplication(sys.argv)
    state = State()
    threading.Thread(target=reader, args=(state,), daemon=True).start()
    w = PressureWindow(state)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
