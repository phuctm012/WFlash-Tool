# PyInstaller spec (onedir). Build from the repo root: pyinstaller --noconfirm wflash.spec
import importlib.util

from PyInstaller.utils.hooks import collect_all

# wflash/resources holds the Teal stylesheets; wflash/gui/style.py finds them next to the
# package (__file__-relative), so they keep the same relative place inside the bundle.
datas = [("profiles", "profiles"), ("wflash/resources", "wflash/resources")]
binaries = []
hiddenimports = ["keyring.backends.Windows", "keyring.backends.macOS"]

# isystem.connect comes from the winIDEA 9.21 installation, not PyPI. Bundle it when the
# build machine has it; otherwise the .exe still runs with --adapter fake.
if importlib.util.find_spec("isystem") is not None:
    _datas, _binaries, _hidden = collect_all("isystem")
    datas += _datas
    binaries += _binaries
    hiddenimports += _hidden
else:
    print("WARNING: isystem.connect not installed; building without real winIDEA support")

a = Analysis(
    ["wflash/__main__.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="WFlash", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="WFlash")
