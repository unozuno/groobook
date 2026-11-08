"""공통발주서 생성 흐름: 검증 → 엑셀 생성 → 수식 검증 → 원본 보관."""
from processors.order_form.archive import archive_order
from processors.order_form.compute import page_total
from processors.order_form.fields import FIELD_IDS
from processors.order_form.models import Item, OrderRequest
from processors.order_form.naming import build_filename
from processors.order_form.pricing import quote
from processors.order_form.reflect import ReflectResult, reflect
from processors.order_form.validation import Issue, ValidationResult, parse_int, validate
from processors.order_form.verify import verify_workbook
from processors.order_form.xlsx_builder import build_workbook


class OrderValidationError(Exception):
    def __init__(self, result: ValidationResult):
        super().__init__("입력 오류")
        self.result = result


class OrderWarningsPending(Exception):
    """경고가 있고 force 가 아니어서 사용자 확인이 필요함."""

    def __init__(self, result: ValidationResult):
        super().__init__("경고 확인 필요")
        self.result = result


def generate(req: OrderRequest, force: bool, settings: dict) -> tuple[bytes, str, list[Issue]]:
    result, order = validate(req, settings)
    if not result.ok or order is None:
        raise OrderValidationError(result)
    if result.warnings and not force:
        raise OrderWarningsPending(result)

    xlsx = build_workbook(order)
    verify_workbook(xlsx, order)
    filename = build_filename(order)
    archive_order(req, filename, result.warnings)
    return xlsx, filename, result.warnings


def reflect_order(req: OrderRequest, targets: dict, dry_run: bool, settings: dict) -> ReflectResult:
    """입력을 검증한 뒤 청구서·마케팅팀 파일 반영 계획(dry_run) 또는 실행 결과를 돌려준다.
    경고(주소록 없음 등)는 반영을 막지 않는다."""
    result, order = validate(req, settings)
    if not result.ok or order is None:
        raise OrderValidationError(result)
    return reflect(order, targets, settings.get("desktop_dir", ""), dry_run)


def quote_items(req: OrderRequest, settings: dict) -> list[dict | None]:
    """화면에 보여 줄 자동 단가. 입력 중에도 호출되므로 검증 오류와 무관하게 가능한 만큼만 계산한다.
    req.items 와 같은 길이이며, 완전히 빈 행은 None."""
    types = {t["id"]: t["name"] for t in settings["types"]}
    type_id = req.type_id if req.mode == "order" and req.type_id in types else None
    type_name = types.get(type_id, req.type_name.strip())
    spec = {fid: (req.spec.get(fid) or "").strip() for fid in FIELD_IDS}
    rules = settings.get("price_rules", [])
    multi = req.order_type == "multi" and req.mode != "blank_delivery"

    out: list[dict | None] = []
    for i, it in enumerate(req.items):
        nums = {k: parse_int(getattr(it, k))[1] for k in ("qty", "mono", "insert", "color", "pages")}
        if not any(v for v in nums.values()) and not (it.name or "").strip():
            out.append(None)
            continue
        if multi:
            qty = sum(parse_int(row.qtys[i])[1] or 0 for row in req.distribution if i < len(row.qtys))
        else:
            qty = nums["qty"]
        pages = (nums["pages"] or 0) if req.mode == "blank_delivery" \
            else page_total(nums["mono"], nums["insert"], nums["color"])
        item = Item(name=it.name.strip(), qty=qty, mono=nums["mono"], insert=nums["insert"],
                    color=nums["color"], pages=pages)
        q = quote(req.mode, type_id, type_name, spec, item, rules)
        out.append({"status": q.status, "price": q.price, "reason": q.reason})
    return out
