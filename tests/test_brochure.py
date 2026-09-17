"""Offline brochure tests: no network, stub tile fetcher, cached geocoder."""
import io
import json

from tools.brochure import (build_pdf, choose_zoom, extract_stops,
                            latlon_to_tile, meters_per_pixel,
                            nice_scale_length, render_map, split_summaries)


def test_tile_math_known_values():
    assert latlon_to_tile(0, 0, 1) == (1, 1)
    assert abs(meters_per_pixel(0, 0) - 156543.03392) < 0.01
    assert nice_scale_length(meters_per_pixel(48.85, 12), 120) > 0


def test_choose_zoom_fits_points():
    points = [("a", 48.85, 2.35), ("b", 48.86, 2.37)]
    zoom = choose_zoom(points)
    assert 8 <= zoom <= 16


def test_extract_stops_collects_bold_and_lists():
    itinerary = ("Day 1: Arrive\n- Visit **Louvre Museum**\n"
                 "- Walk Tuileries Garden\nDay 2: Explore\n- Visit **Louvre Museum**")
    stops = extract_stops(itinerary)
    assert "Louvre Museum" in stops
    assert stops.count("Louvre Museum") == 1
    assert len(stops) <= 12


def test_extract_stops_empty():
    assert extract_stops("") == []


def test_split_summaries_trims_days():
    itinerary = "Day 1: Arrive\n" + ("word " * 200) + "\nDay 2: Explore\nShort day."
    sections = split_summaries(itinerary)
    assert len(sections) == 2
    assert sections[0][0].lower().startswith("day 1")
    assert len(sections[0][1]) <= 410


def _stub_tile(z, x, y):
    from PIL import Image
    image = Image.new("RGB", (256, 256), (200, 220, 200))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_render_map_with_stub_tiles():
    points = [("Louvre", 48.8611, 2.3364), ("Eiffel", 48.8584, 2.2945)]
    png, zoom = render_map(points, fetcher=_stub_tile)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert isinstance(zoom, int) and zoom > 0


def test_render_map_empty():
    assert render_map([]) == (None, 0)


def test_build_pdf_with_map():
    png, _ = render_map([("Louvre", 48.8611, 2.3364)], fetcher=_stub_tile)
    pdf = build_pdf("Voyagent Travel Plan", "Paris trip", png, 13,
                    [("Day 1: Arrive", "Visit the Louvre.")], ["Louvre"])
    assert pdf[:5] == b"%PDF-"


def test_build_pdf_without_map():
    pdf = build_pdf("Voyagent Travel Plan", "Paris trip", None, 0,
                    [("Day 1: Arrive", "Visit.")], [])
    assert pdf[:5] == b"%PDF-"


def test_geocode_uses_cache_without_network(monkeypatch, tmp_path):
    import tools.geocode as geocode
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    cache = {"louvre, paris": [48.8611, 2.3364]}
    (tmp_path / "geocode.json").write_text(json.dumps(cache))

    def fail(*args, **kwargs):
        raise AssertionError("network must not be used on cache hit")

    monkeypatch.setattr("urllib.request.urlopen", fail)
    assert geocode.geocode("Louvre", city="Paris") == (48.8611, 2.3364)
