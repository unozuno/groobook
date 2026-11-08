"""납품서 단가 결정 지점.

1단계: 사용자가 입력한 단가를 그대로 쓴다 (없으면 빈칸, 엑셀에서 직접 입력).
2단계: 단가표가 나오면 이 함수에서 제작 종류·사양·페이지·수량을 보고 단가를 채운다.
"""
from typing import Optional

from processors.order_form.models import DeliveryLine, Order


def fill_unit_prices(order: Order, lines: list[DeliveryLine]) -> list[Optional[int]]:
    return [line.item.unit_price for line in lines]
