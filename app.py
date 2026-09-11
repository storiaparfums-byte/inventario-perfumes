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
# CONEXIÓN A SUPABASE (POSTGRESQL - VARIABLES SEPARADAS)
# ---------------------------------------------------------
try:
    db_user = st.secrets["DB_USER"]
    db_password = st.secrets["DB_PASSWORD"]
    db_host = st.secrets["DB_HOST"]
    db_port = st.secrets["DB_PORT"]
    db_name = st.secrets["DB_NAME"]

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

    # Inicialización de tablas de prueba rápida
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
    
    st.success("¡Conexión exitosa con la base de datos en Supabase!")

except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")

# ---------------------------------------------------------
# RESTO DE TU APLICACIÓN
# ---------------------------------------------------------
st.info("El sistema está cargando el panel principal...")
