from copy import deepcopy

def calculate(trip, flight, hotel, days):
    people = trip['travelers']
    costs = {
        'Flights': flight['price_cents'] * people,
        'Hotels': hotel['nightly_cents'] * (trip['days'] - 1) * hotel['rooms'],
        'Food': 3500 * trip['days'] * people,
        'Local transport': 1200 * trip['days'] * people,
        'Activities': sum(e['cost_cents'] for d in days for e in d['events']) * people,
    }
    subtotal = sum(costs.values())
    costs['Contingency'] = (subtotal + 9) // 10
    total = sum(costs.values())
    return dict(items=[dict(category=k, amount_cents=v, price_source='MOCK') for k, v in costs.items()],
                total_cents=total, limit_cents=trip['budget_cents'], remaining_cents=trip['budget_cents'] - total,
                price_source='MOCK', currency='USD', within_budget=total <= trip['budget_cents'])

def run(state):
    flight = min(state['flight_results'], key=lambda x: x['price_cents'])
    hotel = min(state['hotel_results'], key=lambda x: x['nightly_cents'])
    days = deepcopy(state['itinerary'])
    budget = calculate(state['trip'], flight, hotel, days)
    changes = list(state['changes'])
    original = budget['total_cents']
    if not budget['within_budget']:
        for day in days:
            for event in day['events']:
                if event['cost_cents']:
                    event.update(title='Self-guided area visit' if not event['indoor'] else 'Indoor rest at your accommodation', cost_cents=0)
        budget = calculate(state['trip'], flight, hotel, days)
        if budget['total_cents'] < original:
            changes.append('Paid visits replaced with no-cost stops to reduce the estimate.')
    budget['savings_cents'] = original - budget['total_cents']
    if not budget['within_budget']:
        changes.append('The estimate exceeds your budget. Consider fewer days or a higher budget. No booking has been made.')
    return {'budget': budget, 'itinerary': days, 'selected_flight': flight, 'selected_hotel': hotel,
            'changes': changes, 'trace': state['trace'] + ['Budget check']}
