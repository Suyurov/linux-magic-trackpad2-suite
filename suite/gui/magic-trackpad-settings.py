#!/usr/bin/env python3
import sys, os, glob, json, subprocess, time, shutil
from string import Template
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QSlider, QPushButton, QFrame, QMessageBox,
                             QComboBox, QAbstractButton, QListWidget, QListWidgetItem,
                             QStackedWidget, QScrollArea, QLineEdit)
from PyQt6.QtCore import Qt, QSettings, QRectF
from PyQt6.QtGui import QPainter, QColor, QIcon

PARAM_DIR = "/sys/module/hid_magicmouse/parameters"
DRAG_CONF = "/etc/linux-3-finger-drag/3fd-config.json"
DEFAULT_LANG = "ru"
LANGS = {"ru": "Русский", "en": "English"}
CONF_DIR = os.path.expanduser("~/.config/magic-trackpad-suite")
GESTURES_FILE = os.path.join(CONF_DIR, "gestures.json")
ACTION_KEYS = ["launchpad", "show_desktop", "none", "custom"]
GESTURE_DEFAULTS = {"four": "launchpad", "five": "show_desktop", "force": "click"}
FORCE_KEYS = ["click", "context", "none", "custom"]
FORCE_MODE = {"click": 0}   # everything else -> 3: the daemon sends clicks itself

STRINGS = {
    "ru": {
        "window_title": "Magic Trackpad 2",
        "app_name": "Magic Trackpad 2",
        "subtitle": "Taptic Engine · Force Touch",
        "battery": "{cap}% · {st}",
        "no_battery": "Bluetooth / USB",
        "ms": "мс",
        "nav_taptic": "Taptic Engine",
        "nav_gestures": "Жесты",
        "nav_general": "Основные",
        "grp_touch": "Касание",
        "grp_click": "Клик",
        "grp_force": "Force Touch",
        "grp_drag": "Перетаскивание",
        "grp_taps": "Тапы",
        "grp_interface": "Интерфейс",
        "chk_tick": "Тактильный отклик при касании",
        "sl_tick_strength": "Сила отклика",
        "sl_click_thr": "Усилие нажатия",
        "sl_click_vib": "Сила вибрации",
        "sl_force_thr": "Усилие нажатия",
        "sl_force_vib": "Сила вибрации",
        "chk_drag": "Перетаскивание тремя пальцами",
        "sl_drag_speed": "Скорость",
        "sl_drag_delay": "Задержка отпускания",
        "chk_tap": "Тапы 4 и 5 пальцами",
        "gest_four": "4 пальца",
        "gest_five": "5 пальцев",
        "act_launchpad": "Launchpad",
        "act_show_desktop": "Показать рабочий стол",
        "act_none": "Ничего",
        "act_custom": "Своя команда",
        "cmd_placeholder": "Например: firefox",
        "note_actions": "Своя команда запускается в оболочке. Сочетания клавиш пока не поддерживаются.",
        "force_action": "Действие при Force Touch",
        "act_click": "Обычный клик",
        "act_middle": "Средняя кнопка",
        "act_context": "Контекстное меню",
        "grp_feedback": "Отклик",
        "row_feedback": "Тактильный сигнал при Force Touch",
        "row_sound": "Звук при действии",
        "note_feedback": "Два толчка, если держать палец около 0,25 с после сильного нажатия.",
        "lang_label": "Язык",
        "note_touch": "Короткий тик каждый раз, когда палец касается поверхности.",
        "note_click": "Меньшее усилие означает, что клик срабатывает легче.",
        "note_force": "Более сильное нажатие для второго, глубокого клика.",
        "note_drag": "Перетаскивание и выделение без удержания кнопки.",
        "note_general": "Выбранный язык сохраняется между запусками.",
        "btn_bt": "Переподключить BT",
        "btn_kde": "Жесты KDE",
        "btn_save": "Сохранить",
        "btn_pressure": "Тест давления",
        "done_title": "Готово",
        "done_text": "Службы Bluetooth и трекпада перезапущены.",
        "saved_title": "Сохранено",
        "saved_text": "Настройки вибрации, порогов и жестов сохранены.",
    },
    "en": {
        "window_title": "Magic Trackpad 2",
        "app_name": "Magic Trackpad 2",
        "subtitle": "Taptic Engine · Force Touch",
        "battery": "{cap}% · {st}",
        "no_battery": "Bluetooth / USB",
        "ms": "ms",
        "nav_taptic": "Taptic Engine",
        "nav_gestures": "Gestures",
        "nav_general": "General",
        "grp_touch": "Touch",
        "grp_click": "Click",
        "grp_force": "Force Touch",
        "grp_drag": "Dragging",
        "grp_taps": "Taps",
        "grp_interface": "Interface",
        "chk_tick": "Haptic feedback on touch",
        "sl_tick_strength": "Feedback strength",
        "sl_click_thr": "Press pressure",
        "sl_click_vib": "Vibration strength",
        "sl_force_thr": "Press pressure",
        "sl_force_vib": "Vibration strength",
        "chk_drag": "Three-finger drag",
        "sl_drag_speed": "Speed",
        "sl_drag_delay": "Release delay",
        "chk_tap": "4 and 5 finger taps",
        "gest_four": "4 fingers",
        "gest_five": "5 fingers",
        "act_launchpad": "Launchpad",
        "act_show_desktop": "Show Desktop",
        "act_none": "Nothing",
        "act_custom": "Custom command",
        "cmd_placeholder": "e.g. firefox",
        "note_actions": "A custom command runs in your shell. Key shortcuts are not supported yet.",
        "force_action": "Force Touch action",
        "act_click": "Regular click",
        "act_middle": "Middle click",
        "act_context": "Context menu",
        "grp_feedback": "Feedback",
        "row_feedback": "Haptic signal on Force Touch",
        "row_sound": "Sound on action",
        "note_feedback": "Two taps if you hold for about 0.25 s after a firm press.",
        "lang_label": "Language",
        "note_touch": "A short tick each time a finger touches the surface.",
        "note_click": "Lower pressure means the click triggers more easily.",
        "note_force": "A firmer press for the second, deeper click.",
        "note_drag": "Drag and select without holding the button down.",
        "note_general": "Your language choice is remembered between launches.",
        "btn_bt": "Reconnect BT",
        "btn_kde": "KDE gestures",
        "btn_save": "Save",
        "btn_pressure": "Pressure test",
        "done_title": "Done",
        "done_text": "Bluetooth and trackpad services restarted.",
        "saved_title": "Saved",
        "saved_text": "Vibration, threshold and gesture settings saved.",
    },
}

