#!/usr/bin/env python3
import evdev, subprocess, time, threading, json, os, glob

CONF_DIR = os.path.expanduser("~/.config/magic-trackpad-suite")
GESTURES_FILE = os.path.join(CONF_DIR, "gestures.json")
PRESETS = {
    "launchpad": 'qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.activateLauncherMenu',
    "show_desktop": 'qdbus6 org.kde.kglobalaccel /component/kwin org.kde.kglobalaccel.Component.invokeShortcut "Show Desktop"',
    "none": "", "click": "", "middle": "", "context": "",
}
DEFAULTS = {"four": "launchpad", "five": "show_desktop", "force": "click"}
PULSE_PARAM = "/sys/module/hid_magicmouse/parameters/pulse"
FORCE_VIB_PARAM = "/sys/module/hid_magicmouse/parameters/force_vib"
CLICK_CODES = {"context": evdev.ecodes.BTN_RIGHT}   # middle click removed: it triggers KDE middle-button actions
_virtual_mouse = None
_force_timer = None
PRESSURE_PID = os.path.join(CONF_DIR, "pressure.pid")
BATTERY_TEXT = {
    "ru": ("Magic Trackpad 2", "Заряд трекпада: {cap}%"),
    "en": ("Magic Trackpad 2", "Trackpad battery: {cap}%"),
}

def load_gestures():
    try:
        with open(GESTURES_FILE) as f:
            data = json.load(f)
    except Exception:
        data = {}
    return {k: data.get(k, DEFAULTS[k]) for k in DEFAULTS}

def read_force_vib():
    try:
        return int(open(FORCE_VIB_PARAM).read().strip())
    except Exception:
        return 40

def load_settings():
    try:
        with open(GESTURES_FILE) as f:
            data = json.load(f)
    except Exception:
        data = {}
    # the extra tap after Force Touch is a bit weaker than the Force Touch itself
    force_strength = data.get("force_feedback_strength", max(1, int(read_force_vib() * 0.75)))
    return {
        "feedback": bool(data.get("feedback", True)),
        "strength": int(data.get("feedback_strength", 45)),
        "force_strength": int(force_strength),
        "hold_ms": int(data.get("force_hold_ms", 225)),
        "gap_ms": int(data.get("force_tap_gap_ms", 150)),
        "gesture_gap_ms": int(data.get("gesture_tap_gap_ms", 45)),
    }

def haptic_pulse(strength):
    try:
        with open(PULSE_PARAM, "w") as f:
            f.write(str(strength))
    except Exception:
        pass

def signal_success(pulses=2, strength=None, gap_ms=None):
    """Confirm an action with short haptic taps."""
    st = load_settings()
    if not st["feedback"]:
        return
    s_val = strength or st["strength"]
    gap = (gap_ms if gap_ms is not None else st["gesture_gap_ms"]) / 1000.0
    for i in range(pulses):
        if i:
            time.sleep(gap)
        haptic_pulse(s_val)

def virtual_mouse():
    """Separate mouse device: libinput ignores right/middle buttons coming from a clickpad."""
    global _virtual_mouse
    if _virtual_mouse is None:
        caps = {
            evdev.ecodes.EV_KEY: [evdev.ecodes.BTN_LEFT, evdev.ecodes.BTN_RIGHT, evdev.ecodes.BTN_MIDDLE],
            evdev.ecodes.EV_REL: [evdev.ecodes.REL_X, evdev.ecodes.REL_Y],
        }
        _virtual_mouse = evdev.UInput(caps, name="Magic Trackpad 2 actions")
    return _virtual_mouse

def send_click(code):
    try:
        ui = virtual_mouse()
        ui.write(evdev.ecodes.EV_KEY, code, 1); ui.syn()
        ui.write(evdev.ecodes.EV_KEY, code, 0); ui.syn()
    except Exception:
        pass  # /dev/uinput not accessible

def run_action(name):
    val = load_gestures()[name]
    if val.startswith("custom:"):
        cmd = val[len("custom:"):].strip()
    else:
        cmd = PRESETS.get(val, "")
    if cmd:
        subprocess.Popen(cmd, shell=True)   # no haptic feedback for 4/5-finger gestures for now

def pressure_test_open():
    """True while the pressure test window is open (it writes its PID to PRESSURE_PID)."""
    try:
        with open(PRESSURE_PID) as f:
            pid = int(f.read().strip())
    except Exception:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        try:
            os.remove(PRESSURE_PID)
        except Exception:
            pass
        return False
    except PermissionError:
        return True

def force_pressed():
    """Force Touch went past the threshold: run the action now, and if the press is
    held for hold_ms, confirm with two taps (tap-tap)."""
    global _force_timer
    if pressure_test_open():
        return   # the pressure test window is open: Force Touch binds are ignored
    val = load_gestures()["force"]
    if val in CLICK_CODES:
        send_click(CLICK_CODES[val])
    if val.startswith("custom:"):
        cmd = val[len("custom:"):].strip()
        if cmd:
            subprocess.Popen(cmd, shell=True)
    st = load_settings()
    if st["feedback"]:
        _force_timer = threading.Timer(st["hold_ms"] / 1000.0, force_confirmed)
        _force_timer.start()

