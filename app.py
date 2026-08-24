import streamlit as st
import sqlite3
import pandas as pd

# Configuración de la página web
st.set_page_config(page_title="Control de Stock - Perfumes & Decants", layout="wide")

# Conexión a la base de datos SQLite
def get_connection():
    conn = sqlite3.connect("inventario_perfumes.db")
    return conn

# Creación de tablas iniciales si no existen
def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tipo TEXT CHECK(tipo IN ('Diseñador', 'Árabe')),
            botellas_100ml_cerradas INTEGER DEFAULT 0,
            ml_disponibles_abiertos INTEGER DEFAULT 0,
            decants_10ml_preparados INTEGER DEFAULT 0,
            socio_asignado TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

st.title("🧪 Perfumes & Decants - Control de Stock")

tab1, tab2, tab3 = st.tabs(["📦 Ver Stock Actual", "➕ Agregar Perfume", "🛒 Registrar Venta/Fraccionamiento"])

# Tab 1: Vista general del stock
with tab1:
    st.header("Inventario Global")
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM stock", conn)
    conn.close()
    
    if not df.empty:
        # Filtros rápidos
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_socio = st.multiselect("Filtrar por Socio:", df["socio_asignado"].unique())
        with col_f2:
            filtro_tipo = st.multiselect("Filtrar por Tipo:", df["tipo"].unique())
            
        if filtro_socio:
            df = df[df["socio_asignado"].isin(filtro_socio)]
        if filtro_tipo:
            df = df[df["tipo"].isin(filtro_tipo)]
            
        st.dataframe(df, use_container_width=True)
    else:
        st.info("Aún no hay perfumes cargados en el inventario.")

# Tab 2: Cargar un perfume nuevo
with tab2:
    st.header("Cargar Nuevo Producto")
    with st.form("form_alta"):
        nombre = st.text_input("Nombre del Perfume y Casa (ej. Afnan Club de Nuit)")
        tipo = st.selectbox("Tipo de Perfume", ["Árabe", "Diseñador"])
        botellas = st.number_input("Botellas 100ml cerradas", min_value=0, value=1, step=1)
        ml_abiertos = st.number_input("ml en frascos ya abiertos para decantar (0 a 100)", min_value=0, max_value=100, value=0)
        decants = st.number_input("Decants 10ml ya preparados", min_value=0, value=0, step=1)
        socio = st.selectbox("Socio a cargo del stock", ["Socio 1", "Socio 2", "Socio 3"])
        
        submitted = st.form_submit_button("Guardar en Stock")
        if submitted:
            if nombre.strip() != "":
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO stock (nombre, tipo, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, socio_asignado)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (nombre, tipo, botellas, ml_abiertos, decants, socio))
                conn.commit()
                conn.close()
                st.success(f"¡{nombre} agregado correctamente!")
                st.rerun()
            else:
                st.error("Por favor, ingresa el nombre del perfume.")

# Tab 3: Registrar salidas
with tab3:
    st.header("Registrar Salida / Venta")
    conn = get_connection()
    df_actual = pd.read_sql_query("SELECT id, nombre, socio_asignado, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados FROM stock", conn)
    conn.close()

    if not df_actual.empty:
        opciones = [f"{row['id']} - {row['nombre']} ({row['socio_asignado']})" for _, row in df_actual.iterrows()]
        seleccion = st.selectbox("Selecciona el producto:", opciones)
        id_producto = int(seleccion.split(" - ")[0])
        
        tipo_venta = st.radio("¿Qué se vendió/descontó?", ["Botella 100ml (Cerrada)", "Decant 10ml (Listo)", "Descontar 10ml de frasco en uso"])
        
        if st.button("Procesar Descuento"):
            conn = get_connection()
            cursor = conn.cursor()
            
            # Obtener datos actuales
            cursor.execute("SELECT botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados FROM stock WHERE id = ?", (id_producto,))
            botellas, ml, decants = cursor.fetchone()
            
            if tipo_venta == "Botella 100ml (Cerrada)":
                if botellas > 0:
                    cursor.execute("UPDATE stock SET botellas_100ml_cerradas = botellas_100ml_cerradas - 1 WHERE id = ?", (id_producto,))
                    st.success("1 Botella de 100ml descontada.")
                else:
                    st.error("No hay botellas cerradas disponibles.")
                    
            elif tipo_venta == "Decant 10ml (Listo)":
                if decants > 0:
                    cursor.execute("UPDATE stock SET decants_10ml_preparados = decants_10ml_preparados - 1 WHERE id = ?", (id_producto,))
                    st.success("1 Decant listo descontado.")
                else:
                    st.error("No hay decants preparados. Usa la opción de descontar de frasco en uso.")
                    
            elif tipo_venta == "Descontar 10ml de frasco en uso":
                if ml >= 10:
                    cursor.execute("UPDATE stock SET ml_disponibles_abiertos = ml_disponibles_abiertos - 10 WHERE id = ?", (id_producto,))
                    st.success("10 ml descontados del frasco abierto.")
                elif botellas > 0:
                    # Abrir nueva botella si la actual no alcanza
                    cursor.execute("""
                        UPDATE stock 
                        SET botellas_100ml_cerradas = botellas_100ml_cerradas - 1,
                            ml_disponibles_abiertos = ml_disponibles_abiertos + 90
                        WHERE id = ?
                    """, (id_producto,))
                    st.warning("Se abrió automáticamente una botella nueva de 100ml y se descontaron los 10ml.")
                else:
                    st.error("Sin mililitros suficientes ni frascos de 100ml cerrados.")
                    
            conn.commit()
            conn.close()
            st.rerun()