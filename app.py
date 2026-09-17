from pathlib import Path
import traceback
import uvicorn

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from backend import run_travel_agent

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Travel Agent AI",
    description="LangGraph Multi-Agent Travel Planner with FastAPI Frontend",
    version="1.0.0"
)


app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)


templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)



class TravelRequest(BaseModel):
    message: str
    thread_id: str | None = None
    user_id: str | None = None


class QuickStyle(BaseModel):
    user_id: str | None = None
    vibes: list[str] = []
    pace: str | None = None
    budget: str | None = None
    setting: str | None = None
    free_text: str | None = None


class QuizSubmit(BaseModel):
    user_id: str | None = None
    answers: dict


class TakeoutImport(BaseModel):
    user_id: str | None = None
    takeout: dict


class BrochureRequest(BaseModel):
    thread_id: str



@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.post("/api/travel")
async def travel_planner(request_data: TravelRequest):
    try:
        user_message = request_data.message.strip()

        if not user_message:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Message cannot be empty."
                }
            )

        result = run_travel_agent(
            user_input=user_message,
            thread_id=request_data.thread_id,
            travel_style=_style_for_user(request_data.user_id),
        )

        return JSONResponse(
            content={
                "success": True,
                "thread_id": result["thread_id"],
                "answer": result["answer"],
                "flight_results": result["flight_results"],
                "hotel_results": result["hotel_results"],
                "itinerary": result["itinerary"],
                "llm_calls": result["llm_calls"],
            }
        )

    except Exception as e:
        print("ERROR:", e)
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )



def _save_card(user_id, card):
    import uuid as _uuid
    from tools.user_embedding import embed_personality, save_profile
    uid = user_id or f"user_{_uuid.uuid4().hex[:12]}"
    vector = embed_personality(card)
    save_profile(uid, card, vector)
    return {"user_id": uid, "card": card, "dim": len(vector),
            "embedding_preview": vector[:8]}


def _style_for_user(user_id):
    if not user_id:
        return ""
    try:
        from tools.user_embedding import load_profile, style_line
        profile = load_profile(user_id)
        if not profile:
            return ""
        return style_line(profile.get("card", {}))
    except Exception:
        return ""


@app.get("/api/personality/quick")
async def personality_quick_spec():
    from tools.personality_quick import quick_spec
    return quick_spec()


@app.post("/api/personality/quick")
async def personality_quick_submit(body: QuickStyle):
    from tools.personality_quick import parse_quick
    try:
        card = parse_quick({"vibes": body.vibes or [], "pace": body.pace,
                            "budget": body.budget, "setting": body.setting,
                            "free_text": body.free_text or ""})
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"success": False, "error": str(exc)})
    return _save_card(body.user_id, card)


@app.get("/api/personality/quiz")
async def personality_quiz_spec():
    from tools.personality_quiz import quiz_questions
    return {"questions": quiz_questions()}


@app.post("/api/personality/quiz")
async def personality_quiz_submit(body: QuizSubmit):
    from tools.personality_quiz import score_answers
    try:
        card = score_answers(body.answers)
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"success": False, "error": str(exc)})
    return _save_card(body.user_id, card)


@app.post("/api/personality/import")
async def personality_takeout_import(body: TakeoutImport):
    from tools.personality_takeout import parse_takeout
    try:
        card = parse_takeout(body.takeout)
    except ValueError as exc:
        return JSONResponse(status_code=422, content={"success": False, "error": str(exc)})
    return _save_card(body.user_id, card)


@app.get("/api/personality/{user_id}")
async def personality_get(user_id: str):
    from tools.user_embedding import load_profile
    profile = load_profile(user_id)
    if not profile:
        return JSONResponse(status_code=404, content={"success": False, "error": "No personality found."})
    vector = profile.get("vector", [])
    return {"user_id": user_id, "card": profile.get("card", {}),
            "dim": len(vector), "embedding_preview": vector[:8]}


