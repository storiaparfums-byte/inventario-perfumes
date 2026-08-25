import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import pypdf
import re

# ---------------------------------------------------------
# Configuración inicial de la página
# ---------------------------------------------------------
st.set_page_config(
    page_title="Control de Stock & Precios - S&F Perfumes",
    page_icon="🧪",
    layout="wide"
)

# 💡 NOMBRES REALES DE LOS SOCIOS Y ESTADOS
SOCIOS = ["Sebastián", "Franco", "Tomás"]
ESTADOS = ["Disponible en Proveedor", "En Stock", "Pedido / Señado", "Agotado"]

# ---------------------------------------------------------
# Conexión y Gestión de Base de Datos SQLite
# ---------------------------------------------------------
def get_connection():
    conn = sqlite3.connect("inventario_perfumes.db")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # Tabla de Inventario
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            tipo TEXT CHECK(tipo IN ('Diseñador', 'Árabe')),
            botellas_100ml_cerradas INTEGER DEFAULT 0,
            ml_disponibles_abiertos INTEGER DEFAULT 0,
            decants_10ml_preparados INTEGER DEFAULT 0,
            costo_usd REAL DEFAULT 0.0,
            margen_100ml_custom REAL DEFAULT NULL,
            estado TEXT DEFAULT 'Disponible en Proveedor',
            socio_asignado TEXT NOT NULL
        )
    """)
    
    # Migraciones automáticas
    cursor.execute("PRAGMA table_info(stock)")
    columnas = [col[1] for col in cursor.fetchall()]
    if "costo_usd" not in columnas:
        cursor.execute("ALTER TABLE stock ADD COLUMN costo_usd REAL DEFAULT 0.0")
    if "margen_100ml_custom" not in columnas:
        cursor.execute("ALTER TABLE stock ADD COLUMN margen_100ml_custom REAL DEFAULT NULL")
    if "estado" not in columnas:
        cursor.execute("ALTER TABLE stock ADD COLUMN estado TEXT DEFAULT 'Disponible en Proveedor'")
    
    # Tabla de Configuración de Precios / Cotización
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config_precios (
            id INTEGER PRIMARY KEY DEFAULT 1,
            cotizacion_dolar REAL DEFAULT 1200.0,
            margen_100ml REAL DEFAULT 30.0,
            margen_decant REAL DEFAULT 100.0,
            costo_envase_decant_ars REAL DEFAULT 800.0
        )
    """)
    
    cursor.execute("INSERT OR IGNORE INTO config_precios (id, cotizacion_dolar, margen_100ml, margen_decant, costo_envase_decant_ars) VALUES (1, 1200.0, 30.0, 100.0, 800.0)")
    
    # Tabla de Historial
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            perfume TEXT NOT NULL,
            socio TEXT NOT NULL,
            tipo_movimiento TEXT NOT NULL
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# Funciones Auxiliares
# ---------------------------------------------------------
def obtener_config():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT cotizacion_dolar, margen_100ml, margen_decant, costo_envase_decant_ars FROM config_precios WHERE id = 1")
    res = cursor.fetchone()
    conn.close()
    return res if res else (1200.0, 30.0, 100.0, 800.0)

def extraer_perfume_y_precio(linea):
    """Extrae únicamente el nombre y el precio USD ignorando cantidades o unidades"""
    # Limpiar unidades, ml y paréntesis que contengan números de pack/unidades
    linea_limpia = re.sub(r'(?i)\b\d+\s*(ml|gr|oz|un|unid|unidades|edp|edt|parfum)\b', '', linea)
    linea_limpia = re.sub(r'\(\d+\)', '', linea_limpia)
    
    # Buscar patrón de precio con signo $
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
        # Si no hay signo $, toma el último valor numérico válido al final de la línea
        numeros = re.findall(r'\b\d+[\.\,]?\d*\b', linea_limpia)
        if numeros:
            precio_str = numeros[-1]
            idx_num = linea_limpia.rfind(precio_str)
            nombre = linea_limpia[:idx_num].strip()
            # Limpiar posibles números sueltos al final del nombre
            nombre = re.sub(r'\s+\d+$', '', nombre)
            try:
                precio = float(precio_str.replace(",", "."))
                return nombre, precio
            except ValueError:
                return None, None
    return None, None

