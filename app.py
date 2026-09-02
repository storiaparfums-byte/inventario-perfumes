import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import pypdf
import re
import io
import urllib.parse
import math

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
ESTADOS = ["En Stock", "A pedido", "Pedido / Señado", "Agotado"]
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
    """Sanitiza campos enteros evitando artefactos binarios de SQLite"""
    try:
        if isinstance(val, bytes):
            val = val.decode('utf-8', errors='ignore')
        val_clean = re.sub(r'[^\d]', '', str(val))
        return int(val_clean) if val_clean else defecto
    except Exception:
        return defecto

def formatear_celular_wa(numero_str):
    """
    Normaliza números de Argentina (Mendoza ej. 2611234567, 0261151234567)
    a formato internacional compatible con api.whatsapp.me (5492611234567).
    """
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
# ESTILOS CSS PERSONALIZADOS (STORIA PARFUMS)
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
    .badge-senado {
        background-color: #8B0000 !important;
        color: #FFFFFF !important;
        font-weight: bold;
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
# Base de datos SQLite Local
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect('inventario.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT UNIQUE,
            tipo TEXT,
            genero TEXT DEFAULT 'Unisex',
            capacidad_ml INTEGER DEFAULT 100,
            botellas_100ml_cerradas INTEGER,
            ml_disponibles_abiertos INTEGER,
            decants_10ml_preparados INTEGER,
            costo_usd REAL,
            margen_100ml_custom REAL,
            estado TEXT,
            socio_asignado TEXT,
            monto_senado_ars REAL DEFAULT 0.0,
            cliente_senado TEXT DEFAULT '',
            notas_olfativas TEXT,
            imagen_url TEXT
        )
    ''')
    
    try:
        c.execute("ALTER TABLE stock ADD COLUMN genero TEXT DEFAULT 'Unisex'")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE stock ADD COLUMN capacidad_ml INTEGER DEFAULT 100")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE stock ADD COLUMN monto_senado_ars REAL DEFAULT 0.0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE stock ADD COLUMN cliente_senado TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE stock ADD COLUMN notas_olfativas TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE stock ADD COLUMN imagen_url TEXT")
    except sqlite3.OperationalError:
        pass

    c.execute('''
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

    c.execute('''
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            cotizacion_dolar REAL,
            margen_100ml REAL,
            margen_decant REAL,
            costo_envase_decant_ars REAL
        )
    ''')
    c.execute('''
        INSERT OR IGNORE INTO config (id, cotizacion_dolar, margen_100ml, margen_decant, costo_envase_decant_ars)
        VALUES (1, 1200.0, 30.0, 100.0, 800.0)
    ''')

    c.execute('''
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

    c.execute('''
        CREATE TABLE IF NOT EXISTS egresos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            categoria TEXT,
            descripcion TEXT,
            monto_ars REAL,
            socio_registra TEXT
        )
    ''')

    c.execute('''
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

    conn.commit()
    conn.close()

init_db()

def cargar_datos_stock():
    conn = sqlite3.connect('inventario.db')
    df = pd.read_sql_query("SELECT * FROM stock", conn)
    conn.close()
    if not df.empty:
        if "capacidad_ml" in df.columns:
            df["capacidad_ml"] = df["capacidad_ml"].apply(lambda v: limpiar_int_ml(v, 100))
        if "genero" in df.columns:
            df["genero"] = df["genero"].fillna("Unisex").replace("", "Unisex")
    return df

def cargar_historial():
    conn = sqlite3.connect('inventario.db')
    df = pd.read_sql_query("SELECT * FROM historial ORDER BY id DESC", conn)
    conn.close()
    if not df.empty and "fecha" in df.columns:
        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors='coerce')
    return df

def cargar_egresos():
    conn = sqlite3.connect('inventario.db')
    df = pd.read_sql_query("SELECT * FROM egresos ORDER BY id DESC", conn)
    conn.close()
    if not df.empty and "fecha" in df.columns:
        df["fecha_dt"] = pd.to_datetime(df["fecha"], errors='coerce')
    return df

def cargar_seguimiento():
    conn = sqlite3.connect('inventario.db')
    df = pd.read_sql_query("SELECT * FROM clientes_seguimiento ORDER BY fecha_recordatorio ASC", conn)
    conn.close()
    return df

def cargar_ordenes_compra():
    conn = sqlite3.connect('inventario.db')
    df = pd.read_sql_query("SELECT * FROM ordenes_compra ORDER BY id ASC", conn)
    conn.close()
    if not df.empty and "capacidad_ml" in df.columns:
        df["capacidad_ml"] = df["capacidad_ml"].apply(lambda v: limpiar_int_ml(v, 100))
    return df

def cargar_config():
    conn = sqlite3.connect('inventario.db')
    c = conn.cursor()
    c.execute("SELECT cotizacion_dolar, margen_100ml, margen_decant, costo_envase_decant_ars FROM config WHERE id = 1")
    res = c.fetchone()
    conn.close()
    return res if res else (1200.0, 30.0, 100.0, 800.0)

def guardar_config(dolar, m100, mdec, envase):
    conn = sqlite3.connect('inventario.db')
    c = conn.cursor()
    c.execute('''
        UPDATE config 
        SET cotizacion_dolar = ?, margen_100ml = ?, margen_decant = ?, costo_envase_decant_ars = ?
        WHERE id = 1
    ''', (dolar, m100, mdec, envase))
    conn.commit()
    conn.close()

def normalizar_texto(texto):
    if not texto:
        return ""
    txt = str(texto).lower().strip()
    txt = re.sub(r'\s+', ' ', txt)
    return txt

