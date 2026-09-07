import os
import httpx
from tools.mock_providers import MockFlightProvider
from tools.copy_policy import clean_output

class AviationStackProvider:
    def search(self, trip):
        response = httpx.get('https://api.aviationstack.com/v1/flights',
            params={'access_key': os.environ['AVIATIONSTACK_API_KEY'],
                    'dep_iata': trip['origin_iata'], 'arr_iata': trip['destination_iata'], 'limit': 5}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        if payload.get('error'):
            raise ValueError('Flight provider rejected the request.')
        rows = payload.get('data', [])
        # AviationStack does not sell fares. The budget estimate stays estimated.
        estimate = MockFlightProvider().search(trip)[0]
        return [dict(estimate, id=f'live-flight-{i}',
                     airline=clean_output((row.get('airline') or {}).get('name') or 'Carrier'),
                     number=clean_output((row.get('flight') or {}).get('iata') or 'Schedule'),
                     departure=(row.get('departure') or {}).get('scheduled') or 'Unpublished',
                     arrival=(row.get('arrival') or {}).get('scheduled') or 'Unpublished',
                     data_source='LIVE',
                     note='LIVE recent route research, not date-specific availability. Fare and itinerary timing remain estimated assumptions.')
                for i, row in enumerate(rows[:3])]

def provider():
    return AviationStackProvider() if os.getenv('FLIGHT_PROVIDER', 'mock') == 'live' else MockFlightProvider()
