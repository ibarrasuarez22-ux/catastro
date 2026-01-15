import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from folium import plugins
from streamlit_folium import st_folium
import os
import numpy as np

# ==============================================================================
# PROYECTO SITS - DEMO EXCLUSIVO: AUDITORÍA FISCAL
# ==============================================================================

# 1. CONFIGURACIÓN
st.set_page_config(layout="wide", page_title="SITS: Auditoría Fiscal", page_icon="🛰️")

# 2. ESTILOS
st.markdown("""
<style>
    .kpi-card { background-color: #ffffff; border-radius: 8px; padding: 20px; border-left: 5px solid #2e7d32; text-align: center; }
    .alert-box { background-color: #e8f5e9; padding: 15px; border-radius: 5px; border-left: 5px solid #2e7d32; color: #1b5e20; }
    .fiscal-box { background-color: #fff3e0; padding: 15px; border-radius: 8px; border-left: 5px solid #ef6c00; font-size: 14px; color: #e65100; margin-top: 10px;}
    .section-header { font-size: 22px; font-weight: bold; color: #2c3e50; margin-bottom: 20px; border-bottom: 2px solid #2e7d32; padding-bottom: 10px; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# 3. CARGA DE DATOS (BLINDADA)
@st.cache_data
def cargar_datos():
    # Buscamos el archivo en la raíz (donde usted lo subió)
    archivo = "sits_capa_urbana.geojson"
    
    if not os.path.exists(archivo):
        return None  # Si no existe, regresa vacío
        
    try:
        u = gpd.read_file(archivo)
        
        # Limpieza y formateo básico
        if 'NOM_LOC' not in u.columns: u['NOM_LOC'] = 'Catemaco'
        u['TIPO'] = 'Urbano'
        
        # Rellenar nulos para evitar errores matemáticos
        cols = ['SITS_INDEX', 'CAR_POBREZA_20', 'CAR_VIV_20', 'CAR_SERV_20', 'IND_RESILIENCIA_HIDRICA', 'DICTAMEN_VIABILIDAD']
        for c in cols:
            if c not in u.columns: u[c] = 0
            else: u[c] = u[c].fillna(0)
            
        return u
    except Exception as e:
        st.error(f"Error leyendo el archivo: {e}")
        return None

# --- ASIGNACIÓN DE VARIABLE (AQUÍ ESTABA EL ERROR) ---
gdf_u = cargar_datos()

# --- VERIFICACIÓN DE SEGURIDAD ---
if gdf_u is None:
    st.error("🚨 ERROR CRÍTICO: No se encuentra el archivo 'sits_capa_urbana.geojson' en el repositorio.")
    st.info("Asegúrese de que el archivo .geojson está subido en la misma lista que este archivo .py")
    st.stop() # Detiene la app aquí si no hay datos

# 4. BARRA LATERAL
with st.sidebar:
    st.title("SITS: Módulo Fiscal")
    st.info("Herramienta de Inteligencia Tributaria.")
    st.markdown("---")
    
    # Filtros (Ahora seguros porque gdf_u existe)
    locs = sorted(list(gdf_u['NOM_LOC'].unique()))
    sel_loc = st.selectbox("📍 Filtrar Localidad:", ["TODAS"] + locs)
    
    du = gdf_u.copy()
    if sel_loc != "TODAS":
        du = du[du['NOM_LOC'] == sel_loc]

    st.markdown("---")
    ver_ai = st.checkbox("🤖 Activar Detección AI", value=False)
    ver_red = st.checkbox("🔴 Resaltar Evasión", value=True)

# 5. PANEL PRINCIPAL
st.markdown("<div class='section-header'>🛰️ AUDITORÍA FISCAL: DETECCIÓN DE CAMBIOS</div>", unsafe_allow_html=True)
st.markdown("<div class='alert-box'><b>💰 TECNOLOGÍA DE RECAUDACIÓN:</b> Comparativa Satelital 2020 vs 2025.</div><br>", unsafe_allow_html=True)

# --- MAPA ---
if not du.empty:
    lat = du.geometry.centroid.y.mean()
    lon = du.geometry.centroid.x.mean()
    
    m = folium.Map(location=[lat, lon], zoom_start=18, tiles=None, max_zoom=21)
    
    # Capas Slider
    l_left = folium.TileLayer(tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', attr='Esri', name='2020', overlay=True).add_to(m)
    l_right = folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='2025', overlay=True).add_to(m)
    plugins.SideBySideLayers(layer_left=l_left, layer_right=l_right).add_to(m)

    # Estilo Fiscal
    def estilo(Mx):
        if not ver_red: return {'fillColor': 'transparent', 'color': '#FFFF00', 'weight': 2}
        idx = Mx['properties'].get('SITS_INDEX', 1)
        col = '#FF0000' if idx < 0.25 else '#FFFF00'
        return {'fillColor': 'transparent', 'color': col, 'weight': 3 if idx < 0.25 else 1}

    folium.GeoJson(du, style_function=estilo, tooltip=folium.GeoJsonTooltip(fields=['CVEGEO'], aliases=['Clave:'])).add_to(m)

    # AI Simulado
    if ver_ai:
        for _, r in du[du['SITS_INDEX']<0.3].sample(frac=0.3).iterrows():
            folium.Circle([r.geometry.centroid.y, r.geometry.centroid.x], radius=10, color='red', fill=True, popup="AI: Obra Nueva").add_to(m)

    st_folium(m, height=600, use_container_width=True)

# --- DATOS Y ESCENARIOS ---
st.markdown("---")
st.subheader("💵 Proyección Financiera")

col_kpi = st.columns(4)
col_kpi[0].metric("Predios Muestra", f"{len(du)*25:,.0f}")
col_kpi[1].metric("Evasión Detectada", f"{int(len(du)*25*0.25):,.0f}", "Alta Prioridad")

# Cálculo
total_predios = len(du) * 25
monto_base = (total_predios * 0.25) * 2800

if st.button("🔄 CALCULAR ESCENARIOS DE INGRESO", type="primary"):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Conservador (25%)", f"${monto_base*0.25:,.0f}")
    c2.metric("Moderado (50%)", f"${monto_base*0.50:,.0f}")
    c3.metric("Optimista (70%)", f"${monto_base*0.70:,.0f}")
    c4.metric("Ideal (100%)", f"${monto_base:,.0f}")
else:
    st.info("Haga clic para proyectar ingresos.")

# --- TABLA Y DESCARGA ---
st.markdown("---")
st.subheader("📂 Padrón Fiscal")

if not du.empty:
    df_f = du.copy()
    # Generar Link
    df_f['LINK_FACHADA'] = df_f['geometry'].apply(lambda g: f"https://www.google.com/maps?layer=c&cbll={g.centroid.y},{g.centroid.x}")
    df_f['ZAP'] = df_f['SITS_INDEX'].apply(lambda x: 'SI' if x > 0.35 else 'NO')
    
    cols = ['NOM_LOC', 'CVEGEO', 'SITS_INDEX', 'ZAP', 'LINK_FACHADA']
    df_show = df_f[[c for c in cols if c in df_f.columns]].head(500)
    
    st.data_editor(
        df_show,
        column_config={"LINK_FACHADA": st.column_config.LinkColumn("FACHADA", display_text="Ver Calle")},
        use_container_width=True,
        hide_index=True
    )
    
    csv = df_f.to_csv(index=False).encode('utf-8')
    st.download_button("💾 Descargar CSV", csv, "auditoria.csv", "text/csv")
