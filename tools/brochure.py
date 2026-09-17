"""Downloadable brochure: accurate-scale OSM route map plus day summaries.

Free-resource boundaries, all enforced here:
- Map tiles: OpenStreetMap standard tiles, valid User-Agent, disk cache so
  each tile is downloaded at most once, small bounded tile counts.
  Attribution "Map data (c) OpenStreetMap contributors" is printed on the
  map image and in the PDF (required by the ODbL license).
- Geocoding: Nominatim via tools/geocode.py (1 req/s, cached).
- PDF: reportlab + Pillow (both free, wheels, no API keys).
"""
import io
import math
import os
import re
import urllib.request
from pathlib import Path

TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "VoyagentBrochure/1.0 (https://github.com/GrrrGe/Voyagent)"
TILE_SIZE = 256
MAX_TILES = 12
ATTRIBUTION = "Map data (c) OpenStreetMap contributors"
ATTRIBUTION_PDF = "Map data \u00a9 OpenStreetMap contributors"

# Generic travel words that are never map pins.
GENERIC_WORDS = {
    "from", "to", "total", "cost", "costs", "budget", "summary", "overview",
    "arrival", "departure", "hotel", "hotels", "flight", "flights", "airport",
    "station", "day", "days", "trip", "note", "notes", "tip", "tips", "price",
    "prices", "person", "taxes", "included", "estimate", "estimated", "approx",
    "morning", "evening", "afternoon", "night", "base", "highlights", "look",
    "quick", "stay", "transfer", "check", "lunch", "dinner", "breakfast",
    "travel", "date", "dates",
}

_UNICODE_FIXES = {
    "\u2014": "-", "\u2013": "-", "\u201c": '"', "\u201d": '"',
    "\u2018": "'", "\u2019": "'", "\u2022": "-", "\u2026": "...",
    "\u20b9": "Rs. ", "\u00a0": " ",
}


