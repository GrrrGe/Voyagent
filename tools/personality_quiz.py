"""Short prerequisite quiz -> traveler personality card.

Six questions, each with 3-4 fixed choices. Answers map to the same card
schema as tools/personality_takeout.py so quiz and Takeout profiles share
the embedding and itinerary paths.
"""

QUESTIONS = [
    {"id": "food", "text": "How central is food to your trips?",
     "options": ["food_first", "food_sometimes", "food_rarely"]},
    {"id": "culture", "text": "Pick a morning you enjoy most.",
     "options": ["museum", "temple_history", "market_walk", "park_outdoors"]},
    {"id": "pace", "text": "What pace do you prefer?",
     "options": ["pace_slow", "pace_moderate", "pace_fast"]},
    {"id": "setting", "text": "Indoor or outdoor?",
     "options": ["indoors", "outdoors", "mixed"]},
    {"id": "budget", "text": "How do you spend on trips?",
     "options": ["budget", "mid", "midplus"]},
    {"id": "evening", "text": "Pick an evening.",
     "options": ["nightlife", "shopping_stroll", "quiet_cafe", "early_rest"]},
]

INTERESTS = ["food", "art", "history", "walking", "nature", "shopping", "nightlife"]

_CULTURE_MAP = {
    "museum": {"art": 1.0},
    "temple_history": {"history": 1.0},
    "market_walk": {"food": 0.6, "walking": 0.6, "shopping": 0.4},
    "park_outdoors": {"walking": 0.7, "nature": 0.7},
}

_EVENING_MAP = {
    "nightlife": {"nightlife": 1.0},
    "shopping_stroll": {"shopping": 0.8, "walking": 0.4},
    "quiet_cafe": {"food": 0.5},
    "early_rest": {},
}


def quiz_questions():
    """Public quiz spec for the frontend (no scoring weights leaked)."""
    return QUESTIONS


def score_answers(answers):
    """Score a dict of {question_id: option} into a personality card.

    Raises ValueError on missing or unknown options so the API can 422.
    """
    if not isinstance(answers, dict):
        raise ValueError("Answers must be an object.")
    missing = [q["id"] for q in QUESTIONS if q["id"] not in answers]
    if missing:
        raise ValueError(f"Missing answers: {', '.join(missing)}.")
    for q in QUESTIONS:
        if answers[q["id"]] not in q["options"]:
            raise ValueError(f"Unknown option for {q['id']}: {answers[q['id']]}.")

    scores = {k: 0.0 for k in INTERESTS}
    food = answers["food"]
    if food == "food_first":
        scores["food"] += 1.5
    elif food == "food_sometimes":
        scores["food"] += 0.7
    else:
        scores["food"] += 0.1

    for key, weight in _CULTURE_MAP[answers["culture"]].items():
        scores[key] += weight
    for key, weight in _EVENING_MAP[answers["evening"]].items():
        scores[key] += weight

    pace = answers["pace"].replace("pace_", "")
    setting = answers["setting"]
    indoor_bias = {"indoors": 0.8, "outdoors": 0.2, "mixed": 0.5}[setting]
    budget_tier = answers["budget"]

    peak = max(scores.values()) or 1.0
    interests = {k: round(v / peak, 3) for k, v in scores.items()}
    top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    keywords = [name for name, value in top if value > 0][:6] + [pace, budget_tier, setting]

    return {
        "interests": interests,
        "pace": pace,
        "indoor_bias": indoor_bias,
        "budget_tier": budget_tier,
        "visit_count": 0,
        "avg_duration_min": 0.0,
        "avg_stars": None,
        "top_categories": {name: round(value, 3) for name, value in top if value > 0},
        "keywords": keywords,
        "source": "quiz",
    }
