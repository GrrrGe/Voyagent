from tools.personality_quick import parse_quick, quick_spec


def test_quick_spec_has_chips_and_defaults():
    spec = quick_spec()
    assert len(spec["vibes"]) == 7
    assert spec["defaults"] == {"pace": "moderate", "budget": "mid", "setting": "mixed"}


def test_quick_empty_is_neutral():
    card = parse_quick({})
    assert card["source"] == "quick"
    assert all(v == 0.0 for v in card["interests"].values())
    assert card["pace"] == "moderate"


def test_quick_vibes_and_free_text():
    card = parse_quick({"vibes": ["food", "art"], "free_text": "ramen and museums"})
    assert card["interests"]["food"] == 1.0
    assert card["interests"]["art"] > 0


def test_quick_rejects_unknown_and_too_many():
    import pytest
    with pytest.raises(ValueError):
        parse_quick({"vibes": ["skydiving"]})
    with pytest.raises(ValueError):
        parse_quick({"vibes": ["food", "art", "history", "walking", "nature"]})
    with pytest.raises(ValueError):
        parse_quick({"pace": "warp"})


def test_quick_personality_drives_itinerary(graph, monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from tools.user_embedding import embed_personality
    card = parse_quick({"vibes": ["food", "walking"]})
    vec = embed_personality(card)
    state = graph.invoke({"message": "5 days in Tokyo from New York under $1800 on 2030-10-01",
                          "personality": card, "user_vec": vec},
                         {"configurable": {"thread_id": "quick"}})
    assert state["itinerary"]
