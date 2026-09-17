"""Retrieval benchmark: BM25 vs vector vs hybrid (RRF) vs hybrid + rerank.

Pure Python and offline with no extra dependencies. Runs against a small
built-in destination corpus so results are deterministic on any machine.
Used to justify the retrieval choice the same way tools/user_hnsw.py
justifies brute force over HNSW: measure first, then pick the default.
"""
import hashlib
import math
import re
import time

K1 = 1.5
B = 0.75
RRF_K = 60
DIMENSIONS = 64

# Built-in corpus: short destination blurbs with stable ids.
CORPUS = [
    {"id": "tokyo-asakusa", "text": "Tokyo Japan. Asakusa area. Visit Senso-ji temple. Riverside walk. Museum indoor alternative."},
    {"id": "tokyo-shibuya", "text": "Tokyo Japan. Shibuya area. Meiji Jingu grounds. Crossing walk. Museum indoor alternative."},
    {"id": "tokyo-ueno", "text": "Tokyo Japan. Ueno area. Ueno Park. Market walk. Nature museum indoor alternative."},
    {"id": "lisbon-alfama", "text": "Lisbon Portugal. Alfama area. Lanes walk. Viewpoint. Fado museum indoor alternative."},
    {"id": "lisbon-belem", "text": "Lisbon Portugal. Belem area. Waterfront walk. Monument. Maritime museum indoor alternative."},
    {"id": "paris-marais", "text": "Paris France. Le Marais area. Garden walk. Historic lanes. Museum indoor alternative."},
    {"id": "paris-louvre", "text": "Paris France. Louvre area. Garden walk. Seine riverside. Museum indoor alternative."},
    {"id": "paris-montmartre", "text": "Paris France. Montmartre area. Hill walk. Viewpoint. Museum indoor alternative."},
    {"id": "dubai-marina", "text": "Dubai UAE. Marina area. Beach walk. Waterfront. Museum indoor alternative."},
    {"id": "dubai-deira", "text": "Dubai UAE. Deira area. Souk lanes. Creek walk. Coffee museum indoor alternative."},
    {"id": "tokyo-stay", "text": "Stay in Tokyo in the Asakusa area. Two guests per room. Taxes included in the estimate."},
    {"id": "paris-stay", "text": "Stay in Paris near Canal Saint-Martin. Two guests per room. Taxes included in the estimate."},
]


