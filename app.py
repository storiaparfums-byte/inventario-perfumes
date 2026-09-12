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

# Limpieza automática al iniciar por si quedaron registros con "NUEVOO"
def limpiar_nombres_automatico():
    try:
        engine = get_engine()
        with engine.begin() as conn:
            # Quitamos palabras basura de nombre_comercial si estaban vacías
            conn.execute(text('''
                UPDATE stock 
                SET nombre_comercial = REGEXP_REPLACE(REGEXP_REPLACE(nombre, '(?i)\\bnuevoo?\\b', '', 'g'), '\\s+', ' ', 'g')
                WHERE nombre_comercial IS NULL OR nombre_comercial = ''
            '''))
    except Exception:
        pass

limpiar_nombres_automatico()

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
        if "nombre_comercial" in df.columns:
            df["nombre_catalogo"] = df.apply(
                lambda r: r["nombre_comercial"] if pd.notnull(r["nombre_comercial"]) and str(r["nombre_comercial"]).strip() != "" else r["nombre"], axis=1
            )
        else:
            df["nombre_catalogo"] = df["nombre"]
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
    df = fetch_df("SELECT cotizacion_dolar, margen_100ml, margen_decant, costo_envase_decant_ars FROM config WHERE id = 1")
    if not df.empty:
        r = df.iloc[0]
        return float(r["cotizacion_dolar"]), float(r["margen_100ml"]), float(r["margen_decant"]), float(r["costo_envase_decant_ars"])
    return 1200.0, 30.0, 100.0, 800.0

def guardar_config(dolar, m100, mdec, envase):
    execute_query('''
        UPDATE config 
        SET cotizacion_dolar = :dolar, margen_100ml = :m100, margen_decant = :mdec, costo_envase_decant_ars = :envase
        WHERE id = 1
    ''', {"dolar": dolar, "m100": m100, "mdec": mdec, "envase": envase})

def normalizar_texto(texto):
    if not texto:
        return ""
    txt = str(texto).lower().strip()
    txt = re.sub(r'(?i)\bnuevoo?\b', '', txt)
    txt = re.sub(r'\s+', ' ', txt)
    return txt.strip()

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
    story.append(Paragraph("Catálogo Oficial de Fragancias", subtitle_style))
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

st.markdown("<h1 style='text-align: center; margin-bottom: 0px;'>S T O R I A</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #C5A059; letter-spacing: 3px; font-size: 0.8rem;'>P A R F U M S</p>", unsafe_allow_html=True)
st.markdown("---")

dolar_hoy, margen_100_gen, margen_dec_gen, costo_envase = cargar_config()

modo_acceso = st.sidebar.radio(
    "Acceso al Sistema:",
    ["📖 Catálogo Clientes (Libre)", "🔐 Panel Administrador (Socios)"]
)

