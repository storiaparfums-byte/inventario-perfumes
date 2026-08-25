import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import pypdf
import re
import io
import urllib.parse

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
ESTADOS = ["A pedido", "En Stock", "Pedido / Señado", "Agotado"]
CLAVE_ADMIN_MASTER = "1234"

# Función auxiliar para formato ARS sin decimales con punto de miles ($124.497 ARS)
def fmt_ars(monto):
    try:
        return f"${int(round(float(monto))):,}".replace(",", ".") + " ARS"
    except (ValueError, TypeError):
        return "$0 ARS"

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

    /* Tarjetas de Perfumes */
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

    /* Botones y WhatsApp */
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
            botellas_100ml_cerradas INTEGER,
            ml_disponibles_abiertos INTEGER,
            decants_10ml_preparados INTEGER,
            costo_usd REAL,
            margen_100ml_custom REAL,
            estado TEXT,
            socio_asignado TEXT,
            notas_olfativas TEXT,
            imagen_url TEXT
        )
    ''')
    
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
            fmt_ars(row['precio_100ml']),
            fmt_ars(row['precio_decant'])
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
            fmt_ars(item['precio_unitario']),
            fmt_ars(item['subtotal'])
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
        ["Subtotal:", fmt_ars(subtotal)],
        ["Descuento Aplicado:", f"-{fmt_ars(descuento)}"],
        ["TOTAL FINAL:", fmt_ars(total)]
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
# MODO 1: CATÁLOGO PÚBLICO CLIENTE (ACCESO LIBRE)
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
        df_cat_base["margen_100ml_custom"] = pd.to_numeric(df_cat_base["margen_100ml_custom"], errors='coerce')
        df_cat_base["margen_aplicado"] = df_cat_base["margen_100ml_custom"].fillna(margen_100_gen)
        
        df_cat_base["costo_ars"] = df_cat_base["costo_usd"] * dolar_hoy
        df_cat_base["precio_100ml"] = df_cat_base["costo_ars"] * (1 + (df_cat_base["margen_aplicado"] / 100))
        df_cat_base["precio_decant"] = ((df_cat_base["costo_ars"] * 0.10) + costo_envase) * (1 + (margen_dec_gen / 100))

        # --- SELECCIÓN INTERACTIVA DE CONSULTA POR PERFUMES ---
        st.subheader("💡 ¿Te interesa alguna fragancia?")
        st.markdown("<small>Selecciona los perfumes sobre los que quieres consultar y luego presiona el botón del socio con quien desees hablar:</small>", unsafe_allow_html=True)
        
        perfumes_seleccionados = st.multiselect(
            "Selecciona uno o varios perfumes para consultar:",
            options=df_cat_base["nombre"].tolist(),
            placeholder="Escribe o selecciona perfumes..."
        )
        
        # Construcción del mensaje automático de WhatsApp
        if perfumes_seleccionados:
            lista_p_str = ", ".join(perfumes_seleccionados)
            msg_texto = f"Hola! Estaba viendo el catálogo de STORIA PARFUMS y me gustaría consultar disponibilidad y precio sobre: {lista_p_str}."
        else:
            msg_texto = "Hola! Estaba viendo el catálogo web de STORIA PARFUMS y me gustaría hacerles una consulta."
            
        msg_encoded = urllib.parse.quote(msg_texto)

        # Botones Directos de WhatsApp
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
        
        busq_cli = st.text_input("🔍 Buscar perfume en el catálogo:", placeholder="Ej. Khamrah, Club de Nuit...")
        if busq_cli:
            df_cat_base = df_cat_base[df_cat_base["nombre"].astype(str).str.contains(busq_cli, case=False, na=False)]

        for _, r in df_cat_base.iterrows():
            notas_html = f'<div class="perfume-notes">🌸 <b>Notas:</b> {r["notas_olfativas"]}</div>' if pd.notnull(r.get("notas_olfativas")) and str(r.get("notas_olfativas")).strip() != "" else ""
            
            p_100ml_str = fmt_ars(r['precio_100ml'])
            p_decant_str = fmt_ars(r['precio_decant'])

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
                st.markdown(f"""
                <div class="perfume-card">
                    <div class="perfume-title">{r['nombre']}</div>
                    <span class="perfume-badge">{r['estado']}</span> • <span style="color:#C5A059;">{r['tipo']}</span>
                    {notas_html}
                    <div style="margin-top: 6px;">
                        <div>Frasco 100ml: <span class="perfume-price">{p_100ml_str}</span></div>
                        <div>Decant 10ml: <span class="perfume-price">{p_decant_str}</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
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
                "📦 Stock & Precios", 
                "📋 Crear Presupuesto",
                "🛒 Registrar Venta", 
                "➕ Agregar Perfume", 
                "📄 Cargar PDF Proveedor",
                "✏️ Editar / Eliminar",
                "📜 Historial"
            ]
        )

        st.sidebar.caption(f"💵 Dólar: **{fmt_ars(dolar_hoy)}**")

        # --- SECCIÓN: STOCK Y PRECIOS ---
        if seccion_admin == "📦 Stock & Precios":
            st.header("📦 Inventario Global")
            
            col_p1, col_p2 = st.columns(2)
            with col_p1:
                st.metric("Cotización Dólar", fmt_ars(dolar_hoy))
            with col_p2:
                st.metric("Envase Decant", fmt_ars(costo_envase))

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

                busqueda = st.text_input("🔍 Buscar perfume:", placeholder="Ej. Khamrah, Club de Nuit...")
                
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

                modo_vista = st.radio("Modo de Vista:", ["📱 Tarjetas (Ideal Celular)", "📊 Tabla Completa"], horizontal=True)

                if modo_vista == "📱 Tarjetas (Ideal Celular)":
                    for _, r in df.iterrows():
                        notas_str = f"<div><b>Notas:</b> {r['notas_olfativas']}</div>" if pd.notnull(r.get("notas_olfativas")) and str(r.get("notas_olfativas")).strip() != "" else ""
                        p_100_card = fmt_ars(r['precio_venta_100ml_ars'])
                        p_dec_card = fmt_ars(r['precio_venta_decant_10ml_ars'])
                        
                        st.markdown(f"""
                        <div class="perfume-card">
                            <div class="perfume-title">{r['nombre']}</div>
                            <span class="perfume-badge">{r['estado']}</span> • <span style="color:#C5A059;">{r['tipo']} ({r['socio_asignado']})</span>
                            {notas_str}
                            <div style="margin-top: 8px;">
                                <div><b>100ml:</b> <span class="perfume-price">{p_100_card}</span> <small>({r['botellas_100ml_cerradas']} un)</small></div>
                                <div><b>Decant 10ml:</b> <span class="perfume-price">{p_dec_card}</span> <small>({r['decants_10ml_preparados']} un / {r['ml_disponibles_abiertos']}ml ab.)</small></div>
                                <div style="font-size: 0.8rem; color: #999; margin-top: 4px;">Costo USD: ${r['costo_usd']:.2f}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    df_display = df.copy()
                    df_display["precio_100ml_formatted"] = df_display["precio_venta_100ml_ars"].apply(fmt_ars)
                    df_display["precio_10ml_formatted"] = df_display["precio_venta_decant_10ml_ars"].apply(fmt_ars)
                    
                    df_display = df_display.rename(columns={
                        "id": "ID", "nombre": "Perfume", "tipo": "Tipo", "estado": "Estado",
                        "botellas_100ml_cerradas": "100ml", "ml_disponibles_abiertos": "ml Ab.",
                        "decants_10ml_preparados": "Decants", "costo_usd": "USD",
                        "precio_100ml_formatted": "Precio 100ml", "precio_10ml_formatted": "Precio 10ml",
                        "socio_asignado": "Socio"
                    })
                    st.dataframe(df_display[["ID", "Perfume", "Estado", "100ml", "Precio 100ml", "Precio 10ml", "Socio"]], use_container_width=True)
            else:
                st.info("No hay perfumes registrados.")

        # --- SECCIÓN: PRESUPUESTOS ---
        elif seccion_admin == "📋 Crear Presupuesto":
            st.header("📋 Generar Presupuesto")
            nombre_cliente = st.text_input("Cliente / Contacto:", value="Cliente")
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
                    df_pres_view["subtotal_fmt"] = df_pres_view["subtotal"].apply(fmt_ars)
                    st.dataframe(df_pres_view[["nombre", "presentacion", "cantidad", "subtotal_fmt"]].rename(columns={"subtotal_fmt": "Subtotal"}), use_container_width=True)
                    
                    subtotal_pres = df_pres_view["subtotal"].sum()
                    pct_desc_pres = st.selectbox("Descuento Promocional:", [0, 5, 10, 15, 20])
                    monto_desc_pres = subtotal_pres * (pct_desc_pres / 100)
                    total_pres = subtotal_pres - monto_desc_pres
                    
                    st.metric("TOTAL FINAL", fmt_ars(total_pres))
                    
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

        # --- SECCIÓN: REGISTRAR VENTA ---
        elif seccion_admin == "🛒 Registrar Venta":
            st.header("🛒 Registrar Venta")
            df_actual = cargar_datos_stock()

            if not df_actual.empty:
                opciones = [f"ID: {row['id']} | {row['nombre']} ({row['socio_asignado']})" for _, row in df_actual.iterrows()]
                seleccion = st.selectbox("Selecciona perfume:", opciones)
                id_producto = int(seleccion.split(" | ")[0].replace("ID: ", ""))

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
                                  (fecha_actual, nombre_p, st.session_state.socio_autenticado, tipo_operacion))
                        conn.commit()
                        conn.close()
                        st.success("¡Venta registrada con éxito!")
                        st.rerun()
                    else:
                        conn.close()
                        st.error("Sin stock suficiente.")

        # --- SECCIÓN: AGREGAR PERFUME ---
        elif seccion_admin == "➕ Agregar Perfume":
            st.header("➕ Cargar Producto Manual")
            with st.form("form_alta", clear_on_submit=True):
                nombre = st.text_input("Nombre del perfume")
                tipo = st.selectbox("Categoría", ["Árabe", "Diseñador"])
                estado = st.selectbox("Estado", ESTADOS)
                costo_usd = st.number_input("Costo USD ($)", min_value=0.0, value=0.0, step=1.0)
                botellas = st.number_input("Botellas 100ml", min_value=0, value=1 if estado == "En Stock" else 0)
                ml_abiertos = st.number_input("ml Abiertos", min_value=0, max_value=100, value=0)
                decants = st.number_input("Decants 10ml", min_value=0, value=0)
                notas_olfativas = st.text_input("Notas Olfativas (Opcional):", placeholder="Ej. Bergamota, Vainilla, Ámbar")
                imagen_url = st.text_input("URL Imagen (Opcional):", placeholder="https://ejemplo.com/foto.jpg")
                socio = st.selectbox("Socio a cargo", SOCIOS, index=SOCIOS.index(st.session_state.socio_autenticado))
                
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
                                    decants_10ml_preparados = ?, costo_usd = ?, estado = ?, socio_asignado = ?,
                                    notas_olfativas = ?, imagen_url = ?
                                WHERE id = ?
                            ''', (tipo, botellas, ml_abiertos, decants, costo_usd, estado, socio, notas_olfativas, imagen_url, encontrado_id))
                            st.warning("Producto actualizado sin duplicar.")
                        else:
                            c.execute('''
                                INSERT INTO stock (nombre, tipo, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, costo_usd, estado, socio_asignado, notas_olfativas, imagen_url)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', (nombre.strip(), tipo, botellas, ml_abiertos, decants, costo_usd, estado, socio, notas_olfativas, imagen_url))
                            st.success("¡Perfume guardado!")
                            
                        conn.commit()
                        conn.close()
                        st.rerun()

        # --- SECCIÓN: CARGAR PDF PROVEEDOR ---
        elif seccion_admin == "📄 Cargar PDF Proveedor":
            st.header("📄 Procesar PDF Proveedor")
            with st.expander("⚙️ Ajustes de Precios Globales"):
                nuevo_dolar = st.number_input("Dólar (ARS)", value=float(dolar_hoy))
                nuevo_m100 = st.number_input("Margen 100ml %", value=float(margen_100_gen))
                nuevo_mdec = st.number_input("Margen Decant %", value=float(margen_dec_gen))
                nuevo_envase = st.number_input("Envase Decant (ARS)", value=float(costo_envase))
                if st.button("Guardar Configuración"):
                    guardar_config(nuevo_dolar, nuevo_m100, nuevo_mdec, nuevo_envase)
                    st.success("Configuración actualizada.")
                    st.rerun()

            socio_dest = st.selectbox("Asignar perfumes del PDF a:", SOCIOS, index=SOCIOS.index(st.session_state.socio_autenticado))
            uploaded_pdf = st.file_uploader("Subir PDF de Proveedor", type=["pdf"])

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
                        st.write(f"Detectados: **{len(df_pdf)}** perfumes únicos")
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
                    st.error(f"Error procesando PDF: {e}")

        # --- SECCIÓN: EDITAR / ELIMINAR ---
        elif seccion_admin == "✏️ Editar / Eliminar":
            st.header("✏️ Editar o Eliminar Perfumes")
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
                    
                    val_notas = prod_data['notas_olfativas'] if pd.notnull(prod_data.get('notas_olfativas')) else ""
                    val_img = prod_data['imagen_url'] if pd.notnull(prod_data.get('imagen_url')) else ""
                    
                    nuevas_notas = st.text_input("Notas Olfativas", value=str(val_notas))
                    nueva_img = st.text_input("URL Imagen", value=str(val_img))
                    
                    nuevo_socio = st.selectbox("Socio a cargo", SOCIOS, index=SOCIOS.index(prod_data['socio_asignado']) if prod_data['socio_asignado'] in SOCIOS else 0)

                    if st.form_submit_button("Guardar Cambios"):
                        conn = sqlite3.connect('inventario.db')
                        c = conn.cursor()
                        c.execute('''
                            UPDATE stock
                            SET nombre = ?, tipo = ?, estado = ?, costo_usd = ?, margen_100ml_custom = ?,
                                botellas_100ml_cerradas = ?, ml_disponibles_abiertos = ?, decants_10ml_preparados = ?, 
                                socio_asignado = ?, notas_olfativas = ?, imagen_url = ?
                            WHERE id = ?
                        ''', (nuevo_nombre, nuevo_tipo, nuevo_estado, nuevo_costo, nuevo_margen, nbot, nml, ndec, nuevo_socio, nuevas_notas, nueva_img, id_mod))
                        conn.commit()
                        conn.close()
                        st.success("Guardado.")
                        st.rerun()

                st.markdown("---")
                if st.button(f"🗑️ Eliminar '{prod_data['nombre']}'"):
                    conn = sqlite3.connect('inventario.db')
                    c = conn.cursor()
                    c.execute("DELETE FROM stock WHERE id = ?", (id_mod,))
                    conn.commit()
                    conn.close()
                    st.success("Eliminado.")
                    st.rerun()

            st.markdown("---")
            clave_inv_input = st.text_input("🔑 Clave Master (Vaciar catálogo):", type="password")
            if st.button("🚨 VACIAR CATALOGO COMPLETO"):
                if clave_inv_input == CLAVE_ADMIN_MASTER:
                    conn = sqlite3.connect('inventario.db')
                    c = conn.cursor()
                    c.execute("DELETE FROM stock")
                    conn.commit()
                    conn.close()
                    st.success("Catálogo vaciado.")
                    st.rerun()
                else:
                    st.error("Clave incorrecta.")

        # --- SECCIÓN: HISTORIAL ---
        elif seccion_admin == "📜 Historial":
            st.header("📜 Historial de Movimientos")
            df_hist = cargar_historial()

            if not df_hist.empty:
                st.dataframe(df_hist.drop(columns=['id']), use_container_width=True)
                st.markdown("---")
                
                opciones_hist = [f"ID: {row['id']} | {row['fecha']} - {row['perfume']}" for _, row in df_hist.iterrows()]
                reg_sel = st.selectbox("Eliminar movimiento:", opciones_hist)
                id_h_del = int(reg_sel.split(" | ")[0].replace("ID: ", ""))

                if st.button("❌ Eliminar Movimiento Seleccionado"):
                    conn = sqlite3.connect('inventario.db')
                    c = conn.cursor()
                    c.execute("DELETE FROM historial WHERE id = ?", (id_h_del,))
                    conn.commit()
                    conn.close()
                    st.success("Movimiento eliminado.")
                    st.rerun()

                st.markdown("---")
                clave_hist = st.text_input("🔑 Clave Master (Vaciar historial):", type="password")
                if st.button("🚨 VACIAR HISTORIAL COMPLETO"):
                    if clave_hist == CLAVE_ADMIN_MASTER:
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
                st.info("Sin movimientos en el historial.")