def sanitize(text):
    """Clean Groq markdown into plain WinAnsi-safe text for the PDF.

    Strips headers, bold/italic, code, links, tables, and list markers,
    then replaces common unicode punctuation and drops anything else
    outside latin-1 (emoji included) so Helvetica never prints boxes.
    """
    text = text or ""
    for find, replace in _UNICODE_FIXES.items():
        text = text.replace(find, replace)
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.replace("|", " ")
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"(?m)^\s*(>\s*)+", "", text)
    text = re.sub(r"(?m)^\s*(?:\d+[.)]|[-*+])\s+", "", text)
    text = re.sub(r"[-=]{3,}", " ", text)
    text = re.sub(r"[#*_`>\[\]{}~]", "", text)
    text = "".join(c if ord(c) < 256 else "" for c in text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _base_dir():
    return Path(os.getenv("DATA_DIR", str(Path(__file__).resolve().parents[1] / ".data")))


def tiles_directory():
    directory = _base_dir() / "tiles"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def latlon_to_tile(lat, lon, zoom):
    n = 2.0 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(max(min(lat, 85.0511), -85.0511))
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return max(x, 0), max(y, 0)


def latlon_to_pixel(lat, lon, zoom):
    n = 2.0 ** zoom
    x = (lon + 180.0) / 360.0 * n * TILE_SIZE
    lat_rad = math.radians(max(min(lat, 85.0511), -85.0511))
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n * TILE_SIZE
    return x, y


def meters_per_pixel(lat, zoom):
    return 156543.03392 * math.cos(math.radians(lat)) / (2.0 ** zoom)


def choose_zoom(points, max_tiles=9):
    """Highest zoom where all points fit within max_tiles tiles."""
    lats = [p[1] for p in points]
    lons = [p[2] for p in points]
    for zoom in range(16, 0, -1):
        corners = [latlon_to_tile(lat, lon, zoom) for lat, lon in zip(lats, lons)]
        width = max(c[0] for c in corners) - min(c[0] for c in corners) + 1
        height = max(c[1] for c in corners) - min(c[1] for c in corners) + 1
        if width * height <= max_tiles:
            return zoom
    return 2


def fetch_tile(z, x, y):
    """Fetch one tile with disk cache. Returns PNG bytes or None."""
    path = tiles_directory() / str(z) / str(x)
    path.mkdir(parents=True, exist_ok=True)
    cached = path / f"{y}.png"
    if cached.exists():
        return cached.read_bytes()
    request = urllib.request.Request(
        TILE_URL.format(z=z, x=x, y=y), headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
    except Exception:
        return None
    try:
        cached.write_bytes(data)
    except Exception:
        pass
    return data


def nice_scale_length(meters_per_px, target_px=120):
    target_m = meters_per_px * target_px
    magnitude = 10 ** math.floor(math.log10(max(target_m, 1)))
    for multiple in (1, 2, 5, 10):
        if magnitude * multiple >= target_m:
            return magnitude * multiple
    return magnitude * 10


def render_map(points, fetcher=fetch_tile):
    """Render an accurate-scale route map PNG. Returns (png_bytes, zoom) or (None, 0)."""
    from PIL import Image, ImageDraw
    if not points:
        return None, 0
    zoom = choose_zoom(points) if len(points) > 1 else 13
    corners = [latlon_to_tile(lat, lon, zoom) for _, lat, lon in points]
    min_x, min_y = min(c[0] for c in corners), min(c[1] for c in corners)
    max_x, max_y = max(c[0] for c in corners), max(c[1] for c in corners)
    width, height = (max_x - min_x + 1) * TILE_SIZE, (max_y - min_y + 1) * TILE_SIZE

    canvas = Image.new("RGB", (width, height), (240, 240, 240))
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            data = fetcher(zoom, x, y)
            if not data:
                continue
            try:
                tile = Image.open(io.BytesIO(data)).convert("RGB")
            except Exception:
                continue
            canvas.paste(tile, ((x - min_x) * TILE_SIZE, (y - min_y) * TILE_SIZE))

    origin_x, origin_y = min_x * TILE_SIZE, min_y * TILE_SIZE
    pixels = []
    for _, lat, lon in points:
        px, py = latlon_to_pixel(lat, lon, zoom)
        pixels.append((px - origin_x, py - origin_y))

    draw = ImageDraw.Draw(canvas)
    if len(pixels) > 1:
        draw.line(pixels, fill=(220, 38, 40), width=4, joint="curve")
    for number, (px, py) in enumerate(pixels, 1):
        radius = 13
        draw.ellipse([px - radius, py - radius, px + radius, py + radius],
                     fill=(220, 38, 40), outline=(255, 255, 255), width=2)
        label = str(number)
        draw.text((px - 4 * len(label), py - 7), label, fill=(255, 255, 255))

    # Scale bar from real ground resolution at the mean latitude.
    mean_lat = sum(p[1] for p in points) / len(points)
    mpp = meters_per_pixel(mean_lat, zoom)
    bar_m = nice_scale_length(mpp)
    bar_px = bar_m / mpp
    margin = 14
    bar_y = height - margin - 14
    draw.rectangle([margin, bar_y, margin + bar_px, bar_y + 6], fill=(20, 20, 20))
    draw.rectangle([margin, bar_y, margin + bar_px / 2, bar_y + 6], fill=(255, 255, 255))
    unit = "km" if bar_m >= 1000 else "m"
    value = bar_m / 1000 if bar_m >= 1000 else int(bar_m)
    draw.text((margin, bar_y - 14), f"{value:g} {unit}", fill=(20, 20, 20))
    draw.text((margin, height - margin + 2), ATTRIBUTION, fill=(60, 60, 60))

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue(), zoom


def extract_stops(itinerary, answer="", limit=12):
    """Pull candidate place names from itinerary markdown.

    Collects bold spans and list items, drops generic travel words,
    table junk, and digit-heavy labels, dedupes while keeping visit
    order. Heuristic by design; misses degrade to fewer pins.
    """
    text = "\n".join(part for part in (itinerary or "", answer or "") if part)
    candidates = []
    candidates.extend(re.findall(r"\*\*(.+?)\*\*", text))
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^(\d+[.)]|[-*])\s+", stripped):
            item = re.sub(r"^(\d+[.)]|[-*])\s+", "", stripped)
            if len(re.findall(r"[a-zA-Z]+", item)) <= 5:
                candidates.append(item)
    seen, stops = set(), []
    for raw in candidates:
        name = re.sub(r"[#*_`>\[\]()]", "", raw).strip().rstrip(".,;:")
        name = re.sub(r"\s+", " ", name)
        if len(name) < 3 or len(name) > 60:
            continue
        if "|" in raw or re.search(r"\d", name):
            continue
        if not name[0].isupper():
            continue
        words = [w.lower() for w in re.findall(r"[a-zA-Z]+", name)]
        if not words or all(w in GENERIC_WORDS for w in words):
            continue
        key = name.lower()
        if key not in seen:
            seen.add(key)
            stops.append(name)
        if len(stops) >= limit:
            break
    return stops


def split_summaries(itinerary, per_day_chars=400, max_sections=8):
    """Split Groq markdown into clean (title, short_summary) sections.

    Prefers markdown headers ("## Day 2 ...", "### Quick look"), falls
    back to plain "Day N" splits. All output is sanitized plain text.
    """
    text = (itinerary or "").strip()
    if not text:
        return []
    parts = re.split(r"(?m)^(?=\s{0,3}#{1,4}\s+\S)", text)
    if len(parts) < 2:
        parts = re.split(r"(?im)^(?=day\s+\d+\s*[:\-.])", text)
    sections = []
    for part in parts:
        part = part.strip()
        if not part or len(sanitize(part)) < 20:
            continue
        lines = [line for line in part.splitlines() if line.strip()]
        title = sanitize(lines[0])[:60].rstrip(":") or "Itinerary"
        body = sanitize(" ".join(lines[1:]))
        if len(body) > per_day_chars:
            cut = body[:per_day_chars].rsplit(" ", 1)[0]
            body = cut + "..."
        sections.append((title, body or title))
        if len(sections) >= max_sections:
            break
    return sections


def build_pdf(title, subtitle, map_png, zoom, summaries, stops):
    """Assemble the brochure PDF from sanitized plain text. Returns bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as pdf_canvas
    output = io.BytesIO()
    page = pdf_canvas.Canvas(output, pagesize=A4)
    page_width, page_height = A4

    page.setFont("Helvetica-Bold", 22)
    page.drawString(20 * mm, page_height - 25 * mm, sanitize(title)[:60])
    page.setFont("Helvetica", 11)
    page.drawString(20 * mm, page_height - 32 * mm, sanitize(subtitle)[:100])

    cursor = page_height - 40 * mm
    if map_png:
        path = _base_dir() / "brochure-map.png"
        try:
            path.write_bytes(map_png)
            image_width = page_width - 40 * mm
            image_height = image_width * 0.62
            if cursor - image_height < 30 * mm:
                image_height = cursor - 30 * mm
            page.drawImage(str(path), 20 * mm, cursor - image_height,
                           width=image_width, height=image_height,
                           preserveAspectRatio=True, anchor="n")
            cursor -= image_height + 4 * mm
            page.setFont("Helvetica", 7)
            page.drawString(20 * mm, cursor, ATTRIBUTION_PDF + " | Route in visit order, true map scale.")
            cursor -= 8 * mm
        except Exception:
            pass
    else:
        page.setFont("Helvetica-Oblique", 10)
        page.drawString(20 * mm, cursor, "Route map unavailable for this trip - see the day-by-day plan below.")
        cursor -= 8 * mm

    page.setFont("Helvetica-Bold", 14)
    page.drawString(20 * mm, cursor, "Day by day.")
    cursor -= 8 * mm
    for index, (day_title, body) in enumerate(summaries, 1):
        if cursor < 30 * mm:
            page.showPage()
            cursor = page_height - 20 * mm
        pin = f"{index}. " if index <= len(stops) else ""
        page.setFont("Helvetica-Bold", 11)
        page.drawString(20 * mm, cursor, f"{pin}{day_title}"[:90])
        cursor -= 6 * mm
        page.setFont("Helvetica", 10)
        for line in _wrap(body, 95):
            if cursor < 20 * mm:
                page.showPage()
                cursor = page_height - 20 * mm
                page.setFont("Helvetica", 10)
            page.drawString(20 * mm, cursor, line)
            cursor -= 5 * mm
        cursor -= 3 * mm

    page.setFont("Helvetica", 7)
    page.drawString(20 * mm, 12 * mm,
                   "Planning draft with estimated costs. Confirm bookings, hours, and availability. "
                   + ATTRIBUTION_PDF + ".")
    page.showPage()
    page.save()
    return output.getvalue()


def _wrap(text, width):
    words, lines, current = (text or "").split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines or [""]
