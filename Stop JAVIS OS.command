#!/bin/bash
# Double-click in Finder to stop JARVIS 007.
cd "$(dirname "$0")" || exit 1
bash "bin/javis-stop.sh"
echo ""
echo "You can close this window."
