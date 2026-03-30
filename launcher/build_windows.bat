@echo off
REM Run from project root: launcher\build_windows.bat

setlocal

set "PROJECT_ROOT=%~dp0.."
set "VENV_PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo ERROR: venv not found at %VENV_PYTHON%
    echo Please create venv first: python -m venv venv
    pause
    exit /b 1
)

echo Installing PyInstaller...
"%VENV_PYTHON%" -m pip install pyinstaller --quiet

echo Building grobook.exe...
cd /d "%PROJECT_ROOT%"
"%VENV_PYTHON%" -m PyInstaller ^
  --name "grobook" ^
  --noconsole ^
  --onefile ^
  launcher\launcher.py ^
  --distpath "%PROJECT_ROOT%\dist_launcher" ^
  --workpath "%PROJECT_ROOT%\build_launcher" ^
  --specpath "%PROJECT_ROOT%\build_launcher"

if exist "%PROJECT_ROOT%\dist_launcher\grobook.exe" (
    if exist "%PROJECT_ROOT%\grobook.exe" del "%PROJECT_ROOT%\grobook.exe"
    move "%PROJECT_ROOT%\dist_launcher\grobook.exe" "%PROJECT_ROOT%\grobook.exe"
    echo.
    echo Done: grobook.exe created in project root.
    echo.
    echo NOTE: If Windows Defender blocks it,
    echo   click "More info" then "Run anyway"
) else (
    echo Build failed: grobook.exe not found in dist_launcher.
    pause
    exit /b 1
)

REM Cleanup temp build folders
if exist "%PROJECT_ROOT%\dist_launcher" rmdir /s /q "%PROJECT_ROOT%\dist_launcher"
if exist "%PROJECT_ROOT%\build_launcher" rmdir /s /q "%PROJECT_ROOT%\build_launcher"

pause
