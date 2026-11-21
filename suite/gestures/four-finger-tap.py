#!/usr/bin/env python3
import evdev, subprocess, time, threading

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

        def fire_launchpad():
            subprocess.Popen(["qdbus6", "org.kde.plasmashell", "/PlasmaShell", "org.kde.PlasmaShell.activateLauncherMenu"])

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
                            pending_timer = threading.Timer(0.04, fire_launchpad)
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
                            subprocess.Popen(["qdbus6", "org.kde.kglobalaccel", "/component/kwin", "org.kde.kglobalaccel.Component.invokeShortcut", "Show Desktop"])
    except Exception:
        time.sleep(1)