# ---------------------------------------------------------
# Interfaz Gráfica
# ---------------------------------------------------------
st.title("🧪 Perfumes & Decants - Stock y Precios Automáticos")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📦 Stock & Precios", 
    "🛒 Registrar Venta", 
    "➕ Agregar Perfume", 
    "📄 Cargar PDF Proveedor",
    "✏️ Editar / Eliminar",
    "📜 Historial"
])

dolar_hoy, margen_100_gen, margen_dec_gen, costo_envase = obtener_config()

# ---------------------------------------------------------
# TAB 1: Inventario Global
# ---------------------------------------------------------
with tab1:
    st.header("Inventario Global y Precios")
    
    col_p1, col_p2, col_p3, col_p4 = st.columns(4)
    with col_p1:
        st.metric("Cotización Dólar", f"${dolar_hoy:,.0f} ARS")
    with col_p2:
        st.metric("Margen Base 100ml", f"{margen_100_gen:.0f}%")
    with col_p3:
        st.metric("Margen Base Decant 10ml", f"{margen_dec_gen:.0f}%")
    with col_p4:
        st.metric("Costo Envase Decant", f"${costo_envase:,.0f} ARS")
        
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM stock", conn)
    conn.close()

    if not df.empty:
        df["costo_usd"] = df["costo_usd"].fillna(0.0)
        df["estado"] = df["estado"].fillna("Disponible en Proveedor")
        
        df["margen_aplicado"] = df["margen_100ml_custom"].fillna(margen_100_gen)
        
        df["costo_100ml_ars"] = df["costo_usd"] * dolar_hoy
        df["precio_venta_100ml_ars"] = df["costo_100ml_ars"] * (1 + (df["margen_aplicado"] / 100))
        costo_liquido_10ml = df["costo_100ml_ars"] * 0.10
        df["precio_venta_decant_10ml_ars"] = (costo_liquido_10ml + costo_envase) * (1 + (margen_dec_gen / 100))

        col_busqueda, col_f_est = st.columns([2, 1])
        with col_busqueda:
            busqueda = st.text_input("🔍 Buscar perfume por nombre:", placeholder="Ej. Club de Nuit, Khamrah...")
        with col_f_est:
            filtro_estado = st.multiselect("Filtrar por Estado:", df["estado"].unique(), default=[])

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_socio = st.multiselect("Filtrar por Socio:", df["socio_asignado"].unique())
        with col_f2:
            filtro_tipo = st.multiselect("Filtrar por Tipo:", df["tipo"].unique())

        if busqueda:
            df = df[df["nombre"].str.contains(busqueda, case=False, na=False)]
        if filtro_estado:
            df = df[df["estado"].isin(filtro_estado)]
        if filtro_socio:
            df = df[df["socio_asignado"].isin(filtro_socio)]
        if filtro_tipo:
            df = df[df["tipo"].isin(filtro_tipo)]

        df_display = df.rename(columns={
            "id": "ID",
            "nombre": "Perfume",
            "tipo": "Tipo",
            "estado": "Estado",
            "botellas_100ml_cerradas": "100ml (Cerradas)",
            "ml_disponibles_abiertos": "ml Abiertos",
            "decants_10ml_preparados": "Decants (Listos)",
            "costo_usd": "Costo USD",
            "precio_venta_100ml_ars": "Precio Venta 100ml (ARS)",
            "precio_venta_decant_10ml_ars": "Precio Decant 10ml (ARS)",
            "socio_asignado": "Socio a Cargo"
        })

        df_display["Costo USD"] = df_display["Costo USD"].apply(lambda x: f"${x:,.2f} USD")
        df_display["Precio Venta 100ml (ARS)"] = df_display["Precio Venta 100ml (ARS)"].apply(lambda x: f"${x:,.0f} ARS")
        df_display["Precio Decant 10ml (ARS)"] = df_display["Precio Decant 10ml (ARS)"].apply(lambda x: f"${x:,.0f} ARS")

        st.dataframe(
            df_display[[
                "ID", "Perfume", "Tipo", "Estado", "100ml (Cerradas)", "ml Abiertos", "Decants (Listos)", 
                "Costo USD", "Precio Venta 100ml (ARS)", "Precio Decant 10ml (ARS)", "Socio a Cargo"
            ]], 
            use_container_width=True
        )
    else:
        st.info("No hay perfumes cargados en el inventario.")

