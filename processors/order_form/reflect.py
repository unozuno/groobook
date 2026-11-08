"""생성한 납품서를 바탕화면의 두 엑셀 파일에 반영한다.

1. 청구서   : {연}년 {월}월 매출청구서_소모품/{연}년 {월}월 {학원} 청구서_소모품.xlsx 의 맨 끝에 납품서 시트를 추가하고,
              1번 시트 '견적서' 에 그 시트를 가리키는 품목 줄 한 줄을 추가(빈 줄이 없으면 줄 삽입)
2. 마케팅팀 : {연}년 {월}월 소모품 제작내역_Marketing팀.xlsx 의 '소모품출고내역' 에서 학원 구역 아래 빈 행에 품목 입력

- 연·월·시트명 MMDD 는 모두 납품서의 납품일(발주서 납기일자) 기준이다.
- dry_run=True 이면 파일을 전혀 바꾸지 않고 "무엇을 할지"만 돌려준다 (잠금 여부도 확인).
- 파일이나 학원 구역이 없으면 새로 만들지 않고 건너뛴다. 같은 시트·같은 행이 이미 있으면 건너뛴다.
- 수정은 workbook_io.safe_save 를 통해서만 한다 (백업, 검증, 원본 보호).
"""
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from openpyxl.utils import get_column_letter as L

from processors.order_form import calc_cache as cc
from processors.order_form import desktop_paths as dp
from processors.order_form import estimate_sheet as es
from processors.order_form import workbook_io as wio
from processors.order_form.models import DeliveryNote, Order
from processors.order_form.naming import SHEET_NAME_MAX, sanitize_sheet_name
from processors.order_form.xlsx_builder import delivery_total_row, write_delivery_sheet

INVOICE = "invoice"
MARKETING = "marketing"
MARKETING_SHEET = "소모품출고내역"
BLOCK_HEADERS = ["일자", "제품명", "부수", "페이지", "단가", "금액"]
MARKETING_DATA_FIRST_ROW = 4
CARD_SHEET_LABEL = "명함"


@dataclass
class ReflectItem:
    target: str          # "invoice" | "marketing"
    campus: str
    status: str          # "ok"(예정) | "done" | "skip" | "error"
    message: str
    file: str = ""
    detail: str = ""     # 새 시트명 또는 입력 행 범위
    backup: str = ""

    def as_dict(self) -> dict:
        return {"target": self.target, "campus": self.campus, "status": self.status,
                "message": self.message, "file": self.file, "detail": self.detail, "backup": self.backup}


@dataclass
class ReflectResult:
    items: list[ReflectItem] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"items": [i.as_dict() for i in self.items]}


def _compact(name: str) -> str:
    return re.sub(r"\s+", "", name or "")


def invoice_sheet_name(order: Order, note: DeliveryNote, due: date) -> str:
    """납품일 MMDD + 납품서 첫 제품명(공백 모두 제거). 제작 종류가 명함이면 'MMDD명함'."""
    base = CARD_SHEET_LABEL if order.type_name == CARD_SHEET_LABEL else _compact(note.lines[0].item.name)
    return sanitize_sheet_name(f"{due.strftime('%m%d')}{base}")[:SHEET_NAME_MAX]


# ───────── 청구서 ─────────

