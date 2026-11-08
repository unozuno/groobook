from processors.order_form.compute import (
    campus_totals, distribution_totals, item_totals, page_total, print_volumes,
)
from processors.order_form.models import Item


def test_page_total():
    assert page_total(2, 0, 1) == 3
    assert page_total(None, None, None) == 0
    assert page_total(None, 4, None) == 4


def test_print_volumes():
    assert print_volumes(700, 0, 0, 2) == (0, 0, 1400, 1400)
    assert print_volumes(300, 10, 2, 0) == (3000, 600, 0, 3600)
    assert print_volumes(None, 1, 1, 1) == (0, 0, 0, 0)


def test_distribution_totals_handles_ragged_and_none():
    matrix = [[700, None], [300, 10, 99], [None]]
    assert distribution_totals(matrix, 2) == [1000, 10]
    assert campus_totals(matrix) == [700, 409, 0]


def test_item_totals():
    items = [
        Item("A", 700, 0, 0, 2, 2),
        Item("B", 300, 10, 2, 0, 12),
        Item("C", None, None, None, None, 0),
    ]
    t = item_totals(items)
    assert t == {"qty": 1000, "mono": 10, "insert": 2, "color": 2, "pages": 14,
                 "k": 3000, "l": 600, "m": 1400, "n": 5000}
