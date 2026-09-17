"""User personality -> embedding vector.

Uses the same 256-d space as tools/knowledge.HashEmbeddings so a user vector
can be compared directly with destination area vectors via cosine similarity.
Offline by default; OpenAI embeddings are used only when the server is already
in live mode (same rule as knowledge.embedding_function).
"""
import json
import math
import os
from pathlib import Path

from tools.knowledge import DIMENSIONS, data_directory, embedding_function


def personality_to_text(card):
    """Deterministic text form of a personality card for embedding."""
    interests = card.get("interests", {}) or {}
    ranked = sorted(interests.items(), key=lambda kv: kv[1], reverse=True)
    # Repeat top interests proportionally so the embedding weights them.
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
    text = "traveler who likes " + " ".join(parts)
    return text[:2000]


def embed_personality(card):
    """Embed a personality card -> L2-normalized list[float]."""
    text = personality_to_text(card)
    vector = embedding_function().embed_query(text)
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def users_directory():
    directory = data_directory() / "users"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


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
