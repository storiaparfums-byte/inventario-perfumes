import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import pypdf
import re
import io
import urllib.parse
import json
import base64

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
# DICCIONARIO DE SOCIOS, ZONAS Y WHATSAPP DIRECTOS
# ---------------------------------------------------------
USUARIOS_SOCIOS = {
    "Franco Navarrete": "41004368",
    "Sebastián Agüero": "38473626",
    "Tomás Cubillos": "95113521"
}

SOCIOS_WHATSAPP = {
    "Franco Navarrete": "5492613350949", # Guaymallén - Godoy Cruz
    "Sebastián Agüero": "5492615913895", # Luján - Godoy Cruz
    "Tomás Cubillos": "5492616621668"  # Centro - Las Heras
}

SOCIOS_ZONAS = {
    "Tomás Cubillos": "Centro - Las Heras",
    "Sebastián Agüero": "Luján - Godoy Cruz",
    "Franco Navarrete": "Guaymallén - Godoy Cruz"
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

# Banner por defecto incrustado en Base64 para garantizar visualización inmediata
BANNER_DEFAULT_BASE64 = (
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/4QAuRXhpZgAATU0AKgAAAAgAAkAAAwABAAEAAAA"
    "EAAAAAwABAAAAEAAAAAEAAwABAAAAEAAAAAEGAwABAAAAAQAAABgDAgABAAAAAQAAAEgGAwABAAAAAQAAAA"
    "gGAwABAAAAAQAAABwGAwABAAAAAQAAAK6BAgAOAAAALAAAAKIAAwABAAAAAQAAAH8AAwABAAAAAQAAAHIA"
    "AwABAAAAAQAAAH8AAwABAAAAAQAAAHMAAwABAAAAAQAAAAAAAwABAAAAAQAAAAAAAAAAAAAA"
)

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
        res = int(val_clean) if val_clean else defecto
        return max(10, res)
    except Exception:
        return max(10, defecto)

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
# ESTILOS CSS PERSONALIZADOS (ESTÉTICA DE LUJO Y MINIMALISMO)
# ---------------------------------------------------------
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600&display=swap');

    .stApp {
        background-color: #FAF8F5 !important;
        color: #3A2E2B !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
    }

    h1, h2, h3, h4 {
        color: #4A3B32 !important;
        font-weight: 300 !important;
        letter-spacing: 2px !important;
    }

    p, span, label, div {
        color: #3A2E2B;
    }

    [data-testid="stMetricValue"] {
        color: #7A5C47 !important;
        font-size: 1.6rem !important;
        font-weight: 400 !important;
    }

    [data-testid="stMetricLabel"] {
        color: #4A3B32 !important;
        font-size: 0.85rem !important;
    }

    /* Tarjetas tipo Escaparate de Lujo */
    .perfume-card {
        background-color: #FFFFFF !important;
        border: 1px solid #EFECE6 !important;
        padding: 24px;
        border-radius: 16px;
        margin-bottom: 20px;
        box-shadow: 0 10px 30px rgba(74, 59, 50, 0.04);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        text-align: center;
    }
    
    .perfume-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 15px 40px rgba(74, 59, 50, 0.08);
    }

    .perfume-title {
        color: #2C2220 !important;
        font-size: 1.2rem;
        font-weight: 500;
        margin-bottom: 8px;
        letter-spacing: 0.5px;
    }

    .perfume-badge {
        background-color: #F7F5F0 !important;
        color: #6B4F3B !important;
        font-size: 0.7rem;
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 400;
        display: inline-block;
        margin-bottom: 10px;
        letter-spacing: 1px;
        border: 1px solid #E6DEC5;
    }

    .badge-genero {
        background-color: #F7F5F0 !important;
        color: #6B4F3B !important;
        border: 1px solid #E6DEC5;
    }

    .perfume-notes {
        color: #8C7A6B !important;
        font-size: 0.8rem;
        font-style: italic;
        margin-top: 6px;
        margin-bottom: 12px;
    }

    .perfume-price {
        color: #4A3B32 !important;
        font-weight: 600;
        font-size: 1.05rem;
        letter-spacing: 0.5px;
    }

    .stock-badge-green {
        color: #2E7D32 !important;
        font-size: 0.8rem;
        font-weight: 500;
    }

    .stock-badge-red {
        color: #A34838 !important;
        font-size: 0.8rem;
        font-weight: 500;
    }

    .stImage > img {
        max-height: 240px !important;
        width: 100% !important;
        object-fit: cover !important;
        margin: 0 auto !important;
        display: block !important;
        border-radius: 12px !important;
        background-color: #FAF8F5 !important;
        box-shadow: 0 10px 30px rgba(74, 59, 50, 0.08);
    }

    /* Botones refinados y minimalistas */
    .stButton>button {
        background-color: #4A3B32 !important;
        color: #FFFFFF !important;
        font-weight: 400 !important;
        border-radius: 30px !important;
        border: none !important;
        padding: 10px 24px !important;
        transition: all 0.3s ease;
        width: 100%;
        letter-spacing: 1px;
        font-size: 0.85rem;
        box-shadow: 0 4px 15px rgba(74, 59, 50, 0.15);
    }
    
    .stButton>button p, .stButton>button span, .stButton>button div {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }

    .stButton>button:hover {
        background-color: #6B4F3B !important;
        box-shadow: 0 6px 20px rgba(74, 59, 50, 0.25);
    }

    .btn-whatsapp {
        display: block;
        background-color: #25D366;
        color: white !important;
        text-align: center;
        padding: 11px;
        border-radius: 30px;
        font-weight: 500;
        text-decoration: none;
        margin-bottom: 10px;
        font-size: 0.85rem;
        letter-spacing: 0.5px;
        box-shadow: 0 4px 15px rgba(37, 211, 102, 0.2);
        transition: background-color 0.2s ease;
    }
    .btn-whatsapp:hover {
        background-color: #1EBE57;
    }

    section[data-testid="stSidebar"] {
        background-color: #F2EFE9 !important;
        border-right: 1px solid #E6DEC5;
    }

    .stTextInput input, .stNumberInput input, div[data-baseweb="select"] > div, div[data-baseweb="base-input"] {
        background-color: #FFFFFF !important;
        color: #3A2E2B !important;
        -webkit-text-fill-color: #3A2E2B !important;
        border: 1px solid #E6DEC5 !important;
        border-radius: 12px !important;
    }

    div[data-baseweb="tag"] {
        background-color: #EFECE6 !important;
        color: #5C4033 !important;
    }
    div[data-baseweb="tag"] span {
        color: #5C4033 !important;
    }
    
    li[role="option"] div {
        color: #3A2E2B !important;
    }

    .cart-indicator-box {
        background: linear-gradient(135deg, #4A3B32, #2C2220);
        color: #FFFFFF !important;
        padding: 16px 24px;
        border-radius: 14px;
        margin-bottom: 24px;
        box-shadow: 0 10px 30px rgba(44, 34, 32, 0.2);
        letter-spacing: 0.5px;
    }
    .cart-indicator-box * {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }
    </style>
""", unsafe_allow_html=True)

COLOR_BG_PDF = colors.HexColor("#3A2E2B")
COLOR_GOLD_PDF = colors.HexColor("#8C6D53")

# ---------------------------------------------------------
# INICIALIZACIÓN DE TABLAS EN SUPABASE
# ---------------------------------------------------------
def init_db():
    engine = get_engine()
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
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
                imagen_url TEXT DEFAULT '',
                destacado_portada BOOLEAN DEFAULT FALSE
            )
        '''))

        columnas_a_verificar = [
            ("nombre_comercial", "TEXT DEFAULT ''"),
            ("genero", "TEXT DEFAULT 'Unisex'"),
            ("capacidad_ml", "INTEGER DEFAULT 100"),
            ("botellas_100ml_cerradas", "INTEGER DEFAULT 0"),
            ("ml_disponibles_abiertos", "INTEGER DEFAULT 0"),
            ("decants_10ml_preparados", "INTEGER DEFAULT 0"),
            ("costo_usd", "REAL DEFAULT 0.0"),
            ("margen_100ml_custom", "REAL"),
            ("estado", "TEXT DEFAULT 'A pedido'"),
            ("notas_olfativas", "TEXT DEFAULT ''"),
            ("imagen_url", "TEXT DEFAULT ''"),
            ("destacado_portada", "BOOLEAN DEFAULT FALSE")
        ]

        for col_nombre, col_tipo in columnas_a_verificar:
            try:
                conn.execute(text(f'ALTER TABLE stock ADD COLUMN IF NOT EXISTS {col_nombre} {col_tipo}'))
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
                costo_envase_decant_ars REAL,
                banner_portada_url TEXT DEFAULT ''
            )
        '''))
        
        try:
            conn.execute(text('ALTER TABLE config ADD COLUMN IF NOT EXISTS banner_portada_url TEXT DEFAULT \'\''))
        except Exception:
            pass

        conn.execute(text('''
            INSERT INTO config (id, cotizacion_dolar, margen_100ml, margen_decant, costo_envase_decant_ars, banner_portada_url)
            VALUES (1, 1200.0, 30.0, 100.0, 800.0, :banner_def)
            ON CONFLICT (id) DO NOTHING
        '''), {"banner_def": BANNER_DEFAULT_BASE64})

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
                monto_ars REAL,
                socio_registra TEXT
            )
        '''))

        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS ordenes_compra (
                id SERIAL PRIMARY KEY,
                fecha TEXT,
                nombre TEXT,
                capacidad_ml INTEGER,
                cantidad INTEGER,
                costo_usd REAL,
                estado_inventario TEXT,
                detalle_reserva TEXT,
                socio_agrega TEXT
            )
        '''))

init_db()

# ---------------------------------------------------------
# CARGA DE DATOS DE LA BASE DE DATOS
# ---------------------------------------------------------
def cargar_datos_stock():
    df = fetch_df("SELECT * FROM stock")
    if not df.empty:
        if "capacidad_ml" in df.columns:
            df["capacidad_ml"] = df["capacidad_ml"].apply(lambda v: limpiar_int_ml(v, 100))
        if "genero" in df.columns:
            df["genero"] = df["genero"].fillna("Unisex").replace("", "Unisex")
        if "destacado_portada" in df.columns:
            df["destacado_portada"] = df["destacado_portada"].fillna(False).astype(bool)
        else:
            df["destacado_portada"] = False
        
        if "nombre_comercial" in df.columns:
            df["nombre_catalogo"] = df.apply(
                lambda r: r["nombre_comercial"] if pd.notnull(r["nombre_comercial"]) and str(r["nombre_comercial"]).strip() != "" else r["nombre"], axis=1
            )
        else:
            df["nombre_catalogo"] = df["nombre"]
    else:
        df = pd.DataFrame(columns=["id", "nombre", "nombre_comercial", "nombre_catalogo", "tipo", "genero", "capacidad_ml", "botellas_100ml_cerradas", "ml_disponibles_abiertos", "decants_10ml_preparados", "costo_usd", "estado", "destacado_portada"])
    return df

def cargar_historial():
    df = fetch_df("SELECT * FROM historial ORDER BY id DESC")
    if not df.empty and "fecha" in df.columns:
        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors='coerce')
    return df

def cargar_egresos():
    df = fetch_df("SELECT * FROM egresos ORDER BY id DESC")
    if not df.empty and "fecha" in df.columns:
        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors='coerce')
    return df

def cargar_seguimiento():
    return fetch_df("SELECT * FROM clientes_seguimiento ORDER BY fecha_recordatorio ASC")

def cargar_ordenes_compra():
    df = fetch_df("SELECT * FROM ordenes_compra ORDER BY id ASC")
    if not df.empty and "capacidad_ml" in df.columns:
        df["capacidad_ml"] = df["capacidad_ml"].apply(lambda v: limpiar_int_ml(v, 100))
    return df

def cargar_config():
    df = fetch_df("SELECT cotizacion_dolar, margen_100ml, margen_decant, costo_envase_decant_ars, banner_portada_url FROM config WHERE id = 1")
    if not df.empty:
        r = df.iloc[0]
        banner_url = str(r.get("banner_portada_url", "")) if pd.notnull(r.get("banner_portada_url")) else ""
        if banner_url.strip() == "":
            banner_url = BANNER_DEFAULT_BASE64
        return float(r["cotizacion_dolar"]), float(r["margen_100ml"]), float(r["margen_decant"]), float(r["costo_envase_decant_ars"]), banner_url
    return 1200.0, 30.0, 100.0, 800.0, BANNER_DEFAULT_BASE64

def guardar_config(dolar, m100, mdec, envase, banner_url=""):
    execute_query('''
        UPDATE config 
        SET cotizacion_dolar = :dolar, margen_100ml = :m100, margen_decant = :mdec, costo_envase_decant_ars = :envase, banner_portada_url = :banner
        WHERE id = 1
    ''', {"dolar": dolar, "m100": m100, "mdec": mdec, "envase": envase, "banner": banner_url})

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
# GENERACIÓN DE PDFS ROBUSTOS
# ---------------------------------------------------------
def generar_pdf_catalogo(df_cat):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor("#222222"))
    cell_bold = ParagraphStyle('CellBold', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor("#222222"), fontName="Helvetica-Bold")
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=COLOR_GOLD_PDF, fontName="Helvetica-Bold", alignment=1)

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=22, leading=26, textColor=COLOR_BG_PDF, alignment=1)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=11, leading=14, textColor=colors.HexColor("#777777"), alignment=1)
    
    story.append(Paragraph("STORIA PARFUMS", title_style))
    story.append(Paragraph("CADA FRAGANCIA CUENTA UNA HISTORIA", subtitle_style))
    story.append(Spacer(1, 15))
    
    headers = ["Perfume / Marca", "Género", "Presentación", "Disponibilidad", "Frasco Cerrado", "Decant 10 ml"]
    data = [[Paragraph(h, header_style) for h in headers]]
    
    for _, row in df_cat.iterrows():
        cap = limpiar_int_ml(row.get("capacidad_ml", 100), 100)
        gen = row.get("genero", "Unisex")
        tipo_str = f" ({row['tipo']})" if row.get("tipo") else ""
        nombre_vis = row.get("nombre_catalogo", row["nombre"])
        
        data.append([
            Paragraph(f"{nombre_vis}{tipo_str}", cell_bold),
            Paragraph(gen, cell_style),
            Paragraph(f"{cap} ml", cell_style),
            Paragraph(row["estado"], cell_style),
            Paragraph(fmt_ars(row['precio_100ml']), cell_style),
            Paragraph(fmt_ars(row['precio_decant']), cell_style)
        ])
        
    t = Table(data, colWidths=[170, 55, 65, 80, 90, 90])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_PDF),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_presupuesto(cliente, celular, socio_vendedor, items, subtotal, descuento, total):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    story = []
    styles = getSampleStyleSheet()
    
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor("#222222"))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=COLOR_GOLD_PDF, fontName="Helvetica-Bold", alignment=1)

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=22, leading=26, textColor=COLOR_BG_PDF)
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor("#555555"))
    
    story.append(Paragraph("STORIA PARFUMS", title_style))
    story.append(Paragraph("CADA FRAGANCIA CUENTA UNA HISTORIA", ParagraphStyle('Sub', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor("#777777"))))
    story.append(Spacer(1, 5))
    story.append(Paragraph(f"<b>Presupuesto para:</b> {cliente}", meta_style))
    if celular:
        story.append(Paragraph(f"<b>Celular:</b> {celular}", meta_style))
    story.append(Paragraph(f"<b>Atendido por:</b> {socio_vendedor}", meta_style))
    story.append(Paragraph(f"<b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", meta_style))
    story.append(Spacer(1, 15))
    
    headers = ["Producto", "Presentación", "Cant.", "Precio Unitario", "Subtotal"]
    data = [[Paragraph(h, header_style) for h in headers]]
    
    for item in items:
        data.append([
            Paragraph(item["nombre"], cell_style),
            Paragraph(item["presentacion"], cell_style),
            Paragraph(str(item["cantidad"]), cell_style),
            Paragraph(fmt_ars(item['precio_unitario']), cell_style),
            Paragraph(fmt_ars(item['subtotal']), cell_style)
        ])
        
    t = Table(data, colWidths=[220, 90, 40, 100, 90])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_PDF),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))
    
    totales_data = [
        [Paragraph("Subtotal:", cell_style), Paragraph(fmt_ars(subtotal), cell_style)],
        [Paragraph("Descuento Aplicado:", cell_style), Paragraph(f"-{fmt_ars(descuento)}", cell_style)],
        [Paragraph("<b>TOTAL FINAL:</b>", cell_style), Paragraph(f"<b>{fmt_ars(total)}</b>", cell_style)]
    ]
    t_tot = Table(totales_data, colWidths=[380, 160])
    t_tot.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_tot)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_reporte_contable(socio_filtro, periodo_str, df_ingresos, df_egresos, tot_ing, tot_eg, gan_neta):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor("#222222"))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=COLOR_GOLD_PDF, fontName="Helvetica-Bold", alignment=1)
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=COLOR_BG_PDF)
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor("#555555"))

    story.append(Paragraph("STORIA PARFUMS - REPORTE CONTABLE", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Socio Vendedor:</b> {socio_filtro}", meta_style))
    story.append(Paragraph(f"<b>Período Consultado:</b> {periodo_str}", meta_style))
    story.append(Paragraph(f"<b>Fecha de Emisión:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", meta_style))
    story.append(Spacer(1, 12))

    resumen_data = [
        [Paragraph("🟢 Total Ingresos", header_style), Paragraph("🔴 Total Gastos/Egresos", header_style), Paragraph("🏆 Ganancia Neta", header_style)],
        [Paragraph(fmt_ars(tot_ing), cell_style), Paragraph(fmt_ars(tot_eg), cell_style), Paragraph(fmt_ars(gan_neta), cell_style)]
    ]
    t_res = Table(resumen_data, colWidths=[180, 180, 192])
    t_res.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_PDF),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_res)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>Detalle de Ingresos (Ventas)</b>", meta_style))
    story.append(Spacer(1, 4))
    
    headers_ing = ["Fecha", "Perfume / Detalle", "Socio", "Tipo Movimiento", "Monto"]
    data_ing = [[Paragraph(h, header_style) for h in headers_ing]]
    
    if not df_ingresos.empty:
        for _, r in df_ingresos.iterrows():
            data_ing.append([
                Paragraph(str(r.get('fecha', '')), cell_style),
                Paragraph(str(r.get('perfume', '')), cell_style),
                Paragraph(str(r.get('socio', '')), cell_style),
                Paragraph(str(r.get('tipo_movimiento', '')), cell_style),
                Paragraph(fmt_ars(r.get('monto_ingreso_ars', 0)), cell_style)
            ])
    else:
        data_ing.append([Paragraph("Sin datos", cell_style)] * 5)

    t_ing = Table(data_ing, colWidths=[90, 160, 90, 112, 100])
    t_ing.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_PDF),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_ing)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>Detalle de Gastos y Egresos</b>", meta_style))
    story.append(Spacer(1, 4))
    
    headers_eg = ["Fecha", "Categoría", "Descripción", "Registrado Por", "Monto"]
    data_eg = [[Paragraph(h, header_style) for h in headers_eg]]
    
    if not df_egresos.empty:
        for _, r in df_egresos.iterrows():
            data_eg.append([
                Paragraph(str(r.get('fecha', '')), cell_style),
                Paragraph(str(r.get('categoria', '')), cell_style),
                Paragraph(str(r.get('descripcion', '')), cell_style),
                Paragraph(str(r.get('socio_registra', '')), cell_style),
                Paragraph(fmt_ars(r.get('monto_ars', 0)), cell_style)
            ])
    else:
        data_eg.append([Paragraph("Sin datos", cell_style)] * 5)

    t_eg = Table(data_eg, colWidths=[90, 110, 152, 100, 100])
    t_eg.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_PDF),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_eg)

    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_historial_ventas(df_hist_pdf, socio_filtro):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=colors.HexColor("#222222"))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8, leading=10, textColor=COLOR_GOLD_PDF, fontName="Helvetica-Bold", alignment=1)
    
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=COLOR_BG_PDF)
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor("#555555"))

    story.append(Paragraph("STORIA PARFUMS - HISTORIAL DE VENTAS", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"<b>Filtro Socio:</b> {socio_filtro}", meta_style))
    story.append(Paragraph(f"<b>Fecha de Emisión:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", meta_style))
    story.append(Spacer(1, 12))

    headers = ["Fecha", "Perfume", "Presentación", "Cant.", "Socio", "Detalle / Operación", "Monto"]
    data = [[Paragraph(h, header_style) for h in headers]]
    
    tot_monto = 0.0
    if not df_hist_pdf.empty:
        for _, r in df_hist_pdf.iterrows():
            m_val = float(r.get('monto_ingreso_ars', 0.0))
            tot_monto += m_val
            data.append([
                Paragraph(str(r.get('fecha', '')), cell_style),
                Paragraph(str(r.get('perfume', '')), cell_style),
                Paragraph(str(r.get('presentacion', '')), cell_style),
                Paragraph(str(r.get('cantidad', 1)), cell_style),
                Paragraph(str(r.get('socio', '')), cell_style),
                Paragraph(str(r.get('tipo_movimiento', '')), cell_style),
                Paragraph(fmt_ars(m_val), cell_style)
            ])
            
    t = Table(data, colWidths=[80, 110, 80, 32, 80, 90, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_PDF),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))
    
    story.append(Paragraph(f"<b>Total Acumulado en este reporte:</b> {fmt_ars(tot_monto)}", meta_style))

    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_orden_compra(socio_emite, df_items, total_usd, total_ars, dolar_prov):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    story = []
    styles = getSampleStyleSheet()
    
    cell_style = ParagraphStyle('CellStyle', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=colors.HexColor("#222222"))
    header_style = ParagraphStyle('HeaderStyle', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=COLOR_GOLD_PDF, fontName="Helvetica-Bold", alignment=1)

    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, leading=24, textColor=COLOR_BG_PDF)
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor("#555555"))
    
    story.append(Paragraph("STORIA PARFUMS - ORDEN DE COMPRA", title_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph(f"<b>Solicitado por Socio:</b> {socio_emite}", meta_style))
    story.append(Paragraph(f"<b>Fecha de Solicitud:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", meta_style))
    story.append(Paragraph(f"<b>Cotización Dólar Proveedor Aplicada:</b> {fmt_ars(dolar_prov)}", meta_style))
    story.append(Spacer(1, 15))
    
    headers = ["Perfume / Producto", "Vol (ml)", "Estado / Prioridad", "Cant.", "Costo USD", "Subtotal USD"]
    data = [[Paragraph(h, header_style) for h in headers]]
    
    for _, row in df_items.iterrows():
        est_txt = str(row['estado_inventario'])

        data.append([
            Paragraph(row["nombre"], cell_style),
            Paragraph(f"{limpiar_int_ml(row['capacidad_ml'], 100)} ml", cell_style),
            Paragraph(est_txt, cell_style),
            Paragraph(str(row["cantidad"]), cell_style),
            Paragraph(f"${row['costo_usd']:.2f}", cell_style),
            Paragraph(f"${row['subtotal_usd']:.2f}", cell_style)
        ])
        
    t = Table(data, colWidths=[190, 50, 110, 40, 70, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_PDF),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))
    
    totales_data = [
        [Paragraph("Total Estimado USD:", cell_style), Paragraph(f"${total_usd:.2f} USD", cell_style)],
        [Paragraph("Total Estimado ARS (Dólar Prov.):", cell_style), Paragraph(fmt_ars(total_ars), cell_style)]
    ]
    t_tot = Table(totales_data, colWidths=[380, 160])
    t_tot.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_tot)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# INTERFAZ Y CONTROL DE SESIÓN
# ---------------------------------------------------------
if "socio_autenticado" not in st.session_state:
    st.session_state.socio_autenticado = None

if "carrito_cliente" not in st.session_state:
    st.session_state.carrito_cliente = []

# Encabezado minimalista y elegante
st.markdown("<h1 style='text-align: center; margin-bottom: 0px; font-weight: 300; letter-spacing: 6px;'>S T O R I A</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #8C6D53; letter-spacing: 4px; font-size: 0.75rem; text-transform: uppercase;'>P A R F U M S</p>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #7A5C47; font-style: italic; font-size: 0.85rem; margin-top: -8px; letter-spacing: 1px;'>Cada fragancia cuenta una historia</p>", unsafe_allow_html=True)
st.markdown("---")

dolar_hoy, margen_100_gen, margen_dec_gen, costo_envase, banner_portada_url = cargar_config()

modo_acceso = st.sidebar.radio(
    "Acceso al Sistema:",
    ["📖 Catálogo Clientes (Libre)", "🔐 Panel Administrador (Socios)"]
)

# ---------------------------------------------------------
# MODO 1: CATÁLOGO PÚBLICO CLIENTE (ACCESO LIBRE)
# ---------------------------------------------------------
if modo_acceso == "📖 Catálogo Clientes (Libre)":
    
    # --- BARRA LATERAL IZQUIERDA (CARRITO) ---
    with st.sidebar:
        st.markdown("---")
        st.markdown("### 🛒 Tu Carrito")
        
        if st.session_state.carrito_cliente:
            total_monto_carrito = sum(i['precio'] * i['cantidad'] for i in st.session_state.carrito_cliente)
            
            for idx_c, item_c in enumerate(st.session_state.carrito_cliente):
                subtot_item = item_c['precio'] * item_c['cantidad']
                st.markdown(f"""
                <div style="background-color: #FFFFFF; padding: 10px; border-radius: 8px; margin-bottom: 8px; border: 1px solid #E6DEC5;">
                    <b>{item_c['nombre']}</b><br>
                    <small>{item_c['presentacion']} (x{item_c['cantidad']})</small><br>
                    <span style="color: #6B4F3B; font-weight: 600;">{fmt_ars(subtot_item)}</span>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("❌ Quitar", key=f"btn_quitar_cart_{idx_c}"):
                    st.session_state.carrito_cliente.pop(idx_c)
                    st.rerun()

            st.markdown(f"**Total Carrito: {fmt_ars(total_monto_carrito)}**")
            st.markdown("---")
            st.markdown("💬 **Enviar Pedido por WhatsApp:**")

            mensaje_whatsapp_partes = [f"- {i['nombre']} ({i['presentacion']}) x{i['cantidad']} : {fmt_ars(i['precio'] * i['cantidad'])}" for i in st.session_state.carrito_cliente]
            detalles_pedido_str = "Hola! Armé mi pedido en el escaparate digital de STORIA PARFUMS:\n" + "\n".join(mensaje_whatsapp_partes) + f"\n\n*TOTAL APROXIMADO: {fmt_ars(total_monto_carrito)}*\n¿Me confirman disponibilidad y seña?"
            msg_encoded_cart = urllib.parse.quote(detalles_pedido_str)

            st.markdown(f'<a href="https://wa.me/{SOCIOS_WHATSAPP["Tomás Cubillos"]}?text={msg_encoded_cart}" target="_blank" class="btn-whatsapp">💬 Tomás ({SOCIOS_ZONAS["Tomás Cubillos"]})</a>', unsafe_allow_html=True)
            st.markdown(f'<a href="https://wa.me/{SOCIOS_WHATSAPP["Sebastián Agüero"]}?text={msg_encoded_cart}" target="_blank" class="btn-whatsapp">💬 Sebastián ({SOCIOS_ZONAS["Sebastián Agüero"]})</a>', unsafe_allow_html=True)
            st.markdown(f'<a href="https://wa.me/{SOCIOS_WHATSAPP["Franco Navarrete"]}?text={msg_encoded_cart}" target="_blank" class="btn-whatsapp">💬 Franco ({SOCIOS_ZONAS["Franco Navarrete"]})</a>', unsafe_allow_html=True)

            if st.button("🗑️ Vaciar Carrito"):
                st.session_state.carrito_cliente = []
                st.rerun()
        else:
            st.info("Tu carrito está vacío. Explora el escaparate.")

    # --- BANNER DISCRETO Y ELEGANTE SI HAY PRODUCTOS ---
    total_cant_items = sum(i['cantidad'] for i in st.session_state.carrito_cliente)
    if total_cant_items > 0:
        total_monto_carrito = sum(i['precio'] * i['cantidad'] for i in st.session_state.carrito_cliente)
        
        st.markdown(f"""
            <div class="cart-indicator-box">
                <div>
                    <span style="font-size: 1.05rem; font-weight: 500; color: #FFFFFF !important;">✨ Tienes {total_cant_items} fragancia(s) seleccionada(s) ({fmt_ars(total_monto_carrito)})</span><br>
                    <small style="color: #EFECE6 !important;">Abre el menú lateral izquierdo para ver el detalle y realizar tu pedido vía WhatsApp.</small>
                </div>
            </div>
        """, unsafe_allow_html=True)

    # --- RENDERIZADO DEL BANNER DE PORTADA (USANDO st.image NATIVO) ---
    if banner_portada_url and banner_portada_url.strip() != "":
        try:
            if banner_portada_url.startswith("data:image"):
                header, encoded = banner_portada_url.split(",", 1)
                img_bytes = base64.b64decode(encoded)
                st.image(img_bytes, use_container_width=True)
            else:
                st.image(banner_portada_url, use_container_width=True)
        except Exception:
            pass

    st.markdown("---")

    # Carga de catálogo general para el listado de clientes (EXCLUSIVAMENTE EN STOCK)
    df_cat_base_gen = cargar_datos_stock()
    if not df_cat_base_gen.empty:
        df_cat_base_gen["estado"] = df_cat_base_gen["estado"].replace("Disponible en Proveedor", "A pedido")
        
        # EXCLUSIÓN ESTRICTA: Solo mostrar y filtrar perfumes que están físicamente en stock
        df_cat_base_gen = df_cat_base_gen[df_cat_base_gen["estado"].astype(str).str.strip() == "En Stock"]
        
        df_cat_base_gen["costo_usd"] = pd.to_numeric(df_cat_base_gen["costo_usd"], errors='coerce').fillna(0.0)
        df_cat_base_gen["capacidad_ml"] = df_cat_base_gen["capacidad_ml"].apply(lambda v: limpiar_int_ml(v, 100))
        df_cat_base_gen["decants_10ml_preparados"] = pd.to_numeric(df_cat_base_gen["decants_10ml_preparados"], errors='coerce').fillna(0).astype(int)
        df_cat_base_gen["botellas_100ml_cerradas"] = pd.to_numeric(df_cat_base_gen["botellas_100ml_cerradas"], errors='coerce').fillna(0).astype(int)
        df_cat_base_gen["ml_disponibles_abiertos"] = pd.to_numeric(df_cat_base_gen["ml_disponibles_abiertos"], errors='coerce').fillna(0).astype(int)

        df_cat_base_gen["margen_100ml_custom"] = pd.to_numeric(df_cat_base_gen["margen_100ml_custom"], errors='coerce')
        df_cat_base_gen["margen_aplicado"] = df_cat_base_gen["margen_100ml_custom"].fillna(margen_100_gen)
        
        df_cat_base_gen["costo_ars"] = df_cat_base_gen["costo_usd"] * dolar_hoy
        df_cat_base_gen["precio_100ml_raw"] = df_cat_base_gen["costo_ars"] * (1 + (df_cat_base_gen["margen_aplicado"] / 100))
        df_cat_base_gen["precio_100ml"] = df_cat_base_gen["precio_100ml_raw"].apply(lambda x: redondear_monto(x, 100))
        
        df_cat_base_gen["costo_liquido_10ml"] = df_cat_base_gen.apply(
            lambda r: (r["costo_ars"] / r["capacidad_ml"] * 10) if r["capacidad_ml"] > 0 else (r["costo_ars"] * 0.10), axis=1
        )
        df_cat_base_gen["precio_decant_raw"] = (df_cat_base_gen["costo_liquido_10ml"] + costo_envase) * (1 + (margen_dec_gen / 100))
        df_cat_base_gen["precio_decant"] = df_cat_base_gen["precio_decant_raw"].apply(lambda x: redondear_monto(x, 100))

        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            busq_cli = st.text_input("🔍 Buscar fragancia...", placeholder="Ej. Khamrah, Club de Nuit...")
        with col_f2:
            filtro_genero = st.selectbox("👤 Género:", ["Todos los géneros", "Hombre", "Mujer", "Unisex"])
        with col_f3:
            marcas_disponibles = ["Todas las marcas"] + sorted(list(set(df_cat_base_gen["tipo"].dropna().unique())))
            filtro_marca = st.selectbox("🏷️ Marca / Casa:", marcas_disponibles)
        with col_f4:
            orden_filtro_cli = st.selectbox(
                "🔀 Ordenar:",
                [
                    "Recién Ingresados",
                    "Precio: Menor a Mayor",
                    "Precio: Mayor a Menor"
                ],
                key="orden_filtro_cli"
            )

        if busq_cli:
            df_cat_base_gen = df_cat_base_gen[df_cat_base_gen["nombre_catalogo"].astype(str).str.contains(busq_cli, case=False, na=False)]
        if filtro_genero != "Todos los géneros":
            df_cat_base_gen = df_cat_base_gen[df_cat_base_gen["genero"] == filtro_genero]
        if filtro_marca != "Todas las marcas":
            df_cat_base_gen = df_cat_base_gen[df_cat_base_gen["tipo"] == filtro_marca]

        # Aplicar ordenamiento estricto sobre el stock disponible
        if orden_filtro_cli == "Precio: Menor a Mayor":
            df_cat_base_gen = df_cat_base_gen.sort_values(by="precio_100ml", ascending=True).reset_index(drop=True)
        elif orden_filtro_cli == "Precio: Mayor a Menor":
            df_cat_base_gen = df_cat_base_gen.sort_values(by="precio_100ml", ascending=False).reset_index(drop=True)
        else:
            df_cat_base_gen = df_cat_base_gen.sort_values(by="id", ascending=False).reset_index(drop=True)

        st.markdown("<br>", unsafe_allow_html=True)

        for _, r in df_cat_base_gen.iterrows():
            notas_html = f'<div class="perfume-notes">🌸 {r["notas_olfativas"]}</div>' if pd.notnull(r.get("notas_olfativas")) and str(r.get("notas_olfativas")).strip() != "" else ""
            tipo_html = f' • <span style="color:#8C6D53;">{r["tipo"]}</span>' if pd.notnull(r.get("tipo")) and str(r.get("tipo")).strip() != "" else ""

            gen_val = r.get("genero", "Unisex")
            icon_gen = "♂️" if gen_val == "Hombre" else ("♀️" if gen_val == "Mujer" else "🚻")
            genero_badge = f'<span class="perfume-badge badge-genero">{icon_gen} {gen_val}</span>'

            txt_sen = r['estado']
            nombre_vis = r["nombre_catalogo"]
            cap_ml = limpiar_int_ml(r.get("capacidad_ml", 100), 100)

            p_100ml_val = r['precio_100ml']
            p_decant_val = r['precio_decant']
            p_100ml_str = fmt_ars(p_100ml_val)
            p_decant_str = fmt_ars(p_decant_val)
            cnt_decants = r.get("decants_10ml_preparados", 0)
            cnt_ml_ab = r.get("ml_disponibles_abiertos", 0)

            if cnt_decants > 0 or cnt_ml_ab >= 10:
                stock_dec_html = '<span class="stock-badge-green"> (Disponible)</span>'
            else:
                stock_dec_html = '<span class="stock-badge-red"> (A pedido)</span>'

            precios_card_html = f"""
            <div style="margin-top: 10px;">
                <div>Frasco {cap_ml}ml: <span class="perfume-price">{p_100ml_str}</span></div>
                <div>Decant 10ml: <span class="perfume-price">{p_decant_str}</span>{stock_dec_html}</div>
            </div>
            """

            col_card_1, col_card_2 = st.columns([1, 3])
            with col_card_1:
                if pd.notnull(r.get("imagen_url")) and str(r.get("imagen_url")).strip().startswith("http"):
                    try:
                        st.image(r["imagen_url"], use_container_width=True)
                    except Exception:
                        st.markdown("<h2 style='text-align: center; color: #7A5C47;'>✨</h2>", unsafe_allow_html=True)
                else:
                    st.markdown("<h2 style='text-align: center; color: #7A5C47;'>✨</h2>", unsafe_allow_html=True)
            with col_card_2:
                card_html = f'<div class="perfume-card"><div class="perfume-title">{nombre_vis}</div><span class="perfume-badge">{txt_sen}</span>{genero_badge}{tipo_html}{notas_html}{precios_card_html}</div>'
                st.markdown(card_html, unsafe_allow_html=True)

                col_btn_c1, col_btn_c2 = st.columns(2)
                with col_btn_c1:
                    if st.button(f"Añadir Frasco {cap_ml}ml", key=f"add_frasco_{r['id']}"):
                        st.session_state.carrito_cliente.append({
                            "nombre": nombre_vis,
                            "presentacion": f"Frasco Cerrado ({cap_ml}ml)",
                            "cantidad": 1,
                            "precio": p_100ml_val
                        })
                        st.success(f"¡{nombre_vis} ({cap_ml}ml) agregado!")
                        st.rerun()
                with col_btn_c2:
                    if st.button(f"Añadir Decant 10ml", key=f"add_decant_{r['id']}"):
                        st.session_state.carrito_cliente.append({
                            "nombre": nombre_vis,
                            "presentacion": "Decant 10ml",
                            "cantidad": 1,
                            "precio": p_decant_val
                        })
                        st.success(f"¡{nombre_vis} (Decant 10ml) agregado!")
                        st.rerun()

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
                "🖼️ Banner de Portada",
                "✨ Destacados Portada",
                "📋 Crear Presupuesto",
                "🛒 Registrar Venta", 
                "💬 Seguimiento & Clientes",
                "📊 Contabilidad & Gastos",
                "📦 Orden de Compra Proveedor",
                "➕ Agregar Perfume", 
                "📄 Cargar PDF Proveedor",
                "✏️ Editar / Eliminar",
                "📜 Historial",
                "💾 Copias de Seguridad"
            ]
        )

        st.sidebar.caption(f"💵 Dólar Sistema: **{fmt_ars(dolar_hoy)}**")

        # --- SECCIÓN: STOCK Y PRECIOS ---
        if seccion_admin == "📦 Stock & Precios":
            st.header("📦 Inventario Global")
            
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.metric("Cotización Dólar Sistema", fmt_ars(dolar_hoy))
            with col_p2:
                st.metric("Envase Decant", fmt_ars(costo_envase))

            df = cargar_datos_stock()

            if not df.empty:
                df["costo_usd"] = pd.to_numeric(df["costo_usd"], errors='coerce').fillna(0.0)
                df["capacidad_ml"] = df["capacidad_ml"].apply(lambda v: limpiar_int_ml(v, 100))
                df["genero"] = df["genero"].fillna("Unisex").replace("", "Unisex")
                df["estado"] = df["estado"].replace("Disponible en Proveedor", "A pedido").fillna("A pedido")
                
                df["margen_100ml_custom"] = pd.to_numeric(df["margen_100ml_custom"], errors='coerce')
                df["margen_aplicado"] = df["margen_100ml_custom"].fillna(margen_100_gen)
                
                df["costo_100ml_ars"] = df["costo_usd"] * dolar_hoy
                df["precio_venta_100ml_raw"] = df["costo_100ml_ars"] * (1 + (df["margen_aplicado"] / 100))
                df["precio_venta_100ml_ars"] = df["precio_venta_100ml_raw"].apply(lambda x: redondear_monto(x, 100))
                
                df["costo_liquido_10ml"] = df.apply(
                    lambda r: (r["costo_100ml_ars"] / r["capacidad_ml"] * 10) if r["capacidad_ml"] > 0 else (r["costo_100ml_ars"] * 0.10), axis=1
                )
                df["precio_venta_decant_raw"] = (df["costo_liquido_10ml"] + costo_envase) * (1 + (margen_dec_gen / 100))
                df["precio_venta_decant_10ml_ars"] = df["precio_venta_decant_raw"].apply(lambda x: redondear_monto(x, 100))

                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                with col_s1:
                    busqueda = st.text_input("🔍 Buscar perfume:", placeholder="Ej. Khamrah, Club de Nuit...")
                with col_s2:
                    filtro_gen_adm = st.selectbox("👤 Género:", ["Todos", "Hombre", "Mujer", "Unisex"])
                with col_s3:
                    filtro_estado = st.multiselect("Estado:", df["estado"].unique())
                with col_s4:
                    marcas_adm = ["Todas"] + sorted(list(set(df["tipo"].dropna().unique())))
                    filtro_marca_adm = st.selectbox("🏷️ Marca:", marcas_adm)

                orden_filtro = st.selectbox(
                    "🔀 Filtrar y Ordenar Lista:",
                    [
                        "Predeterminado (Destacados y Stock primero)",
                        "Solo en Stock",
                        "Precio: Menor a Mayor",
                        "Precio: Mayor a Menor",
                        "Recién Ingresados"
                    ]
                )

                if busqueda:
                    df = df[df["nombre_catalogo"].astype(str).str.contains(busqueda, case=False, na=False)]
                if filtro_gen_adm != "Todos":
                    df = df[df["genero"] == filtro_gen_adm]
                if filtro_estado:
                    df = df[df["estado"].isin(filtro_estado)]
                if filtro_marca_adm != "Todas":
                    df = df[df["tipo"] == filtro_marca_adm]

                if orden_filtro == "Solo en Stock":
                    df = df[df["estado"] == "En Stock"]
                    df = df.sort_values(by="id", ascending=False).reset_index(drop=True)
                elif orden_filtro == "Precio: Menor a Mayor":
                    df = df.sort_values(by="precio_venta_100ml_ars", ascending=True).reset_index(drop=True)
                elif orden_filtro == "Precio: Mayor a Menor":
                    df = df.sort_values(by="precio_venta_100ml_ars", ascending=False).reset_index(drop=True)
                elif orden_filtro == "Recién Ingresados":
                    df = df.sort_values(by="id", ascending=False).reset_index(drop=True)
                else:
                    df["orden_portada_val"] = df["destacado_portada"].apply(lambda x: 0 if x == True else 1)
                    df["orden_stock_val"] = df["estado"].apply(lambda x: 0 if x == 'En Stock' else 1)
                    df = df.sort_values(by=["orden_portada_val", "orden_stock_val", "id"], ascending=[True, True, False]).reset_index(drop=True)

                modo_vista = st.radio("Modo de Vista:", ["📱 Tarjetas (Ideal Celular)", "📊 Tabla Completa"], horizontal=True)

                if modo_vista == "📱 Tarjetas (Ideal Celular)":
                    for _, r in df.iterrows():
                        notas_str = f"<div><b>Notas:</b> {r['notas_olfativas']}</div>" if pd.notnull(r.get("notas_olfativas")) and str(r.get("notas_olfativas")).strip() != "" else ""
                        tipo_str = f" ({r['tipo']})" if pd.notnull(r.get("tipo")) and str(r.get("tipo")).strip() != "" else ""
                        gen_str = f" • <span style='color:#5C4033;'>[{r['genero']}]</span>"
                        dest_badge_str = " ⭐ <b>[Destacado Portada]</b>" if r.get("destacado_portada") else ""
                        p_100_card = fmt_ars(r['precio_venta_100ml_ars'])
                        p_dec_card = fmt_ars(r['precio_venta_decant_10ml_ars'])
                        cap = limpiar_int_ml(r.get("capacidad_ml", 100), 100)
                        nombre_vis = r["nombre_catalogo"]

                        card_admin_html = f'<div class="perfume-card"><div class="perfume-title">{nombre_vis}</div><span class="perfume-badge">{r["estado"]}</span>{dest_badge_str}{tipo_str}{gen_str}{notas_str}<div style="margin-top: 8px;"><div><b>Frasco ({cap}ml):</b> <span class="perfume-price">{p_100_card}</span> <small>({r["botellas_100ml_cerradas"]} un)</small></div><div><b>Decants 10ml Listos:</b> <span class="perfume-price">{p_dec_card}</span> <small>({r["decants_10ml_preparados"]} un en stock)</small></div><div style="font-size: 0.8rem; color: #7A5C47; margin-top: 4px;">Costo USD: ${r["costo_usd"]:.2f}</div></div></div>'
                        st.markdown(card_admin_html, unsafe_allow_html=True)
                else:
                    df_display = df.copy()
                    df_display["precio_100ml_formatted"] = df_display["precio_venta_100ml_ars"].apply(fmt_ars)
                    df_display["precio_10ml_formatted"] = df_display["precio_venta_decant_10ml_ars"].apply(fmt_ars)
                    
                    df_display = df_display.rename(columns={
                        "id": "ID", "nombre_catalogo": "Perfume", "genero": "Género", "tipo": "Marca / Categoría", "capacidad_ml": "Vol (ml)", "estado": "Estado",
                        "botellas_100ml_cerradas": "Frascos", "decants_10ml_preparados": "Decants Stock", "costo_usd": "USD",
                        "destacado_portada": "Destacado", "precio_100ml_formatted": "Precio Frasco", "precio_10ml_formatted": "Precio 10ml"
                    })
                    st.dataframe(df_display[["ID", "Perfume", "Género", "Marca / Categoría", "Vol (ml)", "Estado", "Destacado", "Frascos", "Decants Stock", "Precio Frasco", "Precio 10ml"]], use_container_width=True)
            else:
                st.info("No hay perfumes registrados.")

        # --- SECCIÓN: BANNER DE PORTADA ---
        elif seccion_admin == "🖼️ Banner de Portada":
            st.header("🖼️ Imagen Fija de Portada (Banner)")
            st.info("💡 Sube una imagen desde tu dispositivo para fijarla como banner principal en la portada del catálogo.")

            with st.form("form_banner_portada"):
                banner_file = st.file_uploader("Subir
