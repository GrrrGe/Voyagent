"""Deterministic providers. Identical normalized inputs yield identical outputs."""
from typing import Protocol
from tools.catalog import CITIES

class FlightProvider(Protocol):
    def search(self, trip: dict) -> list[dict]: ...

class HotelProvider(Protocol):
    def search(self, trip: dict) -> list[dict]: ...

class LanguageProvider(Protocol):
    def order(self, trip: dict, count: int) -> list[int]: ...
    def report(self, state: dict) -> str: ...

class MockFlightProvider:
    def search(self, trip):
        fare = CITIES[trip['destination']]['fare']
        return [dict(id=f'flight-{i}', airline=name, number=f'VG{210 + i}',
                     origin=trip['origin_iata'], destination=trip['destination_iata'],
                     departure='09:00', arrival='12:00', return_departure='18:00',
                     stops=i, price_cents=fare + i * 8500, price_source='ESTIMATED',
                     data_source='CURATED', price_basis='Round trip, per person',
                     note='Reference schedule. Times are local. Availability is not checked.')
                for i, name in enumerate(['Voyagent Air', 'Demo Airways'])]

class MockHotelProvider:
    def search(self, trip):
        city = CITIES[trip['destination']]
        return [dict(id=f'hotel-{i}', name=name, area=city['area'],
                     nightly_cents=city['night'] + i * 3500, price_source='ESTIMATED',
                     data_source='CURATED', rooms=(trip['travelers'] + 1) // 2,
                     note='Curated lodging. Two guests per room. Taxes included in estimate.', url=None)
                for i, name in enumerate([city['stay'], f"{city['area']} Courtyard"])]

class MockLanguageProvider:
    def order(self, trip, count):
        return list(range(count))
    def report(self, state):
        trip = state['trip']
        return f"{trip['days']} days in {trip['destination']}. Activities are grouped by area, with time for meals and transfers. Confirm opening hours and reservations before travel."
