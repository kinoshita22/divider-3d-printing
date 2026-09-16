#!/usr/bin/env bash
# Open the generated model in the FreeCAD GUI.
#
#   ./tools/open_gui.sh                       # opens output/divider_prototype.FCStd
#   ./tools/open_gui.sh output/STEP/Socket.step
#
# Resolution order for the GUI binary:
#   $FREECAD_GUI, then the AppRun next to $FREECAD_CMD, then PATH.
#
# For an extracted AppImage, launch via AppRun rather than usr/bin/freecad:
# AppRun sets FONTCONFIG_FILE, PYTHONHOME and QT_QPA_PLATFORM=xcb, without
# which the GUI starts with font errors or fails on Wayland.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-$ROOT/output/divider_prototype.FCStd}"

GUI="${FREECAD_GUI:-}"
if [[ -z "$GUI" && -n "${FREECAD_CMD:-}" ]]; then
  CAND="$(dirname "$(dirname "$(dirname "$FREECAD_CMD")")")/AppRun"
  [[ -x "$CAND" ]] && GUI="$CAND"
fi
if [[ -z "$GUI" ]]; then
  for c in freecad FreeCAD; do
    if command -v "$c" >/dev/null 2>&1; then GUI="$c"; break; fi
  done
fi
if [[ -z "$GUI" ]]; then
  echo "No FreeCAD GUI found. Set FREECAD_GUI to your freecad binary or AppRun." >&2
  exit 1
fi

if [[ ! -f "$TARGET" ]]; then
  echo "Nothing to open at $TARGET - run ./tools/run_freecad.sh main.py first." >&2
  exit 1
fi

# Must NOT inherit the offscreen platform the headless wrapper sets.
unset QT_QPA_PLATFORM

# A headless-built FCStd carries no GuiDocument.xml, so the GUI would open it
# with the parts hidden and the camera unfitted - it looks like an empty
# document. Hand FreeCAD a startup script instead of the file itself: FreeCAD
# executes .py arguments in the GUI session, and gui_open.py opens the target
# and supplies the missing visibility, colours and camera.
export DIVIDER_GUI_TARGET="$TARGET"
exec "$GUI" "$ROOT/tools/gui_open.py"
