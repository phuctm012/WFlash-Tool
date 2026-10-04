@echo off
rem Build dist\WFlash\WFlash.exe (onedir). Run from anywhere; it works from the repo root.
setlocal
cd /d "%~dp0\.."
set VENV=%USERPROFILE%\.venvs\wflash
if not exist "%VENV%\Scripts\python.exe" py -3 -m venv "%VENV%" || exit /b 1
set PY=%VENV%\Scripts\python.exe
"%PY%" -m pip install --upgrade pip || exit /b 1
"%PY%" -m pip install -e ".[dev]" || exit /b 1
rem isystem.connect is NOT on PyPI: install it from the winIDEA 9.21 installation (spike\README.md).
"%PY%" -c "import isystem.connect as ic; print('isystem.connect:', ic.__file__)" || echo WARNING: isystem.connect is not installed - the build will only support --adapter fake.
set QT_QPA_PLATFORM=offscreen
"%PY%" -m pytest -q || exit /b 1
"%PY%" -m pytest -k thread -q || exit /b 1
"%PY%" tools\stress_test.py || exit /b 1
set QT_QPA_PLATFORM=
"%PY%" -m PyInstaller --noconfirm wflash.spec || exit /b 1
echo.
echo Built: dist\WFlash\WFlash.exe  (copy the whole dist\WFlash folder)
