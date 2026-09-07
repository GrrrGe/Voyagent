import os
import httpx
from tools.copy_policy import clean_output
from tools.mock_providers import MockHotelProvider

class TavilyHotelProvider:
    def search(self, trip):
        response = httpx.post('https://api.tavily.com/search',
            headers={'Authorization': f"Bearer {os.environ['TAVILY_API_KEY']}"},
            json={'query': f"Hotels in {trip['destination']} {trip['start_date']} {trip['days'] - 1} nights official hotel website", 'max_results': 3}, timeout=20)
        response.raise_for_status()
        rows = response.json().get('results', [])
        estimate = MockHotelProvider().search(trip)[0]
        return [dict(estimate, id=f'live-hotel-{i}', name=clean_output(row['title'])[:120],
                     data_source='LIVE', url=row.get('url'),
                     note='LIVE web research. Nightly cost is an estimated allowance. Rooms and rates are not verified.')
                for i, row in enumerate(rows)]

def provider():
    return TavilyHotelProvider() if os.getenv('HOTEL_PROVIDER', 'mock') == 'live' else MockHotelProvider()
