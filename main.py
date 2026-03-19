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

# Estilo CSS para replicar la identidad visual de Autolux/Toyota
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    h1, h2, h3 { color: #EB0A1E; font-family: 'Arial'; font-weight: bold; }
    .stMetric { background-color: #f8f9fa; border-left: 5px solid #EB0A1E; border-radius: 5px; padding: 15px; }
    div[data-testid="stMetricValue"] { color: #000000; font-size: 40px !important; font-weight: bold; }
    div[data-testid="stMetricLabel"] { color: #EB0A1E; font-weight: bold; font-size: 16px !important; }
    .stTabs [aria-selected="true"] { background-color: #004F43 !important; color: white !important; font-weight: bold; }
    .stDataFrame { border: 1px solid #e6e6e6; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CARGA DE DATOS ---
url = "https://docs.google.com/spreadsheets/d/156gG4r3krIiXEF9nIqsoJoh9YB_kcdhJittobHbxZ9s/edit?gid=1344313191#gid=1344313191"

@st.cache_data(ttl=300)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(spreadsheet=url)
    # Limpiar nombres de columnas (quitar espacios extras)
    df.columns = [str(c).strip() for c in df.columns]
    
    # Conversión de fechas respetando los nombres del Sheet
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

# --- 3. LÓGICA DE CALENDARIO Y FILTROS (SIDEBAR) ---
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/e/ee/Toyota_logo_%28Red%29.svg", width=100)
st.sidebar.header("📅 Periodo de Análisis")

# Selección de Año y Mes para la "Fecha de Corte"
años_disponibles = sorted(df_base["Fecha de ingreso"].dt.year.dropna().unique().astype(int), reverse=True)
sel_año = st.sidebar.selectbox("Seleccione Año", años_disponibles, index=0)

meses_esp = {
    "Enero":1, "Febrero":2, "Marzo":3, "Abril":4, "Mayo":5, "Junio":6,
    "Julio":7, "Agosto":8, "Septiembre":9, "Octubre":10, "Noviembre":11, "Diciembre":12
}
sel_mes_nombre = st.sidebar.selectbox("Seleccione Mes", list(meses_esp.keys()), index=datetime.now().month - 1)
sel_mes_num = meses_esp[sel_mes_nombre]

# Definir la Fecha de Corte (último día del mes seleccionado)
ultimo_dia = calendar.monthrange(sel_año, sel_mes_num)[1]
fecha_corte = pd.Timestamp(datetime(sel_año, sel_mes_num, ultimo_dia))

# --- 4. CÁLCULO DE DOTACIÓN HISTÓRICA (Lógica DAX) ---
# Empleado activo si: Ingreso <= Fecha Corte Y (Egreso es Nulo O Egreso > Fecha Corte)
df_historico = df_base[
    (df_base["Fecha de ingreso"] <= fecha_corte) & 
    ((df_base["FECHA EGRESO"].isna()) | (df_base["FECHA EGRESO"] > fecha_corte)) &
    (df_base["EMPRESA"].astype(str).str.upper() == "AUTOLUX")
].copy()

# Filtros adicionales
st.sidebar.markdown("---")
loc_options = sorted(df_historico["Localidad"].dropna().unique().tolist()) if "Localidad" in df_historico.columns else []
sel_loc = st.sidebar.multiselect("Localidad", loc_options)

dff = df_historico.copy()
if sel_loc:
    dff = dff[dff["Localidad"].isin(sel_loc)]

# --- 5. CUERPO DEL DASHBOARD ---
st.title(f"Visualización de Estructura - {sel_mes_nombre} {sel_año}")

tabs = st.tabs(["ESTRUCTURA", "ESTRUCTURA TASA", "ROTACIÓN", "AUSENTISMO"])

# ==========================================
# PESTAÑA 1: ESTRUCTURA
# ==========================================
with tabs[0]:
    # KPIs Principales
    k1, k2, k3 = st.columns(3)
    with k1:
        st.metric("Dotación Histórica AUTOLUX", len(dff))
    with k2:
        # Dotación Actual (Solo los que hoy son Activos y de Autolux)
        actual = df_base[(df_base["ESTADO"].astype(str).str.upper() == "ACTIVO") & (df_base["EMPRESA"].astype(str).str.upper() == "AUTOLUX")]
        st.metric("Dotación Actual Real", len(actual))

    col_izq, col_der = st.columns([2.5, 2])

    with col_izq:
        # TABLA MATRIZ (Área > Sector > Puesto)
        st.markdown("### Matriz de Dotación")
        niveles = [n for n in ["Area", "Sector", "Puesto"] if n in dff.columns]
        if niveles and "Localidad" in dff.columns:
            pivot = pd.pivot_table(dff, index=niveles, columns="Localidad", 
                                   values="EMPRESA", aggfunc="count", fill_value=0, margins=True, margins_name="Total")
            st.dataframe(pivot, use_container_width=True, height=500)

        # GRÁFICO EVOLUCIÓN (Líneas)
        st.markdown("### Evolución Histórica de Dotación")
        # Generar historial hasta la fecha de corte
        hist_evolucion = []
        # Agrupamos por mes/año de ingreso para ver el acumulado
        df_base["AñoMesNum"] = df_base["Fecha de ingreso"].dt.year * 100 + df_base["Fecha de ingreso"].dt.month
        corte_num = sel_año * 100 + sel_mes_num
        
        # Filtramos solo registros de Autolux previos al corte para el gráfico
        df_prog = df_base[(df_base["AñoMesNum"] <= corte_num) & (df_base["EMPRESA"].astype(str).str.upper() == "AUTOLUX")]
        df_prog_sorted = df_prog.sort_values("AñoMesNum")
        df_prog_sorted["AñoMesStr"] = df_prog_sorted["Fecha de ingreso"].dt.strftime('%Y-%m')
        
        evol_data = df_prog_sorted.groupby("AñoMesStr").size().cumsum().reset_index(name="Dotación")
        fig_line = px.line(evol_data, x="AñoMesStr", y="Dotación", color_discrete_sequence=["#EB0A1E"])
        fig_line.update_layout(xaxis_title="Periodo", yaxis_title="Colaboradores")
        st.plotly_chart(fig_line, use_container_width=True)

    with col_der:
        # GRÁFICO ANTIGÜEDAD (Donut)
        st.markdown("### Antigüedad")
        def calc_antiguedad_rango(fecha):
            if pd.isna(fecha): return "Sin Dato"
            dias = (fecha_corte - fecha).days
            anios = dias / 365.25
            if anios <= 1: return "Hasta 1 año"
            if anios <= 3: return "1-3 años"
            if anios <= 5: return "3-5 años"
            if anios <= 10: return "5-10 años"
            return "Más de 10 años"

        dff["RangoAntiguedad"] = dff["Fecha de ingreso"].apply(calc_antiguedad_rango)
        fig_pie = px.pie(dff, names="RangoAntiguedad", hole=0.5, 
                         color_discrete_sequence=px.colors.sequential.Reds_r,
                         category_orders={"RangoAntiguedad": ["Hasta 1 año", "1-3 años", "3-5 años", "5-10 años", "Más de 10 años"]})
        st.plotly_chart(fig_pie, use_container_width=True)

        # GRÁFICO CATEGORÍA (Barras Horizontales)
        st.markdown("### Categoría")
        if "Categoría" in dff.columns:
            cat_df = dff["Categoría"].value_counts().reset_index()
            cat_df.columns = ["Categoría", "Cantidad"]
            fig_bar = px.bar(cat_df.sort_values("Cantidad"), y="Categoría", x="Cantidad", 
                             orientation='h', color_discrete_sequence=["#EB0A1E"])
            st.plotly_chart(fig_bar, use_container_width=True)

# ==========================================
# PESTAÑA 2: ESTRUCTURA TASA
# ==========================================
with tabs[1]:
    st.title("Estructura TASA (Online Toyota)")
    
    # Lógica de IDs o Flags para Declarados
    # Basado en tu DAX: ID_OnlineToyota = 1 (Declarado)
    col_tasa = "Declarados" # Ajustar al nombre real de tu columna de flag Toyota
    if col_tasa in dff.columns:
        df_on = dff[dff[col_tasa].astype(str).str.upper().str.contains("SI|DECLARADO|1", na=False)]
        df_off = dff[~dff[col_tasa].astype(str).str.upper().str.contains("SI|DECLARADO|1", na=False)]
        
        t1, t2 = st.columns(2)
        with t1:
            st.metric("Dotación Histórica OnlineToyota", len(df_on))
        with t2:
            pct_on = (len(df_on)/len(dff)*100) if len(dff)>0 else 0
            st.metric("% Declarados Online Toyota", f"{pct_on:.1f}%")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### % Declarados Online por Área")
            fig_on_area = px.pie(df_on, names="Area", hole=0.4, color_discrete_sequence=px.colors.sequential.Purp)
            st.plotly_chart(fig_on_area, use_container_width=True)
        with c2:
            st.markdown("### % No Declarados por Área")
            fig_off_area = px.pie(df_off, names="Area", hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig_off_area, use_container_width=True)

        st.markdown("### Comparativa: Declarados vs No Declarados por Área")
        comp_data = dff.groupby(["Area", col_tasa]).size().reset_index(name="Cantidad")
        fig_comp = px.bar(comp_data, x="Area", y="Cantidad", color=col_tasa, barmode="group",
                          color_discrete_map={"Declarado":"#EB0A1E", "No Declarado":"#58595B", "SI":"#EB0A1E", "NO":"#58595B"})
        st.plotly_chart(fig_comp, use_container_width=True)

# ==========================================
# PESTAÑA 3: ROTACIÓN / AUSENTISMO (Placeholders)
# ==========================================
with tabs[2]:
    st.info("Pestaña de Rotación: Utiliza las columnas 'bajas de Rotación real' y 'bajas de delcarados'.")
