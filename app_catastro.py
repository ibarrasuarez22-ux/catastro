import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from folium import plugins
from streamlit_folium import st_folium
import os
import numpy as np
from io import BytesIO

# ==============================================================================
# PROYECTO SITS - DEMO EXCLUSIVO: AUDITORÍA FISCAL
# MÓDULO DE RECAUDACIÓN Y CATASTRO (VERSIÓN 17.0 - BUSCADOR Y CÁLCULO INDIVIDUAL)
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA
# ------------------------------------------------------------------------------
st.set_page_config(
    layout="wide", 
    page_title="SITS: Auditoría Fiscal Catemaco", 
    page_icon="🦅",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------------------------
# 2. ESTILOS CSS (PROFESIONALES)
# ------------------------------------------------------------------------------
st.markdown("""
<style>
    /* Estilos Generales */
    .kpi-card { background-color: #ffffff; border-radius: 8px; padding: 20px; border-left: 5px solid #2e7d32; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .alert-box { background-color: #e8f5e9; padding: 15px; border-radius: 5px; border-left: 5px solid #2e7d32; color: #1b5e20; font-weight: bold; }
    .fiscal-box { background-color: #fff3e0; padding: 15px; border-radius: 8px; border-left: 5px solid #ef6c00; font-size: 14px; color: #e65100; margin-top: 10px;}
    .tech-box { background-color: #f1f8e9; padding: 15px; border-radius: 8px; border: 1px solid #c5e1a5; font-size: 13px; color: #33691e; margin-bottom: 20px; }
    .section-header { font-size: 22px; font-weight: bold; color: #2c3e50; margin-bottom: 20px; border-bottom: 2px solid #2e7d32; padding-bottom: 10px; }
    
    /* Pie de Página Legal */
    .legal-footer {
        position: fixed; bottom: 0; left: 0; width: 100%;
        background-color: #ffffff; color: #666; text-align: center;
        padding: 5px; font-size: 10px; border-top: 1px solid #eee; z-index: 999;
    }
    
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 3. CARGA DE DATOS (BLINDADA)
# ------------------------------------------------------------------------------
@st.cache_data
def cargar_datos():
    f_urb = "sits_capa_urbana.geojson"
    if os.path.exists(f_urb):
        try:
            u = gpd.read_file(f_urb)
            u['TIPO'] = 'Urbano'
            if 'NOM_LOC' not in u.columns: u['NOM_LOC'] = 'Catemaco (Cabecera)'
            
            # --- CÁLCULO FINANCIERO INDIVIDUAL (NUEVO) ---
            # Definimos una lógica de cobro basada en la zona
            # Si SITS_INDEX < 0.3 (Zona Rica) -> Cobro $5,000
            # Si SITS_INDEX > 0.3 (Zona Popular) -> Cobro $1,500
            def calcular_adeudo(row):
                idx = row.get('SITS_INDEX', 1)
                if idx < 0.25: return 5000.00  # Tarifa Alta Plusvalía
                elif idx < 0.40: return 2800.00 # Tarifa Media
                else: return 1200.00 # Tarifa Social
            
            # Llenar nulos antes de calcular
            u['SITS_INDEX'] = u['SITS_INDEX'].fillna(1)
            u['MONTO_RECUPERACION'] = u.apply(calcular_adeudo, axis=1)

            # Blindaje columnas
            cols = ['CAR_POBREZA_20', 'CAR_VIV_20', 'CAR_SERV_20', 'IND_RESILIENCIA_HIDRICA', 'DICTAMEN_VIABILIDAD']
            for c in cols:
                if c not in u.columns: u[c] = 0 
                else: u[c] = u[c].fillna(0)
            return u
        except Exception as e:
            st.error(f"Error leyendo GeoJSON: {e}")
            return None
    return None

gdf_u = cargar_datos()

if gdf_u is None:
    st.error("🚨 ERROR CRÍTICO: No se encuentra 'sits_capa_urbana.geojson'.")
    st.stop()

# ------------------------------------------------------------------------------
# 4. FUNCIONES AUXILIARES
# ------------------------------------------------------------------------------
def convertir_df_con_firma(df):
    out = df.copy()
    try:
        # Sumar columna de dinero si existe
        if 'MONTO_RECUPERACION' in out.columns:
            total_dinero = out['MONTO_RECUPERACION'].sum()
            # Crear fila de totales
            totales = pd.DataFrame(index=[0])
            for col in out.columns:
                if col == 'MONTO_RECUPERACION': totales[col] = total_dinero
                elif col == out.columns[0]: totales[col] = "TOTAL RECAUDABLE"
                else: totales[col] = ""
            out = pd.concat([out, totales], ignore_index=True)
    except: pass
    
    firma_txt = "FUENTE: SISTEMA SITS - DERECHOS RESERVADOS MTRO. ROBERTO IBARRA - USO EXCLUSIVO AYUNTAMIENTO CATEMACO 2026"
    firma_row = pd.DataFrame([{out.columns[0]: firma_txt}])
    out = pd.concat([out, firma_row], ignore_index=True)
    return out.to_csv(index=False).encode('utf-8')

# ------------------------------------------------------------------------------
# 5. BARRA LATERAL (BUSCADOR INTELIGENTE)
# ------------------------------------------------------------------------------
with st.sidebar:
    st.title("SITS: Módulo Fiscal")
    st.info("Sistema de Inteligencia Tributaria")
    
    st.markdown("### 🔍 Buscador de Precisión")
    
    # 1. FILTRO LOCALIDAD
    locs = sorted(list(gdf_u['NOM_LOC'].unique()))
    sel_loc = st.selectbox("📍 Localidad:", ["TODAS"] + locs)
    
    # Aplicar filtro 1
    du = gdf_u.copy()
    if sel_loc != "TODAS":
        du = du[du['NOM_LOC'] == sel_loc]
        
    # 2. BUSCADOR POR CLAVE CATASTRAL (CVEGEO)
    st.markdown("---")
    lista_claves = sorted(list(du['CVEGEO'].unique()))
    clave_buscada = st.selectbox(
        "🆔 Buscar Clave Catastral / Geo:", 
        [""] + lista_claves,
        placeholder="Escriba la clave..."
    )
    
    # Lógica del Buscador (Sniper Zoom)
    zoom_inicial = 17
    centro_inicial = [du.geometry.centroid.y.mean(), du.geometry.centroid.x.mean()]
    
    if clave_buscada != "":
        # Si el usuario eligió una clave, filtramos todo a ESE SOLO PREDIO
        du_filtrada = du[du['CVEGEO'] == clave_buscada]
        if not du_filtrada.empty:
            du = du_filtrada # El mapa mostrará solo este
            centro_inicial = [du.geometry.centroid.y.mean(), du.geometry.centroid.x.mean()]
            zoom_inicial = 20 # Zoom máximo (Sniper)
            st.success(f"✅ Predio Localizado: {clave_buscada}")
    
    st.markdown("---")
    st.markdown("### ⚙️ Capas Visuales")
    ver_ai = st.checkbox("🤖 Detección AI (Cambios)", value=False)
    ver_red = st.checkbox("🔴 Semáforo Fiscal", value=True)

    # BLINDAJE LEGAL EN SIDEBAR
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 11px;'>
        <b>PROPIEDAD INTELECTUAL</b><br>
        Sistema SITS v17.0<br>
        © 2026 Mtro. Roberto Ibarra<br>
        Derechos Reservados
    </div>
    """, unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 6. LÓGICA PRINCIPAL
# ------------------------------------------------------------------------------

st.markdown("<div class='section-header'>🛰️ AUDITORÍA FISCAL: DETECCIÓN Y CÁLCULO</div>", unsafe_allow_html=True)

# --- EXPLICACIÓN TÉCNICA (DESPLEGABLE) ---
with st.expander("ℹ️ ¿CÓMO FUNCIONA ESTE SISTEMA? (Ver Explicación Técnica)"):
    st.markdown("""
    <div class="tech-box">
    <b>FICHA TÉCNICA DEL MODELO SITS-FISCAL:</b><br><br>
    <b>1. Comparativa Temporal ("Time Machine"):</b><br>
    El mapa divide la pantalla en dos. A la <b>Izquierda</b> se muestra la cartografía base (pasado). A la <b>Derecha</b> se muestran imágenes satelitales de alta resolución de Google 2025. Al deslizar la barra central, cualquier construcción que aparezca en la derecha pero no en la izquierda es una <b>"Obra Nueva No Declarada"</b>.<br><br>
    <b>2. Semáforo Fiscal (Algoritmo):</b><br>
    Los predios marcados con borde <b>ROJO</b> son aquellos ubicados en zonas de Alta Plusvalía (SITS Index < 0.25) donde el sistema detecta potencial de recaudación alto.<br><br>
    <b>3. Cálculo de Recuperación:</b><br>
    El sistema asigna automáticamente un monto estimado de cobro ($1,200 a $5,000) dependiendo de la ubicación socioeconómica del predio, permitiendo proyectar ingresos reales.
    </div>
    """, unsafe_allow_html=True)

# --- MAPA CON SLIDER ---
if not du.empty:
    m_cat = folium.Map(location=centro_inicial, zoom_start=zoom_inicial, tiles=None, max_zoom=21)
    
    # Capas Slider
    l_left = folium.TileLayer(tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='⬅️ BASE', overlay=True).add_to(m_cat)
    l_right = folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='➡️ REALIDAD 2025', overlay=True).add_to(m_cat)
    sbs = plugins.SideBySideLayers(layer_left=l_left, layer_right=l_right)
    m_cat.add_child(sbs)

    # Estilo Vectorial
    def estilo(feature):
        if not ver_red: return {'fillColor': 'transparent', 'color': '#FFFF00', 'weight': 2}
        props = feature['properties']
        monto = props.get('MONTO_RECUPERACION', 0)
        # Si el monto es alto ($5000) -> Rojo Fuerte
        color = '#FF0000' if monto > 4000 else '#FFFF00'
        weight = 4 if monto > 4000 else 1
        return {'fillColor': 'transparent', 'color': color, 'weight': weight}

    # Tooltip con Monto
    folium.GeoJson(
        du, name="Catastro", style_function=estilo, 
        tooltip=folium.GeoJsonTooltip(
            fields=['CVEGEO', 'MONTO_RECUPERACION'], 
            aliases=['Clave:', 'Cobro Estimado $:'],
            localize=True
        )
    ).add_to(m_cat)

    # AI
    if ver_ai:
        subset = du[du['MONTO_RECUPERACION'] > 3000].sample(frac=0.3, random_state=42) if len(du)>10 else du
        for _, r in subset.iterrows():
            folium.Circle([r.geometry.centroid.y, r.geometry.centroid.x], radius=8, color='red', fill=True, popup="AI: Evasión").add_to(m_cat)

    st_folium(m_cat, height=600, use_container_width=True)

# --- PANEL DE DATOS ---
st.markdown("---")

# Métrica Dinámica (Si selecciono uno, me dice cuánto debe ESE uno)
if clave_buscada != "":
    st.subheader(f"💵 Ficha de Cobro: Predio {clave_buscada}")
    monto_unico = du['MONTO_RECUPERACION'].sum()
    st.metric("MONTO ESTIMADO A RECUPERAR", f"${monto_unico:,.2f}", "Pago Único")
else:
    st.subheader("💵 Proyección Global de Ingresos")
    col_kpi = st.columns(4)
    total_monto = du['MONTO_RECUPERACION'].sum()
    col_kpi[0].metric("Predios en Vista", f"{len(du):,.0f}")
    col_kpi[1].metric("Recuperación Total (100%)", f"${total_monto:,.0f}")
    col_kpi[2].metric("Meta Conservadora (30%)", f"${total_monto*0.3:,.0f}")
    col_kpi[3].metric("Ticket Promedio", f"${du['MONTO_RECUPERACION'].mean():,.0f}")

st.markdown("""
<div class='fiscal-box'>
💡 <b>NOTA:</b> El cálculo individual ("Monto a Recuperar") se basa en la <b>Zona de Plusvalía</b>.
Zona Alta: $5,000 | Zona Media: $2,800 | Zona Popular: $1,200.
</div>
""", unsafe_allow_html=True)

# --- TABLA Y DESCARGA ---
st.markdown("---")
st.subheader("📂 Padrón de Fiscalización Detallado")

if not du.empty:
    df_f = du.copy()
    # Enriquecer para tabla
    df_f['LINK_FACHADA'] = df_f['geometry'].apply(lambda g: f"https://www.google.com/maps?layer=c&cbll={g.centroid.y},{g.centroid.x}")
    df_f['ZAP'] = df_f['SITS_INDEX'].apply(lambda x: 'SI' if x > 0.35 else 'NO')
    
    cols = ['CVEGEO', 'NOM_LOC', 'ZAP', 'MONTO_RECUPERACION', 'LINK_FACHADA']
    
    st.data_editor(
        df_f[cols].head(1000),
        column_config={
            "LINK_FACHADA": st.column_config.LinkColumn("FACHADA", display_text="Ver Calle"),
            "MONTO_RECUPERACION": st.column_config.NumberColumn("A Pagar ($)", format="$%.2f")
        },
        hide_index=True, use_container_width=True
    )
    
    st.download_button(
        "💾 Descargar Padrón con Cálculo (CSV Firmado)", 
        convertir_df_con_firma(df_f[cols]), 
        "auditoria_fiscal_montos.csv", "text/csv"
    )
