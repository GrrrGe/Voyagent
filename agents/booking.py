from tools.hotel_tool import provider

def run(state):
    hotels = provider().search(state['trip'])
    if not hotels:
        raise ValueError('No hotel research results. Try another destination or provider.')
    return {'hotel_results': hotels, 'trace': state['trace'] + ['Hotel research']}
