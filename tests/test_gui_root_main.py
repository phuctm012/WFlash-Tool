"""`python main.py` at the repo root launches the same app as `python -m wflash`."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.gui

REPO = Path(__file__).resolve().parents[1]


def run_root_main(cwd: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    return subprocess.run(
        [sys.executable, str(REPO / "main.py"), "--adapter", "fake", "--smoke"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_gui_root_main_smoke_from_repo_root():
    result = run_root_main(REPO)
    assert result.returncode == 0, result.stderr


def test_gui_root_main_smoke_from_other_directory(tmp_path):
    result = run_root_main(tmp_path)
    assert result.returncode == 0, result.stderr


def test_gui_root_main_smoke_in_dark_mode(tmp_path):
    """The saved dark_mode setting is applied at start-up without breaking the launch."""
    import json

    home = tmp_path / "home"
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "HOME": str(home),
        "USERPROFILE": str(home),
        "APPDATA": str(home / "AppData" / "Roaming"),
        "LOCALAPPDATA": str(home / "AppData" / "Local"),
    }
    # The locations config_dir() and default_log_dir() compute, under the fake home.
    if sys.platform == "win32":
        config, logs = home / "AppData" / "Roaming" / "WFlash", home / "AppData" / "Local" / "WFlash" / "logs"
    elif sys.platform == "darwin":
        config, logs = home / "Library" / "Application Support" / "WFlash", home / "Library" / "Logs" / "WFlash"
    else:
        config, logs = home / ".config" / "wflash", home / ".local" / "state" / "wflash" / "logs"
    config.mkdir(parents=True)
    (config / "settings.json").write_text(json.dumps({"dark_mode": True}), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(REPO / "main.py"), "--adapter", "fake", "--smoke"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    log_text = "".join(p.read_text(encoding="utf-8") for p in logs.glob("wflash_*.log"))
    assert "Theme: dark" in log_text
