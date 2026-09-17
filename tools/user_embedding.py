"""User personality -> embedding vector.

Self-contained deterministic hash embedding (256-d, L2-normalized), so a
user vector can be compared with cosine similarity without any network
calls, API keys, or extra dependencies. Same card schema as the quiz,
quick picker, and Takeout parser.
"""
import hashlib
import json
import math
import os
import re
from pathlib import Path

DIMENSIONS = 256


def _base_dir():
    return Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parents[1] / ".data")))


def users_directory():
    directory = _base_dir() / "users"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _hash_vector(text):
    values = [0.0] * DIMENSIONS
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.md5(word.encode()).digest()
        values[int.from_bytes(digest[:2], "big") % DIMENSIONS] += 1.0
        values[int.from_bytes(digest[2:4], "big") % DIMENSIONS] += 0.5
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def personality_to_text(card):
    """Deterministic text form of a personality card for embedding."""
    interests = card.get("interests", {}) or {}
    ranked = sorted(interests.items(), key=lambda kv: kv[1], reverse=True)
    parts = []
    for name, score in ranked:
        repeats = 1 + int(round(score * 3))
        parts.extend([name] * repeats)
    keywords = card.get("top_categories", {}) or {}
    parts.extend(list(keywords.keys())[:8])
    parts.append(f"pace {card.get('pace', 'moderate')}")
    parts.append(f"budget {card.get('budget_tier', 'mid')}")
    indoor = card.get("indoor_bias", 0.5)
    parts.append("indoor" if indoor is not None and indoor > 0.6 else
                 "outdoor" if indoor is not None and indoor < 0.4 else "mixed indoor outdoor")
    extra = (card.get("extra") or "").strip()
    if extra:
        parts.append(extra)
    text = "traveler who likes " + " ".join(parts)
    return text[:2000]


def embed_personality(card):
    """Embed a personality card -> L2-normalized list[float]."""
    return _hash_vector(personality_to_text(card))


def style_line(card):
    """One-line traveler style summary for LLM prompt context."""
    interests = card.get("interests", {}) or {}
    top = [name for name, score in sorted(interests.items(), key=lambda kv: kv[1],
                                          reverse=True) if score and score >= 0.5][:3]
    bits = []
    if top:
        bits.append("enjoys " + ", ".join(top))
    bits.append(f"{card.get('pace', 'moderate')} pace")
    bits.append(f"{card.get('budget_tier', 'mid')} spend")
    setting = "indoor" if (card.get("indoor_bias", 0.5) or 0.5) > 0.6 else (
        "outdoor" if (card.get("indoor_bias", 0.5) or 0.5) < 0.4 else "mixed indoor/outdoor")
    bits.append(f"prefers {setting}")
    extra = (card.get("extra") or "").strip()
    if extra:
        bits.append(f"extra filters: {extra}")
    return "Traveler style: " + "; ".join(bits) + "."


def save_profile(user_id, card, vector=None):
    """Persist a user personality profile locally."""
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(user_id))[:64] or "anon"
    path = users_directory() / f"{safe}.json"
    payload = {"user_id": str(user_id), "card": card,
               "vector": vector if vector is not None else embed_personality(card),
               "dim": DIMENSIONS}
    path.write_text(json.dumps(payload, indent=2))
    return path


def load_profile(user_id):
    """Load a saved profile; returns None when missing."""
    safe = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(user_id))[:64] or "anon"
    path = users_directory() / f"{safe}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())
