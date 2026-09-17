"""Free geocoding via OpenStreetMap Nominatim with local cache and throttle.

Hard boundaries of the free service, enforced here:
- max 1 request per second (enforced with a lock + sleep)
- identifying User-Agent with contact info
- all results cached under DATA_DIR/geocode.json so repeat brochures
  and redeploys cost zero new requests
"""
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "VoyagentBrochure/1.0 (https://github.com/GrrrGe/Voyagent)"
MIN_INTERVAL = 1.1

_lock = threading.Lock()
_last_call = 0.0


def _base_dir():
    return Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parents[1] / ".data")))


def _cache_path():
    path = _base_dir() / "geocode.json"
    return path


def load_cache():
    try:
        return json.loads(_cache_path().read_text())
    except Exception:
        return {}


def save_cache(cache):
    try:
        directory = _cache_path().parent
        directory.mkdir(parents=True, exist_ok=True)
        _cache_path().write_text(json.dumps(cache))
    except Exception:
        pass


def geocode(place, city="", country=""):
    """Geocode a place name -> (lat, lon) or None. Cached and throttled."""
    query = ", ".join(part for part in (place, city, country) if part).strip()
    if not query:
        return None
    key = query.lower()
    cache = load_cache()
    if key in cache:
        hit = cache[key]
        return (hit[0], hit[1]) if hit else None

    global _last_call
    with _lock:
        wait = MIN_INTERVAL - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        params = urllib.parse.urlencode(
            {"q": query, "format": "json", "limit": 1, "addressdetails": 0})
        request = urllib.request.Request(
            f"{NOMINATIM_URL}?{params}", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception:
            payload = []
        _last_call = time.monotonic()

    result = None
    if payload:
        try:
            result = (float(payload[0]["lat"]), float(payload[0]["lon"]))
        except (KeyError, TypeError, ValueError):
            result = None
    cache[key] = list(result) if result else None
    save_cache(cache)
    return result


def geocode_stops(stops, city="", country=""):
    """Geocode a list of place names, skipping failures. Returns [(name, lat, lon)]."""
    located = []
    for name in stops:
        point = geocode(name, city=city, country=country)
        if point:
            located.append((name, point[0], point[1]))
        if len(located) >= 12:
            break
    return located
