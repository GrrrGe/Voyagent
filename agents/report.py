import os
from tools.language_tool import provider, is_live

def money(cents):
    return f'USD {cents / 100:,.2f} MOCK'

def run(state):
    trip, budget = state['trip'], state['budget']
    summary = provider().report(state)
    lines = [f"{trip['destination']}. Your trip plan.", summary,
             f"{trip['origin']} to {trip['destination']} | {trip['start_date']} to {trip['end_date']} | {trip['travelers']} traveler(s)",
             'All costs are MOCK planning estimates, not bookable quotes.',
             'Flights.', f"{state['selected_flight']['airline']}: {money(state['selected_flight']['price_cents'])} per person, round trip.",
             f"{state['selected_flight']['data_source']} flight research. {state['selected_flight']['note']}",
             'Hotels.', f"{state['selected_hotel']['name']}: {money(state['selected_hotel']['nightly_cents'])} per room per night.",
             f"{state['selected_hotel']['data_source']} hotel research. {state['selected_hotel']['note']}",
             'Trip assumptions: destination days, one local area per day, 30 minute minimum gaps. Opening hours and travel dates need confirmation. Visa fees, insurance, and shopping are excluded.', 'Itinerary.']
    for day in state['itinerary']:
        lines.append(f"Day {day['day']}. {day['area']}. {day['date']}.")
        lines.append(day['note'])
        for event in day['events']:
            lines.append(f"{event['start'] // 60:02}:{event['start'] % 60:02} to {event['end'] // 60:02}:{event['end'] % 60:02}: {event['title']}. {money(event['cost_cents'])} per person.")
    lines.append('Budget.')
    lines.extend(f"{item['category']}: {money(item['amount_cents'])}" for item in budget['items'])
    lines.extend([f"Total: {money(budget['total_cents'])}", f"Your budget: USD {budget['limit_cents'] / 100:,.2f}", *state['changes']])
    return {'summary': summary, 'answer': '\n\n'.join(lines), 'complete': True,
            'llm_calls': state['llm_calls'] + (1 if is_live() else 0),
            'trace': state['trace'] + ['Report']}
