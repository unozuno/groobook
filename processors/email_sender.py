import os
import re
import smtplib
from collections import defaultdict
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

from dotenv import load_dotenv

from processors.order_form import settings_store
from processors.order_form.desktop_paths import norm_name

load_dotenv()

FILENAME_PATTERN = re.compile(
    r'(\d{4})년\s+(\d{1,2})월\s+(.+?)\s+청구서_(내신교재|소모품(?:\(일반\)|\(교재\))?)(?:\.xlsx?m?)?'
)


def load_campus_emails() -> dict:
    """공통설정 주소록의 이메일을 {정규화한 학원명: 메일} 로 돌려준다 (이메일이 빈 학원은 제외)."""
    book = settings_store.load_settings()["address_book"]
    return {norm_name(a["name"]): a["email"] for a in book if a.get("email")}


def parse_filename(filename: str):
    """파일명에서 (year, month, campus, file_type) 추출. 실패 시 None."""
    match = FILENAME_PATTERN.search(filename)
    if not match:
        return None
    year = match.group(1)
    month = match.group(2).zfill(2)
    campus = match.group(3).strip()
    file_type = match.group(4)
    return year, month, campus, file_type


def scan_files(files: list[dict]) -> dict:
    """
    files: [{"filename": str, "bytes": bytes}, ...]
    반환: {
        "groups": {(year,month,campus): [file_info, ...]},
        "campus_emails": {campus: email},
        "preview": [{"year","month","campus","file_type","email"}, ...]
    }
    """
    campus_emails = load_campus_emails()
    groups = defaultdict(list)
    preview = []

    for f in files:
        parsed = parse_filename(f["filename"])
        if not parsed:
            continue
        year, month, campus, file_type = parsed
        email = campus_emails.get(norm_name(campus), "이메일 없음")
        key = (year, month, campus)
        groups[key].append({
            "filename": f["filename"],
            "bytes": f["bytes"],
            "file_type": file_type,
            "email": email,
        })
        preview.append({
            "year": year,
            "month": month,
            "campus": campus,
            "file_type": file_type,
            "email": email,
        })

    # preview 정렬: 년도 → 월 → 캠퍼스
    preview.sort(key=lambda x: (x["year"], x["month"], x["campus"]))

    return {
        "groups": dict(groups),
        "campus_emails": campus_emails,
        "preview": preview,
    }


def _create_email_body(year: str, month: str, campus: str, additional_msg: str) -> str:
    body = f"""안녕하세요.
그루북 정세동 실장입니다.

{year}년 {month}월 청구서를 보내드리니 확인 바랍니다.
보시고 수정 사항이 있을 경우, 알려주시면 반영하도록 하겠습니다.
"""
    if additional_msg.strip():
        body += f"\n{additional_msg.strip()}\n"

    body += """
감사합니다.

그루북 정세동 드림"""
    return body


def send_billing_emails(
    groups: dict,
    additional_msg: str,
    progress_cb=None,
) -> dict:
    """
    groups: {(year,month,campus): [file_info, ...]}
    반환: {"success": int, "fail": int, "errors": [str]}
    """
    def cb(pct, msg):
        if progress_cb:
            progress_cb(pct, msg)

    gmail_address = os.getenv("GMAIL_ADDRESS", "").strip()
    gmail_password = os.getenv("GMAIL_APP_PASSWORD", "").strip()

    if not gmail_address or not gmail_password:
        raise ValueError(".env 파일에 GMAIL_ADDRESS, GMAIL_APP_PASSWORD가 설정되지 않았습니다.")

    cb(10, "메일 서버 연결 중...")
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(gmail_address, gmail_password)

    total = len(groups)
    success = 0
    fail = 0
    errors = []

    for idx, ((year, month, campus), files) in enumerate(groups.items(), start=1):
        pct = 10 + int((idx / total) * 85)
        cb(pct, f"발송 중... ({idx}/{total}) — {campus}")

        recipient = files[0]["email"]
        if recipient == "이메일 없음":
            fail += 1
            errors.append(f"{campus}: 등록된 이메일 없음")
            continue

        try:
            msg = MIMEMultipart()
            msg["From"] = gmail_address
            msg["To"] = recipient
            msg["Subject"] = f"그루북 {year}년 {month}월 청구서_{campus}"

            body = _create_email_body(year, month, campus, additional_msg)
            msg.attach(MIMEText(body, "plain", "utf-8"))

            for file_info in files:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(file_info["bytes"])
                encoders.encode_base64(part)
                encoded_filename = quote(file_info['filename'], safe='')
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename*=UTF-8''{encoded_filename}",
                )
                msg.attach(part)

            server.send_message(msg)
            success += 1
        except Exception as e:
            fail += 1
            errors.append(f"{campus}: {str(e)}")

    server.quit()
    cb(100, f"완료! 성공 {success}건, 실패 {fail}건")
    return {"success": success, "fail": fail, "errors": errors}