def force_released():
    """Released before hold_ms: no confirmation taps."""
    global _force_timer
    if _force_timer:
        _force_timer.cancel()
        _force_timer = None

def force_confirmed():
    global _force_timer
    _force_timer = None
    st = load_settings()
    haptic_pulse(st["force_strength"])
    time.sleep(st["gap_ms"] / 1000.0)
    haptic_pulse(st["force_strength"])

def ui_lang():
    try:
        with open(os.path.join(CONF_DIR, "control-center.conf")) as f:
            for line in f:
                if line.startswith("lang="):
                    return line.strip().split("=", 1)[1]
    except Exception:
        pass
    return "ru"

def read_trackpad_battery():
    for p in glob.glob("/sys/class/power_supply/*"):
        try:
            if "Trackpad" in open(f"{p}/model_name").read():
                cap = int(open(f"{p}/capacity").read().strip())
                st = open(f"{p}/status").read().strip()
                return cap, st
        except Exception:
            pass
    return None, None

def battery_watch():
    """Notify once when the trackpad battery drops to 15% or below while discharging."""
    notified = False
    while True:
        cap, st = read_trackpad_battery()
        if cap is not None:
            if st == "Discharging" and cap <= 15 and not notified:
                title, body = BATTERY_TEXT.get(ui_lang(), BATTERY_TEXT["en"])
                subprocess.Popen(["notify-send", "-i", "input-touchpad", title, body.format(cap=cap)])
                notified = True
            elif st != "Discharging" or cap > 20:
                notified = False
        time.sleep(60)

threading.Thread(target=battery_watch, daemon=True).start()

def find_clone():
    fallback = None
    for path in evdev.list_devices():
        dev = evdev.InputDevice(path)
        if "Magic Trackpad" in dev.name:
            if "proxy" in (dev.phys or ""):
                return dev
            fallback = dev
    return fallback

while True:
    dev = find_clone()
    if not dev:
        time.sleep(2)
        continue
    try:
        quad_active = False
        quint_active = False
        had_quint = False
        start_time = 0.0
        slot = 0
        sx = {}
        sy = {}
        moved = False
        pending_timer = None

        def cancel_timer():
            global pending_timer
            if pending_timer:
                pending_timer.cancel()
                pending_timer = None

        for event in dev.read_loop():
            if event.type == evdev.ecodes.EV_ABS:
                if event.code == evdev.ecodes.ABS_MT_SLOT:
                    slot = event.value
                elif event.code == evdev.ecodes.ABS_MT_POSITION_X:
                    if not quad_active and not quint_active:
                        sx[slot] = event.value
                    elif slot in sx and abs(event.value - sx[slot]) > 130:
                        moved = True
                        cancel_timer()
                elif event.code == evdev.ecodes.ABS_MT_POSITION_Y:
                    if not quad_active and not quint_active:
                        sy[slot] = event.value
                    elif slot in sy and abs(event.value - sy[slot]) > 130:
                        moved = True
                        cancel_timer()

            elif event.type == evdev.ecodes.EV_KEY:
                if event.code == evdev.ecodes.BTN_TOUCH and event.value == 0:
                    had_quint = False
                    quad_active = False
                    quint_active = False
                    sx.clear()
                    sy.clear()

                elif event.code == evdev.ecodes.BTN_TRIGGER_HAPPY1:
                    if event.value == 1:
                        threading.Thread(target=force_pressed, daemon=True).start()
                    elif event.value == 0:
                        force_released()
                elif event.code == evdev.ecodes.BTN_LEFT and event.value == 1:
                    moved = True
                    cancel_timer()

                elif event.code == evdev.ecodes.BTN_TOOL_QUADTAP:
                    if event.value == 1 and not quint_active and not had_quint:
                        cancel_timer()
                        quad_active = True
                        start_time = time.monotonic()
                        moved = False
                    elif event.value == 0 and quad_active:
                        duration = time.monotonic() - start_time
                        quad_active = False
                        if not moved and not quint_active and not had_quint and 0.03 < duration < 0.30:
                            cancel_timer()
                            pending_timer = threading.Timer(0.04, run_action, args=("four",))
                            pending_timer.start()

                elif event.code == evdev.ecodes.BTN_TOOL_QUINTTAP:
                    if event.value == 1:
                        cancel_timer()
                        quint_active = True
                        had_quint = True
                        quad_active = False
                        start_time = time.monotonic()
                    elif event.value == 0 and quint_active:
                        duration = time.monotonic() - start_time
                        quint_active = False
                        if duration < 0.45:
                            run_action("five")
    except Exception:
        time.sleep(1)
