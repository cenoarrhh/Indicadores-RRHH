import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
import calendar

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Dashboard Autolux BI", layout="wide")

# Estilo CSS Personalizado (Identidad Toyota / Autolux)
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    h1 { color: #EB0A1E; font-family: 'Arial'; font-weight: bold; margin-bottom: 0px; }
    h3 { color: #333333; font-family: 'Arial'; font-weight: bold; }
    .stMetric { background-color: #ffffff; border: 1px solid #EB0A1E; padding: 10px; border-radius: 5px; }
    div[data-testid="stMetricValue"] { color: #000000; font-size: 45px !important; font-weight: bold; }
    div[data-testid="stMetricLabel"] { color: #EB0A1E; font-weight: bold; }
    .stTabs [aria-selected="true"] { background-color: #004F43 !important; color: white !important; font-weight: bold; }
    /* Estilo para tablas */
    .stDataFrame { border: 1px solid #e6e6e6; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CARGA DE DATOS ---
url = "https://docs.google.com/spreadsheets/d/156gG4r3krIiXEF9nIqsoJoh9YB_kcdhJittobHbxZ9s/edit?gid=1344313191#gid=1344313191"

@st.cache_data(ttl=300)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(spreadsheet=url)
    # Limpieza de nombres de columnas (quitar espacios en blanco invisibles)
    df.columns = [str(c).strip() for c in df.columns]
    
    # Conversión de fechas (Ingreso: Col G | Egreso: Col Z)
    if "Fecha de ingreso" in df.columns:
        df["Fecha de ingreso"] = pd.to_datetime(df["Fecha de ingreso"], errors='coerce')
    if "FECHA EGRESO" in df.columns:
        df["FECHA EGRESO"] = pd.to_datetime(df["FECHA EGRESO"], errors='coerce')
    return df

try:
    df_base = load_data()
except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")
    st.stop()

# --- 3. FILTROS DE PERIODO (Sidebar) ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/e/ee/Toyota_logo_%28Red%29.svg", width=120)
st.sidebar.markdown("### 📅 Periodo de Análisis")

# Restricción de años desde 2022 según requerimiento
año_actual = datetime.now().year
años_disponibles = sorted([a for a in range(2022, año_actual + 1)], reverse=True)
sel_año = st.sidebar.selectbox("Seleccione Año", años_disponibles, index=0)

meses_esp = {
    "Enero":1, "Febrero":2, "Marzo":3, "Abril":4, "Mayo":5, "Junio":6,
    "Julio":7, "Agosto":8, "Septiembre":9, "Octubre":10, "Noviembre":11, "Diciembre":12
}
# Mes por defecto es el actual
sel_mes_nombre = st.sidebar.selectbox("Seleccione Mes", list(meses_esp.keys()), index=datetime.now().month - 1)
sel_mes_num = meses_esp[sel_mes_nombre]

# Cálculo de la Fecha de Corte (Snapshot al último día del mes seleccionado)
ultimo_dia = calendar.monthrange(sel_año, sel_mes_num)[1]
fecha_corte = pd.Timestamp(datetime(sel_año, sel_mes_num, ultimo_dia))

# --- 4. LÓGICA DE DOTACIÓN HISTÓRICA ---
# Filtro: Ingreso <= Fecha Corte Y (Egreso es Nulo O Egreso > Fecha Corte)
df_snap = df_base[
    (df_base["Fecha de ingreso"] <= fecha_corte) & 
    ((df_base["FECHA EGRESO"].isna()) | (df_base["FECHA EGRESO"] > fecha_corte)) &
    (df_base["EMPRESA"].astype(str).str.upper() == "AUTOLUX")
].copy()

# Filtros adicionales de Estructura (Selección única)
st.sidebar.markdown("---")
loc_options = ["Todas"] + sorted(df_snap["Localidad"].dropna().unique().tolist()) if "Localidad" in df_snap.columns else ["Todas"]
sel_loc = st.sidebar.selectbox("Localidad", loc_options)

area_options = ["Todas"] + sorted(df_snap["Area"].dropna().unique().tolist()) if "Area" in df_snap.columns else ["Todas"]
sel_area = st.sidebar.selectbox("Área", area_options)

# Aplicación de filtros finales
dff = df_snap.copy()
if sel_loc != "Todas":
    dff = dff[dff["Localidad"] == sel_loc]
if sel_area != "Todas":
    dff = dff[dff["Area"] == sel_area]

# --- 5. CUERPO DEL DASHBOARD ---
# Cabecera
head_1, head_2 = st.columns([4, 1])
with head_1:
    st.markdown("<h1>ESTRUCTURA</h1>", unsafe_allow_html=True)
with head_2:
    st.image("https://upload.wikimedia.org/wikipedia/commons/e/ee/Toyota_logo_%28Red%29.svg", width=100)
    st.markdown("<p style='text-align:right; font-weight:bold; margin-top:-10px;'>Autolux</p>", unsafe_allow_html=True)

tabs = st.tabs(["ESTRUCTURA", "ESTRUCTURA TASA"])

# ==========================================
# PESTAÑA 1: ESTRUCTURA
# ==========================================
with tabs[0]:
    # Fila de KPI y Gráfico de Evolución
    col_kpi, col_evol = st.columns([1, 3])
    
    with col_kpi:
        st.metric("Dotación", len(dff))
        st.write(f"Snapshot: {sel_mes_nombre} {sel_año}")

    with col_evol:
        # Cálculo de Evolución Mensual dinámica para el gráfico de líneas
        # Se calculan los activos al final de cada mes hasta la fecha de corte
        rango_meses = pd.date_range(start="2022-01-01", end=fecha_corte, freq='ME')
        data_evol = []
        for fecha in rango_meses:
            conteo = len(df_base[
                (df_base["Fecha de ingreso"] <= fecha) & 
                ((df_base["FECHA EGRESO"].isna()) | (df_base["FECHA EGRESO"] > fecha)) &
                (df_base["EMPRESA"].astype(str).str.upper() == "AUTOLUX")
            ])
            data_evol.append({"Fecha": fecha.strftime('%Y-%m'), "Colaboradores": conteo})
        
        df_linea = pd.DataFrame(data_evol)
        fig_linea = px.line(df_linea, x="Fecha", y="Colaboradores", title="Evolución de Dotación Histórica",
                           color_discrete_sequence=["#EB0A1E"])
        fig_linea.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_linea, use_container_width=True)

    # Fila de Matriz y Gráficos de Soporte
    col_mat, col_pie_bar = st.columns([2.5, 2])

    with col_mat:
        st.markdown("### Matriz de Dotación (Área > Sector > Puesto)")
        # Definición de niveles jerárquicos
        niveles = [n for n in ["Area", "Sector", "Puesto"] if n in dff.columns]
        
        if niveles and "Localidad" in dff.columns:
            # Creación de la Matriz estilo Power BI
            pivot_matriz = pd.pivot_table(
                dff,
                index=niveles,
                columns="Localidad",
                values="EMPRESA",
                aggfunc="count",
                fill_value=0,
                margins=True,
                margins_name="Total"
            )
            st.dataframe(pivot_matriz, use_container_width=True, height=600)

    with col_pie_bar:
        # Gráfico de Antigüedad
        st.markdown("### Antigüedad")
        def calc_rango_ant(f_ing):
            if pd.isna(f_ing): return "Sin Dato"
            anios = (fecha_corte - f_ing).days / 365.25
            if anios <= 1: return "Hasta 1 año"
            if anios <= 3: return "1-3 años"
            if anios <= 5: return "3-5 años"
            if anios <= 10: return "5-10 años"
            return "Más de 10 años"
        
        dff["Rango_Ant"] = dff["Fecha de ingreso"].apply(calc_rango_ant)
        orden_ant = ["Hasta 1 año", "1-3 años", "3-5 años", "5-10 años", "Más de 10 años"]
        fig_ant = px.pie(dff, names="Rango_Ant", hole=0.5, 
                         color_discrete_sequence=px.colors.sequential.Reds_r,
                         category_orders={"Rango_Ant": orden_ant})
        fig_ant.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_ant, use_container_width=True)

        # Gráfico de Categoría (Barras Horizontales)
        st.markdown("### Categoría")
        if "Categoría" in dff.columns:
            df_cat = dff["Categoría"].value_counts().reset_index()
            df_cat.columns = ["Categoría", "Dotación"]
            fig_cat = px.bar(df_cat.sort_values("Dotación"), y="Categoría", x="Dotación", 
                             orientation='h', color_discrete_sequence=["#EB0A1E"])
            fig_cat.update_layout(height=300, margin=dict(l=0, r=0, t=30, b=0), yaxis={'title':''})
            st.plotly_chart(fig_cat, use_container_width=True)

# ==========================================
# PESTAÑA 2: ESTRUCTURA TASA
# ==========================================
with tabs[1]:
    st.subheader("Análisis TASA (Online Toyota)")
    # Columna flag para TASA
    col_tasa = "Declarados" 
    if col_tasa in dff.columns:
        df_online = dff[dff[col_tasa].astype(str).str.upper().str.contains("SI|DECLARADO|1", na=False)]
        
        m_t1, m_t2 = st.columns(2)
        with m_t1:
            st.metric("Dotación Online Toyota", len(df_online))
        with m_t2:
            porc = (len(df_online)/len(dff)*100) if len(dff)>0 else 0
            st.metric("% de Declaración TASA", f"{porc:.1f}%")
        
        st.markdown("### Comparativa de Declaración por Área")
        df_comp = dff.groupby(["Area", col_tasa]).size().reset_index(name="Cantidad")
        fig_tasa = px.bar(df_comp, x="Area", y="Cantidad", color=col_tasa, barmode="group",
                          color_discrete_map={"Declarado":"#EB0A1E", "No Declarado":"#58595B", "SI":"#EB0A1E", "NO":"#58595B"})
        st.plotly_chart(fig_tasa, use_container_width=True)
