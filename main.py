import json
import threading
import uuid
from io import BytesIO

from urllib.parse import quote
from fastapi import Body, FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from typing import List
from dotenv import load_dotenv

from processors.naeshin import process_naeshin
from processors.quarterly import process_quarterly
from processors.midterm import process_midterm
from processors.jundeung_bill import process_jundeung_bill
from processors.email_sender import scan_files, send_billing_emails
from processors.order_form import settings_store
from processors.order_form.clock import today_seoul
from processors.order_form.fields import (
    FIELD_GROUPS, GROUP_ORDER, ITEM_DEFAULT_KEYS, ITEM_DEFAULT_LABELS, field_meta,
)
from processors.order_form.desktop_paths import resolve_desktop
from processors.order_form.models import GenerateRequest, ReflectRequest
from processors.order_form.naming import yymmdd
from processors.order_form.service import (
    OrderValidationError, OrderWarningsPending, generate, reflect_order,
)
from processors.order_form.settings_models import SettingsValidationError
from processors.order_form.verify import OrderVerifyError
from renderer.pdf_renderer import render_pdf

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 인메모리 작업 저장소
tasks: dict[str, dict] = {}

# 이메일 스캔 임시 저장소
email_scans: dict[str, dict] = {}

# ──────────────── 페이지 라우트 ────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/packaging", response_class=HTMLResponse)
async def packaging(request: Request):
    return templates.TemplateResponse(request=request, name="packaging.html")


@app.get("/naeshin", response_class=HTMLResponse)
async def naeshin_page(request: Request):
    return templates.TemplateResponse(request=request, name="work.html", context={
        "title": "내신노트",
        "type": "naeshin",
        "show_banding": False,
    })


@app.get("/quarterly", response_class=HTMLResponse)
async def quarterly_page(request: Request):
    return templates.TemplateResponse(request=request, name="work.html", context={
        "title": "분기별교재",
        "type": "quarterly",
        "show_banding": False,
    })


@app.get("/midterm", response_class=HTMLResponse)
async def midterm_page(request: Request):
    return templates.TemplateResponse(request=request, name="work.html", context={
        "title": "중간기말교재",
        "type": "midterm",
        "show_banding": True,
    })


@app.get("/jundeung-bill", response_class=HTMLResponse)
async def jundeung_bill_page(request: Request):
    return templates.TemplateResponse(request=request, name="jundeung_bill.html")


@app.get("/email", response_class=HTMLResponse)
async def email_page(request: Request):
    return templates.TemplateResponse(request=request, name="email.html")


@app.get("/order-form", response_class=HTMLResponse)
async def order_form_page(request: Request):
    return templates.TemplateResponse(request=request, name="order_form.html")


@app.get("/order-settings", response_class=HTMLResponse)
async def order_settings_page(request: Request):
    return templates.TemplateResponse(request=request, name="order_settings.html")


# ──────────────── 포장전표 API ────────────────

