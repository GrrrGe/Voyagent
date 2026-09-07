"""Retrieval-grounded trip knowledge over a persistent Chroma vector store.

Destination areas, stays, and visit notes from the catalog are embedded once
and retrieved per trip with LangChain. OpenAI embeddings are used when a
server-side key is configured, otherwise a deterministic hash embedding keeps
local development and tests fully offline.
"""
import hashlib
import math
import os
import re
from pathlib import Path

os.environ.setdefault('ANONYMIZED_TELEMETRY', 'False')

BASE = Path(__file__).resolve().parents[1]
DIMENSIONS = 256


def data_directory():
    directory = Path(os.getenv('DATA_DIR', str(BASE / '.data')))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def use_openai_embeddings():
    return bool(os.getenv('OPENAI_API_KEY')) and os.getenv('LLM_PROVIDER', 'mock') in ('live', 'groq', 'openai')


class HashEmbeddings:
    """Deterministic offline embeddings. Stable across runs without network."""

    def _vector(self, text):
        values = [0.0] * DIMENSIONS
        for word in re.findall(r'[a-z0-9]+', text.lower()):
            digest = hashlib.md5(word.encode()).digest()
            values[int.from_bytes(digest[:2], 'big') % DIMENSIONS] += 1.0
            values[int.from_bytes(digest[2:4], 'big') % DIMENSIONS] += 0.5
        norm = math.sqrt(sum(value * value for value in values)) or 1.0
        return [value / norm for value in values]

    def embed_documents(self, texts):
        return [self._vector(text) for text in texts]

    def embed_query(self, text):
        return self._vector(text)


def embedding_function():
    if use_openai_embeddings():
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=os.getenv('OPENAI_EMBEDDING_MODEL', 'text-embedding-3-small'))
    return HashEmbeddings()


def knowledge_documents():
    from tools.catalog import CITIES
    documents = []
    for city, info in CITIES.items():
        for index, (area, place1, place2, indoor) in enumerate(info['clusters']):
            documents.append({
                'id': f"{city.lower()}-cluster-{index}",
                'text': (f"{city}, {info['country']}. {area} area. Visit {place1}. "
                         f"Visit {place2}. Indoor alternative {indoor}."),
                'metadata': {'city': city, 'area': area, 'kind': 'area', 'index': index},
            })
        documents.append({
            'id': f"{city.lower()}-stay",
            'text': (f"Stay in {city} in the {info['area']} area at {info['stay']}. "
                     f"Two guests per room. Taxes included in the estimate."),
            'metadata': {'city': city, 'area': info['area'], 'kind': 'stay', 'index': -1},
        })
    return documents


_stores = {}


def knowledge_store(persist_directory=None):
    """Shared LangChain Chroma store, seeded from the catalog on first use."""
    from langchain_chroma import Chroma
    directory = str(persist_directory or (data_directory() / 'chroma'))
    key = (directory, use_openai_embeddings())
    if key not in _stores:
        store = Chroma(collection_name='voyagent-knowledge',
                       persist_directory=directory,
                       embedding_function=embedding_function())
        if store._collection.count() == 0:
            from langchain_core.documents import Document
            store.add_documents([
                Document(page_content=item['text'], metadata=item['metadata'], id=item['id'])
                for item in knowledge_documents()
            ])
        _stores[key] = store
    return _stores[key]


def retrieve(trip, limit=4, persist_directory=None):
    """Rank destination areas for a trip with vector search.

    Returns cluster indexes ordered by relevance plus the area names that
    grounded the plan. Falls back to catalog order when the store is empty.
    """
    from tools.catalog import CITIES
    destination = trip.get('destination')
    if destination not in CITIES:
        return {'order': [], 'areas': []}
    interests = ' '.join(trip.get('interests', []))
    query = f"{destination} {interests} areas to visit".strip()
    store = knowledge_store(persist_directory)
    retriever = store.as_retriever(search_kwargs={
        'k': limit, 'filter': {'$and': [{'city': destination}, {'kind': 'area'}]}})
    try:
        matches = retriever.invoke(query)
    except Exception:
        matches = []
    seen, order, areas = set(), [], []
    for match in matches:
        index = (match.metadata or {}).get('index')
        area = (match.metadata or {}).get('area')
        if isinstance(index, int) and index not in seen:
            seen.add(index)
            order.append(index)
            areas.append(area)
    count = len(CITIES[destination]['clusters'])
    order.extend(i for i in range(count) if i not in seen)
    return {'order': order, 'areas': areas}
