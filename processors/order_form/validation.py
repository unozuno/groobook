"""발주 요청 검증·정규화.

오류(error) 가 하나라도 있으면 생성 불가, 경고(warning) 만 있으면 사용자 확인 후 생성.
코드와 path 는 브라우저 쪽 검증과 동일하게 유지한다.
"""
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from processors.order_form import naming
from processors.order_form.compute import distribution_totals, page_total
from processors.order_form.fields import FIELD_IDS
from processors.order_form.models import (
    DeliveryLine, DeliveryNote, DistributionRow, Item, Order, OrderRequest,
)
from processors.order_form.pricing import fill_unit_prices, quote

_INT_RE = re.compile(r"-?\d+(\.0+)?")
_ITEM_NUM_LABELS = {"qty": "발주수량", "mono": "1도", "insert": "청간지", "color": "4도",
                    "pages": "페이지", "unit_price": "단가"}


@dataclass
class Issue:
    level: str          # "error" | "warning"
    code: str
    path: str
    message: str

    def as_dict(self) -> dict:
        return {"level": self.level, "code": self.code, "path": self.path, "message": self.message}


@dataclass
class ValidationResult:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    def error(self, code, path, message):
        self.errors.append(Issue("error", code, path, message))

    def warn(self, code, path, message):
        self.warnings.append(Issue("warning", code, path, message))

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {"errors": [i.as_dict() for i in self.errors],
                "warnings": [i.as_dict() for i in self.warnings]}


# ───────────────────────── 파싱 헬퍼 ─────────────────────────

def parse_int(value) -> tuple[bool, Optional[int]]:
    """(유효 여부, 값). 빈 값은 (True, None). 음수·비숫자는 (False, None)."""
    if value is None:
        return True, None
    if isinstance(value, bool):
        return False, None
    if isinstance(value, (int, float)):
        if value != int(value) or value < 0:
            return False, None
        return True, int(value)
    s = str(value).strip().replace(",", "")
    if s == "":
        return True, None
    if not _INT_RE.fullmatch(s):
        return False, None
    n = int(float(s))
    if n < 0:
        return False, None
    return True, n


def parse_date(value: str) -> tuple[bool, Optional[date]]:
    s = (value or "").strip()
    if not s:
        return True, None
    try:
        return True, date.fromisoformat(s[:10])
    except ValueError:
        return False, None


def _blank(v) -> bool:
    return v is None or str(v).strip() == ""


# ───────────────────────── 메인 ─────────────────────────

