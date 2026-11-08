import pytest

from processors.order_form.models import OrderRequest
from processors.order_form.seed import build_seed_settings
from processors.order_form.validation import validate


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """모든 테스트가 임시 data 디렉토리를 사용하도록 격리한다."""
    monkeypatch.setenv("GROOBOOK_DATA_DIR", str(tmp_path / "data"))
    return tmp_path / "data"


@pytest.fixture
def settings():
    return build_seed_settings()


def make_request(**kw) -> OrderRequest:
    data = {
        "mode": "order", "order_type": "single", "type_id": "textbook",
        "received_date": "2026-11-08", "due_date": "2026-11-10",
        "campus": "평촌캠퍼스", "job_no": "2105",
        "spec": {"binding_method": "무선제본", "binding_staple": "좌철",
                 "inner_paper": "80g 미색모조", "inner_print": "양면 2도", "inner_size": "210*297",
                 "insert_paper": "90g 청간지", "insert_print": "양면 2도", "insert_size": "210*297",
                 "cover_paper": "250g 아트지", "cover_print": "단면 4도", "cover_size": "210*297",
                 "cover_coating": "무광코팅", "cover_plate": "", "packaging": "댐지포장"},
        "messages": ["첫, 마지막 페이지 표지입니다", "쪽번호 붙여 주세요"], "message_extra": "",
        "items": [
            {"name": "중2 영어 내신", "qty": "700", "mono": "", "insert": "", "color": "2"},
            {"name": "중3 영어 내신", "qty": 300, "mono": "10", "insert": "2", "color": ""},
            {"name": "교사용", "qty": "5", "mono": "100", "insert": "", "color": "4", "unit_price": "1200"},
        ],
    }
    data.update(kw)
    return OrderRequest.model_validate(data)


@pytest.fixture
def make_order(settings):
    def _make(**kw):
        res, order = validate(make_request(**kw), settings)
        assert res.ok, [i.message for i in res.errors]
        return order
    return _make


@pytest.fixture
def sample_order(make_order):
    return make_order()


@pytest.fixture
def sample_multi_order(make_order):
    return make_order(order_type="multi", multi_name="평촌분당", distribution=[
        {"campus": "평촌캠퍼스", "qtys": ["700", "0", "5"]},
        {"campus": "분당캠퍼스", "qtys": ["300", "10", ""]},
        {"campus": "없는학원", "qtys": ["0", "", ""]},
    ])
