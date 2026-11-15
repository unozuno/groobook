"""종류 기본값·조건부 규칙·사이즈 따라가기의 참조 구현.

실제 적용은 브라우저(static/js/order_form.js)에서 하고 서버는 최종 값을 받는다.
이 모듈은 JS 와 동일한 의미를 테스트로 고정하기 위한 것이다.
"""
from processors.order_form.fields import FIELD_IDS, SIZE_FOLLOW_FIELDS, SIZE_SOURCE_FIELD


def type_defaults(type_cfg: dict) -> dict[str, str]:
    """종류 선택 직후의 사양 값. 기본값이 없는 칸(간지·표지 사이즈 포함)은 빈칸이고,
    '내지 따름' 은 항상 꺼진 채로 시작한다."""
    return {fid: (type_cfg["fields"][fid]["default"] or "") for fid in FIELD_IDS}


def norm_option(v: str) -> str:
    return "".join(str(v or "").split())


def can_follow(spec: dict[str, str], type_cfg: dict, fid: str) -> bool:
    """내지 따름을 켤 수 있는가 — 현재 내지 사이즈 값이 해당 칸의 옵션 목록에 있어야 한다."""
    src = norm_option(spec.get(SIZE_SOURCE_FIELD))
    if not src or fid not in SIZE_FOLLOW_FIELDS:
        return False
    return any(norm_option(o) == src for o in type_cfg["fields"][fid]["options"])


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
