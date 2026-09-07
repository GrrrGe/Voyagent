import tools.knowledge as knowledge
from tools.catalog import CITIES


def test_index_builds_from_catalog(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('LLM_PROVIDER', 'mock')
    store = knowledge.knowledge_store(tmp_path / 'chroma')
    expected = sum(len(info['clusters']) + 1 for info in CITIES.values())
    assert store._collection.count() == expected


def test_retrieve_is_city_filtered_and_deterministic(tmp_path, monkeypatch, trip):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.setenv('LLM_PROVIDER', 'mock')
    persist = tmp_path / 'chroma'
    first = knowledge.retrieve(trip, persist_directory=persist)
    second = knowledge.retrieve(trip, persist_directory=persist)
    assert first == second
    count = len(CITIES['Tokyo']['clusters'])
    assert sorted(first['order']) == list(range(count))
    assert first['areas']
    assert len(first['areas']) <= 4


def test_retrieve_unknown_destination(tmp_path):
    result = knowledge.retrieve({'destination': 'Rome', 'interests': []}, persist_directory=tmp_path / 'chroma')
    assert result == {'order': [], 'areas': []}


def test_graph_grounding_reaches_report(graph):
    from tests.test_planner import SAMPLE
    state = graph.invoke({'message': SAMPLE}, {'configurable': {'thread_id': 'grounding'}})
    assert state['grounding']
    assert 'Retrieved areas:' in state['answer']
