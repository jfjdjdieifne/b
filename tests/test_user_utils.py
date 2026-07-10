import pytest

from user_utils import parse_price


@pytest.mark.parametrize("raw, expected", [
    ("1769.75", 1769.75),
    ("1,769.75", 1769.75),
    ("1.769,75", 1769.75),
    ("1.769.75", 1769.75),
    ("١٬٧٦٩٫٧٥", 1769.75),
])
def test_parse_price_formats(raw, expected):
    assert parse_price(raw) == expected


def test_parse_price_rejects_non_positive():
    with pytest.raises(ValueError):
        parse_price("0")