# Colour palettes that follow the system light/dark setting (macOS-style).
DARK = dict(window="#1c1c1e", sidebar="#242426", card="#2c2c2e", sep="#3a3a3c",
            text="#f5f5f7", sub="#98989d", accent="#0a84ff", accent_hover="#409cff",
            track_off="#48484a", pill="#3a3a3c", sel="#48484a", btn="#3a3a3c",
            btn_hover="#48484a", border="#3a3a3c")
LIGHT = dict(window="#f5f5f7", sidebar="#ebebf0", card="#ffffff", sep="#e5e5ea",
             text="#1d1d1f", sub="#6e6e73", accent="#007aff", accent_hover="#0066d6",
             track_off="#d1d1d6", pill="#e9e9ee", sel="#ffffff", btn="#ffffff",
             btn_hover="#f2f2f7", border="#e5e5ea")

STYLE = Template("""
QWidget#Root { background: $window; }
QWidget { font-family: 'SF Pro Text', 'SF Pro Display', 'Inter', 'Noto Sans', 'Cantarell', sans-serif;
          font-size: 13px; color: $text; }
QFrame#Sidebar { background: $sidebar; border-right: 1px solid $sep; }
QLabel#AppTitle { font-size: 15px; font-weight: 700; }
QLabel#AppSub { color: $sub; font-size: 11px; }
QLabel#Battery { background: $pill; border-radius: 10px; padding: 5px 10px; font-size: 12px; font-weight: 600; }
QListWidget#Nav { background: transparent; border: none; outline: none; }
QListWidget#Nav::item { padding: 7px 12px; border-radius: 8px; margin: 1px 10px; }
QListWidget#Nav::item:selected { background: $sel; color: $text; font-weight: 600; }
QListWidget#Nav::item:hover:!selected { background: rgba(128, 128, 128, 0.10); }
QWidget#Page { background: transparent; }
QScrollArea { background: transparent; border: none; }
QLabel#PageTitle { font-size: 24px; font-weight: 700; }
QLabel#GroupTitle { color: $sub; font-size: 12px; font-weight: 600; padding-left: 4px; }
QLabel#Note { color: $sub; font-size: 12px; padding-left: 4px; }
QFrame#Group { background: $card; border-radius: 12px; border: 1px solid $border; }
QFrame#Sep { background: $sep; border: none; }
QLabel#Value { color: $sub; min-width: 52px; }
QSlider::groove:horizontal { height: 4px; background: $track_off; border-radius: 2px; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal { background: #ffffff; border: 1px solid rgba(0, 0, 0, 0.10);
                             width: 18px; height: 18px; margin: -7px 0; border-radius: 9px; }
QComboBox { background: $pill; border: none; border-radius: 8px; padding: 5px 10px; min-width: 130px; }
QComboBox::drop-down { border: none; width: 18px; }
QFrame#Footer { background: $window; border-top: 1px solid $sep; }
QLineEdit { background: $pill; border: none; border-radius: 8px; padding: 5px 8px; color: $text; }
QLineEdit:disabled { color: $sub; background: transparent; border: 1px dashed $border; }
""")


