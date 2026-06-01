"""Tests for the curated tag taxonomy."""
from src.data_collectors.tags import TagRegistry, TagSpec


def test_keyword_match_case_insensitive():
    tag = TagSpec(id="ai", label="AI", keywords=["llm"], source_tags=[])
    assert tag.matches(text_lower="anthropic ships new llm".lower(), source_tags_lower=set())


def test_source_tag_match():
    tag = TagSpec(id="ai", label="AI", keywords=[], source_tags=["AI"])
    assert tag.matches(text_lower="some article", source_tags_lower={"ai"})


def test_no_match_when_unrelated():
    tag = TagSpec(id="ai", label="AI", keywords=["gpt"], source_tags=["ai"])
    assert not tag.matches(text_lower="local diner reopens", source_tags_lower={"food"})


def test_registry_from_yaml_loads_defaults():
    reg = TagRegistry.from_yaml()
    ids = reg.ids()
    assert "ai" in ids
    assert "security" in ids
    assert reg.get("ai").label == "AI"
