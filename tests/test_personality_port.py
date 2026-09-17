"""Offline tests for personality + retrieval modules (no API keys needed)."""
import math

from tools.personality_quick import parse_quick, quick_spec
from tools.personality_quiz import quiz_questions, score_answers
from tools.personality_takeout import parse_takeout
from tools.user_embedding import embed_personality, personality_to_text, style_line
from tools.user_hnsw import BruteForceUserIndex, benchmark as hnsw_benchmark
from tools.retrieval_benchmark import BM25, benchmark as retrieval_benchmark


def test_quick_spec_and_defaults():
    spec = quick_spec()
    assert len(spec["vibes"]) == 7
    assert spec["defaults"]["pace"] == "moderate"


def test_quick_empty_is_neutral():
    card = parse_quick({})
    assert card["source"] == "quick"
    assert all(v == 0.0 for v in card["interests"].values())


def test_quick_vibes_score():
    card = parse_quick({"vibes": ["food", "walking"], "pace": "fast"})
    assert card["interests"]["food"] == 1.0
    assert card["pace"] == "fast"


def test_quick_extra_filters_kept_verbatim():
    card = parse_quick({"vibes": [], "free_text": "vegetarian food,  no museums "})
    assert card["extra"] == "vegetarian food, no museums"
    assert card["interests"]["food"] == 1.0
    line = style_line(card)
    assert "vegetarian food, no museums" in line
    assert "vegetarian" in personality_to_text(card)


def test_quiz_scores():
    answers = {"food": "food_first", "culture": "museum", "pace": "pace_moderate",
               "setting": "mixed", "budget": "mid", "evening": "shopping_stroll"}
    assert len(quiz_questions()) == 6
    card = score_answers(answers)
    assert card["interests"]["food"] == 1.0
    assert card["source"] == "quiz"


def test_takeout_parses_visits():
    card = parse_takeout({"visits": [
        {"name": "Ichiran Ramen", "category": "ramen restaurant", "duration_min": 60}]})
    assert card["visit_count"] == 1
    assert card["interests"]["food"] == 1.0


def test_embedding_normalized_and_stable():
    card = parse_quick({"vibes": ["food", "art"]})
    assert "food" in personality_to_text(card)
    first, second = embed_personality(card), embed_personality(card)
    assert first == second
    assert len(first) == 256
    assert abs(math.sqrt(sum(v * v for v in first)) - 1.0) < 1e-6


def test_style_line_mentions_top_vibe():
    line = style_line(parse_quick({"vibes": ["food"]}))
    assert "food" in line and "Traveler style" in line


def test_brute_force_exact_and_hnsw_benchmark():
    index = BruteForceUserIndex()
    index.add(["a", "b"], [[1.0, 0.0], [0.0, 1.0]])
    assert index.query([1.0, 0.0], k=1)[0][0] == "a"
    result = hnsw_benchmark(num_users=200, dim=16, k=5, num_queries=5)
    assert result["recall_at_k"] >= 0.9
    assert result["recommendation"] in ("brute-force", "hnsw")


def test_bm25_and_retrieval_benchmark():
    docs = ["Tokyo ramen area visit", "Paris museum area visit"]
    assert BM25(docs).scores("ramen Tokyo")[0] == max(BM25(docs).scores("ramen Tokyo"))
    result = retrieval_benchmark(limit=4)
    assert set(result["modes"]) == {"bm25", "vector", "hybrid", "hybrid_reranked"}
    assert result["recommended"] in result["modes"]
