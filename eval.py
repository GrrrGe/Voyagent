"""Keyless end-to-end evaluations of the graph, not a live provider benchmark."""
from langgraph.checkpoint.memory import InMemorySaver
from backend import build_graph
from agents.itinerary import feasible
from tools.copy_policy import violations

def main():
    graph = build_graph(InMemorySaver())
    cases = [
        ('tokyo', '7 days in Tokyo from San Francisco under $2500 on 2030-10-01', 7),
        ('lisbon', '5 days in Lisbon from New York under $1800 on 2030-10-01', 5),
        ('paris', '4 days in Paris from Toronto under $1600 on 2030-10-01', 4),
        ('tokyo', 'Rain on day 2', 7),
        ('lisbon', 'A flight cancellation on day 1', 5),
        ('paris', 'Make it 3 days under $1100', 3),
    ]
    for thread, message, days in cases:
        result = graph.invoke({'message': message}, {'configurable': {'thread_id': thread}})
        assert result['complete'] and len(result['trace']) == 6
        assert len(result['itinerary']) == days and feasible(result['itinerary'])
        assert sum(item['amount_cents'] for item in result['budget']['items']) == result['budget']['total_cents']
        assert not violations(result['answer'])
        print(f"PASS {thread}: {message} | USD {result['budget']['total_cents'] / 100:.2f} MOCK")
    print(f'{len(cases)} evaluations passed.')

if __name__ == '__main__':
    main()
