from tavily import TavilyClient
import os
import re
from dotenv import load_dotenv
load_dotenv()

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

JUNK_PATTERNS = [
    r"\(/cdn-cgi/[^)]*\)",      # Cloudflare email protection fragments
    r"\S*/cdn-cgi/\S*",         # bare Cloudflare artifact URLs
]


def clean_snippet(text: str) -> str:
    for pattern in JUNK_PATTERNS:
        text = re.sub(pattern, " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def hotel_destination(user_query: str):
    """Best-effort destination city for a hotel search.

    Uses the parsed flight route when available, otherwise the last
    mentioned location that is not the origin, so a query like
    "Japan trip from Bangladesh" searches hotels in Tokyo rather
    than echoing the whole trip sentence to the search engine.
    """
    from tools.flight_tool import (
        parse_route,
        resolve_location_to_iata,
        find_location_mentions,
        AIRPORTS,
    )
    dep_iata, arr_iata = parse_route(user_query)
    if arr_iata and arr_iata in AIRPORTS:
        return AIRPORTS[arr_iata].get("city")
    origin_iata = dep_iata
    match = re.search(
        r"\bfrom\s+(.+?)(?:\s+(?:to|for|under|including|with|in|on|at)\b|[.!?]|$)",
        user_query.lower(),
    )
    if match:
        origin_iata = resolve_location_to_iata(match.group(1)) or dep_iata
    for mention in reversed(find_location_mentions(user_query)):
        iata = resolve_location_to_iata(mention)
        if iata and iata != origin_iata and iata in AIRPORTS:
            return AIRPORTS[iata].get("city")
    return None


def hotel_search(user_query: str):
    """Search hotels for the trip destination with cleaned snippets."""
    city = hotel_destination(user_query)
    query = f"Best hotels to stay in {city}" if city else f"Best hotels for {user_query}"
    try:
        response = client.search(query, max_results=3, search_depth="advanced")
        results = []
        for i, r in enumerate(response.get("results", []), 1):
            title = (r.get("title") or "No Title").strip()
            url = r.get("url") or "No URL"
            snippet = clean_snippet(r.get("content") or "")
            if len(snippet) < 30 or snippet.lower() in ("loader", "..."):
                continue
            if len(snippet) > 300:
                snippet = snippet[:300].rsplit(" ", 1)[0] + "..."
            results.append(f"{i}. {title}\nURL: {url}\nSnippet: {snippet}\n")
        if not results:
            return "No usable hotel results were returned for this search."
        return "\n\n".join(results)

    except Exception as e:
        print(f"An error occurred while searching: {e}")
        return "An error occurred while searching. Please try again later."


def tavily_search(query: str):
    """
    Search for a query using the Tavily API.

    Args:
        query (str): The search query.

    Returns:
        dict: The search results from the Tavily API.
    """
    return hotel_search(query)
