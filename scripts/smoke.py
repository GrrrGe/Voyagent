"""HTTP-only smoke, including three trips, continuation, and PDF export."""
import time
import httpx


def main():
    with httpx.Client(base_url='http://127.0.0.1:8000', timeout=30) as client:
        for attempt in range(30):
            try:
                client.get('/health').raise_for_status()
                break
            except httpx.HTTPError:
                if attempt == 29: raise
                time.sleep(1)
        for path in ['/', '/planner', '/static/style.css', '/static/script.js', '/static/images/tokyo.jpg', '/static/images/lisbon.jpg', '/static/images/paris.jpg', '/static/fonts/InterVariable.woff2']:
            client.get(path).raise_for_status()
        for destination, origin, days, budget in [('Tokyo', 'San Francisco', 7, 2500), ('Lisbon', 'New York', 5, 1800), ('Paris', 'Toronto', 4, 1600)]:
            response = client.post('/api/travel', json={'message': f'{days} days in {destination} from {origin} under ${budget}'})
            response.raise_for_status()
            state = response.json()
            thread = state['thread_id']
            assert state['complete'] and len(state['trace']) == 6
            client.get(f'/api/travel/{thread}').raise_for_status()
            changed = client.post('/api/travel', json={'message': 'Rain on day 2', 'thread_id': thread})
            changed.raise_for_status()
            assert changed.json()['itinerary'][1]['events'][0]['indoor']
            pdf = client.get(f'/api/travel/{thread}/pdf')
            pdf.raise_for_status()
            assert pdf.content.startswith(b'%PDF-')
            print(f'{destination}: plan, saved state, rain replan, PDF passed.')

if __name__ == '__main__': main()
