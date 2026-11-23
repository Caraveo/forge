#!/usr/bin/env bash
set -eu
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec python3 - "$HERE" <<'PY'
import os
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

project = Path(sys.argv[1])
data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
applications = data_home / "applications"
applications.mkdir(parents=True, exist_ok=True)
desktop_file = applications / "forge.desktop"

# Exec uses its own quoting in addition to desktop-entry string escaping.
launcher = str(project / "forge").replace("%", "%%")
quoted_launcher = '"' + "".join("\\" + char if char in '\\"$`' else char for char in launcher) + '"'
exec_value = quoted_launcher.replace("\\", "\\\\")
icon = str(project / "forge-linux/app/ui/icon.png").replace("\\", "\\\\")

with NamedTemporaryFile(mode="w", encoding="utf-8", dir=applications, delete=False) as temporary:
    temporary.write(f"""[Desktop Entry]
Type=Application
Name=FORGE
Comment=Generate and preview 3D game assets
Exec={exec_value}
Icon={icon}
Terminal=false
Categories=Graphics;3DGraphics;
StartupWMClass=FORGE
""")
    temporary_path = Path(temporary.name)

temporary_path.chmod(0o644)
temporary_path.replace(desktop_file)
print(f"Installed FORGE desktop launcher at {desktop_file}")
PY
