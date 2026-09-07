# Voyagent.

An original six-agent travel planner with a Python API and a no-build interface with color photography and sage, peach, and lavender accents. It runs complete trips without API keys. No source code from the functional reference was copied.

## Start locally.

Requires Python 3.12. Dependencies are pinned in `requirements.lock`.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
cp .env.example .env
```

For keyless local development, set `LLM_PROVIDER=mock` in `.env`. For the live AI plan, keep `LLM_PROVIDER=openai` and set `OPENAI_API_KEY`:

```sh
uvicorn app:app --host 127.0.0.1 --port 8000
```

With uv, use `uv venv --python 3.12` and `uv pip sync requirements.lock` instead of pip.

Open http://127.0.0.1:8000. The home page is the trip planner with examples. `/about` explains how it works and introduces the six agents. Fonts and photos are served locally. There is no frontend build step and no runtime CDN requirement.

The first run creates `.data/checkpoints.sqlite` and a local session signing secret. SQLite checkpoints survive restarts. The browser stores the public `thread_id` in localStorage and an HttpOnly, SameSite signed session cookie. Both are needed to reopen a trip. Clearing cookies removes access to that browser's saved trips. The New trip button starts a new conversation; it does not delete prior database records.

## Three keyless trips.

Use these in the landing input or select the corresponding sample. Dates default to 30 days from today unless an ISO date is provided.

1. `Plan 7 days in Tokyo from San Francisco under $2500 for 1 traveler, with food and walking.` Estimated total: **$1,948.10 USD estimated**.
2. `Plan 5 days in Lisbon from New York under $1800 for 1 traveler, with history and walking.` Estimated total: **$1,281.50 USD estimated**.
3. `Plan 4 days in Paris from Toronto under $1600 for 1 traveler, with art and history.` Estimated total: **$1,272.70 USD estimated**.

Supported destinations are Tokyo, Lisbon, Paris, Dubai, and Bangkok. Country names Japan, Thailand, and the UAE map to Tokyo, Bangkok, and Dubai. Origins are San Francisco, New York, Toronto, London, Chennai, Dhaka, and the five destination cities. Use 2 to 14 days, 1 to 8 travelers, USD budgets from $100 to $100,000, and dates today or later. The form makes these inputs explicit. The deterministic parser recognizes these fields, ISO dates, and food, art, history, or walking interests. It is not an unrestricted natural-language assistant. Other currencies are rejected rather than silently converted. Extend `tools/catalog.py` and parser tests to add destinations.

Examples of follow-ups in the same trip:

```text
Make it 5 days under $1800
Plan for rain on day 2
My flight has a 4 hour delay on day 1
My flight was cancelled on day 1
Clear disruption
```

Rain replaces the day's outdoor stops with one indoor visit. Delay scenarios remove activities before the revised travel window. Cancellation assumes a 24-hour travel interruption. These are user-triggered scenarios, not live disruption alerts. The planner never rebooks flights. Saved disruptions persist through budget changes until cleared. Every replan rebuilds the schedule and recalculates the costs. Invalid changes and provider failures preserve the last completed plan.

## Pipeline and files.

`backend.py` compiles a real LangGraph `StateGraph`:

```text
START -> research -> booking -> itinerary_agent
      -> disruption_agent -> budget_agent -> report_agent -> END
