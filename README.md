# Apple Magic Trackpad 2 — Full Force Touch & Gesture Suite for Linux

Complete macOS-like experience for **Apple Magic Trackpad 2** on Linux (Arch Linux / KDE Plasma 6 Wayland) over **Bluetooth & USB**.

## Features
- **Custom `hid-magicmouse` DKMS Kernel Driver:**
  - **2-Stage Force Touch:** Crisp primary click (`BTN_LEFT`) + deep secondary Force Click with stronger Taptic Engine thump and clean word selection (no phantom release clicks).
  - **Live Touch Haptics (`touch_tick`):** Optional subtle Taptic Engine micro-tick on every finger landing.
  - **Real-Time Tuning:** Adjust thresholds and vibration strength on the fly via `/sys/module/hid_magicmouse/parameters/*`.
- **Three-Finger Drag (`linux-3-finger-drag`):** Drag windows and select text with 3 fingers without pressing down, while keeping 4-finger desktop swipes intact.
- **4 & 5 Finger Taps:** 4-finger tap opens Launchpad / Application Dashboard; 5-finger tap toggles Show Desktop.
- **GUI Control Center (PyQt6):** Native control panel to tune haptic strength, thresholds, drag speed, and save settings permanently.

## One-Command Installation (Arch Linux)
```bash
git clone https://github.com/Suyurov/linux-magic-trackpad2-suite.git
cd linux-magic-trackpad2-suite
./setup-suite.sh
```
*(Log out and back in once after installation so `input` group permissions apply).*
