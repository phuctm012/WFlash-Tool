"""Before building WFlash.exe: is everything already in this Python env? (Run from the repo root.)

Exit 0: ready, nothing to install. Exit 2: modules are missing (the build script then tries pip).
Exit 3: `wflash` would be imported from another folder than this repo, so the exe would contain
old code. Build machines often have no access to pypi.org, so pip runs only when it must.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# import name -> what pip calls it
NEEDED = {
    "PySide6": "PySide6", "requests": "requests", "pydantic": "pydantic", "yaml": "PyYAML",
    "keyring": "keyring", "truststore": "truststore", "pytest": "pytest", "pytestqt": "pytest-qt",
    "responses": "responses", "PyInstaller": "pyinstaller", "hid": "hidapi",  # USB relay, benches 1 and 4
}


def missing_modules() -> list[str]:
    return [pip_name for module, pip_name in NEEDED.items() if importlib.util.find_spec(module) is None]


def wflash_folder() -> Path | None:
    sys.path.insert(0, str(ROOT))  # as pytest and PyInstaller (pathex=".") see it from the repo root
    spec = importlib.util.find_spec("wflash")
    return Path(spec.origin).resolve().parent if spec and spec.origin else None


def main() -> int:
    folder = wflash_folder()
    if folder != ROOT / "wflash":
        print(f"ERROR: wflash is imported from {folder}, not from {ROOT / 'wflash'}.")
        print("       Run: python -m pip uninstall -y wflash   (works offline), then build again.")
        return 3
    print(f"wflash: {folder}")
    missing = missing_modules()
    if missing:
        print("Missing in this env: " + ", ".join(missing))
        return 2
    print("All build dependencies are installed; pip is not needed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
