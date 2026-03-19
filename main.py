import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Dashboard Autolux", layout="wide")

# Estilo Visual Toyota Autolux
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    h1 { color: #EB0A1E; font-family: 'Arial'; font-weight: bold; margin-bottom: 0px; }
    .stMetric { background-color: #f9f9f9; border: 1px solid #e6e6e6; padding: 15px; border-radius: 5px; }
    div[data-testid="stMetricValue"] { color: #000000; font-size: 45px !important; font-weight: bold; }
    div[data-testid="stMetricLabel"] { color: #EB0A1E; font-weight: bold; font-size: 16px !important; }
    .stTabs [aria-selected="true"] { background-color: #004F43 !important; color: white !important; font-weight: bold; }
    .stDataFrame { border: 1px solid #e6e6e6; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN A DATOS ---
url = "https://docs.google.com/spreadsheets/d/156gG4r3krIiXEF9nIqsoJoh9YB_kcdhJittobHbxZ9s/edit?gid=1344313191#gid=1344313191"

@st.cache_data(ttl=60)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(spreadsheet=url)
    # Limpiamos nombres de columnas (quita espacios extras)
    df.columns = [str(c).strip() for c in df.columns]
    return df

df_raw = load_data()
df = df_raw.copy()

# --- 3. PROCESAMIENTO DE ANTIGÜEDAD (Columna: Fecha de Ingreso) ---
# Forzamos la búsqueda de la columna exacta
col_target = "Fecha de Ingreso"

if col_target in df.columns:
    # Convertir a formato fecha
    df[col_target] = pd.to_datetime(df[col_target], errors='coerce')
    
    # Eliminar filas donde la fecha es inválida para el cálculo de antigüedad
    df_temp = df.dropna(subset=[col_target])
    
    # Cálculo de meses
    hoy = pd.Timestamp.now()
    df['Meses_Ant'] = df[col_target].apply(lambda x: (hoy.year - x.year) * 12 + (hoy.month - x.month) if pd.notnull(x) else 0)
    
    # Crear los buckets (Rango Antiguedad)
    conditions = [
        (df['Meses_Ant'] <= 12),
        (df['Meses_Ant'] > 12) & (df['Meses_Ant'] <= 36),
        (df['Meses_Ant'] > 36) & (df['Meses_Ant'] <= 60),
        (df['Meses_Ant'] > 60)
    ]
    labels = ['Hasta 1 año', '1-3 años', '3-5 años', 'Más de 5 años']
    df['Rango Antiguedad'] = np.select(conditions, labels, default='Sin Dato')
    
    # Extraer Mes y Año para filtros
    df['Año_Ingreso'] = df[col_target].dt.year.fillna(0).astype(int)
    df['Mes_Ingreso'] = df[col_target].dt.month_name().fillna("Sin Dato")
    df['AñoMes'] = df[col_target].dt.strftime('%Y-%m')
else:
    st.error(f"⚠️ No se encontró la columna '{col_target}'. Por favor verifica el nombre en el Excel.")
    df['Rango Antiguedad'] = "Error Columna"

# --- 4. HEADER ---
header_col1, header_col2 = st.columns([4, 1])
with header_col1:
    st.markdown("<h1>ESTRUCTURA</h1>", unsafe_allow_html=True)
with header_col2:
    st.image("https://upload.wikimedia.org/wikipedia/commons/e/ee/Toyota_logo_%28Red%29.svg", width=120)

tabs = st.tabs(["ESTRUCTURA", "ESTRUCTURA TASA", "ROTACIÓN", "AUSENTISMO"])

# ==========================================
# PESTAÑA: ESTRUCTURA (Activos Autolux)
# ==========================================
with tabs[0]:
    # FILTRO BASE: ESTADO='ACTIVO' y EMPRESA='AUTOLUX'
    if 'ESTADO' in df.columns and 'EMPRESA' in df.columns:
        df_activos = df[(df['ESTADO'].astype(str).str.upper() == 'ACTIVO') & 
                        (df['EMPRESA'].astype(str).str.upper() == 'AUTOLUX')].copy()
    else:
        st.warning("Faltan columnas de control (ESTADO/EMPRESA).")
        df_activos = df.copy()

    # Filtros Superiores
    f1, f2, f3, f4 = st.columns(4)
    with f1: sel_loc = st.multiselect("Localidad", sorted(df_activos['Localidad'].unique().tolist()) if 'Localidad' in df_activos.columns else [])
    with f2: sel_mes = st.multiselect("Mes", sorted(df_activos['Mes_Ingreso'].unique().tolist()) if 'Mes_Ingreso' in df_activos.columns else [])
    with f3: sel_anio = st.multiselect("Año", sorted([int(x) for x in df_activos['Año_Ingreso'].unique() if x > 0]) if 'Año_Ingreso' in df_activos.columns else [])
    with f4: sel_area = st.multiselect("Área", sorted(df_activos['Area'].unique().tolist()) if 'Area' in df_activos.columns else [])

    # Aplicar Filtros
    dff = df_activos.copy()
    if sel_loc: dff = dff[dff['Localidad'].isin(sel_loc)]
    if sel_mes: dff = dff[dff['Mes_Ingreso'].isin(sel_mes)]
    if sel_anio: dff = dff[dff['Año_Ingreso'].isin(sel_anio)]
    if sel_area: dff = dff[dff['Area'].isin(sel_area)]

    if dff.empty:
        st.info("No hay datos para los filtros seleccionados.")
    else:
        c_izq, c_der = st.columns([2, 3])
        
        with c_izq:
            st.metric("Dotación", len(dff))
            st.markdown("### Matriz por Área y Puesto")
            if all(x in dff.columns for x in ['Area', 'Puesto', 'Localidad']):
                pivot = pd.pivot_table(dff, index=['Area', 'Puesto'], columns='Localidad', values='EMPRESA', aggfunc='count', fill_value=0, margins=True, margins_name='Total')
                st.dataframe(pivot, use_container_width=True)

        with c_der:
            st.markdown("### Dotación Histórica")
            if 'AñoMes' in dff.columns:
                hist_data = dff.groupby('AñoMes').size().reset_index(name='Dotacion')
                fig_line = px.line(hist_data, x='AñoMes', y='Dotacion', color_discrete_sequence=['#EB0A1E'])
                st.plotly_chart(fig_line, use_container_width=True)

            sub_c1, sub_c2 = st.columns(2)
            with sub_c1:
                st.markdown("### Antigüedad")
                # Gráfico circular de antigüedad
                fig_pie = px.pie(dff, names='Rango Antiguedad', hole=0.6, 
                                 color_discrete_sequence=['#EB0A1E', '#58595B', '#939598', '#D1D3D4'])
                fig_pie.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.5))
                st.plotly_chart(fig_pie, use_container_width=True)
                
            with sub_c2:
                st.markdown("### Categoría")
                if 'Categoría' in dff.columns:
                    cat_counts = dff['Categoría'].value_counts().reset_index()
                    fig_bar = px.bar(cat_counts, y='Categoría', x='count', orientation='h', color_discrete_sequence=['#EB0A1E'])
                    st.plotly_chart(fig_bar, use_container_width=True)

# ==========================================
# SECCIONES ADICIONALES (Placeholder)
# ==========================================
with tabs[1]:
    st.subheader("Estructura de Declarados (TASA)")
    if 'Declarados' in df.columns:
        df_tasa = df[df['Declarados'].str.upper().str.contains("SI|DECLARADO", na=False)]
        st.metric("Total Declarados Toyota", len(df_tasa))
with tabs[2]:
    st.subheader("Rotación")
    st.info("Cálculo basado en columnas 'bajas de Rotación real' y 'bajas de delcarados'.")
with tabs[3]:
    st.subheader("Ausentismo")
    st.info("Cálculo basado en la columna 'politica'.")
