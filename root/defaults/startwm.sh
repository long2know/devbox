#!/usr/bin/env bash
set -euo pipefail

export XDG_CURRENT_DESKTOP=X-Cinnamon
export DESKTOP_SESSION=cinnamon
export XDG_SESSION_TYPE=x11
export QT_QPA_PLATFORM=xcb
export GDK_BACKEND=x11
export CLUTTER_BACKEND=x11
unset WAYLAND_DISPLAY KDE_FULL_SESSION KDE_SESSION_VERSION

exec dbus-launch --exit-with-session /usr/local/bin/devbox-cinnamon-session
