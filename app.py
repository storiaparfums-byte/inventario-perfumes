import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pypdf
import re
import io

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

# ---------------------------------------------------------
# ESTILOS CSS PERSONALIZADOS (STORIA PARFUMS: MARRÓN & DORADO)
# ---------------------------------------------------------
st.markdown("""
    <style>
    /* Fondo Principal */
    .stApp {
        background-color: #1C1412;
        color: #F3EBE6;
        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
    }
    
    /* Header / Títulos */
    h1, h2, h3 {
        color: #D4AF37 !important;
        font-weight: 300 !important;
        letter-spacing: 1px !important;
    }

    /* Métrica / Stat Cards */
    [data-testid="stMetricValue"] {
        color: #E5C158 !important;
        font-size: 1.5rem !important;
    }
    [data-testid="stMetricLabel"] {
        color: #C5A059 !important;
    }

    /* Tarjetas de Perfumes (Estilo Mobile) */
    .perfume-card {
        background-color: #291D1A;
        border: 1px solid #3D2B27;
        border-left: 4px solid #D4AF37;
        padding: 14px;
        border-radius: 8px;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .perfume-title {
        color: #FFFFFF;
        font-size: 1.1rem;
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
    }
    .perfume-price {
        color: #E5C158;
        font-weight: bold;
        font-size: 1rem;
    }

    /* Botones */
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

    /* Sidebar / Menú Lateral */
    section[data-testid="stSidebar"] {
        background-color: #140E0D !important;
        border-right: 1px solid #291D1A;
    }

    /* Input Fields */
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input {
        background-color: #291D1A !important;
        color: #FFFFFF !important;
        border: 1px solid #4A3530 !important;
        border-radius: 6px !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #291D1A;
        border-radius: 6px;
        color: #C5A059;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #D4AF37 !important;
        color: #1C1412 !important;
        font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

SOCIOS = ["Sebastián", "Franco", "Tomás"]
ESTADOS = ["A pedido", "En Stock", "Pedido / Señado", "Agotado"]
CLAVE_ADMIN = "1234"

# Color Palette para ReportLab PDF
COLOR_BG_PDF = colors.HexColor("#1C1412")
COLOR_GOLD_PDF = colors.HexColor("#D4AF37")
COLOR_TEXT_PDF = colors.HexColor("#333333")

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
            botellas_100ml_cerradas INTEGER,
            ml_disponibles_abiertos INTEGER,
            decants_10ml_preparados INTEGER,
            costo_usd REAL,
            margen_100ml_custom REAL,
            estado TEXT,
            socio_asignado TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            perfume TEXT,
            socio TEXT,
            tipo_movimiento TEXT
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
    conn.commit()
    conn.close()

init_db()

def cargar_datos_stock():
    conn = sqlite3.connect('inventario.db')
    df = pd.read_sql_query("SELECT * FROM stock", conn)
    conn.close()
    return df

def cargar_historial():
    conn = sqlite3.connect('inventario.db')
    df = pd.read_sql_query("SELECT * FROM historial ORDER BY id DESC", conn)
    conn.close()
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
    linea_limpia = re.sub(r'(?i)\b\d+\s*(ml|gr|oz|un|unid|unidades|edp|edt|parfum)\b', '', linea)
    linea_limpia = re.sub(r'\(\d+\)', '', linea_limpia)
    
    match_precio = re.search(r'\$\s*(\d+[\.\,]?\d*)', linea_limpia)
    if match_precio:
        precio_str = match_precio.group(1)
        idx_precio = linea_limpia.find(match_precio.group(0))
        nombre = linea_limpia[:idx_precio].strip()
        try:
            precio = float(precio_str.replace(",", "."))
            return nombre, precio
        except ValueError:
            return None, None
    else:
        numeros = re.findall(r'\b\d+[\.\,]?\d*\b', linea_limpia)
        if numeros:
            precio_str = numeros[-1]
            idx_num = linea_limpia.rfind(precio_str)
            nombre = linea_limpia[:idx_num].strip()
            nombre = re.sub(r'\s+\d+$', '', nombre)
            try:
                precio = float(precio_str.replace(",", "."))
                return nombre, precio
            except ValueError:
                return None, None
    return None, None

def generar_pdf_catalogo(df_cat):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=22, leading=26, textColor=COLOR_BG_PDF, alignment=1)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=11, leading=14, textColor=colors.HexColor("#777777"), alignment=1)
    
    story.append(Paragraph("STORIA PARFUMS", title_style))
    story.append(Paragraph("Catálogo Oficial de Fragancias", subtitle_style))
    story.append(Spacer(1, 15))
    
    data = [["Perfume", "Tipo", "Estado", "100 ml (ARS)", "Decant 10 ml (ARS)"]]
    for _, row in df_cat.iterrows():
        data.append([
            row["nombre"],
            row["tipo"],
            row["estado"],
            f"${row['precio_100ml']:,.0f}",
            f"${row['precio_decant']:,.0f}"
        ])
        
    t = Table(data, colWidths=[200, 70, 100, 90, 90])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_PDF),
        ('TEXTCOLOR', (0,0), (-1,0), COLOR_GOLD_PDF),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (0,1), (0,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('FONTSIZE', (0,1), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

def generar_pdf_presupuesto(cliente, items, subtotal, descuento, total):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=22, leading=26, textColor=COLOR_BG_PDF)
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor("#555555"))
    
    story.append(Paragraph("STORIA PARFUMS", title_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph(f"<b>Presupuesto para:</b> {cliente}", meta_style))
    story.append(Paragraph(f"<b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", meta_style))
    story.append(Spacer(1, 15))
    
    data = [["Producto", "Presentación", "Cant.", "Precio Unitario", "Subtotal"]]
    for item in items:
        data.append([
            item["nombre"],
            item["presentacion"],
            str(item["cantidad"]),
            f"${item['precio_unitario']:,.0f}",
            f"${item['subtotal']:,.0f}"
        ])
        
    t = Table(data, colWidths=[220, 90, 40, 100, 90])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), COLOR_BG_PDF),
        ('TEXTCOLOR', (0,0), (-1,0), COLOR_GOLD_PDF),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (0,1), (0,-1), 'LEFT'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('PADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))
    
    totales_data = [
        ["Subtotal:", f"${subtotal:,.0f} ARS"],
        ["Descuento Aplicado:", f"-${descuento:,.0f} ARS"],
        ["TOTAL FINAL:", f"${total:,.0f} ARS"]
    ]
    t_tot = Table(totales_data, colWidths=[380, 160])
    t_tot.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,-1), (-1,-1), COLOR_BG_PDF),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_tot)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# INTERFAZ PRINCIPAL CON NAVEGACIÓN AMIGABLE PARA CELULARES
# ---------------------------------------------------------
st.markdown("<h1 style='text-align: center; margin-bottom: 0px;'>S T O R I A</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #C5A059; letter-spacing: 3px; font-size: 0.8rem;'>P A R F U M S</p>", unsafe_allow_html=True)
st.markdown("---")

dolar_hoy, margen_100_gen, margen_dec_gen, costo_envase = cargar_config()

# Navegación Limpia para Celulares en Sidebar / Menú
seccion = st.sidebar.radio(
    "Navegación / Menú",
    [
        "📦 Stock & Precios", 
        "📖 Catálogo Clientes",
        "📋 Crear Presupuesto",
        "🛒 Registrar Venta", 
        "➕ Agregar Perfume", 
        "📄 Cargar PDF Proveedor",
        "✏️ Editar / Eliminar",
        "📜 Historial"
    ]
)

st.sidebar.markdown("---")
st.sidebar.caption(f"💵 Dólar: **${dolar_hoy:,.0f} ARS**")
st.sidebar.caption(f"📈 Margen 100ml: **{margen_100_gen:.0f}%**")
st.sidebar.caption(f"🧪 Margen Decant: **{margen_dec_gen:.0f}%**")

# ---------------------------------------------------------
# SECCIÓN 1: Stock & Precios
# ---------------------------------------------------------
if seccion == "📦 Stock & Precios":
    st.header("📦 Inventario Global")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.metric("Cotización Dólar", f"${dolar_hoy:,.0f} ARS")
    with col_p2:
        st.metric("Envase Decant", f"${costo_envase:,.0f} ARS")

    df = cargar_datos_stock()

    if not df.empty:
        df["costo_usd"] = pd.to_numeric(df["costo_usd"], errors='coerce').fillna(0.0)
        df["estado"] = df["estado"].replace("Disponible en Proveedor", "A pedido").fillna("A pedido")
        df["margen_100ml_custom"] = pd.to_numeric(df["margen_100ml_custom"], errors='coerce')
        df["margen_aplicado"] = df["margen_100ml_custom"].fillna(margen_100_gen)
        
        df["costo_100ml_ars"] = df["costo_usd"] * dolar_hoy
        df["precio_venta_100ml_ars"] = df["costo_100ml_ars"] * (1 + (df["margen_aplicado"] / 100))
        costo_liquido_10ml = df["costo_100ml_ars"] * 0.10
        df["precio_venta_decant_10ml_ars"] = (costo_liquido_10ml + costo_envase) * (1 + (margen_dec_gen / 100))

        busqueda = st.text_input("🔍 Buscar por perfume:", placeholder="Ej. Khamrah, Club de Nuit...")
        
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_estado = st.multiselect("Estado:", df["estado"].unique())
        with col_f2:
            filtro_socio = st.multiselect("Socio:", df["socio_asignado"].unique())

        if busqueda:
            df = df[df["nombre"].astype(str).str.contains(busqueda, case=False, na=False)]
        if filtro_estado:
            df = df[df["estado"].isin(filtro_estado)]
        if filtro_socio:
            df = df[df["socio_asignado"].isin(filtro_socio)]

        modo_vista = st.radio("Vista de Visualización:", ["📱 Tarjetas (Ideal Celular)", "📊 Tabla Completa"], horizontal=True)

        if modo_vista == "📱 Tarjetas (Ideal Celular)":
            for _, r in df.iterrows():
                st.markdown(f"""
                <div class="perfume-card">
                    <div class="perfume-title">{r['nombre']}</div>
                    <span class="perfume-badge">{r['estado']}</span> • <span style="color:#C5A059;">{r['tipo']} ({r['socio_asignado']})</span>
                    <div style="margin-top: 8px;">
                        <div><b>100ml:</b> <span class="perfume-price">${r['precio_venta_100ml_ars']:,.0f} ARS</span> <small>({r['botellas_100ml_cerradas']} un)</small></div>
                        <div><b>Decant 10ml:</b> <span class="perfume-price">${r['precio_venta_decant_10ml_ars']:,.0f} ARS</span> <small>({r['decants_10ml_preparados']} un / {r['ml_disponibles_abiertos']}ml ab.)</small></div>
                        <div style="font-size: 0.8rem; color: #999; margin-top: 4px;">Costo USD: ${r['costo_usd']:.2f}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            df_display = df.rename(columns={
                "id": "ID", "nombre": "Perfume", "tipo": "Tipo", "estado": "Estado",
                "botellas_100ml_cerradas": "100ml", "ml_disponibles_abiertos": "ml Ab.",
                "decants_10ml_preparados": "Decants", "costo_usd": "USD",
                "precio_venta_100ml_ars": "Precio 100ml", "precio_venta_decant_10ml_ars": "Precio 10ml",
                "socio_asignado": "Socio"
            })
            st.dataframe(df_display[["ID", "Perfume", "Estado", "100ml", "Precio 100ml", "Precio 10ml", "Socio"]], use_container_width=True)
    else:
        st.info("No hay perfumes registrados.")

# ---------------------------------------------------------
# SECCIÓN 2: Catálogo Público
# ---------------------------------------------------------
elif seccion == "📖 Catálogo Clientes":
    st.header("📖 Catálogo Público")
    df_cat_base = cargar_datos_stock()
    
    if not df_cat_base.empty:
        df_cat_base["estado"] = df_cat_base["estado"].replace("Disponible en Proveedor", "A pedido")
        df_cat_base = df_cat_base[df_cat_base["estado"].isin(['En Stock', 'A pedido'])]
        
        df_cat_base["orden"] = df_cat_base["estado"].apply(lambda x: 0 if x == "En Stock" else 1)
        df_cat_base = df_cat_base.sort_values(by=["orden", "nombre"]).drop(columns=["orden"])

        df_cat_base["costo_usd"] = pd.to_numeric(df_cat_base["costo_usd"], errors='coerce').fillna(0.0)
        df_cat_base["margen_100ml_custom"] = pd.to_numeric(df_cat_base["margen_100ml_custom"], errors='coerce')
        df_cat_base["margen_aplicado"] = df_cat_base["margen_100ml_custom"].fillna(margen_100_gen)
        
        df_cat_base["costo_ars"] = df_cat_base["costo_usd"] * dolar_hoy
        df_cat_base["precio_100ml"] = df_cat_base["costo_ars"] * (1 + (df_cat_base["margen_aplicado"] / 100))
        df_cat_base["precio_decant"] = ((df_cat_base["costo_ars"] * 0.10) + costo_envase) * (1 + (margen_dec_gen / 100))

        pdf_cat_bytes = generar_pdf_catalogo(df_cat_base)
        st.download_button(
            label="📥 Descargar Catálogo en PDF",
            data=pdf_cat_bytes,
            file_name=f"Catalogo_Storia_Parfums_{datetime.now().strftime('%d_%m_%Y')}.pdf",
            mime="application/pdf"
        )
        st.markdown("---")
        
        for _, r in df_cat_base.iterrows():
            st.markdown(f"""
            <div class="perfume-card">
                <div class="perfume-title">{r['nombre']}</div>
                <span class="perfume-badge">{r['estado']}</span> • <span style="color:#C5A059;">{r['tipo']}</span>
                <div style="margin-top: 6px;">
                    <div>Frasco 100ml: <span class="perfume-price">${r['precio_100ml']:,.0f} ARS</span></div>
                    <div>Decant 10ml: <span class="perfume-price">${r['precio_decant']:,.0f} ARS</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ---------------------------------------------------------
# SECCIÓN 3: Presupuestos
# ---------------------------------------------------------
elif seccion == "📋 Crear Presupuesto":
    st.header("📋 Generar Presupuesto")
    nombre_cliente = st.text_input("Cliente:", value="Cliente")
    df_p = cargar_datos_stock()
    
    if not df_p.empty:
        df_p["costo_usd"] = pd.to_numeric(df_p["costo_usd"], errors='coerce').fillna(0.0)
        df_p["margen_100ml_custom"] = pd.to_numeric(df_p["margen_100ml_custom"], errors='coerce')
        df_p["margen"] = df_p["margen_100ml_custom"].fillna(margen_100_gen)
        
        df_p["precio_100ml"] = (df_p["costo_usd"] * dolar_hoy) * (1 + (df_p["margen"] / 100))
        df_p["precio_decant"] = ((df_p["costo_usd"] * dolar_hoy * 0.10) + costo_envase) * (1 + (margen_dec_gen / 100))
        
        if "items_presupuesto" not in st.session_state:
            st.session_state.items_presupuesto = []
            
        with st.form("form_item_presupuesto"):
            p_sel = st.selectbox("Perfume:", df_p["nombre"].tolist())
            pres_sel = st.selectbox("Presentación:", ["Botella 100ml", "Decant 10ml"])
            cant_sel = st.number_input("Cantidad:", min_value=1, value=1, step=1)
            add_item = st.form_submit_button("➕ Agregar Item")
            
            if add_item:
                p_data = df_p[df_p["nombre"] == p_sel].iloc[0]
                p_unit = p_data["precio_100ml"] if pres_sel == "Botella 100ml" else p_data["precio_decant"]
                st.session_state.items_presupuesto.append({
                    "nombre": p_sel, "presentacion": pres_sel,
                    "cantidad": cant_sel, "precio_unitario": p_unit, "subtotal": p_unit * cant_sel
                })
                st.success(f"Agregado {p_sel}")
                
        if st.session_state.items_presupuesto:
            df_pres_view = pd.DataFrame(st.session_state.items_presupuesto)
            st.dataframe(df_pres_view[["nombre", "presentacion", "cantidad", "subtotal"]], use_container_width=True)
            
            subtotal_pres = df_pres_view["subtotal"].sum()
            pct_desc_pres = st.selectbox("Descuento:", [0, 5, 10, 15, 20])
            monto_desc_pres = subtotal_pres * (pct_desc_pres / 100)
            total_pres = subtotal_pres - monto_desc_pres
            
            st.metric("TOTAL FINAL", f"${total_pres:,.0f} ARS")
            
            pdf_pres_bytes = generar_pdf_presupuesto(nombre_cliente, st.session_state.items_presupuesto, subtotal_pres, monto_desc_pres, total_pres)
            st.download_button(
                label="📄 Descargar Presupuesto PDF",
                data=pdf_pres_bytes,
                file_name=f"Presupuesto_{nombre_cliente}.pdf",
                mime="application/pdf"
            )
            if st.button("🗑️ Limpiar Todo"):
                st.session_state.items_presupuesto = []
                st.rerun()

# ---------------------------------------------------------
# SECCIÓN 4: Registrar Venta
# ---------------------------------------------------------
elif seccion == "🛒 Registrar Venta":
    st.header("🛒 Registrar Venta")
    df_actual = cargar_datos_stock()

    if not df_actual.empty:
        opciones = [f"ID: {row['id']} | {row['nombre']} ({row['socio_asignado']})" for _, row in df_actual.iterrows()]
        seleccion = st.selectbox("Selecciona perfume:", opciones)
        id_producto = int(seleccion.split(" | ")[0].replace("ID: ", ""))

        socio_realiza_venta = st.selectbox("Socio que vende:", SOCIOS)
        tipo_operacion = st.radio("Movimiento:", ["Venta de Botella 100ml (Cerrada)", "Venta de Decant 10ml (Listo)", "Descontar 10ml de frasco abierto (en uso)"])

        if st.button("Confirmar y Descontar Stock"):
            row_idx = df_actual[df_actual['id'] == id_producto].index[0]
            nombre_p = df_actual.loc[row_idx, 'nombre']
            botellas = int(df_actual.loc[row_idx, 'botellas_100ml_cerradas'])
            ml = int(df_actual.loc[row_idx, 'ml_disponibles_abiertos'])
            decants = int(df_actual.loc[row_idx, 'decants_10ml_preparados'])

            exito = False
            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn = sqlite3.connect('inventario.db')
            c = conn.cursor()

            if tipo_operacion == "Venta de Botella 100ml (Cerrada)" and botellas > 0:
                c.execute("UPDATE stock SET botellas_100ml_cerradas = ? WHERE id = ?", (botellas - 1, id_producto))
                exito = True
            elif tipo_operacion == "Venta de Decant 10ml (Listo)" and decants > 0:
                c.execute("UPDATE stock SET decants_10ml_preparados = ? WHERE id = ?", (decants - 1, id_producto))
                exito = True
            elif tipo_operacion == "Descontar 10ml de frasco abierto (en uso)":
                if ml >= 10:
                    c.execute("UPDATE stock SET ml_disponibles_abiertos = ? WHERE id = ?", (ml - 10, id_producto))
                    exito = True
                elif botellas > 0:
                    c.execute("UPDATE stock SET botellas_100ml_cerradas = ?, ml_disponibles_abiertos = ? WHERE id = ?", (botellas - 1, ml + 90, id_producto))
                    exito = True

            if exito:
                c.execute("INSERT INTO historial (fecha, perfume, socio, tipo_movimiento) VALUES (?, ?, ?, ?)",
                          (fecha_actual, nombre_p, socio_realiza_venta, tipo_operacion))
                conn.commit()
                conn.close()
                st.success("¡Venta registrada y stock actualizado!")
                st.rerun()
            else:
                conn.close()
                st.error("Sin stock disponible para esta operación.")

# ---------------------------------------------------------
# SECCIÓN 5: Agregar Perfume
# ---------------------------------------------------------
elif seccion == "➕ Agregar Perfume":
    st.header("➕ Cargar Producto Manual")
    with st.form("form_alta", clear_on_submit=True):
        nombre = st.text_input("Nombre del perfume")
        tipo = st.selectbox("Categoría", ["Árabe", "Diseñador"])
        estado = st.selectbox("Estado", ESTADOS)
        costo_usd = st.number_input("Costo USD ($)", min_value=0.0, value=0.0, step=1.0)
        botellas = st.number_input("Botellas 100ml", min_value=0, value=1 if estado == "En Stock" else 0)
        ml_abiertos = st.number_input("ml Abiertos", min_value=0, max_value=100, value=0)
        decants = st.number_input("Decants 10ml", min_value=0, value=0)
        socio = st.selectbox("Socio a cargo", SOCIOS)
        
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
                        SET tipo = ?, botellas_100ml_cerradas = ?, ml_disponibles_abiertos = ?, 
                            decants_10ml_preparados = ?, costo_usd = ?, estado = ?, socio_asignado = ?
                        WHERE id = ?
                    ''', (tipo, botellas, ml_abiertos, decants, costo_usd, estado, socio, encontrado_id))
                    st.warning("Producto existente actualizado.")
                else:
                    c.execute('''
                        INSERT INTO stock (nombre, tipo, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, costo_usd, estado, socio_asignado)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (nombre.strip(), tipo, botellas, ml_abiertos, decants, costo_usd, estado, socio))
                    st.success("¡Perfume cargado con éxito!")
                    
                conn.commit()
                conn.close()
                st.rerun()

# ---------------------------------------------------------
# SECCIÓN 6: Cargar PDF Proveedor
# ---------------------------------------------------------
elif seccion == "📄 Cargar PDF Proveedor":
    st.header("📄 Procesar PDF Proveedor")
    with st.expander("⚙️ Configuración de Precios"):
        nuevo_dolar = st.number_input("Dólar (ARS)", value=float(dolar_hoy))
        nuevo_m100 = st.number_input("Margen 100ml %", value=float(margen_100_gen))
        nuevo_mdec = st.number_input("Margen Decant %", value=float(margen_dec_gen))
        nuevo_envase = st.number_input("Envase Decant (ARS)", value=float(costo_envase))
        if st.button("Guardar Configuración"):
            guardar_config(nuevo_dolar, nuevo_m100, nuevo_mdec, nuevo_envase)
            st.success("Guardado.")
            st.rerun()

    socio_dest = st.selectbox("Asignar perfumes a:", SOCIOS)
    uploaded_pdf = st.file_uploader("Subir PDF del Proveedor", type=["pdf"])

    if uploaded_pdf is not None:
        try:
            reader = pypdf.PdfReader(uploaded_pdf)
            texto_completo = "".join([page.extract_text() + "\n" for page in reader.pages])
            items = []
            for l in texto_completo.split("\n"):
                p_nom, p_cost = extraer_perfume_y_precio(l)
                if p_nom and p_cost and len(p_nom) > 2 and p_cost > 3:
                    items.append({"nombre": p_nom, "costo_usd": p_cost})

            if items:
                df_pdf = pd.DataFrame(items)
                df_pdf["nombre_norm"] = df_pdf["nombre"].apply(normalizar_texto)
                df_pdf = df_pdf.drop_duplicates(subset=["nombre_norm"]).drop(columns=["nombre_norm"])
                st.write(f"Perfumes detectados: **{len(df_pdf)}**")
                st.dataframe(df_pdf, use_container_width=True)

                if st.button("🚀 Sincronizar con Inventario"):
                    conn = sqlite3.connect('inventario.db')
                    c = conn.cursor()
                    c.execute("SELECT id, nombre FROM stock")
                    dict_existentes = {normalizar_texto(nom): id_bd for id_bd, nom in c.fetchall()}
                    
                    cargados, actualizados = 0, 0
                    for _, r in df_pdf.iterrows():
                        nom_norm = normalizar_texto(r['nombre'])
                        if nom_norm in dict_existentes:
                            c.execute("UPDATE stock SET costo_usd = ? WHERE id = ?", (r['costo_usd'], dict_existentes[nom_norm]))
                            actualizados += 1
                        else:
                            c.execute('''
                                INSERT INTO stock (nombre, tipo, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, costo_usd, estado, socio_asignado)
                                VALUES (?, 'Árabe', 0, 0, 0, ?, 'A pedido', ?)
                            ''', (r['nombre'], r['costo_usd'], socio_dest))
                            cargados += 1
                    conn.commit()
                    conn.close()
                    st.success(f"¡Sincronizado! {cargados} creados y {actualizados} actualizados.")
                    st.rerun()
        except Exception as e:
            st.error(f"Error al leer PDF: {e}")

# ---------------------------------------------------------
# SECCIÓN 7: Editar / Eliminar
# ---------------------------------------------------------
elif seccion == "✏️ Editar / Eliminar":
    st.header("✏️ Editar o Eliminar Perfume")
    df_mod = cargar_datos_stock()

    if not df_mod.empty:
        opciones_mod = [f"ID: {row['id']} | {row['nombre']}" for _, row in df_mod.iterrows()]
        prod_sel = st.selectbox("Selecciona producto:", opciones_mod)
        id_mod = int(prod_sel.split(" | ")[0].replace("ID: ", ""))
        prod_data = df_mod[df_mod['id'] == id_mod].iloc[0]

        with st.form("form_edicion"):
            nuevo_nombre = st.text_input("Nombre", value=prod_data['nombre'])
            nuevo_tipo = st.selectbox("Tipo", ["Árabe", "Diseñador"], index=0 if prod_data['tipo'] == "Árabe" else 1)
            nuevo_estado = st.selectbox("Estado", ESTADOS, index=ESTADOS.index(prod_data['estado']) if prod_data['estado'] in ESTADOS else 0)
            nuevo_costo = st.number_input("Costo USD", value=float(prod_data['costo_usd']))
            nuevo_margen = st.number_input("Margen Custom %", value=float(prod_data['margen_100ml_custom']) if pd.notnull(prod_data['margen_100ml_custom']) else float(margen_100_gen))
            nbot = st.number_input("100ml Cerradas", min_value=0, value=int(prod_data['botellas_100ml_cerradas']))
            nml = st.number_input("ml Abiertos", min_value=0, max_value=100, value=int(prod_data['ml_disponibles_abiertos']))
            ndec = st.number_input("Decants 10ml", min_value=0, value=int(prod_data['decants_10ml_preparados']))
            nuevo_socio = st.selectbox("Socio a cargo", SOCIOS, index=SOCIOS.index(prod_data['socio_asignado']) if prod_data['socio_asignado'] in SOCIOS else 0)

            if st.form_submit_button("Guardar Cambios"):
                conn = sqlite3.connect('inventario.db')
                c = conn.cursor()
                c.execute('''
                    UPDATE stock
                    SET nombre = ?, tipo = ?, estado = ?, costo_usd = ?, margen_100ml_custom = ?,
                        botellas_100ml_cerradas = ?, ml_disponibles_abiertos = ?, decants_10ml_preparados = ?, socio_asignado = ?
                    WHERE id = ?
                ''', (nuevo_nombre, nuevo_tipo, nuevo_estado, nuevo_costo, nuevo_margen, nbot, nml, ndec, nuevo_socio, id_mod))
                conn.commit()
                conn.close()
                st.success("¡Guardado!")
                st.rerun()

        st.markdown("---")
        if st.button(f"🗑️ Eliminar '{prod_data['nombre']}' (Sin clave)"):
            conn = sqlite3.connect('inventario.db')
            c = conn.cursor()
            c.execute("DELETE FROM stock WHERE id = ?", (id_mod,))
            conn.commit()
            conn.close()
            st.success("Eliminado.")
            st.rerun()

    st.markdown("---")
    clave_inv_input = st.text_input("🔑 Clave Admin (Vaciar catálogo):", type="password")
    if st.button("🚨 VACIAR TODO EL CATÁLOGO"):
        if clave_inv_input == CLAVE_ADMIN:
            conn = sqlite3.connect('inventario.db')
            c = conn.cursor()
            c.execute("DELETE FROM stock")
            conn.commit()
            conn.close()
            st.success("Catálogo vaciado.")
            st.rerun()
        else:
            st.error("Clave incorrecta.")

# ---------------------------------------------------------
# SECCIÓN 8: Historial
# ---------------------------------------------------------
elif seccion == "📜 Historial":
    st.header("📜 Historial de Ventas")
    df_hist = cargar_historial()

    if not df_hist.empty:
        st.dataframe(df_hist.drop(columns=['id']), use_container_width=True)
        st.markdown("---")
        
        opciones_hist = [f"ID: {row['id']} | {row['fecha']} - {row['perfume']}" for _, row in df_hist.iterrows()]
        reg_sel = st.selectbox("Eliminar movimiento:", opciones_hist)
        id_h_del = int(reg_sel.split(" | ")[0].replace("ID: ", ""))

        if st.button("❌ Eliminar Movimiento Seleccionado (Sin clave)"):
            conn = sqlite3.connect('inventario.db')
            c = conn.cursor()
            c.execute("DELETE FROM historial WHERE id = ?", (id_h_del,))
            conn.commit()
            conn.close()
            st.success("Movimiento eliminado.")
            st.rerun()

        st.markdown("---")
        clave_hist = st.text_input("🔑 Clave Admin (Vaciar historial):", type="password")
        if st.button("🚨 VACIAR HISTORIAL COMPLETO"):
            if clave_hist == CLAVE_ADMIN:
                conn = sqlite3.connect('inventario.db')
                c = conn.cursor()
                c.execute("DELETE FROM historial")
                conn.commit()
                conn.close()
                st.warning("Historial vaciado.")
                st.rerun()
            else:
                st.error("Clave incorrecta.")
    else:
        st.info("Sin historial aún.")
