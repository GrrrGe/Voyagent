from copy import deepcopy
import re
from agents.itinerary import feasible

def run(state):
    text = state['message'].lower()
    days = deepcopy(state['itinerary'])
    disruption = dict(state.get('disruption') or {})
    if 'clear disruption' in text or 'clear the disruption' in text:
        disruption = {}
    elif any(word in text for word in ['rain', 'delay', 'cancel']):
        match = re.search(r'day\s+(\d+)', text)
        day = int(match[1]) if match else (1 if 'delay' in text or 'cancel' in text else 2)
        if not 1 <= day <= len(days):
            raise ValueError('The disruption day must be within this trip.')
        hours = re.search(r'(\d+)\s*(?:hour|hr)s?', text)
        delay = int(hours[1]) if hours else 4
        if not 1 <= delay <= 24:
            raise ValueError('Use a flight delay of 1 to 24 hours.')
        disruption = {'kind': 'rain' if 'rain' in text else ('cancellation' if 'cancel' in text else 'delay'), 'day': day, 'hours': delay}
    changes = []
    if disruption:
        index = min(disruption['day'], len(days)) - 1
        disruption['day'] = index + 1
        day = days[index]
        if disruption['kind'] == 'rain':
            day['events'] = [dict(start=900 if index == 0 else 600, end=990 if index == 0 else 720,
                                 title=day['indoor_alternative'], indoor=True, cost_cents=1800,
                                 price_source='MOCK', area=day['area'])]
            day['note'] = 'Indoor visit replaces outdoor stops. Check opening hours.'
            changes.append(f"Day {index + 1}: outdoor stops replaced with an indoor visit.")
        else:
            delay = disruption['hours'] * 60 if disruption['kind'] == 'delay' else 24 * 60
            # Preserve trip dates. Remove any activity affected by the travel window.
            for offset in range(index, len(days)):
                threshold = index * 1440 + 900 + delay
                before = len(days[offset]['events'])
                days[offset]['events'] = [e for e in days[offset]['events'] if offset * 1440 + e['start'] >= threshold]
                if len(days[offset]['events']) < before:
                    days[offset]['note'] = 'Activities removed to allow for the changed travel window.'
            changes.append(f"Day {index + 1}: {'flight cancellation' if disruption['kind'] == 'cancellation' else str(disruption['hours']) + ' hour delay'} scenario. Affected activities removed. Contact the carrier to confirm a new flight.")
    assert feasible(days)
    return {'itinerary': days, 'changes': changes, 'disruption': disruption,
            'trace': state['trace'] + ['Disruption replan']}
