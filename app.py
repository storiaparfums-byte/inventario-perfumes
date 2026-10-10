import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pypdf
import re
import io
import urllib.parse
import json

import sqlalchemy as sa
from sqlalchemy import text

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
# CONEXIÓN A SUPABASE (POOLER - PUERTO 6543)
# ---------------------------------------------------------
try:
    db_user = "postgres.rkdxwdpytervrptqovxd"
    db_password = "nvUqLofOvZAiRtmq"
    db_host = "aws-0-us-west-2.pooler.supabase.com"
    db_port = "6543"
    db_name = "postgres"

    DATABASE_URL = f"postgresql+psycopg2://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    def get_engine():
        engine = sa.create_engine(DATABASE_URL, pool_pre_ping=True)
        return engine

    def execute_query(query, params=None):
        engine = get_engine()
        with engine.begin() as conn:
            if "?" in query and "%s" not in query:
                query = query.replace("?", "%s")
            conn.execute(text(query), params if params is not None else {})

    def fetch_df(query, params=None):
        engine = get_engine()
        if "?" in query and "%s" not in query:
            query = query.replace("?", "%s")
        with engine.connect() as conn:
            return pd.read_sql(text(query), conn, params=params if params else None)

except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")
    st.stop()

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
# ESTILOS CSS PERSONALIZADOS (ESTÉTICA MINIMALISTA Y ELEGANTE)
# ---------------------------------------------------------
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');

    .stApp {
        background-color: #1C1412 !important;
        color: #F4F1EA !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }

    h1, h2, h3, h4 {
        color: #D4AF37 !important;
        font-weight: 400 !important;
        letter-spacing: 1.5px !important;
    }

    p, span, label, div {
        color: #F4F1EA;
    }

    [data-testid="stMetricValue"] {
        color: #E5C158 !important;
        font-size: 1.6rem !important;
        font-weight: 500 !important;
    }

    [data-testid="stMetricLabel"] {
        color: #C5A059 !important;
        font-size: 0.85rem !important;
    }

    .perfume-card {
        background-color: #241A17 !important;
        border: 1px solid #362622 !important;
        border-left: 3px solid #D4AF37 !important;
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 16px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    .perfume-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 30px rgba(212, 175, 55, 0.1);
    }

    .perfume-title {
        color: #FFFFFF !important;
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 6px;
    }

    .perfume-badge {
        background-color: #362622 !important;
        color: #D4AF37 !important;
        font-size: 0.75rem;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: 500;
        display: inline-block;
        margin-bottom: 8px;
        margin-right: 6px;
        border: 1px solid #4A3530;
    }

    .badge-genero {
        background-color: #2D2320 !important;
        color: #E2E8F0 !important;
        border: 1px solid #3D2B27;
    }

    .perfume-notes {
        color: #C5A059 !important;
        font-size: 0.85rem;
        font-style: italic;
        margin-top: 6px;
        margin-bottom: 10px;
    }

    .perfume-price {
        color: #E5C158 !important;
        font-weight: 600;
        font-size: 1.1rem;
    }

    .stock-badge-green {
        color: #4EAD5B !important;
        font-size: 0.85rem;
        font-weight: 600;
    }

    .stock-badge-red {
        color: #E55353 !important;
        font-size: 0.85rem;
        font-weight: 600;
    }

    .stImage > img {
        max-height: 150px !important;
        width: auto !important;
        object-fit: contain !important;
        margin: 0 auto !important;
        display: block !important;
        border-radius: 8px !important;
        background-color: #17100E !important;
        padding: 6px !important;
        border: 1px solid #362622 !important;
    }

    .stButton>button {
        background-color: #D4AF37 !important;
        color: #1C1412 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: none !important;
        padding: 10px 20px !important;
        transition: all 0.2s ease;
        width: 100%;
        box-shadow: 0 4px 12px rgba(212, 175, 55, 0.2);
    }
    
    .stButton>button:hover {
        background-color: #E5C158 !important;
        box-shadow: 0 6px 16px rgba(212, 175, 55, 0.35);
    }

    .btn-whatsapp {
        display: block;
        background-color: #25D366;
        color: white !important;
        text-align: center;
        padding: 11px;
        border-radius: 8px;
        font-weight: 600;
        text-decoration: none;
        margin-bottom: 10px;
        font-size: 0.9rem;
        box-shadow: 0 4px 12px rgba(37, 211, 102, 0.25);
        transition: background-color 0.2s ease;
    }
    .btn-whatsapp:hover {
        background-color: #1EBE57;
    }

    section[data-testid="stSidebar"] {
        background-color: #17100E !important;
        border-right: 1px solid #291D1A;
    }

    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input {
        background-color: #241A17 !important;
        color: #F4F1EA !important;
        border: 1px solid #3D2B27 !important;
        border-radius: 8px !important;
    }
    
    .stTextInput>div>div>input:focus, .stSelectbox>div>div>div:focus {
        border-color: #D4AF37 !important;
    }
    </style>
""", unsafe_allow_html=True)

COLOR_BG_PDF = colors.HexColor("#1C1412")
COLOR_GOLD_PDF = colors.HexColor("#D4AF37")

# ---------------------------------------------------------
# INICIALIZACIÓN DE TABLAS EN SUPABASE
# ---------------------------------------------------------
def init_db():
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS stock (
                id SERIAL PRIMARY KEY,
                nombre TEXT UNIQUE,
                nombre_comercial TEXT DEFAULT '',
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
        '''))

        try:
            conn.execute(text('ALTER TABLE stock ADD COLUMN IF NOT EXISTS nombre_comercial TEXT DEFAULT ""'))
        except Exception:
            pass

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS historial (
                id SERIAL PRIMARY KEY,
                fecha TEXT,
                perfume TEXT,
                socio TEXT,
                tipo_movimiento TEXT,
                monto_ingreso_ars REAL DEFAULT 0.0,
                id_producto INTEGER DEFAULT 0,
                presentacion TEXT DEFAULT '',
                cantidad INTEGER DEFAULT 1
            )
        '''))

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                cotizacion_dolar REAL,
                margen_100ml REAL,
                margen_decant REAL,
                costo_envase_decant_ars REAL
            )
        '''))
        conn.execute(text('''
            INSERT INTO config (id, cotizacion_dolar, margen_100ml, margen_decant, costo_envase_decant_ars)
            VALUES (1, 1200.0, 30.0, 100.0, 800.0)
            ON CONFLICT (id) DO NOTHING
        '''))

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS clientes_seguimiento (
                id SERIAL PRIMARY KEY,
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
        '''))

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS egresos (
                id SERIAL PRIMARY KEY,
                fecha TEXT,
                categoria TEXT,
                descripcion TEXT,
                monto_
