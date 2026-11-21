#!/usr/bin/env python3
import sys, os, glob, json, subprocess, time
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QSlider, QCheckBox, QPushButton, QFrame, QMessageBox)
from PyQt6.QtCore import Qt

PARAM_DIR = "/sys/module/hid_magicmouse/parameters"
DRAG_CONF = "/etc/linux-3-finger-drag/3fd-config.json"

def get_battery():
    for p in glob.glob("/sys/class/power_supply/*"):
        try:
            if "Trackpad" in open(f"{p}/model_name").read():
                cap = open(f"{p}/capacity").read().strip()
                st = open(f"{p}/status").read().strip()
                return f"🔋 {cap}% · {st}"
        except Exception:
            pass
    return "⚡ Bluetooth / USB активен"

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
        self.setWindowTitle("Magic Trackpad 2 — Control Center")
        self.setFixedWidth(530)
        self.setStyleSheet(STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(16)

        # Шапка
        hdr = QHBoxLayout()
        title_box = QVBoxLayout(); title_box.setSpacing(2)
        t = QLabel("Magic Trackpad 2"); t.setObjectName("HeaderTitle")
        sub = QLabel("Taptic Engine · Force Touch · Мультитач"); sub.setStyleSheet("color: #888; font-size: 12px;")
        title_box.addWidget(t); title_box.addWidget(sub)
        badge = QLabel(get_battery()); badge.setObjectName("Badge")
        hdr.addLayout(title_box); hdr.addStretch(); hdr.addWidget(badge, alignment=Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(hdr)

        # Карточка 1: Taptic Engine & Force Touch
        c1, l1 = self.make_card("Taptic Engine и Force Touch")
        ct = read_param("touch_tick", 18)
        self.chk_tick = QCheckBox("Тактильный микро-отклик при касании каждым пальцем")
        self.chk_tick.setChecked(ct > 0)
        l1.addWidget(self.chk_tick)
        self.st, self.vt = self.add_slider(l1, "Сила вибрации при касании", 6, 35, ct if ct > 0 else 18, "")
        self.st.setEnabled(ct > 0)

        l1.addWidget(self.divider())
        self.sp1, self.vp1 = self.add_slider(l1, "Усилие 1-го клика (порог)", 70, 160, read_param("click1_down", 120), "")
        self.sv1, self.vv1 = self.add_slider(l1, "Сила вибрации 1-го клика", 15, 63, read_param("click1_vib", 63), "")

        l1.addWidget(self.divider())
        self.sf, self.vf = self.add_slider(l1, "Усилие Force Touch (2-й клик)", 150, 245, read_param("force_down", 208), "")
        self.svf, self.vvf = self.add_slider(l1, "Сила вибрации Force Touch", 20, 63, read_param("force_vib", 63), "")
        root.addWidget(c1)

        # Карточка 2: Жесты и перетаскивание
        c2, l2 = self.make_card("Жесты и перетаскивание")
        self.chk_drag = QCheckBox("Перетаскивание окон и выделение текста 3 пальцами")
        self.chk_drag.setChecked(is_active("three-finger-drag.service"))
        l2.addWidget(self.chk_drag)

        try: dc = json.load(open(DRAG_CONF))
        except Exception: dc = {"acceleration": 1.0, "dragEndDelay": 150}
        self.sa, self.va = self.add_slider(l2, "Скорость перетаскивания", 5, 25, int(round(dc.get("acceleration", 1.0)*10)), "x", scale=0.1)
        self.sd, self.vd = self.add_slider(l2, "Задержка отпускания пальцев", 0, 350, int(dc.get("dragEndDelay", 150)), " мс")

        l2.addWidget(self.divider())
        self.chk_tap = QCheckBox("Тап 4 пальцами → Launchpad   |   Тап 5 пальцами → Рабочий стол")
        self.chk_tap.setChecked(is_active("four-finger-tap.service", True))
        l2.addWidget(self.chk_tap)
        root.addWidget(c2)

        # Нижняя панель кнопок
        btns = QHBoxLayout(); btns.setSpacing(10)
        b_bt = QPushButton("Переподключить BT"); b_bt.setObjectName("SecBtn")
        b_kde = QPushButton("Жесты KDE"); b_kde.setObjectName("SecBtn")
        b_sv = QPushButton("Сохранить навсегда"); b_sv.setObjectName("PrimaryBtn")
        btns.addWidget(b_bt); btns.addWidget(b_kde); btns.addStretch(); btns.addWidget(b_sv)
        root.addLayout(btns)

        # Живые сигналы (мгновенное применение!)
        self.chk_tick.toggled.connect(lambda c: (self.st.setEnabled(c), write_param("touch_tick", self.st.value() if c else 0)))
        self.st.valueChanged.connect(lambda v: (self.vt.setText(str(v)), write_param("touch_tick", v) if self.chk_tick.isChecked() else None))
        self.sp1.valueChanged.connect(lambda v: (self.vp1.setText(str(v)), write_param("click1_down", v)))
        self.sv1.valueChanged.connect(lambda v: (self.vv1.setText(str(v)), write_param("click1_vib", v)))
        self.sf.valueChanged.connect(lambda v: (self.vf.setText(str(v)), write_param("force_down", v), write_param("force_up", max(120, v-40))))
        self.svf.valueChanged.connect(lambda v: (self.vvf.setText(str(v)), write_param("force_vib", v)))
        self.chk_drag.toggled.connect(self.toggle_drag)
        self.sa.valueChanged.connect(lambda v: self.va.setText(f"{v*0.1:.1f}x"))
        self.sd.valueChanged.connect(lambda v: self.vd.setText(f"{v} мс"))
        self.chk_tap.toggled.connect(lambda c: subprocess.run(["systemctl", "--user", "enable" if c else "disable", "--now", "four-finger-tap.service"]))
        b_bt.clicked.connect(self.re_bt)
        b_kde.clicked.connect(lambda: subprocess.Popen(["kcmshell6", "kcm_touchpad"]))
        b_sv.clicked.connect(self.save_all)

    def make_card(self, title_text):
        card = QFrame(); card.setObjectName("Card")
        lay = QVBoxLayout(card); lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(10)
        lbl = QLabel(title_text); lbl.setObjectName("CardTitle"); lay.addWidget(lbl)
        return card, lay

    def divider(self):
        d = QFrame(); d.setObjectName("Divider"); d.setFrameShape(QFrame.Shape.HLine); return d

    def add_slider(self, parent_lay, text, mn, mx, val, suffix, scale=1):
        row = QHBoxLayout(); row.setSpacing(12)
        lbl = QLabel(text); lbl.setFixedWidth(210)
        sld = QSlider(Qt.Orientation.Horizontal); sld.setRange(mn, mx); sld.setValue(val)
        pill = QLabel(f"{val*scale:.1f}{suffix}" if scale != 1 else f"{val}{suffix}")
        pill.setObjectName("ValPill"); pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(lbl); row.addWidget(sld); row.addWidget(pill)
        parent_lay.addLayout(row)
        return sld, pill

    def toggle_drag(self, c):
        subprocess.run(["sudo", "systemctl", "start" if c else "stop", "three-finger-drag.service"])
        time.sleep(1.2)
        subprocess.run(["systemctl", "--user", "restart", "four-finger-tap.service"])

    def re_bt(self):
        subprocess.run(["sudo", "systemctl", "restart", "bluetooth"]); time.sleep(2)
        if self.chk_drag.isChecked(): subprocess.run(["sudo", "systemctl", "restart", "three-finger-drag.service"]); time.sleep(1.2)
        subprocess.run(["systemctl", "--user", "restart", "four-finger-tap.service"])
        QMessageBox.information(self, "Готово", "Службы Bluetooth и трекпада перезапущены!")

    def save_all(self):
        tv = self.st.value() if self.chk_tick.isChecked() else 0
        p1, v1 = self.sp1.value(), self.sv1.value()
        fd, fv = self.sf.value(), self.svf.value()
        fu = max(120, fd - 40)
        mc = f"options hid_magicmouse host_click=on button_down_param=0x783f0b0b button_up_param=0x55250808 click1_down={p1} click1_vib={v1} force_down=0x{fd:02X} force_up=0x{fu:02X} force_vib={fv} touch_tick={tv}\n"
        subprocess.run(["sudo", "tee", "/etc/modprobe.d/hid-magicmouse.conf"], input=mc.encode(), stdout=subprocess.DEVNULL)
        dc = json.dumps({"acceleration": round(self.sa.value()*0.1, 1), "dragEndDelay": self.sd.value()}, indent=2) + "\n"
        subprocess.run(["sudo", "tee", DRAG_CONF], input=dc.encode(), stdout=subprocess.DEVNULL)
        if self.chk_drag.isChecked():
            subprocess.run(["sudo", "systemctl", "restart", "three-finger-drag.service"]); time.sleep(1.2)
        subprocess.run(["systemctl", "--user", "restart", "four-finger-tap.service"])
        QMessageBox.information(self, "Сохранено", "Все параметры вибрации, порогов и жестов сохранены навсегда!")

if __name__ == "__main__":
    app = QApplication(sys.argv); w = TrackpadApp(); w.show(); sys.exit(app.exec())
