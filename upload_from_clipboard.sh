#!/usr/bin/env bash
# Upload a workout whose JSON is on the clipboard (pbpaste) via
# upload_workouts.py, using the local .venv.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

pbpaste > "$tmp"
"$here/.venv/bin/python" "$here/upload_workouts.py" "$tmp"
