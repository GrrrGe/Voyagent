import math

from tools.personality_takeout import parse_takeout
from tools.user_embedding import embed_personality, personality_to_text, save_profile, load_profile
from tools.user_hnsw import (BruteForceUserIndex, HNSWUserIndex, benchmark,
                             cosine_similarity, rerank_areas)
from tools.knowledge import DIMENSIONS


SAMPLE_TAKEOUT = {
    "visits": [
        {"name": "Ichiran Ramen", "category": "ramen restaurant", "duration_min": 60},
        {"name": "Sushi Dai", "category": "sushi restaurant", "duration_min": 90},
        {"name": "Tokyo National Museum", "category": "museum", "duration_min": 150},
        {"name": "Ueno Park walk", "category": "park walk", "duration_min": 80},
    ],
    "reviews": [
        {"place": "Ichiran Ramen", "category": "ramen", "stars": 5, "text": "Best ramen"},
    ],
    "saved": [
        {"name": "TeamLab Gallery", "category": "gallery"},
    ],
}


def test_parse_takeout_builds_card():
    card = parse_takeout(SAMPLE_TAKEOUT)
    assert card["visit_count"] == 6
    assert card["interests"]["food"] == 1.0
    assert card["interests"]["art"] > 0
    assert card["pace"] in ("slow", "moderate", "fast")
    assert 0.0 <= card["indoor_bias"] <= 1.0
    assert card["keywords"]


def test_parse_takeout_empty():
    card = parse_takeout({})
    assert card["visit_count"] == 0
    assert all(v == 0.0 for v in card["interests"].values())


def test_parse_takeout_rejects_non_object():
    import pytest
    with pytest.raises(ValueError):
        parse_takeout([])


def test_personality_embedding_normalized(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    card = parse_takeout(SAMPLE_TAKEOUT)
    text = personality_to_text(card)
    assert "ramen" in text or "food" in text
    vec = embed_personality(card)
    assert len(vec) == DIMENSIONS
    assert abs(math.sqrt(sum(v * v for v in vec)) - 1.0) < 1e-6


def test_profile_save_load(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    card = parse_takeout(SAMPLE_TAKEOUT)
    save_profile("demo-user", card)
    loaded = load_profile("demo-user")
    assert loaded["card"]["visit_count"] == 6
    assert len(loaded["vector"]) == DIMENSIONS


def test_brute_force_exact():
    index = BruteForceUserIndex()
    index.add(["a", "b"], [[1.0, 0.0], [0.0, 1.0]])
    assert index.query([1.0, 0.0], k=1)[0][0] == "a"
    assert cosine_similarity([1, 0], [1, 0]) == 1.0


def test_hnsw_falls_back_without_dependency():
    index = HNSWUserIndex(dim=2)
    index.add(["a", "b"], [[1.0, 0.0], [0.0, 1.0]])
    assert index.query([1.0, 0.0], k=1)[0][0] == "a"
    assert index.backend in ("hnswlib", "brute-force-fallback")


def test_benchmark_reports_recall():
    result = benchmark(num_users=200, dim=16, k=5, num_queries=5)
    assert result["recall_at_k"] >= 0.9
    assert result["brute_force_ms_per_query"] >= 0
    assert result["recommendation"] in ("brute-force", "hnsw")


def test_rerank_keeps_valid_permutation():
    from tools.knowledge import HashEmbeddings
    user_vec = HashEmbeddings().embed_query("food ramen sushi")
    base = [0, 1, 2]
    texts = ["Tokyo ramen area", "Tokyo museum area", "Tokyo park area"]
    order, scores = rerank_areas(base, texts, user_vec, HashEmbeddings().embed_query, alpha=0.3)
    assert sorted(order) == [0, 1, 2]
    assert len(scores) == 3


def test_personalized_itinerary_runs(graph, monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    card = parse_takeout(SAMPLE_TAKEOUT)
    vec = embed_personality(card)
    state = graph.invoke({"message": "5 days in Tokyo from New York under $1800 on 2030-10-01",
                          "personality": card, "user_vec": vec},
                         {"configurable": {"thread_id": "personality"}})
    assert state["itinerary"]
    assert state["grounding"]
