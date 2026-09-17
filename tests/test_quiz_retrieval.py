from tools.personality_quiz import quiz_questions, score_answers
from tools.retrieval_benchmark import BM25, benchmark, retrieve_with_mode, rrf_fusion
from tools.knowledge import HashEmbeddings


ANSWERS = {
    "food": "food_first",
    "culture": "museum",
    "pace": "pace_moderate",
    "setting": "mixed",
    "budget": "mid",
    "evening": "shopping_stroll",
}


def test_quiz_has_six_questions():
    questions = quiz_questions()
    assert len(questions) == 6
    assert {q["id"] for q in questions} == set(ANSWERS)


def test_quiz_scores_food_first():
    card = score_answers(ANSWERS)
    assert card["interests"]["food"] == 1.0
    assert card["interests"]["art"] > 0
    assert card["pace"] == "moderate"
    assert card["source"] == "quiz"


def test_quiz_rejects_missing():
    import pytest
    with pytest.raises(ValueError):
        score_answers({"food": "food_first"})


def test_quiz_rejects_unknown_option():
    import pytest
    bad = dict(ANSWERS, pace="pace_warp")
    with pytest.raises(ValueError):
        score_answers(bad)


def test_bm25_ranks_exact_match_first():
    docs = ["Tokyo ramen area visit", "Paris museum area visit", "Lisbon park walk area"]
    bm25 = BM25(docs)
    scores = bm25.scores("ramen Tokyo")
    assert scores[0] == max(scores)


def test_rrf_fusion_prefers_agreement():
    fused = rrf_fusion([[0, 1, 2], [0, 2, 1]])
    assert fused[0] == 0


def test_retrieval_modes_return_valid_rankings():
    docs = ["Tokyo ramen area", "Tokyo museum area", "Tokyo park walk area"]
    embed = HashEmbeddings()
    vecs = embed.embed_documents(docs)
    for mode in ("bm25", "vector", "hybrid", "hybrid_reranked"):
        ranked = retrieve_with_mode("Tokyo ramen", embed.embed_query("Tokyo ramen"),
                                    docs, vecs, mode=mode, limit=2)
        assert sorted(ranked) != sorted(ranked) or len(ranked) == 2
        assert len(ranked) == 2
        assert set(ranked) <= {0, 1, 2}


def test_retrieval_benchmark_reports_all_modes():
    result = benchmark(limit=4)
    assert set(result["modes"]) == {"bm25", "vector", "hybrid", "hybrid_reranked"}
    for mode, stats in result["modes"].items():
        assert 0.0 <= stats["recall"] <= 1.0
        assert 0.0 <= stats["mrr"] <= 1.0
        assert stats["queries"] > 0
    assert result["recommended"] in result["modes"]


def test_quiz_personality_drives_itinerary(graph, monkeypatch, tmp_path):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from tools.user_embedding import embed_personality
    card = score_answers(ANSWERS)
    vec = embed_personality(card)
    state = graph.invoke({"message": "5 days in Tokyo from New York under $1800 on 2030-10-01",
                          "personality": card, "user_vec": vec},
                         {"configurable": {"thread_id": "quiz"}})
    assert state["itinerary"]
