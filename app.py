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
# CONFIGURACIÓN DE LA PÁGINA
# ---------------------------------------------------------
st.set_page_config(page_title="Storia Parfums", page_icon="🧪", layout="wide")

st.title("🧪 Storia Parfums - Sistema de Inventario y Ventas")

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

    def execute_query(query, params=()):
        engine = get_engine()
        with engine.begin() as conn:
            if "?" in query and "%s" not in query:
                query = query.replace("?", "%s")
            conn.execute(text(query), params)

    def fetch_df(query, params=()):
        engine = get_engine()
        if "?" in query and "%s" not in query:
            query = query.replace("?", "%s")
        with engine.connect() as conn:
            return pd.read_sql(text(query), conn, params=params if params else None)

    # Inicialización automática de todas las tablas
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS stock (
                id SERIAL PRIMARY KEY,
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

except Exception as e:
    st.error(f"Error detallado al conectar con Supabase: {e}")
    st.stop()

# ---------------------------------------------------------
# CARGA DE CONFIGURACIÓN
# ---------------------------------------------------------
try:
    df_config = fetch_df("SELECT * FROM config WHERE id = 1")
    if not df_config.empty:
        COTIZACION_DOLAR = float(df_config.iloc[0]["cotizacion_dolar"])
        MARGEN_100ML_DEF = float(df_config.iloc[0]["margen_100ml"])
        MARGEN_DECANT_DEF = float(df_config.iloc[0]["margen_decant"])
        COSTO_ENVASE_DECANT = float(df_config.iloc[0]["costo_envase_decant_ars"])
    else:
        COTIZACION_DOLAR = 1200.0
        MARGEN_100ML_DEF = 30.0
        MARGEN_DECANT_DEF = 100.0
        COSTO_ENVASE_DECANT = 800.0
except Exception:
    COTIZACION_DOLAR = 1200.0
    MARGEN_100ML_DEF = 30.0
    MARGEN_DECANT_DEF = 100.0
    COSTO_ENVASE_DECANT = 800.0

# ---------------------------------------------------------
# SELECTOR PRINCIPAL: MODO PÚBLICO VS PANEL DE SOCIOS
# ---------------------------------------------------------
modo_app = st.sidebar.selectbox("Seleccionar Vista", ["Catálogo Público", "Panel de Socios"])

# =========================================================
# 1. CATÁLOGO PÚBLICO
# =========================================================
if modo_app == "Catálogo Público":
    st.header("✨ Catálogo de Perfumes - Storia Parfums")
    st.markdown("Explora nuestra selección de fragancias disponibles y a pedido.")
    
    df_stock = fetch_df("SELECT nombre, tipo, genero, capacidad_ml, estado, notas_olfativas FROM stock ORDER BY nombre ASC")
    
    if df_stock.empty:
        st.info("El catálogo se encuentra actualizándose. ¡Vuelve pronto!")
    else:
        busqueda = st.text_input("🔍 Buscar perfume por nombre:", "")
        if busqueda:
            df_stock = df_stock[df_stock["nombre"].str.contains(busqueda, case=False, na=False)]
            
        st.dataframe(df_stock, use_container_width=True)

# =========================================================
# 2. PANEL DE SOCIOS
# =========================================================
elif modo_app == "Panel de Socios":
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔐 Menú de Socios")
    
    menu_socio = st.sidebar.selectbox(
        "Sección de Gestión",
        [
            "Cargar PDF del Proveedor",
            "Inventario y Stock",
            "Registrar Venta / Movimiento",
            "Órdenes de Compra",
            "Seguimiento de Clientes",
            "Egresos y Gastos",
            "Historial y Finanzas",
            "Configuración del Sistema"
        ]
    )
    
    # -----------------------------------------------------
    # 2.1 CARGAR PDF DEL PROVEEDOR
    # -----------------------------------------------------
    if menu_socio == "Cargar PDF del Proveedor":
        st.header("📄 Carga y Procesamiento de PDF del Proveedor")
        st.markdown("Sube el archivo PDF con la lista de precios y productos de tu proveedor para actualizar el sistema automáticamente.")
        
        archivo_pdf = st.file_uploader("Selecciona el archivo PDF del proveedor", type=["pdf"])
        
        if archivo_pdf is not None:
            with st.spinner("Leyendo y procesando el PDF..."):
                try:
                    lector_pdf = pypdf.PdfReader(archivo_pdf)
                    texto_extraido = ""
                    for pagina in lector_pdf.pages:
                        texto_extraido += pagina.extract_text() + "\n"
                    
                    st.success(f"¡PDF leído con éxito! Total de caracteres extraídos: {len(texto_extraido)}")
                    
                    with st.expander("Ver texto extraído del PDF"):
                        st.text(texto_extraido[:3000])
                        
                    if st.button("Procesar e Importar al Stock"):
                        st.info("Procesador de líneas listo para integrar elementos detectados.")
                except Exception as e:
                    st.error(f"Error al leer el PDF: {e}")

    # -----------------------------------------------------
    # 2.2 INVENTARIO Y STOCK
    # -----------------------------------------------------
    elif menu_socio == "Inventario y Stock":
        st.header("📦 Gestión de Inventario y Stock")
        df_stock = fetch_df("SELECT * FROM stock ORDER BY nombre ASC")
        
        if df_stock.empty:
            st.info("No hay perfumes cargados en el inventario.")
        else:
            st.dataframe(df_stock, use_container_width=True)

        st.subheader("➕ Agregar Nuevo Perfume Manualmente")
        with st.form("form_nuevo_perfume"):
            col1, col2, col3 = st.columns(3)
            with col1:
                n_nombre = st.text_input("Nombre del Perfume")
                n_tipo = st.selectbox("Tipo", ["Diseñador", "Niche / Alternativo", "Árabe"])
            with col2:
                n_genero = st.selectbox("Género", ["Unisex", "Masculino", "Femenino"])
                n_capacidad = st.selectbox("Capacidad Botella (ml)", [100, 50, 75, 30])
            with col3:
                n_costo = st.number_input("Costo en USD (Botella)", min_value=0.0, value=0.0, step=1.0)
                n_estado = st.selectbox("Estado", ["A pedido", "En Stock", "Reservado"])
                
            submitted = st.form_submit_button("Guardar Perfume")
            if submitted:
                if n_nombre:
                    try:
                        execute_query(
                            "INSERT INTO stock (nombre, tipo, genero, capacidad_ml, costo_usd, estado) VALUES (?, ?, ?, ?, ?, ?)",
                            (n_nombre, n_tipo, n_genero, n_capacidad, n_costo, n_estado)
                        )
                        st.success(f"¡Perfume '{n_nombre}' agregado con éxito!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar (nombre duplicado o error de base de datos): {e}")
                else:
                    st.warning("Por favor, ingresa al menos el nombre del perfume.")

    # -----------------------------------------------------
    # 2.3 REGISTRAR VENTA / MOVIMIENTO
    # -----------------------------------------------------
    elif menu_socio == "Registrar Venta / Movimiento":
        st.header("🛒 Registrar Venta o Movimiento de Stock")
        df_stock = fetch_df("SELECT id, nombre, capacidad_ml FROM stock ORDER BY nombre ASC")
        
        if df_stock.empty:
            st.warning("No hay perfumes en el inventario para vender.")
        else:
            perfume_seleccionado = st.selectbox("Seleccionar Perfume", df_stock["nombre"].tolist())
            row_perfume = df_stock[df_stock["nombre"] == perfume_seleccionado].iloc[0]
            
            tipo_movimiento = st.selectbox("Tipo de Movimiento", ["Venta Botella Cerrada", "Venta Decant 10ml", "Fraccionar Botella", "Ingreso Manual"])
            socio = st.selectbox("Socio a cargo", ["Socio A", "Socio B", "Ambos / General"])
            
            monto_ars = st.number_input("Monto Total Cobrado (ARS)", min_value=0.0, value=0.0, step=500.0)
            cantidad = st.number_input("Cantidad", min_value=1, value=1, step=1)
            
            if st.button("Confirmar Movimiento / Venta"):
                fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
                try:
                    execute_query(
                        "INSERT INTO historial (fecha, perfume, socio, tipo_movimiento, monto_ingreso_ars, id_producto, presentacion, cantidad) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (fecha_actual, perfume_seleccionado, socio, tipo_movimiento, monto_ars, int(row_perfume["id"]), tipo_movimiento, int(cantidad))
                    )
                    st.success("¡Transacción registrada con éxito!")
                except Exception as e:
                    st.error(f"Error al registrar: {e}")

    # -----------------------------------------------------
    # 2.4 ÓRDENES DE COMPRA
    # -----------------------------------------------------
    elif menu_socio == "Órdenes de Compra":
        st.header("📋 Órdenes de Compra")
        df_oc = fetch_df("SELECT * FROM ordenes_compra ORDER BY id DESC")
        if df_oc.empty:
            st.info("No hay órdenes de compra registradas.")
        else:
            st.dataframe(df_oc, use_container_width=True)
        
        with st.form("form_oc"):
            c_nombre = st.text_input("Nombre del Perfume / Producto")
            c_cap = st.selectbox("Capacidad (ml)", [100, 50, 30])
            c_cant = st.number_input("Cantidad de unidades", min_value=1, value=1)
            c_costo = st.number_input("Costo Unitario USD", min_value=0.0, value=0.0)
            c_socio = st.text_input("Socio que agrega")
            
            if st.form_submit_button("Crear Orden"):
                fecha_oc = datetime.now().strftime("%Y-%m-%d")
                execute_query(
                    "INSERT INTO ordenes_compra (fecha, nombre, capacidad_ml, cantidad, costo_usd, estado_inventario, socio_agrega) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (fecha_oc, c_nombre, c_cap, c_cant, c_costo, "Pendiente", c_socio)
                )
                st.success("¡Orden de compra creada con éxito!")
                st.rerun()

    # -----------------------------------------------------
    # 2.5 SEGUIMIENTO DE CLIENTES
    # -----------------------------------------------------
    elif menu_socio == "Seguimiento de Clientes":
        st.header("👥 Seguimiento de Clientes")
        df_cli = fetch_df("SELECT * FROM clientes_seguimiento ORDER BY id DESC")
        if df_cli.empty:
            st.info("No hay clientes en seguimiento.")
        else:
            st.dataframe(df_cli, use_container_width=True)

    # -----------------------------------------------------
    # 2.6 EGRESOS Y GASTOS
    # -----------------------------------------------------
    elif menu_socio == "Egresos y Gastos":
        st.header("💸 Control de Egresos y Gastos")
        df_egresos = fetch_df("SELECT * FROM egresos ORDER BY id DESC")
        if df_egresos.empty:
            st.info("No hay egresos registrados.")
        else:
            st.dataframe(df_egresos, use_container_width=True)

        with st.form("form_egreso"):
            e_cat = st.selectbox("Categoría", ["Envíos", "Insumos", "Publicidad", "Otros"])
            e_desc = st.text_input("Descripción")
            e_monto = st.number_input("Monto en ARS", min_value=0.0, value=0.0)
            e_socio = st.text_input("Socio que registra")
            
            if st.form_submit_button("Registrar Egreso"):
                fecha_eg = datetime.now().strftime("%Y-%m-%d")
                execute_query(
                    "INSERT INTO egresos (fecha, categoria, descripcion, monto_ars, socio_registra) VALUES (?, ?, ?, ?, ?)",
                    (fecha_eg, e_cat, e_desc, e_monto, e_socio)
                )
                st.success("¡Egreso guardado con éxito!")
                st.rerun()

    # -----------------------------------------------------
    # 2.7 HISTORIAL Y FINANZAS
    # -----------------------------------------------------
    elif menu_socio == "Historial y Finanzas":
        st.header("📊 Historial de Movimientos y Finanzas")
        df_hist = fetch_df("SELECT * FROM historial ORDER BY id DESC")
        if df_hist.empty:
            st.info("El historial de ventas está vacío.")
        else:
            st.dataframe(df_hist, use_container_width=True)

    # -----------------------------------------------------
    # 2.8 CONFIGURACIÓN DEL SISTEMA
    # -----------------------------------------------------
    elif menu_socio == "Configuración del Sistema":
        st.header("⚙️ Configuración General")
        st.write(f"Cotización actual del dólar: **${COTIZACION_DOLAR} ARS**")
        
        with st.form("form_config"):
            nuevo_dolar = st.number_input("Actualizar Cotización Dólar (ARS)", value=COTIZACION_DOLAR)
            nuevo_m100 = st.number_input("Margen 100ml (%)", value=MARGEN_100ML_DEF)
            nuevo_mdec = st.number_input("Margen Decant (%)", value=MARGEN_DECANT_DEF)
            
            if st.form_submit_button("Guardar Configuración"):
                execute_query(
                    "UPDATE config SET cotizacion_dolar = ?, margen_100ml = ?, margen_decant = ? WHERE id = 1",
                    (nuevo_dolar, nuevo_m100, nuevo_mdec)
                )
                st.success("¡Configuración actualizada!")
                st.rerun()
