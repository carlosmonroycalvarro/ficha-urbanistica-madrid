"""
Exportación de la cédula urbanística a PDF usando fpdf2.
"""

from fpdf import FPDF
from datetime import date


class CedulaPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 13)
        self.set_fill_color(30, 80, 160)
        self.set_text_color(255, 255, 255)
        self.cell(0, 10, "CEDULA URBANISTICA - MADRID", align="C", fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, f"Generado el {date.today().isoformat()} | Datos: Catastro + PGOUM Madrid | Pagina {self.page_no()}", align="C")

    def section_title(self, title: str):
        self.set_font("Helvetica", "B", 10)
        self.set_fill_color(220, 230, 245)
        self.set_text_color(20, 50, 120)
        self.cell(0, 7, title.upper(), fill=True, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def field_row(self, label: str, value: str):
        self.set_font("Helvetica", "B", 9)
        self.set_x(12)
        self.cell(58, 6, label + ":", border=0)
        self.set_font("Helvetica", "", 9)
        self.multi_cell(0, 6, str(value) if value else "No disponible", border=0)

    def cedula_text(self, markdown_text: str):
        """Escribe el texto de la cédula generada por Claude (elimina Markdown básico)."""
        self.set_font("Helvetica", "", 9)
        self.set_left_margin(12)
        for line in markdown_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("## ") or stripped.startswith("# "):
                title = stripped.lstrip("# ").strip()
                self.ln(2)
                self.section_title(title)
            elif stripped.startswith("**") and stripped.endswith("**"):
                self.set_font("Helvetica", "B", 9)
                self.multi_cell(0, 5, stripped.strip("*"))
                self.set_font("Helvetica", "", 9)
            elif stripped.startswith("- "):
                self.set_x(16)
                self.multi_cell(0, 5, "• " + stripped[2:])
            elif stripped:
                # Limpiar negrita inline **texto**
                clean = stripped.replace("**", "")
                self.multi_cell(0, 5, clean)
            else:
                self.ln(2)


def generate_pdf(cat: dict, pgoum: dict, cedula_text: str, address: str = "") -> bytes:
    """
    Genera el PDF de la cédula urbanística y devuelve los bytes.
    """
    pdf = CedulaPDF()
    pdf.set_margins(12, 15, 12)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Dirección buscada
    if address:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(0, 6, f"Direccion consultada: {address}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    # Datos catastrales
    pdf.section_title("1. Identificacion y Datos Catastrales")
    pdf.field_row("Referencia catastral", cat.get("refcat", ""))
    pdf.field_row("Direccion", cat.get("address", ""))
    pdf.field_row("Superficie parcela", f"{cat.get('superficie_parcela', 'N/D')} m2")
    pdf.field_row("Superficie construida", f"{cat.get('superficie_construida', 'N/D')} m2")
    pdf.field_row("Uso principal", cat.get("uso", ""))
    pdf.field_row("Anno construccion", cat.get("anio_construccion", ""))
    pdf.ln(3)

    # Datos urbanísticos
    pdf.section_title("2. Planeamiento Urbanistico (PGOUM)")
    pdf.field_row("Ordenanza / Zona", pgoum.get("ordenanza", ""))
    pdf.field_row("Etiqueta zona", pgoum.get("zona_etiqueta", ""))
    pdf.field_row("Num. ordenanza", pgoum.get("numord", ""))
    pdf.field_row("Condicion edificacion", str(pgoum.get("cond_edif", "")))
    pdf.field_row("Codigo NPG", pgoum.get("crs_npg", ""))
    pdf.field_row("Dotacion especifica", pgoum.get("denominacion_dotacion", ""))
    pdf.ln(3)

    # Cédula generada por IA
    if cedula_text:
        pdf.section_title("3. Cedula Urbanistica (generada por IA)")
        pdf.cedula_text(cedula_text)

    return bytes(pdf.output())