def _reflect_invoice(order: Order, desktop: Path, due: date, dry_run: bool, out: ReflectResult) -> None:
    for note in order.deliveries:
        found = dp.find_invoice_file(desktop, due, note.campus)
        if found.path is None:
            out.items.append(ReflectItem(INVOICE, note.campus, "skip",
                                         "청구서 파일을 찾지 못해 건너뜁니다.", str(found.expected)))
            continue
        path = found.path
        sheet = invoice_sheet_name(order, note, due)
        try:
            wio.check_writable(path)
            wb = wio.open_workbook(path)
        except wio.WorkbookIOError as e:
            out.items.append(ReflectItem(INVOICE, note.campus, "error", str(e), str(path)))
            continue
        try:
            existing = {dp.norm_name(t).lower() for t in wb.sheetnames}
            if dp.norm_name(sheet).lower() in existing:
                out.items.append(ReflectItem(INVOICE, note.campus, "skip",
                                             f"같은 이름의 시트 '{sheet}' 이(가) 이미 있어 건너뜁니다.",
                                             str(path), sheet))
                continue
            # 시트와 견적서가 어긋나지 않도록 견적서 틀부터 확인한다 (못 찾으면 아무것도 바꾸지 않음)
            try:
                if es.ESTIMATE_SHEET not in wb.sheetnames:
                    raise es.EstimateError(f"'{es.ESTIMATE_SHEET}' 시트를 찾지 못했습니다.")
                est = wb[es.ESTIMATE_SHEET]
                layout = es.find_layout(est)
            except es.EstimateError as e:
                out.items.append(ReflectItem(INVOICE, note.campus, "error",
                                             f"견적서 구조를 확인하지 못해 반영하지 않았습니다. ({e})",
                                             str(path), sheet))
                continue
            free = es.find_free_row(est, layout)
            row = free if free is not None else layout.separator
            how = "한 줄을 추가" if free is not None else "줄을 삽입해 한 줄을 추가"
            if dry_run:
                out.items.append(ReflectItem(INVOICE, note.campus, "ok",
                                             f"맨 끝에 '{sheet}' 시트를 추가하고, 견적서 {row}행에 {how}합니다.",
                                             str(path), sheet))
                continue

            snap = wio.snapshot(wb)
            orig_cache = wio.load_cached_numbers(path)
            ws = wb.create_sheet(sheet)
            write_delivery_sheet(ws, order, note)
            expected = None
            if free is None:
                row = es.insert_item_row(est, layout)
                layout = es.find_layout(est)
                expected = {es.ESTIMATE_SHEET: es.expected_after_insert(row, es.row_merges(est, row))}
            total_row = delivery_total_row(len(note.lines))
            es.write_item_row(est, layout, row, note.lines[0].item.name, sheet, total_row, due.month, due.day)
            # 엑셀 밖(미리보기 등)에서도 0 이 아닌 값이 보이도록 모든 수식의 계산값을 함께 기록한다
            cached = cc.compute_cached(wb, orig_cache, snap, volatile=(es.ESTIMATE_SHEET,))
            try:
                backup = wio.safe_save(wb, path, snap, allowed={es.ESTIMATE_SHEET: es.row_coords(layout, row)},
                                       new_sheets=[sheet], expected=expected, cached=cached)
            except wio.WorkbookIOError as e:
                out.items.append(ReflectItem(INVOICE, note.campus, "error", str(e), str(path), sheet))
                continue
            out.items.append(ReflectItem(INVOICE, note.campus, "done",
                                         f"맨 끝에 '{sheet}' 시트를 추가하고, 견적서 {row}행에 {how}했습니다.",
                                         str(path), sheet, str(backup)))
        finally:
            wb.close()


# ───────── 마케팅팀 ─────────

def _find_block(ws, campus: str) -> Optional[int]:
    target = dp.norm_name(campus)
    for c in range(1, ws.max_column + 1):
        v = ws.cell(2, c).value
        if isinstance(v, str) and dp.norm_name(v) == target:
            return c
    return None


def _blank(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip() == "")


def _as_date(v) -> Optional[date]:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    return None


def _marketing_plan(ws, note: DeliveryNote, due: date) -> tuple[str, str, Optional[int], Optional[int], int]:
    """(status, message, 시작 열, 시작 행, 필요한 행 수). status: ok | skip | error"""
    need = len(note.lines)
    c0 = _find_block(ws, note.campus)
    if c0 is None:
        return "skip", f"마케팅팀 파일에 '{note.campus}' 구역이 없어 건너뜁니다.", None, None, need
    headers = [str(ws.cell(3, c0 + k).value or "").strip() for k in range(6)]
    if headers != BLOCK_HEADERS:
        return "error", f"'{note.campus}' 구역의 머리글({', '.join(headers)})이 예상과 달라 입력하지 않습니다.", None, None, need
    total_row = None
    for r in range(MARKETING_DATA_FIRST_ROW, ws.max_row + 1):
        if str(ws.cell(r, c0).value or "").strip() == "합계":
            total_row = r
            break
    if total_row is None:
        return "error", f"'{note.campus}' 구역의 합계 행을 찾지 못해 입력하지 않습니다.", None, None, need
    last_data = total_row - 1

    used = []
    for r in range(MARKETING_DATA_FIRST_ROW, last_data + 1):
        if any(not _blank(ws.cell(r, c0 + k).value) for k in range(6)):
            used.append(r)
    for r in used:
        row_date = _as_date(ws.cell(r, c0).value)
        row_name = dp.norm_name(str(ws.cell(r, c0 + 1).value or ""))
        row_qty = ws.cell(r, c0 + 2).value
        for line in note.lines:
            if row_date == due and row_name == dp.norm_name(line.item.name) and row_qty == line.qty:
                return "skip", f"같은 일자·제품명·부수('{line.item.name}')가 이미 입력되어 있어 건너뜁니다.", None, None, need
    start = (max(used) + 1) if used else MARKETING_DATA_FIRST_ROW
    if start + need - 1 > last_data:
        free = max(0, last_data - start + 1)
        return "error", f"'{note.campus}' 구역에 빈 행이 부족합니다 (필요 {need}행, 남은 {free}행).", None, None, need
    return "ok", "", c0, start, need


