"""Local Google Maps Takeout parser -> traveler personality card.

Accepts a deserialized Takeout payload (dict) and returns a deterministic,
human-readable personality card. Fully offline: no network, no LLM.

Supported inputs (all optional, combined when present):
  - "visits": [{name, category, duration_min, rating}]
  - "reviews": [{place, category, stars, text}]
  - "saved": [{name, category}]
  - "timelineObjects": legacy Location History objects with placeVisit
  - "semanticSegments": new Timeline format with visit segments

Example:
    card = parse_takeout(json.load(open("takeout.json")))
    # card["interests"]["food"] -> 0.0..1.0
"""

CATEGORY_TO_INTEREST = {
    # food
    "restaurant": "food", "ramen": "food", "sushi": "food", "cafe": "food",
    "coffee": "food", "bakery": "food", "bar": "food", "izakaya": "food",
    "street food": "food", "market": "food",
    # art
    "museum": "art", "gallery": "art", "exhibition": "art", "craft": "art",
    # history
    "temple": "history", "shrine": "history", "historic": "history",
    "heritage": "history", "monument": "history", "palace": "history",
    # walking / outdoors
    "park": "walking", "garden": "walking", "riverside": "walking",
    "viewpoint": "walking", "trail": "walking", "walk": "walking",
    "beach": "walking", "waterfront": "walking",
    # nature
    "nature": "nature", "zoo": "nature", "aquarium": "nature",
    # shopping / nightlife
    "shopping": "shopping", "souk": "shopping", "mall": "shopping",
    "nightlife": "nightlife", "club": "nightlife", "fado": "nightlife",
}

INTERESTS = ["food", "art", "history", "walking", "nature", "shopping", "nightlife"]

INDOOR_CATEGORIES = {"museum", "gallery", "exhibition", "aquarium", "mall", "craft"}
OUTDOOR_CATEGORIES = {"park", "garden", "trail", "beach", "viewpoint", "walk", "waterfront", "riverside"}


def _normalize_category(raw):
    text = (raw or "").lower()
    for key, interest in CATEGORY_TO_INTEREST.items():
        if key in text:
            return interest, key
    return None, text[:48]


def _extract_visits(payload):
    """Collect uniform visit dicts from all supported Takeout shapes."""
    visits = []

    for item in payload.get("visits", []) or []:
        visits.append({
            "name": item.get("name", "unknown"),
            "category": (item.get("category") or "unknown"),
            "duration_min": float(item.get("duration_min") or 60),
            "rating": item.get("rating"),
        })

    for item in payload.get("saved", []) or []:
        visits.append({
            "name": item.get("name", "unknown"),
            "category": (item.get("category") or "unknown"),
            "duration_min": 60.0,
            "rating": None,
            "saved_only": True,
        })

    for item in payload.get("reviews", []) or []:
        visits.append({
            "name": item.get("place", "unknown"),
            "category": (item.get("category") or "unknown"),
            "duration_min": 60.0,
            "rating": item.get("stars"),
            "review_text": item.get("text", ""),
        })

    # Legacy Location History: {"timelineObjects": [{"placeVisit": {...}}]}
    for obj in payload.get("timelineObjects", []) or []:
        visit = obj.get("placeVisit") or {}
        loc = visit.get("location") or {}
        name = loc.get("name") or loc.get("address") or "unknown"
        duration = visit.get("duration") or {}
        # duration like {"startTimestamp": "...", "endTimestamp": "..."} without minutes;
        # fall back to 60 min when unparseable.
        visits.append({"name": name, "category": "unknown",
                       "duration_min": 60.0, "rating": None})

    # New Timeline: {"semanticSegments": [{"visit": {...}}]}
    for seg in payload.get("semanticSegments", []) or []:
        visit = seg.get("visit") or {}
        name = visit.get("locationName") or visit.get("placeId") or "unknown"
        # hikeProbability / visitDuration sometimes present
        duration_min = 60.0
        raw_dur = visit.get("visitDuration") or visit.get("duration") or ""
        if isinstance(raw_dur, (int, float)):
            duration_min = float(raw_dur) / 60.0 if raw_dur > 1000 else float(raw_dur)
        visits.append({"name": name, "category": "unknown",
                       "duration_min": duration_min, "rating": None})

    return visits


def parse_takeout(payload):
    """Build a personality card from a Takeout payload dict."""
    if not isinstance(payload, dict):
        raise ValueError("Takeout payload must be a JSON object.")
    visits = _extract_visits(payload)

    scores = {interest: 0.0 for interest in INTERESTS}
    weights = {interest: 0.0 for interest in INTERESTS}
    top_categories = {}
    indoor_hits = 0
    outdoor_hits = 0
    total_duration = 0.0
    stars = []

    for visit in visits:
        interest, cat_key = _normalize_category(visit.get("category"))
        name_interest, _ = _normalize_category(visit.get("name"))
        chosen = interest or name_interest
        weight = 1.0
        # Saved-only places count less than actual visits; reviews count more.
        if visit.get("saved_only"):
            weight = 0.5
        if visit.get("review_text") or visit.get("rating") is not None:
            weight = 1.5
        if chosen:
            scores[chosen] += weight
            weights[chosen] += weight
        top_categories[cat_key] = top_categories.get(cat_key, 0) + weight
        cat_lower = (visit.get("category") or "").lower()
        if any(k in cat_lower for k in INDOOR_CATEGORIES):
            indoor_hits += 1
        if any(k in cat_lower for k in OUTDOOR_CATEGORIES):
            outdoor_hits += 1
        total_duration += float(visit.get("duration_min") or 0)
        rating = visit.get("rating")
        if isinstance(rating, (int, float)) and not isinstance(rating, bool):
            stars.append(float(rating))

    # Normalize interest scores to 0..1 by max.
    peak = max(scores.values()) if scores else 0.0
    interests = {k: (round(v / peak, 3) if peak else 0.0) for k, v in scores.items()}

    # Pace: visits per active day heuristic. Takeout payloads rarely include day
    # counts, so estimate from total visits: >60 fast, >25 moderate, else slow.
    count = len(visits)
    if count >= 60:
        pace = "fast"
    elif count >= 25:
        pace = "moderate"
    else:
        pace = "slow"

    total_votes = indoor_hits + outdoor_hits
    indoor_bias = round(indoor_hits / total_votes, 3) if total_votes else 0.5

    avg_stars = round(sum(stars) / len(stars), 2) if stars else None
    # Budget tier heuristic from review stars: generous raters skew midplus.
    if avg_stars is None:
        budget_tier = "mid"
    elif avg_stars >= 4.5:
        budget_tier = "midplus"
    elif avg_stars <= 3.5:
        budget_tier = "budget"
    else:
        budget_tier = "mid"

    ranked = sorted(top_categories.items(), key=lambda kv: kv[1], reverse=True)
    keywords = [name for name, _ in ranked[:12]]

    return {
        "interests": interests,
        "pace": pace,
        "indoor_bias": indoor_bias,
        "budget_tier": budget_tier,
        "visit_count": count,
        "avg_duration_min": round(total_duration / count, 1) if count else 0.0,
        "avg_stars": avg_stars,
        "top_categories": dict(ranked[:12]),
        "keywords": keywords,
    }
