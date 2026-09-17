"""Original six-agent StateGraph with a durable checkpointer per conversation."""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from agents import research, booking, itinerary, disruption, budget_agent, report

class TravelState(TypedDict, total=False):
    message: str
    user_id: str
    personality: dict
    user_vec: list
    trip: dict
    flight_results: list
    hotel_results: list
    itinerary: list
    selected_flight: dict
    selected_hotel: dict
    budget: dict
    disruption: dict
    grounding: list
    changes: list
    summary: str
    answer: str
    llm_calls: int
    trace: list
    complete: bool

def build_graph(checkpointer):
    graph = StateGraph(TravelState)
    nodes = [('research', research.run), ('booking', booking.run), ('itinerary_agent', itinerary.run),
             ('disruption_agent', disruption.run), ('budget_agent', budget_agent.run), ('report_agent', report.run)]
    previous = START
    for name, fn in nodes:
        graph.add_node(name, fn)
        graph.add_edge(previous, name)
        previous = name
    graph.add_edge(previous, END)
    return graph.compile(checkpointer=checkpointer)