def _write_marketing_rows(ws, note: DeliveryNote, due: date, c0: int, start: int) -> set[str]:
    written: set[str] = set()
    when = datetime(due.year, due.month, due.day)
    for i, line in enumerate(note.lines):
        r = start + i
        price = note.unit_prices[i] if i < len(note.unit_prices) else None
        pages = line.item.pages or None
        values = [when, line.item.name, line.qty, pages, price]
        for k, v in enumerate(values):
            cell = ws.cell(r, c0 + k)
            cell.value = v
            written.add(cell.coordinate)
        date_cell = ws.cell(r, c0)
        if date_cell.number_format == "General":
            date_cell.number_format = 'mm"월"\\ dd"일"'
        amount = ws.cell(r, c0 + 5)
        qty_col, price_col = L(c0 + 2), L(c0 + 4)
        amount.value = f"={qty_col}{r}*{price_col}{r}" if (price is not None and line.qty) else None
        written.add(amount.coordinate)
    return written


def _reflect_marketing(order: Order, desktop: Path, due: date, dry_run: bool, out: ReflectResult) -> None:
    found = dp.find_marketing_file(desktop, due)
    if found.path is None:
        for note in order.deliveries:
            out.items.append(ReflectItem(MARKETING, note.campus, "skip",
                                         "마케팅팀 제작내역 파일을 찾지 못해 건너뜁니다.", str(found.expected)))
        return
    path = found.path
    try:
        wio.check_writable(path)
        wb = wio.open_workbook(path)
    except wio.WorkbookIOError as e:
        for note in order.deliveries:
            out.items.append(ReflectItem(MARKETING, note.campus, "error", str(e), str(path)))
        return
    try:
        if MARKETING_SHEET not in wb.sheetnames:
            for note in order.deliveries:
                out.items.append(ReflectItem(MARKETING, note.campus, "error",
                                             f"'{MARKETING_SHEET}' 시트를 찾지 못했습니다.", str(path)))
            return
        ws = wb[MARKETING_SHEET]
        snap = wio.snapshot(wb)
        orig_cache = wio.load_cached_numbers(path)
        allowed: set[str] = set()
        pending: list[ReflectItem] = []
        for note in order.deliveries:
            status, msg, c0, start, need = _marketing_plan(ws, note, due)
            if status != "ok":
                out.items.append(ReflectItem(MARKETING, note.campus, status, msg, str(path)))
                continue
            span = f"{start}~{start + need - 1}행" if need > 1 else f"{start}행"
            if dry_run:
                out.items.append(ReflectItem(MARKETING, note.campus, "ok",
                                             f"'{note.campus}' 구역 {span}에 {need}건을 입력합니다.", str(path), span))
                continue
            allowed |= _write_marketing_rows(ws, note, due, c0, start)
            item = ReflectItem(MARKETING, note.campus, "done",
                               f"'{note.campus}' 구역 {span}에 {need}건을 입력했습니다.", str(path), span)
            out.items.append(item)
            pending.append(item)
        if pending:
            try:
                cached = cc.compute_cached(wb, orig_cache, snap, volatile=(MARKETING_SHEET,))
                backup = wio.safe_save(wb, path, snap, allowed={MARKETING_SHEET: allowed}, cached=cached)
            except wio.WorkbookIOError as e:
                for item in pending:
                    item.status, item.message = "error", str(e)
            else:
                for item in pending:
                    item.backup = str(backup)
    finally:
        wb.close()


# ───────── 진입점 ─────────

def reflect(order: Order, targets: dict, desktop_dir: str = "", dry_run: bool = True) -> ReflectResult:
    out = ReflectResult()
    wanted = [t for t in (INVOICE, MARKETING) if targets.get(t)]
    if not wanted:
        return out

    def fail_all(message: str, file: str = "") -> ReflectResult:
        for t in wanted:
            for note in order.deliveries:
                out.items.append(ReflectItem(t, note.campus, "error", message, file))
        return out

    due = order.due_date
    if due is None:
        return fail_all("납품일(납기일자)이 비어 있어 반영할 파일을 정할 수 없습니다.")
    info = dp.resolve_desktop(desktop_dir)
    if not info.exists:
        return fail_all("바탕화면 폴더를 찾을 수 없습니다. 이 기능은 파일이 있는 PC에서 서버를 실행할 때만 쓸 수 있습니다. "
                        "경로는 공통설정에서 지정할 수 있습니다.", str(info.path))
    if INVOICE in wanted:
        _reflect_invoice(order, info.path, due, dry_run, out)
    if MARKETING in wanted:
        _reflect_marketing(order, info.path, due, dry_run, out)
    return out
