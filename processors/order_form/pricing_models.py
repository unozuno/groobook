"""단가표 규칙 스키마 (Pydantic). 설정 JSON 의 price_rules 항목."""
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from processors.order_form.fields import FIELD_IDS


class PriceFormula(BaseModel):
    """fixed: 단가 = amount / per_page: 단가 = 페이지합계 × rate + base."""
    model_config = ConfigDict(extra="forbid")

    kind: Literal["fixed", "per_page"]
    amount: Optional[int] = Field(default=None, ge=0)
    rate: Optional[int] = Field(default=None, ge=0)
    base: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _by_kind(self):
        if self.kind == "fixed":
            if self.amount is None:
                raise ValueError("고정 단가는 금액이 필요합니다.")
            self.rate = self.base = None
        else:
            if self.rate is None:
                raise ValueError("페이지 단가는 페이지당 금액이 필요합니다.")
            self.base = self.base or 0
            self.amount = None
        return self


class PriceRule(BaseModel):
    """조건이 모두 맞는 첫 규칙의 price 를 쓴다. price 가 None 이면 직접 입력."""
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    type_id: str = Field(min_length=1)
    when: dict[str, list[str]] = Field(default_factory=dict)   # 사양 필드 id → 허용 값 목록 (빈 목록 = 조건 없음)
    qty_min: Optional[int] = Field(default=None, ge=0)
    qty_max: Optional[int] = Field(default=None, ge=0)
    pages: Optional[int] = Field(default=None, ge=0)           # 페이지합계가 정확히 이 값일 때만
    price: Optional[PriceFormula] = None

    @model_validator(mode="after")
    def _check(self):
        bad = sorted(set(self.when) - set(FIELD_IDS))
        if bad:
            raise ValueError(f"단가 규칙 {self.id}: 알 수 없는 필드 {', '.join(bad)}")
        cleaned = {}
        for field, values in self.when.items():
            vals = [v.strip() for v in values if v and v.strip()]
            if vals:
                cleaned[field] = vals
        self.when = cleaned
        if self.qty_min is not None and self.qty_max is not None and self.qty_min > self.qty_max:
            raise ValueError(f"단가 규칙 {self.id}: 수량 하한이 상한보다 큽니다.")
        return self
