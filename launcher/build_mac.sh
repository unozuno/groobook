#!/bin/bash
# 프로젝트 루트에서 실행: bash launcher/build_mac.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_ROOT/venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
  echo "오류: $VENV_PYTHON 를 찾을 수 없습니다."
  echo "프로젝트 루트에 venv가 설치되어 있는지 확인하세요."
  exit 1
fi

echo "PyInstaller 설치 중..."
"$VENV_PYTHON" -m pip install pyinstaller --quiet

echo "그루북.app 빌드 중..."
cd "$PROJECT_ROOT"
"$VENV_PYTHON" -m PyInstaller \
  --name "그루북" \
  --windowed \
  --onefile \
  launcher/launcher.py \
  --distpath "$PROJECT_ROOT/dist_launcher" \
  --workpath "$PROJECT_ROOT/build_launcher" \
  --specpath "$PROJECT_ROOT/build_launcher"

# 빌드 결과물을 프로젝트 루트로 이동
if [ -d "$PROJECT_ROOT/dist_launcher/그루북.app" ]; then
  rm -rf "$PROJECT_ROOT/그루북.app"
  mv "$PROJECT_ROOT/dist_launcher/그루북.app" "$PROJECT_ROOT/그루북.app"
  echo ""
  echo "완료: 그루북.app 생성됨"
  echo "배포 전 첫 실행 테스트를 진행하세요."
  echo ""
  echo "참고: macOS Gatekeeper 경고가 뜰 경우"
  echo "  → 그루북.app 우클릭 → '열기' → '열기' 버튼 클릭"
  echo "  (이후 실행부터는 경고 없음)"
else
  echo "빌드 실패: dist_launcher/그루북.app 를 찾을 수 없습니다."
  exit 1
fi

# 임시 빌드 폴더 정리
rm -rf "$PROJECT_ROOT/dist_launcher" "$PROJECT_ROOT/build_launcher"
