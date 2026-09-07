import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pypdf
import re
import io
import urllib.parse
import json
import requests

# Librerías para generación de PDF profesional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ---------------------------------------------------------
# Configuración inicial de la página
# ---------------------------------------------------------
st.set_page_config(
    page_title="STORIA PARFUMS",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

URL_CATALOGO_PUBLICO = "https://storiaparfums.streamlit.app"

# ---------------------------------------------------------
# DICCIONARIO DE SOCIOS, CLAVES Y WHATSAPP DIRECTOS
# ---------------------------------------------------------
USUARIOS_SOCIOS = {
    "Franco Navarrete": "41004368",
    "Sebastián Agüero": "38473626",
    "Tomás Cubillos": "95113521"
}

SOCIOS_WHATSAPP = {
    "Franco Navarrete": "5492613350949",
    "Sebastián Agüero": "5492615913895",
    "Tomás Cubillos": "5492616621668"
}

SOCIOS = list(USUARIOS_SOCIOS.keys())
ESTADOS = ["En Stock", "A pedido", "Agotado"]
GENEROS = ["Unisex", "Hombre", "Mujer"]

CATEGORIAS = [
    "", 
    "Maison Alhambra", "Lattafa", "Armaf", "Al Haramain", "Rasasi", 
    "French Avenue", "Afnan", "Al Wataniah", "Zimaya", "Bharara", 
    "Orientica", "Matin Martin", "Rayhaan", "Paris Corner", "Borouj", 
    "Victoria's Secret", "Nicho", "Diseñador", "Árabe"
]

CLAVE_ADMIN_MASTER = "1234"

# ---------------------------------------------------------
# CONEXIÓN A TURSO VÍA HTTP API (CON SOPORTE BATCH EN LOTES)
# ---------------------------------------------------------
def get_turso_endpoint():
    url = st.secrets["TURSO_DATABASE_URL"]
    if url.startswith("libsql://"):
        url = url.replace("libsql://", "https://")
    if not url.endswith("/v2/pipeline"):
        url = url.rstrip("/") + "/v2/pipeline"
    return url

def format_arg(p):
    if p is None:
        return {"type": "null"}
    elif isinstance(p, bool):
        return {"type": "number", "value": str(int(p))}
    elif isinstance(p, (int, float)):
        return {"type": "number", "value": str(p)}
    else:
        return {"type": "text", "value": str(p)}

def query_turso_http(sql, params=()):
    url = get_turso_endpoint()
    token = st.secrets["TURSO_AUTH_TOKEN"]

    args = [format_arg(p) for p in params]
    payload = {
        "requests": [
            {"type": "execute", "stmt": {"sql": sql, "args": args}},
            {"type": "close"}
        ]
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    resp = requests.post(url, json=payload, headers=headers, timeout=15)
    if resp.status_code != 200:
        raise Exception(f"Turso Error ({resp.status_code}): {resp.text}")

    data = resp.json()
    res_stmt = data["results"][0]["response"]["result"]
    cols = [c["name"] for c in res_stmt.get("cols", [])]
    
    rows = []
    for r in res_stmt.get("rows", []):
        row_vals = [cell.get("value") for cell in r]
        rows.append(row_vals)

    return cols, rows

def execute_batch_turso(statements):
    """Ejecuta una lista de (sql, params) en un solo pipeline HTTP para evitar rate limits."""
    if not statements:
        return
    url = get_turso_endpoint()
    token = st.secrets["TURSO_AUTH_TOKEN"]
    
    requests_payload = []
    for sql, params in statements:
        args = [format_arg(p) for p in params]
        requests_payload.append({"type": "execute", "stmt": {"sql": sql, "args": args}})
    
    requests_payload.append({"type": "close"})
    
    payload = {"requests": requests_payload}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise Exception(f"Turso Batch Error ({resp.status_code}): {resp.text}")

def execute_query(query, params=()):
    query_turso_http(query, params)

def fetch_df(query, params=()):
    cols, rows = query_turso_http(query, params)
    return pd.DataFrame(rows, columns=cols)

# ---------------------------------------------------------
# FUNCIONES AUXILIARES DE MONEDA, FORMATO Y TELEFONÍA
# ---------------------------------------------------------
def redondear_monto(monto, base=100):
    try:
        val = float(monto)
        return round(val / base) * base
    except (ValueError, TypeError):
        return 0.0

def fmt_ars(monto):
    try:
        return f"${int(round(float(monto))):,}".replace(",", ".") + " ARS"
    except (ValueError, TypeError):
        return "$0 ARS"

def limpiar_int_ml(val, defecto=100):
    try:
        if isinstance(val, bytes):
            val = val.decode('utf-8', errors='ignore')
        val_clean = re.sub(r'[^\d]', '', str(val))
        return int(val_clean) if val_clean else defecto
    except Exception:
        return defecto

def formatear_celular_wa(numero_str):
    if not numero_str:
        return ""
    num = re.sub(r'[^\d]', '', str(numero_str))
    if not num:
        return ""
    if num.startswith("549"):
        return num
    if num.startswith("54") and not num.startswith("549"):
        num = num[2:]
    if num.startswith("0"):
        num = num[1:]
    if num.startswith("26115"):
        num = "261" + num[5:]
    elif num.startswith("15"):
        num = num[2:]
    if not num.startswith("549"):
        num = "549" + num
    return num

# ---------------------------------------------------------
# ESTILOS CSS PERSONALIZADOS
# ---------------------------------------------------------
st.markdown("""
    <style>
    .stApp {
        background-color: #1C1412;
        color: #F3EBE6;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
    h1, h2, h3 {
        color: #D4AF37 !important;
        font-weight: 300 !important;
        letter-spacing: 1px !important;
    }
    [data-testid="stMetricValue"] {
        color: #E5C158 !important;
        font-size: 1.5rem !important;
    }
    [data-testid="stMetricLabel"] {
        color: #C5A059 !important;
    }
    .perfume-card {
        background-color: #291D1A;
        border: 1px solid #3D2B27;
        border-left: 4px solid #D4AF37;
        padding: 14px;
        border-radius: 8px;
        margin-bottom: 14px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .perfume-title {
        color: #FFFFFF;
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .perfume-badge {
        background-color: #3D2B27;
        color: #D4AF37;
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: 12px;
        font-weight: 500;
        display: inline-block;
        margin-bottom: 8px;
        margin-right: 4px;
    }
    .badge-genero {
        background-color: #2D3748;
        color: #E2E8F0;
    }
    .perfume-notes {
        color: #C5A059;
        font-size: 0.85rem;
        font-style: italic;
        margin-top: 4px;
        margin-bottom: 8px;
    }
    .perfume-price {
        color: #E5C158;
        font-weight: bold;
        font-size: 1.05rem;
    }
    .stock-badge-green {
        color: #4EAD5B;
        font-size: 0.82rem;
        font-weight: bold;
    }
    .stock-badge-red {
        color: #E55353;
        font-size: 0.82rem;
        font-weight: bold;
    }
    .stImage > img {
        max-height: 160px !important;
        width: auto !important;
        object-fit: contain !important;
        margin: 0 auto !important;
        display: block !important;
        border-radius: 6px !important;
        background-color: #140E0D !important;
        padding: 4px !important;
        border: 1px solid #3D2B27 !important;
    }
    .stButton>button {
        background-color: #D4AF37 !important;
        color: #1C1412 !important;
        font-weight: bold !important;
        border-radius: 6px !important;
        border: none !important;
        padding: 8px 16px !important;
        transition: all 0.3s ease;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #E5C158 !important;
        box-shadow: 0 0 10px rgba(212, 175, 55, 0.4);
    }
    .btn-whatsapp {
        display: block;
        background-color: #25D366;
        color: white !important;
        text-align: center;
        padding: 10px;
        border-radius: 6px;
        font-weight: bold;
        text-decoration: none;
        margin-bottom: 8px;
        font-size: 0.9rem;
    }
    .btn-whatsapp:hover {
        background-color: #1EBE57;
    }
    section[data-testid="stSidebar"] {
        background-color: #140E0D !important;
        border-right: 1px solid #291D1A;
    }
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input {
        background-color: #291D1A !important;
        color: #FFFFFF !important;
        border: 1px solid #4A3530 !important;
        border-radius: 6px !important;
    }
    </style>
""", unsafe_allow_html=True)

COLOR_BG_PDF = colors.HexColor("#1C1412")
COLOR_GOLD_PDF = colors.HexColor("#D4AF37")

# ---------------------------------------------------------
# INICIALIZACIÓN DE TABLAS EN TURSO
# ---------------------------------------------------------
def init_db():
    execute_query('''
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            tipo TEXT,
            genero TEXT DEFAULT 'Unisex',
            capacidad_ml INTEGER DEFAULT 100,
            botellas_100ml_cerradas INTEGER DEFAULT 0,
            ml_disponibles_abiertos INTEGER DEFAULT 0,
            decants_10ml_preparados INTEGER DEFAULT 0,
            costo_usd REAL DEFAULT 0.0,
            margen_100ml_custom REAL,
            estado TEXT DEFAULT 'A pedido',
            socio_asignado TEXT DEFAULT '',
            monto_senado_ars REAL DEFAULT 0.0,
            cliente_senado TEXT DEFAULT '',
            notas_olfativas TEXT DEFAULT '',
            imagen_url TEXT DEFAULT ''
        )
    ''')

    execute_query('''
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            perfume TEXT,
            socio TEXT,
            tipo_movimiento TEXT,
            monto_ingreso_ars REAL DEFAULT 0.0,
            id_producto INTEGER DEFAULT 0,
            presentacion TEXT DEFAULT '',
            cantidad INTEGER DEFAULT 1
        )
    ''')

    execute_query('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cotizacion_dolar REAL,
            margen_100ml REAL,
            margen_decant REAL,
            costo_envase_decant_ars REAL
        )
    ''')
    execute_query('''
        INSERT OR IGNORE INTO config (id, cotizacion_dolar, margen_100ml, margen_decant, costo_envase_decant_ars)
        VALUES (1, 1200.0, 30.0, 100.0, 800.0)
    ''')

    execute_query('''
        CREATE TABLE IF NOT EXISTS clientes_seguimiento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_compra TEXT,
            cliente_nombre TEXT,
            cliente_celular TEXT,
            socio_vendedor TEXT,
            perfume TEXT,
            presentacion TEXT,
            dias_estimados INTEGER,
            fecha_recordatorio TEXT,
            estado TEXT DEFAULT 'Pendiente'
        )
    ''')

    execute_query('''
        CREATE TABLE IF NOT EXISTS egresos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            categoria TEXT,
            descripcion TEXT,
            monto_ars REAL,
            socio_registra TEXT
        )
    ''')

    execute_query('''
        CREATE TABLE IF NOT EXISTS ordenes_compra (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            nombre TEXT,
            capacidad_ml INTEGER,
            cantidad INTEGER,
            costo_usd REAL,
            estado_inventario TEXT,
            detalle_reserva TEXT,
            socio_agrega TEXT
        )
    ''')

try:
    init_db()
except Exception as e:
    st.error(f"Error al conectar con la base de datos Turso: {e}")

# ---------------------------------------------------------
# CARGA CON CACHÉ DE CORTO TIEMPO
# ---------------------------------------------------------
@st.cache_data(ttl=15)
def cargar_datos_stock():
    df = fetch_df("SELECT * FROM stock")
    if not df.empty:
        if "capacidad_ml" in df.columns:
            df["capacidad_ml"] = df["capacidad_ml"].apply(lambda v: limpiar_int_ml(v, 100))
        if "genero" in df.columns:
            df["genero"] = df["genero"].fillna("Unisex").replace("", "Unisex")
    return df

@st.cache_data(ttl=15)
def cargar_historial():
    df = fetch_df("SELECT * FROM historial ORDER BY id DESC")
    if not df.empty and "fecha" in df.columns:
        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors='coerce')
    return df

@st.cache_data(ttl=15)
def cargar_egresos():
    df = fetch_df("SELECT * FROM egresos ORDER BY id DESC")
    if not df.empty and "fecha" in df.columns:
        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors='coerce')
    return df

@st.cache_data(ttl=15)
def cargar_seguimiento():
    return fetch_df("SELECT * FROM clientes_seguimiento ORDER BY fecha_recordatorio ASC")

@st.cache_data(ttl=15)
def cargar_ordenes_compra():
    df = fetch_df("SELECT * FROM ordenes_compra ORDER BY id ASC")
    if not df.empty and "capacidad_ml" in df.columns:
        df["capacidad_ml"] = df["capacidad_ml"].apply(lambda v: limpiar_int_ml(v, 100))
    return df

@st.cache_data(ttl=15)
def cargar_config():
    df = fetch_df("SELECT cotizacion_dolar, margen_100ml, margen_decant, costo_envase_decant_ars FROM config WHERE id = 1")
    if not df.empty:
        r = df.iloc[0]
        return float(r["cotizacion_dolar"]), float(r["margen_100ml"]), float(r["margen_decant"]), float(r["costo_envase_decant_ars"])
    return 1200.0, 30.0, 100.0, 800.0

def guardar_config(dolar, m100, mdec, envase):
    execute_query('''
        UPDATE config 
        SET cotizacion_dolar = ?, margen_100ml = ?, margen_decant = ?, costo_envase_decant_ars = ?
        WHERE id = 1
    ''', (dolar, m100, mdec, envase))
    st.cache_data.clear()

def normalizar_texto(texto):
    if not texto:
        return ""
    txt = str(texto).lower().strip()
    txt = re.sub(r'\s+', ' ', txt)
    return txt

def extraer_perfume_y_precio(linea):
    linea = str(linea).encode('utf-8', 'ignore').decode('utf-8')
    cap_match = re.search(r'(\d+)\s*(?:ml|ML)\b', linea)
    cap_ml = int(cap_match.group(1)) if cap_match else 100

    linea_limpia = re.sub(r'(?i)\b\d+\s*(ml|gr|oz|un|unid|unidades|edp|edt|parfum)\b', '', linea)
    linea_limpia = re.sub(r'\(\d+\)', '', linea_limpia)
    
    match_precio = re.search(r'\$\s*(\d+[\.\,]?\d*)', linea_limpia)
    if match_precio:
        precio_str = match_precio.group(1)
        idx_precio = linea_limpia.find(match_precio.group(0))
        nombre = linea_limpia[:idx_precio].strip()
        try:
            precio = float(precio_str.replace(",", "."))
            return nombre, precio, cap_ml
        except ValueError:
            return None, None, 100
    else:
        numeros = re.findall(r'\b\d+[\.\,]?\d*\b', linea_limpia)
        if numeros:
            precio_str = numeros[-1]
            idx_num = linea_limpia.rfind(precio_str)
            nombre = linea_limpia[:idx_num].strip()
            nombre = re.sub(r'\s+\d+$', '', nombre)
            try:
                precio = float(precio_str.replace(",", "."))
                return nombre, precio, cap_ml
            except ValueError:
                return None, None, 100
    return None, None, 100

# ---------------------------------------------------------
# INTERFAZ Y CONTROL DE SESIÓN
# ---------------------------------------------------------
if "socio_autenticado" not in st.session_state:
    st.session_state.socio_autenticado = None

st.markdown("<h1 style='text-align: center; margin-bottom: 0px;'>S T O R I A</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #C5A059; letter-spacing: 3px; font-size: 0.8rem;'>P A R F U M S</p>", unsafe_allow_html=True)
st.markdown("---")

dolar_hoy, margen_100_gen, margen_dec_gen, costo_envase = cargar_config()

modo_acceso = st.sidebar.radio(
    "Acceso al Sistema:",
    ["📖 Catálogo Clientes (Libre)", "🔐 Panel Administrador (Socios)"]
)

# ---------------------------------------------------------
# MODO 1: CATÁLOGO PÚBLICO CLIENTE
# ---------------------------------------------------------
if modo_acceso == "📖 Catálogo Clientes (Libre)":
    st.header("📖 Catálogo de Fragancias")

    df_cat_base = cargar_datos_stock()
    
    if not df_cat_base.empty:
        df_cat_base["estado"] = df_cat_base["estado"].replace("Disponible en Proveedor", "A pedido")
        df_cat_base = df_cat_base[df_cat_base["estado"].isin(['En Stock', 'A pedido'])]
        
        df_cat_base["orden"] = df_cat_base["estado"].apply(lambda x: 0 if x == "En Stock" else 1)
        df_cat_base = df_cat_base.sort_values(by=["orden", "nombre"]).drop(columns=["orden"])

        df_cat_base["costo_usd"] = pd.to_numeric(df_cat_base["costo_usd"], errors='coerce').fillna(0.0)
        df_cat_base["capacidad_ml"] = df_cat_base["capacidad_ml"].apply(lambda v: limpiar_int_ml(v, 100))
        df_cat_base["decants_10ml_preparados"] = pd.to_numeric(df_cat_base["decants_10ml_preparados"], errors='coerce').fillna(0).astype(int)
        df_cat_base["botellas_100ml_cerradas"] = pd.to_numeric(df_cat_base["botellas_100ml_cerradas"], errors='coerce').fillna(0).astype(int)
        df_cat_base["ml_disponibles_abiertos"] = pd.to_numeric(df_cat_base["ml_disponibles_abiertos"], errors='coerce').fillna(0).astype(int)

        df_cat_base["margen_100ml_custom"] = pd.to_numeric(df_cat_base["margen_100ml_custom"], errors='coerce')
        df_cat_base["margen_aplicado"] = df_cat_base["margen_100ml_custom"].fillna(margen_100_gen)
        
        df_cat_base["costo_ars"] = df_cat_base["costo_usd"] * dolar_hoy
        df_cat_base["precio_100ml_raw"] = df_cat_base["costo_ars"] * (1 + (df_cat_base["margen_aplicado"] / 100))
        df_cat_base["precio_100ml"] = df_cat_base["precio_100ml_raw"].apply(lambda x: redondear_monto(x, 100))
        
        df_cat_base["costo_liquido_10ml"] = df_cat_base.apply(
            lambda r: (r["costo_ars"] / r["capacidad_ml"] * 10) if r["capacidad_ml"] > 0 else (r["costo_ars"] * 0.10), axis=1
        )
        df_cat_base["precio_decant_raw"] = (df_cat_base["costo_liquido_10ml"] + costo_envase) * (1 + (margen_dec_gen / 100))
        df_cat_base["precio_decant"] = df_cat_base["precio_decant_raw"].apply(lambda x: redondear_monto(x, 100))

        st.subheader("💡 ¿Te interesa alguna fragancia?")
        st.markdown("<small>Selecciona los perfumes sobre los que quieres consultar y luego presiona el botón del socio con quien desees hablar:</small>", unsafe_allow_html=True)
        
        perfumes_seleccionados = st.multiselect(
            "Selecciona uno o varios perfumes para consultar:",
            options=df_cat_base["nombre"].tolist(),
            placeholder="Escribe o selecciona perfumes..."
        )
        
        if perfumes_seleccionados:
            lista_p_str = ", ".join(perfumes_seleccionados)
            msg_texto = f"Hola! Estaba viendo el catálogo de STORIA PARFUMS y me gustaría consultar disponibilidad y precio sobre: {lista_p_str}."
        else:
            msg_texto = "Hola! Estaba viendo el catálogo web de STORIA PARFUMS y me gustaría hacerles una consulta."
            
        msg_encoded = urllib.parse.quote(msg_texto)

        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            st.markdown(f'<a href="https://wa.me/{SOCIOS_WHATSAPP["Franco Navarrete"]}?text={msg_encoded}" target="_blank" class="btn-whatsapp">💬 Consultar a Franco</a>', unsafe_allow_html=True)
        with col_w2:
            st.markdown(f'<a href="https://wa.me/{SOCIOS_WHATSAPP["Sebastián Agüero"]}?text={msg_encoded}" target="_blank" class="btn-whatsapp">💬 Consultar a Sebastián</a>', unsafe_allow_html=True)
        with col_w3:
            st.markdown(f'<a href="https://wa.me/{SOCIOS_WHATSAPP["Tomás Cubillos"]}?text={msg_encoded}" target="_blank" class="btn-whatsapp">💬 Consultar a Tomás</a>', unsafe_allow_html=True)

        st.markdown("---")

        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            busq_cli = st.text_input("🔍 Buscar perfume:", placeholder="Ej. Khamrah, Club de Nuit...")
        with col_f2:
            filtro_genero = st.selectbox("👤 Filtrar por Género:", ["Todos los géneros", "Hombre", "Mujer", "Unisex"])
        with col_f3:
            marcas_disponibles = ["Todas las marcas / categorías"] + sorted(list(set(df_cat_base["tipo"].dropna().unique())))
            filtro_marca = st.selectbox("🏷️ Filtrar por Marca:", marcas_disponibles)

        if busq_cli:
            df_cat_base = df_cat_base[df_cat_base["nombre"].astype(str).str.contains(busq_cli, case=False, na=False)]
        if filtro_genero != "Todos los géneros":
            df_cat_base = df_cat_base[df_cat_base["genero"] == filtro_genero]
        if filtro_marca != "Todas las marcas / categorías":
            df_cat_base = df_cat_base[df_cat_base["tipo"] == filtro_marca]

        for _, r in df_cat_base.iterrows():
            notas_html = f'<div class="perfume-notes">🌸 <b>Notas:</b> {r["notas_olfativas"]}</div>' if pd.notnull(r.get("notas_olfativas")) and str(r.get("notas_olfativas")).strip() != "" else ""
            tipo_html = f' • <span style="color:#C5A059;">{r["tipo"]}</span>' if pd.notnull(r.get("tipo")) and str(r.get("tipo")).strip() != "" else ""

            gen_val = r.get("genero", "Unisex")
            icon_gen = "♂️" if gen_val == "Hombre" else ("♀️" if gen_val == "Mujer" else "🚻")
            genero_badge = f'<span class="perfume-badge badge-genero">{icon_gen} {gen_val}</span>'

            p_100ml_str = fmt_ars(r['precio_100ml'])
            p_decant_str = fmt_ars(r['precio_decant'])
            cap_ml = limpiar_int_ml(r.get("capacidad_ml", 100), 100)
            cnt_decants = r.get("decants_10ml_preparados", 0)
            cnt_ml_ab = r.get("ml_disponibles_abiertos", 0)

            if cnt_decants > 0 or cnt_ml_ab >= 10:
                stock_dec_html = '<span class="stock-badge-green"> (Disponible)</span>'
            else:
                stock_dec_html = '<span class="stock-badge-red"> (A pedido)</span>'

            estado_class = "perfume-badge"
            txt_sen = r['estado']

            col_card_1, col_card_2 = st.columns([1, 3])
            with col_card_1:
                if pd.notnull(r.get("imagen_url")) and str(r.get("imagen_url")).strip().startswith("http"):
                    try:
                        st.image(r["imagen_url"], use_container_width=True)
                    except Exception:
                        st.markdown("<h2 style='text-align: center; color: #D4AF37;'>✨</h2>", unsafe_allow_html=True)
                else:
                    st.markdown("<h2 style='text-align: center; color: #D4AF37;'>✨</h2>", unsafe_allow_html=True)
            with col_card_2:
                card_html = f'<div class="perfume-card"><div class="perfume-title">{r["nombre"]}</div><span class="{estado_class}">{txt_sen}</span>{genero_badge}{tipo_html}{notas_html}<div style="margin-top: 6px;"><div>Frasco {cap_ml}ml: <span class="perfume-price">{p_100ml_str}</span></div><div>Decant 10ml: <span class="perfume-price">{p_decant_str}</span>{stock_dec_html}</div></div></div>'
                st.markdown(card_html, unsafe_allow_html=True)
    else:
        st.info("No hay fragancias disponibles en el catálogo.")

# ---------------------------------------------------------
# MODO 2: PANEL DE ADMINISTRADOR (RESTRINGIDO)
# ---------------------------------------------------------
else:
    st.sidebar.markdown("---")
    
    if st.session_state.socio_autenticado is None:
        st.header("🔐 Ingreso de Socios")
        
        with st.form("login_form"):
            socio_ingresado = st.selectbox("Selecciona Socio / Usuario:", SOCIOS)
            clave_ingresada = st.text_input("Ingresa tu Contraseña:", type="password")
            btn_login = st.form_submit_button("Ingresar")
            
            if btn_login:
                if clave_ingresada == USUARIOS_SOCIOS.get(socio_ingresado):
                    st.session_state.socio_autenticado = socio_ingresado
                    st.success(f"Bienvenido {socio_ingresado}")
                    st.rerun()
                else:
                    st.error("❌ Contraseña incorrecta.")
    
    else:
        st.sidebar.success(f"👤 Socio: **{st.session_state.socio_autenticado}**")
        if st.sidebar.button("🚪 Cerrar Sesión"):
            st.session_state.socio_autenticado = None
            st.rerun()

        st.sidebar.markdown("---")
        seccion_admin = st.sidebar.radio(
            "Gestión Interna:",
            [
                "📦 Stock & Precios", 
                "✏️ Editar / Eliminar",
                "➕ Agregar Perfume", 
                "📄 Cargar PDF Proveedor",
                "💾 Copias de Seguridad"
            ]
        )

        # --- SECCIÓN: STOCK Y PRECIOS ---
        if seccion_admin == "📦 Stock & Precios":
            st.header("📦 Inventario Global")
            df = cargar_datos_stock()

            if not df.empty:
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No hay perfumes en el sistema.")

        # --- SECCIÓN: EDITAR / ELIMINAR ---
        elif seccion_admin == "✏️ Editar / Eliminar":
            st.header("✏️ Editar Estado o Eliminar")
            df_mod = cargar_datos_stock()

            if not df_mod.empty:
                opciones_mod = [f"ID: {row['id']} | {row['nombre']}" for _, row in df_mod.iterrows()]
                prod_sel = st.selectbox("Selecciona producto:", opciones_mod)
                id_mod = int(prod_sel.split(" | ")[0].replace("ID: ", ""))
                prod_data = df_mod[df_mod['id'] == id_mod].iloc[0]

                with st.form("form_edicion"):
                    nuevo_nombre = st.text_input("Nombre", value=prod_data['nombre'])
                    nuevo_costo = st.number_input("Costo USD", value=float(prod_data['costo_usd']))

                    if st.form_submit_button("Guardar Cambios"):
                        execute_query("UPDATE stock SET nombre = ?, costo_usd = ? WHERE id = ?", (nuevo_nombre, nuevo_costo, id_mod))
                        st.cache_data.clear()
                        st.success("Guardado correctamente!")
                        st.rerun()

        # --- SECCIÓN: AGREGAR PERFUME ---
        elif seccion_admin == "➕ Agregar Perfume":
            st.header("➕ Cargar Producto Manual")
            with st.form("form_alta", clear_on_submit=True):
                nombre = st.text_input("Nombre del perfume")
                costo_usd = st.number_input("Costo USD ($)", min_value=0.0, value=0.0)
                
                if st.form_submit_button("Guardar Perfume"):
                    if nombre.strip() != "":
                        execute_query('''
                            INSERT INTO stock (nombre, costo_usd, estado) VALUES (?, ?, 'A pedido')
                        ''', (nombre.strip(), costo_usd))
                        st.cache_data.clear()
                        st.success("¡Perfume guardado!")
                        st.rerun()

        # --- SECCIÓN: CARGAR PDF PROVEEDOR ---
        elif seccion_admin == "📄 Cargar PDF Proveedor":
            st.header("📄 Procesar PDF Proveedor")
            uploaded_pdf = st.file_uploader("Subir PDF de Proveedor", type=["pdf"])

            if uploaded_pdf is not None:
                try:
                    reader = pypdf.PdfReader(uploaded_pdf)
                    texto_completo = ""
                    for page in reader.pages:
                        txt_p = page.extract_text()
                        if txt_p:
                            texto_completo += txt_p + "\n"

                    items = []
                    for l in texto_completo.split("\n"):
                        p_nom, p_cost, p_cap = extraer_perfume_y_precio(l)
                        if p_nom and p_cost and len(p_nom) > 2 and p_cost > 3:
                            items.append({"nombre": str(p_nom), "costo_usd": float(p_cost), "capacidad_ml": int(p_cap)})

                    if items:
                        df_pdf = pd.DataFrame(items)
                        df_pdf["nombre_norm"] = df_pdf["nombre"].apply(normalizar_texto)
                        df_pdf = df_pdf.drop_duplicates(subset=["nombre_norm"]).drop(columns=["nombre_norm"])
                        st.write(f"Detectados: **{len(df_pdf)}** perfumes en el PDF")
                        st.dataframe(df_pdf, use_container_width=True)

                        if st.button("🚀 Sincronizar Catálogo"):
                            df_ex = fetch_df("SELECT id, nombre FROM stock")
                            dict_existentes = {}
                            if not df_ex.empty:
                                dict_existentes = {normalizar_texto(r["nombre"]): r["id"] for _, r in df_ex.iterrows()}
                            
                            statements = []
                            for _, r in df_pdf.iterrows():
                                nom_norm = normalizar_texto(r['nombre'])
                                if nom_norm in dict_existentes:
                                    statements.append((
                                        "UPDATE stock SET costo_usd = ?, capacidad_ml = ? WHERE id = ?",
                                        (float(r['costo_usd']), int(r['capacidad_ml']), int(dict_existentes[nom_norm]))
                                    ))
                                else:
                                    statements.append((
                                        '''INSERT INTO stock (nombre, tipo, genero, capacidad_ml, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, costo_usd, estado, socio_asignado)
                                           VALUES (?, '', 'Unisex', ?, 0, 0, 0, ?, 'A pedido', '')''',
                                        (str(r['nombre']), int(r['capacidad_ml']), float(r['costo_usd']))
                                    ))

                            # Ejecutamos por lotes de 25
                            chunk_size = 25
                            for i in range(0, len(statements), chunk_size):
                                chunk = statements[i:i + chunk_size]
                                execute_batch_turso(chunk)

                            st.cache_data.clear()
                            st.success("¡Sincronización completada en lote!")
                            st.rerun()
                except Exception as e:
                    st.error(f"Error procesando PDF: {e}")

        # --- SECCIÓN: COPIAS DE SEGURIDAD (RESTAURACIÓN RÁPIDA VÍA BATCH) ---
        elif seccion_admin == "💾 Copias de Seguridad":
            st.header("💾 Copias de Seguridad (Backup y Restauración)")

            tab_bk1, tab_bk2 = st.tabs(["📥 Descargar Backup", "📤 Restaurar Copia de Seguridad"])

            with tab_bk1:
                backup_data = {
                    "stock": fetch_df("SELECT * FROM stock").to_dict(orient="records"),
                    "historial": fetch_df("SELECT * FROM historial").to_dict(orient="records"),
                    "config": fetch_df("SELECT * FROM config").to_dict(orient="records"),
                    "clientes_seguimiento": fetch_df("SELECT * FROM clientes_seguimiento").to_dict(orient="records"),
                    "egresos": fetch_df("SELECT * FROM egresos").to_dict(orient="records"),
                    "ordenes_compra": fetch_df("SELECT * FROM ordenes_compra").to_dict(orient="records")
                }
                json_bytes = json.dumps(backup_data, indent=4, ensure_ascii=False).encode('utf-8')
                
                st.download_button(
                    label="⬇️ Descargar Copia de Seguridad (.json)",
                    data=json_bytes,
                    file_name=f"Backup_Storia_{datetime.now().strftime('%Y_%m_%d_%H%M')}.json",
                    mime="application/json"
                )

            with tab_bk2:
                uploaded_backup = st.file_uploader("Selecciona archivo .json:", type=["json"])

                if uploaded_backup is not None:
                    try:
                        data_restaurar = json.load(uploaded_backup)
                        
                        st.write("📋 **Contenido detectado:**")
                        for t_name, rows_t in data_restaurar.items():
                            st.write(f"- Tabla **{t_name}**: {len(rows_t)} registros.")

                        confirm_restore = st.checkbox("⚠️ Confirmar restauración completa", key="chk_confirm_restore")

                        if st.button("🚀 Iniciar Restauración Ultra-Rápida"):
                            if confirm_restore:
                                progress_bar = st.progress(0)
                                statements = []

                                # 1. STOCK
                                if "stock" in data_restaurar:
                                    for r in data_restaurar["stock"]:
                                        sql = '''INSERT OR REPLACE INTO stock (id, nombre, tipo, genero, capacidad_ml, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, costo_usd, margen_100ml_custom, estado, socio_asignado, monto_senado_ars, cliente_senado, notas_olfativas, imagen_url)
                                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
                                        params = (
                                            r.get("id"), str(r.get("nombre", "")), str(r.get("tipo", "")), str(r.get("genero", "Unisex")), int(r.get("capacidad_ml", 100)),
                                            int(r.get("botellas_100ml_cerradas", 0)), int(r.get("ml_disponibles_abiertos", 0)), int(r.get("decants_10ml_preparados", 0)),
                                            float(r.get("costo_usd", 0.0)), r.get("margen_100ml_custom"), str(r.get("estado", "A pedido")), str(r.get("socio_asignado", "")),
                                            float(r.get("monto_senado_ars", 0.0)), str(r.get("cliente_senado", "")), str(r.get("notas_olfativas", "")), str(r.get("imagen_url", ""))
                                        )
                                        statements.append((sql, params))

                                # 2. HISTORIAL
                                if "historial" in data_restaurar:
                                    for r in data_restaurar["historial"]:
                                        sql = '''INSERT OR REPLACE INTO historial (id, fecha, perfume, socio, tipo_movimiento, monto_ingreso_ars, id_producto, presentacion, cantidad)
                                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'''
                                        params = (
                                            r.get("id"), str(r.get("fecha", "")), str(r.get("perfume", "")), str(r.get("socio", "")), str(r.get("tipo_movimiento", "")),
                                            float(r.get("monto_ingreso_ars", 0.0)), int(r.get("id_producto", 0)), str(r.get("presentacion", "")), int(r.get("cantidad", 1))
                                        )
                                        statements.append((sql, params))

                                # 3. EGRESOS
                                if "egresos" in data_restaurar:
                                    for r in data_restaurar["egresos"]:
                                        sql = '''INSERT OR REPLACE INTO egresos (id, fecha, categoria, descripcion, monto_ars, socio_registra)
                                                 VALUES (?, ?, ?, ?, ?, ?)'''
                                        params = (
                                            r.get("id"), str(r.get("fecha", "")), str(r.get("categoria", "")), str(r.get("descripcion", "")),
                                            float(r.get("monto_ars", 0.0)), str(r.get("socio_registra", ""))
                                        )
                                        statements.append((sql, params))

                                # 4. CLIENTES SEGUIMIENTO
                                if "clientes_seguimiento" in data_restaurar:
                                    for r in data_restaurar["clientes_seguimiento"]:
                                        sql = '''INSERT OR REPLACE INTO clientes_seguimiento (id, fecha_compra, cliente_nombre, cliente_celular, socio_vendedor, perfume, presentacion, dias_estimados, fecha_recordatorio, estado)
                                                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''
                                        params = (
                                            r.get("id"), str(r.get("fecha_compra", "")), str(r.get("cliente_nombre", "")), str(r.get("cliente_celular", "")),
                                            str(r.get("socio_vendedor", "")), str(r.get("perfume", "")), str(r.get("presentacion", "")), int(r.get("dias_estimados", 90)),
                                            str(r.get("fecha_recordatorio", "")), str(r.get("estado", "Pendiente"))
                                        )
                                        statements.append((sql, params))

                                # Envío masivo en bloques de 25
                                chunk_size = 25
                                total_chunks = (len(statements) // chunk_size) + 1
                                for idx, i in enumerate(range(0, len(statements), chunk_size)):
                                    chunk = statements[i:i + chunk_size]
                                    execute_batch_turso(chunk)
                                    progress_bar.progress(int(((idx + 1) / total_chunks) * 100))

                                st.cache_data.clear()
                                st.success("🎉 ¡Todos los datos de la copia de seguridad se restauraron con éxito!")
                                st.rerun()
                            else:
                                st.warning("Marca la casilla para confirmar.")
                    except Exception as err_bk:
                        st.error(f"Error restaurando la copia: {err_bk}")