# ---------------------------------------------------------
# TAB 2: Registrar salidas, ventas y Calculadora con Descuento Desplegable
# ---------------------------------------------------------
with tab2:
    st.header("🛒 Registrar Venta y Calculadora de Promociones")
    
    st.subheader("1. Venta Individual y Descuento de Stock")
    conn = get_connection()
    df_actual = pd.read_sql_query("SELECT id, nombre, socio_asignado, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, costo_usd, margen_100ml_custom FROM stock", conn)
    conn.close()

    if not df_actual.empty:
        opciones = [
            f"ID: {row['id']} | {row['nombre']} (Posee: {row['socio_asignado']})" 
            for _, row in df_actual.iterrows()
        ]
        seleccion = st.selectbox("Selecciona el producto:", opciones)
        id_producto = int(seleccion.split(" | ")[0].replace("ID: ", ""))

        socio_realiza_venta = st.selectbox("¿Qué socio está realizando esta venta/movimiento?", SOCIOS)

        tipo_operacion = st.radio(
            "¿Qué movimiento deseas registrar?",
            [
                "Venta de Botella 100ml (Cerrada)",
                "Venta de Decant 10ml (Listo)",
                "Descontar 10ml de frasco abierto (en uso)"
            ]
        )

        if st.button("Procesar Movimiento", type="primary"):
            conn = get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT nombre, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados FROM stock WHERE id = ?", (id_producto,))
            nombre_p, botellas, ml, decants = cursor.fetchone()

            exito = False
            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if tipo_operacion == "Venta de Botella 100ml (Cerrada)":
                if botellas > 0:
                    cursor.execute("UPDATE stock SET botellas_100ml_cerradas = botellas_100ml_cerradas - 1 WHERE id = ?", (id_producto,))
                    st.success("Se descontó 1 botella cerrada de 100ml.")
                    exito = True
                else:
                    st.error("No hay botellas cerradas disponibles.")

            elif tipo_operacion == "Venta de Decant 10ml (Listo)":
                if decants > 0:
                    cursor.execute("UPDATE stock SET decants_10ml_preparados = decants_10ml_preparados - 1 WHERE id = ?", (id_producto,))
                    st.success("Se descontó 1 decant listo de 10ml.")
                    exito = True
                else:
                    st.error("No hay decants listos. Descuenta del frasco abierto.")

            elif tipo_operacion == "Descontar 10ml de frasco abierto (en uso)":
                if ml >= 10:
                    cursor.execute("UPDATE stock SET ml_disponibles_abiertos = ml_disponibles_abiertos - 10 WHERE id = ?", (id_producto,))
                    st.success("Se descontaron 10ml del frasco abierto.")
                    exito = True
                elif botellas > 0:
                    cursor.execute("""
                        UPDATE stock 
                        SET botellas_100ml_cerradas = botellas_100ml_cerradas - 1,
                            ml_disponibles_abiertos = ml_disponibles_abiertos + 90
                        WHERE id = ?
                    """, (id_producto,))
                    st.warning("Se abrió automáticamente una botella de 100ml y se descontaron los 10ml.")
                    exito = True
                else:
                    st.error("No quedan mililitros ni frascos cerrados.")

            if exito:
                cursor.execute(
                    "INSERT INTO historial (fecha, perfume, socio, tipo_movimiento) VALUES (?, ?, ?, ?)",
                    (fecha_actual, nombre_p, socio_realiza_venta, tipo_operacion)
                )
                conn.commit()
                conn.close()
                st.rerun()
            else:
                conn.close()

        st.markdown("---")
        st.subheader("🏷️ 2. Calculadora de Promociones (Venta de 2 o más perfumes)")
        
        df_actual["costo_usd"] = df_actual["costo_usd"].fillna(0.0)
        df_actual["margen_aplicado"] = df_actual["margen_100ml_custom"].fillna(margen_100_gen)
        df_actual["precio_100ml_ars"] = (df_actual["costo_usd"] * dolar_hoy) * (1 + (df_actual["margen_aplicado"] / 100))

        prods_combo = st.multiselect("Selecciona los perfumes de 100ml que lleva el cliente:", df_actual["nombre"].tolist())
        
        if prods_combo:
            subtotal = df_actual[df_actual["nombre"].isin(prods_combo)]["precio_100ml_ars"].sum()
            cant = len(prods_combo)
            
            # Menú desplegable para porcentaje de descuento
            opcion_desc = st.selectbox(
                "Seleccionar Descuento Aplicable:",
                ["Sin Descuento (0%)", "5% de Descuento", "10% de Descuento", "15% de Descuento", "20% de Descuento", "Otro % (Manual)"]
            )
            
            if opcion_desc == "Sin Descuento (0%)":
                pct_descuento = 0.0
            elif opcion_desc == "5% de Descuento":
                pct_descuento = 5.0
            elif opcion_desc == "10% de Descuento":
                pct_descuento = 10.0
            elif opcion_desc == "15% de Descuento":
                pct_descuento = 15.0
            elif opcion_desc == "20% de Descuento":
                pct_descuento = 20.0
            else:
                pct_descuento = st.number_input("Ingresa el % de descuento personalizado:", min_value=0.0, max_value=100.0, value=10.0, step=1.0)

            monto_descuento = subtotal * (pct_descuento / 100)
            total_final = subtotal - monto_descuento
            
            c_combo1, c_combo2, c_combo3 = st.columns(3)
            with c_combo1:
                st.metric("Subtotal Normal", f"${subtotal:,.0f} ARS")
            with c_combo2:
                st.metric(f"Ahorro Cliente ({pct_descuento:.0f}%)", f"-${monto_descuento:,.0f} ARS")
            with c_combo3:
                st.metric("Total a Cobrar", f"${total_final:,.0f} ARS")

    else:
        st.info("No hay productos cargados.")

