from copy import deepcopy
import pytest
from agents.itinerary import feasible
from agents.budget_agent import calculate
from agents.research import parse_trip
from tools.mock_providers import MockFlightProvider, MockHotelProvider, MockLanguageProvider

SAMPLE = '7 days in Tokyo from San Francisco under $2500 for 1 traveler on 2030-10-01'

def run(graph, message=SAMPLE, thread='test'):
    return graph.invoke({'message': message, 'complete': False}, {'configurable': {'thread_id': thread}})

@pytest.mark.parametrize('destination,origin,days,budget', [('Tokyo', 'San Francisco', 7, 2500), ('Lisbon', 'New York', 5, 1800), ('Paris', 'Toronto', 4, 1600)])
def test_complete_keyless_trip(graph, destination, origin, days, budget):
    state = run(graph, f'{days} days in {destination} from {origin} under ${budget} on 2030-10-01')
    assert state['complete'] and len(state['trace']) == 6
    assert len(state['itinerary']) == days
    assert state['llm_calls'] == 0
    assert feasible(state['itinerary'])
    assert state['itinerary'][0]['events'][0]['start'] >= 900
    assert state['itinerary'][-1]['events'][-1]['end'] <= 840
    assert state['budget']['price_source'] == 'MOCK'
    assert 'MOCK' in state['answer']

def test_budget_math_and_room_rounding(trip):
    trip['travelers'] = 3
    flights, hotels = MockFlightProvider().search(trip), MockHotelProvider().search(trip)
    assert hotels[0]['rooms'] == 2
    days = [{'events': [{'cost_cents': 1800}]}]
    budget = calculate(trip, flights[0], hotels[0], days)
    expected = 68000 * 3 + 11200 * 6 * 2 + 3500 * 7 * 3 + 1200 * 7 * 3 + 1800 * 3
    assert budget['total_cents'] == expected + (expected + 9) // 10
    assert sum(item['amount_cents'] for item in budget['items']) == budget['total_cents']
    assert budget['remaining_cents'] == 250000 - budget['total_cents']

def test_known_tokyo_total(graph):
    assert run(graph)['budget']['total_cents'] == 194810

def test_continuation_preserves_details(graph):
    first = run(graph)
    second = run(graph, 'Make it 5 days under $1800')
    assert second['trip']['days'] == 5 and second['trip']['budget_cents'] == 180000
    for field in ('origin', 'destination', 'travelers', 'start_date'):
        assert first['trip'][field] == second['trip'][field]
    assert len(second['itinerary']) == 5

def test_rain_replan_and_clear(graph):
    first = run(graph)
    rain = run(graph, 'Rain on day 2')
    assert all(event['indoor'] for event in rain['itinerary'][1]['events'])
    assert len(rain['itinerary'][1]['events']) == 1
    assert rain['changes'] and feasible(rain['itinerary'])
    assert rain['itinerary'][0] == first['itinerary'][0]
    follow = run(graph, 'Budget $2200')
    assert follow['disruption']['kind'] == 'rain'
    cleared = run(graph, 'Clear disruption')
    assert not cleared['disruption'] and cleared['itinerary'][1] == first['itinerary'][1]

@pytest.mark.parametrize('message', ['Flight delay of 4 hours on day 1', 'Flight cancellation on day 1', 'Flight delay of 24 hours on day 1'])
def test_disruption_removes_infeasible_visits(graph, message):
    first = run(graph)
    second = run(graph, message)
    assert second['itinerary'][0]['events'] == []
    assert feasible(second['itinerary']) and second['changes']
    assert second['budget']['total_cents'] <= first['budget']['total_cents']
    assert second['trip']['days'] == first['trip']['days']

def test_low_budget_is_honest(graph):
    state = run(graph, '7 days in Tokyo under $100 on 2030-10-01')
    assert not state['budget']['within_budget']
    assert state['budget']['remaining_cents'] < 0
    assert state['budget']['savings_cents'] > 0
    assert all(e['cost_cents'] == 0 for d in state['itinerary'] for e in d['events'])
    assert any('exceeds' in c for c in state['changes'])

@pytest.mark.parametrize('message', ['0 days in Tokyo', '30 days in Tokyo', 'Tokyo for 9 travelers', 'Tokyo under $20', 'Paris from Mars', 'Trip to Rome', 'Tokyo under 2000 EUR', 'Tokyo on 2020-01-01'])
def test_invalid_requests(message):
    with pytest.raises(ValueError): parse_trip(message)

def test_feasibility_detects_overlap():
    assert not feasible([{'events': [{'start': 600, 'end': 700}, {'start': 710, 'end': 800}]}])
    assert not feasible([{'events': [{'start': 1200, 'end': 1300}]}])

def test_mock_provider_contracts(trip):
    for provider, price_key in [(MockFlightProvider(), 'price_cents'), (MockHotelProvider(), 'nightly_cents')]:
        result = provider.search(trip)
        assert result == provider.search(deepcopy(trip))
        assert len({item['id'] for item in result}) == len(result)
        for item in result:
            assert type(item[price_key]) is int and item[price_key] > 0
            assert item['price_source'] == item['data_source'] == 'MOCK'
    assert MockLanguageProvider().order(trip, 3) == [0, 1, 2]

def test_sqlite_checkpoint_survives_reopen(tmp_path):
    from langgraph.checkpoint.sqlite import SqliteSaver
    from backend import build_graph
    path = str(tmp_path / 'checkpoint.db')
    with SqliteSaver.from_conn_string(path) as saver:
        run(build_graph(saver))
    with SqliteSaver.from_conn_string(path) as saver:
        state = run(build_graph(saver), 'Make it 4 days')
        assert state['trip']['destination'] == 'Tokyo'
        assert state['trip']['days'] == 4

def test_art_preferences_do_not_duplicate_visits(graph):
    state = run(graph, '4 days in Paris from Toronto under $1600 with art and history on 2030-10-01')
    for day in state['itinerary']:
        titles = [event['title'] for event in day['events']]
        assert len(titles) == len(set(titles))
    assert state['budget']['total_cents'] == 127270
