"""관리자 설정 초기 데이터(seed).

지시서 4장(제작 종류별 선택지·기본값·품목 기본값)과 기준 파일
`인수처주소및담당자` 시트(53곳)를 그대로 옮긴 것이다.
최초 실행 시 data/order_settings.json 으로 기록된 뒤에는 관리자 화면에서 수정한다.
"""
import copy

from processors.order_form.fields import FIELD_IDS, ITEM_DEFAULT_KEYS

SCHEMA_VERSION = 1

DEFAULT_MULTI_LABEL = "다중"

DEFAULT_MESSAGES = [
    "첫, 마지막 페이지 표지입니다",
    "사방여백 조정해 주세요",
    "사이즈 조정해 주세요",
    "쪽번호 붙여 주세요",
]


def _opts(*values: str) -> dict:
    """선택지 목록 → {"options": [...], "default": 첫 값}. 값이 없으면 빈 필드."""
    values = [v for v in values if v]
    return {"options": list(values), "default": values[0] if values else None}


def _type(type_id: str, name: str, fields: dict, item_defaults: dict | None = None) -> dict:
    full_fields = {fid: fields.get(fid, _opts()) for fid in FIELD_IDS}
    defaults = {k: None for k in ITEM_DEFAULT_KEYS}
    if item_defaults:
        defaults.update(item_defaults)
    return {"id": type_id, "name": name, "fields": full_fields, "item_defaults": defaults}


_TEXTBOOK = _type("textbook", "교재", {
    "binding_method": _opts("무선제본", "스프링제본", "중철제본"),
    "binding_staple": _opts("좌철", "상철", "양면 PVC"),
    "inner_paper": _opts("80g 미색모조", "80g 백색모조", "100g 미색모조",
                         "100g 백색모조", "120g 미색모조", "120g 백색모조"),
    "inner_print": _opts("양면 2도", "양면 4도", "양면 8도"),
    "inner_size": _opts("210*297", "188*257", "182*257", "148*210"),
    "insert_paper": _opts("80g 미색모조"),
    "insert_print": _opts("양면 2도"),
    # insert_size / cover_size: 기본값 없음 → 내지 사이즈를 따라감
    "cover_paper": _opts("250g 아트지", "300g 아트지"),
    "cover_print": _opts("단면 4도", "양면 8도", "단면 1도"),
    "cover_coating": _opts("무광코팅", "유광코팅", "엠보코팅"),
    "packaging": _opts("댐지포장", "박스포장"),
})

_NOTE = _type("note", "노트", {
    "binding_method": _opts("무선제본"),
    "binding_staple": _opts("좌철"),
    "inner_paper": _opts("80g 미색모조"),
    "inner_print": _opts("양면 2도"),
    "inner_size": _opts("210*297"),
    "cover_paper": _opts("250g 아트지"),
    "cover_print": _opts("단면 4도"),
    "cover_size": _opts("210*297"),
    "cover_coating": _opts("무광코팅"),
    "packaging": _opts("댐지포장"),
})

_EXAM = _type("exam_paper", "시험지", {
    "binding_method": _opts("중철제본"),
    "inner_paper": _opts("80g 미색모조"),
    "inner_print": _opts("양면 2도"),
    "inner_size": _opts("210*297"),
    "packaging": _opts("박스포장"),
})

_BUSINESS_CARD = _type("business_card", "명함", {
    "inner_paper": _opts("스타드림", "300 아르떼"),
    "inner_print": _opts("양면 8도"),
    "inner_size": _opts("90*50", "50*90"),
}, {"qty": 200, "color": 2})

_BROCHURE = _type("brochure", "브로셔", {
    "binding_method": _opts("무선제본", "중철제본"),
    "binding_staple": _opts("좌철", "상철"),
    "inner_paper": _opts("130g 아르떼"),
    "inner_print": _opts("양면 8도", "단면 4도"),
    "inner_size": _opts("210*297"),
    "cover_paper": _opts("230g 아르떼"),
    "cover_print": _opts("단면 4도"),
    "cover_size": _opts("210*297"),
    "cover_coating": _opts("무광코팅"),
    "packaging": _opts("댐지포장"),
})

_LEAFLET = _type("leaflet", "안내문", {
    "binding_method": _opts("A4 재단", "A3 2단 오시접지", "3단 오시접지"),
    "cover_paper": _opts("190g 아르떼"),
    "cover_print": _opts("양면 8도", "단면 4도"),
    "cover_size": _opts("210*297", "297*210", "148*210", "210*148"),
    "packaging": _opts("박스포장"),
})

