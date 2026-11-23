#!/usr/bin/env bash
set -eu
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for arg in "$@"; do
    case "$arg" in
        --check|--help|-h)
            exec python3 "$HERE/forge-linux/app/backend/setup_runtime.py" "$@"
            ;;
    esac
done
python3 "$HERE/forge-linux/app/backend/setup_runtime.py" "$@"
"$HERE/install-desktop.sh"
