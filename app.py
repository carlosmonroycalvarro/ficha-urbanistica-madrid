# -*- coding: utf-8 -*-
"""
Ficha Urbanística Madrid — interfaz web con Streamlit.
Ejecutar: streamlit run app.py
"""

import json
import os
from datetime import datetime

import folium
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

from catastro import get_full_cadastral_data
from geolocator import geocode_address, reverse_geocode
from generator import generate_ficha
from pdf_export import generate_pdf
from pgoum import get_pgoum_data

st.set_page_config(
    page_title="Ficha Urbanística Madrid",
    page_icon="🏙️",
    layout="wide",
)

# ── CSS: oculta todo excepto la ficha al imprimir ──────────────────────────
st.markdown("""
<style>
@media print {
    [data-testid="stSidebar"],
    [data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    .no-print { display: none !important; }
    .print-only { display: block !important; }
    [data-testid="stMain"] { margin: 0 !important; padding: 0 !important; }
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ────────────────────────────────────────────────────────────────
def _build_map(lat: float, lon: float, zoom: int = 17,
               style: str = "Satélite (Google)", marker: bool = False,
               polygon: list = None) -> folium.Map:
    tiles = {
        "Satélite (Google)": ("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}", "Google Satellite"),
        "Híbrido (Google)":  ("https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}", "Google Hybrid"),
        "Callejero (OSM)":   ("OpenStreetMap", "© OpenStreetMap contributors"),
    }
    tile_url, attr = tiles.get(style, tiles["Satélite (Google)"])
    m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None)
    folium.TileLayer(tiles=tile_url, attr=attr, name=style, max_zoom=21).add_to(m)

    # Polígono de parcela (prioridad sobre el marcador simple)
    if polygon and len(polygon) >= 3:
        folium.Polygon(
            locations=polygon,
            color="#FF4500",
            weight=3,
            fill=True,
            fill_color="#FF4500",
            fill_opacity=0.20,
            popup=folium.Popup(st.session_state.get("result_address", ""), max_width=220),
        ).add_to(m)
        # Icono centrado en el polígono
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(st.session_state.get("result_address", ""), max_width=220),
            icon=folium.Icon(color="red", icon="home", prefix="fa"),
        ).add_to(m)
    elif marker:
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(st.session_state.get("result_address", ""), max_width=220),
            icon=folium.Icon(color="red", icon="home", prefix="fa"),
        ).add_to(m)

    # Instrucción visual al usuario (solo en vista búsqueda)
    if not marker and not polygon:
        folium.map.Marker(
            [lat + 0.0012, lon],
            icon=folium.DivIcon(
                html='<div style="font-size:12px;background:rgba(255,255,255,0.85);'
                     'padding:3px 7px;border-radius:4px;white-space:nowrap;">'
                     '📍 Haz clic en el mapa para seleccionar una parcela</div>',
                icon_size=(280, 24),
                icon_anchor=(140, 12),
            ),
        ).add_to(m)

    folium.LayerControl().add_to(m)
    return m


def _run_query(lat: float, lon: float, address_label: str):
    """Ejecuta el flujo completo y guarda resultados en session_state."""
    with st.spinner("Consultando Catastro..."):
        cat = get_full_cadastral_data(lat, lon)
    pgoum_lat = cat.get("centroid_lat") or lat
    pgoum_lon = cat.get("centroid_lon") or lon
    with st.spinner("Consultando PGOUM..."):
        pgoum = get_pgoum_data(pgoum_lat, pgoum_lon)

    cedula = ""
    if st.session_state.get("generar_cedula") and os.environ.get("ANTHROPIC_API_KEY"):
        with st.spinner("Generando cédula con Claude..."):
            try:
                cedula = generate_ficha(cat, pgoum, address=address_label)
            except Exception as exc:
                st.warning(f"No se pudo generar la cédula: {exc}")

    # Guardar en historial
    st.session_state.historial.insert(0, {
        "ts": datetime.now().strftime("%H:%M"),
        "address": address_label,
        "refcat": cat.get("refcat", ""),
        "zona": pgoum.get("zona_etiqueta", ""),
        "lat": pgoum_lat, "lon": pgoum_lon,
    })
    st.session_state.historial = st.session_state.historial[:10]

    st.session_state.result = {"cat": cat, "pgoum": pgoum, "cedula": cedula}
    st.session_state.result_address = address_label
    st.session_state.result_lat = pgoum_lat
    st.session_state.result_lon = pgoum_lon
    st.session_state.view = "result"


# ── Session state inicial ──────────────────────────────────────────────────
for key, default in [
    ("view", "search"),        # "search" | "result"
    ("historial", []),
    ("generar_cedula", True),
    ("map_style", "Satélite (Google)"),
    ("clicked_lat", None),
    ("clicked_lon", None),
    ("clicked_address", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuración")
    default_key = ""
    try:
        default_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        pass
    default_key = default_key or os.environ.get("ANTHROPIC_API_KEY", "")
    api_key = st.text_input("Anthropic API Key", type="password", value=default_key,
                            help="Necesaria para generar la cédula con IA.")
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key

    st.session_state.generar_cedula = st.toggle("Generar cédula con IA", value=st.session_state.generar_cedula)
    st.session_state.map_style = st.selectbox(
        "Estilo de mapa",
        ["Satélite (Google)", "Híbrido (Google)", "Callejero (OSM)"],
        index=["Satélite (Google)", "Híbrido (Google)", "Callejero (OSM)"].index(st.session_state.map_style),
    )
    st.divider()

    if st.session_state.historial:
        st.subheader("🕐 Historial")
        for item in st.session_state.historial:
            if st.button(f"`{item['ts']}` {item['address'][:28]}", key=f"hist_{item['ts']}_{item['refcat']}", use_container_width=True):
                _run_query(item["lat"], item["lon"], item["address"])
                st.rerun()
        if st.button("Limpiar historial", use_container_width=True):
            st.session_state.historial = []
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# VISTA: BÚSQUEDA
# ══════════════════════════════════════════════════════════════════════════
if st.session_state.view == "search":
    st.title("🏙️ Ficha Urbanística Madrid")
    st.caption("Escribe una dirección o haz clic directamente sobre la parcela en el mapa.")

    # Formulario de texto
    with st.form("form_busqueda", clear_on_submit=False):
        col_txt, col_btn = st.columns([5, 1])
        with col_txt:
            direccion_texto = st.text_input("Dirección", placeholder="Ej: Gran Via 28, Madrid",
                                            label_visibility="collapsed")
        with col_btn:
            buscar = st.form_submit_button("Buscar", type="primary", use_container_width=True)

    if buscar and direccion_texto.strip():
        with st.spinner("Geocodificando..."):
            try:
                geo = geocode_address(direccion_texto.strip())
                _run_query(geo["lat"], geo["lon"], direccion_texto.strip())
                st.rerun()
            except Exception as exc:
                st.error(f"No se encontró la dirección: {exc}")

    # Mapa interactivo — clic para seleccionar punto
    st.markdown("**O selecciona directamente en el mapa:**")
    map_center_lat = st.session_state.get("result_lat", 40.4168)
    map_center_lon = st.session_state.get("result_lon", -3.7038)
    m = _build_map(map_center_lat, map_center_lon, zoom=13, style=st.session_state.map_style)
    # Mostrar punto seleccionado provisionalmente mientras no se ha enviado la consulta
    if st.session_state.clicked_lat:
        folium.CircleMarker(
            location=[st.session_state.clicked_lat, st.session_state.clicked_lon],
            radius=10,
            color="#FF4500",
            fill=True,
            fill_color="#FF4500",
            fill_opacity=0.6,
            popup=st.session_state.clicked_address or "Punto seleccionado",
        ).add_to(m)
    map_data = st_folium(m, height=450, use_container_width=True, returned_objects=["last_clicked"])

    # Procesar clic en el mapa
    clicked = map_data.get("last_clicked")
    if clicked:
        clat, clon = clicked["lat"], clicked["lng"]
        if (clat, clon) != (st.session_state.clicked_lat, st.session_state.clicked_lon):
            st.session_state.clicked_lat = clat
            st.session_state.clicked_lon = clon
            try:
                rev = reverse_geocode(clat, clon)
                st.session_state.clicked_address = rev["address_short"] or rev["display_name"]
            except Exception:
                st.session_state.clicked_address = f"Punto ({clat:.5f}, {clon:.5f})"

    if st.session_state.clicked_lat:
        st.info(f"📍 Punto seleccionado: **{st.session_state.clicked_address}**")
        if st.button("Consultar este punto", type="primary", use_container_width=True):
            _run_query(
                st.session_state.clicked_lat,
                st.session_state.clicked_lon,
                st.session_state.clicked_address,
            )
            st.session_state.clicked_lat = None
            st.session_state.clicked_lon = None
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# VISTA: RESULTADO
# ══════════════════════════════════════════════════════════════════════════
elif st.session_state.view == "result":
    res   = st.session_state.result
    cat   = res["cat"]
    pgoum = res["pgoum"]
    cedula = res.get("cedula", "")
    address = st.session_state.result_address
    lat = st.session_state.result_lat
    lon = st.session_state.result_lon

    # ── Barra de acciones ──────────────────────────────────────────────
    st.markdown('<div class="no-print">', unsafe_allow_html=True)
    act1, act2, act3, act4 = st.columns([2, 2, 2, 1])

    with act1:
        refcat_slug = cat.get("refcat", "madrid")
        try:
            pdf_bytes = generate_pdf(cat, pgoum, cedula, address=address)
            st.download_button("⬇️ Descargar informe PDF", data=pdf_bytes,
                               file_name=f"cedula_{refcat_slug}.pdf",
                               mime="application/pdf", use_container_width=True)
        except Exception as exc:
            st.caption(f"PDF no disponible: {exc}")

    with act2:
        if cedula:
            st.download_button("⬇️ Descargar Markdown", data=cedula.encode("utf-8"),
                               file_name=f"cedula_{refcat_slug}.md",
                               mime="text/markdown", use_container_width=True)
        else:
            json_data = json.dumps({"catastro": cat, "pgoum": pgoum}, ensure_ascii=False, indent=2)
            st.download_button("⬇️ Descargar JSON", data=json_data.encode("utf-8"),
                               file_name=f"datos_{refcat_slug}.json",
                               mime="application/json", use_container_width=True)

    with act3:
        if st.button("🖨️ Imprimir", use_container_width=True):
            components.html("<script>window.print();</script>", height=0)

    with act4:
        if st.button("🔍 Nueva consulta", use_container_width=True, type="primary"):
            st.session_state.view = "search"
            st.session_state.clicked_lat = None
            st.session_state.clicked_lon = None
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)
    st.divider()

    # ── Datos en dos columnas + mapa ──────────────────────────────────
    col_datos, col_mapa = st.columns([2, 3])

    with col_datos:
        st.subheader(f"📍 {address}")
        st.markdown("**Datos Catastrales**")
        st.metric("Referencia catastral", cat.get("refcat") or "N/D")
        st.caption(cat.get("address") or "")

        c1, c2 = st.columns(2)
        c1.metric("Sup. parcela", f"{cat.get('superficie_parcela') or 'N/D'} m²")
        c2.metric("Sup. construida", f"{cat.get('superficie_construida') or 'N/D'} m²")
        c3, c4 = st.columns(2)
        c3.metric("Uso", cat.get("uso") or "N/D")
        c4.metric("Año construc.", cat.get("anio_construccion") or "N/D")

        st.divider()
        st.markdown("**Planeamiento PGOUM**")
        st.metric("Ordenanza / Zona", pgoum.get("ordenanza") or "N/D")
        c5, c6 = st.columns(2)
        c5.metric("Zona", pgoum.get("zona_etiqueta") or "N/D")
        c6.metric("Núm. ordenanza", pgoum.get("numord") or "N/D")
        c7, c8 = st.columns(2)
        c7.metric("Cond. edificación", str(pgoum.get("cond_edif") or "N/D"))
        c8.metric("Código NPG", pgoum.get("crs_npg") or "N/D")
        if pgoum.get("denominacion_dotacion"):
            st.caption(f"Dotación: {pgoum['denominacion_dotacion']}")

    with col_mapa:
        polygon = cat.get("parcel_polygon")
        m2 = _build_map(lat, lon, zoom=18, style=st.session_state.map_style,
                        marker=True, polygon=polygon)
        st_folium(m2, height=420, use_container_width=True, returned_objects=[])

    # ── Cédula urbanística ────────────────────────────────────────────
    if cedula:
        st.divider()
        st.subheader("📄 Cédula Urbanística")
        st.markdown(cedula)
    elif st.session_state.generar_cedula and not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("🔑 Introduce tu Anthropic API Key en el panel lateral para generar la cédula.")

    # ── Datos brutos ──────────────────────────────────────────────────
    st.markdown('<div class="no-print">', unsafe_allow_html=True)
    with st.expander("🔍 Ver datos en bruto"):
        st.json({"catastro": cat, "pgoum": pgoum})
    st.markdown('</div>', unsafe_allow_html=True)
