"""
Ficha Urbanística Madrid — interfaz web con Streamlit.
Ejecutar: streamlit run app.py
"""

import os
from datetime import datetime

import folium
import streamlit as st
from streamlit_folium import st_folium

from catastro import get_full_cadastral_data
from geocoder import geocode_address
from generator import generate_ficha
from pdf_export import generate_pdf
from pgoum import get_pgoum_data

st.set_page_config(
    page_title="Ficha Urbanística Madrid",
    page_icon="🏙️",
    layout="wide",
)


def _build_map(lat: float, lon: float, zoom: int = 17, style: str = "Satélite (Google)") -> folium.Map:
    """Construye un mapa Folium con el estilo seleccionado."""
    tile_configs = {
        "Satélite (Google)": {
            "tiles": "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
            "attr": "Google Satellite",
            "name": "Satélite",
        },
        "Híbrido (Google)": {
            "tiles": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
            "attr": "Google Hybrid",
            "name": "Híbrido",
        },
        "Callejero (OpenStreetMap)": {
            "tiles": "OpenStreetMap",
            "attr": "OpenStreetMap contributors",
            "name": "Callejero",
        },
    }
    cfg = tile_configs.get(style, tile_configs["Satélite (Google)"])
    m = folium.Map(location=[lat, lon], zoom_start=zoom, tiles=None)
    folium.TileLayer(
        tiles=cfg["tiles"],
        attr=cfg["attr"],
        name=cfg["name"],
        max_zoom=21,
    ).add_to(m)
    folium.LayerControl().add_to(m)
    return m

# ── Historial en session_state ─────────────────────────────────────────────
if "historial" not in st.session_state:
    st.session_state.historial = []  # lista de dicts {ts, address, refcat, zona}


def _add_to_historial(address, cat, pgoum):
    st.session_state.historial.insert(0, {
        "ts": datetime.now().strftime("%H:%M"),
        "address": address,
        "refcat": cat.get("refcat", ""),
        "zona": pgoum.get("zona_etiqueta", ""),
    })
    st.session_state.historial = st.session_state.historial[:10]  # máx 10


# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuración")
    # Leer clave desde secrets (Streamlit Cloud) o variable de entorno
    default_key = st.secrets.get("ANTHROPIC_API_KEY", "") if hasattr(st, "secrets") else ""
    default_key = default_key or os.environ.get("ANTHROPIC_API_KEY", "")
    api_key_input = st.text_input(
        "Anthropic API Key",
        type="password",
        value=default_key,
        help="Necesaria para generar la cédula con IA. Obtenerla en console.anthropic.com",
    )
    if api_key_input:
        os.environ["ANTHROPIC_API_KEY"] = api_key_input

    generar_cedula = st.toggle("Generar cédula con IA", value=True)
    map_style = st.selectbox(
        "Estilo de mapa",
        ["Satélite (Google)", "Callejero (OpenStreetMap)", "Híbrido (Google)"],
        index=0,
    )
    st.divider()

    # Historial
    if st.session_state.historial:
        st.subheader("🕐 Historial")
        for item in st.session_state.historial:
            st.caption(f"`{item['ts']}` {item['address'][:30]}")
            st.caption(f"↳ {item['refcat']} | Zona {item['zona']}")
        if st.button("Limpiar historial", use_container_width=True):
            st.session_state.historial = []
            st.rerun()

# ── Cabecera ────────────────────────────────────────────────────────────────
st.title("🏙️ Ficha Urbanística Madrid")
st.caption("Consulta datos catastrales y ordenanza PGOUM para cualquier dirección de Madrid.")

# ── Formulario ──────────────────────────────────────────────────────────────
with st.form("busqueda"):
    col_input, col_btn = st.columns([5, 1])
    with col_input:
        direccion = st.text_input(
            "Dirección",
            placeholder="Ej: Gran Via 28, Madrid  |  Calle Serrano 41, Madrid",
            label_visibility="collapsed",
        )
    with col_btn:
        submitted = st.form_submit_button("Consultar", type="primary", use_container_width=True)

if not submitted or not direccion.strip():
    # Mostrar mapa vacío centrado en Madrid
    m = _build_map(40.4168, -3.7038, zoom=12, style=map_style)
    st_folium(m, height=350, use_container_width=True)
    st.stop()

direccion = direccion.strip()

# ── Ejecución del flujo ─────────────────────────────────────────────────────
progress = st.progress(0, text="Iniciando consulta...")

with st.spinner("Geocodificando dirección..."):
    try:
        geo = geocode_address(direccion)
        progress.progress(25, text="✅ Coordenadas obtenidas")
    except Exception as exc:
        st.error(f"No se pudo geocodificar la dirección: {exc}")
        st.stop()

with st.spinner("Consultando Catastro..."):
    try:
        cat = get_full_cadastral_data(geo["lat"], geo["lon"])
        progress.progress(55, text="✅ Datos catastrales obtenidos")
    except Exception as exc:
        st.error(f"Error al consultar el Catastro: {exc}")
        st.stop()