```

| File | Responsibility |
| --- | --- |
| `app.py` | FastAPI routes, application lifespan, checkpoint connection, browser session boundary |
| `backend.py` | Typed state and six sequential agent nodes |
| `agents/research.py` | Normalize trip details and research flights |
| `agents/booking.py` | Research hotel options, no purchases |
| `agents/itinerary.py` | Schedule local activity groups, validate timing |
| `agents/disruption.py` | Apply rain, flight delay, or cancellation scenarios |
| `agents/budget_agent.py` | Select lowest estimated costs, integer-cent totals and budget adjustment |
| `agents/report.py` | Produce the summary and exportable full report |
| `tools/flight_tool.py` | AviationStack adapter selected only by an explicit flag |
| `tools/hotel_tool.py` | Tavily adapter selected only by an explicit flag |
| `tools/mock_providers.py` | Provider protocols and deterministic default implementations |
| `tools/language_tool.py` | Groq and OpenAI adapters, JSON contracts and copy validation |
| `tools/knowledge.py` | Chroma vector store, LangChain retriever, trip grounding |
| `tools/pdf_export.py` | Paginated PDF output from the saved plan |
| `security.py` | Configuration checks, session secret, thread scoping, rate limiter |
| `eval.py` | Six keyless graph evaluation cases |
| `templates/index.html` | Landing and planner document |
| `static/style.css` | Design tokens, responsive layout, print-independent UI |
| `static/script.js` | API requests, localStorage continuity, tabs, copy, PDF download |
| `scripts/lint_copy.py` | Copy policy gate for frontend, templates, prompts, and agent copy |

Each agent's successful completion appears in `trace`. Loading text does not claim that individual agents have completed before the server responds. `llm_calls` is zero in mock mode and two with Groq or OpenAI enabled.

## Prices and feasibility.

Every provider object has separate `data_source` and `price_source` fields. **All monetary figures in this implementation are estimated allowances**, even if the related research is LIVE. AviationStack supplies route schedules, not fares. Tavily supplies web research, not guaranteed room inventory. Neither is presented as a booking quote. There are no payment or booking operations.

Curated costs use integer cents. Round-trip fares are per traveler. Hotel costs are per room per night with two guests per room, rounded up. Nights equal destination days minus one. Food is $35 USD estimated per person per day, transport is $12 USD estimated per person per day, and paid visits are $18 USD estimated per person. A reserve equals 10% of the subtotal, rounded up to the next cent. Sample hotel allowances include taxes. Visa fees, insurance, shopping, and origin-airport transfers are excluded.

The budget agent first uses the least expensive available fixture. If the total is too high, it replaces paid visits with no-cost stops and recalculates. If it is still over budget, it says so and keeps the shortfall visible. It does not invent lower fares or room rates.

The feasibility check enforces ordered, nonoverlapping visits, at least 30 minutes between stops, and an 08:00 to 21:00 activity window. The first visit is after 15:00 on arrival day. The last day ends by 14:00 for an assumed 18:00 return departure. Days represent time at the destination, not total international travel duration. Opening hours, flight date availability, exact transfer times, timezone crossings, and accessibility are not verified. Trips longer than the local area inventory revisit areas. These assumptions are also shown in the plan.

## API and curl.

```sh
curl --fail http://127.0.0.1:8000/health

curl --fail -c cookies.txt -b cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"message":"7 days in Tokyo from San Francisco under $2500","thread_id":null}' \
  http://127.0.0.1:8000/api/travel
```

The response contains `thread_id`, `answer`, `trip`, `flight_results`, `hotel_results`, `itinerary`, `budget`, `selected_flight`, `selected_hotel`, `disruption`, `changes`, `trace`, `summary`, `llm_calls`, and `complete`. Copy the returned UUID into the next requests:

```sh
curl --fail -c cookies.txt -b cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"message":"Rain on day 2","thread_id":"RETURNED_UUID"}' \
  http://127.0.0.1:8000/api/travel

curl --fail -b cookies.txt \
  http://127.0.0.1:8000/api/travel/RETURNED_UUID

curl --fail -b cookies.txt \
  http://127.0.0.1:8000/api/travel/RETURNED_UUID/pdf \
  -o trip.pdf
```

`GET /health` returns storage mode and each provider's MOCK or LIVE mode. It does not make billable provider calls. Requests with invalid fields return 422. Rate limits return 429. External request failures return 502. Saved trips outside the current session return 404. Use the same cookie jar for all calls in a conversation.

## Enable live research.

Local development defaults to curated fixtures when provider flags stay `mock`. Set the matching flag to `live` in `.env`, then restart:

```dotenv
FLIGHT_PROVIDER=live
AVIATIONSTACK_API_KEY=your_key
HOTEL_PROVIDER=live
TAVILY_API_KEY=your_key
LLM_PROVIDER=live
GROQ_API_KEY=your_key
GROQ_MODEL=llama-3.3-70b-versatile
```

Flags can be enabled independently. Missing keys fail startup. Live failures do not silently switch to curated providers. AviationStack uses HTTPS with a 20-second timeout and searches recent route observations. Future schedule inventory can require a different paid endpoint; this app does not claim those observations match the requested dates. Tavily returns hotel research titles and source URLs with estimated lodging allowances. Groq orders the supplied local area groups and writes a constrained report. The itinerary schema requires a valid permutation; report output must pass the same copy policy as authored content. Malformed output fails the request.

No live calls are made by the default demo, tests, or CI. Live adapters are tested using stubbed HTTP responses. Credentials, availability, and quota behavior need verification in your own provider accounts.

## Use your OpenAI project.

Set these server-side values in `.env`, or in the Render service environment. Do not paste secrets into the browser trip form.

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=your_existing_project_key
OPENAI_PROJECT_ID=your_existing_project_id
OPENAI_MODEL=gpt-4.1-mini
```

`OPENAI_PROJECT_ID` is optional for a project-scoped key. When set, it is sent as the `OpenAI-Project` request header. This selects an existing OpenAI project; it does not create an OpenAI project. The key must have access to that project and model. The server sends two constrained Responses API calls per trip, with strict JSON schemas, an output-token cap, a 30-second timeout, and `store: false`. Incomplete responses, refusals, and invalid copy fail the request. Flight and hotel prices stay estimated unless a verified fare provider is added.

