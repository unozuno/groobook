@echo off
REM 프로젝트 루트에서 실행: launcher\build_windows.bat

setlocal

set "PROJECT_ROOT=%~dp0.."
set "VENV_PYTHON=%PROJECT_ROOT%\venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo 오류: %VENV_PYTHON% 를 찾을 수 없습니다.
    echo 프로젝트 루트에 venv가 설치되어 있는지 확인하세요.
    pause
    exit /b 1
)

echo PyInstaller 설치 중...
"%VENV_PYTHON%" -m pip install pyinstaller --quiet

echo 그루북.exe 빌드 중...
cd /d "%PROJECT_ROOT%"
"%VENV_PYTHON%" -m PyInstaller ^
  --name "그루북" ^
  --noconsole ^
  --onefile ^
  launcher\launcher.py ^
  --distpath "%PROJECT_ROOT%\dist_launcher" ^
  --workpath "%PROJECT_ROOT%\build_launcher" ^
  --specpath "%PROJECT_ROOT%\build_launcher"

if exist "%PROJECT_ROOT%\dist_launcher\그루북.exe" (
    if exist "%PROJECT_ROOT%\그루북.exe" del "%PROJECT_ROOT%\그루북.exe"
    move "%PROJECT_ROOT%\dist_launcher\그루북.exe" "%PROJECT_ROOT%\그루북.exe"
    echo.
    echo 완료: 그루북.exe 생성됨
    echo 배포 전 첫 실행 테스트를 진행하세요.
    echo.
    echo 참고: Windows Defender 경고가 뜰 경우
    echo   ^-^> "추가 정보" 클릭 ^-^> "실행" 클릭
) else (
    echo 빌드 실패: dist_launcher\그루북.exe 를 찾을 수 없습니다.
    pause
    exit /b 1
)

REM 임시 빌드 폴더 정리
if exist "%PROJECT_ROOT%\dist_launcher" rmdir /s /q "%PROJECT_ROOT%\dist_launcher"
if exist "%PROJECT_ROOT%\build_launcher" rmdir /s /q "%PROJECT_ROOT%\build_launcher"

pause
