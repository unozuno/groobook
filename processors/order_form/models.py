"""발주 요청 모델.

- *In 모델: 브라우저가 보내는 원본. 숫자 칸은 문자열 그대로 받아서 validation.py 가
  한국어 메시지와 함께 검증한다 (Pydantic 의 영어 422 응답을 피하기 위함).
- dataclass: 검증·정규화가 끝난 뒤 엑셀 빌더가 쓰는 구조.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

Num = Union[str, int, float, None]

Mode = Literal["order", "blank_order", "blank_delivery"]
OrderKind = Literal["single", "multi"]


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    qty: Num = None
    mono: Num = None      # 1도 페이지 수
    insert: Num = None    # 청간지 페이지 수
    color: Num = None     # 4도 페이지 수
    pages: Num = None     # 빈 납품서 모드에서만 직접 입력
    unit_price: Num = None


class DistributionRowIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    campus: str = ""
    qtys: list[Num] = Field(default_factory=list)


class OrderRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: Mode = "order"
    order_type: OrderKind = "single"
    type_id: Optional[str] = None
    type_name: str = ""
    received_date: str = ""
    due_date: str = ""
    campus: str = ""
    multi_name: str = ""
    job_no: str = ""
    spec: dict[str, Optional[str]] = Field(default_factory=dict)
    messages: list[str] = Field(default_factory=list)
    message_extra: str = ""
    items: list[ItemIn] = Field(default_factory=list)
    distribution: list[DistributionRowIn] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    order: OrderRequest
    force: bool = False


class ReflectRequest(BaseModel):
    """생성한 납품서를 바탕화면의 청구서·마케팅팀 엑셀에 반영 (dry_run=True 면 계획만)."""
    model_config = ConfigDict(extra="ignore")

    order: OrderRequest
    targets: dict[str, bool] = Field(default_factory=dict)   # {"invoice": bool, "marketing": bool}
    dry_run: bool = True


# ───────────────────────── 정규화된 구조 ─────────────────────────

@dataclass
class Item:
    name: str
    qty: Optional[int]
    mono: Optional[int]
    insert: Optional[int]
    color: Optional[int]
    pages: int
    unit_price: Optional[int] = None


@dataclass
class DistributionRow:
    campus: str
    qtys: list[Optional[int]]   # items 와 같은 길이


@dataclass
class DeliveryLine:
    item: Item
    qty: Optional[int]


@dataclass
class DeliveryNote:
    campus: str
    sheet_name: str
    lines: list[DeliveryLine]
    address: Optional[str]      # 주소록 미조회 시 None
    contact: Optional[str]
    unit_prices: list[Optional[int]] = field(default_factory=list)


@dataclass
class Order:
    mode: str
    order_type: str
    type_id: Optional[str]
    type_name: str
    received_date: Optional[date]
    due_date: Optional[date]
    campus: str                 # 다중이면 multi_label, 빈 납품서면 수령자
    multi_name: str
    job_no: str
    spec: dict[str, str]
    messages: list[str]         # 선택 문구 + 자유 입력 (빈 값 제외)
    items: list[Item]
    distribution: list[DistributionRow]
    deliveries: list[DeliveryNote]
