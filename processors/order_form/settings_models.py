"""관리자 설정 스키마 (Pydantic). 저장·가져오기 전에 구조와 중복을 검증한다."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from processors.order_form.fields import FIELD_IDS, ITEM_DEFAULT_KEYS


class SettingsValidationError(ValueError):
    """사람이 읽을 수 있는 한국어 메시지 목록을 가진 설정 검증 오류."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _strip_unique(values: list[str], what: str) -> list[str]:
    cleaned = []
    for v in values:
        s = (v or "").strip()
        if not s:
            raise ValueError(f"{what}에 빈 값이 있습니다.")
        if s in cleaned:
            raise ValueError(f"{what}에 중복 값이 있습니다: {s}")
        cleaned.append(s)
    return cleaned


class FieldOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    options: list[str] = Field(default_factory=list)
    default: Optional[str] = None

    @field_validator("options")
    @classmethod
    def _options_clean(cls, v):
        return _strip_unique(v, "선택지")

    @model_validator(mode="after")
    def _default_in_options(self):
        if self.default is not None:
            self.default = self.default.strip()
            if self.default == "":
                self.default = None
            elif self.default not in self.options:
                raise ValueError(f"기본값 '{self.default}' 이(가) 선택지에 없습니다.")
        return self


class OrderType(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    fields: dict[str, FieldOptions] = Field(default_factory=dict)
    item_defaults: dict[str, Optional[int]] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def _name_strip(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("종류 이름이 비어 있습니다.")
        return v

    @model_validator(mode="after")
    def _normalize(self):
        unknown = set(self.fields) - set(FIELD_IDS)
        if unknown:
            raise ValueError(f"알 수 없는 필드: {', '.join(sorted(unknown))}")
        self.fields = {fid: self.fields.get(fid, FieldOptions()) for fid in FIELD_IDS}

        unknown = set(self.item_defaults) - set(ITEM_DEFAULT_KEYS)
        if unknown:
            raise ValueError(f"알 수 없는 품목 기본값 키: {', '.join(sorted(unknown))}")
        for k, v in self.item_defaults.items():
            if v is not None and v < 0:
                raise ValueError(f"품목 기본값 {k} 은(는) 0 이상이어야 합니다.")
        self.item_defaults = {k: self.item_defaults.get(k) for k in ITEM_DEFAULT_KEYS}
        return self


class RuleWhen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type_id: str
    field: str
    equals: str


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    when: RuleWhen
    set: dict[str, str]

    @model_validator(mode="after")
    def _fields_known(self):
        bad = [f for f in [self.when.field, *self.set] if f not in FIELD_IDS]
        if bad:
            raise ValueError(f"규칙 {self.id}: 알 수 없는 필드 {', '.join(bad)}")
        return self


class AddressEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    address: str = ""
    contact: str = ""
    phone: str = ""

    @model_validator(mode="after")
    def _strip_all(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("캠퍼스명이 비어 있습니다.")
        self.address = self.address.strip()
        self.contact = self.contact.strip()
        self.phone = self.phone.strip()
        return self


class OrderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    updated_at: Optional[str] = None
    multi_label: str = "다중"
    # 청구서·마케팅팀 엑셀을 찾을 바탕화면 경로. 비우면 자동 탐색
    desktop_dir: str = ""
    messages: list[str] = Field(default_factory=list)
    types: list[OrderType] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
    address_book: list[AddressEntry] = Field(default_factory=list)

    @field_validator("desktop_dir")
    @classmethod
    def _desktop_dir(cls, v):
        v = (v or "").strip()
        if "\x00" in v:
            raise ValueError("바탕화면 경로에 사용할 수 없는 문자가 있습니다.")
        return v

    @field_validator("multi_label")
    @classmethod
    def _multi_label(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("다중 발주 표기 문구가 비어 있습니다.")
        return v

    @field_validator("messages")
    @classmethod
    def _messages(cls, v):
        return _strip_unique(v, "전달사항 문구")

    @model_validator(mode="after")
    def _uniques(self):
        ids = [t.id for t in self.types]
        if len(ids) != len(set(ids)):
            raise ValueError("제작 종류 id 가 중복됩니다.")
        names = [t.name for t in self.types]
        dup = sorted({n for n in names if names.count(n) > 1})
        if dup:
            raise ValueError(f"제작 종류 이름이 중복됩니다: {', '.join(dup)}")

        aids = [a.id for a in self.address_book]
        if len(aids) != len(set(aids)):
            raise ValueError("주소록 id 가 중복됩니다.")
        anames = [a.name for a in self.address_book]
        dup = sorted({n for n in anames if anames.count(n) > 1})
        if dup:
            raise ValueError(f"주소록 캠퍼스명이 중복됩니다: {', '.join(dup)}")

        rids = [r.id for r in self.rules]
        if len(rids) != len(set(rids)):
            raise ValueError("규칙 id 가 중복됩니다.")
        return self


def _format_errors(exc: ValidationError) -> list[str]:
    out = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e["loc"])
        msg = e["msg"]
        # pydantic 의 "Value error, ..." 접두어 제거
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        out.append(f"{loc}: {msg}" if loc else msg)
    return out


def validate_settings(data: dict) -> dict:
    """검증 후 정규화된 dict 를 반환. 실패 시 SettingsValidationError."""
    try:
        model = OrderSettings.model_validate(data)
    except ValidationError as exc:
        raise SettingsValidationError(_format_errors(exc)) from exc
    return model.model_dump()
