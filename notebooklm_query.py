# -*- coding: utf-8 -*-
"""
Consulta las condiciones normativas del PGOUM.
Fuente preferida: compendio_zonas.json (extraído del PDF local).
Fuente alternativa: cuaderno NotebookLM (solo en local con CLI instalada).
"""

import json
import subprocess
from pathlib import Path

_NLM_BIN     = str(Path.home() / ".notebooklm-venv" / "Scripts" / "notebooklm.exe")
_NOTEBOOK_ID  = "08e2124c-9213-4d02-97ec-82a5f90323d8"
_JSON_PATH    = Path(__file__).parent / "compendio_zonas.json"
_USOS_PATH    = Path(__file__).parent / "compendio_usos.json"

# Mapa uso catastral / GIS → clave en compendio_usos.json
_USO_MAP = {
    "residencial":              "Residencial",
    "vivienda":                 "Residencial",
    "industrial":               "Industrial",
    "almacen":                  "Industrial",
    "almacenamiento":           "Industrial",
    "garaje":                   "Garaje-Aparcamiento",
    "aparcamiento":             "Garaje-Aparcamiento",
    "oficina":                  "Servicios Terciarios",
    "oficinas":                 "Servicios Terciarios",
    "comercial":                "Servicios Terciarios",
    "comercio":                 "Servicios Terciarios",
    "terciario":                "Servicios Terciarios",
    "hotelero":                 "Servicios Terciarios",
    "dotacional":               "Dotacional Servicios Colectivos",
    "educativo":                "Dotacional Servicios Colectivos",
    "sanitario":                "Dotacional Servicios Colectivos",
    "deportivo":                "Dotacional Servicios Colectivos",
    "cultural":                 "Dotacional Servicios Colectivos",
    "religioso":                "Dotacional Servicios Colectivos",
    "infraestructural":         "Dotacional Infraestructural",
    "infraestructura":          "Dotacional Infraestructural",
    "via publica":              "Dotacional Via Publica",
    "vial":                     "Dotacional Via Publica",
    "transporte":               "Dotacional Transporte",
}

# Mapa de normalización: clave GIS → clave en el JSON
_ZONA_MAP = {
    "1": "ZONA 1 - Proteccion del Patrimonio Historico",
    "2": "ZONA 2 - Proteccion de Colonias Historicas",
    "3": "ZONA 3 - Volumetria Especifica",
    "4": "ZONA 4 - Edificacion en Manzana",
    "5": "ZONA 5 - Edificacion en Bloques",
    "6": "ZONA 6 - Edificacion en Cascos Historicos",
    "8": "ZONA 8 - Edificacion en Vivienda",
    "9": "ZONA 9 - Actividades Economicas",
}


def query_uso_definition(uso_str: str) -> str:
    """Devuelve el texto definitorio del uso desde compendio_usos.json."""
    if not _USOS_PATH.exists():
        return ""
    try:
        with open(_USOS_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ""
    uso_lower = uso_str.lower().strip()
    for key, json_key in _USO_MAP.items():
        if key in uso_lower:
            return data.get(json_key, "")[:2500]
    return ""


def _zona_number(zona_str: str) -> str:
    """Extrae el número de zona de una cadena como 'ZONA 1 GRADO 1ª' o '4.1'."""
    import re
    # Formato canónico "ZONA N ..."
    m = re.search(r"ZONA\s+(\d+)", zona_str.upper())
    if m:
        return m.group(1)
    # Formato etiqueta "4.1" o "4"
    m2 = re.match(r"^(\d+)", zona_str.strip())
    return m2.group(1) if m2 else ""


def query_compendio(zona: str, numord: str = "", cond_edif: str = "") -> str:
    """
    Devuelve el texto normativo para la zona dada.
    Intenta en orden:
      1. JSON local (compendio_zonas.json) — funciona en cualquier entorno
      2. NotebookLM CLI — solo en local con el CLI instalado
    """
    # 1. JSON local
    texto_zona = _query_json(zona)
    if texto_zona:
        return texto_zona

    # 2. NotebookLM CLI como fallback
    return _query_notebooklm(zona, numord, cond_edif)


def _query_json(zona: str) -> str:
    """Busca el texto normativo en el JSON extraído del PDF."""
    if not _JSON_PATH.exists():
        return ""
    try:
        with open(_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ""

    num = _zona_number(zona)
    if not num:
        return ""

    clave = _ZONA_MAP.get(num, "")
    if not clave or clave not in data:
        return ""

    texto = data[clave]
    # Limitar a 6000 chars para no saturar el contexto de Claude
    return texto[:6000]


def _query_notebooklm(zona: str, numord: str, cond_edif: str) -> str:
    """Consulta el cuaderno NotebookLM (solo disponible en local)."""
    if not Path(_NLM_BIN).exists():
        return ""
    try:
        subprocess.run(
            [_NLM_BIN, "use", _NOTEBOOK_ID],
            capture_output=True, timeout=30,
        )
        detalles = ""
        if numord:
            detalles += f" (número de ordenanza {numord})"
        if cond_edif:
            detalles += f", condición código {cond_edif}"

        pregunta = (
            f"Para la {zona}{detalles} del PGOUM de Madrid, "
            f"extrae del Compendio los parámetros exactos: "
            f"edificabilidad, plantas y altura máxima, ocupación, "
            f"retranqueos, usos permitidos, parcela mínima. "
            f"Responde en español con valores literales."
        )
        result = subprocess.run(
            [_NLM_BIN, "ask", pregunta],
            capture_output=True, timeout=120,
        )
        output = result.stdout.decode("utf-8", errors="replace")
        if "Answer:" in output:
            answer = output.split("Answer:", 1)[1]
            lines = [l for l in answer.splitlines()
                     if not l.startswith("Resumed conversation")]
            return "\n".join(lines).strip()
    except Exception:
        pass
    return ""
