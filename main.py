import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Dashboard Autolux", layout="wide")

# Estilo Toyota Autolux
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    h1 { color: #EB0A1E; font-family: 'Arial'; font-weight: bold; margin-bottom: 0px; }
    .stMetric { background-color: #f9f9f9; border: 1px solid #e6e6e6; padding: 15px; border-radius: 5px; }
    div[data-testid="stMetricValue"] { color: #000000; font-size: 45px !important; font-weight: bold; }
    div[data-testid="stMetricLabel"] { color: #EB0A1E; font-weight: bold; }
    .stTabs [aria-selected="true"] { background-color: #004F43 !important; color: white !important; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CARGA DE DATOS ---
url = "https://docs.google.com/spreadsheets/d/156gG4r3krIiXEF9nIqsoJoh9YB_kcdhJittobHbxZ9s/edit?gid=1344313191#gid=1344313191"

@st.cache_data(ttl=60)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Intentamos leer la hoja
    df = conn.read(spreadsheet=url)
    # Limpieza básica de nombres de columnas: quitar espacios al inicio/final
    df.columns = [str(c).strip() for c in df.columns]
    return df

df_raw = load_data()
df = df_raw.copy()

# --- 3. DETECCIÓN INTELIGENTE DE LA COLUMNA DE FECHA ---
# Buscamos una columna que contenga "fecha" e "ingreso" en su nombre
col_fecha_real = None
for c in df.columns:
    nombre_min = c.lower()
    if 'fecha' in nombre_min and 'ingreso' in nombre_min:
        col_fecha_real = c
        break

# --- 4. PROCESAMIENTO DE DATOS ---
if col_fecha_real:
    # Convertir a fecha
    df[col_fecha_real] = pd.to_datetime(df[col_fecha_real], errors='coerce')
    
    # Cálculo de Antigüedad
    hoy = pd.Timestamp.now()
    df['Meses_Ant'] = df[col_fecha_real].apply(lambda x: (hoy.year - x.year) * 12 + (hoy.month - x.month) if pd.notnull(x) else 0)
    
    # Buckets de antigüedad
    conds = [(df['Meses_Ant'] <= 12), (df['Meses_Ant'] > 12) & (df['Meses_Ant'] <= 36), 
             (df['Meses_Ant'] > 36) & (df['Meses_Ant'] <= 60), (df['Meses_Ant'] > 60)]
    labels = ['Hasta 1 año', '1-3 años', '3-5 años', 'Más de 5 años']
    df['Rango Antiguedad'] = np.select(conds, labels, default='Sin Dato')
    
    # Auxiliares para filtros
    df['Año_Ingreso'] = df[col_fecha_real].dt.year.fillna(0).astype(int)
    df['Mes_Ingreso'] = df[col_fecha_real].dt.month_name().fillna("Sin Dato")
    df['AñoMes'] = df[col_fecha_real].dt.strftime('%Y-%m')
else:
    # Si falla la detección, creamos columnas vacías para que no rompa la app
    st.warning(f"⚠️ No se detectó la columna de fecha. Columnas encontradas: {list(df.columns)}")
    df['Rango Antiguedad'] = "N/A"
    df['Año_Ingreso'] = 0
    df['Mes_Ingreso'] = "N/A"
    df['AñoMes'] = "N/A"

# --- 5. INTERFAZ ---
header_col1, header_col2 = st.columns([4, 1])
with header_col1:
    st.markdown("<h1>ESTRUCTURA</h1>", unsafe_allow_html=True)
with header_col2:
    st.image("https://upload.wikimedia.org/wikipedia/commons/e/ee/Toyota_logo_%28Red%29.svg", width=120)

tabs = st.tabs(["ESTRUCTURA", "ESTRUCTURA TASA", "ROTACIÓN", "AUSENTISMO"])

# PESTAÑA ESTRUCTURA
with tabs[0]:
    # FILTRO BASE REQUERIDO: ACTIVO Y AUTOLUX
    # Buscamos columnas ignorando mayúsculas/minúsculas
    col_estado = next((c for c in df.columns if c.upper() == 'ESTADO'), 'ESTADO')
    col_empresa = next((c for c in df.columns if c.upper() == 'EMPRESA'), 'EMPRESA')

    try:
        df_activos = df[(df[col_estado].astype(str).str.upper() == 'ACTIVO') & 
                        (df[col_empresa].astype(str).str.upper() == 'AUTOLUX')].copy()
    except:
        df_activos = df.copy()

    # Filtros Superiores
    f1, f2, f3, f4 = st.columns(4)
    with f1: sel_loc = st.multiselect("Localidad", sorted(df_activos['Localidad'].unique().tolist()) if 'Localidad' in df_activos.columns else [])
    with f2: sel_mes = st.multiselect("Mes", sorted(df_activos['Mes_Ingreso'].unique().tolist()))
    with f3: sel_anio = st.multiselect("Año", sorted([int(x) for x in df_activos['Año_Ingreso'].unique() if x > 0]))
    with f4: sel_area = st.multiselect("Área", sorted(df_activos['Area'].unique().tolist()) if 'Area' in df_activos.columns else [])

    # Aplicar Filtros
    dff = df_activos.copy()
    if sel_loc: dff = dff[dff['Localidad'].isin(sel_loc)]
    if sel_mes: dff = dff[dff['Mes_Ingreso'].isin(sel_mes)]
    if sel_anio: dff = dff[dff['Año_Ingreso'].isin(sel_anio)]
    if sel_area: dff = dff[dff['Area'].isin(sel_area)]

    col_izq, col_der = st.columns([2, 3])
    
    with col_izq:
        st.metric("Dotación", len(dff))
        st.markdown("### Matriz por Área y Puesto")
        if all(x in dff.columns for x in ['Area', 'Puesto', 'Localidad']):
            pivot = pd.pivot_table(dff, index=['Area', 'Puesto'], columns='Localidad', values=col_empresa, aggfunc='count', fill_value=0, margins=True, margins_name='Total')
            st.dataframe(pivot, use_container_width=True)

    with col_der:
        st.markdown("### Dotación Histórica")
        if 'AñoMes' in dff.columns and not dff['AñoMes'].isnull().all():
            hist_data = dff.groupby('AñoMes').size().reset_index(name='Dotacion')
            st.plotly_chart(px.line(hist_data, x='AñoMes', y='Dotacion', color_discrete_sequence=['#EB0A1E']), use_container_width=True)

        c_sub1, c_sub2 = st.columns(2)
        with c_sub1:
            st.markdown("### Antigüedad")
            if 'Rango Antiguedad' in dff.columns:
                fig_pie = px.pie(dff, names='Rango Antiguedad', hole=0.6, color_discrete_sequence=['#EB0A1E', '#58595B', '#939598', '#D1D3D4'])
                fig_pie.update_layout(showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=-0.5))
                st.plotly_chart(fig_pie, use_container_width=True)
        with c_sub2:
            st.markdown("### Categoría")
            if 'Categoría' in dff.columns:
                cat_counts = dff['Categoría'].value_counts().reset_index()
                st.plotly_chart(px.bar(cat_counts, y='Categoría', x='count', orientation='h', color_discrete_sequence=['#EB0A1E']), use_container_width=True)
