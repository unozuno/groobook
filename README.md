# 그루북 업무 자동화 웹앱

그루북 업무를 자동화하는 내부용 웹 애플리케이션입니다.

## 지원 작업

- **내신노트** — 비법전수 내신노트 포장전표 (밴딩 30 고정)
- **분기별교재** — 분기별 교재 포장전표 (밴딩 파일에서 자동 읽기)
- **중간기말교재** — 중간/기말고사 교재 포장전표 (본책 · 미니북 · 교사용)
- **청구서 메일 발송** — 청구서 엑셀 파일명에서 학원을 찾아 주소록의 이메일로 Gmail 발송
- **공통발주서** — 발주서·납품서 엑셀 생성, 단가표 자동 단가, 바탕화면 청구서·마케팅팀 파일에 반영
- **공통설정** — 제작 종류, 선택지, 단가표, 학원 주소록(이메일 포함) 관리

개발 규칙과 내부 구조는 [CLAUDE.md](CLAUDE.md), 서버 배포는 [deploy/README.md](deploy/README.md) 를 참고하세요.

---

## 설치 및 실행

### 공통 사전 준비

**Python 3.10 이상** 이 필요합니다.

```bash
# 저장소 클론 (private 저장소라 GitHub 로그인이 필요합니다. 아래 '다른 컴퓨터에서 사용하기' 참고)
git clone https://github.com/unozuno/groobook.git
cd groobook
```

---

### Windows

**1. WeasyPrint 의존 라이브러리 설치**

GTK 런타임이 필요합니다.
아래 링크에서 GTK3 런타임 인스톨러를 받아 설치하세요.
https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases
(최신 `gtk3-runtime-*-x64.exe` 다운로드 후 실행)

설치 후 **PC 재시작**을 권장합니다.

**2. Python 패키지 설치 및 실행**

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

브라우저에서 http://127.0.0.1:8000 접속

---

### macOS

**1. WeasyPrint 의존 라이브러리 설치** (Homebrew 필요)

```bash
brew install pango glib
```

**2. 라이브러리 경로 설정** (최초 1회)

```bash
echo 'export DYLD_LIBRARY_PATH=/opt/homebrew/lib' >> ~/.zshrc
source ~/.zshrc
```

> Intel Mac의 경우 `/opt/homebrew` 대신 `/usr/local` 을 사용하세요.

**3. Python 패키지 설치 및 실행**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

브라우저에서 http://127.0.0.1:8000 접속

---

### Linux (Ubuntu / Debian)

**1. WeasyPrint 의존 라이브러리 설치**

```bash
sudo apt update
sudo apt install -y libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0
```

**2. Python 패키지 설치 및 실행**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

브라우저에서 http://127.0.0.1:8000 접속

---

## AWS EC2 배포 (Ubuntu)

```bash
# 의존 라이브러리
sudo apt update
sudo apt install -y libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf2.0-0 nginx

# 앱 실행 (백그라운드)
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000 &

# Nginx 리버스 프록시 설정
sudo nano /etc/nginx/sites-available/groobook
```

Nginx 설정 내용:

```nginx
server {
    listen 80;
    server_name your-domain.duckdns.org;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/groobook /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 다른 컴퓨터에서 사용하기

저장소가 private 이므로 **저장소 접근 권한이 있는 GitHub 계정(`unozuno`)으로 로그인**해야 받을 수 있습니다.

### 1. 최초 설치

1. **Git 과 Python 3.10 이상** 을 설치합니다. (macOS: `brew install git python`, Windows: git-scm.com / python.org 에서 설치)
2. 위 '설치 및 실행'의 **OS별 사전 준비**(WeasyPrint 라이브러리)를 합니다.
3. 저장소를 받습니다.
   ```bash
   git clone https://github.com/unozuno/groobook.git
   cd groobook
   ```
   - 처음 받을 때 로그인 창이 뜨면 `unozuno` 계정으로 브라우저 로그인합니다. (Windows/macOS 는 Git 이 로그인 정보를 저장해 두므로 다음부터는 묻지 않습니다.)
   - 창이 안 뜨고 비밀번호를 물으면 비밀번호 대신 **Personal Access Token** 을 입력합니다. 발급: <https://github.com/settings/tokens/new> → `repo` 체크.
   - 이전에 다른 GitHub 계정으로 로그인한 컴퓨터라면 `Repository not found` 가 나올 수 있습니다. 저장된 로그인을 지우고 다시 시도하세요 (Windows: 제어판 → 자격 증명 관리자 → `github.com` 삭제 / macOS: 키체인 접근 → `github.com` 삭제).
4. 가상환경을 만들고 패키지를 설치한 뒤 실행합니다.
   ```bash
   python3 -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn main:app --reload
   ```
   브라우저에서 <http://127.0.0.1:8000> 접속.

### 2. 저장소에 없는 파일 (이 컴퓨터에서 따로 준비)

`.gitignore` 로 제외돼 있어 `git clone` 으로는 오지 않습니다.

| 항목 | 설명 |
|---|---|
| `.env` | 청구서 메일 발송용. 프로젝트 루트에 만들고 `GMAIL_ADDRESS=…` / `GMAIL_APP_PASSWORD=…` 를 적습니다. 메일 기능을 쓰는 컴퓨터에만 필요합니다. |
| `data/` | 공통설정(주소록·이메일·단가표)과 발주 기록. 처음 실행하면 기본값으로 자동 생성됩니다. **컴퓨터마다 따로**라서, 기존 컴퓨터의 설정을 쓰려면 기존 컴퓨터의 공통설정 화면에서 **내보내기** → 새 컴퓨터의 공통설정에서 **가져오기** 하세요. |
| `sample/` | 개발용 참조 엑셀. 일반 사용에는 필요 없습니다. |

공통발주서의 **바탕화면 파일 반영**은 청구서·마케팅팀 파일이 있는 컴퓨터에서 서버를 실행해야 동작합니다.

### 3. 최신 버전으로 업데이트

```bash
cd groobook
git pull
pip install -r requirements.txt     # 패키지가 바뀐 경우를 대비해 함께 실행
```

실행 중인 서버는 껐다가 다시 시작합니다. 코드가 바뀌어도 `data/` 와 `.env` 는 그대로 유지됩니다.

### 4. 작업하고 올리기

```bash
git add -A
git commit -m "fix: 수정 내용"
git push
```

> `git config user.name` / `user.email` 을 컴퓨터마다 한 번 설정해야 커밋 작성자가 올바르게 기록됩니다.

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| 백엔드 | FastAPI, Python 3.10+ |
| PDF 생성 | WeasyPrint (HTML → PDF) |
| Excel 파싱 | openpyxl |
| 프론트엔드 | HTML / CSS / Vanilla JS |
