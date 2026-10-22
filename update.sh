#!/bin/sh
set -eu
command -v python3 >/dev/null 2>&1 || { echo 'Python 3 fehlt.' >&2; exit 1; }
FCA_TOOL_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$FCA_TOOL_ROOT/scripts/fca_admin.py" update "$@"
