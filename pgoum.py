"""
Consulta de ordenanza urbanística del PGOUM de Madrid vía sigma.madrid.es.
Dado un punto (lat, lon), devuelve la ordenanza, clasificación del suelo
y condiciones edificatorias que aplican según el Plan General.

Capas verificadas en los servicios ArcGIS REST de sigma.madrid.es:
- PGOUM97/PG_CONDICIONES_EDIFICACION/MapServer/6  → Condiciones de la Edificación
- DESARROLLO_URBANO_ACTUALIZADO/PLANEAMIENTO_URBANISTICO/MapServer/2 → Ámbitos
- PGOUM97/PG_ORDENACION_SIN_AMBITO/MapServer/9   → Dotaciones / Norma Zonal
"""

import re
import requests

_SIGMA_BASE = "https://sigma.madrid.es/hosted/rest/services"

_ENDPOINTS = {
    "condiciones_edificacion": f"{_SIGMA_BASE}/PGOUM97/PG_CONDICIONES_EDIFICACION/MapServer/6",
    "planeamiento_ambitos":    f"{_SIGMA_BASE}/DESARROLLO_URBANO_ACTUALIZADO/PLANEAMIENTO_URBANISTICO/MapServer/2",
    "norma_zonal":             f"{_SIGMA_BASE}/PGOUM97/PG_ORDENACION_SIN_AMBITO/MapServer/9",
}

# Tabla de traducción NUMORD / zona → denominación normalizada
_ZONA_NOMBRES = {
    "1": "Zona 1 — Protección del Patrimonio Histórico",
    "2": "Zona 2 — Protección de Colonias Históricas",
    "3": "Zona 3 — Volumetría Específica",
    "4": "Zona 4 — Edificación en Manzana",
    "5": "Zona 5 — Edificación en Bloques",
    "6": "Zona 6 — Edificación en Cascos Históricos",
    "8": "Zona 8 — Edificación en Vivienda Unifamiliar",
    "9": "Zona 9 — Actividades Económicas",
}


def _parse_numord(numord: str) -> tuple[str, str]:
    """
    Descompone un código NUMORD en (zona_num, grado).
    Ejemplos: '4.1' → ('4','1'), '1.2' → ('1','2'), '9' → ('9',''), '4a' → ('4','a').
    """
    if not numord:
        return "", ""
    s = str(numord).strip()
    m = re.match(r"^(\d+)[.\-_]?([0-9a-zA-Zº°]*)", s)
    if m:
        return m.group(1), m.group(2)
    return s, ""


def _parse_denom(denom: str) -> tuple[str, str]:
    """
    Extrae (zona_num, grado) de cadenas como 'ZONA 4 GRADO 1º' o 'ZONA 1 GRADO 2º'.
    """
    if not denom:
        return "", ""
    m = re.search(r"ZONA\s+(\d+).*?GRADO\s+([0-9]+[ºa-zA-Z]*)", denom.upper())
    if m:
        return m.group(1), m.group(2)
    m2 = re.search(r"ZONA\s+(\d+)", denom.upper())
    if m2:
        return m2.group(1), ""
    return "", ""


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

    # ── Capa 1: Condiciones de la Edificación (PGOUM97 layer 6) ──────────
    try:
        feats = _query_point(_ENDPOINTS["condiciones_edificacion"], lon, lat)
        if feats:
            attrs = feats[0]
            result["numord"]    = str(attrs.get("NUMORD") or "").strip()
            result["codmanzana"]= str(attrs.get("CODMANZANA") or "").strip()
            result["cond_edif"] = attrs.get("COND_EDIF", "")
            result["coef_z"]    = str(attrs.get("COEF_Z") or "").strip()
            result["raw_condiciones"] = {k: v for k, v in attrs.items()
                                         if v not in (None, "Null", "")}
    except Exception as exc:
        result["error_condiciones"] = str(exc)

    # ── Capa 2: Ámbitos del Planeamiento Actualizado ──────────────────────
    try:
        feats = _query_point(_ENDPOINTS["planeamiento_ambitos"], lon, lat)
        if feats:
            attrs = feats[0]
            etiq  = str(attrs.get("AMB_TX_ETIQ") or "").strip()
            denom = str(attrs.get("AMB_TX_DENOM") or "").strip()
            result["zona_etiqueta"]    = etiq
            result["zona_denominacion"]= denom
            # Parsear zona y grado desde la denominación oficial (más fiable que NUMORD)
            zn, gr = _parse_denom(denom)
            if not zn and etiq:          # fallback: etiqueta "4.1" → zona 4, grado 1
                zn, gr = _parse_numord(etiq)
            result["zona_numero"] = zn
            result["zona_grado"]  = gr
            result["zona_nombre"] = _ZONA_NOMBRES.get(zn, denom)
            result["raw_planeamiento"] = {k: v for k, v in attrs.items()
                                          if v not in (None, "Null", "")}
    except Exception as exc:
        result["error_planeamiento"] = str(exc)

    # Si aún no tenemos zona/grado, intentar con NUMORD de condiciones
    if not result.get("zona_numero") and result.get("numord"):
        zn, gr = _parse_numord(result["numord"])
        result["zona_numero"] = zn
        result["zona_grado"]  = gr
        result["zona_nombre"] = _ZONA_NOMBRES.get(zn, result["numord"])

    # ── Capa 3: Norma Zonal / Dotaciones (PGOUM97 sin ámbito layer 9) ────
    try:
        feats = _query_point(_ENDPOINTS["norma_zonal"], lon, lat)
        if feats:
            attrs = feats[0]
            result["crs_npg"]              = str(attrs.get("CRS_NPG") or "").strip()
            result["denominacion_dotacion"] = str(attrs.get("DENOMINA") or "").strip()
            result["codigo_dotacion"]       = str(attrs.get("CODIGO") or "").strip()
            result["raw_norma_zonal"] = {k: v for k, v in attrs.items()
                                         if v not in (None, "Null", "")}
    except Exception as exc:
        result["error_norma_zonal"] = str(exc)

    # ── Campo consolidado "ordenanza" ────────────────────────────────────
    # Preferir denominación completa con zona+grado cuando esté disponible
    if result.get("zona_nombre") and result.get("zona_grado"):
        result["ordenanza"] = f"{result['zona_nombre']} — Grado {result['zona_grado']}"
    elif result.get("zona_nombre"):
        result["ordenanza"] = result["zona_nombre"]
    elif result.get("zona_denominacion"):
        result["ordenanza"] = result["zona_denominacion"]
    elif result.get("denominacion_dotacion"):
        result["ordenanza"] = result["denominacion_dotacion"]
    else:
        result["ordenanza"] = result.get("numord") or "No disponible"

    return result
