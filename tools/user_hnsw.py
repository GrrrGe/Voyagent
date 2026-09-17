"""User-similarity search: exact brute-force default + optional HNSW.

Design note (interview story): at Voyagent scale (tens of destination vectors,
one vector per user) exact cosine search is correct and fastest. HNSW is
provided as an explicit, measured alternative behind a threshold, not as the
default path. Chroma (destination knowledge) already uses HNSW internally;
this module makes the user side explicit with hnswlib when installed.

  pip install hnswlib   # optional; module falls back to brute force otherwise.
"""
import math
import random
import time

try:
    import hnswlib  # type: ignore
    _HNSW_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    hnswlib = None
    _HNSW_AVAILABLE = False

HNSW_AVAILABLE = _HNSW_AVAILABLE
DEFAULT_M = 16
DEFAULT_EF_CONSTRUCTION = 200
DEFAULT_EF = 50
# Below this many users brute force wins; above it HNSW is worth considering.
HNSW_THRESHOLD = 10000


def hnsw_available():
    return HNSW_AVAILABLE


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


class BruteForceUserIndex:
    """Exact cosine search. Default for all production paths."""

    def __init__(self):
        self.ids = []
        self.vectors = []

    def __len__(self):
        return len(self.ids)

    def add(self, user_ids, vectors):
        for uid, vec in zip(user_ids, vectors):
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            self.ids.append(uid)
            self.vectors.append([v / norm for v in vec])

    def query(self, vector, k=5):
        scored = [(uid, cosine_similarity(vector, vec))
                  for uid, vec in zip(self.ids, self.vectors)]
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:k]


class HNSWUserIndex:
    """Approximate HNSW search over user vectors (requires hnswlib).

    Falls back to brute force when hnswlib is not installed so imports and
    tests never break on Render free / offline environments.
    """

    def __init__(self, dim, m=DEFAULT_M, ef_construction=DEFAULT_EF_CONSTRUCTION, ef=DEFAULT_EF):
        self.dim = dim
        self.params = {"M": m, "efConstruction": ef_construction, "ef": ef}
        self.ids = []
        self.vectors = []
        self._index = None
        if HNSW_AVAILABLE:
            self._index = hnswlib.Index(space="cosine", dim=dim)
        else:
            self._fallback = BruteForceUserIndex()

    @property
    def backend(self):
        return "hnswlib" if self._index is not None else "brute-force-fallback"

    def __len__(self):
        return len(self.ids)

    def add(self, user_ids, vectors):
        self.ids.extend(list(user_ids))
        self.vectors.extend([list(v) for v in vectors])
        if self._index is None:
            self._fallback.add(user_ids, vectors)
            return
        import numpy as np
        data = np.array(self.vectors, dtype="float32")
        norms = np.linalg.norm(data, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        data = data / norms
        if len(self.ids) == len(vectors):
            self._index.init_index(max_elements=max(len(vectors), 100),
                                   ef_construction=self.params["efConstruction"],
                                   M=self.params["M"])
            self._index.set_ef(self.params["ef"])
            self._index.add_items(data, list(range(len(self.ids))))
        else:  # pragma: no cover - incremental path
            self._index.resize_index(len(self.ids))
            start = len(self.ids) - len(vectors)
            self._index.add_items(data[start:], list(range(start, len(self.ids))))

    def query(self, vector, k=5):
        if self._index is None:
            return self._fallback.query(vector, k=k)
        import numpy as np
        query = np.array(vector, dtype="float32").reshape(1, -1)
        labels, distances = self._index.knn_query(query, k=min(k, len(self.ids)))
        # hnswlib cosine distance = 1 - cosine similarity
        return [(self.ids[int(i)], float(1 - d)) for i, d in zip(labels[0], distances[0])]


def _random_vectors(n, dim, seed=42):
    rng = random.Random(seed)
    vectors = []
    for _ in range(n):
        vec = [rng.gauss(0, 1) for _ in range(dim)]
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        vectors.append([v / norm for v in vec])
    return vectors


def benchmark(num_users=2000, dim=64, k=10, seed=42, num_queries=20):
    """Compare brute-force vs HNSW recall/latency on synthetic users.

    Returns a JSON-serializable dict. When hnswlib is missing, the HNSW side
    reports backend="brute-force-fallback" with recall 1.0 so CI stays green
    while still proving the measurement harness works.
    """
    vectors = _random_vectors(num_users, dim, seed=seed)
    ids = [f"user-{i}" for i in range(num_users)]
    queries = _random_vectors(num_queries, dim, seed=seed + 1)

    brute = BruteForceUserIndex()
    brute.add(ids, vectors)
    start = time.perf_counter()
    expected = [brute.query(q, k=k) for q in queries]
    brute_ms = (time.perf_counter() - start) / max(num_queries, 1) * 1000

    hnsw = HNSWUserIndex(dim=dim)
    hnsw.add(ids, vectors)
    start = time.perf_counter()
    actual = [hnsw.query(q, k=k) for q in queries]
    hnsw_ms = (time.perf_counter() - start) / max(num_queries, 1) * 1000

    recalls = []
    for exp, act in zip(expected, actual):
        exp_set = {uid for uid, _ in exp}
        act_set = {uid for uid, _ in act}
        recalls.append(len(exp_set & act_set) / max(k, 1))
    recall = sum(recalls) / len(recalls) if recalls else 0.0

    return {
        "num_users": num_users,
        "dim": dim,
        "k": k,
        "brute_force_ms_per_query": round(brute_ms, 3),
        "hnsw_ms_per_query": round(hnsw_ms, 3),
        "recall_at_k": round(recall, 4),
        "hnsw_backend": hnsw.backend,
        "hnsw_available": hnsw_available(),
        "hnsw_params": hnsw.params,
        "threshold": HNSW_THRESHOLD,
        "recommendation": ("brute-force" if num_users < HNSW_THRESHOLD or not hnsw_available()
                           else "hnsw"),
    }


def rerank_areas(base_order, area_texts, user_vector, embed_query_fn, alpha=0.3):
    """Blend destination order with user-personality similarity.

    base_order: list[int] cluster indexes from Chroma retrieval.
    area_texts: list[str] indexed by cluster position.
    user_vector: L2-normalized user embedding or None.
    embed_query_fn: callable(text) -> vector (e.g. HashEmbeddings().embed_query).
    alpha: weight of personalization (0 = catalog order only).
    Returns (new_order, scores) where scores align with new_order.
    """
    if not user_vector or alpha <= 0:
        return list(base_order), [1.0 / (rank + 1) for rank in range(len(base_order))]
    scored = []
    for rank, idx in enumerate(base_order):
        base_score = 1.0 / (rank + 1)
        try:
            area_vec = embed_query_fn(area_texts[idx])
        except Exception:
            area_vec = None
        user_score = cosine_similarity(user_vector, area_vec) if area_vec else 0.0
        # Map cosine [-1,1] to [0,1] then blend.
        blended = (1 - alpha) * base_score + alpha * ((user_score + 1) / 2)
        scored.append((idx, blended))
    scored.sort(key=lambda kv: kv[1], reverse=True)
    return [idx for idx, _ in scored], [round(s, 4) for _, s in scored]