@app.post("/api/process/{proc_type}")
async def process(
    proc_type: str,
    file: UploadFile = File(...),
    main_banding: int = Form(20),
    mini_banding: int = Form(70),
    teacher_banding: int = Form(15),
):
    if proc_type == "jundeung_bill":
        file_bytes = await file.read()
        task_id = str(uuid.uuid4())
        original_name = file.filename.rsplit('.', 1)[0]
        tasks[task_id] = {
            "status": "processing",
            "progress": 0,
            "message": "준비 중...",
            "result_bytes": None,
            "filename": f"{original_name}_{task_id[:8]}.xlsx",
            "error": None,
            "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }

        def run_bill():
            def progress_cb(pct, msg):
                tasks[task_id]["progress"] = pct
                tasks[task_id]["message"] = msg
            try:
                xlsx_bytes = process_jundeung_bill(file_bytes, progress_cb)
                tasks[task_id]["result_bytes"] = xlsx_bytes
                tasks[task_id]["status"] = "done"
            except Exception as e:
                tasks[task_id]["status"] = "error"
                tasks[task_id]["error"] = str(e)

        threading.Thread(target=run_bill, daemon=True).start()
        return JSONResponse({"task_id": task_id})

    if proc_type not in ("naeshin", "quarterly", "midterm"):
        raise HTTPException(status_code=400, detail="알 수 없는 작업 유형입니다.")

    file_bytes = await file.read()
    task_id = str(uuid.uuid4())
    original_name = file.filename.rsplit('.', 1)[0]
    tasks[task_id] = {
        "status": "processing",
        "progress": 0,
        "message": "준비 중...",
        "result_bytes": None,
        "filename": f"{original_name}_{task_id[:8]}.pdf",
        "error": None,
    }

    def run():
        def progress_cb(pct, msg):
            tasks[task_id]["progress"] = pct
            tasks[task_id]["message"] = msg

        try:
            if proc_type == "naeshin":
                slip_list = process_naeshin(file_bytes, progress_cb)
            elif proc_type == "quarterly":
                slip_list = process_quarterly(file_bytes, progress_cb)
            else:
                slip_list, excel_bytes = process_midterm(
                    file_bytes, main_banding, mini_banding, teacher_banding, progress_cb
                )
                tasks[task_id]["result_bytes_excel"] = excel_bytes
                tasks[task_id]["filename_excel"] = f"{original_name}_배본표_{task_id[:8]}.xlsx"

            pdf_bytes = render_pdf(slip_list, progress_cb, proc_type=proc_type)
            tasks[task_id]["result_bytes"] = pdf_bytes
            tasks[task_id]["status"] = "done"
        except Exception as e:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["error"] = str(e)

    threading.Thread(target=run, daemon=True).start()
    return JSONResponse({"task_id": task_id})


@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    task = tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return JSONResponse({
        "status": task["status"],
        "progress": task["progress"],
        "message": task["message"],
        "error": task.get("error"),
        "email_result": task.get("email_result"),
    })


@app.get("/api/download/{task_id}")
async def download(task_id: str):
    task = tasks.get(task_id)
    if not task or task["status"] != "done":
        raise HTTPException(status_code=404, detail="완성된 파일이 없습니다.")
    file_bytes = task["result_bytes"]
    filename = task["filename"]
    content_type = task.get("content_type", "application/pdf")
    # 엑셀이 없거나 이미 엑셀도 다운로드됐으면 태스크 삭제
    if not task.get("result_bytes_excel") or task.get("excel_downloaded"):
        tasks.pop(task_id, None)
    else:
        task["pdf_downloaded"] = True
    return Response(
        content=file_bytes,
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@app.get("/api/download/{task_id}/excel")
async def download_excel(task_id: str):
    task = tasks.get(task_id)
    if not task or task["status"] != "done" or not task.get("result_bytes_excel"):
        raise HTTPException(status_code=404, detail="배본표 엑셀 파일이 없습니다.")
    file_bytes = task["result_bytes_excel"]
    filename = task["filename_excel"]
    # PDF도 다운로드됐으면 태스크 삭제
    if task.get("pdf_downloaded"):
        tasks.pop(task_id, None)
    else:
        task["excel_downloaded"] = True
    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


# ──────────────── 이메일 API ────────────────

@app.post("/api/email/scan")
async def email_scan(files: List[UploadFile] = File(...)):
    """파일 업로드 → 파일명 파싱 → 스캔 결과 반환"""
    file_list = []
    for f in files:
        content = await f.read()
        file_list.append({"filename": f.filename, "bytes": content})

    result = scan_files(file_list)

    if not result["groups"]:
        raise HTTPException(status_code=400, detail="패턴에 맞는 청구서 파일이 없습니다.\n파일명 형식: YYYY년 MM월 캠퍼스명 청구서_내신교재.xlsx")

    scan_id = str(uuid.uuid4())
    email_scans[scan_id] = result

    return JSONResponse({
        "scan_id": scan_id,
        "preview": result["preview"],
        "total_groups": len(result["groups"]),
    })


@app.post("/api/email/send")
async def email_send(
    scan_id: str = Form(...),
    additional_msg: str = Form(""),
):
    """스캔된 파일 그룹으로 이메일 발송 시작"""
    scan = email_scans.get(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="스캔 결과를 찾을 수 없습니다. 다시 스캔해주세요.")

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        "status": "processing",
        "progress": 0,
        "message": "준비 중...",
        "result_bytes": None,
        "filename": "",
        "error": None,
        "email_result": None,
    }

    groups = scan["groups"]

    def run():
        def progress_cb(pct, msg):
            tasks[task_id]["progress"] = pct
            tasks[task_id]["message"] = msg

        try:
            result = send_billing_emails(groups, additional_msg, progress_cb)
            tasks[task_id]["status"] = "done"
            tasks[task_id]["email_result"] = result
            email_scans.pop(scan_id, None)
        except Exception as e:
            tasks[task_id]["status"] = "error"
            tasks[task_id]["error"] = str(e)

    threading.Thread(target=run, daemon=True).start()
    return JSONResponse({"task_id": task_id})


# ──────────────── 공통발주서 ────────────────

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _attachment(filename: str) -> dict:
    return {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}


def _settings_meta() -> dict:
    return {
        "fields": field_meta(),
        "groups": [{"name": g, "fields": FIELD_GROUPS[g]} for g in GROUP_ORDER],
        "item_default_keys": list(ITEM_DEFAULT_KEYS),
        "item_default_labels": ITEM_DEFAULT_LABELS,
        "today": today_seoul().isoformat(),
    }


@app.get("/api/order-settings")
async def order_settings_get():
    return JSONResponse({"settings": settings_store.load_settings(), "meta": _settings_meta()})


@app.put("/api/order-settings")
async def order_settings_put(payload: dict = Body(...)):
    """{"settings": {...}, "expected_updated_at": "..."}  (저장·가져오기 공용)"""
    data = payload.get("settings")
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="settings 객체가 필요합니다.")
    try:
        saved = settings_store.save_settings(data, payload.get("expected_updated_at"))
    except settings_store.SettingsConflictError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except SettingsValidationError as e:
        return JSONResponse(status_code=422, content={"detail": "설정 검증 실패", "errors": e.errors})
    return JSONResponse({"settings": saved})


