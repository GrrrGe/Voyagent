# 🧭 Voyagent — AI Multi-Agent Travel Planner

**Live demo:** https://voyagent-live.onrender.com/

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-1C3C3C)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon-4169E1?logo=postgresql&logoColor=white)
![Groq](https://img.shields.io/badge/LLM-Groq%20Llama%203.3-F55036)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

Voyagent is an AI travel planner built on a **LangGraph multi-agent pipeline**. You describe a trip in plain language — destination, days, budget — and four specialized agents run in sequence to search live flights, find hotels, build a day-by-day itinerary, and compile it all into one final, ready-to-read travel plan.

> ⚠️ Live flight data (via AviationStack) reflects flight status/schedules, not ticket prices. Use it for route/schedule research, not fare booking.

---

## Table of contents

- [Overview](#overview)
- [Tech stack](#tech-stack)
- [Architecture](#architecture)
- [End-to-end request flow](#end-to-end-request-flow)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Environment variables](#environment-variables)
- [API reference](#api-reference)
- [Running with Docker](#running-with-docker)
- [Conversation memory / checkpointing](#conversation-memory--checkpointing)
- [Roadmap](#roadmap)

---

## Overview

| | |
|---|---|
| **Input** | A free-text travel request, e.g. *"Plan a complete 7 day Japan trip from Toronto under CAD 2,500"* |
| **Output** | A formatted trip summary — flights, hotel suggestions, day-by-day itinerary, estimated budget |
| **Orchestration** | A [LangGraph](https://www.langchain.com/langgraph) `StateGraph` with 4 sequential nodes |
| **Persistence** | Every conversation thread is checkpointed to Postgres, so a `thread_id` can be reused to continue a plan |
| **Frontend** | A single-page FastAPI + Jinja2 UI, no build step required |

---

## Tech stack

### At a glance

| Layer | Technology |
|---|---|
| **Language** | Python 3.12 |
| **Web framework** | FastAPI (served by Uvicorn) |
| **Agent orchestration** | LangGraph (`StateGraph`) + LangChain |
| **LLM provider** | Groq — `llama-3.3-70b-versatile` |
| **Database** | PostgreSQL (hosted on Neon) |
| **DB access** | `psycopg` / `psycopg-pool` + `langgraph-checkpoint-postgres` |
| **Web/hotel search** | Tavily |
| **Flight data** | AviationStack |
| **Frontend** | HTML5, CSS3, vanilla JavaScript, Jinja2 templates |
| **Package manager** | `pip` (with pinned `requirements.lock`) |
| **Containerization** | Docker |
| **Deployment** | Render Blueprint (`render.yaml`) |

### Detail

**Backend / AI**
- [FastAPI](https://fastapi.tiangolo.com/) — HTTP API and template serving
- [LangGraph](https://www.langchain.com/langgraph) — multi-agent orchestration (`StateGraph`)
- [LangChain](https://www.langchain.com/) / `langchain-groq` — LLM message plumbing
- [Groq](https://groq.com/) (`llama-3.3-70b-versatile`) — the LLM behind the itinerary & report agents
- [Tavily](https://tavily.com/) — live web search for hotel research
- [AviationStack](https://aviationstack.com/) — live flight schedule/status data
- `psycopg` / `psycopg-pool` — PostgreSQL driver
- `langgraph-checkpoint-postgres` — persists LangGraph state per conversation thread
- `airportsdata`, `pycountry` — resolve city/country names to IATA airport codes

**Database**
- [Neon](https://neon.tech/) — serverless PostgreSQL, used as the LangGraph checkpoint store

**Frontend**
- Jinja2 templates + vanilla HTML/CSS/JS (no framework, no build step)
- [`marked.js`](https://github.com/markedjs/marked) — renders the AI's markdown response
- [`html2pdf.js`](https://github.com/eKoopmans/html2pdf.js) — exports the generated plan as a PDF

**Tooling / Ops**
- Docker — containerized deployment (see [`Dockerfile`](Dockerfile))
- Render Blueprint — one-click deploy (see [`render.yaml`](render.yaml))
- `python-dotenv` — loads secrets from `.env` in local development

---

## Architecture

Voyagent runs a fixed, single-pass LangGraph pipeline — each node below is a real graph node in [`backend.py`](backend.py), not a simulated step:

```mermaid
flowchart LR
    START([User request]) --> A[✈️ Flight Agent]
    A --> B[🏨 Hotel Agent]
    B --> C[🗺️ Itinerary Agent]
    C --> D[📋 Final Report Agent]
    D --> END([Formatted travel plan])

    A -. AviationStack API .-> A
    B -. Tavily search .-> B
    C -. Groq LLM .-> C
    D -. Groq LLM .-> D
```

| Node | Function | What it does |
|---|---|---|
| Flight Agent | `flight_agent` | Parses the request for origin/destination, calls `search_flights()` against the AviationStack API |
| Hotel Agent | `hotel_agent` | Calls `tavily_search()` to find hotel options for the destination |
| Itinerary Agent | `itinerary_agent` | Sends flight + hotel results to the Groq LLM to draft a day-by-day itinerary |
| Final Report Agent | `final_agent` | Sends everything to the Groq LLM again to produce the final, formatted trip summary |

State flows through a shared `TravelState` (a `TypedDict`) that accumulates `flight_results`, `hotel_results`, `itinerary`, the running `messages` list, and an `llm_calls` counter — all of which are returned to the frontend and rendered in separate tabs.

---

## End-to-end request flow

```mermaid
sequenceDiagram
    participant U as Browser (index.html)
    participant F as FastAPI (app.py)
    participant G as LangGraph (backend.py)
    participant AV as AviationStack
    participant TV as Tavily
    participant GQ as Groq LLM
    participant DB as PostgreSQL

    U->>F: POST /api/travel {message, thread_id}
    F->>G: run_travel_agent(user_input, thread_id)
    G->>DB: load checkpoint for thread_id (if any)
    G->>AV: flight_agent -> search_flights(query)
    AV-->>G: live flight data
    G->>TV: hotel_agent -> tavily_search(query)
    TV-->>G: hotel search results
    G->>GQ: itinerary_agent -> llm.invoke(prompt)
    GQ-->>G: day-by-day itinerary
    G->>GQ: final_agent -> llm.invoke(prompt)
    GQ-->>G: formatted final plan
    G->>DB: save checkpoint for thread_id
    G-->>F: {answer, flight_results, hotel_results, itinerary, llm_calls}
    F-->>U: JSON response
    U->>U: render markdown into Overview / Flights / Hotels / Itinerary tabs
```

**In short:**

1. The browser sends the free-text request plus an optional `thread_id` (used to continue a prior conversation).
2. FastAPI hands it to `run_travel_agent()`, which invokes the compiled LangGraph graph with Postgres checkpointing enabled.
3. The graph runs its four nodes in order, calling AviationStack, Tavily, and Groq along the way.
4. The final state (answer + all intermediate results + call count) is returned as JSON.
5. The frontend renders the markdown response, splits results into tabs, and lets the user copy or download the plan as a PDF.

---

## Project structure

```
.
├── app.py                    # FastAPI app: routes, request/response models
├── backend.py                # LangGraph state, agent nodes, graph wiring, Postgres checkpointer
├── tools/
│   ├── flight_tool.py        # AviationStack integration + city/country -> IATA resolution
│   └── tavily_tool.py        # Tavily search wrapper used by the hotel agent
├── templates/
│   └── index.html            # Single-page UI (Jinja2)
├── static/
│   ├── style.css             # UI styling
│   └── script.js             # Frontend logic: API calls, tabs, PDF export
├── requirements.txt          # Dependency ranges
├── requirements.lock         # Pinned dependencies (used by Render builds)
├── render.yaml               # Render Blueprint: web service + environment
├── Dockerfile                # Container build for deployment
├── .env.example              # Example secrets file (copy to .env)
└── .env                      # Local secrets (not committed)
```

---

## Getting started

### Prerequisites

- Python 3.12+
- A [Neon](https://neon.tech/) (or any) PostgreSQL database
- API keys: [Groq](https://console.groq.com/), [Tavily](https://tavily.com/), [AviationStack](https://aviationstack.com/)

### 1. Clone and install dependencies

```sh
git clone https://github.com/GrrrGe/Voyagent.git
cd Voyagent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment variables

Create a `.env` file in the project root (see [Environment variables](#environment-variables) below). An example is provided in [`.env.example`](.env.example).

### 3. Run the app

```sh
.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

The app starts at **http://127.0.0.1:8000**. On first run, `backend.py` automatically creates the LangGraph checkpoint tables in your Postgres database.

---

## Environment variables

Create a `.env` file with the following:

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | PostgreSQL connection string used for LangGraph checkpointing |
| `GROQ_API_KEY` | ✅ | Groq API key — powers the itinerary and final report agents |
| `TAVILY_API_KEY` | ✅ | Tavily API key — powers the hotel search agent |
| `AVIATIONSTACK_API_KEY` | ✅ | AviationStack API key — powers the flight search agent |
| `DEFAULT_ORIGIN` | optional | Fallback IATA origin code used when a request only mentions a destination |

Example `.env`:

```env
DATABASE_URL='postgresql://user:password@host/dbname?sslmode=require'
GROQ_API_KEY=your_groq_api_key
TAVILY_API_KEY=your_tavily_api_key
AVIATIONSTACK_API_KEY=your_aviationstack_api_key
DEFAULT_ORIGIN=DEL
```

---

## API reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serves the Voyagent UI (`templates/index.html`) |
| `POST` | `/api/travel` | Runs the multi-agent pipeline for a travel request |
| `GET` | `/health` | Health check |

### `POST /api/travel`

**Request body**

```json
{
  "message": "Plan a 7 day Japan trip from Toronto under CAD 2,500",
  "thread_id": null
}
```

`thread_id` is optional — omit it (or pass `null`) to start a new conversation; pass a previously returned `thread_id` to continue an existing one using its saved checkpoint.

**Response**

```json
{
  "success": true,
  "thread_id": "user_3f9a1c2b...",
  "answer": "## Trip Summary\n...",
  "flight_results": "Live flights from MAA to NRT\n...",
  "hotel_results": "1. Hotel XYZ\n...",
  "itinerary": "Day 1: Arrive in Tokyo...",
  "llm_calls": 4
}
```

On failure, the API returns a `4xx`/`5xx` status with `{"success": false, "error": "..."}`.

---

## Running with Docker

```sh
docker build -t voyagent .
docker run -p 8000:8000 --env-file .env voyagent
```

The container installs dependencies from `requirements.txt` and starts `uvicorn app:app` on port `8000`.

---

## Conversation memory / checkpointing

Voyagent uses `langgraph-checkpoint-postgres` (`PostgresSaver`) so every run of the graph is saved against a `thread_id`. This means:

- Reusing a `thread_id` resumes the same LangGraph conversation state instead of starting fresh.
- All checkpoint tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations`) live in your configured Postgres database and are created automatically via `checkpointer.setup()` on startup.
- The frontend stores the active `thread_id` in `localStorage` so a returning browser session continues the same plan; "New plan" clears it and starts a fresh thread.

---

## Roadmap

- [ ] Real-time streaming of agent progress (currently simulated client-side while waiting on the response)
- [ ] Conditional routing (e.g. skip the flight agent for hotel-only requests) instead of a fixed sequential graph
- [ ] Ticket pricing integration (AviationStack provides schedules/status, not fares)
- [ ] Multi-turn refinement within a thread (e.g. "make it cheaper", "add one more day")

---

## License

Add your license of choice here (e.g. MIT).