class Switch(QAbstractButton):
    """macOS-style toggle switch. Colours come from the theme set on the class."""
    theme = LIGHT

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(42, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.4)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        track = QColor(self.theme["accent"] if self.isChecked() else self.theme["track_off"])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        d = r.height() - 4
        x = r.right() - d - 2 if self.isChecked() else r.left() + 2
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, r.top() + 2, d, d))
        p.end()


class PillButton(QPushButton):
    """Capsule button painted by hand so the rounded corners always show."""
    theme = LIGHT

    def __init__(self, text="", primary=False, parent=None):
        super().__init__(text, parent)
        self.primary = primary
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(30)
        self.setMinimumWidth(96)
        self.setAutoFillBackground(False)

    def paintEvent(self, _):
        t = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.4)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self.primary:
            fill = t["accent_hover"] if self.underMouse() else t["accent"]
            text_color = "#ffffff"
            border = None
        else:
            fill = t["btn_hover"] if self.underMouse() else t["btn"]
            text_color = t["text"]
            border = t["border"]
        p.setPen(QColor(border) if border else Qt.PenStyle.NoPen)
        p.setBrush(QColor(fill))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(QColor(text_color))
        f = self.font(); f.setWeight(f.Weight.DemiBold if self.primary else f.Weight.Medium)
        p.setFont(f)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


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


