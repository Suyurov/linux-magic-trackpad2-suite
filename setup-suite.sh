#!/usr/bin/env bash
set -e

REAL_USER="${SUDO_USER:-$USER}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)

echo "==> 1. Installing dependencies (Arch Linux)..."
sudo pacman -S --needed --noconfirm linux-headers dkms base-devel python-pyqt6 python-evdev
if command -v yay &>/dev/null; then
    yay -S --needed --noconfirm linux-3-finger-drag-git
fi

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
sed "s|/home/suyurov|$REAL_HOME|g" suite/gui/magic-trackpad-settings.desktop > "$REAL_HOME/.local/share/applications/magic-trackpad-settings.desktop"

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
