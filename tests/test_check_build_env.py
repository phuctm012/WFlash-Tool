import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_check_build_env_passes_in_the_dev_env_without_pip():
    """The Windows build machine has no pypi.org (user report): the check must say pip is not needed."""
    done = subprocess.run([sys.executable, str(ROOT / "tools" / "check_build_env.py")],
                          cwd=ROOT, capture_output=True, text=True)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "pip is not needed" in done.stdout


def test_check_build_env_names_what_pip_would_install(monkeypatch):
    sys.path.insert(0, str(ROOT / "tools"))
    import check_build_env
    monkeypatch.setitem(check_build_env.NEEDED, "no_such_module_xyz", "no-such-package")
    assert check_build_env.missing_modules() == ["no-such-package"]
