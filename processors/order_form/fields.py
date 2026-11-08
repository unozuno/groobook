"""발주서 사양 필드 정의 (단일 출처).

필드 id 는 설정 JSON, 요청 JSON, 프런트엔드가 공유하는 안정적인 키다.
표시 이름이나 순서를 바꿀 때는 이 파일만 수정한다.
"""

# (field_id, 표시 라벨, 그룹)
FIELD_DEFS: list[tuple[str, str, str]] = [
    ("binding_method", "제본제식", "제본"),
    ("binding_staple", "제본철", "제본"),
    ("inner_paper", "용지", "내지"),
    ("inner_print", "인쇄도수", "내지"),
    ("inner_size", "사이즈", "내지"),
    ("insert_paper", "용지", "간지"),
    ("insert_print", "인쇄도수", "간지"),
    ("insert_size", "사이즈", "간지"),
    ("cover_paper", "용지", "표지"),
    ("cover_print", "인쇄도수", "표지"),
    ("cover_size", "사이즈", "표지"),
    ("cover_coating", "코팅·후가공", "표지"),
    ("cover_plate", "동판", "표지"),
    ("packaging", "포장 방식", "포장"),
]

FIELD_IDS: tuple[str, ...] = tuple(f[0] for f in FIELD_DEFS)
FIELD_LABELS: dict[str, str] = {f[0]: f[1] for f in FIELD_DEFS}
FIELD_GROUP_OF: dict[str, str] = {f[0]: f[2] for f in FIELD_DEFS}

GROUP_ORDER: tuple[str, ...] = ("제본", "내지", "간지", "표지", "포장")
FIELD_GROUPS: dict[str, list[str]] = {
    g: [f[0] for f in FIELD_DEFS if f[2] == g] for g in GROUP_ORDER
}

# 내지 사이즈를 따라가는(기본값이 비어 있을 때) 필드
SIZE_FOLLOW_FIELDS: tuple[str, ...] = ("insert_size", "cover_size")
SIZE_SOURCE_FIELD = "inner_size"

# 품목 표 기본값 키
ITEM_DEFAULT_KEYS: tuple[str, ...] = ("qty", "mono", "insert", "color")
ITEM_DEFAULT_LABELS: dict[str, str] = {
    "qty": "발주수량",
    "mono": "1도",
    "insert": "청간지",
    "color": "4도",
}


def field_meta() -> list[dict]:
    """API 로 프런트엔드에 전달할 필드 메타데이터."""
    return [{"id": fid, "label": label, "group": group} for fid, label, group in FIELD_DEFS]
