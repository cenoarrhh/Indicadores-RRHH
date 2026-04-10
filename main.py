import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import calendar
import unicodedata
import re

# =========================================================
# 1. CONFIGURACIÓN GENERAL
# =========================================================
st.set_page_config(
    page_title="Dashboard Autolux BI",
    layout="wide",
    initial_sidebar_state="expanded"
)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/156gG4r3krIiXEF9nIqsoJoh9YB_kcdhJittobHbxZ9s/edit?gid=1344313191#gid=1344313191"

COLOR_ROJO = "#EB0A1E"
COLOR_GRIS = "#58595B"
COLOR_FONDO = "#F7F7F7"
EMPRESA_OBJETIVO = "AUTOLUX"
TARGET_ROTACION_TASA = 10.0  # objetivo del gauge

st.markdown(
    f"""
    <style>
    .stApp {{
        background-color: #FFFFFF;
    }}
    h1, h2, h3 {{
        color: {COLOR_ROJO};
        font-family: Arial, sans-serif;
        font-weight: 700;
    }}
    .block-container {{
        padding-top: 1rem;
        padding-bottom: 1rem;
    }}
    div[data-testid="stMetric"] {{
        background-color: white;
        border: 1px solid {COLOR_ROJO};
        border-radius: 10px;
        padding: 10px 14px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }}
    div[data-testid="stMetricLabel"] {{
        color: {COLOR_ROJO};
        font-weight: 700;
    }}
    div[data-testid="stMetricValue"] {{
        color: #222222;
        font-size: 2rem !important;
        font-weight: 700;
    }}
    .small-note {{
        color: #666666;
        font-size: 0.85rem;
    }}
    .section-card {{
        background: white;
        border: 1px solid #E5E5E5;
        border-radius: 12px;
        padding: 12px;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 8px 8px 0px 0px;
        padding: 8px 16px;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {COLOR_ROJO} !important;
        color: white !important;
        font-weight: 700;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

# =========================================================
# 2. FUNCIONES AUXILIARES
# =========================================================
def normalize_text(text):
    if text is None:
        return ""
    text = str(text).strip()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text

def normalize_columns(df):
    df = df.copy()
    df.columns = [normalize_text(c) for c in df.columns]
    return df

def first_existing_column(df, options):
    for col in options:
        if col in df.columns:
            return col
    return None

def parse_date_series(series):
    """
    Intenta convertir fechas considerando formato día/mes/año.
    """
    return pd.to_datetime(series, errors="coerce", dayfirst=True)

def safe_upper(series):
    return series.astype(str).str.strip().str.upper()

def is_yes(value):
    txt = str(value).strip().upper()
    return txt in ["SI", "SÍ", "1", "TRUE", "DECLARADO", "ACTIVO", "X"]

def classify_yes_no(value):
    return "Declarado" if is_yes(value) else "No Declarado"

def add_month_end(date_value):
    if pd.isna(date_value):
        return pd.NaT
    return pd.Timestamp(date_value) + pd.offsets.MonthEnd(0)

def metric_card(label, value):
    st.metric(label, value)

def dotacion_snapshot(df, fecha_corte, col_ingreso, col_egreso, col_empresa=None, empresa_objetivo=None):
    cond = (df[col_ingreso] <= fecha_corte) & (
        df[col_egreso].isna() | (df[col_egreso] > fecha_corte)
    )
    if col_empresa and empresa_objetivo and col_empresa in df.columns:
        cond = cond & (safe_upper(df[col_empresa]) == empresa_objetivo.upper())
    return df.loc[cond].copy()

def apply_filters(df, filters_dict):
    out = df.copy()
    for col, selected in filters_dict.items():
        if col in out.columns and selected not in [None, "Todas", "Todos"]:
            out = out[out[col] == selected]
    return out

def calc_antiguedad_rango(fecha_ingreso, fecha_corte):
    if pd.isna(fecha_ingreso):
        return "Sin dato"
    anios = (fecha_corte - fecha_ingreso).days / 365.25
    if anios <= 1:
        return "Hasta 1 año"
    elif anios <= 3:
        return "1-3 años"
    elif anios <= 5:
        return "3-5 años"
    elif anios <= 10:
        return "5-10 años"
    return "Más de 10 años"

def format_pct(value, decimals=2):
    try:
        return f"{value:.{decimals}f} %"
    except Exception:
        return "0,00 %"

def month_name_es(month_num):
    meses = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    return meses.get(month_num, str(month_num))

def month_range(start_date, end_date):
    return pd.date_range(start=start_date, end=end_date, freq="MS")

def make_line_chart(df, x, y, title, color=COLOR_ROJO):
    fig = px.line(df, x=x, y=y, markers=True)
    fig.update_traces(line=dict(color=color, width=3), marker=dict(size=7))
    fig.update_layout(
        title=title,
        height=320,
        margin=dict(l=10, r=10, t=45, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title="",
        yaxis_title="",
        showlegend=False
    )
    return fig

def make_bar_chart(df, x, y, title, color=COLOR_ROJO, orientation="v", text_auto=True):
    fig = px.bar(df, x=x, y=y, orientation=orientation, text_auto=text_auto)
    fig.update_traces(marker_color=color)
    fig.update_layout(
        title=title,
        height=320,
        margin=dict(l=10, r=10, t=45, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title="",
        yaxis_title="",
        showlegend=False
    )
    return fig

def make_grouped_bar(df, x, y, color_col, title, color_map=None):
    fig = px.bar(
        df,
        x=x,
        y=y,
        color=color_col,
        barmode="group",
        text_auto=True,
        color_discrete_map=color_map or {}
    )
    fig.update_layout(
        title=title,
        height=320,
        margin=dict(l=10, r=10, t=45, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        xaxis_title="",
        yaxis_title="",
        legend_title=""
    )
    return fig

def make_donut(df, names, values, title):
    fig = px.pie(df, names=names, values=values, hole=0.58)
    fig.update_layout(
        title=title,
        height=300,
        margin=dict(l=10, r=10, t=45, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        legend_title=""
    )
    return fig

def make_gauge(value, target, title):
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={"suffix": " %"},
            title={"text": title},
            gauge={
                "axis": {"range": [0, max(target, value, 1)]},
                "bar": {"color": COLOR_ROJO},
                "steps": [
                    {"range": [0, target], "color": "#F3F3F3"},
                    {"range": [target, max(target, value, 1)], "color": "#FFD9DD"},
                ],
                "threshold": {
                    "line": {"color": COLOR_GRIS, "width": 4},
                    "thickness": 0.75,
                    "value": target,
                },
            },
        )
    )
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=45, b=10))
    return fig

# =========================================================
# 3. CARGA DE DATOS
# =========================================================
@st.cache_resource
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300, show_spinner=False)
def try_load_sheet(spreadsheet_url, worksheet=None):
    conn = get_connection()
    try:
        if worksheet:
            df = conn.read(spreadsheet=spreadsheet_url, worksheet=worksheet)
        else:
            df = conn.read(spreadsheet=spreadsheet_url)
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None

@st.cache_data(ttl=300, show_spinner=False)
def load_nomina_data():
    df = try_load_sheet(SPREADSHEET_URL)
    if df is None or df.empty:
        raise ValueError("No se pudo leer la hoja principal de nómina.")
    df = normalize_columns(df)

    # Mapeo flexible de columnas
    col_ingreso = first_existing_column(df, ["fecha_de_ingreso", "fecha_ingreso"])
    col_egreso = first_existing_column(df, ["fecha_egreso", "fecha_de_egreso"])
    col_empresa = first_existing_column(df, ["empresa"])
    col_area = first_existing_column(df, ["area"])
    col_sector = first_existing_column(df, ["sector"])
    col_puesto = first_existing_column(df, ["puesto"])
    col_localidad = first_existing_column(df, ["localidad"])
    col_categoria = first_existing_column(df, ["categoria"])
    col_online = first_existing_column(df, ["online_toyota", "declarados", "declarado", "online"])
    col_baja_ot = first_existing_column(df, ["baja_declarada_o_t", "baja_declarada_ot"])
    col_motivo_baja = first_existing_column(df, ["motivo_de_baja"])
    col_nombre = first_existing_column(df, ["apellido_y_nombre", "apellidoynombre", "nombre_y_apellido"])
    col_estado = first_existing_column(df, ["estado"])
    col_id = first_existing_column(df, ["id_empleado", "id"])

    required = [col_ingreso, col_egreso, col_empresa]
    if any(c is None for c in required):
        raise ValueError("Faltan columnas clave en la nómina: Fecha de ingreso / FECHA EGRESO / EMPRESA.")

    df[col_ingreso] = parse_date_series(df[col_ingreso])
    df[col_egreso] = parse_date_series(df[col_egreso])

    if col_online:
        df["flag_online_tasa"] = df[col_online].apply(classify_yes_no)
    else:
        df["flag_online_tasa"] = "No Declarado"

    if col_baja_ot:
        df["flag_baja_ot"] = df[col_baja_ot].apply(classify_yes_no)
    else:
        df["flag_baja_ot"] = "No Declarado"

    metadata = {
        "col_ingreso": col_ingreso,
        "col_egreso": col_egreso,
        "col_empresa": col_empresa,
        "col_area": col_area,
        "col_sector": col_sector,
        "col_puesto": col_puesto,
        "col_localidad": col_localidad,
        "col_categoria": col_categoria,
        "col_online": col_online,
        "col_baja_ot": col_baja_ot,
        "col_motivo_baja": col_motivo_baja,
        "col_nombre": col_nombre,
        "col_estado": col_estado,
        "col_id": col_id,
    }

    return df, metadata

@st.cache_data(ttl=300, show_spinner=False)
def load_ausentismo_data():
    possible_sheets = [
        "Ausentismo",
        "AUSENTISMO",
        "Ausentismo_Normalizado",
        "ausentismo",
        "Licencias",
        "Licencias_Normalizado"
    ]

    for sheet_name in possible_sheets:
        df = try_load_sheet(SPREADSHEET_URL, worksheet=sheet_name)
        if df is not None and not df.empty:
            df = normalize_columns(df)

            col_fecha = first_existing_column(df, [
                "fecha", "fecha_licencia", "fecha_inicio", "fecha_desde"
            ])
            col_dias = first_existing_column(df, [
                "cantidad_dias", "dias", "dias_corridos", "dias_filtrados"
            ])
            col_tipo = first_existing_column(df, [
                "tipo_licencia", "motivo_licencia", "licencia", "motivo"
            ])
            col_nombre = first_existing_column(df, [
                "apellido_y_nombre", "apellidoynombre", "nombre_y_apellido"
            ])
            col_area = first_existing_column(df, ["area"])
            col_sector = first_existing_column(df, ["sector"])
            col_localidad = first_existing_column(df, ["localidad"])

            if col_fecha:
                df[col_fecha] = parse_date_series(df[col_fecha])
            if col_dias:
                df[col_dias] = pd.to_numeric(df[col_dias], errors="coerce").fillna(0)

            meta = {
                "sheet_name": sheet_name,
                "col_fecha": col_fecha,
                "col_dias": col_dias,
                "col_tipo": col_tipo,
                "col_nombre": col_nombre,
                "col_area": col_area,
                "col_sector": col_sector,
                "col_localidad": col_localidad,
            }
            return df, meta

    return None, None

# =========================================================
# 4. PREPARACIÓN DE DATOS
# =========================================================
try:
    df_nomina, meta = load_nomina_data()
except Exception as e:
    st.error(f"Error al cargar la nómina: {e}")
    st.stop()

df_aus, meta_aus = load_ausentismo_data()

col_ingreso = meta["col_ingreso"]
col_egreso = meta["col_egreso"]
col_empresa = meta["col_empresa"]
col_area = meta["col_area"]
col_sector = meta["col_sector"]
col_puesto = meta["col_puesto"]
col_localidad = meta["col_localidad"]
col_categoria = meta["col_categoria"]
col_motivo_baja = meta["col_motivo_baja"]
col_nombre = meta["col_nombre"]

# =========================================================
# 5. FILTROS GLOBALES
# =========================================================
st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/e/ee/Toyota_logo_%28Red%29.svg", width=120)
st.sidebar.markdown("## Filtros")

today = datetime.now()
anio_actual = today.year
anios_disponibles = list(range(2022, anio_actual + 1))
anios_disponibles.sort(reverse=True)

sel_anio = st.sidebar.selectbox("Año", anios_disponibles, index=0)
sel_mes_nombre = st.sidebar.selectbox(
    "Mes",
    [month_name_es(m) for m in range(1, 13)],
    index=today.month - 1
)
sel_mes_num = [k for k, v in {i: month_name_es(i) for i in range(1, 13)}.items() if v == sel_mes_nombre][0]

ultimo_dia = calendar.monthrange(sel_anio, sel_mes_num)[1]
fecha_corte = pd.Timestamp(datetime(sel_anio, sel_mes_num, ultimo_dia))
fecha_inicio_mes = pd.Timestamp(datetime(sel_anio, sel_mes_num, 1))
fecha_inicio_anio = pd.Timestamp(datetime(sel_anio, 1, 1))

df_snap_base = dotacion_snapshot(
    df_nomina,
    fecha_corte=fecha_corte,
    col_ingreso=col_ingreso,
    col_egreso=col_egreso,
    col_empresa=col_empresa,
    empresa_objetivo=EMPRESA_OBJETIVO,
)

localidades = ["Todas"]
areas = ["Todas"]
online_opts = ["Todos", "Declarado", "No Declarado"]

if col_localidad and col_localidad in df_snap_base.columns:
    localidades += sorted(df_snap_base[col_localidad].dropna().astype(str).unique().tolist())

if col_area and col_area in df_snap_base.columns:
    areas += sorted(df_snap_base[col_area].dropna().astype(str).unique().tolist())

sel_localidad = st.sidebar.selectbox("Localidad", localidades)
sel_area = st.sidebar.selectbox("Área", areas)
sel_online = st.sidebar.selectbox("Online Toyota", online_opts)

filtros = {}
if col_localidad:
    filtros[col_localidad] = sel_localidad
if col_area:
    filtros[col_area] = sel_area

df_snap = apply_filters(df_snap_base, filtros)
if sel_online != "Todos":
    df_snap = df_snap[df_snap["flag_online_tasa"] == sel_online]

# =========================================================
# 6. FUNCIONES DE NEGOCIO
# =========================================================
def snapshot_filtered(fecha, area=None, localidad=None, online=None):
    df = dotacion_snapshot(
        df_nomina,
        fecha,
        col_ingreso=col_ingreso,
        col_egreso=col_egreso,
        col_empresa=col_empresa,
        empresa_objetivo=EMPRESA_OBJETIVO,
    )
    if col_area and area not in [None, "Todas"]:
        df = df[df[col_area] == area]
    if col_localidad and localidad not in [None, "Todas"]:
        df = df[df[col_localidad] == localidad]
    if online not in [None, "Todos"]:
        df = df[df["flag_online_tasa"] == online]
    return df

def get_bajas_periodo(fecha_ini, fecha_fin, area=None, localidad=None):
    cond = (
        df_nomina[col_egreso].notna()
        & (df_nomina[col_egreso] >= fecha_ini)
        & (df_nomina[col_egreso] <= fecha_fin)
    )
    if col_empresa:
        cond = cond & (safe_upper(df_nomina[col_empresa]) == EMPRESA_OBJETIVO.upper())

    df = df_nomina.loc[cond].copy()

    if col_area and area not in [None, "Todas"]:
        df = df[df[col_area] == area]
    if col_localidad and localidad not in [None, "Todas"]:
        df = df[df[col_localidad] == localidad]

    return df

def dotacion_promedio_mes(fecha_ini, fecha_fin, area=None, localidad=None, online=None):
    dot_ini = len(snapshot_filtered(fecha_ini, area=area, localidad=localidad, online=online))
    dot_fin = len(snapshot_filtered(fecha_fin, area=area, localidad=localidad, online=online))
    return (dot_ini + dot_fin) / 2 if (dot_ini + dot_fin) > 0 else 0

def rotacion_periodo(fecha_ini, fecha_fin, area=None, localidad=None):
    bajas = get_bajas_periodo(fecha_ini, fecha_fin, area=area, localidad=localidad)
    dot_prom = dotacion_promedio_mes(fecha_ini, fecha_fin, area=area, localidad=localidad, online="Todos")
    rot_real = (len(bajas) / dot_prom * 100) if dot_prom > 0 else 0

    bajas_tasa = bajas[bajas["flag_baja_ot"] == "Declarado"].copy()
    dot_prom_tasa = dotacion_promedio_mes(fecha_ini, fecha_fin, area=area, localidad=localidad, online="Declarado")
    rot_tasa = (len(bajas_tasa) / dot_prom_tasa * 100) if dot_prom_tasa > 0 else 0

    return {
        "bajas_real": len(bajas),
        "bajas_tasa": len(bajas_tasa),
        "dot_prom_real": dot_prom,
        "dot_prom_tasa": dot_prom_tasa,
        "rot_real": rot_real,
        "rot_tasa": rot_tasa,
        "detalle_bajas": bajas
    }

def build_dotacion_history(fecha_fin, area=None, localidad=None, online=None):
    fechas = pd.date_range(start="2022-01-31", end=fecha_fin, freq="ME")
    rows = []
    for f in fechas:
        df_aux = snapshot_filtered(f, area=area, localidad=localidad, online=online)
        rows.append(
            {
                "periodo": f.strftime("%Y-%m"),
                "dotacion": len(df_aux)
            }
        )
    return pd.DataFrame(rows)

def build_rotacion_history(fecha_fin, area=None, localidad=None):
    fechas = pd.date_range(start="2023-01-01", end=fecha_fin, freq="MS")
    rows = []
    for f in fechas:
        inicio = pd.Timestamp(datetime(f.year, f.month, 1))
        fin = pd.Timestamp(datetime(f.year, f.month, calendar.monthrange(f.year, f.month)[1]))
        info = rotacion_periodo(inicio, fin, area=area, localidad=localidad)
        rows.append(
            {
                "periodo": inicio.strftime("%Y-%m"),
                "rot_real": info["rot_real"],
                "rot_tasa": info["rot_tasa"]
            }
        )
    return pd.DataFrame(rows)

def build_rotacion_area_mes(fecha_ini, fecha_fin, localidad=None):
    if not col_area:
        return pd.DataFrame()
    areas_disp = sorted(snapshot_filtered(fecha_fin, localidad=localidad)[col_area].dropna().astype(str).unique().tolist())
    rows = []
    for a in areas_disp:
        info = rotacion_periodo(fecha_ini, fecha_fin, area=a, localidad=localidad)
        rows.append({"area": a, "rot_real": info["rot_real"], "rot_tasa": info["rot_tasa"]})
    return pd.DataFrame(rows)

def build_tasa_area_snapshot(fecha_fin, localidad=None):
    df = snapshot_filtered(fecha_fin, localidad=localidad, online="Todos")
    if col_area is None or df.empty:
        return pd.DataFrame()
    out = df.groupby([col_area, "flag_online_tasa"]).size().reset_index(name="cantidad")
    out = out.rename(columns={col_area: "area"})
    return out

def build_antiguedad_data(df_snapshot):
    df = df_snapshot.copy()
    df["rango_antiguedad"] = df[col_ingreso].apply(lambda x: calc_antiguedad_rango(x, fecha_corte))
    orden = ["Hasta 1 año", "1-3 años", "3-5 años", "5-10 años", "Más de 10 años", "Sin dato"]
    out = df["rango_antiguedad"].value_counts().reindex(orden, fill_value=0).reset_index()
    out.columns = ["rango", "cantidad"]
    return out

def build_categoria_data(df_snapshot):
    if not col_categoria or col_categoria not in df_snapshot.columns:
        return pd.DataFrame()
    out = df_snapshot[col_categoria].fillna("Sin dato").value_counts().reset_index()
    out.columns = ["categoria", "cantidad"]
    return out.sort_values("cantidad", ascending=True)

def build_matriz_estructura(df_snapshot):
    niveles = [c for c in [col_area, col_sector, col_puesto] if c and c in df_snapshot.columns]
    if not niveles or not col_localidad or col_localidad not in df_snapshot.columns:
        return pd.DataFrame()
    pivot = pd.pivot_table(
        df_snapshot,
        index=niveles,
        columns=col_localidad,
        values=col_empresa,
        aggfunc="count",
        fill_value=0,
        margins=True,
        margins_name="Total"
    )
    return pivot

def ausentismo_disponible():
    if df_aus is None or meta_aus is None:
        return False
    return bool(meta_aus.get("col_fecha") and meta_aus.get("col_dias"))

def filtrar_ausentismo_mes(anio, mes, area=None, localidad=None):
    if not ausentismo_disponible():
        return pd.DataFrame()

    col_fecha = meta_aus["col_fecha"]
    col_dias = meta_aus["col_dias"]
    col_area_aus = meta_aus["col_area"]
    col_localidad_aus = meta_aus["col_localidad"]

    df = df_aus.copy()
    df = df[
        df[col_fecha].notna()
        & (df[col_fecha].dt.year == anio)
        & (df[col_fecha].dt.month == mes)
    ].copy()

    if col_area_aus and area not in [None, "Todas"]:
        df = df[df[col_area_aus] == area]
    if col_localidad_aus and localidad not in [None, "Todas"]:
        df = df[df[col_localidad_aus] == localidad]

    if col_dias in df.columns:
        df[col_dias] = pd.to_numeric(df[col_dias], errors="coerce").fillna(0)

    return df

def dias_laborables_estimados(anio, mes):
    # Lunes a viernes
    inicio = pd.Timestamp(datetime(anio, mes, 1))
    fin = pd.Timestamp(datetime(anio, mes, calendar.monthrange(anio, mes)[1]))
    return len(pd.bdate_range(start=inicio, end=fin))

# =========================================================
# 7. CABECERA
# =========================================================
head1, head2 = st.columns([5, 1])
with head1:
    st.markdown("<h1>Dashboard de Indicadores RRHH - Autolux</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='small-note'>Período seleccionado: {sel_mes_nombre} {sel_anio} | Fecha de corte: {fecha_corte.strftime('%d/%m/%Y')}</div>",
        unsafe_allow_html=True
    )
with head2:
    st.image("https://upload.wikimedia.org/wikipedia/commons/e/ee/Toyota_logo_%28Red%29.svg", width=95)
    st.markdown("<div style='text-align:right;font-weight:700;'>Autolux</div>", unsafe_allow_html=True)

tabs = st.tabs(["ESTRUCTURA", "ESTRUCTURA TASA", "ROTACIÓN", "AUSENTISMO"])

# =========================================================
# 8. TAB 1 - ESTRUCTURA
# =========================================================
with tabs[0]:
    st.subheader("Estructura Real")

    c1, c2 = st.columns([1, 3])

    with c1:
        metric_card("Dotación", len(df_snap))
        if col_area and sel_area != "Todas":
            st.caption(f"Área: {sel_area}")
        if col_localidad and sel_localidad != "Todas":
            st.caption(f"Localidad: {sel_localidad}")

    with c2:
        df_hist = build_dotacion_history(
            fecha_corte,
            area=None if sel_area == "Todas" else sel_area,
            localidad=None if sel_localidad == "Todas" else sel_localidad,
            online="Todos" if sel_online == "Todos" else sel_online
        )
        if not df_hist.empty:
            fig = make_line_chart(df_hist, "periodo", "dotacion", "Dotación Histórica")
            st.plotly_chart(fig, use_container_width=True)

    left, right = st.columns([2.2, 1.3])

    with left:
        st.markdown("### Matriz de Dotación")
        matriz = build_matriz_estructura(df_snap)
        if not matriz.empty:
            st.dataframe(matriz, use_container_width=True, height=520)
        else:
            st.info("No fue posible construir la matriz con las columnas actuales.")

    with right:
        ant_df = build_antiguedad_data(df_snap)
        if not ant_df.empty:
            fig_ant = make_donut(ant_df, "rango", "cantidad", "Antigüedad")
            st.plotly_chart(fig_ant, use_container_width=True)

        cat_df = build_categoria_data(df_snap)
        if not cat_df.empty:
            fig_cat = px.bar(
                cat_df,
                x="cantidad",
                y="categoria",
                orientation="h",
                text_auto=True
            )
            fig_cat.update_traces(marker_color=COLOR_ROJO)
            fig_cat.update_layout(
                title="Categoría",
                height=320,
                margin=dict(l=10, r=10, t=45, b=10),
                paper_bgcolor="white",
                plot_bgcolor="white",
                xaxis_title="",
                yaxis_title=""
            )
            st.plotly_chart(fig_cat, use_container_width=True)

# =========================================================
# 9. TAB 2 - ESTRUCTURA TASA
# =========================================================
with tabs[1]:
    st.subheader("Estructura TASA / Online Toyota")

    df_snap_tasa = snapshot_filtered(
        fecha_corte,
        area=None if sel_area == "Todas" else sel_area,
        localidad=None if sel_localidad == "Todas" else sel_localidad,
        online="Todos"
    )

    df_online = df_snap_tasa[df_snap_tasa["flag_online_tasa"] == "Declarado"].copy()
    df_no_online = df_snap_tasa[df_snap_tasa["flag_online_tasa"] == "No Declarado"].copy()

    k1, k2, k3 = st.columns(3)
    with k1:
        metric_card("Dotación", len(df_snap_tasa))
    with k2:
        metric_card("Dotación Online Toyota", len(df_online))
    with k3:
        pct_decl = (len(df_online) / len(df_snap_tasa) * 100) if len(df_snap_tasa) > 0 else 0
        metric_card("% Declarados Online", format_pct(pct_decl))

    l1, l2 = st.columns([1.3, 2.2])

    with l1:
        if col_area and not df_snap_tasa.empty:
            tasa_area = (
                df_snap_tasa.groupby([col_area, "flag_online_tasa"])
                .size()
                .reset_index(name="cantidad")
                .rename(columns={col_area: "area"})
            )

            resumen_area = (
                tasa_area.pivot_table(index="area", columns="flag_online_tasa", values="cantidad", fill_value=0)
                .reset_index()
            )

            if "Declarado" not in resumen_area.columns:
                resumen_area["Declarado"] = 0
            if "No Declarado" not in resumen_area.columns:
                resumen_area["No Declarado"] = 0

            resumen_area["% Declarados"] = resumen_area.apply(
                lambda r: (r["Declarado"] / (r["Declarado"] + r["No Declarado"]) * 100)
                if (r["Declarado"] + r["No Declarado"]) > 0 else 0,
                axis=1
            )

            fig1 = px.pie(
                resumen_area,
                names="area",
                values="% Declarados",
                hole=0.55,
                title="% Declarados Online por Área"
            )
            fig1.update_layout(height=300, margin=dict(l=10, r=10, t=45, b=10))
            st.plotly_chart(fig1, use_container_width=True)

            resumen_area["% No Declarados"] = 100 - resumen_area["% Declarados"]
            fig2 = px.pie(
                resumen_area,
                names="area",
                values="% No Declarados",
                hole=0.55,
                title="% No Declarados por Área"
            )
            fig2.update_layout(height=300, margin=dict(l=10, r=10, t=45, b=10))
            st.plotly_chart(fig2, use_container_width=True)

    with l2:
        comp_area = build_tasa_area_snapshot(
            fecha_corte,
            localidad=None if sel_localidad == "Todas" else sel_localidad
        )
        if not comp_area.empty:
            fig_comp = make_grouped_bar(
                comp_area,
                x="area",
                y="cantidad",
                color_col="flag_online_tasa",
                title="Declarados vs. No Declarados",
                color_map={"Declarado": COLOR_ROJO, "No Declarado": COLOR_GRIS}
            )
            st.plotly_chart(fig_comp, use_container_width=True)

        if col_nombre and col_nombre in df_online.columns:
            st.markdown("### Colaboradores Declarados")
            cols_show = [c for c in [col_nombre, col_area, col_localidad, col_puesto] if c]
            st.dataframe(
                df_online[cols_show].sort_values(by=col_nombre).reset_index(drop=True),
                use_container_width=True,
                height=260
            )

# =========================================================
# 10. TAB 3 - ROTACIÓN
# =========================================================
with tabs[2]:
    st.subheader("Rotación Real vs. Rotación TASA")

    info_mes = rotacion_periodo(
        fecha_inicio_mes,
        fecha_corte,
        area=None if sel_area == "Todas" else sel_area,
        localidad=None if sel_localidad == "Todas" else sel_localidad
    )

    info_ytd = rotacion_periodo(
        fecha_inicio_anio,
        fecha_corte,
        area=None if sel_area == "Todas" else sel_area,
        localidad=None if sel_localidad == "Todas" else sel_localidad
    )

    a1, a2, a3 = st.columns([1.2, 1.2, 1.3])
    with a1:
        metric_card("Rotación Real Acumulada Año", format_pct(info_ytd["rot_real"]))
        st.caption(f"Bajas acumuladas: {info_ytd['bajas_real']}")
    with a2:
        metric_card("Rotación TASA Acumulada Año", format_pct(info_ytd["rot_tasa"]))
        st.caption(f"Bajas TASA acumuladas: {info_ytd['bajas_tasa']}")
    with a3:
        fig_g = make_gauge(info_ytd["rot_tasa"], TARGET_ROTACION_TASA, "Target Rotación TASA")
        st.plotly_chart(fig_g, use_container_width=True)

    b1, b2, b3 = st.columns([1.4, 1.4, 1.2])

    with b1:
        df_area_rot = build_rotacion_area_mes(
            fecha_inicio_mes,
            fecha_corte,
            localidad=None if sel_localidad == "Todas" else sel_localidad
        )
        if not df_area_rot.empty:
            fig_area_real = make_bar_chart(
                df_area_rot.sort_values("rot_real", ascending=False),
                x="area",
                y="rot_real",
                title="% Rotación Mensual por Área",
                color=COLOR_GRIS
            )
            st.plotly_chart(fig_area_real, use_container_width=True)

    with b2:
        df_rot_hist = build_rotacion_history(
            fecha_corte,
            area=None if sel_area == "Todas" else sel_area,
            localidad=None if sel_localidad == "Todas" else sel_localidad
        )
        if not df_rot_hist.empty:
            fig_real_hist = make_bar_chart(
                df_rot_hist,
                x="periodo",
                y="rot_real",
                title="% Rotación Real - Evolución Mensual",
                color=COLOR_ROJO
            )
            st.plotly_chart(fig_real_hist, use_container_width=True)

    with b3:
        if not df_rot_hist.empty:
            fig_tasa_hist = make_bar_chart(
                df_rot_hist,
                x="periodo",
                y="rot_tasa",
                title="% Rotación TASA - Evolución Mensual",
                color=COLOR_ROJO
            )
            st.plotly_chart(fig_tasa_hist, use_container_width=True)

    c1, c2 = st.columns([1.2, 1.8])

    with c1:
        st.markdown("### Bajas por Motivo")
        bajas_mes = info_mes["detalle_bajas"]
        if col_motivo_baja and not bajas_mes.empty:
            motivo_df = bajas_mes[col_motivo_baja].fillna("Sin dato").value_counts().reset_index()
            motivo_df.columns = ["motivo_baja", "cantidad"]
            fig_mot = px.bar(
                motivo_df,
                x="cantidad",
                y="motivo_baja",
                orientation="h",
                text_auto=True
            )
            fig_mot.update_traces(marker_color=COLOR_ROJO)
            fig_mot.update_layout(
                height=300,
                margin=dict(l=10, r=10, t=20, b=10),
                xaxis_title="",
                yaxis_title=""
            )
            st.plotly_chart(fig_mot, use_container_width=True)
        else:
            st.info("No hay bajas en el período seleccionado.")

    with c2:
        st.markdown("### Detalle de Bajas del Período")
        if not bajas_mes.empty:
            show_cols = [c for c in [col_nombre, col_area, col_localidad, col_motivo_baja, col_egreso] if c]
            detalle = bajas_mes[show_cols].copy()
            if col_egreso in detalle.columns:
                detalle[col_egreso] = detalle[col_egreso].dt.strftime("%d/%m/%Y")
            st.dataframe(detalle.reset_index(drop=True), use_container_width=True, height=300)
        else:
            st.info("No se registran bajas para el período filtrado.")

# =========================================================
# 11. TAB 4 - AUSENTISMO
# =========================================================
with tabs[3]:
    st.subheader("Ausentismo")

    if not ausentismo_disponible():
        st.warning(
            "No encontré una hoja de ausentismo compatible. "
            "La app está preparada para leer hojas llamadas "
            "'Ausentismo', 'AUSENTISMO' o 'Ausentismo_Normalizado'."
        )
    else:
        df_aus_mes = filtrar_ausentismo_mes(
            sel_anio,
            sel_mes_num,
            area=None if sel_area == "Todas" else sel_area,
            localidad=None if sel_localidad == "Todas" else sel_localidad
        )

        col_fecha_aus = meta_aus["col_fecha"]
        col_dias_aus = meta_aus["col_dias"]
        col_tipo_aus = meta_aus["col_tipo"]
        col_nombre_aus = meta_aus["col_nombre"]
        col_area_aus = meta_aus["col_area"]
        col_sector_aus = meta_aus["col_sector"]

        dot_mes = len(snapshot_filtered(
            fecha_corte,
            area=None if sel_area == "Todas" else sel_area,
            localidad=None if sel_localidad == "Todas" else sel_localidad,
            online="Todos"
        ))

        dias_ausentes = df_aus_mes[col_dias_aus].sum() if not df_aus_mes.empty else 0
        dias_lab = dias_laborables_estimados(sel_anio, sel_mes_num)
        ausentismo_pct = (dias_ausentes / (dot_mes * dias_lab) * 100) if dot_mes > 0 and dias_lab > 0 else 0

        aa1, aa2 = st.columns([1, 2.2])
        with aa1:
            metric_card("Ausentismo Mensual", format_pct(ausentismo_pct))
            st.caption(f"Días ausentes: {dias_ausentes:.0f}")
            st.caption(f"Días laborables estimados: {dias_lab}")
            st.caption(f"Hoja leída: {meta_aus['sheet_name']}")

        with aa2:
            if not df_aus_mes.empty and col_nombre_aus:
                resumen_cols = [c for c in [col_nombre_aus, col_tipo_aus, col_dias_aus] if c]
                resumen = df_aus_mes[resumen_cols].copy()
                st.dataframe(resumen.reset_index(drop=True), use_container_width=True, height=160)

        bb1, bb2, bb3 = st.columns([1.2, 1.2, 1.3])

        with bb1:
            if not df_aus_mes.empty and col_sector_aus:
                sec_df = (
                    df_aus_mes.groupby(col_sector_aus)[col_dias_aus]
                    .sum()
                    .reset_index()
                    .sort_values(col_dias_aus, ascending=False)
                )
                sec_df["aus_pct"] = sec_df[col_dias_aus].apply(
                    lambda x: (x / (dot_mes * dias_lab) * 100) if dot_mes > 0 and dias_lab > 0 else 0
                )
                fig_sec = px.bar(
                    sec_df,
                    x="aus_pct",
                    y=col_sector_aus,
                    orientation="h",
                    text_auto=".2f"
                )
                fig_sec.update_traces(marker_color=COLOR_ROJO)
                fig_sec.update_layout(
                    title="% Ausentismo por Sector",
                    height=300,
                    margin=dict(l=10, r=10, t=45, b=10),
                    xaxis_title="",
                    yaxis_title=""
                )
                st.plotly_chart(fig_sec, use_container_width=True)

        with bb2:
            if not df_aus_mes.empty and col_area_aus:
                area_df = (
                    df_aus_mes.groupby(col_area_aus)[col_dias_aus]
                    .sum()
                    .reset_index()
                    .sort_values(col_dias_aus, ascending=False)
                )
                area_df["aus_pct"] = area_df[col_dias_aus].apply(
                    lambda x: (x / (dot_mes * dias_lab) * 100) if dot_mes > 0 and dias_lab > 0 else 0
                )
                fig_area_aus = px.bar(
                    area_df,
                    x=col_area_aus,
                    y="aus_pct",
                    text_auto=".2f"
                )
                fig_area_aus.update_traces(marker_color=COLOR_ROJO)
                fig_area_aus.update_layout(
                    title="% Ausentismo por Área",
                    height=300,
                    margin=dict(l=10, r=10, t=45, b=10),
                    xaxis_title="",
                    yaxis_title=""
                )
                st.plotly_chart(fig_area_aus, use_container_width=True)

        with bb3:
            punto_df = pd.DataFrame(
                {"mes": [sel_mes_nombre], "ausentismo": [ausentismo_pct]}
            )
            fig_punto = px.scatter(punto_df, x="mes", y="ausentismo", size=[18])
            fig_punto.update_traces(marker=dict(color=COLOR_ROJO))
            fig_punto.update_layout(
                title="Ausentismo Mensual",
                height=300,
                margin=dict(l=10, r=10, t=45, b=10),
                xaxis_title="",
                yaxis_title=""
            )
            st.plotly_chart(fig_punto, use_container_width=True)

        cc1, cc2 = st.columns([1.5, 1.2])

        with cc1:
            if not df_aus_mes.empty and col_tipo_aus:
                tipo_df = (
                    df_aus_mes.groupby(col_tipo_aus)[col_dias_aus]
                    .sum()
                    .reset_index()
                    .sort_values(col_dias_aus, ascending=False)
                )
                tipo_df["aus_pct"] = tipo_df[col_dias_aus].apply(
                    lambda x: (x / (dot_mes * dias_lab) * 100) if dot_mes > 0 and dias_lab > 0 else 0
                )

                fig_tipo = px.bar(
                    tipo_df,
                    x="aus_pct",
                    y=col_tipo_aus,
                    orientation="h",
                    text_auto=".2f"
                )
                fig_tipo.update_traces(marker_color=COLOR_ROJO)
                fig_tipo.update_layout(
                    title="% Ausentismo por Tipo de Licencia",
                    height=320,
                    margin=dict(l=10, r=10, t=45, b=10),
                    xaxis_title="",
                    yaxis_title=""
                )
                st.plotly_chart(fig_tipo, use_container_width=True)

        with cc2:
            if not df_aus_mes.empty and col_tipo_aus:
                tipo_pie = (
                    df_aus_mes.groupby(col_tipo_aus)[col_dias_aus]
                    .sum()
                    .reset_index()
                    .sort_values(col_dias_aus, ascending=False)
                )
                fig_pie_tipo = make_donut(tipo_pie, col_tipo_aus, col_dias_aus, "Distribución por Tipo de Licencia")
                st.plotly_chart(fig_pie_tipo, use_container_width=True)
