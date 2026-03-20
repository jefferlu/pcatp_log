@echo off
setlocal enabledelayedexpansion

echo ============================================
echo  ATP Log Analyzer - Windows Build Script
echo ============================================
echo.

:: ---------------------------------------------------------------------------
:: Find Python (try "py" launcher first, then "python")
:: ---------------------------------------------------------------------------
set PYTHON_CMD=

where py >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=py
    goto :found_python
)

where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_CMD=python
        goto :found_python
    )
)

echo [ERROR] Python 3.10+ not found.
echo Please install from https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation.
goto :end_pause

:found_python
for /f "tokens=*" %%v in ('!PYTHON_CMD! --version 2^>^&1') do echo [OK] Found: %%v
echo.

:: ---------------------------------------------------------------------------
:: Install dependencies
:: ---------------------------------------------------------------------------
echo [1/3] Installing dependencies...
!PYTHON_CMD! -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install dependencies.
    goto :end_pause
)

echo.
echo [2/3] Installing PyInstaller...
!PYTHON_CMD! -m pip install pyinstaller
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to install PyInstaller.
    goto :end_pause
)

:: ---------------------------------------------------------------------------
:: Clean previous build
:: ---------------------------------------------------------------------------
echo.
echo [3/3] Building executable...
if exist dist\ATPLogAnalyzer (
    echo Removing previous build...
    rmdir /s /q dist\ATPLogAnalyzer
)
if exist build\ATPLogAnalyzer (
    rmdir /s /q build\ATPLogAnalyzer
)

!PYTHON_CMD! -m PyInstaller ATPLogAnalyzer.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed. Check the output above for details.
    goto :end_pause
)

echo.
echo ============================================
echo  Build complete!
echo  Output: dist\ATPLogAnalyzer\ATPLogAnalyzer.exe
echo  Zip and distribute the dist\ATPLogAnalyzer\ folder.
echo ============================================

:end_pause
echo.
pause
