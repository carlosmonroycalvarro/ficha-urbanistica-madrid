"""
Geocodificación de direcciones usando Nominatim (OpenStreetMap).
Convierte texto de dirección en coordenadas geográficas (lat, lon).
"""

import requests

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "ficha-urbanistica-madrid/1.0"}


def geocode_address(address: str, city: str = "Madrid", country: str = "Spain") -> dict:
    """
    Devuelve {'lat': float, 'lon': float, 'display_name': str} o lanza ValueError.
    """
    query = f"{address}, {city}, {country}"
    resp = requests.get(
        _NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1, "addressdetails": 1},
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json()
    if not results:
        raise ValueError(f"No se encontró la dirección: {query!r}")
    r = results[0]
    return {
        "lat": float(r["lat"]),
        "lon": float(r["lon"]),
        "display_name": r.get("display_name", ""),
    }
