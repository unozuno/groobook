# Groobook Web 배포 가이드 (AWS EC2 + DuckDNS)

> ⚠️ **중요**: 이 문서는 실제 배포 경험을 통해 검증된 실패 해결 방법을 포함합니다.

## 📋 사전 준비

### 사용자가 해야 할 일 (AWS 콘솔 + 외부 서비스)

#### 1. AWS EC2 인스턴스 생성

**중요**: Amazon Linux 2023 (kernel-6.1) AMI를 선택하세요.

- **AMI**: Amazon Linux 2023 (kernel-6.1) — `apt` 대신 `dnf` 사용
- **Instance Type**: t2.micro (Free Tier)
- **Key Pair**: 새로 생성 후 `.pem` 파일 **로컬에 저장**
- **Security Group 인바운드 규칙**:
  - SSH (22): 내 IP 또는 0.0.0.0/0
  - HTTP (80): 0.0.0.0/0
  - (HTTPS 필요 시 443도 추가)
- **Storage**: 8GB gp2 (기본값)

인스턴스 시작 후 **퍼블릭 IPv4 주소** 메모.

#### 2. DuckDNS 도메인 생성

1. [https://www.duckdns.org](https://www.duckdns.org) 접속
2. Google/GitHub로 로그인
3. 원하는 서브도메인 생성 (예: `groobook`)
4. **EC2 퍼블릭 IP 입력** 후 `update` 클릭
5. **Token 메모** (배포 스크립트에 필요)

> ⚠️ **주의**: 나중에 EC2를 재시작하면 IP가 바뀝니다. DuckDNS cron이 자동으로 5분 내에 갱신합니다.

---

## 🚀 배포 프로세스

### Step 1: EC2에 SSH 접속

```bash
ssh -i your-key.pem ec2-user@<EC2-퍼블릭-IP>
```

예:
```bash
ssh -i ~/Downloads/groobook-key.pem ec2-user@3.39.255.162
```

### Step 2: 프로젝트 클론 및 배포 스크립트 실행

```bash
cd /home/ec2-user
git clone https://github.com/unozuno/groobook.git groobook-web
cd groobook-web
bash deploy/setup.sh <DUCKDNS_TOKEN> <DUCKDNS_DOMAIN>
```

예:
```bash
bash deploy/setup.sh abc123xyz456token789 groobook
```

**이 스크립트가 자동으로 설치하는 것:**
- ✅ Python 3, pip, venv
- ✅ WeasyPrint 시스템 라이브러리 (pango, gdk-pixbuf2, cairo)
- ✅ Nginx 리버스 프록시
- ✅ systemd groobook 서비스 (자동 재시작)
- ✅ DuckDNS cron 스크립트 (5분마다 IP 자동 갱신)

> ⚠️ **실패 이력**: 초기에 `.env` 파일이 없으면 systemd 서비스가 시작 실패. 현재는 `-` 플래그로 해결되어 있습니다.

### Step 3: .env 파일 생성

```bash
nano /home/ec2-user/groobook-web/.env
```

다음 내용 입력:
```env
AUTH_CODE=<실제인증코드>
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
```

저장: `Ctrl+X` → `Y` → `Enter`

### Step 4: 서비스 재시작

```bash
sudo systemctl restart groobook
sudo systemctl status groobook
```

`active (running)` 확인.

> ⚠️ **실패 이력**: 첫 시작 시 WeasyPrint 로드로 90초 이상 걸림. 현재 `Type=simple`로 설정되어 있어서 타임아웃 없습니다.

### Step 5: campus_emails.json 업로드

**로컬 터미널에서** (EC2가 아닌 자신의 컴퓨터):
```bash
scp -i your-key.pem campus_emails.json ec2-user@<EC2-IP>:/home/ec2-user/groobook-web/
```

예:
```bash
scp -i ~/Downloads/groobook-key.pem campus_emails.json ec2-user@3.39.255.162:/home/ec2-user/groobook-web/
```

### Step 6: Nginx 설정 확인 및 고정

> ⚠️ **실패 이력**: 기본 Nginx server 블록이 활성화되어 있어서 groobook이 아닌 "Welcome to nginx!" 페이지만 보임.

EC2에서:
```bash
sudo nano /etc/nginx/nginx.conf
```

다음 부분을 찾아서 **전체를 주석 처리**하세요:

```nginx
# server {
#     listen       80;
#     listen       [::]:80;
#     server_name  _;
#     root         /usr/share/nginx/html;
#
#     # Load configuration files for the default server block.
#     include /etc/nginx/default.d/*.conf;
#
#     error_page 404 /404.html;
#     location = /404.html {
#     }
#
#     error_page 500 502 503 504 /50x.html;
#     location = /50x.html {
#     }
# }
```

저장 후:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Step 7: 정적 파일 권한 설정

> ⚠️ **실패 이력**: CSS/JS 파일이 403 Forbidden으로 로드 안 됨.

EC2에서:
```bash
# Nginx 워커를 ec2-user로 실행하도록 변경
sudo nano /etc/nginx/nginx.conf
```

첫 줄을:
```nginx
user ec2-user;
```

로 변경.

저장 후:
```bash
sudo systemctl reload nginx
```

또는 권한 수정:
```bash
sudo chown -R nginx:nginx /home/ec2-user/groobook-web/static
sudo chmod -R 755 /home/ec2-user/groobook-web/static
```

---

## ✅ 배포 검증

### 1. localhost에서 확인 (EC2에서)

```bash
curl -s http://localhost/ | head -20
```

그루북 HTML이 나오면 정상.

### 2. 정적 파일 확인 (EC2에서)

```bash
curl -s http://localhost/static/css/style.css | head -5
```

CSS 내용이 나오면 정상.

### 3. 브라우저에서 확인

```
http://<DUCKDNS_DOMAIN>.duckdns.org
```

예: `http://groobook.duckdns.org`

로그인 페이지가 정상적으로 **스타일과 함께** 표시되면 **배포 완료!** ✅

---

## 🔧 배포 후 유지보수

### 코드 변경 후 서버에 적용하기

**로컬에서 코드 수정 후:**
```bash
git add .
git commit -m "fix: 뭔가 수정함"
git push origin main
```

**EC2에서:**
```bash
cd /home/ec2-user/groobook-web
git pull
sudo systemctl restart groobook
```

이제 변경사항이 서버에 반영됩니다.

#### ⚠️ git pull로 갱신되지 않는 파일들

다음 파일들은 git에 없으므로 `git pull` 후에도 변경되지 않습니다:

- **`.env`**: 로컬 환경변수 파일
  - EC2에서 직접 수정: `nano /home/ec2-user/groobook-web/.env`
  - 수정 후 서비스 재시작: `sudo systemctl restart groobook`

- **`campus_emails.json`**: 캠퍼스 이메일 매핑 파일
  - 로컬에서 업로드: `scp -i key.pem campus_emails.json ec2-user@<IP>:/home/ec2-user/groobook-web/`

---

### 서비스 상태 확인

```bash
sudo systemctl status groobook
sudo systemctl status nginx
```

### 로그 확인

```bash
# Uvicorn 로그 (실시간)
sudo journalctl -u groobook -f

# Uvicorn 로그 (최근 100줄)
sudo journalctl -u groobook -n 100

# Nginx 에러 로그
sudo tail -50 /var/log/nginx/groobook_error.log

# Nginx 접근 로그
sudo tail -50 /var/log/nginx/groobook_access.log
```

### 서비스 재시작

```bash
sudo systemctl restart groobook
```

### Python 패키지 업그레이드

```bash
cd /home/ec2-user/groobook-web
source venv/bin/activate
pip install -U -r requirements.txt
sudo systemctl restart groobook
```

### DuckDNS 자동 업데이트 확인

```bash
# 최근 업데이트 결과
cat ~/duckdns/duck.log

# cron 작업 확인
crontab -l
```

---

## ⚠️ 알려진 이슈 및 해결

### 1. systemd 서비스가 계속 재시작되는 경우

**증상**: `sudo systemctl status groobook`에서 계속 재시작 중

**원인**: Python 임포트 오류 (문법 오류, 패키지 미설치 등)

**해결**:
```bash
sudo journalctl -u groobook -n 50
```

로그에서 오류 메시지 확인 후 수정.

### 2. 브라우저에서 "연결할 수 없음" 오류

**증상**: `http://groobook.duckdns.org` 접속 불가

**확인**:
```bash
# 1. Nginx가 포트 80을 리스닝하는지 확인
sudo netstat -tlnp | grep 80

# 2. DuckDNS가 올바른 IP를 가리키는지 확인
nslookup groobook.duckdns.org

# 3. EC2 Security Group에서 HTTP (80)이 열려있는지 AWS 콘솔에서 확인
```

**해결**:
- DuckDNS IP가 틀리면 [https://www.duckdns.org](https://www.duckdns.org)에서 수동으로 업데이트
- Security Group 규칙 확인 및 수정

### 3. CSS/JS 파일이 로드되지 않음 (403 Forbidden)

**증상**: 웹사이트에 스타일 없이 순수 HTML만 보임

**원인**: Nginx 워커 프로세스가 정적 파일을 읽을 수 없음

**해결** (두 가지 방법 중 하나):

**방법 1**: Nginx를 ec2-user로 실행 (권장)
```bash
sudo nano /etc/nginx/nginx.conf
# user nginx; → user ec2-user; 로 변경
sudo systemctl reload nginx
```

**방법 2**: 파일 권한 변경
```bash
sudo chown -R nginx:nginx /home/ec2-user/groobook-web/static
sudo chmod -R 755 /home/ec2-user/groobook-web/static
sudo systemctl reload nginx
```

---

## 💰 비용 추정

| 항목 | 비용 |
|---|---|
| EC2 t2.micro | 프리 티어: 12개월 무료, 이후 월 ~$8-10 |
| 데이터 전송 | 월 15GB 이내 무료 |
| DuckDNS 도메인 | 무료 ∞ |
| **총합** | **프리 티어: 무료, 이후 월 ~$8-10** |

---

## 📝 체크리스트 (새로 배포할 때)

- [ ] AWS EC2 t2.micro 생성 (Amazon Linux 2023)
- [ ] Security Group: SSH (22) + HTTP (80) 열기
- [ ] DuckDNS 도메인 생성 및 EC2 IP 입력
- [ ] EC2에 SSH 접속
- [ ] 프로젝트 클론 및 deploy/setup.sh 실행
- [ ] .env 파일 생성
- [ ] campus_emails.json 업로드
- [ ] Nginx 기본 server 블록 주석 처리
- [ ] Nginx user를 ec2-user로 변경
- [ ] localhost에서 curl 테스트
- [ ] 브라우저에서 DuckDNS 도메인 접속 확인
- [ ] 스타일이 포함되어 있는지 확인

---

## 🆘 추가 도움말

### 서비스 로그를 파이프로 보내기

```bash
sudo journalctl -u groobook -f --no-pager
```

### Nginx 설정 문법 검사

```bash
sudo nginx -t -c /etc/nginx/nginx.conf
```

### 포트 점유 상태 확인

```bash
sudo netstat -tlnp | grep -E ':(80|8000)'
```

### Nginx 설정 재로드 (재시작 없이)

```bash
sudo systemctl reload nginx
```

---

**마지막 업데이트**: 2026-03-26
**성공한 배포 환경**: Amazon Linux 2023 (kernel-6.1), EC2 t2.micro, DuckDNS
