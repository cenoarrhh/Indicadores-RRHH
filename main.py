import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# --- 1. CONFIGURACIÓN DE PÁGINA Y ESTILO ---
st.set_page_config(page_title="Dashboard Autolux", layout="wide")

# Estilo CSS para replicar la estética de Power BI (Toyota Red)
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    h1 { color: #EB0A1E; font-family: 'Arial'; font-weight: bold; }
    .stMetric { background-color: #f9f9f9; border: 1px solid #e6e6e6; padding: 15px; border-radius: 5px; }
    div[data-testid="stMetricValue"] { color: #000000; font-size: 45px !important; }
    div[data-testid="stMetricLabel"] { color: #EB0A1E; font-weight: bold; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { 
        background-color: #f0f2f6; 
        border-radius: 4px 4px 0 0; 
        padding: 10px 20px; 
        font-weight: bold;
    }
    .stTabs [aria-selected="true"] { background-color: #004F43 !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CARGA DE DATOS ---
url = "https://docs.google.com/spreadsheets/d/156gG4r3krIiXEF9nIqsoJoh9YB_kcdhJittobHbxZ9s/edit?gid=1344313191#gid=1344313191"

@st.cache_data(ttl=600)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(spreadsheet=url)
    return df

df_raw = load_data()
df = df_raw.copy()

# --- 3. PREPARACIÓN DE DATOS (ETL) ---
# Limpieza de columnas críticas
for col in ['ESTADO', 'EMPRESA', 'Declarados', 'Area', 'Localidad', 'Puesto']:
    if col in df.columns:
        df[col] = df[col].astype(str).str.strip()

# Procesamiento de Fechas
if 'Fecha Ingreso' in df.columns:
    df['Fecha Ingreso'] = pd.to_datetime(df['Fecha Ingreso'], errors='coerce')
    df['Año'] = df['Fecha Ingreso'].dt.year.fillna(0).astype(int)
    df['Mes'] = df['Fecha Ingreso'].dt.month_name()
    df['AñoMes'] = df['Fecha Ingreso'].dt.strftime('%Y-%m')

# Cálculo de Antigüedad
if 'Fecha Ingreso' in df.columns:
    hoy = pd.Timestamp.now()
    df['Meses_Antiguedad'] = ((hoy - df['Fecha Ingreso']).dt.days / 30).fillna(0)
    conditions = [
        (df['Meses_Antiguedad'] <= 12),
        (df['Meses_Antiguedad'] > 12) & (df['Meses_Antiguedad'] <= 36),
        (df['Meses_Antiguedad'] > 36) & (df['Meses_Antiguedad'] <= 60),
        (df['Meses_Antiguedad'] > 60)
    ]
    labels = ['Hasta 1 año', '1-3 años', '3-5 años', 'Más de 5 años']
    df['Rango Antiguedad'] = np.select(conditions, labels, default='Sin Dato')

# --- 4. INTERFAZ ---
header_col1, header_col2 = st.columns([4, 1])
with header_col1:
    st.title("ESTRUCTURA")
with header_col2:
    st.image("https://upload.wikimedia.org/wikipedia/commons/e/ee/Toyota_logo_%28Red%29.svg", width=120)
    st.markdown("<p style='text-align:right; font-weight:bold;'>Autolux</p>", unsafe_allow_html=True)

tabs = st.tabs(["ESTRUCTURA", "ESTRUCTURA TASA", "ROTACIÓN", "AUSENTISMO"])

# ==========================================
# PESTAÑA 1: ESTRUCTURA (Activos Autolux)
# ==========================================
with tabs[0]:
    # Filtro base obligatorio
    df_activos = df[(df['ESTADO'] == 'ACTIVO') & (df['EMPRESA'] == 'AUTOLUX')].copy()

    # Filtros Interactivos Superiores
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        sel_loc = st.multiselect("Localidad", sorted(df_activos['Localidad'].unique() if 'Localidad' in df_activos.columns else []))
    with f2:
        sel_mes = st.multiselect("Mes", sorted(df_activos['Mes'].unique() if 'Mes' in df_activos.columns else []))
    with f3:
        sel_anio = st.multiselect("Año", sorted(df_activos['Año'].unique() if 'Año' in df_activos.columns else []))
    with f4:
        sel_area = st.multiselect("Área", sorted(df_activos['Area'].unique() if 'Area' in df_activos.columns else []))

    # Aplicar filtros
    dff = df_activos.copy()
    if sel_loc: dff = dff[dff['Localidad'].isin(sel_loc)]
    if sel_mes: dff = dff[dff['Mes'].isin(sel_mes)]
    if sel_anio: dff = dff[dff['Año'].isin(sel_anio)]
    if sel_area: dff = dff[dff['Area'].isin(sel_area)]

    col_izq, col_der = st.columns([2, 3])

    with col_izq:
        # KPI Dotación
        st.metric("Dotación", len(dff))
        
        # Tabla Dinámica (Matriz)
        st.markdown("### Detalle por Área y Puesto")
        if all(x in dff.columns for x in ['Area', 'Puesto', 'Localidad']):
            pivot = pd.pivot_table(dff, index=['Area', 'Puesto'], columns='Localidad', values='EMPRESA', aggfunc='count', fill_value=0, margins=True, margins_name='Total')
            st.dataframe(pivot, use_container_width=True)

    with col_der:
        # Gráfico Histórico
        st.markdown("### Evolución de Dotación")
        if 'AñoMes' in dff.columns:
            hist_data = dff.groupby('AñoMes').size().reset_index(name='Dotacion')
            fig_line = px.line(hist_data, x='AñoMes', y='Dotacion', color_discrete_sequence=['#EB0A1E'])
            st.plotly_chart(fig_line, use_container_width=True)

        c_sub1, c_sub2 = st.columns(2)
        with c_sub1:
            st.markdown("### Antigüedad")
            fig_pie = px.pie(dff, names='Rango Antiguedad', hole=0.6, color_discrete_sequence=['#EB0A1E', '#58595B', '#939598', '#D1D3D4'])
            st.plotly_chart(fig_pie, use_container_width=True)
        with c_sub2:
            st.markdown("### Categoría")
            if 'Categoría' in dff.columns:
                cat_data = dff['Categoría'].value_counts().reset_index()
                fig_bar = px.bar(cat_data, y='Categoría', x='count', orientation='h', color_discrete_sequence=['#EB0A1E'])
                st.plotly_chart(fig_bar, use_container_width=True)

# ==========================================
# PESTAÑA 2: ESTRUCTURA TASA
# ==========================================
with tabs[1]:
    st.subheader("Colaboradores Declarados en Toyota")
    if 'Declarados' in df.columns:
        # Filtramos solo Autolux para consistencia
        df_tasa = df[df['EMPRESA'] == 'AUTOLUX'].copy()
        
        c1, c2 = st.columns([1, 3])
        with c1:
            dot_tasa = len(df_tasa[df_tasa['Declarados'].str.upper().str.contains("SI|DECLARADO", na=False)])
            st.metric("Dotación TASA", dot_tasa)
        with c2:
            fig_tasa = px.bar(df_tasa, x='Area', color='Declarados', barmode='group', color_discrete_map={'Declarado': '#EB0A1E', 'No Declarado': '#000000'})
            st.plotly_chart(fig_tasa, use_container_width=True)

# ==========================================
# PESTAÑA 3: ROTACIÓN
# ==========================================
with tabs[2]:
    st.subheader("Indicadores de Rotación")
    # Usando columnas exactas: 'bajas de Rotación real' y 'bajas de delcarados'
    r1, r2, r3 = st.columns(3)
    with r1:
        b_real = df['bajas de Rotación real'].sum() if 'bajas de Rotación real' in df.columns else 0
        st.metric("Bajas Rotación Real", int(b_real))
    with r2:
        b_tasa = df['bajas de delcarados'].sum() if 'bajas de delcarados' in df.columns else 0
        st.metric("Bajas Rotación TASA", int(b_tasa))
    with r3:
        st.write("Target 2026: **9.00%**")
        fig_gauge = go.Figure(go.Indicator(mode="gauge+number", value=9.00, gauge={'axis': {'range': [0, 15]}, 'bar': {'color': "#EB0A1E"}}))
        fig_gauge.update_layout(height=200)
        st.plotly_chart(fig_gauge, use_container_width=True)

# ==========================================
# PESTAÑA 4: AUSENTISMO
# ==========================================
with tabs[3]:
    st.subheader("Análisis de Ausentismo")
    # Usando columna exacta: 'politica'
    if 'politica' in df.columns:
        aus_col1, aus_col2 = st.columns(2)
        with aus_col1:
            fig_aus1 = px.pie(df, names='politica', title="Por Política", hole=0.4, color_discrete_sequence=px.colors.sequential.Reds_r)
            st.plotly_chart(fig_aus1, use_container_width=True)
        with aus_col2:
            # Replicamos el gráfico de barras por motivo si existe la columna
            col_motivo = 'Motivo Licencia' if 'Motivo Licencia' in df.columns else 'politica'
            fig_aus2 = px.bar(df, x=col_motivo, title="Días por Motivo", color_discrete_sequence=['#EB0A1E'])
            st.plotly_chart(fig_aus2, use_container_width=True)
