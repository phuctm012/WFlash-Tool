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