@app.get("/api/personality/benchmark/hnsw")
async def personality_benchmark_hnsw(num_users: int = 2000, dim: int = 64, k: int = 10):
    from tools.user_hnsw import benchmark
    num_users = max(100, min(num_users, 20000))
    dim = max(16, min(dim, 256))
    k = max(1, min(k, 50))
    return benchmark(num_users=num_users, dim=dim, k=k)


@app.get("/api/personality/benchmark/retrieval")
async def retrieval_benchmark(limit: int = 4):
    from tools.retrieval_benchmark import benchmark
    limit = max(1, min(limit, 10))
    return benchmark(limit=limit)


import threading as _threading
import uuid as _uuid

_brochure_jobs = {}
_brochure_lock = _threading.Lock()


def _run_brochure_job(job_id, thread_id):
    try:
        from backend import travel_graph
        from tools.brochure import (build_pdf, extract_stops, render_map,
                                    split_summaries)
        from tools.geocode import geocode_stops
        state = travel_graph.get_state({"configurable": {"thread_id": thread_id}}).values
        if not state or not state.get("itinerary"):
            raise ValueError("No completed trip found for this thread.")
        user_query = state.get("user_query", "")
        try:
            from tools.tavily_tool import hotel_destination
            city = hotel_destination(user_query) or ""
        except Exception:
            city = ""
        itinerary = state.get("itinerary", "")
        answer = ""
        messages = state.get("messages", []) or []
        if messages:
            try:
                answer = getattr(messages[-1], "content", "") or ""
            except Exception:
                answer = ""
        stops = extract_stops(itinerary, answer)
        located = geocode_stops(stops, city=city)
        map_png, zoom = render_map(located)
        summaries = split_summaries(itinerary)
        pdf = build_pdf("Voyagent Travel Plan", user_query[:100], map_png, zoom,
                        summaries, [name for name, _, _ in located])
        with _brochure_lock:
            _brochure_jobs[job_id].update({"status": "ready", "pdf": pdf,
                                           "stops": len(located)})
    except Exception as exc:
        with _brochure_lock:
            _brochure_jobs[job_id].update({"status": "failed", "error": str(exc)[:300]})


@app.post("/api/brochure")
async def brochure_start(body: BrochureRequest):
    job_id = f"brochure_{_uuid.uuid4().hex[:12]}"
    with _brochure_lock:
        _brochure_jobs[job_id] = {"status": "working", "thread_id": body.thread_id}
    worker = _threading.Thread(target=_run_brochure_job, args=(job_id, body.thread_id),
                               daemon=True)
    worker.start()
    return {"job_id": job_id, "status": "working"}


@app.get("/api/brochure/{job_id}")
async def brochure_status(job_id: str):
    with _brochure_lock:
        job = dict(_brochure_jobs.get(job_id, {}))
    if not job:
        return JSONResponse(status_code=404, content={"success": False, "error": "Unknown job."})
    response = {"job_id": job_id, "status": job["status"], "stops": job.get("stops", 0)}
    if job["status"] == "failed":
        response["error"] = job.get("error", "Brochure failed.")
    if job["status"] == "ready":
        response["download_url"] = f"/api/brochure/{job_id}/pdf"
    return response


@app.get("/api/brochure/{job_id}/pdf")
async def brochure_pdf(job_id: str):
    from fastapi.responses import Response
    with _brochure_lock:
        job = _brochure_jobs.get(job_id)
        pdf = job.get("pdf") if job else None
    if not job:
        return JSONResponse(status_code=404, content={"success": False, "error": "Unknown job."})
    if job["status"] != "ready" or not pdf:
        return JSONResponse(status_code=409,
                            content={"success": False, "error": "Brochure is not ready yet."})
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Voyagent-brochure-{job_id}.pdf"'})


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "AI Travel Planner API is running"
    }


@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(content={})



if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )