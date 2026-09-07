import re
from datetime import date, timedelta
from tools.catalog import CITIES, ORIGINS
from tools.flight_tool import provider

def parse_trip(message, previous=None):
    text = message.lower()
    trip = dict(previous or {})
    aliases = {'nyc': 'New York', 'sfo': 'San Francisco', 'yyz': 'Toronto', 'jfk': 'New York'}
    for alias, city in aliases.items():
        text = re.sub(r'\b' + alias + r'\b', city.lower(), text)
    origin = re.search(r'\bfrom\s+([a-z ]+?)(?=\s+(?:to|for|under|with|on|in)\b|[,.;]|$)', text)
    if origin:
        city = next((c for c in ORIGINS if c.lower() == origin[1].strip()), None)
        if not city:
            raise ValueError('Use an origin of San Francisco, New York, Toronto, London, Chennai, Tokyo, Lisbon, or Paris.')
        trip['origin'] = city
    destination = re.search(r'\b(?:to|in|visit)\s+(tokyo|lisbon|paris)\b', text)
    mentioned = [c for c in CITIES if c.lower() in text and c != trip.get('origin')]
    if destination:
        trip['destination'] = destination[1].title()
    elif mentioned:
        trip['destination'] = mentioned[0]
    explicit_destination = re.search(r'\b(?:to|in|visit)\s+([a-z]+)(?:\s+(?:for|trip|on|under|from)\b|\s*$)', text)
    if explicit_destination and explicit_destination[1].title() not in CITIES:
        raise ValueError('Currently supports Tokyo, Lisbon, and Paris. Choose one destination.')
    if 'destination' not in trip:
        raise ValueError('Include Tokyo, Lisbon, or Paris in your trip request.')
    trip.setdefault('origin', 'San Francisco')
    if trip['origin'] == trip['destination']:
        raise ValueError('Choose different origin and destination cities.')
    days = re.search(r'\b(\d+)\s*(?:day|night)s?\b', text)
    if days:
        trip['days'] = int(days[1]) + (1 if 'night' in days[0] else 0)
    trip.setdefault('days', 7)
    people = re.search(r'\b(\d+)\s*(?:traveler|traveller|adult|people|person|guest)s?\b', text)
    if people:
        trip['travelers'] = int(people[1])
    trip.setdefault('travelers', 1)
    if re.search(r'\b(?:eur|cad|inr|gbp|yen|rupees|lakhs?)\b|[€£₹]', text):
        raise ValueError('Use a total budget in USD.')
    amount = re.search(r'(?:\$\s*|\b(?:budget(?:\s+of)?|under)\s*\$?\s*)(\d[\d,]*(?:\.\d{1,2})?)', text)
    if amount:
        from decimal import Decimal
        trip['budget_cents'] = int(Decimal(amount[1].replace(',', '')) * 100)
    trip.setdefault('budget_cents', 250000)
    dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b', text)
    if dates:
        trip['start_date'] = date.fromisoformat(dates[0]).isoformat()
    trip.setdefault('start_date', (date.today() + timedelta(days=30)).isoformat())
    if date.fromisoformat(trip['start_date']) < date.today():
        raise ValueError('Choose a start date today or later.')
    if not 2 <= trip['days'] <= 14:
        raise ValueError('Choose a trip of 2 to 14 days.')
    if not 1 <= trip['travelers'] <= 8:
        raise ValueError('Choose 1 to 8 travelers.')
    if not 10000 <= trip['budget_cents'] <= 10000000:
        raise ValueError('Use a total USD budget from $100 to $100,000.')
    trip.update(origin_iata=ORIGINS[trip['origin']], destination_iata=CITIES[trip['destination']]['airport'], currency='USD')
    trip['end_date'] = (date.fromisoformat(trip['start_date']) + timedelta(days=trip['days'] - 1)).isoformat()
    trip['interests'] = [word for word in ['food', 'art', 'history', 'walking'] if word in text] or trip.get('interests', ['food', 'walking'])
    return trip

def run(state):
    trip = parse_trip(state['message'], state.get('trip'))
    flights = provider().search(trip)
    if not flights:
        raise ValueError('No flight research results. Try another origin or switch the flight provider.')
    return {'trip': trip, 'flight_results': flights, 'trace': ['Flight research'], 'complete': False}