def validate(req: OrderRequest, settings: dict) -> tuple[ValidationResult, Optional[Order]]:
    res = ValidationResult()
    mode = req.mode
    multi = req.order_type == "multi" and mode != "blank_delivery"
    types_by_id = {t["id"]: t for t in settings["types"]}
    address_by_name = {a["name"]: a for a in settings["address_book"]}

    # 종류
    type_id = None
    type_name = ""
    if mode == "order":
        if req.type_id in types_by_id:
            type_id = req.type_id
            type_name = types_by_id[type_id]["name"]
        else:
            res.error("TYPE_REQUIRED", "type_id", "제작 종류를 선택해 주세요.")
    elif mode == "blank_order":
        type_name = req.type_name.strip()

    # 날짜
    ok, received = parse_date(req.received_date)
    if not ok:
        res.error("DATE_INVALID", "received_date", "접수일자 형식이 올바르지 않습니다.")
    ok, due = parse_date(req.due_date)
    if not ok:
        res.error("DATE_INVALID", "due_date", "납기일자 형식이 올바르지 않습니다.")
    elif due is None:
        label = "납품일" if mode == "blank_delivery" else "납기일자"
        res.warn("DUE_DATE_MISSING", "due_date", f"{label}이 비어 있어 납품서의 납품일이 빈칸으로 출력됩니다.")

    # 작업번호
    if not req.job_no.strip():
        res.error("JOB_NO_REQUIRED", "job_no", "작업번호를 입력해 주세요.")

    # 납품학원 / 수령자
    campus = req.campus.strip()
    multi_name = req.multi_name.strip()
    if multi:
        campus = settings["multi_label"]
        if not multi_name:
            res.error("MULTI_NAME_REQUIRED", "multi_name", "다중 발주 파일명에 쓸 이름을 입력해 주세요.")
    elif mode == "blank_delivery":
        if not campus:
            res.error("RECEIVER_REQUIRED", "campus", "수령자를 입력해 주세요.")
    else:
        if not campus:
            res.error("CAMPUS_REQUIRED", "campus", "납품학원을 입력해 주세요.")

    price_rules = settings.get("price_rules", [])

    # 사양
    spec = {fid: (req.spec.get(fid) or "").strip() for fid in FIELD_IDS}

    # 전달사항
    messages = [m.strip() for m in req.messages if m and m.strip()]
    extra = (req.message_extra or "").strip()
    if extra:
        messages.append(extra)

    # 품목
    items: list[Item] = []
    kept_idx: list[int] = []
    bad_price: set[int] = set()   # 형식 오류가 난 단가 칸 (PRICE_REQUIRED 를 중복으로 내지 않음)
    for i, it in enumerate(req.items):
        fields_present = {k: not _blank(getattr(it, k)) for k in
                          ("name", "qty", "mono", "insert", "color", "pages", "unit_price")}
        if not any(fields_present.values()):
            continue
        kept_idx.append(i)
        if _blank(it.name):
            label = "제품명" if mode == "blank_delivery" else "교재명"
            res.error("ITEM_NAME_REQUIRED", f"items[{i}].name", f"{i + 1}번 품목의 {label}을 입력해 주세요.")
        nums = {}
        for key in ("qty", "mono", "insert", "color", "pages", "unit_price"):
            ok, val = parse_int(getattr(it, key))
            if not ok:
                if key == "unit_price":
                    bad_price.add(i)
                code = "PRICE_INVALID" if key == "unit_price" else "ITEM_NUM_INVALID"
                res.error(code, f"items[{i}].{key}",
                          f"{i + 1}번 품목의 {_ITEM_NUM_LABELS[key]}은(는) 0 이상의 정수여야 합니다.")
                val = None
            nums[key] = val
        if mode == "blank_delivery":
            pages = nums["pages"] or 0
        else:
            pages = page_total(nums["mono"], nums["insert"], nums["color"])
        items.append(Item(
            name=it.name.strip(), qty=nums["qty"], mono=nums["mono"], insert=nums["insert"],
            color=nums["color"], pages=pages, unit_price=nums["unit_price"],
        ))

    if not items:
        res.error("NO_ITEMS", "items", "품목을 1개 이상 입력해 주세요.")

    # 다중 분배표
    distribution: list[DistributionRow] = []
    if multi and items:
        seen: dict[str, int] = {}
        for j, row in enumerate(req.distribution):
            row_qtys_raw = [row.qtys[i] if i < len(row.qtys) else None for i in kept_idx]
            c = row.campus.strip()
            if not c and all(_blank(q) for q in row_qtys_raw):
                continue
            if not c:
                res.error("DIST_CAMPUS_EMPTY", f"distribution[{j}].campus",
                          f"분배표 {j + 1}행의 학원을 입력해 주세요.")
            elif c in seen:
                res.error("DIST_DUP_CAMPUS", f"distribution[{j}].campus",
                          f"분배표에 '{c}' 학원이 중복으로 들어 있습니다.")
            else:
                seen[c] = j
            qtys: list[Optional[int]] = []
            for k, (i, raw) in enumerate(zip(kept_idx, row_qtys_raw)):
                ok, val = parse_int(raw)
                if not ok:
                    res.error("DIST_NUM_INVALID", f"distribution[{j}].qtys[{i}]",
                              f"분배표 {j + 1}행 {k + 1}번 품목 수량은 0 이상의 정수여야 합니다.")
                    val = None
                qtys.append(val)
            distribution.append(DistributionRow(campus=c, qtys=qtys))

        if len([d for d in distribution if d.campus]) < 2:
            res.warn("DIST_TOO_FEW", "distribution",
                     "다중 발주인데 학원이 2곳 미만입니다. 단일 발주가 아닌지 확인해 주세요.")

        totals = distribution_totals([d.qtys for d in distribution], len(items))
        for it, total in zip(items, totals):
            it.qty = total

    # 품목 경고
    for i, it in zip(kept_idx, items):
        has_content = bool(it.name) or bool(it.qty)
        if mode != "blank_delivery" and has_content and it.pages == 0:
            res.warn("ITEM_PAGES_ZERO", f"items[{i}].pages",
                     f"{i + 1}번 품목의 페이지합계가 0 입니다.")
        others = any(v not in (None, 0, "") for v in (it.name, it.mono, it.insert, it.color, it.unit_price)) \
            or (mode == "blank_delivery" and it.pages)
        if not it.qty and others:
            res.warn("ITEM_QTY_EMPTY", f"items[{i}].qty",
                     f"{i + 1}번 품목의 발주수량이 비어 있거나 0 입니다.")
        if it.qty and it.unit_price is None and i not in bad_price:
            q = quote(mode, type_id, type_name, spec, it, price_rules, campus)
            if q.status == "manual":
                res.error("PRICE_REQUIRED", f"items[{i}].unit_price", f"{i + 1}번 품목: {q.reason}")

    # 납품서 구성
    deliveries: list[DeliveryNote] = []
    taken: set[str] = set()

    def lookup(name: str, path: str):
        entry = address_by_name.get(name)
        if entry is None:
            res.warn("ADDRESS_NOT_FOUND", path,
                     f"'{name}' 은(는) 주소록에 없어 납품서의 주소·담당자가 빈칸으로 출력됩니다.")
            return None, None
        return entry["address"], entry["contact"]

    if multi:
        for j, d in enumerate(distribution):
            if not d.campus:
                continue
            lines = [DeliveryLine(item=it, qty=q) for it, q in zip(items, d.qtys) if q]
            if not lines:
                res.warn("DIST_CAMPUS_ZERO", f"distribution[{j}]",
                         f"'{d.campus}' 의 분배 수량이 모두 0 이라 납품서를 만들지 않습니다.")
                continue
            sheet, adjusted = naming.delivery_sheet_name(d.campus, taken, multi=True)
            taken.add(sheet)
            if adjusted:
                res.warn("SHEET_NAME_ADJUSTED", f"distribution[{j}].campus",
                         f"'{d.campus}' 납품서 시트명이 엑셀 규칙에 맞게 '{sheet}' 로 조정되었습니다.")
            addr, contact = lookup(d.campus, f"distribution[{j}].campus")
            deliveries.append(DeliveryNote(d.campus, sheet, lines, addr, contact))
    elif campus and items:
        lines = [DeliveryLine(item=it, qty=it.qty) for it in items]
        sheet, _ = naming.delivery_sheet_name(campus, taken, multi=False)
        addr, contact = lookup(campus, "campus")
        deliveries.append(DeliveryNote(campus, sheet, lines, addr, contact))

    if not res.ok:
        return res, None

    order = Order(
        mode=mode, order_type="multi" if multi else "single", type_id=type_id, type_name=type_name,
        received_date=received, due_date=due, campus=campus, multi_name=multi_name,
        job_no=req.job_no.strip(), spec=spec, messages=messages, items=items,
        distribution=distribution, deliveries=deliveries,
    )
    for note in order.deliveries:
        note.unit_prices = fill_unit_prices(mode, type_id, type_name, spec, note.lines, price_rules, note.campus)
    return res, order
