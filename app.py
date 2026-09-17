from contextlib import asynccontextmanager, ExitStack
from pathlib import Path
from threading import RLock
from uuid import UUID, uuid4
import os
import sqlite3
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict
from starlette.middleware.sessions import SessionMiddleware
from langgraph.checkpoint.sqlite import SqliteSaver
from backend import build_graph
from security import session_secret, internal_thread, validate_providers, RateLimiter

load_dotenv()
BASE = Path(__file__).resolve().parent
DATA = Path(os.getenv('DATA_DIR', str(BASE / '.data')))
DATA.mkdir(parents=True, exist_ok=True)
lock = RLock()
limiter = RateLimiter()

@asynccontextmanager
async def lifespan(app):
    validate_providers()
    with ExitStack() as stack:
        database = os.getenv('DATABASE_URL')
        if database:
            from langgraph.checkpoint.postgres import PostgresSaver
            saver = stack.enter_context(PostgresSaver.from_conn_string(database))
            saver.setup()
            app.state.storage = 'postgres'
        else:
            conn = sqlite3.connect(DATA / 'checkpoints.sqlite', check_same_thread=False)
            stack.callback(conn.close)
            saver = SqliteSaver(conn)
            saver.setup()
            app.state.storage = 'sqlite'
        app.state.graph = build_graph(saver)
        yield

app = FastAPI(title='Voyagent', lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=session_secret(DATA), same_site='strict',
                   https_only=os.getenv('APP_ENV') == 'production', max_age=60 * 60 * 24 * 30)
app.mount('/static', StaticFiles(directory=BASE / 'static'), name='static')

