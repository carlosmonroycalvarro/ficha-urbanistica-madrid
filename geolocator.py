"""
Geocodificación de direcciones usando Nominatim (OpenStreetMap).
Convierte texto de dirección en coordenadas geográficas (lat, lon).
"""

import requests

_NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "ficha-urbanistica-madrid/1.0"}


def reverse_geocode(lat: float, lon: float) -> dict:
    """
    Dado lat/lon devuelve la dirección más cercana.
    Resultado: {'lat', 'lon', 'display_name', 'address_short'}
    """
    resp = requests.get(
        "https://nominatim.openstreetmap.org/reverse",
        params={"lat": lat, "lon": lon, "format": "json", "addressdetails": 1},
        headers=_HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    r = resp.json()
    if "error" in r:
        raise ValueError(f"No se encontró dirección para lat={lat}, lon={lon}")
    addr = r.get("address", {})
    road = addr.get("road", "")
    number = addr.get("house_number", "")
    short = f"{road} {number}".strip() if road else r.get("display_name", "")
    return {
        "lat": float(r["lat"]),
        "lon": float(r["lon"]),
        "display_name": r.get("display_name", ""),
        "address_short": short,
    }


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