with st.spinner("Consultando PGOUM (sigma.madrid.es)..."):
    try:
        pgoum_lat = cat.get("centroid_lat") or geo["lat"]
        pgoum_lon = cat.get("centroid_lon") or geo["lon"]
        pgoum = get_pgoum_data(pgoum_lat, pgoum_lon)
        progress.progress(80, text="✅ Datos urbanísticos obtenidos")
    except Exception as exc:
        st.error(f"Error al consultar el PGOUM: {exc}")
        st.stop()

_add_to_historial(direccion, cat, pgoum)
progress.progress(100, text="✅ Consulta completada")
progress.empty()

# ── Layout principal: mapa + datos ─────────────────────────────────────────
col_map, col_datos = st.columns([3, 2])

with col_map:
    lat = cat.get("centroid_lat") or geo["lat"]
    lon = cat.get("centroid_lon") or geo["lon"]
    m = _build_map(lat, lon, zoom=18, style=map_style)
    # Pin con la dirección
    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(
            f"<b>{cat.get('refcat', '')}</b><br>{cat.get('address', direccion)}", max_width=220
        ),
        tooltip=cat.get("refcat", direccion),
        icon=folium.Icon(color="red", icon="home"),
    ).add_to(m)
    st_folium(m, height=420, use_container_width=True)

with col_datos:
    # Datos catastrales
    st.subheader("📋 Datos Catastrales")
    st.metric("Referencia catastral", cat.get("refcat") or "N/D")
    st.caption(cat.get("address") or geo.get("display_name") or "")

    c1, c2 = st.columns(2)
    c1.metric("Sup. parcela", f"{cat.get('superficie_parcela') or 'N/D'} m²")
    c2.metric("Sup. construida", f"{cat.get('superficie_construida') or 'N/D'} m²")

    c3, c4 = st.columns(2)
    c3.metric("Uso", cat.get("uso") or "N/D")
    c4.metric("Año construcción", cat.get("anio_construccion") or "N/D")

    st.divider()

    # Datos urbanísticos
    st.subheader("🗺️ Planeamiento PGOUM")
    st.metric("Ordenanza / Zona", pgoum.get("ordenanza") or "N/D")

    c5, c6 = st.columns(2)
    c5.metric("Zona", pgoum.get("zona_etiqueta") or "N/D")
    c6.metric("Núm. ordenanza", pgoum.get("numord") or "N/D")

    c7, c8 = st.columns(2)
    c7.metric("Cond. edificación", str(pgoum.get("cond_edif") or "N/D"))
    c8.metric("Código NPG", pgoum.get("crs_npg") or "N/D")

    if pgoum.get("denominacion_dotacion"):
        st.caption(f"Dotación: {pgoum['denominacion_dotacion']}")

# ── Cédula urbanística ──────────────────────────────────────────────────────
st.divider()
cedula_text = ""

if generar_cedula:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.warning("🔑 Introduce tu Anthropic API Key en el panel lateral para generar la cédula urbanística.")
    else:
        with st.spinner("Generando cédula urbanística con Claude..."):
            try:
                cedula_text = generate_ficha(cat, pgoum, address=direccion)
            except Exception as exc:
                st.error(f"Error generando cédula: {exc}")

        if cedula_text:
            st.subheader("📄 Cédula Urbanística")
            st.markdown(cedula_text)

# ── Botones de descarga ─────────────────────────────────────────────────────
st.divider()
dl_col1, dl_col2, dl_col3 = st.columns(3)

refcat_slug = cat.get("refcat", "madrid").replace(" ", "_")

with dl_col1:
    if cedula_text:
        st.download_button(
            label="⬇️ Descargar Markdown",
            data=cedula_text.encode("utf-8"),
            file_name=f"cedula_{refcat_slug}.md",
            mime="text/markdown",
            use_container_width=True,
        )

with dl_col2:
    try:
        pdf_bytes = generate_pdf(cat, pgoum, cedula_text, address=direccion)
        st.download_button(
            label="⬇️ Descargar PDF",
            data=pdf_bytes,
            file_name=f"cedula_{refcat_slug}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    except Exception as exc:
        st.caption(f"PDF no disponible: {exc}")

with dl_col3:
    import json
    json_data = json.dumps({"geo": geo, "catastro": cat, "pgoum": pgoum}, ensure_ascii=False, indent=2)
    st.download_button(
        label="⬇️ Descargar JSON",
        data=json_data.encode("utf-8"),
        file_name=f"datos_{refcat_slug}.json",
        mime="application/json",
        use_container_width=True,
    )

# ── Expander datos brutos ───────────────────────────────────────────────────
with st.expander("🔍 Ver datos en bruto"):
    st.json({"catastro": cat, "pgoum": pgoum, "geo": geo})
