"""The build must ship everything the app reads at runtime."""
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_pyinstaller_spec_bundles_the_stylesheets():
    spec = (REPO / "wflash.spec").read_text(encoding="utf-8")
    assert '("wflash/resources", "wflash/resources")' in spec
    assert '("profiles", "profiles")' in spec


def test_package_data_includes_the_stylesheets():
    data = tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))
    assert "resources/*.qss" in data["tool"]["setuptools"]["package-data"]["wflash"]
    for name in ("style.qss", "style_dark.qss"):
        assert (REPO / "wflash" / "resources" / name).is_file()
