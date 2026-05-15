# -*- coding: utf-8 -*-
"""
Exportación de la cédula urbanística a PDF.
Respeta el modelo normalizado del Ayuntamiento de Madrid.
"""

from datetime import date
from fpdf import FPDF

_CHAR_MAP = str.maketrans({
    "—": "-",   # em dash —
    "–": "-",   # en dash –
    "‘": "'",   # left single quote '
    "’": "'",   # right single quote '
    "“": '"',   # left double quote "
    "”": '"',   # right double quote "
    "•": "-",   # bullet •
    "…": "...", # ellipsis …
    "²": "2",   # superscript 2 ²
    "³": "3",   # superscript 3 ³
    "º": "o",   # ordinal masculine º
    "ª": "a",   # ordinal feminine ª
    "€": "EUR", # euro sign €
})


def _s(text) -> str:
    """Sanitiza texto para Helvetica (Latin-1): sustituye caracteres fuera de rango."""
    if not text:
        return ""
    text = str(text).translate(_CHAR_MAP)
    return text.encode("latin-1", errors="replace").decode("latin-1")


class CedulaPDF(FPDF):

    def header(self):
        # Banda azul institucional
        self.set_fill_color(0, 90, 170)
        self.rect(0, 0, 210, 18, 'F')
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 4)
        self.cell(130, 6, "CEDULA URBANISTICA", ln=0)
        self.set_font("Helvetica", "", 8)
        self.set_xy(10, 11)
        self.cell(190, 5,
                  "Ayuntamiento de Madrid  |  Area de Gobierno de Urbanismo, "
                  "Medio Ambiente y Movilidad  |  Oficina de Informacion Urbanistica",
                  ln=0)
        self.set_text_color(0, 0, 0)
        self.ln(12)

    def footer(self):
        self.set_y(-18)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(100, 100, 100)
        self.set_fill_color(240, 240, 240)
        self.rect(0, self.get_y(), 210, 18, 'F')
        self.set_x(10)
        self.multi_cell(
            190, 4,
            "Documento de caracter informativo generado automaticamente. "
            "Sin efectos juridicos vinculantes. "
            "La version oficial del planeamiento se publica en el BOCM. "
            f"Emitido el {date.today().strftime('%d/%m/%Y')}  |  Pag. {self.page_no()}",
            align="C",
        )
        self.set_text_color(0, 0, 0)

    # ── Helpers de maquetación ──────────────────────────────────────────

    def section_header(self, roman: str, title: str):
        self.ln(3)
        self.set_fill_color(0, 90, 170)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)
        self.cell(0, 7, _s(f"  {roman}. {title.upper()}"), fill=True,
                  new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def field(self, label: str, value: str, col_w: int = 65):
        self.set_font("Helvetica", "B", 8)
        self.set_x(12)
        self.set_fill_color(235, 242, 255)
        self.cell(col_w, 6, _s(label), fill=True, border=1)
        self.set_font("Helvetica", "", 8)
        self.set_fill_color(255, 255, 255)
        val = _s(value) if value and str(value) not in ("None", "null") \
            else "No consta en la documentacion consultada."
        self.multi_cell(0, 6, val, fill=True, border=1)

    def two_fields(self, label1, val1, label2, val2, col_w=65):
        half = (self.w - 24) / 2
        for label, val in [(label1, val1), (label2, val2)]:
            self.set_font("Helvetica", "B", 8)
            self.set_fill_color(235, 242, 255)
            self.cell(col_w, 6, _s(label), fill=True, border=1)
            self.set_font("Helvetica", "", 8)
            self.set_fill_color(255, 255, 255)
            v = _s(val) if val and str(val) not in ("None", "null") \
                else "No consta."
            self.cell(half - col_w, 6, v, fill=True, border=1)
        self.ln()

    def note_box(self, text: str):
        if not text or text.strip() == "":
            text = "Sin observaciones."
        self.set_font("Helvetica", "I", 8)
        self.set_fill_color(250, 250, 240)
        self.set_x(12)
        self.multi_cell(186, 5, _s(text.strip()), fill=True, border=1)

    def legal_note(self):
        self.ln(4)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(100, 100, 100)
        self.set_x(12)
        self.multi_cell(
            186, 4,
            _s("Este documento tiene caracter exclusivamente informativo y ha sido "
               "generado de forma automatizada a partir de los servicios cartograficos "
               "del Catastro, del PGOUM y del Compendio de las Normas Urbanisticas "
               "(ed. septiembre 2025). Para tramites oficiales, solicite cedula urbanistica "
               "en la Oficina de Informacion Urbanistica del Ayuntamiento de Madrid "
               "(C/ Guatemala, 13)."),
            border=0,
        )
        self.set_text_color(0, 0, 0)


def generate_pdf(cat: dict, pgoum: dict, cedula_md: str,
                 address: str = "") -> bytes:
    """
    Genera el PDF de la cédula urbanística y devuelve los bytes.
    Si se dispone del texto Markdown (cedula_md), lo parsea para extraer
    los valores de cada apartado. Si no, usa los dicts directamente.
    """
    pdf = CedulaPDF()
    pdf.set_margins(10, 22, 10)
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.add_page()

    # Extraer valores del Markdown generado por Claude (si existe)
    vals = _parse_markdown_table(cedula_md) if cedula_md else {}

    def v(key_md: str, key_dict=None, suffix=""):
        """Obtiene valor del Markdown o del dict de fallback, sanitizado para Latin-1."""
        val = vals.get(key_md, "")
        if not val and key_dict:
            raw = cat.get(key_dict) or pgoum.get(key_dict, "")
            val = str(raw) if raw and str(raw) != "None" else ""
        return _s((val + suffix).strip()) if val else ""

    # ── Cabecera del documento ──────────────────────────────────────────
    pdf.set_font("Helvetica", "", 8)
    pdf.set_x(12)
    pdf.cell(80, 5, _s(f"Direccion consultada: {address}"))
    pdf.cell(0, 5, _s(f"Fecha: {date.today().strftime('%d/%m/%Y')}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    # ── I. DATOS DE LA PARCELA ──────────────────────────────────────────
    pdf.section_header("I", "Datos de la parcela")
    pdf.field("Direccion", v("Dirección", "address"))
    pdf.field("Referencia catastral",
              v("Referencia catastral", "refcat"))
    pdf.two_fields(
        "Superficie de parcela",
        v("Superficie de parcela", "superficie_parcela", " m2"),
        "Superficie construida",
        v("Superficie construida", "superficie_construida", " m2"),
    )
    pdf.two_fields(
        "Uso catastral",
        v("Uso catastral actual", "uso"),
        "Ano de construccion",
        v("Año de construcción", "anio_construccion"),
    )

    # ── II. RÉGIMEN URBANÍSTICO ─────────────────────────────────────────
    pdf.section_header("II", "Regimen urbanistico")
    pdf.field("Clasificacion del suelo",
              v("Clasificación del suelo") or "Suelo Urbano Consolidado")
    pdf.field("Calificacion urbanistica",
              v("Calificación urbanística", "zona_denominacion"))
    pdf.two_fields(
        "Norma Zonal",
        v("Norma Zonal", "zona_denominacion"),
        "Grado",
        v("Grado", "zona_etiqueta"),
    )
    pdf.two_fields(
        "Numero de ordenanza",
        v("Número de ordenanza", "numord"),
        "Nivel de proteccion",
        v("Nivel de protección", "crs_npg"),
    )

    # ── III. CONDICIONES DE EDIFICACIÓN ────────────────────────────────
    pdf.section_header("III", "Condiciones de edificacion")
    pdf.field("Edificabilidad neta",
              v("Edificabilidad neta"))
    pdf.two_fields(
        "Num. maximo de plantas",
        v("Número máximo de plantas"),
        "Altura maxima reguladora",
        v("Altura máxima reguladora"),
    )
    pdf.two_fields(
        "Ocupacion maxima",
        v("Ocupación máxima"),
        "Parcela minima edificable",
        v("Parcela mínima edificable"),
    )
    pdf.two_fields(
        "Retranqueo a fachada",
        v("Retranqueo a fachada"),
        "Retranqueo a linderos",
        v("Retranqueo a linderos"),
    )

    # ── IV. USOS URBANÍSTICOS ───────────────────────────────────────────
    pdf.section_header("IV", "Usos urbanisticos")
    pdf.field("Uso cualificado (principal)", v("Uso cualificado (principal)"))
    pdf.field("Usos compatibles",           v("Usos compatibles"))
    pdf.field("Usos autorizables",          v("Usos autorizables"))
    pdf.field("Usos prohibidos",            v("Usos prohibidos"))

    # ── V. CONDICIONES ESPECIALES ───────────────────────────────────────
    pdf.section_header("V", "Condiciones especiales y afecciones")
    esp = v("Condiciones especiales")
    if pgoum.get("denominacion_dotacion") and not esp:
        esp = f"Dotacion especifica: {pgoum['denominacion_dotacion']}"
    pdf.note_box(esp or "Sin afecciones especiales identificadas.")

    # ── VI. OBSERVACIONES ───────────────────────────────────────────────
    pdf.section_header("VI", "Observaciones")
    pdf.note_box(v("Observaciones"))

    # ── VII. DEFINICIÓN DE LOS USOS URBANÍSTICOS ────────────────────────
    pdf.section_header("VII", "Definicion de los usos urbanisticos")
    uso_def = v("Uso cualificado (principal)")
    # Intentar extraer la definición completa del uso desde el Markdown
    uso_def_text = ""
    if cedula_md:
        import re
        m = re.search(
            r"##\s*VII\.\s*DEFINICI[ÓO]N[^\n]*\n(.*?)(?=\n##|\Z)",
            cedula_md, re.DOTALL | re.IGNORECASE,
        )
        if m:
            uso_def_text = m.group(1).strip()
    pdf.note_box(uso_def_text or "No consta en la documentacion consultada.")

    # Nota legal
    pdf.legal_note()

    return bytes(pdf.output())


def _parse_markdown_table(md: str) -> dict:
    """
    Extrae pares clave-valor de las tablas Markdown de la cédula.
    Formato esperado: | **Clave** | Valor |
    """
    import re
    result = {}
    for line in md.splitlines():
        # Línea de tabla: | campo | valor |
        m = re.match(r"\|\s*\*{0,2}([^|*]+)\*{0,2}\s*\|\s*([^|]*)\s*\|", line)
        if m:
            key = m.group(1).strip().strip("*")
            val = m.group(2).strip()
            # Ignorar cabeceras y separadores
            if val and val not in ("---", "Valor", "Descripción"):
                result[key] = val
    return result
