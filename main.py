import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Dashboard Autolux", layout="wide")

# Estilo visual personalizado (Toyota Red & Professional Grey)
st.markdown("""
    <style>
    .stApp { background-color: #FFFFFF; }
    h1 { color: #EB0A1E; font-family: 'Arial'; font-weight: bold; margin-bottom: 0px; }
    .stMetric { background-color: #f9f9f9; border: 1px solid #e6e6e6; padding: 15px; border-radius: 5px; }
    div[data-testid="stMetricValue"] { color: #000000; font-size: 40px !important; font-weight: bold; }
    div[data-testid="stMetricLabel"] { color: #EB0A1E; font-weight: bold; }
    .stTabs [aria-selected="true"] { background-color: #004F43 !important; color: white !important; font-weight: bold; }
    .stDataFrame { border: 1px solid #e6e6e6; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CARGA Y LIMPIEZA DE DATOS ---
url = "https://docs.google.com/spreadsheets/d/156gG4r3krIiXEF9nIqsoJoh9YB_kcdhJittobHbxZ9s/edit?gid=1344313191#gid=1344313191"

@st.cache_data(ttl=60)
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(spreadsheet=url)
    # Limpiar espacios en blanco en los nombres de las columnas
    df.columns = [str(c).strip() for c in df.columns]
    return df

try:
    df_raw = load_data()
    df = df_raw.copy()
except Exception as e:
    st.error("Error de conexión: Verifica que el link de Google Sheets sea público y que los Secrets estén configurados.")
    st.stop()

# --- 3. PROCESAMIENTO DE KPIs Y FECHAS ---
# Buscamos la columna de fecha de forma flexible
col_fecha = next((c for c in df.columns if 'fecha' in c.lower() and 'ingreso' in c.lower()), None)

if col_fecha:
    df[col_fecha] = pd.to_datetime(df[col_fecha], errors='coerce')
    hoy = pd.Timestamp.now()
    
    # Cálculo de meses de antigüedad
    df['Meses_Ant'] = df[col_fecha].apply(lambda x: (hoy.year - x.year) * 12 + (hoy.month - x.month) if pd.notnull(x) else 0)
    
    # Segmentación de Antigüedad
    conds = [(df['Meses_Ant'] <= 12), (df['Meses_Ant'] > 12) & (df['Meses_Ant'] <= 36), 
             (df['Meses_Ant'] > 36) & (df['Meses_Ant'] <= 60), (df['Meses_Ant'] > 60)]
    labels = ['Hasta 1 año', '1-3 años', '3-5 años', 'Más de 5 años']
    df['Rango Antiguedad'] = np.select(conds, labels, default='Sin Dato')
    
    # Columnas auxiliares para filtros
    df['Año'] = df[col_fecha].dt.year.fillna(0).astype(int)
    df['Mes'] = df[col_fecha].dt.month_name().fillna("Sin Dato")
    df['AñoMes'] = df[col_fecha].dt.strftime('%Y-%m')
else:
    df['Rango Antiguedad'] = "N/A"
    df['Año'] = 0
    df['Mes'] = "N/A"
    df['AñoMes'] = "N/A"

# --- 4. CABECERA ---
header_col1, header_col2 = st.columns([4, 1])
with header_col1:
    st.markdown("<h1>ESTRUCTURA</h1>", unsafe_allow_html=True)
with header_col2:
    st.image("https://upload.wikimedia.org/wikipedia/commons/e/ee/Toyota_logo_%28Red%29.svg", width=120)

tabs = st.tabs(["ESTRUCTURA", "ESTRUCTURA TASA", "ROTACIÓN", "AUSENTISMO"])

# ==========================================
# PESTAÑA 1: ESTRUCTURA (Réplica exacta)
# ==========================================
with tabs[0]:
    # FILTRO BASE: Solo Activos y Empresa Autolux
    col_estado = next((c for c in df.columns if c.upper() == 'ESTADO'), 'ESTADO')
    col_empresa = next((c for c in df.columns if c.upper() == 'EMPRESA'), 'EMPRESA')
    
    df_activos = df[(df[col_estado].astype(str).str.upper() == 'ACTIVO') & 
                    (df[col_empresa].astype(str).str.upper() == 'AUTOLUX')].copy()

    # Filtros Dinámicos Superiores
    f1, f2, f3, f4 = st.columns(4)
    with f1: sel_loc = st.multiselect("Localidad", sorted(df_activos['Localidad'].unique().tolist()) if 'Localidad' in df_activos.columns else [])
    with f2: sel_mes = st.multiselect("Mes", sorted(df_activos['Mes'].unique().tolist()))
    with f3: sel_anio = st.multiselect("Año", sorted([int(x) for x in df_activos['Año'].unique() if x > 0]))
    with f4: sel_area = st.multiselect("Área", sorted(df_activos['Area'].unique().tolist()) if 'Area' in df_activos.columns else [])

    # Aplicar Filtros
    dff = df_activos.copy()
    if sel_loc: dff = dff[dff['Localidad'].isin(sel_loc)]
    if sel_mes: dff = dff[dff['Mes'].isin(sel_mes)]
    if sel_anio: dff = dff[dff['Año'].isin(sel_anio)]
    if sel_area: dff = dff[dff['Area'].isin(sel_area)]

    if dff.empty:
        st.warning("⚠️ No se encontraron datos para los filtros seleccionados.")
    else:
        # Layout de visualización
        col_main_1, col_main_2 = st.columns([2.5, 2])

        with col_main_1:
            st.metric("Dotación", len(dff))
            
            # MATRIZ JERÁRQUICA (Área > Puesto vs Localidad)
            st.markdown("### Matriz de Dotación")
            filas_matriz = [c for c in ['Area', 'Puesto'] if c in dff.columns]
            
            if len(filas_matriz) > 0 and 'Localidad' in dff.columns:
                matrix = pd.pivot_table(
                    dff,
                    index=filas_matriz,
                    columns='Localidad',
                    values=col_empresa,
                    aggfunc='count',
                    fill_value=0,
                    margins=True,
                    margins_name='Total'
                )
                st.dataframe(matrix, use_container_width=True, height=550)
            else:
                st.info("Faltan columnas 'Area', 'Puesto' o 'Localidad' para mostrar la matriz.")

        with col_main_2:
            # Gráfico de Evolución
            st.markdown("### Dotación Histórica")
            if 'AñoMes' in dff.columns and not dff['AñoMes'].isnull().all():
                hist = dff.groupby('AñoMes').size().reset_index(name='Total')
                fig_line = px.line(hist, x='AñoMes', y='Total', color_discrete_sequence=['#EB0A1E'])
                fig_line.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
                st.plotly_chart(fig_line, use_container_width=True)

            # Sub-gráficos: Antigüedad y Categoría
            sub_c1, sub_c2 = st.columns(2)
            with sub_c1:
                st.markdown("### Antigüedad")
                fig_pie = px.pie(dff, names='Rango Antiguedad', hole=0.6, 
                                 color_discrete_sequence=['#EB0A1E', '#58595B', '#939598', '#D1D3D4'])
                fig_pie.update_layout(showlegend=False, height=250, margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig_pie, use_container_width=True)
                
            with sub_c2:
                st.markdown("### Categoría")
                if 'Categoría' in dff.columns:
                    cat_data = dff['Categoría'].value_counts().reset_index()
                    fig_bar = px.bar(cat_data, y='Categoría', x='count', orientation='h', color_discrete_sequence=['#EB0A1E'])
                    fig_bar.update_layout(height=250, margin=dict(l=0, r=0, t=20, b=0), yaxis={'title':''}, xaxis={'title':''})
                    st.plotly_chart(fig_bar, use_container_width=True)

# ==========================================
# PESTAÑA 2: ESTRUCTURA TASA
# ==========================================
with tabs[1]:
    st.subheader("Estructura de Declarados en Toyota (TASA)")
    if 'Declarados' in df.columns:
        df_tasa = df[(df[col_empresa].astype(str).str.upper() == 'AUTOLUX') & 
                     (df['Declarados'].astype(str).str.upper().str.contains("SI|DECLARADO", na=False))]
        st.metric("Total Declarados TASA", len(df_tasa))
        st.write("Esta sección muestra los colaboradores con registro activo en la terminal.")

# ==========================================
# PESTAÑA 3: ROTACIÓN
# ==========================================
with tabs[2]:
    st.subheader("Indicadores de Rotación Mensual")
    c_rot1, c_rot2 = st.columns(2)
    with c_rot1:
        b_real = df['bajas de Rotación real'].sum() if 'bajas de Rotación real' in df.columns else 0
        st.metric("Bajas Rotación Real", int(b_real))
    with c_rot2:
        b_tasa = df['bajas de delcarados'].sum() if 'bajas de delcarados' in df.columns else 0
        st.metric("Bajas Rotación TASA", int(b_tasa))

# ==========================================
# PESTAÑA 4: AUSENTISMO
# ==========================================
with tabs[3]:
    st.subheader("Análisis de Ausentismo")
    if 'politica' in df.columns:
        fig_aus = px.pie(df, names='politica', title="Distribución por Política", hole=0.4, color_discrete_sequence=px.colors.sequential.Reds_r)
        st.plotly_chart(fig_aus, use_container_width=True)
