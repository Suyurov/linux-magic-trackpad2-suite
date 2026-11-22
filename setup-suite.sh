#!/usr/bin/env bash
set -euo pipefail

REAL_USER="${SUDO_USER:-${USER:-$(id -un)}}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

if [[ "$REAL_USER" == "root" ]]; then
    echo "Run this as your normal user, not root. The script asks for sudo itself."
    exit 1
fi

detect_pm() {
    if command -v pacman >/dev/null 2>&1; then echo arch
    elif command -v apt-get >/dev/null 2>&1; then echo debian
    elif command -v dnf >/dev/null 2>&1; then echo fedora
    elif command -v zypper >/dev/null 2>&1; then echo suse
    else echo unknown
    fi
}

warn_3fd() {
    echo "WARN: linux-3-finger-drag is not packaged for this distro by this script."
    echo "      Build it from its upstream project and install it to /usr/bin/linux-3-finger-drag."
    echo "      Three-finger drag will not work until you do. Everything else will."
}

PM=$(detect_pm)
echo "==> 1. Installing dependencies (detected: $PM)..."
case "$PM" in
    arch)
        sudo pacman -S --needed --noconfirm linux-headers dkms base-devel python-pyqt6 python-evdev
        if command -v yay >/dev/null 2>&1; then
            yay -S --needed --noconfirm linux-3-finger-drag-git
        else
            echo "WARN: yay not found. Install linux-3-finger-drag-git from the AUR manually."
        fi
        ;;
    debian)
        sudo apt-get update
        sudo apt-get install -y "linux-headers-$(uname -r)" dkms build-essential python3-pyqt6 python3-evdev
        warn_3fd
        ;;
    fedora)
        sudo dnf install -y kernel-devel dkms gcc make python3-pyqt6 python3-evdev
        warn_3fd
        ;;
    suse)
        sudo zypper --non-interactive install kernel-default-devel dkms gcc make python3-PyQt6 python3-evdev
        warn_3fd
        ;;
    *)
        echo "Unsupported system: no pacman, apt-get, dnf or zypper found."
        echo "Install manually: kernel headers, dkms, gcc, make, PyQt6, python-evdev, linux-3-finger-drag."
        exit 1
        ;;
esac

echo "==> 2. Building and installing patched hid-magicmouse DKMS driver..."
sudo ./scripts/remove.sh 2>/dev/null || true
sudo ./scripts/install.sh

echo "==> 3. Installing configs, udev rules, and sudoers permissions..."
sudo mkdir -p /etc/modprobe.d /etc/linux-3-finger-drag /etc/udev/rules.d /etc/systemd/system/three-finger-drag.service.d
sudo cp suite/configs/hid-magicmouse.conf /etc/modprobe.d/
sudo cp suite/configs/3fd-config.json /etc/linux-3-finger-drag/
sudo cp suite/configs/99-hid-magicmouse-perms.rules /etc/udev/rules.d/

cat << UDEV | sudo tee /etc/udev/rules.d/99-magictrackpad-3fd.rules >/dev/null
ACTION=="add", SUBSYSTEM=="input", ATTRS{name}=="Apple Inc. Magic Trackpad 2", ATTRS{phys}!="*proxy*", RUN+="/usr/bin/systemctl restart three-finger-drag.service"
ACTION=="add", SUBSYSTEM=="input", ATTRS{name}=="Apple Inc. Magic Trackpad 2", ATTRS{phys}=="*proxy*", RUN+="/usr/bin/systemctl --machine=${REAL_USER}@.host --user restart four-finger-tap.service"
UDEV

cat << OVR | sudo tee /etc/systemd/system/three-finger-drag.service.d/override.conf >/dev/null
[Service]
Restart=always
RestartSec=2
ExecStartPre=/bin/sleep 2
ExecStart=
ExecStart=/bin/sh -c 'for d in /sys/class/input/event*; do if grep -q "Apple Inc. Magic Trackpad 2" "\$d/device/name" 2>/dev/null && ! grep -q "proxy" "\$d/device/phys" 2>/dev/null; then exec /usr/bin/linux-3-finger-drag --device "/dev/input/\$(basename "\$d")"; fi; done; exit 1'
OVR

cat << SUDO | sudo tee /etc/sudoers.d/magic-trackpad-gui >/dev/null
${REAL_USER} ALL=(ALL) NOPASSWD: /usr/bin/tee /sys/module/hid_magicmouse/parameters/touch_tick, /usr/bin/tee /sys/module/hid_magicmouse/parameters/click1_down, /usr/bin/tee /sys/module/hid_magicmouse/parameters/click1_vib, /usr/bin/tee /sys/module/hid_magicmouse/parameters/force_down, /usr/bin/tee /sys/module/hid_magicmouse/parameters/force_up, /usr/bin/tee /sys/module/hid_magicmouse/parameters/force_vib, /usr/bin/tee /etc/modprobe.d/hid-magicmouse.conf, /usr/bin/tee /etc/linux-3-finger-drag/3fd-config.json, /usr/bin/systemctl restart three-finger-drag.service, /usr/bin/systemctl start three-finger-drag.service, /usr/bin/systemctl stop three-finger-drag.service, /usr/bin/systemctl restart bluetooth
SUDO
sudo chmod 0440 /etc/sudoers.d/magic-trackpad-gui
sudo gpasswd -a "$REAL_USER" input >/dev/null
echo "uinput" | sudo tee /etc/modules-load.d/uinput.conf >/dev/null

echo "==> 4. Installing GUI Control Center and 4/5-finger tap daemon..."
mkdir -p "$REAL_HOME/.local/bin" "$REAL_HOME/.local/share/applications" "$REAL_HOME/.config/systemd/user"
cp suite/gui/magic-trackpad-settings.py "$REAL_HOME/.local/bin/"
chmod +x "$REAL_HOME/.local/bin/magic-trackpad-settings.py"
cp suite/gui/magic-trackpad-pressure.py "$REAL_HOME/.local/bin/"
chmod +x "$REAL_HOME/.local/bin/magic-trackpad-pressure.py"
sed "s|/home/REPLACE_USER|$REAL_HOME|g" suite/gui/magic-trackpad-settings.desktop > "$REAL_HOME/.local/share/applications/magic-trackpad-settings.desktop"
mkdir -p "$REAL_HOME/.local/share/icons/hicolor/scalable/apps" && cp suite/gui/magic-trackpad-settings.svg "$REAL_HOME/.local/share/icons/hicolor/scalable/apps/"

cp suite/gestures/four-finger-tap.py "$REAL_HOME/.local/bin/"
chmod +x "$REAL_HOME/.local/bin/four-finger-tap.py"
cp suite/gestures/four-finger-tap.service "$REAL_HOME/.config/systemd/user/"
chown -R "$REAL_USER:$REAL_USER" "$REAL_HOME/.local" "$REAL_HOME/.config/systemd"

echo "==> 5. Reloading kernel module and services..."
sudo modprobe uinput
sudo modprobe -r hid_magicmouse 2>/dev/null || true
sudo modprobe hid_magicmouse
sudo chmod 0666 /sys/module/hid_magicmouse/parameters/* 2>/dev/null || true
sudo udevadm control --reload-rules
sudo systemctl daemon-reload
sudo systemctl enable --now three-finger-drag.service
systemctl --user daemon-reload
systemctl --user enable --now four-finger-tap.service

echo "✅ Done! Launch 'Magic Trackpad 2 Settings' from your app menu or run ~/.local/bin/magic-trackpad-settings.py"