def extraer_perfume_y_precio(linea):
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
# GENERACIÓN DE PDFS ROBUSTOS Y SIN SUPERPOSICIÓN DE TEXTO
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
        est_publico = "Reservado / A pedido" if row["estado"] == "Pedido / Señado" else row["estado"]
        
        data.append([
            Paragraph(f"{row['nombre']}{tipo_str}", cell_bold),
            Paragraph(gen, cell_style),
            Paragraph(f"{cap} ml", cell_style),
            Paragraph(est_publico, cell_style),
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

    # Resumen Financiero
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

    # Tabla de Ingresos
    story.append(Paragraph("<b>Detalle de Ingresos (Ventas y Señas)</b>", meta_style))
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

    # Tabla de Egresos
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
    
    headers = ["Perfume / Producto", "Estado / Reserva", "Cant.", "Costo USD", "Subtotal USD"]
    data = [[Paragraph(h, header_style) for h in headers]]
    
    for _, row in df_items.iterrows():
        est_txt = row['estado_inventario']
        if row.get('detalle_reserva'):
            est_txt += f" ({row['detalle_reserva']})"
        data.append([
            Paragraph(row["nombre"], cell_style),
            Paragraph(est_txt, cell_style),
            Paragraph(str(row["cantidad"]), cell_style),
            Paragraph(f"${row['costo_usd']:.2f}", cell_style),
            Paragraph(f"${row['subtotal_usd']:.2f}", cell_style)
        ])
        
    t = Table(data, colWidths=[200, 110, 40, 90, 100])
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

# Selección Inicial de Modo de Uso
modo_acceso = st.sidebar.radio(
    "Acceso al Sistema:",
    ["📖 Catálogo Clientes (Libre)", "🔐 Panel Administrador (Socios)"]
)

# ---------------------------------------------------------
# MODO 1: CATÁLOGO PÚBLICO CLIENTE (ACCESO LIBRE - SOLO CONSULTA)
# ---------------------------------------------------------
if modo_acceso == "📖 Catálogo Clientes (Libre)":
    st.header("📖 Catálogo de Fragancias")

    df_cat_base = cargar_datos_stock()
    
    if not df_cat_base.empty:
        df_cat_base["estado"] = df_cat_base["estado"].replace("Disponible en Proveedor", "A pedido")
        df_cat_base = df_cat_base[df_cat_base["estado"].isin(['En Stock', 'A pedido', 'Pedido / Señado'])]
        
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

        # --- SELECCIÓN INTERACTIVA DE CONSULTA POR PERFUMES ---
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
            cnt_frascos = r.get("botellas_100ml_cerradas", 0)
            cnt_ml_ab = r.get("ml_disponibles_abiertos", 0)

            if cnt_decants > 0 or cnt_ml_ab >= 10:
                stock_dec_html = '<span class="stock-badge-green"> (Disponible)</span>'
            else:
                stock_dec_html = '<span class="stock-badge-red"> (A pedido)</span>'

            if r['estado'] == "Pedido / Señado":
                estado_class = "perfume-badge badge-senado"
                txt_sen = "📌 RESERVADO / A PEDIDO"
            else:
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
# MODO 2: PANEL DE ADMINISTRADOR (RESTRINGIDO CON CONTRASEÑA)
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
                "📌 Registrar Seña / Reserva",
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
                "💾 Copia de Seguridad"
            ]
        )

        st.sidebar.caption(f"💵 Dólar Sistema: **{fmt_ars(dolar_hoy)}**")

        # --- SECCIÓN: REGISTRAR SEÑA / RESERVA ---
        if seccion_admin == "📌 Registrar Seña / Reserva":
            st.header("📌 Registrar Seña o Reserva (Frascos o Decants)")
            st.info("💡 Aparta un perfume. En el catálogo público solo aparecerá como 'RESERVADO / A PEDIDO' sin revelar el nombre del cliente ni montos.")

            df_sen = cargar_datos_stock()

            if not df_sen.empty:
                p_senia_sel = st.selectbox("Perfume / Fragancia:", df_sen["nombre"].tolist())
                p_data_sen = df_sen[df_sen["nombre"] == p_senia_sel].iloc[0]
                cap_sen = limpiar_int_ml(p_data_sen.get("capacidad_ml", 100), 100)

                with st.form("form_reg_senia", clear_on_submit=True):
                    col_sen1, col_sen2 = st.columns(2)
                    with col_sen1:
                        pres_senia_sel = st.selectbox("Presentación a Apartar:", [f"Frasco Completo ({cap_sen}ml)", "Decant 10ml"])
                        cli_senia_nom = st.text_input("Nombre del Cliente:", placeholder="Ej. Juan Pérez")
                        socio_senia_sel = st.selectbox("Socio que toma el pedido:", SOCIOS, index=SOCIOS.index(st.session_state.socio_autenticado))
                    
                    with col_sen2:
                        tipo_operacion_res = st.radio(
                            "Tipo de Operación:",
                            ["📌 Seña (Con Pago)", "🔒 Reserva (Sin Pago)"],
                            horizontal=True
                        )
                        
                        if tipo_operacion_res == "📌 Seña (Con Pago)":
                            monto_senia_val = st.number_input("Monto Entregado de Seña ($ ARS):", min_value=0.0, value=5000.0, step=1000.0)
                        else:
                            monto_senia_val = 0.0
                            st.caption("ℹ️ La reserva sin pago no genera movimientos en la contabilidad.")

                        agregar_a_orden = st.checkbox("📦 Agregar automáticamente a la Orden de Compra para Proveedor", value=True)

                    btn_guardar_senia = st.form_submit_button("📌 Confirmar Seña / Reserva")

                    if btn_guardar_senia and cli_senia_nom.strip() != "":
                        conn = sqlite3.connect('inventario.db')
                        c = conn.cursor()
                        
                        nom_item_senia = f"{p_senia_sel} ({pres_senia_sel})"
                        
                        c.execute('''
                            UPDATE stock 
                            SET estado = 'Pedido / Señado', socio_asignado = ?, monto_senado_ars = ?, cliente_senado = ?
                            WHERE nombre = ?
                        ''', (socio_senia_sel, monto_senia_val, f"{cli_senia_nom.strip()} [{pres_senia_sel}]", p_senia_sel))
                        
                        if monto_senia_val > 0:
                            f_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            c.execute('''
                                INSERT INTO historial (fecha, perfume, socio, tipo_movimiento, monto_ingreso_ars, id_producto, presentacion, cantidad)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (
                                f_actual, 
                                nom_item_senia, 
                                socio_senia_sel, 
                                f"📌 SEÑA recibida de {cli_senia_nom.strip()}", 
                                monto_senia_val, 
                                int(p_data_sen['id']), 
                                pres_senia_sel, 
                                1
                            ))

                        if agregar_a_orden:
                            f_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            det_res = f"RESERVA/SEÑA: {cli_senia_nom.strip()} [{pres_senia_sel}]"
                            costo_u = float(p_data_sen.get("costo_usd", 0.0))
                            
                            c.execute('''
                                INSERT INTO ordenes_compra (fecha, nombre, capacidad_ml, cantidad, costo_usd, estado_inventario, detalle_reserva, socio_agrega)
                                VALUES (?, ?, ?, 1, ?, 'A pedido / Señado', ?, ?)
                            ''', (f_now, p_senia_sel, cap_sen, costo_u, det_res, socio_senia_sel))

                        conn.commit()
                        conn.close()
                        
                        st.success(f"¡El producto quedó registrado como SEÑADO/RESERVADO con éxito!")
                        st.rerun()

                st.markdown("---")
                st.subheader("📋 Productos Actualmente Señados o Reservados (Vista Interna)")
                df_senados_list = df_sen[df_sen["estado"] == "Pedido / Señado"]

                if not df_senados_list.empty:
                    for _, row_sen in df_senados_list.iterrows():
                        col_s_card1, col_s_card2 = st.columns([3, 1])
                        m_entregado = float(row_sen.get('monto_senado_ars', 0))
                        
                        badge_tipo = "📌 SEÑADO" if m_entregado > 0 else "🔒 RESERVADO (SIN PAGO)"
                        monto_txt = fmt_ars(m_entregado) if m_entregado > 0 else "$0 ARS (Sin Seña)"
                        
                        with col_s_card1:
                            st.markdown(f"""
                            <div style="background-color: #291D1A; border-left: 4px solid #8B0000; padding: 12px; border-radius: 6px; margin-bottom: 8px;">
                                <div style="font-size: 1.1rem; font-weight: bold; color: #FFFFFF;">{row_sen['nombre']} <span style="font-size:0.8rem; color:#D4AF37;">[{badge_tipo}]</span></div>
                                <div>👤 <b>Cliente:</b> {row_sen.get('cliente_senado', 'Cliente')} | 📌 <b>Socio:</b> {row_sen.get('socio_asignado', 'Socio')}</div>
                                <div>💵 <b>Monto Entregado:</b> <span style="color:#E5C158; font-weight:bold;">{monto_txt}</span></div>
                            </div>
                            """, unsafe_allow_html=True)
                        with col_s_card2:
                            chk_liberar = st.checkbox("⚠️ ¿Confirmar liberación?", key=f"chk_unmark_{row_sen['id']}")
                            if st.button(f"🔓 Liberar Producto", key=f"btn_unmark_{row_sen['id']}"):
                                if chk_liberar:
                                    conn = sqlite3.connect('inventario.db')
                                    c = conn.cursor()
                                    c.execute("UPDATE stock SET estado = 'En Stock', socio_asignado = '', monto_senado_ars = 0, cliente_senado = '' WHERE id = ?", (row_sen['id'],))
                                    c.execute("DELETE FROM ordenes_compra WHERE nombre = ? AND estado_inventario LIKE '%Señado%'", (row_sen['nombre'],))
                                    conn.commit()
                                    conn.close()
                                    st.success("Reserva/Seña liberada y removida de la Orden de Compra.")
                                    st.rerun()
                                else:
                                    st.warning("Marca la casilla para confirmar.")
                else:
                    st.caption("No hay productos señados ni reservados en este momento.")

        # --- SECCIÓN: STOCK Y PRECIOS ---
        elif seccion_admin == "📦 Stock & Precios":
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
                    df = df[df["nombre"].astype(str).str.contains(busqueda, case=False, na=False)]
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
                        
                        socio_reserva_html = ""
                        if r['estado'] == "Pedido / Señado":
                            m_sen = float(r.get('monto_senado_ars', 0))
                            cli_sen = r.get('cliente_senado', 'Cliente')
                            socio_reserva_html = f'<div style="color: #FF6B6B; font-weight: bold; margin-top: 4px; font-size: 0.85rem;">📌 SEÑADO/RESERVADO POR: {cli_sen} (Socio: {r.get("socio_asignado", "-")}) - {fmt_ars(m_sen)}</div>'

                        card_admin_html = f'<div class="perfume-card"><div class="perfume-title">{r["nombre"]}</div><span class="perfume-badge">{r["estado"]}</span>{tipo_str}{gen_str}{socio_reserva_html}{notas_str}<div style="margin-top: 8px;"><div><b>Frasco ({cap}ml):</b> <span class="perfume-price">{p_100_card}</span> <small>({r["botellas_100ml_cerradas"]} un)</small></div><div><b>Decants 10ml Listos:</b> <span class="perfume-price">{p_dec_card}</span> <small>({r["decants_10ml_preparados"]} un en stock)</small></div><div style="font-size: 0.8rem; color: #999; margin-top: 4px;">Costo USD: ${r["costo_usd"]:.2f}</div></div></div>'
                        st.markdown(card_admin_html, unsafe_allow_html=True)
                else:
                    df_display = df.copy()
                    df_display["precio_100ml_formatted"] = df_display["precio_venta_100ml_ars"].apply(fmt_ars)
                    df_display["precio_10ml_formatted"] = df_display["precio_venta_decant_10ml_ars"].apply(fmt_ars)
                    df_display["Reserva_Socio"] = df_display.apply(
                        lambda row: f"{row['cliente_senado']} ({fmt_ars(row['monto_senado_ars'])})" if row['estado'] == "Pedido / Señado" else "-", axis=1
                    )
                    
                    df_display = df_display.rename(columns={
                        "id": "ID", "nombre": "Perfume", "genero": "Género", "tipo": "Marca / Categoría", "capacidad_ml": "Vol (ml)", "estado": "Estado",
                        "botellas_100ml_cerradas": "Frascos", "decants_10ml_preparados": "Decants Stock", "costo_usd": "USD",
                        "precio_100ml_formatted": "Precio Frasco", "precio_10ml_formatted": "Precio 10ml",
                        "Reserva_Socio": "Señado/Reservado Por"
                    })
                    st.dataframe(df_display[["ID", "Perfume", "Género", "Marca / Categoría", "Vol (ml)", "Estado", "Señado/Reservado Por", "Frascos", "Decants Stock", "Precio Frasco", "Precio 10ml"]], use_container_width=True)
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
                socio_presupuesto = st.selectbox(
                    "👤 Socio Vendedor (Obligatorio):", 
                    options=SOCIOS, 
                    index=SOCIOS.index(st.session_state.socio_autenticado)
                )

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
                    
                p_sel = st.selectbox("Perfume:", df_p["nombre"].tolist())
                p_data_temp = df_p[df_p["nombre"] == p_sel].iloc[0]
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
                    
                    tipo_descuento = st.radio(
                        "Tipo de Descuento General a aplicar:",
                        ["Sin Descuento Extra", "Monto Fijo Manual ($ ARS)", "Descuento en Lista (%)", "Porcentaje Personalizado (%)"],
                        horizontal=True
                    )
                    
                    monto_desc_pres = 0.0
                    
                    if tipo_descuento == "Descuento en Lista (%)":
                        pct_desc = st.selectbox("Selecciona Porcentaje:", [0, 5, 10, 15, 20], index=0)
                        monto_desc_pres = subtotal_pres * (pct_desc / 100.0)
                    elif tipo_descuento == "Monto Fijo Manual ($ ARS)":
                        monto_manual = st.number_input("Ingresa monto en Pesos ($ ARS):", min_value=0.0, max_value=float(subtotal_pres), value=0.0, step=500.0)
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
                socio_vendedor_real = st.selectbox(
                    "👤 Socio Vendedor que realizó la venta (Obligatorio):", 
                    options=SOCIOS, 
                    index=SOCIOS.index(st.session_state.socio_autenticado)
                )

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

                p_sel_v = st.selectbox("Perfume a vender:", df_actual["nombre"].tolist())
                p_data_v = df_actual[df_actual["nombre"] == p_sel_v].iloc[0]
                cap_v = limpiar_int_ml(p_data_v.get("capacidad_ml", 100), 100)

                with st.form("form_item_venta"):
                    st.subheader("➕ Agregar Perfume / Decant a la Venta")
                    col_vi1, col_vi2 = st.columns([2, 1])
                    with col_vi1:
                        pres_sel_v = st.selectbox("Presentación:", [f"Frasco Cerrado ({cap_v}ml)", "Decant 10ml (Listo)", "Descontar 10ml de frasco abierto"])
                    with col_vi2:
                        cant_sel_v = st.number_input("Cantidad unidades:", min_value=1, value=1, step=1)
                        desc_ind_v = st.number_input("Descuento Individual a este producto ($ ARS):", min_value=0.0, value=0.0, step=500.0)
                        dias_estimados_uso = st.selectbox("⏱️ Tiempo estimado de uso para recordatorio:", [1, 30, 60, 90, 120, 180], index=3)
                        
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
                    tipo_desc_v = st.radio(
                        "Tipo de Descuento General:",
                        ["Sin Descuento Extra", "Monto Fijo en Pesos ($ ARS)", "Porcentaje Personalizado (%)"],
                        horizontal=True
                    )
                    
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
                            conn = sqlite3.connect('inventario.db')
                            c = conn.cursor()
                            fecha_actual = datetime.now()
                            fecha_actual_str = fecha_actual.strftime("%Y-%m-%d %H:%M:%S")

                            factor_descuento = (total_v / subtotal_v) if subtotal_v > 0 else 1.0

                            for item in st.session_state.items_venta:
                                id_p = item["id_producto"]
                                cap_prod = item.get("capacidad_ml", 100)
                                c.execute("SELECT botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, capacidad_ml FROM stock WHERE id = ?", (id_p,))
                                row_stock = c.fetchone()
                                
                                if row_stock:
                                    botellas, ml, decants, cap_tot = row_stock
                                    cap_tot = limpiar_int_ml(cap_tot, 100)
                                    cant = item["cantidad"]
                                    pres = item["presentacion"]

                                    monto_cobrado_real_item = redondear_monto(item['subtotal'] * factor_descuento, 100)

                                    if "Frasco" in pres:
                                        nuevas_botellas = max(0, botellas - cant)
                                        if nuevas_botellas > 0 or decants > 0 or ml >= 10:
                                            nuevo_est = "En Stock"
                                        else:
                                            nuevo_est = "A pedido"
                                            
                                        c.execute('''
                                            UPDATE stock 
                                            SET botellas_100ml_cerradas = ?, estado = ?, monto_senado_ars = 0, cliente_senado = '', socio_asignado = '' 
                                            WHERE id = ?
                                        ''', (nuevas_botellas, nuevo_est, id_p))

                                    elif "Listo" in pres:
                                        nuevos_decants = max(0, decants - cant)
                                        if nuevos_decants > 0 or botellas > 0 or ml >= 10:
                                            nuevo_est = "En Stock"
                                        else:
                                            nuevo_est = "A pedido"
                                            
                                        c.execute('''
                                            UPDATE stock 
                                            SET decants_10ml_preparados = ?, estado = ?, monto_senado_ars = 0, cliente_senado = '', socio_asignado = '' 
                                            WHERE id = ?
                                        ''', (nuevos_decants, nuevo_est, id_p))

                                    elif "abierto" in pres:
                                        ml_necesarios = cant * 10
                                        if ml >= ml_necesarios:
                                            nuevos_ml = ml - ml_necesarios
                                            if nuevos_ml >= 10 or botellas > 0 or decants > 0:
                                                nuevo_est = "En Stock"
                                            else:
                                                nuevo_est = "A pedido"
                                            c.execute("UPDATE stock SET ml_disponibles_abiertos = ?, estado = ?, monto_senado_ars = 0, cliente_senado = '', socio_asignado = '' WHERE id = ?", (nuevos_ml, nuevo_est, id_p))
                                        elif botellas > 0:
                                            nuevas_bot = botellas - 1
                                            nuevos_ml = ml + cap_tot - ml_necesarios
                                            nuevo_est = "En Stock" if (nuevas_bot > 0 or decants > 0 or nuevos_ml >= 10) else "A pedido"
                                            c.execute("UPDATE stock SET botellas_100ml_cerradas = ?, ml_disponibles_abiertos = ?, estado = ? WHERE id = ?", (nuevas_bot, nuevos_ml, nuevo_est, id_p))

                                    info_cli = f"Cliente: {cliente_venta}" + (f" (Cel: {celular_venta})" if celular_venta else "")
                                    
                                    c.execute('''
                                        INSERT INTO historial (fecha, perfume, socio, tipo_movimiento, monto_ingreso_ars, id_producto, presentacion, cantidad) 
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                    ''', (fecha_actual_str, item['nombre'], socio_vendedor_real, f"{pres} (x{cant}) - {info_cli}", monto_cobrado_real_item, id_p, pres, cant))

                                    dias_u = item.get("dias_estimados", 90)
                                    fecha_rec = (fecha_actual + timedelta(days=dias_u)).strftime("%Y-%m-%d")
                                    c.execute('''
                                        INSERT INTO clientes_seguimiento (fecha_compra, cliente_nombre, cliente_celular, socio_vendedor, perfume, presentacion, dias_estimados, fecha_recordatorio, estado)
                                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pendiente')
                                    ''', (fecha_actual.strftime("%Y-%m-%d"), cliente_venta, celular_venta, socio_vendedor_real, item['nombre'], pres, dias_u, fecha_rec))

                            conn.commit()
                            conn.close()
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
                                conn = sqlite3.connect('inventario.db')
                                c = conn.cursor()
                                c.execute("UPDATE clientes_seguimiento SET estado = 'Contactado' WHERE id = ?", (row_c['id'],))
                                conn.commit()
                                conn.close()
                                st.rerun()

                            confirm_del_seg = st.checkbox("⚠️ ¿Confirmar eliminación?", key=f"chk_del_seg_{row_c['id']}")
                            if st.button(f"🗑️ Eliminar", key=f"btn_del_seg_{row_c['id']}"):
                                if confirm_del_seg:
                                    conn = sqlite3.connect('inventario.db')
                                    c = conn.cursor()
                                    c.execute("DELETE FROM clientes_seguimiento WHERE id = ?", (row_c['id'],))
                                    conn.commit()
                                    conn.close()
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
                                    conn = sqlite3.connect('inventario.db')
                                    c = conn.cursor()
                                    c.execute("DELETE FROM clientes_seguimiento WHERE id = ?", (row_p['id'],))
                                    conn.commit()
                                    conn.close()
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
                        conn = sqlite3.connect('inventario.db')
                        c = conn.cursor()
                        f_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        c.execute("INSERT INTO egresos (fecha, categoria, descripcion, monto_ars, socio_registra) VALUES (?, ?, ?, ?, ?)",
                                  (f_hoy, cat_gasto, desc_gasto, monto_gasto, socio_gasto))
                        conn.commit()
                        conn.close()
                        st.success("¡Gasto registrado con éxito!")
                        st.rerun()

            st.markdown("---")
            st.subheader("📅 Filtro de Fecha y Socio para Reportes Contables")

            col_cf1, col_cf2 = st.columns([2, 1])
            with col_cf1:
                tipo_filtro_f = st.radio(
                    "Selecciona Período a consultar:",
                    ["Todo el Histórico", "Por Mes / Año", "Por Día Específico", "Rango de Fechas"],
                    horizontal=True
                )
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

            # Aplicar filtro por socio en ventas
            if socio_filtro_contable != "Todos los Socios":
                if not df_h_filt.empty and "socio" in df_h_filt.columns:
                    df_h_filt = df_h_filt[df_h_filt["socio"] == socio_filtro_contable]

            total_ingresos = df_h_filt["monto_ingreso_ars"].sum() if not df_h_filt.empty and "monto_ingreso_ars" in df_h_filt.columns else 0.0
            total_egresos = df_e_filt["monto_ars"].sum() if not df_e_filt.empty and "monto_ars" in df_e_filt.columns else 0.0
            ganancia_neta = total_ingresos - total_egresos
            cant_ventas = len(df_h_filt) if not df_h_filt.empty else 0

            st.markdown("---")
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("🟢 Ingresos (Ventas y Señas)", fmt_ars(total_ingresos))
            with col_m2:
                st.metric("🔴 Egresos (Gastos)", fmt_ars(total_egresos))
            with col_m3:
                st.metric("🏆 GANANCIA NETA", fmt_ars(ganancia_neta))
            with col_m4:
                st.metric("🛒 Cantidad Ventas", str(cant_ventas))

            st.markdown("---")
            pdf_contable_bytes = generar_pdf_reporte_contable(socio_filtro_contable, periodo_txt, df_h_filt, df_e_filt, total_ingresos, total_egresos, ganancia_neta)
            st.download_button(
                label="📄 Descargar Reporte Contable Completo (PDF)",
                data=pdf_contable_bytes,
                file_name=f"Reporte_Contable_Storia_{socio_filtro_contable.replace(' ', '_')}.pdf",
                mime="application/pdf"
            )

            st.markdown("---")
            col_tab1, col_tab2 = st.columns(2)
            with col_tab1:
                st.subheader("🔴 Egresos del Período")
                if not df_e_filt.empty:
                    st.dataframe(df_e_filt[["fecha", "categoria", "descripcion", "monto_ars", "socio_registra"]], use_container_width=True)
                else:
                    st.caption("Sin gastos en este período.")

            with col_tab2:
                st.subheader("🟢 Ventas del Período")
                if not df_h_filt.empty:
                    st.dataframe(df_h_filt[["fecha", "perfume", "tipo_movimiento", "socio", "monto_ingreso_ars"]], use_container_width=True)
                else:
                    st.caption("Sin ventas en este período.")

        # --- SECCIÓN: ORDEN DE COMPRA PROVEEDOR ---
        elif seccion_admin == "📦 Orden de Compra Proveedor":
            st.header("📦 Generar Orden de Compra para Proveedor")
            st.info("💡 Todos los ítems cargados aquí quedan guardados en la base de datos compartida entre socios.")

            dolar_proveedor = st.number_input(
                "💵 Cotización Dólar del Proveedor ($ ARS):",
                min_value=1.0,
                value=float(dolar_hoy),
                step=10.0,
                help="Esta cotización aplica solo para esta Orden de Compra y no cambia la cotización general del sistema."
            )

            df_st_oc = cargar_datos_stock()

            tab_oc1, tab_oc2 = st.tabs(["📌 Seleccionar de Stock / Inventario", "➕ Agregar Producto Nuevo (Fuera de Inventario)"])

            with tab_oc1:
                if not df_st_oc.empty:
                    p_oc_sel = st.selectbox("Seleccionar perfume del Inventario:", df_st_oc["nombre"].tolist())
                    p_data_oc = df_st_oc[df_st_oc["nombre"] == p_oc_sel].iloc[0]
                    cap_oc = limpiar_int_ml(p_data_oc.get("capacidad_ml", 100), 100)

                    with st.form("form_add_oc_stock", clear_on_submit=True):
                        col_oc1, col_oc2 = st.columns([2, 1])
                        with col_oc1:
                            est_inv = p_data_oc.get("estado", "En Stock")
                            det_reserva = ""
                            if est_inv == "Pedido / Señado":
                                cli_s = p_data_oc.get("cliente_senado", "")
                                det_reserva = f"RESERVA/SEÑA: {cli_s}"
                                st.caption(f"📌 **Estado Actual:** {est_inv} - {det_reserva}")
                            else:
                                st.caption(f"📌 **Estado Actual:** {est_inv}")
                                
                        with col_oc2:
                            cant_oc = st.number_input("Cantidad a pedir:", min_value=1, value=1, step=1)
                            costo_override = st.number_input("Costo USD (Lista Proveedor):", min_value=0.0, value=float(p_data_oc["costo_usd"]), step=1.0)
                        
                        btn_oc_add = st.form_submit_button("➕ Agregar a la Orden de Compra")
                        if btn_oc_add:
                            conn = sqlite3.connect('inventario.db')
                            c = conn.cursor()
                            f_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            c.execute('''
                                INSERT INTO ordenes_compra (fecha, nombre, capacidad_ml, cantidad, costo_usd, estado_inventario, detalle_reserva, socio_agrega)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (f_now, p_oc_sel, cap_oc, cant_oc, costo_override, est_inv, det_reserva, st.session_state.socio_autenticado))
                            conn.commit()
                            conn.close()
                            st.success(f"¡{p_oc_sel} agregado a la Orden de Compra!")
                            st.rerun()

            with tab_oc2:
                with st.form("form_add_oc_nuevo", clear_on_submit=True):
                    col_ocn1, col_ocn2 = st.columns(2)
                    with col_ocn1:
                        nom_nuevo_oc = st.text_input("Nombre del nuevo perfume:")
                        cap_nuevo_oc = st.number_input("Capacidad ML:", min_value=10, value=100, step=5)
                    with col_ocn2:
                        cant_nuevo_oc = st.number_input("Cantidad a pedir:", min_value=1, value=1, step=1)
                        costo_nuevo_oc = st.number_input("Costo USD unidad:", min_value=0.0, value=0.0, step=1.0)
                    
                    btn_oc_nuevo_add = st.form_submit_button("➕ Agregar Producto Nuevo")
                    if btn_oc_nuevo_add and nom_nuevo_oc.strip() != "":
                        conn = sqlite3.connect('inventario.db')
                        c = conn.cursor()
                        f_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        c.execute('''
                            INSERT INTO ordenes_compra (fecha, nombre, capacidad_ml, cantidad, costo_usd, estado_inventario, detalle_reserva, socio_agrega)
                            VALUES (?, ?, ?, ?, ?, 'Nuevo', '', ?)
                        ''', (f_now, nom_nuevo_oc.strip(), int(cap_nuevo_oc), cant_nuevo_oc, costo_nuevo_oc, st.session_state.socio_autenticado))
                        conn.commit()
                        conn.close()
                        st.success(f"¡{nom_nuevo_oc.strip()} agregado a la Orden de Compra!")
                        st.rerun()

            df_oc_saved = cargar_ordenes_compra()

            if not df_oc_saved.empty:
                st.markdown("---")
                st.subheader("📝 Lista Compartida de Orden de Compra")

                df_oc_saved["subtotal_usd"] = df_oc_saved["costo_usd"] * df_oc_saved["cantidad"]
                df_oc_saved["costo_ars_prov"] = df_oc_saved["subtotal_usd"] * dolar_proveedor
                df_oc_saved["precio_sugerido_ars"] = df_oc_saved["costo_usd"].apply(
                    lambda c: redondear_monto((c * dolar_proveedor) * (1 + (margen_100_gen / 100)), 100)
                )

                for idx, row_oc in df_oc_saved.iterrows():
                    col_oc_i1, col_oc_i2 = st.columns([3, 1])
                    cap_ml_clean = limpiar_int_ml(row_oc['capacidad_ml'], 100)
                    with col_oc_i1:
                        est_badge = f"<b>[{row_oc['estado_inventario']}]</b>"
                        det_res = f" - <span style='color:#FF6B6B;'>{row_oc['detalle_reserva']}</span>" if row_oc['detalle_reserva'] else ""
                        st.markdown(f"""
                        <div style="background-color: #291D1A; padding: 10px; border-radius: 6px; margin-bottom: 6px; border-left: 3px solid #D4AF37;">
                            <b>{row_oc['nombre']}</b> ({cap_ml_clean}ml) x {row_oc['cantidad']} un | {est_badge}{det_res}<br>
                            <small>Costo USD: <b>${row_oc['costo_usd']:.2f}</b> | Subtotal USD: <b>${row_oc['subtotal_usd']:.2f}</b> | Costo ARS Prov: <b>{fmt_ars(row_oc['costo_ars_prov'])}</b> | PVP Sugerido: <b>{fmt_ars(row_oc['precio_sugerido_ars'])}</b> | Creado por: {row_oc['socio_agrega']}</small>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_oc_i2:
                        confirm_del_oc = st.checkbox("⚠️ ¿Confirmar eliminación?", key=f"chk_del_oc_{row_oc['id']}")
                        if st.button("🗑️ Eliminar", key=f"btn_del_oc_{row_oc['id']}"):
                            if confirm_del_oc:
                                conn = sqlite3.connect('inventario.db')
                                c = conn.cursor()
                                c.execute("DELETE FROM ordenes_compra WHERE id = ?", (row_oc['id'],))
                                conn.commit()
                                conn.close()
                                st.rerun()
                            else:
                                st.warning("Marca la casilla para confirmar.")

                tot_usd_oc = df_oc_saved["subtotal_usd"].sum()
                tot_ars_oc = tot_usd_oc * dolar_proveedor

                st.markdown("---")
                col_octot1, col_octot2 = st.columns(2)
                with col_octot1:
                    st.metric("Total Estimado USD", f"${tot_usd_oc:.2f} USD")
                with col_octot2:
                    st.metric("Total Estimado ARS (Dólar Prov.)", fmt_ars(tot_ars_oc))

                pdf_oc_bytes = generar_pdf_orden_compra(st.session_state.socio_autenticado, df_oc_saved, tot_usd_oc, tot_ars_oc, dolar_proveedor)

                col_ocbtn1, col_ocbtn2 = st.columns(2)
                with col_ocbtn1:
                    st.download_button(
                        label="📄 Descargar Orden de Compra (PDF)",
                        data=pdf_oc_bytes,
                        file_name=f"Orden_Compra_Storia_{datetime.now().strftime('%d_%m_%Y')}.pdf",
                        mime="application/pdf"
                    )
                with col_ocbtn2:
                    confirm_vaciar_oc = st.checkbox("⚠️ ¿Confirmar eliminación?", key="chk_vaciar_oc_all")
                    if st.button("🚨 Vaciar Orden de Compra Completa"):
                        if confirm_vaciar_oc:
                            conn = sqlite3.connect('inventario.db')
                            c = conn.cursor()
                            c.execute("DELETE FROM ordenes_compra")
                            conn.commit()
                            conn.close()
                            st.success("Orden de compra vaciada.")
                            st.rerun()
                        else:
                            st.warning("Marca la casilla para vaciar toda la orden.")
            else:
                st.info("No hay ítems agregados en la orden de compra actual.")

        # --- SECCIÓN: AGREGAR PERFUME ---
        elif seccion_admin == "➕ Agregar Perfume":
            st.header("➕ Cargar Producto Manual")
            with st.form("form_alta", clear_on_submit=True):
                nombre = st.text_input("Nombre del perfume")
                
                col_a1, col_a2, col_a3 = st.columns(3)
                with col_a1:
                    tipo = st.selectbox("Marca / Categoría", CATEGORIAS, index=0)
                with col_a2:
                    genero_sel = st.selectbox("Género", GENEROS, index=0)
                with col_a3:
                    capacidad_ml = st.number_input("Capacidad Total en ML", min_value=10, value=100, step=5)

                estado = st.selectbox("Estado inicial", ESTADOS)
                costo_usd = st.number_input("Costo USD ($)", min_value=0.0, value=0.0, step=1.0)
                
                col_st1, col_st2, col_st3 = st.columns(3)
                with col_st1:
                    botellas = st.number_input("Frascos Cerrados en Stock", min_value=0, value=1 if estado == "En Stock" else 0)
                with col_st2:
                    ml_abiertos = st.number_input("ml Abiertos en Frasco", min_value=0, max_value=int(capacidad_ml), value=0)
                with col_st3:
                    decants = st.number_input("Cantidad Decants 10ml Listos", min_value=0, value=0)
                
                st.markdown("---")
                
                notas_olfativas = st.text_input("Notas Olfativas (Opcional):", placeholder="Ej. Bergamota, Vainilla, Ámbar")
                imagen_url = st.text_input("URL Imagen (Opcional):", placeholder="https://ejemplo.com/foto.jpg")
                
                if st.form_submit_button("Guardar Perfume"):
                    if nombre.strip() != "":
                        conn = sqlite3.connect('inventario.db')
                        c = conn.cursor()
                        c.execute("SELECT id, nombre FROM stock")
                        todos = c.fetchall()
                        nom_norm = normalizar_texto(nombre.strip())
                        encontrado_id = next((item_id for item_id, row_nom in todos if normalizar_texto(row_nom) == nom_norm), None)

                        if encontrado_id:
                            c.execute('''
                                UPDATE stock 
                                SET tipo = ?, genero = ?, capacidad_ml = ?, botellas_100ml_cerradas = ?, ml_disponibles_abiertos = ?, 
                                    decants_10ml_preparados = ?, costo_usd = ?, estado = ?,
                                    notas_olfativas = ?, imagen_url = ?
                                WHERE id = ?
                            ''', (tipo, genero_sel, int(capacidad_ml), botellas, ml_abiertos, decants, costo_usd, estado, notas_olfativas, imagen_url, encontrado_id))
                            st.warning("Producto actualizado sin duplicar.")
                        else:
                            c.execute('''
                                INSERT INTO stock (nombre, tipo, genero, capacidad_ml, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, costo_usd, estado, notas_olfativas, imagen_url)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (nombre.strip(), tipo, genero_sel, int(capacidad_ml), botellas, ml_abiertos, decants, costo_usd, estado, notas_olfativas, imagen_url))
                            st.success("¡Perfume guardado!")
                            
                        conn.commit()
                        conn.close()
                        st.rerun()

        # --- SECCIÓN: CARGAR PDF PROVEEDOR ---
        elif seccion_admin == "📄 Cargar PDF Proveedor":
            st.header("📄 Procesar PDF Proveedor")
            st.info("💡 **Sincronización Inteligente:** Al subir el PDF, si un perfume ya existe se conservará todo su stock y género, actualizando únicamente el costo USD.")
            
            with st.expander("⚙️ Ajustes de Precios Globales"):
                nuevo_dolar = st.number_input("Dólar Sistema (ARS)", value=float(dolar_hoy))
                nuevo_m100 = st.number_input("Margen Frasco %", value=float(margen_100_gen))
                nuevo_mdec = st.number_input("Margen Decant %", value=float(margen_dec_gen))
                nuevo_envase = st.number_input("Envase Decant (ARS)", value=float(costo_envase))
                if st.button("Guardar Configuración"):
                    guardar_config(nuevo_dolar, nuevo_m100, nuevo_mdec, nuevo_envase)
                    st.success("Configuración actualizada.")
                    st.rerun()

            uploaded_pdf = st.file_uploader("Subir PDF de Proveedor", type=["pdf"])

            if uploaded_pdf is not None:
                try:
                    reader = pypdf.PdfReader(uploaded_pdf)
                    texto_completo = "".join([page.extract_text() + "\n" for page in reader.pages])
                    items = []
                    for l in texto_completo.split("\n"):
                        p_nom, p_cost, p_cap = extraer_perfume_y_precio(l)
                        if p_nom and p_cost and len(p_nom) > 2 and p_cost > 3:
                            items.append({"nombre": p_nom, "costo_usd": p_cost, "capacidad_ml": int(p_cap)})

                    if items:
                        df_pdf = pd.DataFrame(items)
                        df_pdf["nombre_norm"] = df_pdf["nombre"].apply(normalizar_texto)
                        df_pdf = df_pdf.drop_duplicates(subset=["nombre_norm"]).drop(columns=["nombre_norm"])
                        st.write(f"Detectados: **{len(df_pdf)}** perfumes únicos en el PDF")
                        st.dataframe(df_pdf, use_container_width=True)

                        if st.button("🚀 Sincronizar Catálogo"):
                            conn = sqlite3.connect('inventario.db')
                            c = conn.cursor()
                            c.execute("SELECT id, nombre FROM stock")
                            dict_existentes = {normalizar_texto(nom): id_bd for id_bd, nom in c.fetchall()}
                            
                            cargados, actualizados = 0, 0
                            for _, r in df_pdf.iterrows():
                                nom_norm = normalizar_texto(r['nombre'])
                                if nom_norm in dict_existentes:
                                    c.execute("UPDATE stock SET costo_usd = ?, capacidad_ml = ? WHERE id = ?", (r['costo_usd'], int(r['capacidad_ml']), dict_existentes[nom_norm]))
                                    actualizados += 1
                                else:
                                    c.execute('''
                                        INSERT INTO stock (nombre, tipo, genero, capacidad_ml, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, costo_usd, estado, socio_asignado)
                                        VALUES (?, '', 'Unisex', ?, 0, 0, 0, ?, 'A pedido', '')
                                    ''', (r['nombre'], int(r['capacidad_ml']), r['costo_usd']))
                                    cargados += 1
                            conn.commit()
                            conn.close()
                            st.success(f"¡Sincronizado! {actualizados} precios/volúmenes actualizados y {cargados} perfumes nuevos agregados.")
                            st.rerun()
                except Exception as e:
                    st.error(f"Error procesando PDF: {e}")

        # --- SECCIÓN: EDITAR / ELIMINAR ---
        elif seccion_admin == "✏️ Editar / Eliminar":
            st.header("✏️ Editar Estado, Género, Stock & Decants")
            df_mod = cargar_datos_stock()

            if not df_mod.empty:
                opciones_mod = [f"ID: {row['id']} | {row['nombre']}" for _, row in df_mod.iterrows()]
                prod_sel = st.selectbox("Selecciona producto a editar:", opciones_mod)
                id_mod = int(prod_sel.split(" | ")[0].replace("ID: ", ""))
                prod_data = df_mod[df_mod['id'] == id_mod].iloc[0]

                val_tipo = prod_data['tipo'] if pd.notnull(prod_data.get('tipo')) and prod_data['tipo'] in CATEGORIAS else ""
                val_gen = prod_data['genero'] if pd.notnull(prod_data.get('genero')) and prod_data['genero'] in GENEROS else "Unisex"
                val_cap = limpiar_int_ml(prod_data.get('capacidad_ml', 100), 100)
                val_decants = int(prod_data.get('decants_10ml_preparados', 0))

                with st.form("form_edicion"):
                    nuevo_nombre = st.text_input("Nombre", value=prod_data['nombre'])
                    
                    col_ed1, col_ed2, col_ed3 = st.columns(3)
                    with col_ed1:
                        nuevo_tipo = st.selectbox("Marca / Categoría", CATEGORIAS, index=CATEGORIAS.index(val_tipo) if val_tipo in CATEGORIAS else 0)
                    with col_ed2:
                        nuevo_genero = st.selectbox("Género", GENEROS, index=GENEROS.index(val_gen) if val_gen in GENEROS else 0)
                    with col_ed3:
                        nueva_capacidad = st.number_input("Capacidad Total en ML", min_value=10, value=val_cap, step=5)

                    nuevo_estado = st.selectbox("Estado", ESTADOS, index=ESTADOS.index(prod_data['estado']) if prod_data['estado'] in ESTADOS else 0)
                    
                    col_ed_s1, col_ed_s2 = st.columns(2)
                    with col_ed_s1:
                        nuevo_costo = st.number_input("Costo USD", value=float(prod_data['costo_usd']))
                    with col_ed_s2:
                        nuevo_margen = st.number_input("Margen Custom %", value=float(prod_data['margen_100ml_custom']) if pd.notnull(prod_data['margen_100ml_custom']) else float(margen_100_gen))

                    col_ed_b1, col_ed_b2, col_ed_b3 = st.columns(3)
                    with col_ed_b1:
                        nbot = st.number_input("Frascos Cerrados en Stock", min_value=0, value=int(prod_data['botellas_100ml_cerradas']))
                    with col_ed_b2:
                        nml = st.number_input("ml Abiertos en Frasco", min_value=0, max_value=int(nueva_capacidad), value=int(prod_data['ml_disponibles_abiertos']))
                    with col_ed_b3:
                        ndec = st.number_input("🧪 Decants 10ml Listos", min_value=0, value=val_decants)
                    
                    val_notas = prod_data['notas_olfativas'] if pd.notnull(prod_data.get('notas_olfativas')) else ""
                    val_img = prod_data['imagen_url'] if pd.notnull(prod_data.get('imagen_url')) else ""
                    
                    nuevas_notas = st.text_input("Notas Olfativas", value=str(val_notas))
                    nueva_img = st.text_input("URL Imagen", value=str(val_img))

                    if st.form_submit_button("💾 Guardar Cambios de Stock"):
                        conn = sqlite3.connect('inventario.db')
                        c = conn.cursor()
                        c.execute('''
                            UPDATE stock
                            SET nombre = ?, tipo = ?, genero = ?, capacidad_ml = ?, estado = ?, costo_usd = ?, margen_100ml_custom = ?,
                                botellas_100ml_cerradas = ?, ml_disponibles_abiertos = ?, decants_10ml_preparados = ?, 
                                notas_olfativas = ?, imagen_url = ?
                            WHERE id = ?
                        ''', (nuevo_nombre, nuevo_tipo, nuevo_genero, int(nueva_capacidad), nuevo_estado, nuevo_costo, nuevo_margen, nbot, nml, ndec, nuevas_notas, nueva_img, id_mod))
                        conn.commit()
                        conn.close()
                        st.success("¡Stock y datos del perfume actualizados correctamente!")
                        st.rerun()

                st.markdown("---")
                confirm_del_prod = st.checkbox("⚠️ ¿Confirmar eliminación?", key=f"chk_del_prod_{id_mod}")
                if st.button(f"🗑️ Eliminar '{prod_data['nombre']}'"):
                    if confirm_del_prod:
                        conn = sqlite3.connect('inventario.db')
                        c = conn.cursor()
                        c.execute("DELETE FROM stock WHERE id = ?", (id_mod,))
                        c.execute("DELETE FROM ordenes_compra WHERE nombre = ?", (prod_data['nombre'],))
                        conn.commit()
                        conn.close()
                        st.success("Perfume eliminado del sistema.")
                        st.rerun()
                    else:
                        st.warning("Marca la casilla '⚠️ ¿Confirmar eliminación?' para borrar este producto.")

            st.markdown("---")
            clave_inv_input = st.text_input("🔑 Clave Master (Vaciar catálogo):", type="password")
            confirm_vaciar_cat = st.checkbox("⚠️ ¿Confirmar eliminación?", key="chk_vaciar_cat_master")
            if st.button("🚨 VACIAR CATALOGO COMPLETO"):
                if clave_inv_input == CLAVE_ADMIN_MASTER and confirm_vaciar_cat:
                    conn = sqlite3.connect('inventario.db')
                    c = conn.cursor()
                    c.execute("DELETE FROM stock")
                    conn.commit()
                    conn.close()
                    st.success("Catálogo vaciado.")
                    st.rerun()
                else:
                    st.error("Clave incorrecta o casilla de confirmación no marcada.")

        # --- SECCIÓN: HISTORIAL ---
        elif seccion_admin == "📜 Historial":
            st.header("📜 Historial de Ventas por Socio & Anulación de Movimientos")
            df_hist = cargar_historial()

            if not df_hist.empty:
                col_hf1, col_hf2 = st.columns([2, 1])
                with col_hf1:
                    busq_hist_p = st.text_input("🔍 Buscar por perfume o cliente:", placeholder="Ej. Khamrah, Juan...")
                with col_hf2:
                    filtro_socio_hist = st.selectbox("👤 Filtrar por Socio:", ["Todos los Socios"] + SOCIOS)

                df_hist_filt = df_hist.copy()

                if busq_hist_p:
                    df_hist_filt = df_hist_filt[
                        df_hist_filt["perfume"].astype(str).str.contains(busq_hist_p, case=False, na=False) |
                        df_hist_filt["tipo_movimiento"].astype(str).str.contains(busq_hist_p, case=False, na=False)
                    ]

                if filtro_socio_hist != "Todos los Socios":
                    df_hist_filt = df_hist_filt[df_hist_filt["socio"] == filtro_socio_hist]

                st.dataframe(df_hist_filt.drop(columns=['id', 'fecha_dt'], errors='ignore'), use_container_width=True)

                pdf_hist_bytes = generar_pdf_historial_ventas(df_hist_filt, filtro_socio_hist)
                st.download_button(
                    label="📄 Descargar Historial de Ventas (PDF)",
                    data=pdf_hist_bytes,
                    file_name=f"Historial_Ventas_Storia_{filtro_socio_hist.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )

                st.markdown("---")
                opciones_hist = [f"ID: {row['id']} | {row['fecha']} - {row['perfume']} ({row['tipo_movimiento']})" for _, row in df_hist.iterrows()]
                reg_sel = st.selectbox("Selecciona movimiento a anular / eliminar:", opciones_hist)
                id_h_del = int(reg_sel.split(" | ")[0].replace("ID: ", ""))

                confirm_anular = st.checkbox("⚠️ ¿Confirmar eliminación?", key=f"chk_anular_hist_{id_h_del}")
                if st.button("🔄 Anular Movimiento & Devolver Stock Automáticamente"):
                    if confirm_anular:
                        conn = sqlite3.connect('inventario.db')
                        c = conn.cursor()
                        
                        c.execute("SELECT id_producto, presentacion, cantidad FROM historial WHERE id = ?", (id_h_del,))
                        res_h = c.fetchone()
                        
                        if res_h:
                            id_p, pres, cant = res_h
                            cant = cant if cant and cant > 0 else 1
                            
                            if id_p and id_p > 0:
                                c.execute("SELECT botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados FROM stock WHERE id = ?", (id_p,))
                                row_p = c.fetchone()
                                
                                if row_p:
                                    bot, ml, dec = row_p
                                    if "Frasco" in str(pres):
                                        c.execute("UPDATE stock SET botellas_100ml_cerradas = ?, estado = 'En Stock' WHERE id = ?", (bot + cant, id_p))
                                    elif "Listo" in str(pres):
                                        c.execute("UPDATE stock SET decants_10ml_preparados = ?, estado = 'En Stock' WHERE id = ?", (dec + cant, id_p))
                                    elif "abierto" in str(pres):
                                        c.execute("UPDATE stock SET ml_disponibles_abiertos = ?, estado = 'En Stock' WHERE id = ?", (ml + (cant * 10), id_p))

                        c.execute("DELETE FROM historial WHERE id = ?", (id_h_del,))
                        conn.commit()
                        conn.close()
                        st.success("¡Movimiento anulado y stock devuelto al inventario automáticamente!")
                        st.rerun()
                    else:
                        st.warning("Marca la casilla para efectuar la anulación.")

                st.markdown("---")
                clave_hist = st.text_input("🔑 Clave Master (Vaciar historial):", type="password")
                confirm_vaciar_hist = st.checkbox("⚠️ ¿Confirmar eliminación?", key="chk_vaciar_hist_master")
                if st.button("🚨 VACIAR HISTORIAL COMPLETO"):
                    if clave_hist == CLAVE_ADMIN_MASTER and confirm_vaciar_hist:
                        conn = sqlite3.connect('inventario.db')
                        c = conn.cursor()
                        c.execute("DELETE FROM historial")
                        conn.commit()
                        conn.close()
                        st.warning("Historial vaciado.")
                        st.rerun()
                    else:
                        st.error("Clave incorrecta o casilla de confirmación no marcada.")
            else:
                st.info("Sin movimientos en el historial.")

        # --- SECCIÓN: COPIA DE SEGURIDAD (BACKUP) ---
        elif seccion_admin == "💾 Copia de Seguridad":
            st.header("💾 Copia de Seguridad y Respaldo")
            st.info("Descarga una copia completa de la base de datos para resguardo.")
            
            try:
                with open("inventario.db", "rb") as fp:
                    backup_bytes = fp.read()
                    
                st.download_button(
                    label="📥 Descargar Base de Datos Completa (.db)",
                    data=backup_bytes,
                    file_name=f"Backup_Storia_Parfums_{datetime.now().strftime('%Y_%m_%d_%H%M')}.db",
                    mime="application/x-sqlite3"
                )
            except FileNotFoundError:
                st.error("Aún no se ha generado la base de datos local.")
                
            st.markdown("---")
            st.subheader("🔄 Restaurar Copia de Seguridad")
            
            uploaded_backup = st.file_uploader("Subir archivo de respaldo (.db):", type=["db"])
            
            if uploaded_backup is not None:
                confirm_restore = st.checkbox("⚠️ ¿Confirmar eliminación?", key="chk_restore_backup_db")
                if st.button("⚠️ Confirmar y Restaurar Base de Datos"):
                    if confirm_restore:
                        with open("inventario.db", "wb") as f:
                            f.write(uploaded_backup.getbuffer())
                        st.success("¡Base de datos restaurada con éxito!")
                        st.rerun()
                    else:
                        st.warning("Marca la casilla para restaurar la base de datos.")
