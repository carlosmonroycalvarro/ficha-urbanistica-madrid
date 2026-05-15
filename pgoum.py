"""
Consulta de ordenanza urbanística del PGOUM de Madrid vía sigma.madrid.es.
Dado un punto (lat, lon), devuelve la ordenanza, clasificación del suelo
y condiciones edificatorias que aplican según el Plan General.

Capas verificadas en los servicios ArcGIS REST de sigma.madrid.es:
- PGOUM97/PG_CONDICIONES_EDIFICACION/MapServer/6  → Condiciones de la Edificación
- DESARROLLO_URBANO_ACTUALIZADO/PLANEAMIENTO_URBANISTICO/MapServer/2 → Ámbitos
- PGOUM97/PG_ORDENACION_SIN_AMBITO/MapServer/9   → Dotaciones / Norma Zonal
"""

import requests

_SIGMA_BASE = "https://sigma.madrid.es/hosted/rest/services"

_ENDPOINTS = {
    "condiciones_edificacion": f"{_SIGMA_BASE}/PGOUM97/PG_CONDICIONES_EDIFICACION/MapServer/6",
    "planeamiento_ambitos": f"{_SIGMA_BASE}/DESARROLLO_URBANO_ACTUALIZADO/PLANEAMIENTO_URBANISTICO/MapServer/2",
    "norma_zonal": f"{_SIGMA_BASE}/PGOUM97/PG_ORDENACION_SIN_AMBITO/MapServer/9",
}


def _query_point(endpoint_url: str, lon: float, lat: float) -> list[dict]:
    """Consulta una capa ArcGIS MapServer por intersección de punto (lon, lat en EPSG:4326)."""
    url = f"{endpoint_url}/query"
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "*",
        "returnGeometry": "false",
        "f": "json",
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(f"ArcGIS error {data['error'].get('code')}: {data['error'].get('message')}")
    return [feat.get("attributes", {}) for feat in data.get("features", [])]


def get_pgoum_data(lat: float, lon: float) -> dict:
    """
    Devuelve ordenanza y condiciones urbanísticas para la coordenada dada.

    Campos clave en el resultado:
    - condiciones_edificacion: código NUMORD (número de ordenanza)
    - zona_denominacion: nombre de zona del planeamiento actualizado
    - zona_etiqueta: etiqueta corta de zona (ej. "1.1")
    - crs_npg: código de condición urbanística (ej. "IE")
    - raw_*: todos los atributos devueltos por cada capa
    """
    result: dict = {}

    # Capa: Condiciones de la Edificación (PGOUM97)
    try:
        feats = _query_point(_ENDPOINTS["condiciones_edificacion"], lon, lat)
        if feats:
            attrs = feats[0]
            result["numord"] = attrs.get("NUMORD", "")
            result["codmanzana"] = attrs.get("CODMANZANA", "")
            result["cond_edif"] = attrs.get("COND_EDIF", "")
            result["raw_condiciones"] = {k: v for k, v in attrs.items() if v not in (None, "Null", "")}
    except Exception as exc:
        result["error_condiciones"] = str(exc)

    # Capa: Ámbitos del Planeamiento Actualizado
    try:
        feats = _query_point(_ENDPOINTS["planeamiento_ambitos"], lon, lat)
        if feats:
            attrs = feats[0]
            result["zona_etiqueta"] = attrs.get("AMB_TX_ETIQ", "")
            result["zona_denominacion"] = attrs.get("AMB_TX_DENOM", "")
            result["raw_planeamiento"] = {k: v for k, v in attrs.items() if v not in (None, "Null", "")}
    except Exception as exc:
        result["error_planeamiento"] = str(exc)

    # Capa: Norma Zonal / Dotaciones (PGOUM97 sin ámbito)
    try:
        feats = _query_point(_ENDPOINTS["norma_zonal"], lon, lat)
        if feats:
            attrs = feats[0]
            result["crs_npg"] = attrs.get("CRS_NPG", "")
            result["denominacion_dotacion"] = attrs.get("DENOMINA", "")
            result["codigo_dotacion"] = attrs.get("CODIGO", "")
            result["raw_norma_zonal"] = {k: v for k, v in attrs.items() if v not in (None, "Null", "")}
    except Exception as exc:
        result["error_norma_zonal"] = str(exc)

    # Campo consolidado "ordenanza" para la ficha
    result["ordenanza"] = (
        result.get("zona_denominacion")
        or result.get("denominacion_dotacion")
        or result.get("numord")
        or "No disponible"
    )

    return result
