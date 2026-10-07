from typing import Optional

import httpx

from app.core.config import settings

PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


class GoogleMapsError(Exception):
    pass


def search_places(query: str, city: Optional[str] = None, max_results: int = 20) -> list[dict]:
    """
    Text Search - e.g. query="electronics store", city="Gurugram" becomes
    "electronics store in Gurugram". Returns raw Places API results
    (business_name/address/place_id/etc still need normalize_place()).

    Kept to one page (~20 results) per call, which is enough for a single
    "Search Leads" click in the UI. Pagination via next_page_token can be
    added later if bulk imports need more.
    """
    if not settings.GOOGLE_MAPS_API_KEY:
        raise GoogleMapsError("GOOGLE_MAPS_API_KEY is not configured")

    full_query = f"{query} in {city}" if city else query
    params = {"query": full_query, "key": settings.GOOGLE_MAPS_API_KEY}

    with httpx.Client(timeout=15) as client:
        resp = client.get(PLACES_TEXT_SEARCH_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    status = data.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        raise GoogleMapsError(f"Places API error: {status} - {data.get('error_message', '')}")

    return data.get("results", [])[:max_results]


def get_place_details(place_id: str) -> dict:
    """Fetches phone/website, which Text Search does not return."""
    if not settings.GOOGLE_MAPS_API_KEY:
        raise GoogleMapsError("GOOGLE_MAPS_API_KEY is not configured")

    params = {
        "place_id": place_id,
        "fields": "name,formatted_phone_number,international_phone_number,website,formatted_address,url",
        "key": settings.GOOGLE_MAPS_API_KEY,
    }
    with httpx.Client(timeout=15) as client:
        resp = client.get(PLACES_DETAILS_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") != "OK":
        raise GoogleMapsError(f"Place Details error: {data.get('status')}")
    return data.get("result", {})


def normalize_place(place: dict, details: Optional[dict], category: Optional[str],
                     city: Optional[str], state: Optional[str], country: Optional[str]) -> dict:
    """
    Maps raw Places API shape -> our Lead schema's field names, so the
    router/ingestion code never has to know Google's JSON keys.
    """
    return {
        "business_name": place.get("name", "Unknown business"),
        "category": category,
        "phone": (details or {}).get("formatted_phone_number") or (details or {}).get("international_phone_number"),
        "website": (details or {}).get("website"),
        "google_maps_url": (details or {}).get("url") or f"https://www.google.com/maps/place/?q=place_id:{place.get('place_id')}",
        "google_place_id": place.get("place_id"),
        "address": place.get("formatted_address", ""),
        "city": city,
        "state": state,
        "country": country,
    }


def discover_leads(query: str, city: Optional[str] = None, state: Optional[str] = None,
                    country: Optional[str] = None, category: Optional[str] = None,
                    max_results: int = 20, fetch_details: bool = True) -> list[dict]:
    """
    High-level entry point the ingestion router calls. Returns a list of
    normalized dicts ready for LeadCreate - does NOT touch the DB (keeps
    this service pure/testable; the router handles dedup + insert).
    """
    places = search_places(query, city, max_results=max_results)
    results = []
    for place in places:
        details = None
        if fetch_details and place.get("place_id"):
            try:
                details = get_place_details(place["place_id"])
            except GoogleMapsError:
                details = None  # still ingest the lead with what Text Search gave us
        results.append(normalize_place(place, details, category or query, city, state, country))
    return results
