"""종류 기본값·조건부 규칙·사이즈 따라가기의 참조 구현.

실제 적용은 브라우저(static/js/order_form.js)에서 하고 서버는 최종 값을 받는다.
이 모듈은 JS 와 동일한 의미를 테스트로 고정하기 위한 것이다.
"""
from processors.order_form.fields import FIELD_IDS, SIZE_FOLLOW_FIELDS, SIZE_SOURCE_FIELD


def type_defaults(type_cfg: dict) -> dict[str, str]:
    """종류 선택 직후의 사양 값. 기본값이 없는 사이즈 칸은 내지 사이즈를 따른다."""
    spec = {fid: (type_cfg["fields"][fid]["default"] or "") for fid in FIELD_IDS}
    for fid in SIZE_FOLLOW_FIELDS:
        if type_cfg["fields"][fid]["default"] is None:
            spec[fid] = spec[SIZE_SOURCE_FIELD]
    return spec


def follow_fields(type_cfg: dict) -> set[str]:
    """내지 사이즈를 따라가는 필드 집합 (사용자가 직접 수정하기 전까지)."""
    return {fid for fid in SIZE_FOLLOW_FIELDS if type_cfg["fields"][fid]["default"] is None}


def apply_rules(spec: dict[str, str], type_cfg: dict, rules: list[dict],
                touched: set[str] | None = None) -> dict[str, str]:
    """조건이 맞는 규칙의 set 값을, 사용자가 직접 수정하지 않은 칸에만 적용한다.
    조건이 맞지 않는 규칙의 대상 칸은 종류 기본값으로 되돌린다."""
    touched = touched or set()
    out = dict(spec)
    defaults = type_defaults(type_cfg)
    targeted: set[str] = set()
    assigned: dict[str, str] = {}
    for rule in rules:
        when = rule["when"]
        if when["type_id"] != type_cfg["id"]:
            continue
        matched = spec.get(when["field"], "") == when["equals"]
        for fid, value in rule["set"].items():
            targeted.add(fid)
            if matched and fid not in assigned:
                assigned[fid] = value
    for fid in targeted:
        if fid in touched:
            continue
        out[fid] = assigned.get(fid, defaults[fid])
    return out


def apply_size_follow(spec: dict[str, str], following: set[str]) -> dict[str, str]:
    out = dict(spec)
    for fid in following:
        out[fid] = out[SIZE_SOURCE_FIELD]
    return out
