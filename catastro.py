"""
Consulta al Servicio de Catastro (Sede Electrónica del Catastro).
Flujo: coordenadas → referencia catastral → datos de la parcela (superficies).

Nota: el API devuelve XML; la búsqueda por coordenadas exactas puede fallar
si el punto cae fuera de la parcela — se usa Consulta_RCCOOR_Distancia como
fallback automático.
"""

import requests
import xml.etree.ElementTree as ET

_OVC_BASE = "http://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCoordenadas.svc/rest"
_INSPIRE_WFS = "http://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
_NS = "http://www.catastro.meh.es/"


def _text(root, path: str) -> str:
    """Extrae texto de un elemento XML dado su path con namespace."""
    elem = root.find(path, {"c": _NS})
    return elem.text.strip() if elem is not None and elem.text else ""


def get_cadastral_ref(lat: float, lon: float) -> dict:
    """
    Dado lat/lon (EPSG:4326), devuelve la referencia catastral y datos básicos.
    Usa fallback por distancia (50m) si las coordenadas exactas no coinciden.
    """
    # Intento 1: coordenadas exactas
    result = _query_rccoor(lon, lat)
    if result:
        return result

    # Intento 2: búsqueda por distancia (radio 50m)
    result = _query_rccoor_distancia(lon, lat)
    if result:
        return result

    raise ValueError(
        f"No se encontró referencia catastral para lat={lat}, lon={lon}. "
        "La coordenada puede estar fuera del término municipal de Madrid."
    )


