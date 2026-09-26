"""GEO-8: rule constants and their citations."""

from app.rules import check_design, sources
from app.rules import constants as c


def test_every_constant_has_a_source_key_that_exists():
    assert c.ALL, "no constants found"
    for name, constant in c.ALL.items():
        assert constant.source_key in sources(), f"{name} cites {constant.source_key!r}, which is not in sources.json"


def test_no_source_is_unused():
    used = {constant.source_key for constant in c.ALL.values()}
    assert used == set(sources()), f"unused sources: {set(sources()) - used}"


def test_placeholder_values_match_the_agreed_starting_numbers():
    assert c.MIN_SLOPE_RATIO.value == 12
    assert c.MAX_RISE_PER_RUN_IN.value == 30
    assert c.MIN_CLEAR_WIDTH_IN.value == 36
    assert c.MIN_LANDING_LENGTH_IN.value == 60
    assert c.HANDRAIL_RISE_THRESHOLD_IN.value == 6
    assert c.HANDRAIL_HEIGHT_IN.value == 36


def test_sources_have_the_documented_shape():
    for key, source in sources().items():
        assert set(source) == {"title", "publisher", "url", "notes"}, key


def test_a_template_without_a_rules_module_has_no_checks():
    assert check_design("no_such_template", None, None, []) == []
