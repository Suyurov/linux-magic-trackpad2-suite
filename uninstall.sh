#!/usr/bin/env bash
# Reverts everything setup-suite.sh installed and returns the stock kernel driver.
#   ./uninstall.sh            ask for confirmation, then remove
#   ./uninstall.sh --dry-run  only print the commands
#   ./uninstall.sh --yes      no confirmation
#   ./uninstall.sh --purge    also remove your settings and the input-group membership
set -uo pipefail

DRY=0; YES=0; PURGE=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY=1 ;;
        --yes|-y)  YES=1 ;;
        --purge)   PURGE=1 ;;
        -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

REAL_USER="${SUDO_USER:-${USER:-$(id -un)}}"
REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
if [[ -z "$REAL_HOME" || ! -d "$REAL_HOME" ]]; then
    echo "Could not find the home directory for $REAL_USER. Aborting."
    exit 1
fi
if [[ "$REAL_USER" == "root" ]]; then
    echo "Run this as your normal user, not root. The script asks for sudo itself."
    exit 1
fi

DKMS_NAME="hid-magicmouse-dkms"
DKMS_VERSION="4.18+magictrackpad2"

run() {
    if (( DRY )); then echo "[dry-run] $*"; else "$@"; fi
}

echo "This will remove the Magic Trackpad 2 suite and return the stock hid_magicmouse driver."
echo "  - services: three-finger-drag (system), four-finger-tap (user)"
echo "  - DKMS driver: $DKMS_NAME $DKMS_VERSION"
echo "  - system files: sudoers rule, udev rules, modprobe config, 3-finger-drag config"
echo "  - user files: GUI, gesture daemon, desktop entry, icon, user service"
if (( PURGE )); then
    echo "  - PURGE: settings in ~/.config/magic-trackpad-suite, uinput autoload, input-group membership"
fi
echo "Packages (dkms, PyQt6, linux-3-finger-drag, ...) are NOT removed."

if (( ! DRY && ! YES )); then
    read -rp "Continue? [y/N] " ans
    [[ "$ans" =~ ^[Yy]$ ]] || { echo "Cancelled."; exit 0; }
fi

echo "==> 1. Stopping services..."
run systemctl --user disable --now four-finger-tap.service
run sudo systemctl disable --now three-finger-drag.service
run sudo rm -rf /etc/systemd/system/three-finger-drag.service.d
run sudo systemctl daemon-reload
run systemctl --user daemon-reload

echo "==> 2. Removing user files..."
run rm -f "$REAL_HOME/.local/bin/magic-trackpad-settings.py"
run rm -f "$REAL_HOME/.local/bin/four-finger-tap.py"
run rm -f "$REAL_HOME/.local/bin/magic-trackpad-pressure.py"
run rm -f "$REAL_HOME/.local/share/applications/magic-trackpad-settings.desktop"
run rm -f "$REAL_HOME/.local/share/icons/hicolor/scalable/apps/magic-trackpad-settings.svg"
run rm -f "$REAL_HOME/.config/systemd/user/four-finger-tap.service"
if (( PURGE )); then
    run rm -rf "$REAL_HOME/.config/magic-trackpad-suite"
fi

echo "==> 3. Removing system config..."
run sudo rm -f /etc/sudoers.d/magic-trackpad-gui
run sudo rm -f /etc/sudoers.d/magic-trackpad-pulse
run sudo rm -f /etc/udev/rules.d/99-magictrackpad-3fd.rules
run sudo rm -f /etc/udev/rules.d/99-hid-magicmouse-perms.rules
run sudo rm -f /etc/modprobe.d/hid-magicmouse.conf
run sudo rm -f /etc/linux-3-finger-drag/3fd-config.json
run sudo udevadm control --reload-rules
if (( PURGE )); then
    run sudo rm -f /etc/modules-load.d/uinput.conf
    run sudo gpasswd -d "$REAL_USER" input
fi

echo "==> 4. Removing DKMS driver and loading the stock one..."
run sudo dkms remove "$DKMS_NAME/$DKMS_VERSION" --all
run sudo modprobe -r hid_magicmouse
run sudo modprobe hid_magicmouse
run sudo systemctl restart bluetooth

echo "✅ Reverted. Log out and back in if the trackpad still behaves oddly."
