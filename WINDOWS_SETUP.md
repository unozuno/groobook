# 다른 윈도우 컴퓨터에서 설치하는 방법

## 1. 프로그램 설치 (최초 1회)

1. **Git**: https://git-scm.com/download/win 에서 받아 설치합니다. 옵션은 기본값으로 둡니다.
2. **Python 3.10 이상**: https://www.python.org/downloads/ 에서 받습니다.
   - 설치 첫 화면에서 **"Add python.exe to PATH"에 꼭 체크**하세요.
   - 서버 창(런처)에 쓰이는 tkinter가 기본 설치에 포함돼 있습니다. 설치 옵션에서 `tcl/tk`를 끄지 마세요.
3. **GTK3 런타임**: PDF 생성(WeasyPrint)에 필요합니다.
   - https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases 에서 최신 `gtk3-runtime-*-x64.exe`를 받아 설치합니다.
   - 설치 후 **PC를 재시작**하세요.

## 2. 저장소 받기

바탕화면 등 원하는 폴더에서 명령 프롬프트(cmd)나 PowerShell을 열고 입력합니다.

```bat
git clone https://github.com/unozuno/groobook.git
cd groobook
```

- 로그인 창이 뜨면 **`unozuno` 계정**으로 브라우저 로그인합니다.
- `Repository not found`가 나오면 이전 GitHub 계정 로그인이 저장돼 있는 겁니다. 제어판 → 자격 증명 관리자 → Windows 자격 증명에서 `git:https://github.com`을 삭제하고 다시 시도하세요.

## 3. 파이썬 환경 설치

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 4. 실행 파일 만들기 (더블클릭 실행용)

`groobook` 폴더 안의 `launcher\build_windows.bat`을 더블클릭합니다. 끝나면 프로젝트 폴더에 `grobook.exe`가 생깁니다.

- Windows Defender가 막으면 "추가 정보" → "실행"을 누릅니다.
- `grobook.exe`는 `venv`가 있는 `groobook` 폴더 안에 있어야 합니다. 바탕화면에 두려면 바로가기를 만드세요.

## 5. 실행

`grobook.exe`를 더블클릭하면 서버 창이 뜨고 브라우저가 열립니다. 직접 열려면 http://127.0.0.1:8000 으로 접속하세요. 창을 닫으면 서버가 종료됩니다.

터미널에서 직접 실행하는 방법도 있습니다.

```bat
venv\Scripts\activate
uvicorn main:app
```

## 6. 저장소에 없는 파일 옮기기

| 항목 | 방법 |
|---|---|
| 공통설정(주소록·이메일·단가표) | 기존 컴퓨터의 **공통설정 → 내보내기**로 파일을 저장하고, 새 컴퓨터의 **공통설정 → 가져오기**로 불러옵니다. |
| `.env` (메일 발송용) | 메일을 보낼 컴퓨터에만 필요합니다. 프로젝트 폴더에 `.env` 파일을 만들고 아래 두 줄을 넣습니다. |

```env
GMAIL_ADDRESS=메일주소@gmail.com
GMAIL_APP_PASSWORD=앱비밀번호16자리
```

공통발주서의 "청구서·마케팅팀 파일에 반영" 기능은 해당 엑셀 파일이 바탕화면에 있는 컴퓨터에서 실행할 때만 동작합니다.

## 7. 업데이트 받기

```bat
cd groobook
git pull
venv\Scripts\activate
pip install -r requirements.txt
```

서버를 껐다가 다시 켜면 반영됩니다. `launcher\launcher.py`가 바뀐 경우가 아니면 `grobook.exe`를 다시 만들 필요는 없습니다. `data` 폴더와 `.env`는 업데이트해도 그대로 유지됩니다.

## 자주 생기는 문제

- **`python`이 인식되지 않음**: Python 설치 때 PATH에 추가하지 않은 경우입니다. 재설치하면서 체크하세요.
- **PDF 생성 시 라이브러리 오류**: GTK3 런타임이 없거나 설치 후 재시작을 하지 않은 경우입니다.
- **`grobook.exe`를 눌러도 아무 일이 없음**: `venv` 폴더가 같은 위치에 없거나 8000번 포트를 다른 프로그램이 쓰고 있을 수 있습니다.
