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


def test_values_match_the_2010_ada_standards():
    """Each number checked against the published text (NC-3). Change one only with a new citation."""
    assert c.MIN_SLOPE_RATIO.value == 12  # 405.2: 1:12
    assert c.MAX_RISE_PER_RUN_IN.value == 30  # 405.6
    assert c.MIN_CLEAR_WIDTH_IN.value == 36  # 405.5
    assert c.MIN_LANDING_LENGTH_IN.value == 60  # 405.7.3
    assert c.HANDRAIL_RISE_THRESHOLD_IN.value == 6  # 405.8: rise greater than 6 in
    assert 34 <= c.HANDRAIL_HEIGHT_IN.value <= 38  # 505.4: 34 to 38 in
    assert (c.BED_MIN_HEIGHT_IN.value, c.BED_MAX_HEIGHT_IN.value) == (15, 34)  # 308.2.1 low reach, 308.3.2 obstruction height
    assert c.BED_MAX_WIDTH_ONE_SIDE_IN.value == 24  # 308.3.2 obstruction depth
    assert c.BED_MAX_WIDTH_BOTH_SIDES_IN.value == 2 * c.BED_MAX_WIDTH_ONE_SIDE_IN.value  # derived: 24 in from each side
    assert c.BED_PATH_CLEARANCE_IN.value == 36  # 403.5.1
    assert (c.STEP_MAX_RISER_IN.value, c.STEP_MIN_TREAD_IN.value) == (7, 11)  # 504.2


def test_sources_have_the_documented_shape():
    for key, source in sources().items():
        assert set(source) == {"title", "publisher", "url", "notes"}, key


def test_a_template_without_a_rules_module_has_no_checks():
    assert check_design("no_such_template", None, None, []) == []


def test_no_citation_is_a_placeholder_any_more():
    for key, source in sources().items():
        assert "TBD" not in source["title"] and "TBD" not in source["publisher"], key
        assert not key.startswith("tbd-"), key


def test_every_ada_citation_names_a_section_and_links_to_the_standard():
    for key, source in sources().items():
        if key.startswith("ada-"):
            assert "2010 ADA Standards" in source["title"] and source["url"].startswith("https://www.access-board.gov/ada/"), key
            assert "Verified" in source["notes"], key


def test_the_only_sources_without_a_link_are_the_non_guideline_ones():
    assert {k for k, s in sources().items() if s["url"] is None} == {"local-code-notice", "site-fit", "lumber-stock-lengths"}
