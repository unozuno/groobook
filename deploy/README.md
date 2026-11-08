# AWS EC2 + DuckDNS 배포 가이드 (Amazon Linux 2023)

## 📋 사전 준비사항

### 사용자가 해야 할 일 (외부 서비스)

1. **AWS 콘솔에서 EC2 생성**
   - AMI: Amazon Linux 2023 (kernel-6.1)
   - Instance Type: t2.micro (Free Tier)
   - Key pair: 새로 생성 후 `.pem` 파일 저장
   - Security Group 인바운드 규칙:
     - SSH (22): 내 IP
     - HTTP (80): 0.0.0.0/0
   - 인스턴스 시작 후 **퍼블릭 IPv4 주소** 메모

2. **DuckDNS 가입 및 도메인 생성**
   - [https://www.duckdns.org](https://www.duckdns.org) 접속
   - Google/GitHub 로그인
   - 원하는 서브도메인 생성 (예: `groobook`)
   - EC2 퍼블릭 IP 입력
   - **Token** 메모 (배포 스크립트에 필요)

3. **로컬에서 준비**
   - `.env` 파일 생성 (다음 섹션 참조)
   - `campus_emails.json` 준비 (git-ignored 파일)

---

## 🚀 배포 프로세스

### Step 1: EC2에 SSH 접속

```bash
# 로컬 터미널에서
ssh -i your-key.pem ec2-user@<EC2-퍼블릭-IP>
```

### Step 2: 프로젝트 클론

```bash
cd /home/ec2-user
git clone <your-repo-url> groobook-web
cd groobook-web
```

### Step 3: 배포 스크립트 실행

```bash
bash deploy/setup.sh <DUCKDNS_TOKEN> <DUCKDNS_DOMAIN>
```

**예:**
```bash
bash deploy/setup.sh abc123xyz456token789 groobook
```

이 스크립트가 자동으로:
- ✓ 시스템 패키지 설치 (Python, Nginx, WeasyPrint 라이브러리)
- ✓ Python 가상환경 및 의존성 설치
- ✓ systemd 서비스 등록 (자동 재시작)
- ✓ Nginx 리버스 프록시 설정
- ✓ DuckDNS 자동 업데이트 cron 등록

### Step 4: .env 파일 생성

```bash
nano .env
```

다음 내용 입력:
```
AUTH_CODE=실제_인증_코드
GMAIL_ADDRESS=your-email@gmail.com
GMAIL_APP_PASSWORD=your-16-char-app-password
```

저장 후 종료 (`Ctrl+X` → `Y` → `Enter`)

### Step 5: campus_emails.json 업로드

로컬에서:
```bash
scp -i your-key.pem campus_emails.json ec2-user@<EC2-IP>:/home/ec2-user/groobook-web/
```

### Step 5-1: 공통발주서 데이터 폴더 (`data/`)

공통발주서 설정(`data/order_settings.json`)과 발주 원본(`data/orders/*.json`)은 서버가 첫 요청 때 자동으로 만듭니다.
- git 에 포함되지 않으므로 `git pull` 로 코드를 갱신해도 설정은 유지됩니다.
- 백업은 `data/` 폴더를 통째로 복사하면 됩니다. 다른 위치에 두려면 서비스 환경변수 `GROOBOOK_DATA_DIR` 를 지정합니다.
- 설정은 반드시 웹 화면(`/order-settings`)에서 수정하고, 서버 실행 중에 파일을 직접 편집하지 않습니다.

### Step 6: 서비스 상태 확인

```bash
sudo systemctl status groobook
```

출력:
```
● groobook.service - Groobook Web App
     Loaded: loaded (/etc/systemd/system/groobook.service; enabled; vendor preset: enabled)
     Active: active (running) since ...
```

---

## ✅ 배포 검증

### 1. 웹 접속 확인

```bash
curl http://<DUCKDNS_DOMAIN>.duckdns.org
```

또는 브라우저에서 `http://<DUCKDNS_DOMAIN>.duckdns.org` 접속

### 2. 서비스 로그 확인

```bash
# 실시간 로그
sudo journalctl -u groobook -f

# 최근 50줄
sudo journalctl -u groobook -n 50
```

### 3. Nginx 상태

```bash
sudo systemctl status nginx
sudo nginx -t  # 설정 문법 검사
```

### 4. DuckDNS 자동 업데이트 확인

```bash
cat ~/duckdns/duck.log  # 최근 업데이트 결과
crontab -l              # cron 작업 확인
```

---

## ⚙️ 배포 후 유지보수

### 서비스 재시작

```bash
sudo systemctl restart groobook
```

### 로그 확인

```bash
sudo journalctl -u groobook -n 100  # 최근 100줄
```

### Python 패키지 업그레이드

```bash
cd /home/ubuntu/groobook-web
source venv/bin/activate
pip install -U -r requirements.txt
sudo systemctl restart groobook
```

### Nginx 재시작

```bash
sudo systemctl reload nginx
```

---

## ⚠️ 주의사항

### IP 변경 대응

EC2를 **Stop → Start** 하면 퍼블릭 IP가 변경됩니다.
- ✓ DuckDNS cron이 5분마다 자동으로 IP를 갱신하므로 수동 업데이트 불필요
- ✓ 최대 5분 후 도메인으로 다시 접속 가능

### HTTPS 적용 (선택사항)

HTTP만으로 배포되어 있습니다. HTTPS가 필요하면:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d <DUCKDNS_DOMAIN>.duckdns.org
```

### 로그 저장소

- Nginx: `/var/log/nginx/groobook_access.log`
- systemd: `sudo journalctl -u groobook`

---

## 📊 예상 비용

| 항목 | 비용 |
|---|---|
| EC2 t2.micro | 프리 티어: 12개월 무료, 이후 월 ~$8-10 |
| 데이터 전송 | 월 15GB 이내 무료 |
| DuckDNS | 무료 ∞ |
| **총합** | **프리 티어: 무료, 이후 월 ~$8-10** |

---

## 🆘 트러블슈팅

### 웹사이트가 접속 안 됨

```bash
# 1. 서비스 상태 확인
sudo systemctl status groobook

# 2. 포트 8000 리스닝 확인
sudo netstat -tlnp | grep 8000

# 3. Nginx 상태 확인
sudo systemctl status nginx

# 4. 로그 확인
sudo journalctl -u groobook -n 50
```

### 파일 업로드 안 됨

- Nginx `client_max_body_size`를 확인하세요 (현재 50MB)
- `/var/log/nginx/groobook_error.log` 확인

### 이메일 발송 실패

```bash
# .env 파일 확인
cat .env

# 서비스 재시작
sudo systemctl restart groobook

# 로그 확인
sudo journalctl -u groobook -f
```

### DuckDNS 자동 업데이트 작동 안 함

```bash
# 스크립트 수동 실행
~/duckdns/duck.sh

# 결과 확인
cat ~/duckdns/duck.log

# cron 작업 확인
crontab -l
```

---

## 📚 추가 참고자료

- [FastAPI 배포 공식 문서](https://fastapi.tiangolo.com/deployment/concepts/)
- [Nginx 설정 가이드](https://nginx.org/en/docs/)
- [DuckDNS 문서](https://www.duckdns.org)
- [systemd 서비스 가이드](https://www.freedesktop.org/software/systemd/man/systemd.unit.html)