_STAMP_BOARD = _type("stamp_board", "스탬프보드", {
    "binding_method": _opts("A4 재단"),
    "cover_paper": _opts("220 백색모조"),
    "cover_print": _opts("양면 8도"),
    "cover_size": _opts("210*297"),
    "packaging": _opts("박스포장"),
}, {"color": 2})

_VOUCHER = _type("voucher", "상품권", {
    "binding_method": _opts("재단"),
    "cover_paper": _opts("200 스노우"),
    "cover_print": _opts("양면 8도"),
    "cover_size": _opts("145*65"),
}, {"color": 2})

_LETTER_PAPER = _type("letter_paper", "레터지", {
    "binding_method": _opts("재단"),
    "inner_paper": _opts("100g 미색모조", "120g 미색모조"),
    "inner_print": _opts("단면 4도"),
    "inner_size": _opts("210*297"),
    "packaging": _opts("박스포장"),
}, {"color": 1})

_BINGO = _type("bingo_board", "빙고판", {
    "binding_method": _opts("A4 재단"),
    "cover_paper": _opts("190g 아르떼", "160g 아르떼", "130g 아르떼"),
    "cover_print": _opts("양면 8도", "단면 4도"),
    "cover_size": _opts("210*297"),
    "packaging": _opts("박스포장"),
})

_POSTER = _type("poster", "포스터", {
    "binding_method": _opts("A2 재단", "A3 재단"),
    "cover_paper": _opts("스티커형 인쇄", "200스노우"),
    "cover_print": _opts("단면 4도"),
    "cover_size": _opts("420*594", "297*420"),
    "packaging": _opts("박스포장"),
}, {"color": 1})

_CERTIFICATE = _type("certificate", "상장", {
    "binding_method": _opts("A4 재단"),
    "cover_paper": _opts("220g 백색모조", "160g 랑데부"),
    "cover_print": _opts("단면 4도"),
    "cover_size": _opts("210*297", "297*210"),
    "cover_coating": _opts("유광금박"),
    "cover_plate": _opts("기존동판사용", "동판출력"),
    "packaging": _opts("박스포장"),
}, {"color": 1})

_INVITATION = _type("invitation", "초대장", {
    "binding_method": _opts("2단접지", "재단"),
    "cover_paper": _opts("190g 아르떼"),
    "cover_print": _opts("양면 8도", "단면 4도"),
    "cover_size": _opts("210*297", "148*105"),
    "packaging": _opts("박스포장"),
})


def _copy_type(src: dict, type_id: str, name: str) -> dict:
    """상장→졸업장, 초대장→엽서처럼 값은 같지만 독립적으로 저장되는 종류."""
    t = copy.deepcopy(src)
    t["id"] = type_id
    t["name"] = name
    return t


SEED_TYPES = [
    _TEXTBOOK, _NOTE, _EXAM, _BUSINESS_CARD, _BROCHURE, _LEAFLET, _STAMP_BOARD,
    _VOUCHER, _LETTER_PAPER, _BINGO, _POSTER,
    _CERTIFICATE, _copy_type(_CERTIFICATE, "diploma", "졸업장"),
    _INVITATION, _copy_type(_INVITATION, "postcard", "엽서"),
]

# 조건부 규칙: 값은 설정에서 읽히므로 관리자가 JSON 을 수정하면 바뀐다 (1단계는 편집 UI 없음)
SEED_RULES = [
    {
        "id": "textbook_spring",
        "when": {"type_id": "textbook", "field": "binding_method", "equals": "스프링제본"},
        "set": {"binding_staple": "양면 PVC", "cover_coating": "", "packaging": "박스포장"},
    },
    {
        "id": "textbook_saddle",
        "when": {"type_id": "textbook", "field": "binding_method", "equals": "중철제본"},
        "set": {"binding_staple": ""},
    },
]