# ---------------------------------------------------------
# TAB 3: Agregar perfume nuevo
# ---------------------------------------------------------
with tab3:
    st.header("Cargar Nuevo Producto Manualmente")
    with st.form("form_alta", clear_on_submit=True):
        nombre = st.text_input("Nombre del perfume y casa (ej. Lattafa Khamrah)")
        tipo = st.selectbox("Categoría / Tipo", ["Árabe", "Diseñador"])
        estado = st.selectbox("Estado inicial del producto", ESTADOS)
        costo_usd = st.number_input("Costo de compra en USD ($)", min_value=0.0, value=0.0, step=1.0)
        
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            botellas = st.number_input("Botellas 100ml cerradas", min_value=0, value=1 if estado == "En Stock" else 0, step=1)
        with col_c2:
            ml_abiertos = st.number_input("ml en frasco abierto (0-100ml)", min_value=0, max_value=100, value=0)
        with col_c3:
            decants = st.number_input("Decants 10ml ya listos", min_value=0, value=0, step=1)
            
        socio = st.selectbox("¿Quién guarda este producto?", SOCIOS)

        guardar = st.form_submit_button("Guardar en Inventario")

        if guardar:
            if nombre.strip() != "":
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO stock (nombre, tipo, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, costo_usd, estado, socio_asignado)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (nombre.strip(), tipo, botellas, ml_abiertos, decants, costo_usd, estado, socio))
                conn.commit()
                conn.close()
                st.success(f"¡'{nombre}' fue agregado correctamente como '{estado}'!")
                st.rerun()
            else:
                st.error("Debes ingresar el nombre del perfume.")

