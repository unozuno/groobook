"""공통발주서 생성 흐름: 검증 → 엑셀 생성 → 수식 검증 → 원본 보관."""
from processors.order_form.archive import archive_order
from processors.order_form.models import OrderRequest
from processors.order_form.naming import build_filename
from processors.order_form.validation import Issue, ValidationResult, validate
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
