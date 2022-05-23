import pytest

from ckanext.scheming.unaids_helpers import comma_swap_formatter


@pytest.mark.parametrize("input,expected",
                         [("no_commas", "no_commas"),
                          ("comma,split", "split comma"),
                          ("Tanzania, Republic of", "Republic of Tanzania")
                          ])
def test_comma_swap_formatter(input, expected):
    actual = comma_swap_formatter(input)
    assert actual == expected
