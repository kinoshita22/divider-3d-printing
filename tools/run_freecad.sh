#!/usr/bin/env bash
# Run a script of this project under a headless FreeCAD.
#
#   ./tools/run_freecad.sh main.py --stl
#
# FreeCAD rejects command-line flags it does not recognise, and its own
# --pass escape reliably forwards only one token, so everything after the
# script name is handed over in the DIVIDER_ARGS environment variable.
#
# Point FREECAD_CMD at your FreeCAD if it is not on PATH:
#   export FREECAD_CMD=/opt/squashfs-root/usr/bin/freecadcmd
set -euo pipefail

CMD="${FREECAD_CMD:-}"
if [[ -z "$CMD" ]]; then
  for c in freecadcmd FreeCADCmd freecad FreeCAD; do
    if command -v "$c" >/dev/null 2>&1; then CMD="$c"; break; fi
  done
fi
if [[ -z "$CMD" ]]; then
  echo "No FreeCAD found. Set FREECAD_CMD to your freecadcmd binary." >&2
  exit 1
fi

SCRIPT="${1:?usage: run_freecad.sh <script.py> [options]}"
shift || true
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$SCRIPT" ]] || SCRIPT="$ROOT/$SCRIPT"

export QT_QPA_PLATFORM=offscreen
# Shell-quote each argument so paths with spaces survive the round trip.
ARGS=""
for a in "$@"; do ARGS+="$(printf '%q ' "$a")"; done
export DIVIDER_ARGS="$ARGS"
exec "$CMD" "$SCRIPT"
