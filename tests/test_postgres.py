"""Runs in CI with PostgreSQL. Skips locally unless TEST_DATABASE_URL is set."""
import os
from uuid import uuid4
import pytest

@pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'), reason='Set TEST_DATABASE_URL for PostgreSQL integration.')
def test_postgres_reconnect():
    from langgraph.checkpoint.postgres import PostgresSaver
    from backend import build_graph
    thread = str(uuid4())
    config = {'configurable': {'thread_id': thread}}
    url = os.environ['TEST_DATABASE_URL']
    with PostgresSaver.from_conn_string(url) as saver:
        saver.setup()
        graph = build_graph(saver)
        graph.invoke({'message': '5 days in Lisbon from New York under $1800 on 2030-10-01'}, config)
    with PostgresSaver.from_conn_string(url) as saver:
        graph = build_graph(saver)
        result = graph.invoke({'message': 'Rain on day 2'}, config)
        assert result['trip']['destination'] == 'Lisbon'
        assert all(event['indoor'] for event in result['itinerary'][1]['events'])
        saver.delete_thread(thread)