OpenAI support is covered by stubbed HTTP contract tests. A live call requires your actual server-side key. The curated default remains available without keys for local development.

## Vector knowledge.

Destination areas and stays are embedded into a persistent Chroma collection at `DATA_DIR/chroma` and seeded from the catalog on first use. The itinerary agent retrieves the top areas per trip with a LangChain retriever, passes them to the language model as grounding, and records them in the plan under `grounding` and a `Retrieved areas` report line.

With `OPENAI_API_KEY` configured, embeddings use `text-embedding-3-small` (override with `OPENAI_EMBEDDING_MODEL`). Without a key, deterministic hash embeddings keep local development and tests offline. On Render free plans the filesystem is ephemeral, so the index rebuilds automatically on restart.

## PostgreSQL checkpoints.

Set `DATABASE_URL` to a psycopg-compatible PostgreSQL URI. On startup, `PostgresSaver.setup()` creates the LangGraph checkpoint schema, so the configured database user needs schema creation rights for the first deployment. Each graph step is checkpointed. The internal thread key hashes the signed browser session ID with the public UUID to prevent cross-session retrieval.

```dotenv
DATABASE_URL=postgresql://user:password@host:5432/voyagent?sslmode=require
SESSION_SECRET=replace_with_a_stable_random_value_of_at_least_32_characters
```

SQLite is the local default. Set a persistent `DATA_DIR` when using SQLite in a container. Keep `SESSION_SECRET` stable across restarts and replicas. There is no account recovery or cross-device identity feature. Checkpoint history stores trip details; use database retention and backups appropriate for your deployment.

## Tests and checks.

```sh
python scripts/lint_copy.py
pytest -q
python eval.py
# Start the app in another terminal before the HTTP smoke check.
python scripts/smoke.py
```

The suite checks schedule feasibility, budget totals, room rounding, provider contracts, live data provenance, disruption changes, state restoration, SQLite persistence, browser session isolation, input bounds, request rate limits, HTTP endpoints, PDF output, and copy rules. The optional Postgres reconnect test requires `TEST_DATABASE_URL`; CI provisions Postgres and runs it. Browser interaction tests are not included.

`lint_copy.py` scans first-party HTML, JS, CSS, SVG, JSON, prompt text, and backend copy for prohibited words and Unicode dash characters. Only the policy definition file and third-party font license are excluded. The workflow runs the linter as its own required job step. A test inserts prohibited copy into temporary frontend and prompt files to verify that the scanner fails.

## Deploy.

The app requires a Python process. A static host or a JavaScript-only Worker cannot run this backend.

**Render:** push this directory as a repository, create a Blueprint from `render.yaml`, and review the generated web service and database resources. Hosting may incur charges. The blueprint sets `LLM_PROVIDER=openai`, generates a session secret, and connects PostgreSQL. After deploy, add your `OPENAI_API_KEY` in the Render dashboard under the service Environment tab and redeploy. `/health` is the readiness endpoint and should report the language provider as `openai`.

**Docker:**

```sh
docker build -t voyagent .
docker run --rm -p 8000:8000 --env-file .env -v voyagent-data:/app/.data voyagent
```

Use `APP_ENV=production` behind HTTPS to require Secure cookies and a configured session secret. Keep the service behind a reverse proxy with a request-size limit. Do not put keys in frontend code or commit `.env`. The API uses a 16 KB body cap, a 2,000-character message limit, a 20-request-per-minute per-IP limiter, same-origin checks, CSP, and escaped DOM/PDF rendering. Run **one worker**: in-process serialization protects same-thread updates, and rate limits are process-local. Distributed locks and a shared limiter are needed before horizontal scaling. No arbitrary code execution or URL fetching from user text is supported.

## Design and sources.

The requested Mobbin-inspired system uses Inter, white, sage, peach, and lavender surfaces, a forest-green footer, pill controls, 16px inputs and media, 24px cards, no shadows, and blue savings and Popular badges. Every headline ends with a period. All three travel photos are local full-color copies from Unsplash; source URLs are below. Inter is included under the SIL Open Font License in `static/fonts/LICENSE.txt`.

Functional architecture reference, consulted for the API contract and agent roles only:
https://github.com/Karthiksaran-001/Multi-Agent-Travel-Planner

Provider documentation:
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://aviationstack.com/documentation
- https://docs.tavily.com/documentation/api-reference/endpoint/search
- https://console.groq.com/docs/api-reference

Image sources:
- Tokyo: https://images.unsplash.com/photo-1540959733332-eab4deabeeaf
- Lisbon: https://images.unsplash.com/photo-1555881400-74d7acaacd8b
- Paris: https://images.unsplash.com/photo-1502602898657-3e91760cbb34
