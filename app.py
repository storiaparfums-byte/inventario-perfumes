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
# CONEXIÓN A SUPABASE (POOLER)
# ---------------------------------------------------------
try:
    DATABASE_URL = st.secrets["DATABASE_URL"]

    def get_engine():
        url = DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        engine = sa.create_engine(url, pool_pre_ping=True)
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

    # Inicialización automática de todas las tablas del sistema
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

    st.success("¡Conexión exitosa con Supabase y tablas inicializadas correctamente! 🚀")

except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")
    st.stop()

# ---------------------------------------------------------
# INTERFAZ PRINCIPAL DE LA APLICACIÓN
# ---------------------------------------------------------
st.info("El sistema está listo para operar.")
