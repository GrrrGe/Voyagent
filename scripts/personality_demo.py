"""Local prototype: Takeout -> personality -> embedding -> HNSW benchmark.

Run:  .venv/bin/python scripts/personality_demo.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

SAMPLE = {
    "visits": [
        {"name": "Ichiran Ramen", "category": "ramen restaurant", "duration_min": 60},
        {"name": "Sushi Dai", "category": "sushi restaurant", "duration_min": 90},
        {"name": "Tokyo National Museum", "category": "museum", "duration_min": 150},
        {"name": "Ueno Park walk", "category": "park walk", "duration_min": 80},
        {"name": "Meiji Jingu Shrine", "category": "shrine", "duration_min": 70},
    ],
    "reviews": [{"place": "Ichiran Ramen", "category": "ramen", "stars": 5, "text": "Best ramen"}],
    "saved": [{"name": "TeamLab Gallery", "category": "gallery"}],
}


def main():
    from tools.personality_takeout import parse_takeout
    from tools.user_embedding import embed_personality, personality_to_text, save_profile
    from tools.user_hnsw import benchmark, hnsw_available

    card = parse_takeout(SAMPLE)
    print("personality card:")
    print(json.dumps(card, indent=2))
    print("\nembedding text:", personality_to_text(card)[:160], "...")

    vector = embed_personality(card)
    print(f"embedding dim={len(vector)} preview={vector[:4]}")
    save_profile("demo-user", card, vector)
    print("saved profile for demo-user")

    result = benchmark(num_users=2000, dim=64, k=10)
    print("\nHNSW benchmark (synthetic 2000 users):")
    print(json.dumps(result, indent=2))
    print(f"\nhnswlib installed: {hnsw_available()} (fallback is brute-force, still exact)")

    # Personalized itinerary through the real graph.
    from langgraph.checkpoint.memory import InMemorySaver
    from backend import build_graph
    graph = build_graph(InMemorySaver())
    state = graph.invoke(
        {"message": "5 days in Tokyo from New York under $1800 on 2030-10-01",
         "personality": card, "user_vec": vector},
        {"configurable": {"thread_id": "demo"}})
    print(f"\nitinerary days={len(state['itinerary'])} grounding={state['grounding']}")
    print("OK - prototype works. Deploy only after pytest -q is green.")


if __name__ == "__main__":
    main()
