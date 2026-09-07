import httpx
import pytest
from tools.flight_tool import AviationStackProvider
from tools.hotel_tool import TavilyHotelProvider
from tools.language_tool import GroqLanguageProvider
from security import validate_providers


def response(payload):
    return httpx.Response(200, json=payload, request=httpx.Request('GET', 'https://provider.example'))

def test_live_flight_never_claims_live_fare(monkeypatch, trip):
    monkeypatch.setenv('AVIATIONSTACK_API_KEY', 'test')
    monkeypatch.setattr(httpx, 'get', lambda *a, **k: response({'data': [{'airline': {'name': 'Carrier'}, 'flight': {'iata': 'AA10'}, 'departure': {'scheduled': '2030-10-01T09:00'}, 'arrival': {'scheduled': '2030-10-01T12:00'}}]}))
    flight = AviationStackProvider().search(trip)[0]
    assert flight['data_source'] == 'LIVE' and flight['price_source'] == 'ESTIMATED'
    assert flight['price_cents'] == 68000

def test_tavily_is_research_not_verified_rate(monkeypatch, trip):
    monkeypatch.setenv('TAVILY_API_KEY', 'test')
    monkeypatch.setattr(httpx, 'post', lambda *a, **k: response({'results': [{'title': 'Hotel source', 'url': 'https://hotel.example'}]}))
    hotel = TavilyHotelProvider().search(trip)[0]
    assert hotel['data_source'] == 'LIVE' and hotel['price_source'] == 'ESTIMATED'
    assert hotel['url'].startswith('https://')

@pytest.mark.parametrize('result', [{'order': [1, 1]}, {'order': 'wrong'}, {'order': [True, 0]}])
def test_llm_schema_guard(monkeypatch, trip, result):
    monkeypatch.setattr(GroqLanguageProvider, 'call', lambda *a: result)
    with pytest.raises(ValueError): GroqLanguageProvider().order(trip, 2)

def test_llm_copy_guard(monkeypatch):
    monkeypatch.setattr(GroqLanguageProvider, 'call', lambda *a: {'summary': 'Bad\u2014copy'})
    with pytest.raises(ValueError): GroqLanguageProvider().report({'trip': {}, 'changes': []})

def test_live_requires_explicit_flag_and_key(monkeypatch):
    from tools.flight_tool import provider
    from tools.mock_providers import MockFlightProvider
    monkeypatch.setenv('AVIATIONSTACK_API_KEY', 'unused')
    assert isinstance(provider(), MockFlightProvider)
    monkeypatch.setenv('FLIGHT_PROVIDER', 'live')
    monkeypatch.delenv('AVIATIONSTACK_API_KEY')
    with pytest.raises(RuntimeError): validate_providers()

def test_openai_responses_contract(monkeypatch, trip):
    import json
    from tools.language_tool import OpenAILanguageProvider, provider
    monkeypatch.setenv('LLM_PROVIDER', 'openai')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-key')
    monkeypatch.setenv('OPENAI_PROJECT_ID', 'proj_test')
    captured = []
    def send(url, **kwargs):
        captured.append((url, kwargs))
        name = kwargs['json']['text']['format']['name']
        output = {'order': [0, 1]} if name == 'travel_itinerary' else {'summary': 'Two days in Tokyo. Check opening hours before travel.'}
        return response({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(output)}]}]})
    monkeypatch.setattr(httpx, 'post', send)
    assert isinstance(provider(), OpenAILanguageProvider)
    validate_providers()
    assert provider().order(trip, 2) == [0, 1]
    assert provider().report({'trip': trip, 'changes': []}).startswith('Two days')
    url, kwargs = captured[0]
    assert url == 'https://api.openai.com/v1/responses'
    assert kwargs['headers']['OpenAI-Project'] == 'proj_test'
    assert kwargs['json']['store'] is False
    assert kwargs['json']['text']['format']['strict'] is True
    assert kwargs['json']['max_output_tokens'] == 800

@pytest.mark.parametrize('payload', [{'status': 'incomplete'}, {'status': 'completed', 'output': []}, {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'No'}]}]}])
def test_openai_refusal_and_truncation(monkeypatch, trip, payload):
    from tools.language_tool import OpenAILanguageProvider
    monkeypatch.setenv('OPENAI_API_KEY', 'test-only-key')
    monkeypatch.setattr(httpx, 'post', lambda *a, **k: response(payload))
    with pytest.raises(ValueError): OpenAILanguageProvider().order(trip, 2)

def test_openai_requires_key(monkeypatch):
    monkeypatch.setenv('LLM_PROVIDER', 'openai')
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(RuntimeError, match='OPENAI_API_KEY'): validate_providers()