def tokenize(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def hash_vector(text, dim=DIMENSIONS):
    values = [0.0] * dim
    for word in tokenize(text):
        digest = hashlib.md5(word.encode()).digest()
        values[int.from_bytes(digest[:2], "big") % dim] += 1.0
        values[int.from_bytes(digest[2:4], "big") % dim] += 0.5
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


class BM25:
    """Minimal BM25 over a static corpus."""

    def __init__(self, documents):
        self.documents = list(documents)
        self.tokens = [tokenize(doc) for doc in self.documents]
        self.doc_len = [len(t) for t in self.tokens]
        self.avg_len = sum(self.doc_len) / max(len(self.doc_len), 1) or 1.0
        self.doc_freq = {}
        for toks in self.tokens:
            for term in set(toks):
                self.doc_freq[term] = self.doc_freq.get(term, 0) + 1
        self.count = len(self.documents)

    def scores(self, query):
        terms = tokenize(query)
        out = []
        for toks, length in zip(self.tokens, self.doc_len):
            total = 0.0
            counts = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            for term in terms:
                freq = counts.get(term, 0)
                if not freq:
                    continue
                df = self.doc_freq.get(term, 0)
                idf = math.log(1 + (self.count - df + 0.5) / (df + 0.5))
                denom = freq + K1 * (1 - B + B * length / self.avg_len)
                total += idf * freq * (K1 + 1) / denom
            out.append(total)
        return out


def _order(scores, limit=None):
    ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return ranked[:limit] if limit else ranked


def rrf_fusion(rank_lists, k=RRF_K):
    fused = {}
    for ranks in rank_lists:
        for rank, idx in enumerate(ranks):
            fused[idx] = fused.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(fused, key=lambda idx: fused[idx], reverse=True)


def rerank(query_text, personality, candidate_ids, documents):
    """Second-stage rerank: lexical base plus personality bonus."""
    query_terms = set(tokenize(query_text))
    interests = (personality or {}).get("interests", {}) or {}
    top_interests = {name for name, score in interests.items() if score and score >= 0.5}
    keywords = set((personality or {}).get("keywords", []) or [])
    pace = (personality or {}).get("pace", "moderate")

    scored = []
    for rank, idx in enumerate(candidate_ids):
        base = 1.0 / (rank + 1)
        doc_terms = set(tokenize(documents[idx]))
        overlap = len(query_terms & doc_terms)
        bonus = 0.0
        for term in doc_terms & (top_interests | {k.lower() for k in keywords}):
            bonus += 0.15
            _ = term
        if pace == "fast" and ("walk" in doc_terms or "walking" in doc_terms):
            bonus += 0.05
        if pace == "slow" and ("museum" in doc_terms or "garden" in doc_terms):
            bonus += 0.05
        scored.append((idx, base + 0.1 * overlap + bonus))
    scored.sort(key=lambda kv: kv[1], reverse=True)
    return [idx for idx, _ in scored]


def retrieve_with_mode(query_text, query_vec, documents, doc_vectors, mode="hybrid",
                       personality=None, limit=4):
    """Retrieve doc ids with one of bm25, vector, hybrid, hybrid_reranked."""
    from tools.user_hnsw import cosine_similarity
    bm25 = BM25(documents)
    bm25_scores = bm25.scores(query_text)
    bm25_rank = _order(bm25_scores)

    if query_vec is not None and doc_vectors is not None:
        vec_scores = [cosine_similarity(query_vec, dv) for dv in doc_vectors]
        vec_rank = _order(vec_scores)
    else:
        vec_rank = list(range(len(documents)))

    if mode == "bm25":
        final = bm25_rank
    elif mode == "vector":
        final = vec_rank
    else:
        fused = rrf_fusion([bm25_rank, vec_rank])
        if mode == "hybrid_reranked":
            fused = rerank(query_text, personality, fused, documents)
        final = fused
    return final[:limit]


def _queries():
    texts = [d["text"] for d in CORPUS]
    queries = []
    for i, doc in enumerate(CORPUS):
        if doc["id"].endswith("-stay"):
            continue
        city = doc["text"].split(".")[0]
        area = doc["text"].split(".")[1].strip()
        queries.append({"text": f"{city} {area} areas to visit", "relevant": {i}})
    return texts, queries


def benchmark(limit=4, modes=("bm25", "vector", "hybrid", "hybrid_reranked")):
    """Score each retrieval mode on built-in corpus queries.

    Metrics per mode: recall@limit, MRR, ms per query. Deterministic.
    """
    texts, queries = _queries()
    doc_vectors = [hash_vector(t) for t in texts]

    results = {}
    for mode in modes:
        hits = 0
        reciprocal = 0.0
        start = time.perf_counter()
        for q in queries:
            qvec = hash_vector(q["text"])
            ranked = retrieve_with_mode(q["text"], qvec, texts, doc_vectors,
                                        mode=mode, limit=limit)
            relevant = q["relevant"]
            if any(idx in relevant for idx in ranked):
                hits += 1
            for rank, idx in enumerate(ranked):
                if idx in relevant:
                    reciprocal += 1.0 / (rank + 1)
                    break
        elapsed_ms = (time.perf_counter() - start) / max(len(queries), 1) * 1000
        results[mode] = {
            "recall": round(hits / max(len(queries), 1), 4),
            "mrr": round(reciprocal / max(len(queries), 1), 4),
            "ms_per_query": round(elapsed_ms, 3),
            "queries": len(queries),
        }
    order = sorted(results, key=lambda m: (results[m]["recall"], results[m]["mrr"]),
                   reverse=True)
    return {"limit": limit, "modes": results, "recommended": order[0] if order else "hybrid"}