def _query_rccoor(lon: float, lat: float) -> dict | None:
    """Llama a Consulta_RCCOOR y devuelve dict o None si hay error."""
    url = f"{_OVC_BASE}/Consulta_RCCOOR"
    resp = requests.get(
        url,
        params={"CoorX": lon, "CoorY": lat, "SRS": "EPSG:4326"},
        timeout=15,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    ns = {"c": _NS}

    err_cod = _text(root, "c:lerr/c:err/c:cod")
    if err_cod and err_cod != "0":
        return None

    return _parse_coord_result(root)


def _query_rccoor_distancia(lon: float, lat: float, distancia: int = 50) -> dict | None:
    """Fallback: busca la parcela más cercana en un radio de `distancia` metros."""
    url = f"{_OVC_BASE}/Consulta_RCCOOR_Distancia"
    resp = requests.get(
        url,
        params={"CoorX": lon, "CoorY": lat, "SRS": "EPSG:4326", "Distancia": distancia},
        timeout=15,
    )
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    err_cod = _text(root, "c:lerr/c:err/c:cod")
    if err_cod and err_cod != "0":
        return None

    # La respuesta de Distancia tiene estructura diferente: .../coordd/lpcd/pcd
    ns = {"c": _NS}
    pcds = root.findall(".//c:pcd", ns)
    if not pcds:
        return None

    pcd = pcds[0]
    pc1 = _text(pcd, "c:pc/c:pc1")
    pc2 = _text(pcd, "c:pc/c:pc2")
    refcat = pc1 + pc2

    return {
        "refcat": refcat,
        "address": _text(pcd, "c:ldt"),
        "municipality": "",
        "province": "",
    }


def _parse_coord_result(root) -> dict | None:
    """Extrae los campos de la respuesta XML de OVC coordenadas."""
    ns = {"c": _NS}
    coords = root.findall(".//c:coord", ns)
    if not coords:
        return None

    coord = coords[0]

    pc1 = _text(coord, "c:pc/c:pc1")
    pc2 = _text(coord, "c:pc/c:pc2")
    refcat = pc1 + pc2

    return {
        "refcat": refcat,
        "address": _text(coord, "c:ldt"),
        "municipality": _text(coord, "c:lmun"),
        "province": _text(coord, "c:lprov"),
    }


_OVC_CALLEJERO = "http://ovc.catastro.meh.es/OVCServWeb/OVCWcfCallejero/COVCCallejero.svc/rest"


def get_inmueble_data(refcat: str) -> dict:
    """
    Consulta Consulta_DNPRC para obtener datos completos del inmueble:
    superficie construida total (sfc), superficie suelo (ss), uso, año construcción.
    """
    url = f"{_OVC_CALLEJERO}/Consulta_DNPRC"
    resp = requests.get(url, params={"RefCat": refcat}, timeout=15)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    result: dict = {}
    ns = {"c": _NS}

    err_cod = _text(root, "c:lerr/c:err/c:cod")
    if err_cod and err_cod != "0":
        return result

    # bico/bi es el bloque principal del inmueble
    bi = root.find(".//c:bi", ns)
    if bi is None:
        return result

    sfc = _text(bi, "c:debi/c:sfc")   # superficie construida total
    ss  = _text(bi, "c:debi/c:slt")   # superficie suelo (puede aparecer como slt)
    if not ss:
        ss = _text(bi, "c:debi/c:ss")
    uso = _text(bi, "c:debi/c:luso")
    ant = _text(bi, "c:debi/c:ant")   # año construcción

    if sfc:
        try:
            result["superficie_construida"] = float(sfc)
        except ValueError:
            pass
    if ss:
        try:
            result["superficie_suelo_dnp"] = float(ss)
        except ValueError:
            pass
    if uso:
        result["uso"] = uso
    if ant:
        result["anio_construccion"] = ant

    return result


def get_parcel_surfaces(refcat: str) -> dict:
    """
    Dado una referencia catastral, consulta el WFS INSPIRE para obtener
    superficie de parcela y superficie construida total.
    """
    params = {
        "SERVICE": "WFS",
        "REQUEST": "GetFeature",
        "VERSION": "2.0.0",
        "STOREDQUERY_ID": "GetParcel",
        "REFCAT": refcat,
        "SRSNAME": "EPSG:4326",
    }
    resp = requests.get(_INSPIRE_WFS, params=params, timeout=15)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    result: dict = {
        "superficie_parcela": None,
        "superficie_construida": None,
        "uso": None,
        "centroid_lat": None,
        "centroid_lon": None,
    }

    for elem in root.iter():
        localname = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if localname == "areaValue" and result["superficie_parcela"] is None:
            try:
                result["superficie_parcela"] = float(elem.text)
            except (TypeError, ValueError):
                pass
        if localname in ("officialAreaValue",) and result["superficie_construida"] is None:
            try:
                result["superficie_construida"] = float(elem.text)
            except (TypeError, ValueError):
                pass
        if localname == "currentUse" and result["uso"] is None:
            result["uso"] = elem.text
        # El centroide de la parcela está en el elemento <pos> (lat lon en EPSG:4326)
        if localname == "pos" and result["centroid_lat"] is None:
            try:
                parts = elem.text.strip().split()
                result["centroid_lat"] = float(parts[0])
                result["centroid_lon"] = float(parts[1])
            except (IndexError, ValueError):
                pass
        # Polígono de la parcela: posList tiene pares "lat lon lat lon ..."
        if localname == "posList" and "parcel_polygon" not in result:
            try:
                nums = list(map(float, elem.text.strip().split()))
                # pares (lat, lon)
                coords = [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
                if len(coords) >= 3:
                    result["parcel_polygon"] = coords
            except (ValueError, IndexError):
                pass

    return result


def get_full_cadastral_data(lat: float, lon: float) -> dict:
    """
    Punto de entrada principal: devuelve todos los datos catastrales disponibles.
    """
    ref_data = get_cadastral_ref(lat, lon)
    refcat = ref_data.get("refcat", "")
    surfaces: dict = {}
    if refcat:
        try:
            surfaces = get_parcel_surfaces(refcat)
        except Exception as exc:
            surfaces = {"error_surfaces": str(exc)}

    # Enriquecer con datos del inmueble (superficie construida, uso, año)
    inmueble: dict = {}
    if refcat:
        try:
            inmueble = get_inmueble_data(refcat)
        except Exception as exc:
            inmueble = {"error_inmueble": str(exc)}

    merged = {**ref_data, **surfaces, **inmueble}
    # superficie_parcela desde WFS INSPIRE tiene prioridad; si no, usar slt del inmueble
    if not merged.get("superficie_parcela") and merged.get("superficie_suelo_dnp"):
        merged["superficie_parcela"] = merged["superficie_suelo_dnp"]
    return merged