def load_gestures_gui():
    try:
        with open(GESTURES_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def detect_theme(app):
    return DARK if app.palette().window().color().lightness() < 128 else LIGHT


class TrackpadApp(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = QSettings("magic-trackpad-suite", "control-center")
        saved = self.settings.value("lang", DEFAULT_LANG)
        self.lang = saved if saved in LANGS else DEFAULT_LANG

        self.theme = detect_theme(QApplication.instance())
        Switch.theme = self.theme
        PillButton.theme = self.theme
        self.setObjectName("Root")
        self.setStyleSheet(STYLE.substitute(self.theme))
        self.resize(820, 600)
        self.setMinimumSize(760, 560)

        self.L = {}        # key -> list of widgets that show STRINGS[key]
        self.pills = []    # (value label, slider, formatter)
        self.nav_items = []
        self.action_widgets = {}   # name -> (combo, line edit)

        # ---- sidebar ----
        side = QFrame(); side.setObjectName("Sidebar"); side.setFixedWidth(210)
        sl = QVBoxLayout(side); sl.setContentsMargins(12, 22, 12, 16); sl.setSpacing(0)
        title = QLabel(); title.setObjectName("AppTitle"); self.register("app_name", title)
        sub = QLabel(); sub.setObjectName("AppSub"); sub.setWordWrap(True); self.register("subtitle", sub)
        sl.addWidget(title); sl.addWidget(sub); sl.addSpacing(18)

        self.nav = QListWidget(); self.nav.setObjectName("Nav")
        self.nav.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for key in ("nav_taptic", "nav_gestures", "nav_general"):
            item = QListWidgetItem(); self.nav.addItem(item); self.nav_items.append((item, key))
        sl.addWidget(self.nav, 1)

        self.battery = QLabel(); self.battery.setObjectName("Battery")
        sl.addWidget(self.battery, alignment=Qt.AlignmentFlag.AlignLeft)

        # ---- pages ----
        self.stack = QStackedWidget()
        self.stack.addWidget(self.page("nav_taptic", [
            self.section("grp_touch", [
                self.switch_row("chk_tick", "chk_tick", read_param("touch_tick", 18) > 0),
                self.slider_row("sl_tick_strength", 6, 35, read_param("touch_tick", 18) or 18),
            ], note="note_touch"),
            self.section("grp_click", [
                self.slider_row("sl_click_thr", 70, 160, read_param("click1_down", 120)),
                self.slider_row("sl_click_vib", 15, 63, read_param("click1_vib", 63)),
            ], note="note_click"),
            self.section("grp_force", [
                self.action_row("force_action", "force", keys=FORCE_KEYS, default="click"),
                self.slider_row("sl_force_thr", 150, 245, read_param("force_down", 208)),
                self.slider_row("sl_force_vib", 20, 63, read_param("force_vib", 63)),
            ], note="note_force"),
        ]))

        try: dc = json.load(open(DRAG_CONF))
        except Exception: dc = {"acceleration": 1.0, "dragEndDelay": 150}
        self.stack.addWidget(self.page("nav_gestures", [
            self.section("grp_drag", [
                self.switch_row("chk_drag", "chk_drag", is_active("three-finger-drag.service")),
                self.slider_row("sl_drag_speed", 5, 25, int(round(dc.get("acceleration", 1.0) * 10)),
                                lambda v: f"{v * 0.1:.1f}x"),
                self.slider_row("sl_drag_delay", 0, 350, int(dc.get("dragEndDelay", 150)),
                                lambda v: f"{v} {T(self.lang, 'ms')}"),
            ], note="note_drag"),
            self.section("grp_taps", [
                self.switch_row("chk_tap", "chk_tap", is_active("four-finger-tap.service", True)),
                self.action_row("gest_four", "four"),
                self.action_row("gest_five", "five"),
            ], note="note_actions"),
            self.section("grp_feedback", [
                self.switch_row("row_feedback", "sw_feedback", load_gestures_gui().get("feedback", True)),
            ], note="note_feedback"),
        ]))

        self.lang_box = QComboBox()
        for code, name in LANGS.items():
            self.lang_box.addItem(name, code)
        self.lang_box.setCurrentIndex(self.lang_box.findData(self.lang))
        lang_row = self.row("lang_label", self.lang_box)
        self.stack.addWidget(self.page("nav_general", [
            self.section("grp_interface", [lang_row], note="note_general"),
        ]))

        # ---- footer ----
        footer = QFrame(); footer.setObjectName("Footer"); footer.setFixedHeight(62)
        fl = QHBoxLayout(footer); fl.setContentsMargins(22, 0, 22, 0); fl.setSpacing(10)
        self.b_bt = PillButton(); self.register("btn_bt", self.b_bt)
        self.b_kde = PillButton(); self.register("btn_kde", self.b_kde)
        self.b_sv = PillButton(primary=True); self.register("btn_save", self.b_sv)
        self.b_press = PillButton(); self.register("btn_pressure", self.b_press)
        fl.addWidget(self.b_bt); fl.addWidget(self.b_kde); fl.addWidget(self.b_press)
        fl.addStretch(); fl.addWidget(self.b_sv)

        right = QVBoxLayout(); right.setContentsMargins(0, 0, 0, 0); right.setSpacing(0)
        right.addWidget(self.stack, 1); right.addWidget(footer)

        root = QHBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        root.addWidget(side); root.addLayout(right, 1)

        # ---- signals ----
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.setCurrentRow(0)
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
        self.b_press.clicked.connect(self.open_pressure_test)
        if shutil.which("kcmshell6") is None:
            self.b_kde.hide()   # KDE settings module not available on this desktop
        self.b_sv.clicked.connect(self.save_all)
        self.lang_box.currentIndexChanged.connect(self.change_language)
        self.st.setEnabled(self.chk_tick.isChecked())

        self.retranslate()

    # ---- builders ------------------------------------------------------

    def register(self, key, widget):
        self.L.setdefault(key, []).append(widget)

    def page(self, title_key, sections):
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.viewport().setAutoFillBackground(False)
        content = QWidget(); content.setObjectName("Page")
        lay = QVBoxLayout(content); lay.setContentsMargins(30, 26, 30, 26); lay.setSpacing(20)
        head = QLabel(); head.setObjectName("PageTitle"); self.register(title_key, head)
        lay.addWidget(head)
        for s in sections:
            lay.addLayout(s)
        lay.addStretch(1)
        scroll.setWidget(content)
        return scroll

    def section(self, title_key, rows, note=None):
        box = QVBoxLayout(); box.setSpacing(7)
        t = QLabel(); t.setObjectName("GroupTitle"); self.register(title_key, t)
        box.addWidget(t)
        card = QFrame(); card.setObjectName("Group")
        cl = QVBoxLayout(card); cl.setContentsMargins(0, 0, 0, 0); cl.setSpacing(0)
        for i, r in enumerate(rows):
            if i:
                wrap = QWidget(); wl = QVBoxLayout(wrap); wl.setContentsMargins(16, 0, 0, 0); wl.setSpacing(0)
                sep = QFrame(); sep.setObjectName("Sep"); sep.setFixedHeight(1)
                wl.addWidget(sep); cl.addWidget(wrap)
            cl.addWidget(r)
        box.addWidget(card)
        if note:
            n = QLabel(); n.setObjectName("Note"); n.setWordWrap(True); self.register(note, n)
            box.addWidget(n)
        return box

    def row(self, label_key, control):
        w = QWidget(); lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 11, 16, 11); lay.setSpacing(12)
        lbl = QLabel(); lbl.setWordWrap(True); self.register(label_key, lbl)
        lay.addWidget(lbl, 1); lay.addWidget(control)
        return w

    def switch_row(self, label_key, attr, checked):
        sw = Switch(); sw.setChecked(checked)
        setattr(self, attr, sw)
        return self.row(label_key, sw)

    def action_row(self, label_key, name, keys=None, default=None):
        keys = keys or ACTION_KEYS
        default = default or GESTURE_DEFAULTS[name]
        w = QWidget(); lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 11, 16, 11); lay.setSpacing(12)
        lbl = QLabel(); lbl.setWordWrap(True); self.register(label_key, lbl)
        combo = QComboBox(); combo.setFixedWidth(190)
        for k in keys:
            combo.addItem("", k)
        edit = QLineEdit(); edit.setFixedWidth(190)
        lay.addWidget(lbl, 1); lay.addWidget(combo); lay.addWidget(edit)

        current = load_gestures_gui().get(name, default)
        if current.startswith("custom:"):
            key, text = "custom", current[len("custom:"):]
        else:
            key, text = (current if current in keys else "none"), ""
        combo.setCurrentIndex(combo.findData(key))
        edit.setText(text)
        edit.setEnabled(key == "custom")
        combo.currentIndexChanged.connect(lambda _i, c=combo, e=edit: e.setEnabled(c.currentData() == "custom"))
        self.action_widgets[name] = (combo, edit)
        return w

    def slider_row(self, label_key, mn, mx, val, fmt=str):
        w = QWidget(); lay = QHBoxLayout(w)
        lay.setContentsMargins(16, 11, 16, 11); lay.setSpacing(12)
        lbl = QLabel(); lbl.setWordWrap(True); self.register(label_key, lbl)
        sld = QSlider(Qt.Orientation.Horizontal); sld.setRange(mn, mx); sld.setValue(val)
        sld.setFixedWidth(190)
        pill = QLabel(fmt(val)); pill.setObjectName("Value")
        pill.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        sld.valueChanged.connect(lambda v: pill.setText(fmt(v)))
        self.pills.append((pill, sld, fmt))
        lay.addWidget(lbl, 1); lay.addWidget(sld); lay.addWidget(pill)
        # expose the slider under the attribute names used by save_all
        self._bind_slider(label_key, sld)
        return w

    def _bind_slider(self, label_key, sld):
        names = {"sl_tick_strength": "st", "sl_click_thr": "sp1", "sl_click_vib": "sv1",
                 "sl_force_thr": "sf", "sl_force_vib": "svf", "sl_drag_speed": "sa",
                 "sl_drag_delay": "sd"}
        setattr(self, names[label_key], sld)

    # ---- language & text -------------------------------------------------

    def change_language(self, index):
        self.lang = self.lang_box.itemData(index)
        self.settings.setValue("lang", self.lang)
        self.retranslate()

    def retranslate(self):
        lang = self.lang
        self.setWindowTitle(T(lang, "window_title"))
        for key, widgets in self.L.items():
            for w in widgets:
                w.setText(T(lang, key))
        for item, key in self.nav_items:
            item.setText(T(lang, key))
        self.battery.setText(get_battery(lang))
        for pill, sld, fmt in self.pills:
            pill.setText(fmt(sld.value()))
        for combo, edit in self.action_widgets.values():
            for i in range(combo.count()):
                combo.setItemText(i, T(lang, "act_" + combo.itemData(i)))
            edit.setPlaceholderText(T(lang, "cmd_placeholder"))

    # ---- actions -------------------------------------------------------

    def open_pressure_test(self):
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "magic-trackpad-pressure.py")
        subprocess.Popen([sys.executable, script])

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
        fa = FORCE_MODE.get(self.action_widgets["force"][0].currentData(), 3)
        mc = f"options hid_magicmouse host_click=on button_down_param=0x783f0b0b button_up_param=0x55250808 click1_down={p1} click1_vib={v1} force_down=0x{fd:02X} force_up=0x{fu:02X} force_vib={fv} touch_tick={tv} force_action={fa}\n"
        write_param("force_action", fa)
        subprocess.run(["sudo", "tee", "/etc/modprobe.d/hid-magicmouse.conf"], input=mc.encode(), stdout=subprocess.DEVNULL)
        dc = json.dumps({"acceleration": round(self.sa.value() * 0.1, 1), "dragEndDelay": self.sd.value()}, indent=2) + "\n"
        subprocess.run(["sudo", "tee", DRAG_CONF], input=dc.encode(), stdout=subprocess.DEVNULL)
        if self.chk_drag.isChecked():
            subprocess.run(["sudo", "systemctl", "restart", "three-finger-drag.service"]); time.sleep(1.2)
        subprocess.run(["systemctl", "--user", "restart", "four-finger-tap.service"])
        gest = {"feedback": self.sw_feedback.isChecked()}
        for name, (combo, edit) in self.action_widgets.items():
            key = combo.currentData()
            if key == "custom":
                cmd = edit.text().strip()
                gest[name] = f"custom:{cmd}" if cmd else "none"
            else:
                gest[name] = key
        os.makedirs(CONF_DIR, exist_ok=True)
        with open(GESTURES_FILE, "w") as f:
            json.dump(gest, f, indent=2)
        QMessageBox.information(self, T(self.lang, "saved_title"), T(self.lang, "saved_text"))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Ties the window to magic-trackpad-settings.desktop so the shell shows our icon.
    app.setDesktopFileName("magic-trackpad-settings")
    app.setWindowIcon(QIcon.fromTheme("magic-trackpad-settings"))
    w = TrackpadApp()
    w.show()
    sys.exit(app.exec())
