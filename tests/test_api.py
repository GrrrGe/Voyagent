from uuid import uuid4
from tests.test_planner import SAMPLE

def test_api_and_thread_isolation(client):
    response = client.post('/api/travel', json={'message': SAMPLE})
    assert response.status_code == 200
    body = response.json()
    thread = body['thread_id']
    assert client.get(f'/api/travel/{thread}').json()['trip'] == body['trip']
    follow = client.post('/api/travel', json={'message': 'Rain on day 2', 'thread_id': thread})
    assert follow.status_code == 200 and follow.json()['disruption']['kind'] == 'rain'
    client.cookies.clear()
    assert client.get(f'/api/travel/{thread}').status_code == 404
    assert client.get(f'/api/travel/{thread}/pdf').status_code == 404

def test_pdf_export(client):
    body = client.post('/api/travel', json={'message': SAMPLE}).json()
    response = client.get(f'/api/travel/{body["thread_id"]}/pdf')
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    assert response.content.startswith(b'%PDF-')
    assert 'attachment' in response.headers['content-disposition']

def test_bad_input_and_origin(client):
    for payload in [{'message': ''}, {'message': 'x' * 2001}, {'message': SAMPLE, 'thread_id': '../test'}]:
        assert client.post('/api/travel', json=payload).status_code == 422
    assert client.post('/api/travel', json={'message': SAMPLE}, headers={'Origin': 'https://elsewhere.example'}).status_code == 403
    assert client.post('/api/travel', content='x' * 17000).status_code == 413
    assert client.get('/health').json()['status'] == 'ok'

def test_request_limits(client):
    for _ in range(20): client.post('/api/travel', json={'message': 'No destination'})
    assert client.post('/api/travel', json={'message': SAMPLE}).status_code == 429

def test_rejected_change_preserves_completed_plan(client):
    first = client.post('/api/travel', json={'message': SAMPLE}).json()
    response = client.post('/api/travel', json={'message': 'Make it 100 days', 'thread_id': first['thread_id']})
    assert response.status_code == 422
    assert client.get(f'/api/travel/{first["thread_id"]}').json()['trip'] == first['trip']

def test_markup_and_static_files(client):
    for path in ['/', '/planner', '/static/style.css', '/static/script.js', '/static/fonts/InterVariable.woff2', '/static/images/tokyo.jpg']:
        response = client.get(path)
        assert response.status_code == 200
        assert 'frame-ancestors' in response.headers['content-security-policy']

def test_invalid_disruption_preserves_plan(client):
    first = client.post('/api/travel', json={'message': SAMPLE}).json()
    response = client.post('/api/travel', json={'message': 'Rain on day 99', 'thread_id': first['thread_id']})
    assert response.status_code == 422
    restored = client.get(f'/api/travel/{first["thread_id"]}').json()
    assert restored['answer'] == first['answer'] and restored['complete']

def test_provider_failure_preserves_plan_and_hides_secrets(client, monkeypatch):
    from tools.mock_providers import MockHotelProvider
    first = client.post('/api/travel', json={'message': SAMPLE}).json()
    def fail(*args):
        raise RuntimeError('private-key-example')
    monkeypatch.setattr(MockHotelProvider, 'search', fail)
    response = client.post('/api/travel', json={'message': 'Make it 5 days', 'thread_id': first['thread_id']})
    assert response.status_code == 502 and 'private-key-example' not in response.text
    assert client.get(f'/api/travel/{first["thread_id"]}').json()['answer'] == first['answer']

def test_openai_health_and_call_count(client, monkeypatch):
    from tools.language_tool import OpenAILanguageProvider
    monkeypatch.setenv('LLM_PROVIDER', 'openai')
    monkeypatch.setattr(OpenAILanguageProvider, 'order', lambda self, trip, count: list(range(count)))
    monkeypatch.setattr(OpenAILanguageProvider, 'report', lambda self, state: 'Seven days in Tokyo. Confirm opening hours before travel.')
    health = client.get('/health').json()
    assert health['providers']['llm'] == 'LIVE' and health['language_provider'] == 'openai'
    result = client.post('/api/travel', json={'message': SAMPLE})
    assert result.status_code == 200
    assert result.json()['llm_calls'] == 2
    assert result.json()['budget']['price_source'] == 'MOCK'
