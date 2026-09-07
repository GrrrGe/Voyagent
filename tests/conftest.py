import os
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

@pytest.fixture(autouse=True)
def mock_mode(monkeypatch):
    for name in ('FLIGHT_PROVIDER', 'HOTEL_PROVIDER', 'LLM_PROVIDER'):
        monkeypatch.setenv(name, 'mock')
    monkeypatch.delenv('DATABASE_URL', raising=False)

@pytest.fixture
def graph():
    from langgraph.checkpoint.memory import InMemorySaver
    from backend import build_graph
    return build_graph(InMemorySaver())

@pytest.fixture
def trip():
    from agents.research import parse_trip
    return parse_trip('7 days in Tokyo from San Francisco under $2500 for 1 traveler on 2030-10-01')

@pytest.fixture
def client(tmp_path, monkeypatch):
    import app as module
    from fastapi.testclient import TestClient
    monkeypatch.setattr(module, 'DATA', tmp_path)
    module.limiter.events.clear()
    with TestClient(module.app) as client:
        yield client
