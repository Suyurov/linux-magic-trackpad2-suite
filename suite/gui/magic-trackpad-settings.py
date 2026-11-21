#!/usr/bin/env python3
import sys, glob, json, subprocess, time
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QSlider, QCheckBox, QPushButton, QFrame,
                             QMessageBox, QComboBox)
from PyQt6.QtCore import Qt, QSettings

PARAM_DIR = "/sys/module/hid_magicmouse/parameters"
DRAG_CONF = "/etc/linux-3-finger-drag/3fd-config.json"
DEFAULT_LANG = "ru"
LANGS = {"ru": "Русский", "en": "English"}

STRINGS = {
    "ru": {
        "window_title": "Magic Trackpad 2 — Control Center",
        "app_name": "Magic Trackpad 2",
        "subtitle": "Taptic Engine · Force Touch · Мультитач",
        "battery": "🔋 {cap}% · {st}",
        "no_battery": "⚡ Bluetooth / USB активен",
        "ms": "мс",
        "card_taptic": "Taptic Engine и Force Touch",
        "chk_tick": "Тактильный микро-отклик при касании каждым пальцем",
        "sl_tick_strength": "Сила вибрации при касании",
        "sl_click_thr": "Усилие 1-го клика (порог)",
        "sl_click_vib": "Сила вибрации 1-го клика",
        "sl_force_thr": "Усилие Force Touch (2-й клик)",
        "sl_force_vib": "Сила вибрации Force Touch",
        "card_gestures": "Жесты и перетаскивание",
        "chk_drag": "Перетаскивание окон и выделение текста 3 пальцами",
        "sl_drag_speed": "Скорость перетаскивания",
        "sl_drag_delay": "Задержка отпускания пальцев",
        "chk_tap": "Тап 4 пальцами → Launchpad   |   Тап 5 пальцами → Рабочий стол",
        "btn_bt": "Переподключить BT",
        "btn_kde": "Жесты KDE",
        "btn_save": "Сохранить навсегда",
        "done_title": "Готово",
        "done_text": "Службы Bluetooth и трекпада перезапущены!",
        "saved_title": "Сохранено",
        "saved_text": "Все параметры вибрации, порогов и жестов сохранены навсегда!",
    },
    "en": {
        "window_title": "Magic Trackpad 2 — Control Center",
        "app_name": "Magic Trackpad 2",
        "subtitle": "Taptic Engine · Force Touch · Multi-touch",
        "battery": "🔋 {cap}% · {st}",
        "no_battery": "⚡ Bluetooth / USB active",
        "ms": "ms",
        "card_taptic": "Taptic Engine and Force Touch",
        "chk_tick": "Subtle haptic tick when each finger touches down",
        "sl_tick_strength": "Touch tick strength",
        "sl_click_thr": "Click 1 pressure (threshold)",
        "sl_click_vib": "Click 1 vibration strength",
        "sl_force_thr": "Force Touch pressure (2nd click)",
        "sl_force_vib": "Force Touch vibration strength",
        "card_gestures": "Gestures and dragging",
        "chk_drag": "Drag windows and select text with 3 fingers",
        "sl_drag_speed": "Drag speed",
        "sl_drag_delay": "Finger release delay",
        "chk_tap": "4-finger tap → Launchpad   |   5-finger tap → Show Desktop",
        "btn_bt": "Reconnect BT",
        "btn_kde": "KDE gestures",
        "btn_save": "Save permanently",
        "done_title": "Done",
        "done_text": "Bluetooth and trackpad services restarted!",
        "saved_title": "Saved",
        "saved_text": "All vibration, threshold and gesture settings saved permanently!",
    },
}


def T(lang, key, **kw):
    table = STRINGS.get(lang, STRINGS[DEFAULT_LANG])
    text = table.get(key) or STRINGS[DEFAULT_LANG][key]
    return text.format(**kw) if kw else text


