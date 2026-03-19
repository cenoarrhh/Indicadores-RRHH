import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
import calendar

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Autolux Business Intelligence", layout="wide")

# Estilo CSS Personalizado (Rojo Toyota / Estilo Profesional)
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    h1, h2, h3 { color: #EB0A1E; font-family: 'Arial'; font-weight: bold; margin-bottom: 5px; }
    .stMetric { background-color: #f8f9fa; border-left: 5px solid #EB0A1E; border-radius: 5px; padding: 15px; }
    div[data-testid="stMetricValue"] { color: #000000; font-size: 40px !important; font-weight: bold; }
    div[data-testid="stMetricLabel"] { color: #EB0A1E; font-weight: bold; }
    section[data-testid="stSidebar"] { background-color: #f1f3f6; }
    .stSelectbox label { color: #333; font-weight: bold; }
    /* Estilo para la Matriz */
    .stDataFrame { border: 1px solid #e6e6e6; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CARGA DE DATOS ---
url = "https://docs.google.com/spreadsheets/d/156gG4r3krIiXEF9nIqsoJoh9YB_kcdhJittobHbxZ9s/edit?gid=1344313191#gid=1344313191"

@st.cache_data(ttl=300)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(spreadsheet=url)
    # Limpieza de nombres de columnas (quita espacios invisibles)
    df.columns = [str(c).strip() for c in df.columns]
    
    # Conversión de fechas respetando nombres del Sheet
    if "Fecha de ingreso" in df.columns:
        df["Fecha de ingreso"] = pd.to_datetime(df["Fecha de ingreso"], errors='coerce')
    if "FECHA EGRESO" in df.columns:
        df["FECHA EGRESO"] = pd.to_datetime(df["FECHA EGRESO"], errors='coerce')
    return df

try:
    df_raw = load_data()
    df_base = df_raw.copy()
except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")
    st.stop()

# --- 3. BARRA LATERAL (FILTROS DE PERIODO HISTÓRICO) ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/e/ee/Toyota_logo_%28Red%29.svg", width=120)
st.sidebar.markdown("### 📅 Periodo de Análisis")

# Restricción de años desde 2022
año_actual = datetime.now().year
años_disponibles = [a for a in range(2022, año_actual + 1)]
sel_año = st.sidebar.selectbox("Seleccione Año", sorted(años_disponibles, reverse=True))

meses_esp = {
    "Enero":1, "Febrero":2, "Marzo":3, "Abril":4, "Mayo":5, "Junio":6,
    "Julio":7, "Agosto":8, "Septiembre":9, "Octubre":10, "Noviembre":11, "Diciembre":12
}
sel_mes_nombre = st.sidebar.selectbox("Seleccione Mes", list(meses_esp.keys()), index=datetime.now().month - 1)
sel_mes_num = meses_esp[sel_mes_nombre]

# Cálculo de la Fecha de Corte (Snapshot al último día del mes seleccionado)
ultimo_dia = calendar.monthrange(sel_año, sel_mes_num)[1]
fecha_corte = pd.Timestamp(datetime(sel_año, sel_mes_num, ultimo_dia))

# --- 4. FILTRADO DE DOTACIÓN HISTÓRICA (Lógica DAX) ---
# Ingreso <= Corte Y (Egreso es Nulo O Egreso > Corte) Y Empresa Autolux
df_snapshot = df_base[
    (df_base["Fecha de ingreso"] <= fecha_corte) & 
    ((df_base["FECHA EGRESO"].isna()) | (df_base["FECHA EGRESO"] > fecha_corte)) &
    (df_base["EMPRESA"].astype(str).str.upper() == "AUTOLUX")
].copy()

# Filtros adicionales de Estructura
st.sidebar.markdown("---")
loc_options = ["Todas"] + sorted(df_snapshot["Localidad"].dropna().unique().tolist()) if "Localidad" in df_snapshot.columns else ["Todas"]
sel_loc = st.sidebar.selectbox("Localidad", loc_options)

area_options = ["Todas"] + sorted(df_snapshot["Area"].dropna().unique().tolist()) if "Area" in df_snapshot.columns else ["Todas"]
sel_area = st.sidebar.selectbox("Área", area_options)

# Aplicación de filtros de selección única
dff = df_snapshot.copy()
if sel_loc != "Todas":
    dff = dff[dff["Localidad"] == sel_loc]
if sel_area != "Todas":
    dff = dff[dff["Area"] == sel_area]

# --- 5. CUERPO DEL DASHBOARD ---
st.title("Estructura de Dotación")
st.markdown(f"**Análisis al:** {ultimo_dia} de {sel_mes_nombre}, {sel_año}")

tab1, tab2, tab3 = st.tabs(["ESTRUCTURA", "ESTRUCTURA TASA", "EVOLUCIÓN"])

# ==========================================
# PESTAÑA: ESTRUCTURA (Matriz Dinámica)
# ==========================================
with tab1:
    col_kpi, _ = st.columns([1, 3])
    with col_kpi:
        st.metric("Dotación Activa", len(dff))

    st.markdown("---")
    st.subheader("Matriz de Colaboradores (Jerarquía: Área > Sector > Puesto)")
    
    # Columnas para la jerarquía de filas y columnas
    niveles_filas = [n for n in ["Area", "Sector", "Puesto"] if n in dff.columns]

    if niveles_filas and "Localidad" in dff.columns:
        try:
            # Creación de la Tabla Dinámica (Pivot Table)
            matriz_dinamica = pd.pivot_table(
                dff,
                index=niveles_filas,
                columns="Localidad",
                values="EMPRESA", # Columna base para el conteo
                aggfunc="count",
                fill_value=0,
                margins=True,       # Columna y fila de TOTAL
                margins_name="Total General"
            )
            st.dataframe(matriz_dinamica, use_container_width=True, height=600)
        except Exception as e:
            st.error(f"Error al generar la matriz dinámica: {e}")
    else:
        st.warning("Verifique que las columnas 'Area', 'Sector', 'Puesto' y 'Localidad' existan en el origen de datos.")

    # Gráficos de Soporte
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Distribución por Antigüedad")
        def calcular_rango(fecha):
            if pd.isna(fecha): return "Sin Dato"
            anios = (fecha_corte - fecha).days / 365.25
            if anios <= 1: return "Hasta 1 año"
            if anios <= 3: return "1-3 años"
            if anios <= 5: return "3-5 años"
            if anios <= 10: return "5-10 años"
            return "Más de 10 años"
        
        dff["Rango"] = dff["Fecha de ingreso"].apply(calcular_rango)
        fig_pie = px.pie(dff, names="Rango", hole=0.5, 
                         color_discrete_sequence=px.colors.sequential.Reds_r,
                         category_orders={"Rango": ["Hasta 1 año", "1-3 años", "3-5 años", "5-10 años", "Más de 10 años"]})
        st.plotly_chart(fig_pie, use_container_width=True)

    with c2:
        st.markdown("### Dotación por Categoría")
        if "Categoría" in dff.columns:
            cat_df = dff["Categoría"].value_counts().reset_index()
            cat_df.columns = ["Categoría", "Cant"]
            fig_cat = px.bar(cat_df.sort_values("Cant"), y="Categoría", x="Cant", 
                             orientation='h', color_discrete_sequence=["#EB0A1E"])
            fig_cat.update_layout(yaxis={'title':''}, xaxis={'title':''})
            st.plotly_chart(fig_cat, use_container_width=True)

# ==========================================
# PESTAÑA: ESTRUCTURA TASA
# ==========================================
with tab2:
    st.subheader("Análisis TASA (Online Toyota)")
    col_tasa = "Declarados" # Ajustar si el nombre de columna de flag TASA es diferente
    
    if col_tasa in dff.columns:
        df_on = dff[dff[col_tasa].astype(str).str.upper().str.contains("SI|DECLARADO|1", na=False)]
        
        m1, m2 = st.columns(2)
        with m1:
            st.metric("Dotación Histórica OnlineToyota", len(df_on))
        with m2:
            porcentaje = (len(df_on)/len(dff)*100) if len(dff)>0 else 0
            st.metric("% de Declaración TASA", f"{porcentaje:.1f}%")
        
        st.markdown("### Comparativa por Área")
        comp_tasa = dff.groupby(["Area", col_tasa]).size().reset_index(name="Cantidad")
        fig_tasa = px.bar(comp_tasa, x="Area", y="Cantidad", color=col_tasa, barmode="group",
                          color_discrete_map={"Declarado":"#EB0A1E", "No Declarado":"#58595B", "SI":"#EB0A1E", "NO":"#58595B"})
        st.plotly_chart(fig_tasa, use_container_width=True)
