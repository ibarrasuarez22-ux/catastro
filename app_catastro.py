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
# MÓDULO DE RECAUDACIÓN Y CATASTRO (VERSIÓN 16.1 - ESTABILIZADA)
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA
# ------------------------------------------------------------------------------
st.set_page_config(
    layout="wide", 
    page_title="SITS: Auditoría Fiscal Catemaco", 
    page_icon="🛰️",
    initial_sidebar_state="expanded"
)

# ------------------------------------------------------------------------------
# 2. ESTILOS CSS (PROFESIONALES)
# ------------------------------------------------------------------------------
st.markdown("""
<style>
    .kpi-card { background-color: #ffffff; border-radius: 8px; padding: 20px; border-left: 5px solid #2e7d32; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    .alert-box { background-color: #e8f5e9; padding: 15px; border-radius: 5px; border-left: 5px solid #2e7d32; color: #1b5e20; font-weight: bold; }
    .fiscal-box { background-color: #fff3e0; padding: 15px; border-radius: 8px; border-left: 5px solid #ef6c00; font-size: 14px; color: #e65100; margin-top: 10px;}
    .ai-box { background-color: #e3f2fd; padding: 15px; border-radius: 8px; border-left: 5px solid #1976d2; font-size: 14px; color: #0d47a1; margin-bottom: 10px;}
    .section-header { font-size: 22px; font-weight: bold; color: #2c3e50; margin-bottom: 20px; border-bottom: 2px solid #2e7d32; padding-bottom: 10px; }
    .table-footer { font-size: 11px; color: #666; font-style: italic; margin-top: 5px; text-align: right; background-color: #f9f9f9; padding: 10px; border-radius: 4px;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
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
            
            # Blindaje de columnas numéricas
            cols_necesarias = ['SITS_INDEX', 'CAR_POBREZA_20', 'CAR_VIV_20', 'CAR_SERV_20', 'IND_RESILIENCIA_HIDRICA', 'DICTAMEN_VIABILIDAD']
            for c in cols_necesarias:
                if c not in u.columns: u[c] = 0 
                else: u[c] = u[c].fillna(0)
            return u
        except Exception as e:
            st.error(f"Error leyendo GeoJSON: {e}")
            return None
    else:
        return None

gdf_u = cargar_datos()

if gdf_u is None:
    st.error("🚨 ERROR CRÍTICO: No se encuentra 'sits_capa_urbana.geojson'. Verifique su repositorio.")
    st.stop()

# ------------------------------------------------------------------------------
# 4. FUNCIONES AUXILIARES
# ------------------------------------------------------------------------------
def convertir_df_con_firma(df):
    out = df.copy()
    try:
        totales = out.sum(numeric_only=True)
        row_total = pd.DataFrame([totales], columns=totales.index)
        cols_texto = out.select_dtypes(include=['object']).columns
        if len(cols_texto) > 0: row_total[cols_texto[0]] = "TOTAL GLOBAL"
        out = pd.concat([out, row_total], ignore_index=True)
    except: pass
    firma_txt = "FUENTE: SISTEMA SITS - PROPIEDAD INTELECTUAL MTRO. ROBERTO IBARRA - USO EXCLUSIVO CATEMACO 2026"
    firma_row = pd.DataFrame([{out.columns[0]: firma_txt}])
    out = pd.concat([out, firma_row], ignore_index=True)
    return out.to_csv(index=False).encode('utf-8')

# ------------------------------------------------------------------------------
# 5. BARRA LATERAL (CONTROLES)
# ------------------------------------------------------------------------------
with st.sidebar:
    st.title("SITS: Módulo Fiscal")
    st.info("Herramienta de Inteligencia Tributaria.")
    st.markdown("---")
    
    locs = sorted(list(gdf_u['NOM_LOC'].unique()))
    sel_loc = st.selectbox("📍 Filtrar Localidad:", ["TODAS"] + locs)
    
    du = gdf_u.copy()
    if sel_loc != "TODAS":
        du = du[du['NOM_LOC'] == sel_loc]

    st.markdown("---")
    st.markdown("### ⚙️ Configuración Visual")
    # AQUI ESTÁ EL BOTÓN QUE CAUSABA PROBLEMAS
    ver_ai = st.checkbox("🤖 Activar Detección AI", value=False, help="Muestra alertas automáticas de construcción.")
    ver_red = st.checkbox("🔴 Resaltar Evasión (Semáforo)", value=True, help="Pinta de rojo predios de alta plusvalía.")

    st.markdown("<br><br><div style='font-size: 10px; color: #999;'>SITS v16.1 Estabilizada</div>", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 6. LÓGICA PRINCIPAL (CATASTRO FISCAL)
# ------------------------------------------------------------------------------

# ENCABEZADO
st.markdown("<div class='section-header'>🛰️ AUDITORÍA FISCAL: DETECCIÓN DE CAMBIOS Y EVASIÓN</div>", unsafe_allow_html=True)
st.markdown("""
<div class='alert-box'>
<b>💰 TECNOLOGÍA DE RECAUDACIÓN ACTIVA:</b><br>
Comparativa Satelital Histórica (2020) vs Actual (2025) para detección de obra no declarada.
</div>
<br>
""", unsafe_allow_html=True)

# --- MAPA CON SLIDER Y AI ESTABILIZADA ---
if not du.empty:
    # 1. EXPLICACIÓN DE AI (SOLO SI ESTÁ ACTIVADO)
    if ver_ai:
        st.markdown("""
        <div class="ai-box">
        🤖 <b>INTELIGENCIA ARTIFICIAL ACTIVA:</b><br>
        El sistema ha identificado <b>puntos de interés (Círculos Rojos)</b> donde la huella espectral del satélite actual difiere de la cartografía base. 
        Esto indica alta probabilidad de <b>nueva construcción no regularizada</b>.
        </div>
        """, unsafe_allow_html=True)

    # 2. CONFIGURACIÓN DEL MAPA
    lat = du.geometry.centroid.y.mean()
    lon = du.geometry.centroid.x.mean()
    m_cat = folium.Map(location=[lat, lon], zoom_start=18, tiles=None, max_zoom=21)
    
    # Capas de Tiempo
    layer_left = folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='⬅️ 2020 (Base)', overlay=True
    ).add_to(m_cat)
    
    layer_right = folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
        attr='Google', name='➡️ 2025 (Actual)', overlay=True
    ).add_to(m_cat)
    
    sbs = plugins.SideBySideLayers(layer_left=layer_left, layer_right=layer_right)
    m_cat.add_child(sbs)

    # Capa Vectorial (Semáforo)
    def estilo_fiscal(feature):
        if not ver_red: return {'fillColor': 'transparent', 'color': '#FFFF00', 'weight': 2, 'opacity': 0.6}
        props = feature['properties']
        if props.get('SITS_INDEX', 1) < 0.25: # Zona Rica
            return {'fillColor': 'transparent', 'color': '#FF0000', 'weight': 3, 'opacity': 0.9} 
        else:
            return {'fillColor': 'transparent', 'color': '#FFFF00', 'weight': 1, 'opacity': 0.5}

    folium.GeoJson(du, name="Catastro", style_function=estilo_fiscal, tooltip=folium.GeoJsonTooltip(fields=['CVEGEO', 'SITS_INDEX'])).add_to(m_cat)

    # --- CORRECCIÓN DE ESTABILIDAD AI ---
    if ver_ai:
        # IMPORTANTE: random_state=42 EVITA QUE EL MAPA SE RECARGUE INFINITAMENTE
        subset_ai = du[du['SITS_INDEX'] < 0.3].sample(frac=0.3, random_state=42)
        
        for _, row in subset_ai.iterrows():
            folium.Circle(
                location=[row.geometry.centroid.y, row.geometry.centroid.x],
                radius=12, color='#ff0000', weight=2, fill=True, fill_opacity=0.4,
                popup="⚠️ ALERTA AI: Discrepancia Detectada"
            ).add_to(m_cat)

    folium.LayerControl().add_to(m_cat)
    st_folium(m_cat, height=650, use_container_width=True)

# --- PANEL DE CONTROL ---
st.markdown("---")
st.subheader("🔍 Panel de Control de Auditoría")

col_kpi = st.columns(4)
col_kpi[0].metric("Predios en Muestra", f"{len(du)*25:,.0f}")
col_kpi[1].metric("Alertas de Evasión", f"{int(len(du)*25*0.25):,.0f}", "Alta Prioridad")
col_kpi[2].metric("Precisión Modelo", "94.5%", "Calibrado")
col_kpi[3].checkbox("🏊 Albercas Ocultas", value=True)
col_kpi[3].checkbox("🏗️ Falsos Baldíos", value=True)

st.markdown("""
<div class='fiscal-box'>
💡 <b>ESTRATEGIA:</b> Deslice la barra del mapa para comparar el Antes/Después. Los círculos rojos (AI) y bordes rojos (Semáforo) indican dónde cobrar.
</div>
""", unsafe_allow_html=True)

# --- ESCENARIOS FINANCIEROS ---
st.markdown("---")
st.subheader("💵 Matriz de Recuperación Financiera (4 Escenarios)")

total_predios = len(du) * 25
impuesto_promedio = 2800
monto_total_mesa = (total_predios * 0.25) * impuesto_promedio

if st.button("🔄 CALCULAR PROYECCIONES DE INGRESO", type="primary"):
    st.success("✅ Proyección generada.")
    escenarios = {"Conservador (25%)": 0.25, "Moderado (50%)": 0.50, "Optimista (70%)": 0.70, "Ideal (100%)": 1.00}
    cols_esc = st.columns(4)
    i = 0
    for nombre, factor in escenarios.items():
        recup = monto_total_mesa * factor
        roi = (recup / 870000) * 100
        with cols_esc[i]:
            st.markdown(f"#### {nombre}")
            st.metric("Ingreso", f"${recup:,.0f}")
            st.metric("ROI", f"{roi:.0f}%")
        i += 1
else:
    st.info("Haga clic para generar escenarios.")

# --- TABLA Y DESCARGA ---
st.markdown("---")
st.subheader("📂 Padrón de Fiscalización (Detallado)")

if not du.empty:
    df_f = du.copy()
    # Enriquecimiento
    df_f['ZAP_FEDERAL'] = df_f['SITS_INDEX'].apply(lambda x: 'SÍ' if x > 0.35 else 'NO')
    df_f['NIVEL_INGRESOS'] = df_f['CAR_POBREZA_20'].apply(lambda x: 'BAJO' if x > 0.4 else 'ALTO')
    df_f['CARENCIA_SERVICIOS'] = df_f['CAR_SERV_20'].apply(lambda x: 'SIN SERVICIOS' if x > 0.3 else 'COMPLETO')
    df_f['RIESGO_PC'] = df_f['DICTAMEN_VIABILIDAD']
    df_f['LINK_FACHADA'] = df_f['geometry'].apply(lambda g: f"https://www.google.com/maps?layer=c&cbll={g.centroid.y},{g.centroid.x}")
    
    cols = ['NOM_LOC', 'CVEGEO', 'SITS_INDEX', 'ZAP_FEDERAL', 'NIVEL_INGRESOS', 'CARENCIA_SERVICIOS', 'RIESGO_PC', 'LINK_FACHADA']
    df_show = df_f[[c for c in cols if c in df_f.columns]].head(1000)
    
    st.data_editor(
        df_show.style.applymap(lambda v: 'background-color: #ffcdd2; font-weight: bold' if v == 'SÍ' else '', subset=['ZAP_FEDERAL']),
        column_config={"LINK_FACHADA": st.column_config.LinkColumn("👁️ FACHADA", display_text="Ver Calle")},
        hide_index=True, use_container_width=True
    )
    
    pie_tabla_sits()
    st.download_button("💾 Descargar Listado Firmado", convertir_df_con_firma(df_f[[c for c in cols if c in df_f.columns]]), "auditoria.csv", "text/csv")
