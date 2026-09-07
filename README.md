# Voyagent.

### Agentic AI travel planner. Six specialized agents, one LangGraph pipeline, retrieval-grounded generation.

Turn a trip request into flight research, hotel options, a day-by-day itinerary, and a checked budget. Continue the same conversation to change the trip or plan around rain, flight delays, and cancellations.

[![Verify planner](https://github.com/GrrrGe/Voyagent/actions/workflows/ci.yml/badge.svg)](https://github.com/GrrrGe/Voyagent/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-245b48)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)

**[Setup and provider guide](docs/guide.md) · [API examples](#api) · [Deployment](#deployment)**

## What it does.

- Runs six specialized agents in a LangGraph `StateGraph`: flight research, hotel research, itinerary, disruption replan, budget check, and report.
- Retrieval-grounded generation: agents gather flight schedules, hotel research, and curated destination data first, then the LLM reasons over that retrieved context under strict JSON schemas.
- Searches a persistent Chroma vector store with LangChain to ground every itinerary in embedded destination knowledge.
- Produces Overview, Flights, Hotels, Itinerary, and Budget tabs.
- Persists conversation checkpoints in PostgreSQL with per-thread resumption.
- Replans affected days for rain, flight delays, or cancellations.
- Calculates costs in integer cents, includes a 10% reserve, and flags budget shortfalls.
- Plugs in OpenAI, Groq, AviationStack, and Tavily adapters behind provider interfaces.
- Exports the complete plan as text or a paginated PDF.
- Serves a responsive HTML, CSS, and JavaScript frontend without a build step.

<p>
  <img src="static/images/tokyo.jpg" width="32%" alt="Tokyo cityscape">
  <img src="static/images/lisbon.jpg" width="32%" alt="Lisbon cityscape">
  <img src="static/images/paris.jpg" width="32%" alt="Paris cityscape">
</p>

## Architecture.

```mermaid
flowchart LR
    A[Trip request] --> B[Flight research]
    B --> C[Hotel research]
    C --> D[Itinerary]
    D --> E[Disruption replan]
    E --> F[Budget check]
    F --> G[Report]
    G --> H[Tabbed plan and PDF]
    P[(PostgreSQL)] -. Checkpoints per thread .-> D
```

| Layer | Implementation |
| --- | --- |
| API | FastAPI, Pydantic validation, Uvicorn |
| Agentic orchestration | LangGraph `StateGraph`, six typed-state nodes, tool calls per agent |
| Retrieval grounding | AviationStack routes, Tavily hotel search, curated destination catalogs |
| Vector knowledge | Chroma persistent store, LangChain retriever, OpenAI or offline hash embeddings |
| Conversation state | PostgreSQL checkpoints, browser session isolation |
| Language models | OpenAI Responses API with strict JSON schemas, or Groq |
| Cost model | Integer-cent arithmetic, budget adjustment |
| Frontend | Vanilla JavaScript, Inter, responsive CSS, accessible tabs |
| Export | ReportLab PDF generation |
| Quality | pytest, graph evaluations, copy lint, HTTP smoke checks, GitHub Actions |

The provider interfaces separate the graph from external services. A failed provider call preserves the last completed plan instead of replacing it with a partial result.

## Run locally.

Requires Python 3.12.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
cp .env.example .env
```

Set `LLM_PROVIDER=openai` with `OPENAI_API_KEY` in `.env`, then start the server:

```sh
uvicorn app:app --host 0.0.0.0 --port $PORT
```

The home page is the trip planner. `/about` explains how it works. No database server or frontend build tools are needed. Dependencies, fonts, and photos are served locally after setup.

## Try a trip.

| Request | Estimated total |
| --- | --- |
| 7 days in Tokyo from San Francisco under $2500, with food and walking | $1,948.10 USD estimated |
| 5 days in Lisbon from New York under $1800, with history and walking | $1,281.50 USD estimated |
| 4 days in Paris from Toronto under $1600, with art and history | $1,272.70 USD estimated |
| 5 days in Dubai from Dhaka, with flights, hotels, and sightseeing | $1,695.10 USD estimated |
| 6 days in Thailand from London under $2000, with food and walking | $1,555.40 USD estimated |

These examples use one traveler and default to 30 days from today. Then try `Rain on day 2`, `My flight has a 4 hour delay on day 1`, or `Make it 5 days under $1800` in the same conversation.

Trips run 2 to 14 days for 1 to 8 travelers. The parser handles destinations, dates, budgets, and interests from plain language.

<a id="api"></a>
## API.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/travel` | Create or continue a trip using `{message, thread_id}` |
| `GET` | `/api/travel/{thread_id}` | Restore a completed trip within the browser session |
| `GET` | `/api/travel/{thread_id}/pdf` | Download the saved plan |
| `GET` | `/health` | Check storage and provider modes |

```sh
curl --fail -c cookies.txt -b cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"message":"7 days in Tokyo from San Francisco under $2500","thread_id":null}' \
  https://your-app.onrender.com/api/travel
```

Reuse the returned `thread_id` and the same cookie jar for follow-ups. The response includes the itinerary, research results, budget breakdown, agent trace, full report, and provider labels.

## Testing.

```sh
python scripts/lint_copy.py
pytest -q
python eval.py
# With the app running:
python scripts/smoke.py
```

CI runs the test suite against a PostgreSQL service, six graph evaluation cases, the copy linter, and HTTP smoke checks for all three sample trips. Tests cover feasibility, budget math, provider contracts, replanning, persistence, session isolation, input bounds, and PDF export. External providers use stubbed HTTP responses in tests.

## Data labels and scope.

All monetary figures are **estimated** allowances, including when related route or hotel research is **LIVE**. AviationStack does not provide ticket fares, and Tavily results do not verify room inventory. The app makes no bookings.

The planner checks activity overlap, transfer gaps, arrival windows, and budget arithmetic. It does not verify opening hours, exact travel times, visa requirements, or availability. Flight changes are user-entered scenarios, not live alerts. These limits are shown in the plan.

<a id="deployment"></a>
## Deployment.

[Deploy on Render](https://render.com/deploy?repo=https://github.com/GrrrGe/Voyagent)

The checked-in `render.yaml` defines a Voyagent project with a Python web service and PostgreSQL database. It selects free plans, generates a session secret, sets `LLM_PROVIDER=openai`, and connects PostgreSQL. Set `OPENAI_API_KEY` in the Render dashboard after the first deploy. Review the platform's current free-plan limits before deployment.

Set `LLM_PROVIDER=openai` and `OPENAI_API_KEY` in the server environment. Optionally set `OPENAI_PROJECT_ID` and `OPENAI_MODEL`. Render deploys use these values from the service environment. Keys are never placed in the frontend. See the [provider and deployment guide](docs/guide.md) for all flags, Docker instructions, and production constraints.

## Implementation notes.

- **Agentic state continuity:** each agent checkpoints its state, and session-scoped thread identifiers prevent cross-browser access to saved trips.
- **Budget correctness:** totals use integer cents and include per-person fares, room counts, nights, activities, and reserve rounding.
- **Failure handling:** invalid replans and provider failures restore the previous completed plan.
- **Constrained generation:** LLM output is schema-checked and copy-validated before it enters the plan.
- **Vector grounding:** destination areas and stays are embedded once into Chroma and retrieved per trip. OpenAI embeddings apply when a key is configured, otherwise deterministic offline embeddings keep development and tests network-free.
- **Reproducibility:** pinned dependencies and offline fixtures support development and automated evaluation.

Inter is distributed under its [SIL Open Font License](static/fonts/LICENSE.txt). Travel images are from Unsplash: [Tokyo](https://images.unsplash.com/photo-1540959733332-eab4deabeeaf), [Lisbon](https://images.unsplash.com/photo-1555881400-74d7acaacd8b), and [Paris](https://images.unsplash.com/photo-1502602898657-3e91760cbb34).
