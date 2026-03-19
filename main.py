import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURACIÓN ESTÉTICA (Estilo Toyota) ---
st.set_page_config(page_title="Dashboard RRHH Autolux", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    [data-testid="stMetricValue"] { color: #EB0A1E; font-weight: bold; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #F0F2F6; border-radius: 4px 4px 0 0; padding: 10px; }
    .stTabs [aria-selected="true"] { background-color: #EB0A1E !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# --- CONEXIÓN A DATOS ---
url = "https://docs.google.com/spreadsheets/d/156gG4r3krIiXEF9nIqsoJoh9YB_kcdhJittobHbxZ9s/edit?gid=1344313191#gid=1344313191"

@st.cache_data(ttl=600)
def load_data(url):
    conn = st.connection("gsheets", type=GSheetsConnection)
    # Leemos la hoja, asegurándonos de que tome la primera fila como cabecera
    df = conn.read(spreadsheet=url)
    return df

df = load_data(url)

# --- TÍTULO Y LOGO ---
col_t1, col_t2 = st.columns([3, 1])
with col_t1:
    st.title("Sistema de Visualización de Nómina - Autolux")
with col_t2:
    st.image("https://upload.wikimedia.org/wikipedia/commons/e/ee/Toyota_logo_%28Red%29.svg", width=150)

# --- NAVEGACIÓN POR TABS (Réplica de tu Power BI) ---
tabs = st.tabs([
    "ESTRUCTURA", 
    "ESTRUCTURA TASA", 
    "ROTACIÓN", 
    "AUSENTISMO", 
    "PERFORMANCE/OTROS"
])

# ==========================================
# 1. TAB ESTRUCTURA (Real)
# ==========================================
with tabs[0]:
    st.subheader("Análisis de Estructura Real")
    
    # Filtros dinámicos (Usando nombres comunes, ajusta si varían)
    c1, c2, c3 = st.columns(3)
    with c1:
        # Nota: Si en tu base 'Localidad' se llama distinto, cambia el nombre del string aquí
        loc_list = df['Localidad'].unique() if 'Localidad' in df.columns else []
        sel_loc = st.multiselect("Filtrar por Localidad", loc_list)
    
    df_filtered = df.copy()
    if sel_loc:
        df_filtered = df[df['Localidad'].isin(sel_loc)]

    col_kpi1, col_kpi2 = st.columns([1, 3])
    with col_kpi1:
        st.metric("Dotación Real", len(df_filtered))
        if 'Area' in df_filtered.columns:
            st.write("**Dotación por Área:**")
            st.dataframe(df_filtered['Area'].value_counts(), use_container_width=True)

    with col_kpi2:
        if 'Rango Antiguedad' in df_filtered.columns:
            fig_ant = px.pie(df_filtered, names='Rango Antiguedad', hole=0.5, 
                             color_discrete_sequence=['#EB0A1E', '#58595B', '#939598', '#D1D3D4'])
            fig_ant.update_layout(title="Distribución por Antigüedad")
            st.plotly_chart(fig_ant, use_container_width=True)

# ==========================================
# 2. TAB ESTRUCTURA TASA (Toyota)
# ==========================================
with tabs[1]:
    st.subheader("Estructura de Declarados (TASA)")
    
    # Aquí usamos la columna exacta: "Declarados"
    if 'Declarados' in df.columns:
        # Filtramos solo los que dicen "Declarado" (o similar)
        # Ajustamos a mayúsculas para evitar errores de tipeo en la base
        df_tasa = df[df['Declarados'].astype(str).str.upper().str.contains("SI|DECLARADO", na=False)]
        
        k1, k2 = st.columns([1, 3])
        with k1:
            st.metric("Dotación TASA", len(df_tasa))
            st.write(f"{(len(df_tasa)/len(df)*100):.1f}% del total")
        
        with k2:
            # Gráfico comparativo Declarados vs No Declarados
            fig_dec = px.bar(df, x='Declarados', color='Declarados',
                             color_discrete_map={'Declarado': '#EB0A1E', 'No Declarado': '#58595B'},
                             title="Comparativa de Declaración")
            st.plotly_chart(fig_dec, use_container_width=True)
    else:
        st.error("No se encontró la columna 'Declarados' en la base.")

# ==========================================
# 3. TAB ROTACIÓN (Real vs TASA)
# ==========================================
with tabs[2]:
    st.subheader("Indicadores de Rotación Mensual")
    
    # Usamos las columnas exactas: "bajas de Rotación real" y "bajas de delcarados"
    col_r1, col_r2, col_r3 = st.columns(3)
    
    with col_r1:
        bajas_reales = df['bajas de Rotación real'].sum() if 'bajas de Rotación real' in df.columns else 0
        st.metric("Bajas Totales (Real)", int(bajas_reales))
        
    with col_r2:
        bajas_tasa = df['bajas de delcarados'].sum() if 'bajas de delcarados' in df.columns else 0
        st.metric("Bajas TASA (Declarados)", int(bajas_tasa))
        
    with col_r3:
        # Gauge de Target (Réplica de tu imagen)
        fig_target = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = 9.0, # Valor de ejemplo
            title = {'text': "Target Rotación 2026"},
            gauge = {'axis': {'range': [0, 15]}, 'bar': {'color': "#EB0A1E"}}
        ))
        fig_target.update_layout(height=250)
        st.plotly_chart(fig_target, use_container_width=True)

# ==========================================
# 4. TAB AUSENTISMO
# ==========================================
with tabs[3]:
    st.subheader("Análisis de Ausentismo y Licencias")
    
    # Usamos la columna exacta: "politica"
    if 'politica' in df.columns:
        c_aus1, c_aus2 = st.columns(2)
        
        with c_aus1:
            fig_pol = px.pie(df, names='politica', title="Distribución por Política de Ausentismo",
                             color_discrete_sequence=px.colors.sequential.Reds_r)
            st.plotly_chart(fig_pol, use_container_width=True)
            
        with c_aus2:
            # Si existe una columna de Motivo o Cantidad de Días, la graficamos
            # Aquí asumo 'Motivo Licencia' basado en tus capturas
            col_motivo = 'Motivo Licencia' if 'Motivo Licencia' in df.columns else 'politica'
            fig_mot = px.bar(df, y=col_motivo, orientation='h', title="Días por Motivo",
                             color_discrete_sequence=['#EB0A1E'])
            st.plotly_chart(fig_mot, use_container_width=True)
    else:
        st.error("No se encontró la columna 'politica' en la base.")

# ==========================================
# 5. TAB PERFORMANCE / CAPACITACIÓN
# ==========================================
with tabs[4]:
    st.info("Esta sección se alimentará de las columnas de Desempeño y Capacitación.")
    # Aquí puedes añadir los gráficos de Performance Comercial cuando definamos las columnas exactas.
