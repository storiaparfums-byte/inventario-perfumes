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
# CONEXIÓN A SUPABASE (POSTGRESQL - VARIABLES SEPARADAS)
# ---------------------------------------------------------
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