@app.get("/api/order-settings/export")
async def order_settings_export():
    data = settings_store.load_settings()
    body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(content=body, media_type="application/json",
                    headers=_attachment(f"order_settings_{yymmdd()}.json"))


@app.post("/api/order-settings/reset")
async def order_settings_reset():
    return JSONResponse({"settings": settings_store.reset_settings()})


@app.post("/api/order-form/generate")
async def order_form_generate(req: GenerateRequest):
    settings = settings_store.load_settings()
    try:
        xlsx, filename, warnings = generate(req.order, req.force, settings)
    except OrderValidationError as e:
        return JSONResponse(status_code=422, content={"detail": "입력 오류", **e.result.as_dict()})
    except OrderWarningsPending as e:
        return JSONResponse(status_code=409, content={"detail": "확인이 필요한 경고가 있습니다.",
                                                      "warnings": e.result.as_dict()["warnings"]})
    except OrderVerifyError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return Response(content=xlsx, media_type=XLSX_MEDIA_TYPE, headers=_attachment(filename))


@app.get("/api/order-form/desktop-info")
async def order_form_desktop_info():
    settings = settings_store.load_settings()
    return JSONResponse(resolve_desktop(settings.get("desktop_dir", "")).as_dict())


@app.post("/api/order-form/reflect")
async def order_form_reflect(req: ReflectRequest):
    settings = settings_store.load_settings()
    try:
        result = reflect_order(req.order, req.targets, req.dry_run, settings)
    except OrderValidationError as e:
        return JSONResponse(status_code=422, content={"detail": "입력 오류", **e.result.as_dict()})
    return JSONResponse(result.as_dict())