@app.middleware('http')
async def headers(request, call_next):
    if request.method == 'POST':
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail': 'Cross-site requests are not allowed.'}, 403)
        origin = request.headers.get('origin')
        public_origin = os.getenv('PUBLIC_ORIGIN') or os.getenv('RENDER_EXTERNAL_URL') or str(request.base_url)
        if origin and origin.rstrip('/') != public_origin.rstrip('/'):
            return JSONResponse({'detail': 'Origin is not allowed.'}, 403)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            limit = 500000 if request.url.path.startswith('/api/personality') else 16000
            if len(body) > limit:
                return JSONResponse({'detail': 'Request is too large.'}, 413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers.update({'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'same-origin',
        'Content-Security-Policy': "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
        'Cache-Control': 'no-store' if request.url.path.startswith('/api') else 'no-cache'})
    return response

class TravelRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    message: str = Field(min_length=3, max_length=2000)
    thread_id: UUID | None = None
    user_id: str | None = Field(default=None, max_length=64)


class PersonalityImport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: str | None = Field(default=None, max_length=64)
    takeout: dict


class QuizSubmit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: str | None = Field(default=None, max_length=64)
    answers: dict


class QuickStyle(BaseModel):
    model_config = ConfigDict(extra='forbid')
    user_id: str | None = Field(default=None, max_length=64)
    vibes: list[str] = Field(default_factory=list, max_length=4)
    pace: str | None = Field(default=None, max_length=16)
    budget: str | None = Field(default=None, max_length=16)
    setting: str | None = Field(default=None, max_length=16)
    free_text: str | None = Field(default=None, max_length=500)


def config_for(request, thread_id):
    if 'owner' not in request.session:
        request.session['owner'] = str(uuid4())
    return {'configurable': {'thread_id': internal_thread(request.session['owner'], str(thread_id))}}

@app.get('/', response_class=HTMLResponse)
@app.get('/planner', response_class=HTMLResponse)
def index():
    page = BASE / 'templates' / 'index.html'
    return page.read_text() if page.exists() else '<h1>Voyagent.</h1><p>Planning API is ready.</p>'

@app.get('/about', response_class=HTMLResponse)
@app.get('/how-it-works', response_class=HTMLResponse)
def about():
    page = BASE / 'templates' / 'about.html'
    return page.read_text() if page.exists() else '<h1>How it works.</h1><p>Six agents plan your trip.</p>'

@app.get('/health')
def health():
    return {'status': 'ok', 'storage': app.state.storage,
            'providers': {k: 'MOCK' if os.getenv(f'{k.upper()}_PROVIDER', 'mock') == 'mock' else 'LIVE' for k in ['flight', 'hotel', 'llm']},
            'language_provider': os.getenv('LLM_PROVIDER', 'mock')}

@app.post('/api/travel')
def travel(body: TravelRequest, request: Request):
    thread_id = body.thread_id or uuid4()
    config = config_for(request, thread_id)
    with lock:
        limiter.check(request.client.host if request.client else 'local')
        previous = {}
        try:
            # Parse before invocation so a rejected input cannot corrupt a saved plan.
            from agents.research import parse_trip
            previous = app.state.graph.get_state(config).values
            parse_trip(body.message, previous.get('trip'))
            initial = {'message': body.message, 'complete': False}
            if body.user_id:
                from tools.user_embedding import load_profile
                profile = load_profile(body.user_id)
                if profile:
                    initial.update({'user_id': body.user_id,
                                    'personality': profile.get('card'),
                                    'user_vec': profile.get('vector')})
            result = app.state.graph.invoke(initial, config)
        except ValueError as exc:
            if previous.get('complete'):
                app.state.graph.update_state(config, previous, as_node='report_agent')
            return JSONResponse({'detail': str(exc), 'thread_id': str(thread_id)}, 422)
        except Exception as exc:
            if previous.get('complete'):
                app.state.graph.update_state(config, previous, as_node='report_agent')
            # Provider exception text can contain credential-bearing request URLs.
            logging.getLogger('voyagent').error('Planning failed: %s', type(exc).__name__)
            return JSONResponse({'detail': 'Planning failed. Check provider configuration or try again.', 'thread_id': str(thread_id)}, 502)
    return dict(result, thread_id=str(thread_id))

@app.get('/api/travel/{thread_id}')
def saved(thread_id: UUID, request: Request):
    with lock:
        state = app.state.graph.get_state(config_for(request, thread_id)).values
    if not state or not state.get('complete'):
        raise HTTPException(404, 'No completed trip found in this browser session.')
    return dict(state, thread_id=str(thread_id))

@app.post('/api/personality/import')
def personality_import(body: PersonalityImport):
    """Build a traveler personality from Google Maps Takeout (local only)."""
    from tools.personality_takeout import parse_takeout
    from tools.user_embedding import embed_personality, save_profile
    try:
        card = parse_takeout(body.takeout)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    user_id = body.user_id or str(uuid4())
    vector = embed_personality(card)
    save_profile(user_id, card, vector)
    return {'user_id': user_id, 'card': card, 'dim': len(vector),
            'embedding_preview': vector[:8]}

@app.get('/api/personality/quick')
def personality_quick_spec():
    """Fast style picker spec: chips with defaults, nothing required."""
    from tools.personality_quick import quick_spec
    return quick_spec()

@app.post('/api/personality/quick')
def personality_quick_submit(body: QuickStyle):
    """One-call style save: tap chips (or skip) and get a profile id."""
    from tools.personality_quick import parse_quick
    from tools.user_embedding import embed_personality, save_profile
    try:
        card = parse_quick({"vibes": body.vibes, "pace": body.pace,
                            "budget": body.budget, "setting": body.setting,
                            "free_text": body.free_text or ""})
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    user_id = body.user_id or str(uuid4())
    vector = embed_personality(card)
    save_profile(user_id, card, vector)
    return {'user_id': user_id, 'card': card, 'dim': len(vector),
            'embedding_preview': vector[:8]}

@app.get('/api/personality/quiz')
def personality_quiz():
    """Short prerequisite quiz spec (six questions)."""
    from tools.personality_quiz import quiz_questions
    return {'questions': quiz_questions()}

@app.post('/api/personality/quiz')
def personality_quiz_submit(body: QuizSubmit):
    """Score quiz answers into a personality embedding profile."""
    from tools.personality_quiz import score_answers
    from tools.user_embedding import embed_personality, save_profile
    try:
        card = score_answers(body.answers)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    user_id = body.user_id or str(uuid4())
    vector = embed_personality(card)
    save_profile(user_id, card, vector)
    return {'user_id': user_id, 'card': card, 'dim': len(vector),
            'embedding_preview': vector[:8]}

@app.get('/api/personality/benchmark/retrieval')
def retrieval_benchmark(limit: int = 4):
    """BM25 vs vector vs hybrid vs hybrid-reranked on catalog queries."""
    from tools.retrieval_benchmark import benchmark
    limit = max(1, min(limit, 10))
    return benchmark(limit=limit)

@app.get('/api/personality/{user_id}')
def personality_get(user_id: str):
    from tools.user_embedding import load_profile
    profile = load_profile(user_id)
    if not profile:
        raise HTTPException(404, 'No personality found for this user.')
    card = profile.get('card', {})
    vector = profile.get('vector', [])
    return {'user_id': user_id, 'card': card, 'dim': len(vector),
            'embedding_preview': vector[:8]}

@app.get('/api/personality/benchmark/hnsw')
def personality_benchmark(num_users: int = 2000, dim: int = 64, k: int = 10):
    """Brute-force vs HNSW recall/latency on synthetic users."""
    from tools.user_hnsw import benchmark
    num_users = max(100, min(num_users, 20000))
    dim = max(16, min(dim, 256))
    k = max(1, min(k, 50))
    return benchmark(num_users=num_users, dim=dim, k=k)

@app.get('/api/travel/{thread_id}/pdf')
def pdf(thread_id: UUID, request: Request):
    from tools.pdf_export import build_pdf
    from fastapi.responses import Response
    state = saved(thread_id, request)
    return Response(build_pdf(state), media_type='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="Voyagent-{state["trip"]["destination"]}.pdf"'})
