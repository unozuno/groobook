"""납품서 단가 결정.

설정의 단가표(price_rules)에서 제작 종류·사양·페이지합계·총 발주수량이 모두 맞는
첫 규칙을 찾아 단가를 계산한다. 규칙이 없거나 규칙의 price 가 비어 있으면 직접 입력이다.
사용자가 단가를 직접 넣은 품목은 그 값을 우선한다 (자동 단가는 수정 가능해야 함).
"""
from dataclasses import dataclass
from typing import Optional

from processors.order_form.models import DeliveryLine, Item
from processors.order_form.pricing_models import DELIVERY_TYPE_ID


@dataclass
class PriceQuote:
    status: str                     # "auto" | "manual"
    price: Optional[int] = None
    rule_id: Optional[str] = None
    reason: str = ""                # manual 일 때 사용자에게 보여 줄 이유


def _norm(value: str) -> str:
    """공백을 모두 제거해 비교한다 ('200 스노우' == '200스노우')."""
    return "".join((value or "").split())


def _matches(rule: dict, spec: dict[str, str], item: Item) -> bool:
    for field, allowed in rule["when"].items():
        if _norm(spec.get(field, "")) not in {_norm(a) for a in allowed}:
            return False
    qty = item.qty or 0
    if rule["qty_min"] is not None and qty < rule["qty_min"]:
        return False
    if rule["qty_max"] is not None and qty > rule["qty_max"]:
        return False
    if rule["pages"] is not None and item.pages != rule["pages"]:
        return False
    return True


def _compute(price: dict, item: Item) -> int:
    if price["kind"] == "fixed":
        return price["amount"]
    return item.pages * price["rate"] + (price["base"] or 0)


def _quote_delivery(item: Item, campus: str, rules: list[dict]) -> PriceQuote:
    """납품서 모드: 제품명이 같고 납품학원이 맞는 첫 규칙 (납품학원이 비어 있는 규칙은 모든 납품학원)."""
    product = _norm(item.name)
    named = [r for r in rules if r["type_id"] == DELIVERY_TYPE_ID and _norm(r.get("product", "")) == product]
    for rule in named:
        campuses = {_norm(c) for c in rule.get("campuses", [])}
        if campuses and _norm(campus) not in campuses:
            continue
        if rule["price"] is None:
            return PriceQuote("manual", rule_id=rule["id"], reason=f"'{item.name}' 은(는) 단가를 직접 입력해야 합니다.")
        return PriceQuote("auto", price=_compute(rule["price"], item), rule_id=rule["id"])
    if named:
        return PriceQuote("manual", reason=f"'{item.name}' 은(는) 이 납품학원의 단가가 없어 직접 입력해야 합니다.")
    return PriceQuote("manual", reason="납품서 단가표에 없는 제품이라 단가를 직접 입력해야 합니다.")


def quote(mode: str, type_id: Optional[str], type_name: str, spec: dict[str, str],
          item: Item, rules: list[dict], campus: str = "") -> PriceQuote:
    """한 품목의 자동 단가. item.qty 는 총 발주수량(다중이면 분배표 합계)이어야 한다.
    campus 는 납품서 모드의 납품학원(학원별로 단가가 다른 제품용)."""
    if mode == "blank_order":
        return PriceQuote("manual", reason="빈 발주서는 단가를 직접 입력해야 합니다.")
    if mode == "blank_delivery":
        return _quote_delivery(item, campus, rules)

    typed = [r for r in rules if r["type_id"] == type_id]
    for rule in typed:
        if _matches(rule, spec, item):
            if rule["price"] is None:
                return PriceQuote("manual", rule_id=rule["id"],
                                  reason=f"{type_name}은(는) 단가를 직접 입력해야 합니다.")
            return PriceQuote("auto", price=_compute(rule["price"], item), rule_id=rule["id"])
    if not typed:
        return PriceQuote("manual", reason=f"{type_name}의 단가표가 없어 단가를 직접 입력해야 합니다.")
    return PriceQuote("manual", reason="단가표에 없는 조합이라 단가를 직접 입력해야 합니다.")


def fill_unit_prices(mode: str, type_id: Optional[str], type_name: str, spec: dict[str, str],
                     lines: list[DeliveryLine], rules: list[dict], campus: str = "") -> list[Optional[int]]:
    """납품서 각 줄의 단가: 사용자 입력 > 자동 단가 > 빈칸."""
    out: list[Optional[int]] = []
    for line in lines:
        typed = line.item.unit_price
        if typed is not None:
            out.append(typed)
            continue
        q = quote(mode, type_id, type_name, spec, line.item, rules, campus)
        out.append(q.price if q.status == "auto" else None)
    return out
