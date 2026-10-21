#!/bin/sh
# Accent Color for the NextUI Style theme.
# Runs the picker through spruce's own PyUI launcher (so the display/input setup
# matches the main menu on every device), then lets spruce restart the menu.

. /mnt/SDCARD/spruce/scripts/helperFunctions.sh

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
export ACCENT_APP_DIR="$APP_DIR"
PICKER="/mnt/SDCARD/App/PyUI/main-ui/accent_picker_app.py"
LAUNCHER="/tmp/accent_pyui_launch.sh"

cp -f "$APP_DIR/accent_picker.py" "$PICKER"
sed "s#/mnt/SDCARD/App/PyUI/main-ui/mainui.py#$PICKER#g" /mnt/SDCARD/App/PyUI/launch.sh > "$LAUNCHER"

log_message "Accent Color: starting picker"
sh "$LAUNCHER"
log_message "Accent Color: picker exited"

rm -f "$PICKER" "$LAUNCHER"
sync
