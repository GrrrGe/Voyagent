from datetime import date, timedelta
import os
from tools.catalog import CITIES
from tools.language_tool import provider, is_live

def feasible(days):
    for day in days:
        last_end = 0
        for event in day['events']:
            start, end = event['start'], event['end']
            if start < last_end + (30 if last_end else 0) or end <= start or end > 21 * 60 or start < 8 * 60:
                return False
            last_end = end
    return True

def run(state):
    trip = state['trip']
    clusters = CITIES[trip['destination']]['clusters']
    order = provider().order(trip, len(clusters))
    days = []
    for i in range(trip['days']):
        area, place1, place2, indoor = clusters[order[i % len(order)]]
        times = [(900, 990)] if i == 0 else ([(600, 690), (780, 840)] if i == trip['days'] - 1 else [(600, 690), (780, 870), (960, 1050)])
        titles = [place1, place2, indoor]
        events = [dict(start=start, end=end, title=titles[j], indoor=j == 2,
                       cost_cents=1800 if j == 2 else 0, price_source='ESTIMATED', area=area)
                  for j, (start, end) in enumerate(times)]
        if 'art' in trip['interests'] and len(events) > 1:
            events[1].update(title=indoor, indoor=True, cost_cents=1800)
            if len(events) > 2:
                events[2].update(title=place2, indoor=False, cost_cents=0)
        days.append(dict(day=i + 1, date=(date.fromisoformat(trip['start_date']) + timedelta(days=i)).isoformat(),
                         area=area, events=events, indoor_alternative=indoor,
                         note='Arrival and check-in before 15:00.' if i == 0 else ('Leave for the airport after 14:00.' if i == trip['days'] - 1 else 'Meal breaks and at least 30 minutes between stops.')))
    assert feasible(days)
    return {'itinerary': days, 'llm_calls': 1 if is_live() else 0,
            'trace': state['trace'] + ['Itinerary']}
