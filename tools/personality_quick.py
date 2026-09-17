"""Fast travel-style picker: chips plus your own words, zero quiz feeling.

The user taps up to 4 vibe chips and optionally types extra filters in
their own words ("vegetarian food, late nights, no museums"), or skips
everything and hits Generate Plan. All fields are optional; empty input
yields a neutral card that leaves the plan unchanged. Same card schema as
quiz and Takeout, so the embedding and itinerary paths are shared.
"""
import re

VIBES = ["food", "art", "history", "walking", "nature", "shopping", "nightlife"]
PACE_OPTIONS = ["slow", "moderate", "fast"]
BUDGET_OPTIONS = ["budget", "mid", "midplus"]
SETTING_OPTIONS = ["indoors", "outdoors", "mixed"]

_FREE_TEXT_MAP = {
    "food": ["food", "ramen", "sushi", "cafe", "coffee", "restaurant", "eat", "cuisine"],
    "art": ["art", "museum", "gallery", "craft"],
    "history": ["history", "temple", "shrine", "heritage", "historic", "palace"],
    "walking": ["walk", "hike", "stroll", "park", "garden", "viewpoint", "riverside"],
    "nature": ["nature", "beach", "aquarium", "zoo", "garden"],
    "shopping": ["shop", "market", "souk", "mall"],
    "nightlife": ["night", "bar", "club", "fado", "evening"],
}


def quick_spec():
    return {"vibes": VIBES, "pace": PACE_OPTIONS, "budget": BUDGET_OPTIONS,
            "setting": SETTING_OPTIONS,
            "defaults": {"pace": "moderate", "budget": "mid", "setting": "mixed"}}


def parse_quick(payload):
    """Parse a fast style payload into a personality card. Never requires input."""
    if not isinstance(payload, dict):
        raise ValueError("Style payload must be an object.")
    vibes = payload.get("vibes") or []
    if not isinstance(vibes, list):
        raise ValueError("Vibes must be a list.")
    unknown = [v for v in vibes if v not in VIBES]
    if unknown:
        raise ValueError(f"Unknown vibes: {', '.join(unknown)}.")
    if len(vibes) > 4:
        raise ValueError("Pick up to 4 vibes.")
    pace = payload.get("pace") or "moderate"
    budget = payload.get("budget") or "mid"
    setting = payload.get("setting") or "mixed"
    if pace not in PACE_OPTIONS:
        raise ValueError(f"Unknown pace: {pace}.")
    if budget not in BUDGET_OPTIONS:
        raise ValueError(f"Unknown budget: {budget}.")
    if setting not in SETTING_OPTIONS:
        raise ValueError(f"Unknown setting: {setting}.")

    scores = {v: 0.0 for v in VIBES}
    for vibe in vibes:
        scores[vibe] += 1.0

    free_text = payload.get("free_text") or ""
    if not isinstance(free_text, str):
        raise ValueError("free_text must be a string.")
    free_text = " ".join(free_text.split())[:300]
    words = set(re.findall(r"[a-z0-9]+", free_text.lower()))
    for interest, keys in _FREE_TEXT_MAP.items():
        if words & set(keys):
            scores[interest] += 0.5

    peak = max(scores.values()) if scores and max(scores.values()) else 0.0
    interests = {k: round(v / peak, 3) if peak else 0.0 for k, v in scores.items()}
    indoor_bias = {"indoors": 0.8, "outdoors": 0.2, "mixed": 0.5}[setting]
    top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    keywords = [name for name, value in top if value > 0][:4]

    return {
        "interests": interests,
        "pace": pace,
        "indoor_bias": indoor_bias,
        "budget_tier": budget,
        "visit_count": 0,
        "avg_duration_min": 0.0,
        "avg_stars": None,
        "top_categories": {name: round(value, 3) for name, value in top if value > 0},
        "keywords": keywords + ([setting] if keywords else [setting]),
        "extra": free_text,
        "source": "quick",
    }