# ---------------------------------------------------------
# TAB 4: Importación de PDF (Estricto 0 unidades en stock)
# ---------------------------------------------------------
with tab4:
    st.header("📄 Procesar PDF del Proveedor y Ajustar Márgenes")
    
    st.subheader("⚙️ 1. Ajustes Generales de Moneda y Márgenes Base")
    with st.form("form_config"):
        col_cfg1, col_cfg2, col_cfg3, col_cfg4 = st.columns(4)
        with col_cfg1:
            nuevo_dolar = st.number_input("Cotización Dólar (ARS)", min_value=1.0, value=float(dolar_hoy), step=10.0)
        with col_cfg2:
            nuevo_margen_100 = st.number_input("Margen Base 100ml (%)", min_value=0.0, value=float(margen_100_gen), step=5.0)
        with col_cfg3:
            nuevo_margen_dec = st.number_input("Margen Base Decant (%)", min_value=0.0, value=float(margen_dec_gen), step=5.0)
        with col_cfg4:
            nuevo_costo_envase = st.number_input("Envase Decant (ARS)", min_value=0.0, value=float(costo_envase), step=50.0)
            
        guardar_cfg = st.form_submit_button("Guardar Parámetros de Precios")
        if guardar_cfg:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE config_precios 
                SET cotizacion_dolar = ?, margen_100ml = ?, margen_decant = ?, costo_envase_decant_ars = ?
                WHERE id = 1
            """, (nuevo_dolar, nuevo_margen_100, nuevo_margen_dec, nuevo_costo_envase))
            conn.commit()
            conn.close()
            st.success("Parámetros actualizados.")
            st.rerun()

    st.markdown("---")
    st.subheader("📥 2. Cargar Lista en PDF del Proveedor")
    st.info("📌 TODOS los productos del PDF se sincronizarán estrictamente con 0 unidades físicas y estado 'Disponible en Proveedor'.")
    
    socio_destinatario = st.selectbox("Asignar estos perfumes al socio:", SOCIOS)
    uploaded_pdf = st.file_uploader("Sube el PDF enviado por tu proveedor", type=["pdf"])

    if uploaded_pdf is not None:
        try:
            reader = pypdf.PdfReader(uploaded_pdf)
            texto_completo = ""
            for page in reader.pages:
                texto_completo += page.extract_text() + "\n"

            lineas = texto_completo.split("\n")
            items_encontrados = []

            for linea in lineas:
                p_nombre, p_costo = extraer_perfume_y_precio(linea)
                if p_nombre and p_costo and len(p_nombre) > 2 and p_costo > 3:
                    items_encontrados.append({"nombre": p_nombre, "costo_usd": p_costo})

            if items_encontrados:
                df_pdf = pd.DataFrame(items_encontrados)
                st.write(f"Se detectaron **{len(df_pdf)}** perfumes en el PDF:")
                st.dataframe(df_pdf, use_container_width=True)

                if st.button("🚀 Sincronizar catálogo del PDF con el Inventario", type="primary"):
                    conn = get_connection()
                    cursor = conn.cursor()
                    cargados = 0
                    actualizados = 0

                    for _, row in df_pdf.iterrows():
                        p_nom = row['nombre']
                        p_costo = row['costo_usd']

                        cursor.execute("SELECT id FROM stock WHERE LOWER(nombre) = LOWER(?)", (p_nom,))
                        existe = cursor.fetchone()

                        if existe:
                            # Al actualizar el precio del PDF, forzamos que si sigue en "Disponible en Proveedor" no altere las unidades
                            cursor.execute("""
                                UPDATE stock 
                                SET costo_usd = ? 
                                WHERE id = ?
                            """, (p_costo, existe[0]))
                            actualizados += 1
                        else:
                            # Inserción limpia: Estrictamente 0 unidades
                            cursor.execute("""
                                INSERT INTO stock (nombre, tipo, botellas_100ml_cerradas, ml_disponibles_abiertos, decants_10ml_preparados, costo_usd, estado, socio_asignado)
                                VALUES (?, 'Árabe', 0, 0, 0, ?, 'Disponible en Proveedor', ?)
                            """, (p_nom, p_costo, socio_destinatario))
                            cargados += 1

                    conn.commit()
                    conn.close()
                    st.success(f"¡Sincronización realizada! Se registraron {cargados} perfumes con 0 unidades (Disponible en Proveedor) y se actualizaron {actualizados} precios.")
                    st.rerun()
            else:
                st.warning("No se pudieron extraer precios automáticamente. Vista previa del texto extraído:")
                st.text_area("Texto extraído del PDF:", texto_completo, height=250)

        except Exception as e:
            st.error(f"Error procesando el PDF: {e}")

# ---------------------------------------------------------
# TAB 5: Editar Estado, Stock y Detalles del Producto
# ---------------------------------------------------------
with tab5:
    st.header("✏️ Modificar Producto, Estado o Stock")
    conn = get_connection()
    df_mod = pd.read_sql_query("SELECT * FROM stock", conn)
    conn.close()

    if not df_mod.empty:
        opciones_mod = [f"ID: {row['id']} | {row['nombre']} [{row.get('estado', 'Disponible en Proveedor')}]" for _, row in df_mod.iterrows()]
        prod_seleccionado = st.selectbox("Selecciona el producto a modificar:", opciones_mod)
        id_mod = int(prod_seleccionado.split(" | ")[0].replace("ID: ", ""))

        prod_data = df_mod[df_mod['id'] == id_mod].iloc[0]

        st.subheader("Editar Ficha del Perfume")
        with st.form("form_edicion"):
            nuevo_nombre = st.text_input("Nombre del Perfume", value=prod_data['nombre'])
            nuevo_tipo = st.selectbox("Tipo", ["Árabe", "Diseñador"], index=0 if prod_data['tipo'] == "Árabe" else 1)
            
            estado_actual = prod_data['estado'] if pd.notnull(prod_data['estado']) and prod_data['estado'] in ESTADOS else ESTADOS[0]
            nuevo_estado = st.selectbox("Estado del Perfume", ESTADOS, index=ESTADOS.index(estado_actual))
            
            costo_val = float(prod_data['costo_usd']) if pd.notnull(prod_data['costo_usd']) else 0.0
            nuevo_costo = st.number_input("Costo USD ($)", min_value=0.0, value=costo_val, step=1.0)
            
            margen_actual_val = float(prod_data['margen_100ml_custom']) if pd.notnull(prod_data['margen_100ml_custom']) else float(margen_100_gen)
            nuevo_margen_indiv = st.number_input("Margen 100ml % (Personalizado)", min_value=0.0, value=margen_actual_val, step=5.0)

            c1, c2, c3 = st.columns(3)
            with c1:
                nuevas_botellas = st.number_input("Botellas 100ml Cerradas", min_value=0, value=int(prod_data['botellas_100ml_cerradas']))
            with c2:
                nuevos_ml = st.number_input("ml Abiertos en Uso", min_value=0, max_value=100, value=int(prod_data['ml_disponibles_abiertos']))
            with c3:
                nuevos_decants = st.number_input("Decants 10ml Listos", min_value=0, value=int(prod_data['decants_10ml_preparados']))

            socio_val = prod_data['socio_asignado'] if prod_data['socio_asignado'] in SOCIOS else SOCIOS[0]
            nuevo_socio = st.selectbox("Socio a Cargo", SOCIOS, index=SOCIOS.index(socio_val))

            guardar_cambios = st.form_submit_button("Guardar Cambios")

            if guardar_cambios:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE stock 
                    SET nombre = ?, tipo = ?, botellas_100ml_cerradas = ?, ml_disponibles_abiertos = ?, decants_10ml_preparados = ?, costo_usd = ?, margen_100ml_custom = ?, estado = ?, socio_asignado = ?
                    WHERE id = ?
                """, (nuevo_nombre, nuevo_tipo, nuevas_botellas, nuevos_ml, nuevos_decants, nuevo_costo, nuevo_margen_indiv, nuevo_estado, nuevo_socio, id_mod))
                conn.commit()
                conn.close()
                st.success("¡Perfume actualizado con éxito!")
                st.rerun()

        st.markdown("---")
        st.subheader("🗑️ Eliminar Producto")
        if st.button("❌ ELIMINAR ESTE PRODUCTO DEL INVENTARIO", type="secondary"):
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stock WHERE id = ?", (id_mod,))
            conn.commit()
            conn.close()
            st.warning("Producto eliminado.")
            st.rerun()
    else:
        st.info("No hay productos para editar.")