def get_battery(lang):
    for p in glob.glob("/sys/class/power_supply/*"):
        try:
            if "Trackpad" in open(f"{p}/model_name").read():
                cap = open(f"{p}/capacity").read().strip()
                st = open(f"{p}/status").read().strip()
                return T(lang, "battery", cap=cap, st=st)
        except Exception:
            pass
    return T(lang, "no_battery")


def read_param(n, d=0):
    try: return int(open(f"{PARAM_DIR}/{n}").read().strip())
    except Exception: return d


def write_param(n, v):
    try:
        with open(f"{PARAM_DIR}/{n}", "w") as f: f.write(str(v))
    except Exception:
        subprocess.run(["sudo", "tee", f"{PARAM_DIR}/{n}"], input=f"{v}\n".encode(), stdout=subprocess.DEVNULL)


def is_active(s, u=False):
    return subprocess.run(["systemctl"] + (["--user"] if u else []) + ["is-active", "--quiet", s]).returncode == 0


STYLE = """
QWidget { font-family: 'SF Pro Text', 'Inter', sans-serif; font-size: 13px; }
QLabel#HeaderTitle { font-size: 20px; font-weight: 700; }
QLabel#Badge { background: rgba(0, 122, 255, 0.14); color: #007AFF; border-radius: 10px; padding: 4px 10px; font-weight: 600; font-size: 12px; }
QLabel#CardTitle { font-size: 13px; font-weight: 700; color: #007AFF; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
QLabel#ValPill { background: rgba(128, 128, 128, 0.14); border-radius: 6px; padding: 2px 8px; font-weight: 600; min-width: 48px; }
QFrame#Card { background: rgba(128, 128, 128, 0.07); border: 1px solid rgba(128, 128, 128, 0.18); border-radius: 12px; }
QFrame#Divider { background: rgba(128, 128, 128, 0.15); max-height: 1px; }
QSlider::groove:horizontal { height: 5px; background: rgba(128, 128, 128, 0.25); border-radius: 2px; }
QSlider::sub-page:horizontal { background: #007AFF; border-radius: 2px; }
QSlider::handle:horizontal { background: white; border: 1px solid rgba(0,0,0,0.2); width: 16px; height: 16px; margin: -6px 0; border-radius: 8px; }
QPushButton#PrimaryBtn { background: #007AFF; color: white; border-radius: 8px; padding: 9px 18px; font-weight: 600; }
QPushButton#PrimaryBtn:hover { background: #0063D1; }
QPushButton#SecBtn { background: rgba(128, 128, 128, 0.12); border: 1px solid rgba(128, 128, 128, 0.2); border-radius: 8px; padding: 9px 14px; }
QPushButton#SecBtn:hover { background: rgba(128, 128, 128, 0.2); }
"""


