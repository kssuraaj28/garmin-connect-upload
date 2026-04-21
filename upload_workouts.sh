#!/usr/bin/env bash
# Wrapper around upload_workouts.py that uses the local .venv.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$here/.venv/bin/python" "$here/upload_workouts.py" "$@"
