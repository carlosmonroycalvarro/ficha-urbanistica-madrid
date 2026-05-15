# -*- coding: utf-8 -*-
"""
Generación de la cédula urbanística con el modelo normalizado
del Ayuntamiento de Madrid (Oficina de Información Urbanística).
"""

import os
from datetime import date
import anthropic

_MODEL = "claude-sonnet-4-6"

_SYSTEM_PROMPT = """\
Eres un técnico urbanista del Ayuntamiento de Madrid especializado en el
Plan General de Ordenación Urbana de Madrid de 1997 (PGOUM97) y su
Compendio de Normas Urbanísticas actualizado a 2025.

Se te proporcionan datos catastrales, datos GIS del PGOUM y el texto
normativo aplicable extraído del Compendio. Tu tarea es redactar una
cédula urbanística siguiendo EXACTAMENTE el modelo normalizado del
Ayuntamiento de Madrid que se indica a continuación.

REGLAS ESTRICTAS:
- Usa ÚNICAMENTE los datos proporcionados. Nunca inventes valores.
- Si un dato no está disponible, escribe: "No consta en la documentación consultada."
- Los valores normativos (edificabilidad, alturas, etc.) deben extraerse
  literalmente del texto del Compendio proporcionado.
- Usa el formato Markdown indicado sin añadir ni eliminar secciones.
- La fecha de emisión es HOY.
- El documento tiene carácter informativo; incluye siempre el pie legal.

FORMATO EXACTO A SEGUIR:

---

# CÉDULA URBANÍSTICA
**Ayuntamiento de Madrid — Área de Gobierno de Urbanismo, Medio Ambiente y Movilidad**
*Oficina de Información Urbanística*

| | |
|---|---|
| **Fecha de emisión** | {fecha} |
| **Carácter** | Informativo — sin efectos jurídicos vinculantes |

---

## I. DATOS DE LA PARCELA

| Campo | Valor |
|---|---|
| **Dirección** | |
| **Distrito** | Madrid |
| **Referencia catastral** | |
| **Superficie de parcela** | m² |
| **Superficie construida** | m² |
| **Uso catastral actual** | |
| **Año de construcción** | |

---

## II. RÉGIMEN URBANÍSTICO

| Campo | Valor |
|---|---|
| **Clasificación del suelo** | Suelo Urbano Consolidado |
| **Calificación urbanística** | |
| **Norma Zonal** | |
| **Grado** | |
| **Número de ordenanza** | |
| **Nivel de protección** | |

---

## III. CONDICIONES DE EDIFICACIÓN
*(Según Compendio de las Normas Urbanísticas del PGOUM — Ed. septiembre 2025)*

| Parámetro | Valor |
|---|---|
| **Edificabilidad neta** | |
| **Número máximo de plantas** | |
| **Altura máxima reguladora** | m |
| **Ocupación máxima** | % |
| **Retranqueo a fachada** | |
| **Retranqueo a linderos** | |
| **Parcela mínima edificable** | m² |
| **Fachada mínima** | m |

---

## IV. USOS URBANÍSTICOS

| Categoría | Descripción |
|---|---|
| **Uso cualificado (principal)** | |
| **Usos compatibles** | |
| **Usos autorizables** | |
| **Usos prohibidos** | |

---

## V. CONDICIONES ESPECIALES Y AFECCIONES

*(Indicar protecciones patrimoniales, afecciones viarias, planes especiales
u otras condiciones singulares aplicables a la parcela)*

---

## VI. OBSERVACIONES

*(Indicar datos no disponibles, limitaciones de la consulta o aclaraciones técnicas)*

---

## VII. DEFINICIÓN DE LOS USOS URBANÍSTICOS

*(Extraer del Compendio la definición completa del uso cualificado y de los usos
compatibles aplicables a esta parcela. Incluir artículo, descripción y condiciones
específicas del uso según la normativa del PGOUM.)*

---

*Este documento tiene carácter exclusivamente informativo y ha sido generado
de forma automatizada a partir de los servicios cartográficos del Catastro,
del PGOUM y del Compendio de las Normas Urbanísticas (ed. septiembre 2025).
La versión oficial del planeamiento se publica en el BOCM. Para trámites
oficiales, solicite cédula urbanística en la Oficina de Información Urbanística
del Ayuntamiento de Madrid (C/ Guatemala, 13).*

---
""".replace("{fecha}", date.today().strftime("%d/%m/%Y"))


def generate_ficha(cadastral: dict, pgoum: dict, address: str = "") -> str:
    """
    Genera la cédula urbanística con el modelo normalizado del Ayuntamiento.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY no está definida. "
            "Configúrala en el panel lateral de la app."
        )

    normas = _fetch_normas(pgoum)
    uso_defs = _fetch_uso_definitions(cadastral)
    user_content = _build_user_message(cadastral, pgoum, address, normas, uso_defs)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=_MODEL,
        max_tokens=3000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text


def _fetch_normas(pgoum: dict) -> str:
    try:
        from notebooklm_query import query_compendio
        zona = pgoum.get("zona_denominacion") or pgoum.get("ordenanza") or ""
        if not zona:
            return ""
        return query_compendio(
            zona=zona,
            numord=str(pgoum.get("numord") or ""),
            cond_edif=str(pgoum.get("cond_edif") or ""),
        )
    except Exception:
        return ""


def _fetch_uso_definitions(cadastral: dict) -> str:
    try:
        from notebooklm_query import query_uso_definition
        uso = cadastral.get("uso") or ""
        if not uso:
            return ""
        return query_uso_definition(uso)
    except Exception:
        return ""


def _build_user_message(cadastral: dict, pgoum: dict,
                        address: str, normas: str, uso_defs: str = "") -> str:
    lines = [
        "Rellena la cédula urbanística normalizada con los siguientes datos.\n",
        f"**Dirección consultada:** {address}\n",
        "## A) DATOS CATASTRALES",
        f"- Referencia catastral: {cadastral.get('refcat', 'No consta')}",
        f"- Dirección catastral: {cadastral.get('address', 'No consta')}",
        f"- Superficie de parcela: {cadastral.get('superficie_parcela', 'No consta')} m²",
        f"- Superficie construida total: {cadastral.get('superficie_construida', 'No consta')} m²",
        f"- Año de construcción: {cadastral.get('anio_construccion', 'No consta')}",
        f"- Uso catastral: {cadastral.get('uso', 'No consta')}",
        "\n## B) DATOS GIS DEL PGOUM",
        f"- Zona y grado: {pgoum.get('zona_denominacion', 'No consta')}",
        f"- Etiqueta zona: {pgoum.get('zona_etiqueta', 'No consta')}",
        f"- Número de ordenanza: {pgoum.get('numord', 'No consta')}",
        f"- Código condición edificación (COND_EDIF): {pgoum.get('cond_edif', 'No consta')}",
        f"- Código NPG: {pgoum.get('crs_npg', 'No consta')}",
    ]
    if pgoum.get("denominacion_dotacion"):
        lines.append(f"- Dotación específica: {pgoum['denominacion_dotacion']}")

    if normas:
        lines.append("\n## C) TEXTO NORMATIVO DEL COMPENDIO PGOUM 2025")
        lines.append(normas)
    else:
        lines.append("\n## C) TEXTO NORMATIVO")
        lines.append("No disponible en este entorno.")

    if uso_defs:
        lines.append("\n## D) DEFINICIÓN DEL USO URBANÍSTICO (Compendio PGOUM 2025)")
        lines.append(uso_defs)

    return "\n".join(lines)
