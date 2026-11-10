@echo off
rem Build dist\WFlash\WFlash.exe (onedir). Run from anywhere; it works from the repo root.
rem Uses the active conda env (conda activate wflash) if there is one, else the venv %USERPROFILE%\.venvs\wflash.
setlocal
cd /d "%~dp0\.."
if not defined CONDA_PREFIX goto use_venv
if /i "%CONDA_DEFAULT_ENV%"=="base" (
    echo ERROR: the conda "base" env is active. Run "conda activate wflash" first ^(docs\windows_test_guide.md^).
    exit /b 1
)
set PY=%CONDA_PREFIX%\python.exe
echo Using conda env %CONDA_DEFAULT_ENV%: %PY%
goto have_python
:use_venv
set VENV=%USERPROFILE%\.venvs\wflash
if not exist "%VENV%\Scripts\python.exe" py -3 -m venv "%VENV%" || exit /b 1
set PY=%VENV%\Scripts\python.exe
echo Using venv: %PY%
:have_python
rem pip only when something is missing: build PCs often cannot reach pypi.org (user report, 2026-11-10).
"%PY%" tools\check_build_env.py
if errorlevel 3 exit /b 1
if not errorlevel 2 goto deps_ready
"%PY%" -m pip install -e ".[dev]"
if errorlevel 1 (
    echo ERROR: pip could not install the missing modules listed above ^(no access to pypi.org?^).
    echo        Behind a proxy: set PIP_PROXY=http://^<user^>:^<password^>@^<proxy^>:^<port^> in this window, then build again.
    echo        Never write the proxy password into this script: it would be committed.
    exit /b 1
)
:deps_ready
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
