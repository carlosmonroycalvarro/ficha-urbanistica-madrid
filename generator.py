"""
Generación de la ficha urbanística usando la API de Claude (Anthropic).
Recibe los datos catastrales y del PGOUM y devuelve un texto estructurado
listo para incluir en informes.
"""

import os
import anthropic

_MODEL = "claude-sonnet-4-6"

_SYSTEM_PROMPT = """\
Eres un arquitecto urbanista experto en el planeamiento general de Madrid (PGOUM).
Cuando el usuario te facilite datos catastrales y urbanísticos de una parcela,
redacta una ficha urbanística profesional y concisa en español.

La ficha debe incluir los siguientes apartados si los datos están disponibles:
1. **Identificación de la parcela** — referencia catastral, dirección, municipio
2. **Datos catastrales** — superficie de parcela (m²), superficie construida (m²), uso
3. **Clasificación y calificación del suelo** — clasificación, calificación, zona
4. **Ordenanza de aplicación** — código y nombre de la ordenanza del PGOUM
5. **Condiciones de edificación** — edificabilidad (m²/m²), altura máxima (plantas/metros), usos permitidos
6. **Observaciones** — cualquier dato relevante o incompleto

Si algún dato no está disponible, indícalo claramente. No inventes datos.
Usa formato Markdown con negrita para los títulos de cada apartado.
"""


def generate_ficha(cadastral: dict, pgoum: dict, address: str = "") -> str:
    """
    Llama a la Claude API y devuelve el texto de la ficha urbanística.
    Requiere ANTHROPIC_API_KEY en las variables de entorno.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY no está definida. "
            "Ejecútala con: set ANTHROPIC_API_KEY=sk-ant-..."
        )

    client = anthropic.Anthropic(api_key=api_key)

    user_content = _build_user_message(cadastral, pgoum, address)

    message = client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text


def _build_user_message(cadastral: dict, pgoum: dict, address: str) -> str:
    lines = ["Por favor, genera la ficha urbanística con los siguientes datos:\n"]

    if address:
        lines.append(f"**Dirección buscada:** {address}")

    lines.append("\n### Datos catastrales")
    lines.append(f"- Referencia catastral: {cadastral.get('refcat', 'No disponible')}")
    lines.append(f"- Dirección catastral: {cadastral.get('address', 'No disponible')}")
    lines.append(f"- Municipio: {cadastral.get('municipality', 'No disponible')}")
    lines.append(f"- Provincia: {cadastral.get('province', 'No disponible')}")
    lines.append(f"- Superficie de parcela: {cadastral.get('superficie_parcela', 'No disponible')} m²")
    lines.append(f"- Superficie construida: {cadastral.get('superficie_construida', 'No disponible')} m²")
    lines.append(f"- Uso: {cadastral.get('uso', 'No disponible')}")

    lines.append("\n### Datos urbanísticos (PGOUM)")
    lines.append(f"- Ordenanza / zona: {pgoum.get('ordenanza', 'No disponible')}")
    lines.append(f"- Zona etiqueta: {pgoum.get('zona_etiqueta', 'No disponible')}")
    lines.append(f"- Zona denominación: {pgoum.get('zona_denominacion', 'No disponible')}")
    lines.append(f"- Condición edificación (COND_EDIF): {pgoum.get('cond_edif', 'No disponible')}")
    lines.append(f"- Número de ordenanza (NUMORD): {pgoum.get('numord', 'No disponible')}")
    lines.append(f"- Código manzana: {pgoum.get('codmanzana', 'No disponible')}")
    lines.append(f"- Código condición urbanística (CRS_NPG): {pgoum.get('crs_npg', 'No disponible')}")
    lines.append(f"- Denominación dotación: {pgoum.get('denominacion_dotacion', 'No disponible')}")

    # Incluye todos los campos raw si tienen valor (pueden aportar info adicional)
    raw_cond = pgoum.get("raw_condiciones", {})
    raw_plan = pgoum.get("raw_planeamiento", {})
    raw_norma = pgoum.get("raw_norma_zonal", {})
    extra = {k: v for d in [raw_cond, raw_plan, raw_norma] for k, v in d.items() if v not in (None, "", "Null")}
    if extra:
        lines.append("\n### Atributos adicionales del PGOUM")
        for k, v in list(extra.items())[:20]:  # limita para no saturar el contexto
            lines.append(f"- {k}: {v}")

    return "\n".join(lines)