# (캠퍼스명, 인수처 주소, 인수 담당자, 전화번호) — 접두어·공백 제거 완료
_ADDRESS_ROWS = [
    ('대치본원', '서울시 강남구 남부순환로 2917 청실상가 4층 DYB최선어학원', '박일도 과장님(010-8543-8993)', '02-556-7094'),
    ('대치본원 S관', '서울시 강남구 남부순환로 2927 대치클래시아 4층 DYB 최선어학원', '박정기 대리님 (010-6881-9800)', '02-555-7094'),
    ('송파캠퍼스', '서울시 송파구 방이동 마천로21 DYB빌딩 2층 DYB최선어학원 02-424-7094', '조중원 과장님 (010-2937-9832)', '02-424-7094'),
    ('중계캠퍼스', '서울시 노원구 한글비석로 264 그랜드 프라자 6층 DYB최선어학원', '전성민 주임님 (010-9050-7831)', '02-934-7094'),
    ('분당캠퍼스', '경기도 성남시 분당구 백현로 101번길 30 엑스와이빌딩 4층 DYB최선어학원 031-716-2945', '동경태 차장님 (010-8322-5282)', '031-716-2945'),
    ('수지캠퍼스', '경기도 용인시 수지구 수지로 296번길 51-7(풍덕천동) 가람빌딩 4층 DYB최선어학원', '김재연 대리님 (010-4767-9333)', '031-265-3139'),
    ('수지고등관', '경기도 용인시 수지구 문정로 7번길 14, 삼공타워 6층', '김미영 차장님 (010-8931-6654)', '031-263-3139'),
    ('영통캠퍼스', '경기도 수원시 영통구 영통2동 959-1번지 모던타운빌딩 3층  031-206-8197', '홍수연 주임님 (010-6368-3932)', '031-206-8197'),
    ('1동탄캠퍼스', '경기도 화성시 동탄원천로 163 위너스타빌딩 3층  최선어학원 동탄캠퍼스', '이시웅 차장님 (010-4136-9054)', '031-613-7094'),
    ('2동탄캠퍼스', '경기도 화성시 왕배산길 7 오션타워 3층 (031-373-7094)', '신동훈 과장님 (010-4815-7311)', '031-373-7094'),
    ('수원캠퍼스', '경기도 수원시 장안구 대평로 80 정연메이저빌딩 5층 DYB최선어학원 031-268-5100', '민성범 대리님 (010-4190-9253)', '031-268-5100'),
    ('평촌캠퍼스', '경기도 안양시 동안구 평촌대로 132 제일빌딩 5층 DYB최선어학원 031-387-7227', '김경민 과장님 (010-5125-7196)', '031-387-7227'),
    ('평촌고등관', '경기도 안양시 동안구 평촌대로 136 신세기빌딩 2층 DYB프리머스어학원', '이민우 님 (010-8298-3831)', '031-381-5335'),
    ('일산캠퍼스', '고양시 일산서구 일산로 541 수신빌딩 5층 DYB최선어학원 031-913-6980', '모상현 대리님 (010-8904-1019)', '031-913-6980'),
    ('강동하남캠퍼스', '경기도 하남시 미사강변대로 54번길 90 최선빌딩 3층  031-793-7094', '한경태 차장님 (010-7386-2545)', '031-793-7094'),
    ('죽전캠퍼스', '경기도 용인시 기흥구 죽현로 35 로얄프라자 1,4,8층 (031-889-7094)', '정동환 대리님 (010-9425-9697)', '031-889-7094'),
    ('최선메이트', '경기도 광주시 오포읍 봉골길 23-42 러닝큐브', '송형규 대표님 (010-7460-5042)', ''),
    ('평촌마타수학', '경기도 안양시 동안구 평촌대로 122 내외프라자 4층', '양두영 과장님 (010-5209-9272)', '031-383-1357'),
    ('하남크레오', '경기도 하남시 풍산동 509-1 1층  031-793-0570', '장지훈 과장님 (010-6395-5305)', ''),
    ('대치크레오', '서울시 강남구 남부순환로 2909 8층 크레오어학원 고객지원실 02-563-0579', '이지희 과장님 (010-9949-0939)', ''),
    ('송파크레오', '서울시 송파구 마천로21 최선빌딩 1층 02-418-0579', '곽민기 팀장님 (010-8534-8073)', ''),
    ('러닝큐브', '경기도 광주시 오포읍 봉골길 23-42 러닝큐브', '송형규 대표님 (010-7460-5042)', ''),
    ('MPC', '서울 동대문구 무학로44길 8, 갑산빌딩 101호', '김규회 이사님 (010-6336-4083)', ''),
    ('수지3관캠퍼스', '경기도 용인시 수지구 문정로 7번길 20 해명빌딩 2층', '신설희 대리님 (010-4782-5632)', '031-272-7094'),
    ('MPC_안성', '경기 안성시 양성면 남북대로 1698', '임철영 과장님 (010-9041-3713)', ''),
    ('Beyond 팀', '서울시 강남구 남부순환로 2917 4층 DYB최선어학원, S22호 DX Beyond팀', '이은정 매니저님 (010-3431-3411)', ''),
    ('브랜드마케팅', '서울시 강남구 남부순환로 2917 4층 DYB최선어학원, S22호 브랜드마케팅', '천미진 매니저님 (010-9459-5259)', ''),
    ('입시전략연구소', '서울 강남구 대치 미도상가 2층 입시전략 연구소', '조 으뜸나 M2 님', ''),
    ('키비즈', '서울시 강남구 논현로 170 서원빌딩', '유승혜 소장님 (010-8925-5899)', ''),
    ('최선 구리남양주', '경기 남양주시 다산순환로 459, 미래빌딩 5층', '031-567-7094', ''),
    ('최선 동래', '부산시 동래구 사직동 129-34번지 SB 빌딩 3층', '051-501-2345', ''),
    ('최선 마포', '서울특별시 마포구 서강대길 3 서강빌딩 8층', '02-822-0579', ''),
    ('최선 송도', '인천 연수구 신송로 164 아데니움 플라자 4층', '032-715-7220', ''),
    ('최선 청라', '인천광역시 서구 청라루비로 93 루비타워 5층', '032-715-8324', ''),
    ('최선 은평', '서울시 은평구 가좌로 204 동양빌딩', '02-336-0263', ''),
    ('최선 은평2관', '서울특별시 서대문구 응암로 54, 4층 (북가좌동, 서부프라자빌딩)', '02-304-0263', ''),
    ('최선 천안', '충남 천안시 서북구 검은들 3길 38 한나프라자 6층', '041-414-5115', ''),
    ('최선 포항남구', '경북 포항시 남구 대이로 39 이화빌딩 3층', '054-285-1000', ''),
    ('최선 운정', '경기 파주시 미래로 369-21 삼우프라자 3층', '031-941-6980', ''),
    ('최선 동작', '서울특별시 동작구 상도로 121 영진빌딩 2층', '02-877-7094', ''),
    ('최선 광명', '경기 광명시 하안로 288번길 15, 3층', '02-893-0579', ''),
    ('최선 경기광주', '경기 광주시 태전중앙1길 5, 2동  8층', '031-767-1666', ''),
    ('최선 둔산', '대전 서구 문예로 59  6층', '042-477-1001', ''),
    ('최선 부천', '경기도 부천시 길주로 115, 9층', '032-212-7094', ''),
    ('최선 평택국제', '경기도 평택시 고덕로 249 서강빌딩 5층', '031-667-7094', ''),
    ('최선 김포한강', '경기 김포시 전원로 5 핵심프라자 4층', '031-987-7094', ''),
    ('최선 창원', '창원시 의창구 중동 782-1번지 제이디윙스 3층', '055-298-2345', ''),
    ('최선 광주', '광주광역시 광산구 목련로 253번길 31, 2층', '062-716-7094', ''),
    ('최선 전주', '전북특별자치도 전주시 완산구 유연로 154, 3층', '063-227-7094', ''),
    ('최선 인천남동', '인천 남동구 구월로 221 아세아프라자 3층', '032-721-7094', ''),
    ('최선 덕양', '경기 고양시 덕양구 향기로 115 봄프라자 7층 702호 최선어학원', '02-6930-5898', ''),
    ('최선 세종', '세종특별자치시 한누리대로 275, 형성프라자 3층 303호', '044-868-3001', ''),
    ('최선 대구 수성시지', '대구광역시 수성구 달구벌대로 3294, 7층(신매동)', '053-794-0565', ''),
]

SEED_ADDRESS_BOOK = [
    {"id": f"a{idx + 1:03d}", "name": name, "address": addr, "contact": contact, "phone": phone}
    for idx, (name, addr, contact, phone) in enumerate(_ADDRESS_ROWS)
]


def build_seed_settings() -> dict:
    """항상 새 복사본을 반환한다 (호출자가 수정해도 시드가 오염되지 않도록)."""
    return copy.deepcopy({
        "schema_version": SCHEMA_VERSION,
        "updated_at": None,
        "multi_label": DEFAULT_MULTI_LABEL,
        "messages": list(DEFAULT_MESSAGES),
        "types": SEED_TYPES,
        "rules": SEED_RULES,
        "address_book": SEED_ADDRESS_BOOK,
    })