class TrackpadApp(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("magic-trackpad-suite", "control-center")
        saved = self.settings.value("lang", DEFAULT_LANG)
        self.lang = saved if saved in LANGS else DEFAULT_LANG

        self.setFixedWidth(530)
        self.setStyleSheet(STYLE)
        self.L = {}        # key -> widget that shows STRINGS[key]
        self.pills = []    # (pill label, slider, formatter)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        title_box = QVBoxLayout(); title_box.setSpacing(2)
        self.L["app_name"] = QLabel(); self.L["app_name"].setObjectName("HeaderTitle")
        self.L["subtitle"] = QLabel(); self.L["subtitle"].setStyleSheet("color: #888; font-size: 12px;")
        title_box.addWidget(self.L["app_name"]); title_box.addWidget(self.L["subtitle"])
        self.badge = QLabel(); self.badge.setObjectName("Badge")
        self.lang_box = QComboBox()
        for code, name in LANGS.items():
            self.lang_box.addItem(name, code)
        self.lang_box.setCurrentIndex(self.lang_box.findData(self.lang))
        hdr.addLayout(title_box); hdr.addStretch()
        hdr.addWidget(self.badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        hdr.addWidget(self.lang_box, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(hdr)

        # Card 1: Taptic Engine & Force Touch
        c1, l1 = self.make_card("card_taptic")
        ct = read_param("touch_tick", 18)
        self.chk_tick = QCheckBox(); self.L["chk_tick"] = self.chk_tick
        self.chk_tick.setChecked(ct > 0)
        l1.addWidget(self.chk_tick)
        self.st, _ = self.add_slider(l1, "sl_tick_strength", 6, 35, ct if ct > 0 else 18)
        self.st.setEnabled(ct > 0)

        l1.addWidget(self.divider())
        self.sp1, _ = self.add_slider(l1, "sl_click_thr", 70, 160, read_param("click1_down", 120))
        self.sv1, _ = self.add_slider(l1, "sl_click_vib", 15, 63, read_param("click1_vib", 63))

        l1.addWidget(self.divider())
        self.sf, _ = self.add_slider(l1, "sl_force_thr", 150, 245, read_param("force_down", 208))
        self.svf, _ = self.add_slider(l1, "sl_force_vib", 20, 63, read_param("force_vib", 63))
        root.addWidget(c1)

        # Card 2: Gestures & dragging
        c2, l2 = self.make_card("card_gestures")
        self.chk_drag = QCheckBox(); self.L["chk_drag"] = self.chk_drag
        self.chk_drag.setChecked(is_active("three-finger-drag.service"))
        l2.addWidget(self.chk_drag)

        try: dc = json.load(open(DRAG_CONF))
        except Exception: dc = {"acceleration": 1.0, "dragEndDelay": 150}
        self.sa, _ = self.add_slider(l2, "sl_drag_speed", 5, 25,
                                     int(round(dc.get("acceleration", 1.0) * 10)),
                                     lambda v: f"{v * 0.1:.1f}x")
        self.sd, _ = self.add_slider(l2, "sl_drag_delay", 0, 350,
                                     int(dc.get("dragEndDelay", 150)),
                                     lambda v: f"{v} {T(self.lang, 'ms')}")

        l2.addWidget(self.divider())
        self.chk_tap = QCheckBox(); self.L["chk_tap"] = self.chk_tap
        self.chk_tap.setChecked(is_active("four-finger-tap.service", True))
        l2.addWidget(self.chk_tap)
        root.addWidget(c2)

        # Bottom buttons
        btns = QHBoxLayout(); btns.setSpacing(10)
        self.b_bt = QPushButton(); self.b_bt.setObjectName("SecBtn"); self.L["btn_bt"] = self.b_bt
        self.b_kde = QPushButton(); self.b_kde.setObjectName("SecBtn"); self.L["btn_kde"] = self.b_kde
        self.b_sv = QPushButton(); self.b_sv.setObjectName("PrimaryBtn"); self.L["btn_save"] = self.b_sv
        btns.addWidget(self.b_bt); btns.addWidget(self.b_kde); btns.addStretch(); btns.addWidget(self.b_sv)
        root.addLayout(btns)

        # Live signals (apply immediately)
        self.chk_tick.toggled.connect(lambda c: (self.st.setEnabled(c), write_param("touch_tick", self.st.value() if c else 0)))
        self.st.valueChanged.connect(lambda v: write_param("touch_tick", v) if self.chk_tick.isChecked() else None)
        self.sp1.valueChanged.connect(lambda v: write_param("click1_down", v))
        self.sv1.valueChanged.connect(lambda v: write_param("click1_vib", v))
        self.sf.valueChanged.connect(lambda v: (write_param("force_down", v), write_param("force_up", max(120, v - 40))))
        self.svf.valueChanged.connect(lambda v: write_param("force_vib", v))
        self.chk_drag.toggled.connect(self.toggle_drag)
        self.chk_tap.toggled.connect(lambda c: subprocess.run(["systemctl", "--user", "enable" if c else "disable", "--now", "four-finger-tap.service"]))
        self.b_bt.clicked.connect(self.re_bt)
        self.b_kde.clicked.connect(lambda: subprocess.Popen(["kcmshell6", "kcm_touchpad"]))
        self.b_sv.clicked.connect(self.save_all)
        self.lang_box.currentIndexChanged.connect(self.change_language)

        self.retranslate()

    # ---- helpers -------------------------------------------------------

    def make_card(self, key):
        card = QFrame(); card.setObjectName("Card")
        lay = QVBoxLayout(card); lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(10)
        lbl = QLabel(); lbl.setObjectName("CardTitle"); self.L[key] = lbl
        lay.addWidget(lbl)
        return card, lay

    def divider(self):
        d = QFrame(); d.setObjectName("Divider"); d.setFrameShape(QFrame.Shape.HLine); return d

    def add_slider(self, parent_lay, key, mn, mx, val, fmt=None):
        if fmt is None:
            fmt = lambda v: str(v)
        row = QHBoxLayout(); row.setSpacing(12)
        lbl = QLabel(); lbl.setFixedWidth(210); self.L[key] = lbl
        sld = QSlider(Qt.Orientation.Horizontal); sld.setRange(mn, mx); sld.setValue(val)
        pill = QLabel(fmt(val)); pill.setObjectName("ValPill"); pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sld.valueChanged.connect(lambda v: pill.setText(fmt(v)))
        self.pills.append((pill, sld, fmt))
        row.addWidget(lbl); row.addWidget(sld); row.addWidget(pill)
        parent_lay.addLayout(row)
        return sld, pill

    # ---- language ------------------------------------------------------

    def change_language(self, index):
        self.lang = self.lang_box.itemData(index)
        self.settings.setValue("lang", self.lang)
        self.retranslate()

    def retranslate(self):
        lang = self.lang
        self.setWindowTitle(T(lang, "window_title"))
        for key, widget in self.L.items():
            widget.setText(T(lang, key))
        self.badge.setText(get_battery(lang))
        for pill, sld, fmt in self.pills:
            pill.setText(fmt(sld.value()))

    # ---- actions -------------------------------------------------------

    def toggle_drag(self, c):
        subprocess.run(["sudo", "systemctl", "start" if c else "stop", "three-finger-drag.service"])
        time.sleep(1.2)
        subprocess.run(["systemctl", "--user", "restart", "four-finger-tap.service"])

    def re_bt(self):
        subprocess.run(["sudo", "systemctl", "restart", "bluetooth"]); time.sleep(2)
        if self.chk_drag.isChecked():
            subprocess.run(["sudo", "systemctl", "restart", "three-finger-drag.service"]); time.sleep(1.2)
        subprocess.run(["systemctl", "--user", "restart", "four-finger-tap.service"])
        QMessageBox.information(self, T(self.lang, "done_title"), T(self.lang, "done_text"))

    def save_all(self):
        tv = self.st.value() if self.chk_tick.isChecked() else 0
        p1, v1 = self.sp1.value(), self.sv1.value()
        fd, fv = self.sf.value(), self.svf.value()
        fu = max(120, fd - 40)
        mc = f"options hid_magicmouse host_click=on button_down_param=0x783f0b0b button_up_param=0x55250808 click1_down={p1} click1_vib={v1} force_down=0x{fd:02X} force_up=0x{fu:02X} force_vib={fv} touch_tick={tv}\n"
        subprocess.run(["sudo", "tee", "/etc/modprobe.d/hid-magicmouse.conf"], input=mc.encode(), stdout=subprocess.DEVNULL)
        dc = json.dumps({"acceleration": round(self.sa.value() * 0.1, 1), "dragEndDelay": self.sd.value()}, indent=2) + "\n"
        subprocess.run(["sudo", "tee", DRAG_CONF], input=dc.encode(), stdout=subprocess.DEVNULL)
        if self.chk_drag.isChecked():
            subprocess.run(["sudo", "systemctl", "restart", "three-finger-drag.service"]); time.sleep(1.2)
        subprocess.run(["systemctl", "--user", "restart", "four-finger-tap.service"])
        QMessageBox.information(self, T(self.lang, "saved_title"), T(self.lang, "saved_text"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = TrackpadApp()
    w.show()
    sys.exit(app.exec())
