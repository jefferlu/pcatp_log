@echo off
setlocal

echo ============================================
echo  ATP Log Analyzer - Windows Build Script
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

:: Install / upgrade dependencies
echo [1/3] Installing dependencies...
pip install -r requirements.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

pip install pyinstaller --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install PyInstaller.
    pause
    exit /b 1
)

:: Clean previous build
echo [2/3] Cleaning previous build...
if exist dist\ATPLogAnalyzer rmdir /s /q dist\ATPLogAnalyzer
if exist build\ATPLogAnalyzer rmdir /s /q build\ATPLogAnalyzer

:: Build
echo [3/3] Building executable...
pyinstaller ATPLogAnalyzer.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build complete!
echo  Output: dist\ATPLogAnalyzer\ATPLogAnalyzer.exe
echo  Distribute the entire dist\ATPLogAnalyzer\ folder.
echo ============================================
pause
