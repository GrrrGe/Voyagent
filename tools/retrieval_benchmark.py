"""Retrieval benchmark: BM25 vs vector vs hybrid (RRF) vs hybrid + rerank.

Pure Python and offline. Used to justify the retrieval choice in the same
way as tools/user_hnsw.py justifies brute force over HNSW: measure first,
then pick the default. Corpus defaults to the real catalog documents from
tools/knowledge.py so results reflect the app instead of toy data.
"""
import math
import re
import time

K1 = 1.5
B = 0.75
RRF_K = 60


def tokenize(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


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
    """Second-stage rerank: lexical base plus personality bonus.

    Keeps the same card schema as quiz and Takeout profiles. Docs whose
    text mentions a top interest or keyword move up; pace adjusts the
    weight of walking-heavy areas.
    """
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
                       personality=None, limit=4, embed_query_fn=None,
                       vector_weight=0.5):
    """Retrieve doc ids with one of bm25, vector, hybrid, hybrid_reranked."""
    from tools.user_hnsw import cosine_similarity
    bm25 = BM25(documents)
    bm25_scores = bm25.scores(query_text)
    bm25_rank = _order(bm25_scores)

    if query_vec is not None and doc_vectors is not None:
        vec_scores = [cosine_similarity(query_vec, dv) for dv in doc_vectors]
        vec_rank = _order(vec_scores)
    elif embed_query_fn is not None:
        vec_scores = [cosine_similarity(embed_query_fn(query_text), embed_query_fn(d))
                      for d in documents]
        vec_rank = _order(vec_scores)
    else:
        vec_scores = [0.0] * len(documents)
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


def _catalog_corpus():
    from tools.knowledge import knowledge_documents
    docs = knowledge_documents()
    texts = [d["text"] for d in docs]
    return docs, texts


def _synthetic_queries(docs, per_city=3):
    """Queries with known relevant docs: city plus area name."""
    queries = []
    by_city = {}
    for i, doc in enumerate(docs):
        by_city.setdefault(doc["metadata"].get("city", ""), []).append((i, doc))
    for city, items in by_city.items():
        for i, doc in items[:per_city]:
            area = doc["metadata"].get("area", "")
            query = f"{city} {area} areas to visit"
            queries.append({"text": query, "relevant": {i}})
    return queries


def benchmark(limit=4, modes=("bm25", "vector", "hybrid", "hybrid_reranked")):
    """Score each retrieval mode on catalog queries.

    Metrics per mode: recall@limit, MRR, ms per query. Deterministic and
    offline using HashEmbeddings vectors.
    """
    from tools.knowledge import HashEmbeddings
    docs, texts = _catalog_corpus()
    queries = _synthetic_queries(docs)
    embed = HashEmbeddings()
    doc_vectors = embed.embed_documents(texts)

    results = {}
    for mode in modes:
        hits = 0
        reciprocal = 0.0
        start = time.perf_counter()
        for q in queries:
            qvec = embed.embed_query(q["text"])
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
