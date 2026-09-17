import os
import certifi
from dotenv import load_dotenv
load_dotenv()


os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

from typing import TypedDict, Annotated
import operator
import threading
import uuid

import psycopg
from psycopg.rows import dict_row

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)
from langchain_groq import ChatGroq
from tools.tavily_tool import hotel_search
from tools.flight_tool import search_flights


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise ValueError(
            "DATABASE_URL is missing. Please add your Neon PostgreSQL connection string to .env"
        )

    if "sslmode=" not in database_url:
        separator = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{separator}sslmode=require"

    return database_url

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY is missing. Please add it to your .env file.")


# =========================
# LLM
# =========================

llm = ChatGroq(
    model="openai/gpt-oss-120b",  
    api_key=GROQ_API_KEY
)


# =========================
# State
# =========================

class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    travel_style: str
    flight_results: str
    hotel_results: str
    itinerary: str
    llm_calls: int


def flight_agent(state: TravelState):
    query = state["user_query"]
    flight_data = search_flights(query)

    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(content="Flight results fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


def hotel_agent(state: TravelState):
    hotel_results = hotel_search(state['user_query'])

    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Hotel information fetched.")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }


def itinerary_agent(state: TravelState):
    style = (state.get("travel_style") or "").strip()
    style_block = f"\nTraveler Style:\n{style}\n" if style else ""
    prompt = f"""
Create a complete travel itinerary.

User Query:
{state['user_query']}
{style_block}
Flight Results:
{state['flight_results']}

Hotel Results:
{state['hotel_results']}

Make the itinerary practical, budget-aware, and easy to follow.
Shape activity choices to the traveler style when one is given.
"""

    response = llm.invoke([
        SystemMessage(content="You are an expert travel planner."),
        HumanMessage(content=prompt)
    ])

    return {
        "itinerary": response.content,
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }



def final_agent(state: TravelState):
    style = (state.get("travel_style") or "").strip()
    style_block = f"\nTraveler Style:\n{style}\n" if style else ""
    final_prompt = f"""
Generate the final travel response for the user.

User Request:
{state['user_query']}
{style_block}
Flights:
{state['flight_results']}

Hotels:
{state['hotel_results']}

Itinerary:
{state['itinerary']}

Format the final answer beautifully using these sections:

1. Trip Summary
2. Flight Information
3. Hotel Suggestions
4. Day-by-Day Itinerary
5. Estimated Budget
6. Final Recommendations

Important:
- Be clear and practical.
- Use Canadian dollars (CAD) for all prices, fares, and budget figures unless the user explicitly requests another currency.
- Never narrate data problems, API limitations, or mismatches in the flight or hotel research. If no usable live data was returned for a section, write at most one short line pointing the reader to check a booking engine for current options, then continue with the rest of the plan.
- Keep the response useful for real travel planning.
"""

    response = llm.invoke([
        SystemMessage(content="You are a professional AI travel booking assistant."),
        HumanMessage(content=final_prompt)
    ])

    return {
        "messages": [response],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)


# =========================
# PostgreSQL Checkpointer
# =========================
DATABASE_URL = get_database_url()

_conn = None
travel_graph = None
_graph_lock = threading.Lock()


def _connect():
    """Open a fresh connection and compile the graph against it."""
    global _conn, travel_graph
    conn = psycopg.connect(
        DATABASE_URL,
        autocommit=True,
        row_factory=dict_row,
    )
    checkpointer = PostgresSaver(conn)
    checkpointer.setup()
    _conn = conn
    travel_graph = graph.compile(checkpointer=checkpointer)


def ensure_graph():
    """Return a working graph, reconnecting when Postgres closed the link.

    Free-tier databases sleep and drop idle connections ("the connection
    is closed"). Without this, the first idle timeout permanently breaks
    every request until the next redeploy.
    """
    with _graph_lock:
        needs_reconnect = _conn is None or travel_graph is None
        if not needs_reconnect:
            try:
                if _conn.closed:
                    needs_reconnect = True
                else:
                    _conn.execute("SELECT 1")
            except Exception:
                needs_reconnect = True
        if needs_reconnect:
            try:
                if _conn is not None:
                    _conn.close()
            except Exception:
                pass
            _connect()
        return travel_graph


_connect()



def run_travel_agent(user_input: str, thread_id: str | None = None,
                     travel_style: str | None = None):
    if not thread_id:
        thread_id = f"user_{uuid.uuid4().hex}"

    config = {"configurable": {"thread_id": thread_id}}

    graph_handle = ensure_graph()
    payload = {"messages": [HumanMessage(content=user_input)],"user_query": user_input,"travel_style": travel_style or "","flight_results": "","hotel_results": "","itinerary": "","llm_calls": 0}
    try:
        result = graph_handle.invoke(payload, config=config)
    except Exception:
        # The link may have dropped between the health check and the
        # invoke; reconnect once and retry before giving up.
        graph_handle = ensure_graph()
        result = graph_handle.invoke(payload, config=config)

    final_answer = result["messages"][-1].content

    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": result.get("llm_calls", 0),
    }