# ---------------------------------------------------------
# MODO 1: CATÁLOGO PÚBLICO CLIENTE (ACCESO LIBRE)
# ---------------------------------------------------------
if modo_acceso == "📖 Catálogo Clientes (Libre)":
    st.header("📖 Catálogo de Fragancias")

    df_cat_base = cargar_datos_stock()
    
    if not df_cat_base.empty:
        df_cat_base["estado"] = df_cat_base["estado"].replace("Disponible en Proveedor", "A pedido")
        df_cat_base = df_cat_base[df_cat_base["estado"].isin(['En Stock', 'A pedido'])]
        
        df_cat_base["orden"] = df_cat_base["estado"].apply(lambda x: 0 if x == "En Stock" else 1)
        df_cat_base = df_cat_base.sort_values(by=["orden", "nombre_catalogo"]).drop(columns=["orden"])

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
            options=df_cat_base["nombre_catalogo"].tolist(),
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

        pdf_cat_bytes = generar_pdf_catalogo(df_cat_base)
        st.download_button(
            label="📥 Descargar Catálogo Completo (PDF)",
            data=pdf_cat_bytes,
            file_name=f"Catalogo_Storia_Parfums_{datetime.now().strftime('%d_%m_%Y')}.pdf",
            mime="application/pdf"
        )
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
            df_cat_base = df_cat_base[df_cat_base["nombre_catalogo"].astype(str).str.contains(busq_cli, case=False, na=False)]
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
            nombre_vis = r["nombre_catalogo"]

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
                card_html = f'<div class="perfume-card"><div class="perfume-title">{nombre_vis}</div><span class="{estado_class}">{txt_sen}</span>{genero_badge}{tipo_html}{notas_html}<div style="margin-top: 6px;"><div>Frasco {cap_ml}ml: <span class="perfume-price">{p_100ml_str}</span></div><div>Decant 10ml: <span class="perfume-price">{p_decant_str}</span>{stock_dec_html}</div></div></div>'
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

                if busqueda:
                    df = df[df["nombre_catalogo"].astype(str).str.contains(busqueda, case=False, na=False)]
                if filtro_gen_adm != "Todos":
                    df = df[df["genero"] == filtro_gen_adm]
                if filtro_estado:
                    df = df[df["estado"].isin(filtro_estado)]
                if filtro_marca_adm != "Todas":
                    df = df[df["tipo"] == filtro_marca_adm]

                modo_vista = st.radio("Modo de Vista:", ["📱 Tarjetas (Ideal Celular)", "📊 Tabla Completa"], horizontal=True)

                if modo_vista == "📱 Tarjetas (Ideal Celular)":
                    for _, r in df.iterrows():
                        notas_str = f"<div><b>Notas:</b> {r['notas_olfativas']}</div>" if pd.notnull(r.get("notas_olfativas")) and str(r.get("notas_olfativas")).strip() != "" else ""
                        tipo_str = f" ({r['tipo']})" if pd.notnull(r.get("tipo")) and str(r.get("tipo")).strip() != "" else ""
                        gen_str = f" • <span style='color:#E2E8F0;'>[{r['genero']}]</span>"
                        p_100_card = fmt_ars(r['precio_venta_100ml_ars'])
                        p_dec_card = fmt_ars(r['precio_venta_decant_10ml_ars'])
                        cap = limpiar_int_ml(r.get("capacidad_ml", 100), 100)
                        nombre_vis = r["nombre_catalogo"]

                        card_admin_html = f'<div class="perfume-card"><div class="perfume-title">{nombre_vis}</div><span class="perfume-badge">{r["estado"]}</span>{tipo_str}{gen_str}{notas_str}<div style="margin-top: 8px;"><div><b>Frasco ({cap}ml):</b> <span class="perfume-price">{p_100_card}</span> <small>({r["botellas_100ml_cerradas"]} un)</small></div><div><b>Decants 10ml Listos:</b> <span class="perfume-price">{p_dec_card}</span> <small>({r["decants_10ml_preparados"]} un en stock)</small></div><div style="font-size: 0.8rem; color: #999; margin-top: 4px;">Costo USD: ${r["costo_usd"]:.2f}</div></div></div>'
                        st.markdown(card_admin_html, unsafe_allow_html=True)
                else:
                    df_display = df.copy()
                    df_display["precio_100ml_formatted"] = df_display["precio_venta_100ml_ars"].apply(fmt_ars)
                    df_display["precio_10ml_formatted"] = df_display["precio_venta_decant_10ml_ars"].apply(fmt_ars)
                    
                    df_display = df_display.rename(columns={
                        "id": "ID", "nombre_catalogo": "Perfume", "genero": "Género", "tipo": "Marca / Categoría", "capacidad_ml": "Vol (ml)", "estado": "Estado",
                        "botellas_100ml_cerradas": "Frascos", "decants_10ml_preparados": "Decants Stock", "costo_usd": "USD",
                        "precio_100ml_formatted": "Precio Frasco", "precio_10ml_formatted": "Precio 10ml"
                    })
                    st.dataframe(df_display[["ID", "Perfume", "Género", "Marca / Categoría", "Vol (ml)", "Estado", "Frascos", "Decants Stock", "Precio Frasco", "Precio 10ml"]], use_container_width=True)
            else:
                st.info("No hay perfumes registrados.")

        # --- SECCIÓN: PRESUPUESTOS ---
        elif seccion_admin == "📋 Crear Presupuesto":
            st.header("📋 Generar Presupuesto")
            
            col_pr1, col_pr2, col_pr3 = st.columns(3)
            with col_pr1:
                nombre_cliente = st.text_input("Nombre del Cliente / Contacto:", value="Cliente")
            with col_pr2:
                celular_cliente = st.text_input("Celular del Cliente (Ej: 2611234567):", placeholder="Ej: 2611234567")
            with col_pr3:
                socio_presupuesto = st.selectbox("👤 Socio Vendedor (Obligatorio):", options=SOCIOS, index=SOCIOS.index(st.session_state.socio_autenticado))

            df_p = cargar_datos_stock()
            
            if not df_p.empty:
                df_p["costo_usd"] = pd.to_numeric(df_p["costo_usd"], errors='coerce').fillna(0.0)
                df_p["capacidad_ml"] = df_p["capacidad_ml"].apply(lambda v: limpiar_int_ml(v, 100))
                df_p["margen_100ml_custom"] = pd.to_numeric(df_p["margen_100ml_custom"], errors='coerce')
                df_p["margen"] = df_p["margen_100ml_custom"].fillna(margen_100_gen)
                
                df_p["precio_100ml_raw"] = (df_p["costo_usd"] * dolar_hoy) * (1 + (df_p["margen"] / 100))
                df_p["precio_100ml"] = df_p["precio_100ml_raw"].apply(lambda x: redondear_monto(x, 100))
                
                df_p["costo_liquido_10ml"] = df_p.apply(
                    lambda r: ((r["costo_usd"] * dolar_hoy) / r["capacidad_ml"] * 10) if r["capacidad_ml"] > 0 else (r["costo_usd"] * dolar_hoy * 0.10), axis=1
                )
                df_p["precio_decant_raw"] = (df_p["costo_liquido_10ml"] + costo_envase) * (1 + (margen_dec_gen / 100))
                df_p["precio_decant"] = df_p["precio_decant_raw"].apply(lambda x: redondear_monto(x, 100))

                if "items_presupuesto" not in st.session_state:
                    st.session_state.items_presupuesto = []
                    
                p_sel = st.selectbox("Perfume:", df_p["nombre_catalogo"].tolist())
                p_data_temp = df_p[df_p["nombre_catalogo"] == p_sel].iloc[0]
                cap_temp = limpiar_int_ml(p_data_temp.get("capacidad_ml", 100), 100)

                with st.form("form_item_presupuesto"):
                    col_pitem1, col_pitem2 = st.columns([2, 1])
                    with col_pitem1:
                        pres_sel = st.selectbox("Presentación:", [f"Frasco Cerrado ({cap_temp}ml)", "Decant 10ml"])
                    with col_pitem2:
                        cant_sel = st.number_input("Cantidad:", min_value=1, value=1, step=1)
                        desc_individual = st.number_input("Descuento Individual ($ ARS):", min_value=0.0, value=0.0, step=500.0)
                        
                    add_item = st.form_submit_button("➕ Agregar a la Lista")
                    
                    if add_item:
                        p_unit_base = p_data_temp["precio_100ml"] if "Frasco" in pres_sel else p_data_temp["precio_decant"]
                        p_unit_final = redondear_monto(max(0.0, p_unit_base - desc_individual), 100)
                        st.session_state.items_presupuesto.append({
                            "nombre": p_sel, "presentacion": pres_sel,
                            "cantidad": cant_sel, "precio_unitario": p_unit_final, "subtotal": p_unit_final * cant_sel
                        })
                        st.success(f"Agregado {p_sel}")
                        st.rerun()
                        
                if st.session_state.items_presupuesto:
                    st.subheader("🛒 Items en el Presupuesto")
                    
                    for idx_p, item_p in enumerate(st.session_state.items_presupuesto):
                        col_pi1, col_pi2, col_pi3, col_pi4, col_pi5 = st.columns([3, 2, 1, 2, 1])
                        with col_pi1:
                            st.write(f"**{item_p['nombre']}**")
                        with col_pi2:
                            st.write(f"{item_p['presentacion']}")
                        with col_pi3:
                            st.write(f"x{item_p['cantidad']}")
                        with col_pi4:
                            st.write(f"{fmt_ars(item_p['subtotal'])}")
                        with col_pi5:
                            if st.button("🗑️", key=f"btn_del_p_item_{idx_p}"):
                                st.session_state.items_presupuesto.pop(idx_p)
                                st.rerun()

                    subtotal_pres = sum(i["subtotal"] for i in st.session_state.items_presupuesto)

                    st.markdown("---")
                    st.subheader("🎁 Descuento General sobre la Compra")
                    
                    tipo_descuento = st.radio("Tipo de Descuento General:", ["Sin Descuento Extra", "Monto Fijo Manual ($ ARS)", "Descuento en Lista (%)", "Porcentaje Personalizado (%)"], horizontal=True)
                    monto_desc_pres = 0.0
                    
                    if tipo_descuento == "Descuento en Lista (%)":
                        pct_desc = st.selectbox("Selecciona Porcentaje:", [0, 5, 10, 15, 20], index=0)
                        monto_desc_pres = subtotal_pres * (pct_desc / 100.0)
                    elif tipo_descuento == "Monto Fijo Manual ($ ARS)":
                        monto_manual = st.number_input("Ingresa monto in Pesos ($ ARS):", min_value=0.0, max_value=float(subtotal_pres), value=0.0, step=500.0)
                        monto_desc_pres = float(monto_manual)
                    elif tipo_descuento == "Porcentaje Personalizado (%)":
                        pct_manual = st.number_input("Ingresa porcentaje exacto (%):", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
                        monto_desc_pres = subtotal_pres * (pct_manual / 100.0)

                    total_pres = redondear_monto(max(0.0, subtotal_pres - monto_desc_pres), 100)
                    
                    col_tot1, col_tot2, col_tot3 = st.columns(3)
                    with col_tot1:
                        st.metric("Subtotal", fmt_ars(subtotal_pres))
                    with col_tot2:
                        st.metric("Descuento", f"-{fmt_ars(monto_desc_pres)}")
                    with col_tot3:
                        st.metric("TOTAL FINAL", fmt_ars(total_pres))
                    
                    pdf_pres_bytes = generar_pdf_presupuesto(nombre_cliente, celular_cliente, socio_presupuesto, st.session_state.items_presupuesto, subtotal_pres, monto_desc_pres, total_pres)
                    
                    col_btn1, col_btn2 = st.columns(2)
                    with col_btn1:
                        st.download_button(
                            label="📄 Descargar Presupuesto PDF",
                            data=pdf_pres_bytes,
                            file_name=f"Presupuesto_{nombre_cliente}_{socio_presupuesto}.pdf",
                            mime="application/pdf"
                        )
                    with col_btn2:
                        chk_limpiar_p = st.checkbox("⚠️ ¿Confirmar limpieza de lista?", key="chk_clear_presupuesto")
                        if st.button("🗑️ Limpiar Lista Completa"):
                            if chk_limpiar_p:
                                st.session_state.items_presupuesto = []
                                st.rerun()
                            else:
                                st.warning("Marca la casilla para limpiar la lista.")

        # --- SECCIÓN: REGISTRAR VENTA ---
        elif seccion_admin == "🛒 Registrar Venta":
            st.header("🛒 Registrar Venta Multi-Item")
            
            col_vcli1, col_vcli2, col_vcli3 = st.columns(3)
            with col_vcli1:
                cliente_venta = st.text_input("Nombre del Cliente:", value="Cliente")
            with col_vcli2:
                celular_venta = st.text_input("Número de Celular del Cliente (Ej: 2611234567):", placeholder="Ej: 2611234567")
            with col_vcli3:
                socio_vendedor_real = st.selectbox("👤 Socio Vendedor:", options=SOCIOS, index=SOCIOS.index(st.session_state.socio_autenticado))

            df_actual = cargar_datos_stock()

            if not df_actual.empty:
                df_actual["costo_usd"] = pd.to_numeric(df_actual["costo_usd"], errors='coerce').fillna(0.0)
                df_actual["capacidad_ml"] = df_actual["capacidad_ml"].apply(lambda v: limpiar_int_ml(v, 100))
                df_actual["margen_100ml_custom"] = pd.to_numeric(df_actual["margen_100ml_custom"], errors='coerce')
                df_actual["margen"] = df_actual["margen_100ml_custom"].fillna(margen_100_gen)
                
                df_actual["precio_100ml_raw"] = (df_actual["costo_usd"] * dolar_hoy) * (1 + (df_actual["margen"] / 100))
                df_actual["precio_100ml"] = df_actual["precio_100ml_raw"].apply(lambda x: redondear_monto(x, 100))
                
                df_actual["costo_liquido_10ml"] = df_actual.apply(
                    lambda r: ((r["costo_usd"] * dolar_hoy) / r["capacidad_ml"] * 10) if r["capacidad_ml"] > 0 else (r["costo_usd"] * dolar_hoy * 0.10), axis=1
                )
                df_actual["precio_decant_raw"] = (df_actual["costo_liquido_10ml"] + costo_envase) * (1 + (margen_dec_gen / 100))
                df_actual["precio_decant"] = df_actual["precio_decant_raw"].apply(lambda x: redondear_monto(x, 100))

                if "items_venta" not in st.session_state:
                    st.session_state.items_venta = []

                p_sel_v = st.selectbox("Perfume a vender:", df_actual["nombre_catalogo"].tolist())
                p_data_v = df_actual[df_actual["nombre_catalogo"] == p_sel_v].iloc[0]
                cap_v = limpiar_int_ml(p_data_v.get("capacidad_ml", 100), 100)

                with st.form("form_item_venta"):
                    st.subheader("➕ Agregar Perfume / Decant a la Venta")
                    col_vi1, col_vi2 = st.columns([2, 1])
                    with col_vi1:
                        pres_sel_v = st.selectbox("Presentación:", [f"Frasco Cerrado ({cap_v}ml)", "Decant 10ml (Listo)", "Descontar 10ml de frasco abierto"])
                    with col_vi2:
                        cant_sel_v = st.number_input("Cantidad unidades:", min_value=1, value=1, step=1)
                        desc_ind_v = st.number_input("Descuento Individual ($ ARS):", min_value=0.0, value=0.0, step=500.0)
                        dias_estimados_uso = st.selectbox("⏱️ Tiempo estimado de uso:", [1, 30, 60, 90, 120, 180], index=3)
                        
                    add_vitem = st.form_submit_button("➕ Agregar a la Venta")

                    if add_vitem:
                        p_unit_base = p_data_v["precio_100ml"] if "Frasco" in pres_sel_v else p_data_v["precio_decant"]
                        p_unit_final = redondear_monto(max(0.0, p_unit_base - desc_ind_v), 100)
                        
                        st.session_state.items_venta.append({
                            "id_producto": int(p_data_v["id"]),
                            "nombre": p_sel_v,
                            "presentacion": pres_sel_v,
                            "cantidad": cant_sel_v,
                            "precio_unitario": p_unit_final,
                            "subtotal": p_unit_final * cant_sel_v,
                            "dias_estimados": dias_estimados_uso,
                            "capacidad_ml": cap_v,
                            "costo_usd": float(p_data_v.get("costo_usd", 0.0))
                        })
                        st.success(f"Agregado {p_sel_v}")
                        st.rerun()

                if st.session_state.items_venta:
                    st.markdown("---")
                    st.subheader("🛒 Resumen de la Venta a Confirmar")
                    
                    for idx_v, item_v in enumerate(st.session_state.items_venta):
                        col_vi_1, col_vi_2, col_vi_3, col_vi_4, col_vi_5 = st.columns([3, 2, 1, 2, 1])
                        with col_vi_1:
                            st.write(f"**{item_v['nombre']}**")
                        with col_vi_2:
                            st.write(f"{item_v['presentacion']}")
                        with col_vi_3:
                            st.write(f"x{item_v['cantidad']}")
                        with col_vi_4:
                            st.write(f"{fmt_ars(item_v['subtotal'])}")
                        with col_vi_5:
                            if st.button("🗑️", key=f"btn_del_v_item_{idx_v}"):
                                st.session_state.items_venta.pop(idx_v)
                                st.rerun()

                    subtotal_v = sum(i["subtotal"] for i in st.session_state.items_venta)

                    st.subheader("🎁 Descuento General sobre Total de Venta")
                    tipo_desc_v = st.radio("Tipo de Descuento General:", ["Sin Descuento Extra", "Monto Fijo en Pesos ($ ARS)", "Porcentaje Personalizado (%)"], horizontal=True)
                    
                    monto_desc_v = 0.0
                    if tipo_desc_v == "Monto Fijo en Pesos ($ ARS)":
                        monto_desc_v = float(st.number_input("Monto en Pesos ($ ARS):", min_value=0.0, max_value=float(subtotal_v), value=0.0, step=500.0))
                    elif tipo_desc_v == "Porcentaje Personalizado (%)":
                        pct_v = st.number_input("Porcentaje (%):", min_value=0.0, max_value=100.0, value=0.0, step=0.5)
                        monto_desc_v = subtotal_v * (pct_v / 100.0)

                    total_v = redondear_monto(max(0.0, subtotal_v - monto_desc_v), 100)

                    col_vtot1, col_vtot2, col_vtot3 = st.columns(3)
                    with col_vtot1:
                        st.metric("Subtotal Venta", fmt_ars(subtotal_v))
                    with col_vtot2:
                        st.metric("Descuento Total", f"-{fmt_ars(monto_desc_v)}")
                    with col_vtot3:
                        st.metric("TOTAL REAL A COBRAR", fmt_ars(total_v))

                    st.markdown("---")
                    col_vbtn1, col_vbtn2 = st.columns(2)
                    
                    with col_vbtn1:
                        if st.button("🚀 Confirmar Venta, Descontar Stock & Registrar Ingreso"):
                            fecha_actual = datetime.now()
                            fecha_actual_str = fecha_actual.strftime("%Y-%m-%d %H:%M:%S")
                            factor_descuento = (total_v / subtotal_v) if subtotal_v > 0 else 1.0

                            for item in st.session_state.items_venta:
                                id_p = item["id_producto"]
                                df_stock_p = fetch_df("SELECT botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, capacidad_ml FROM stock WHERE id = :id_p", {"id_p": id_p})
                                
                                if not df_stock_p.empty:
                                    r_p = df_stock_p.iloc[0]
                                    botellas = int(r_p["botellas_100ml_cerradas"])
                                    ml = int(r_p["ml_disponibles_abiertos"])
                                    decants = int(r_p["decants_10ml_preparados"])
                                    cap_tot = limpiar_int_ml(r_p["capacidad_ml"], 100)
                                    cant = item["cantidad"]
                                    pres = item["presentacion"]
                                    monto_cobrado_real_item = redondear_monto(item['subtotal'] * factor_descuento, 100)

                                    if "Frasco" in pres:
                                        nuevas_botellas = max(0, botellas - cant)
                                        nuevo_est = "En Stock" if (nuevas_botellas > 0 or decants > 0 or ml >= 10) else "A pedido"
                                        execute_query('''
                                            UPDATE stock 
                                            SET botellas_100ml_cerradas = :nbot, estado = :est, monto_senado_ars = 0, cliente_senado = '', socio_asignado = '' 
                                            WHERE id = :id_p
                                        ''', {"nbot": nuevas_botellas, "est": nuevo_est, "id_p": id_p})

                                    elif "Listo" in pres:
                                        nuevos_decants = max(0, decants - cant)
                                        nuevo_est = "En Stock" if (nuevos_decants > 0 or botellas > 0 or ml >= 10) else "A pedido"
                                        execute_query('''
                                            UPDATE stock 
                                            SET decants_10ml_preparados = :ndec, estado = :est, monto_senado_ars = 0, cliente_senado = '', socio_asignado = '' 
                                            WHERE id = :id_p
                                        ''', {"ndec": nuevos_decants, "est": nuevo_est, "id_p": id_p})

                                    elif "abierto" in pres:
                                        ml_necesarios = cant * 10
                                        if ml >= ml_necesarios:
                                            nuevos_ml = ml - ml_necesarios
                                            nuevo_est = "En Stock" if (nuevos_ml >= 10 or botellas > 0 or decants > 0) else "A pedido"
                                            execute_query("UPDATE stock SET ml_disponibles_abiertos = :nml, estado = :est, monto_senado_ars = 0, cliente_senado = '', socio_asignado = '' WHERE id = :id_p", {"nml": nuevos_ml, "est": nuevo_est, "id_p": id_p})
                                        elif botellas > 0:
                                            nuevas_bot = botellas - 1
                                            nuevos_ml = ml + cap_tot - ml_necesarios
                                            nuevo_est = "En Stock" if (nuevas_bot > 0 or decants > 0 or nuevos_ml >= 10) else "A pedido"
                                            execute_query("UPDATE stock SET botellas_100ml_cerradas = :nbot, ml_disponibles_abiertos = :nml, estado = :est WHERE id = :id_p", {"nbot": nuevas_bot, "nml": nuevos_ml, "est": nuevo_est, "id_p": id_p})

                                    info_cli = f"Cliente: {cliente_venta}" + (f" (Cel: {celular_venta})" if celular_venta else "")
                                    execute_query('''
                                        INSERT INTO historial (fecha, perfume, socio, tipo_movimiento, monto_ingreso_ars, id_producto, presentacion, cantidad) 
                                        VALUES (:fec, :perf, :soc, :tip, :mon, :idp, :pres, :cant)
                                    ''', {"fec": fecha_actual_str, "perf": item['nombre'], "soc": socio_vendedor_real, "tip": f"{pres} (x{cant}) - {info_cli}", "mon": monto_cobrado_real_item, "idp": id_p, "pres": pres, "cant": cant})

                                    dias_u = item.get("dias_estimados", 90)
                                    fecha_rec = (fecha_actual + timedelta(days=dias_u)).strftime("%Y-%m-%d")
                                    execute_query('''
                                        INSERT INTO clientes_seguimiento (fecha_compra, cliente_nombre, cliente_celular, socio_vendedor, perfume, presentacion, dias_estimados, fecha_recordatorio, estado)
                                        VALUES (:fcomp, :cnom, :ccel, :svend, :perf, :pres, :dias, :frec, 'Pendiente')
                                    ''', {"fcomp": fecha_actual.strftime("%Y-%m-%d"), "cnom": cliente_venta, "ccel": celular_venta, "svend": socio_vendedor_real, "perf": item['nombre'], "pres": pres, "dias": dias_u, "frec": fecha_rec})

                            st.session_state.items_venta = []
                            st.success(f"¡Venta registrada con éxito!")
                            st.rerun()

                    with col_vbtn2:
                        chk_canc_v = st.checkbox("⚠️ ¿Confirmar cancelación?", key="chk_cancel_venta")
                        if st.button("🗑️ Cancelar / Limpiar Lista Completa"):
                            if chk_canc_v:
                                st.session_state.items_venta = []
                                st.rerun()
                            else:
                                st.warning("Marca la casilla para confirmar.")

        # --- SECCIÓN: SEGUIMIENTO & CLIENTES ---
        elif seccion_admin == "💬 Seguimiento & Clientes":
            st.header("💬 Seguimiento de Clientes & Recordatorios WhatsApp")
            st.info("💡 Este módulo calcula el tiempo estimado de uso del perfume. Cuando llega la fecha, permite enviar WhatsApp directo o eliminar el registro.")

            df_seg = cargar_seguimiento()

            if not df_seg.empty:
                hoy_str = datetime.now().strftime("%Y-%m-%d")
                df_seg["vencido"] = df_seg["fecha_recordatorio"] <= hoy_str
                df_vencidos = df_seg[df_seg["vencido"] & (df_seg["estado"] == "Pendiente")]
                df_proximos = df_seg[~df_seg["vencido"] & (df_seg["estado"] == "Pendiente")]
                df_contactados = df_seg[df_seg["estado"] == "Contactado"]

                st.subheader(f"🚨 Clientes para Contactar Hoy ({len(df_vencidos)})")
                if not df_vencidos.empty:
                    for _, row_c in df_vencidos.iterrows():
                        msg_auto = f"Hola {row_c['cliente_nombre']}! Te escribimos de STORIA PARFUMS. Esperamos que estés disfrutando tu perfume {row_c['perfume']} ✨. Calculamos que ya debe estar por terminarse o listo para renovar. Te dejamos nuestro catálogo actualizado: {URL_CATALOGO_PUBLICO}"
                        msg_enc = urllib.parse.quote(msg_auto)
                        cel_clean = formatear_celular_wa(row_c['cliente_celular'])
                        
                        col_seg1, col_seg2 = st.columns([3, 1])
                        with col_seg1:
                            st.markdown(f"""
                            <div style="background-color: #3D1C19; border-left: 4px solid #FF4D4D; padding: 10px; border-radius: 6px; margin-bottom: 8px;">
                                <b>👤 Cliente:</b> {row_c['cliente_nombre']} (Cel: {row_c['cliente_celular']})<br>
                                <b>🌸 Perfume:</b> {row_c['perfume']} ({row_c['presentacion']})<br>
                                <b>📅 Fecha Compra:</b> {row_c['fecha_compra']} | <b>Vendedor:</b> {row_c['socio_vendedor']}
                            </div>
                            """, unsafe_allow_html=True)
                        with col_seg2:
                            if cel_clean:
                                st.markdown(f'<a href="https://wa.me/{cel_clean}?text={msg_enc}" target="_blank" class="btn-whatsapp">💬 Enviar WhatsApp</a>', unsafe_allow_html=True)
                            
                            if st.button(f"✅ Contactado", key=f"btn_mark_{row_c['id']}"):
                                execute_query("UPDATE clientes_seguimiento SET estado = 'Contactado' WHERE id = :id_seg", {"id_seg": row_c['id']})
                                st.rerun()

                            confirm_del_seg = st.checkbox("⚠️ ¿Confirmar eliminación?", key=f"chk_del_seg_{row_c['id']}")
                            if st.button(f"🗑️ Eliminar", key=f"btn_del_seg_{row_c['id']}"):
                                if confirm_del_seg:
                                    execute_query("DELETE FROM clientes_seguimiento WHERE id = :id_seg", {"id_seg": row_c['id']})
                                    st.success("Registro eliminado.")
                                    st.rerun()
                                else:
                                    st.warning("Marca la casilla para confirmar.")
                else:
                    st.success("🎉 ¡No hay recordatorios pendientes para contactar hoy!")

                st.markdown("---")
                st.subheader("📅 Próximos Vencimientos Estimados")
                if not df_proximos.empty:
                    for _, row_p in df_proximos.iterrows():
                        col_p1, col_p2 = st.columns([3, 1])
                        with col_p1:
                            st.markdown(f"**👤 {row_p['cliente_nombre']}** | {row_p['perfume']} ({row_p['presentacion']}) - Recordatorio: `{row_p['fecha_recordatorio']}`")
                        with col_p2:
                            confirm_del_prox = st.checkbox("⚠️ ¿Confirmar eliminación?", key=f"chk_del_prox_{row_p['id']}")
                            if st.button("🗑️ Eliminar", key=f"btn_del_prox_{row_p['id']}"):
                                if confirm_del_prox:
                                    execute_query("DELETE FROM clientes_seguimiento WHERE id = :id_seg", {"id_seg": row_p['id']})
                                    st.rerun()
                                else:
                                    st.warning("Marca la casilla para confirmar.")

                if not df_contactados.empty:
                    with st.expander("✅ Ver Historial de Clientes Contactados"):
                        st.dataframe(df_contactados[["fecha_compra", "cliente_nombre", "perfume", "socio_vendedor", "estado"]], use_container_width=True)
            else:
                st.info("Aún no hay registros de clientes en el sistema de seguimiento.")

        # --- SECCIÓN: CONTABILIDAD Y GASTOS ---
        elif seccion_admin == "📊 Contabilidad & Gastos":
            st.header("📊 Contabilidad, Gastos y Balance de Caja")
            st.info("💡 Lleva el control contable completo con reportes temporales y filtros por socio.")

            with st.expander("➕ Registrar Nuevo Gasto / Egreso"):
                with st.form("form_egreso", clear_on_submit=True):
                    col_eg1, col_eg2 = st.columns(2)
                    with col_eg1:
                        cat_gasto = st.selectbox("Categoría del Gasto:", ["Envases / Decants", "Bolsas & Packings", "Tarjetas / Etiquetas", "Envíos / Logística", "Compra Stock", "Marketing / Publicidad", "Otros Gastos"])
                        desc_gasto = st.text_input("Descripción del Gasto:", placeholder="Ej. 100 bolsas kraft personalizadas")
                    with col_eg2:
                        monto_gasto = st.number_input("Monto en Pesos ($ ARS):", min_value=0.0, value=0.0, step=500.0)
                        socio_gasto = st.selectbox("Socio que abonó el gasto:", SOCIOS, index=SOCIOS.index(st.session_state.socio_autenticado))
                    
                    btn_save_eg = st.form_submit_button("💾 Registar Gasto")
                    if btn_save_eg and monto_gasto > 0:
                        f_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        execute_query("INSERT INTO egresos (fecha, categoria, descripcion, monto_ars, socio_registra) VALUES (:fec, :cat, :desc, :mon, :soc)",
                                      {"fec": f_hoy, "cat": cat_gasto, "desc": desc_gasto, "mon": monto_gasto, "soc": socio_gasto})
                        st.success("¡Gasto registrado con éxito!")
                        st.rerun()

            st.markdown("---")
            st.subheader("📅 Filtro de Fecha y Socio para Reportes Contables")

            col_cf1, col_cf2 = st.columns([2, 1])
            with col_cf1:
                tipo_filtro_f = st.radio("Selecciona Período a consultar:", ["Todo el Histórico", "Por Mes / Año", "Por Día Específico", "Rango de Fechas"], horizontal=True)
            with col_cf2:
                socio_filtro_contable = st.selectbox("👤 Filtrar Vendedor:", ["Todos los Socios"] + SOCIOS)

            df_hist_c = cargar_historial()
            df_eg_c = cargar_egresos()

            df_h_filt = df_hist_c.copy()
            df_e_filt = df_eg_c.copy()

            periodo_txt = "Todo el Histórico"

            if tipo_filtro_f == "Por Mes / Año":
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    mes_sel = st.selectbox("Mes:", list(range(1, 13)), index=datetime.now().month - 1)
                with col_m2:
                    anio_sel = st.number_input("Año:", min_value=2020, max_value=2030, value=datetime.now().year)

                periodo_txt = f"{mes_sel}/{anio_sel}"
                if not df_h_filt.empty and "fecha_dt" in df_h_filt.columns:
                    df_h_filt = df_h_filt[(df_h_filt["fecha_dt"].dt.month == mes_sel) & (df_h_filt["fecha_dt"].dt.year == anio_sel)]
                if not df_e_filt.empty and "fecha_dt" in df_e_filt.columns:
                    df_e_filt = df_e_filt[(df_e_filt["fecha_dt"].dt.month == mes_sel) & (df_e_filt["fecha_dt"].dt.year == anio_sel)]

            elif tipo_filtro_f == "Por Día Específico":
                dia_sel = st.date_input("Selecciona Día:", value=datetime.now().date())
                dia_str = dia_sel.strftime("%Y-%m-%d")
                periodo_txt = dia_str

                if not df_h_filt.empty and "fecha" in df_h_filt.columns:
                    df_h_filt = df_h_filt[df_h_filt["fecha"].astype(str).str.startswith(dia_str)]
                if not df_e_filt.empty and "fecha" in df_e_filt.columns:
                    df_e_filt = df_e_filt[df_e_filt["fecha"].astype(str).str.startswith(dia_str)]

            elif tipo_filtro_f == "Rango de Fechas":
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    f_inicio = st.date_input("Fecha Inicio:", value=datetime.now().date() - timedelta(days=30))
                with col_r2:
                    f_fin = st.date_input("Fecha Fin:", value=datetime.now().date())

                periodo_txt = f"{f_inicio.strftime('%d/%m/%Y')} al {f_fin.strftime('%d/%m/%Y')}"
                if not df_h_filt.empty and "fecha_dt" in df_h_filt.columns:
                    df_h_filt = df_h_filt[(df_h_filt["fecha_dt"].dt.date >= f_inicio) & (df_h_filt["fecha_dt"].dt.date <= f_fin)]
                if not df_e_filt.empty and "fecha_dt" in df_e_filt.columns:
                    df_e_filt = df_e_filt[(df_e_filt["fecha_dt"].dt.date >= f_inicio) & (df_e_filt["fecha_dt"].dt.date <= f_fin)]

            if socio_filtro_contable != "Todos los Socios":
                if not df_h_filt.empty and "socio" in df_h_filt.columns:
                    df_h_filt = df_h_filt[df_h_filt["socio"] == socio_filtro_contable]

            total_ingresos = df_h_filt["monto_ingreso_ars"].sum