# ---------------------------------------------------------
# TAB 6: Historial de Ventas
# ---------------------------------------------------------
with tab6:
    st.header("📜 Historial de Movimientos")
    conn = get_connection()
    df_historial = pd.read_sql_query("SELECT id, fecha as Fecha, perfume as Perfume, socio as 'Socio que vendió', tipo_movimiento as 'Tipo de Movimiento' FROM historial ORDER BY id DESC", conn)
    conn.close()

    if not df_historial.empty:
        st.dataframe(df_historial.drop(columns=['id']), use_container_width=True)
        
        st.markdown("---")
        st.subheader("🗑️ Eliminar Registros del Historial")
        
        opciones_hist = [f"ID: {row['id']} | {row['Fecha']} - {row['Perfume']} ({row['Tipo de Movimiento']})" for _, row in df_historial.iterrows()]
        registro_sel = st.selectbox("Selecciona un registro para eliminar:", opciones_hist)
        id_hist_del = int(registro_sel.split(" | ")[0].replace("ID: ", ""))

        col_h1, col_h2 = st.columns(2)
        with col_h1:
            if st.button("❌ Eliminar Registro Seleccionado"):
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM historial WHERE id = ?", (id_hist_del,))
                conn.commit()
                conn.close()
                st.success("Registro eliminado del historial.")
                st.rerun()
                
        with col_h2:
            if st.button("🚨 VACIAR HISTORIAL COMPLETO", type="secondary"):
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM historial")
                conn.commit()
                conn.close()
                st.warning("Historial vaciado completamente.")
                st.rerun()
    else:
        st.info("Aún no hay movimientos registrados.")
