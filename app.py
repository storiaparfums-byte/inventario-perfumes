import streamlit as st
import pandas as pd
from datetime import datetime
import pypdf
import re
import io
from streamlit_gsheets import GSheetsConnection

# Librerías para generación de PDF profesional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# ---------------------------------------------------------
# Configuración inicial de la página
# ---------------------------------------------------------
st.set_page_config(
    page_title="STORIA PARFUMS - Control de Stock & Precios",
    page_icon="🧪",
    layout="wide"
)

SOCIOS = ["Sebastián", "Franco", "Tomás"]
ESTADOS = ["A pedido", "En Stock", "Pedido / Señado", "Agotado"]
CLAVE_ADMIN = "1234"

# ---------------------------------------------------------
# Conexión Persistente con Google Sheets
# ---------------------------------------------------------
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos_stock():
    try:
        df = conn.read(worksheet="stock", ttl=0)
        if df.empty:
            return pd.DataFrame(columns=[
                "id", "nombre", "tipo", "botellas_100ml_cerradas", 
                "ml_disponibles_abiertos", "decants_10ml_preparados", 
                "costo_usd", "margen_100ml_custom", "estado", "socio_asignado"
            ])
        return df
    except Exception:
        return pd.DataFrame(columns=[
            "id", "nombre", "tipo", "botellas_100ml_cerradas", 
            "ml_disponibles_abiertos", "decants_10ml_preparados", 
            "costo_usd", "margen_100ml_custom", "estado", "socio_asignado"
        ])

def guardar_datos_stock(df):
    conn.update(worksheet="stock", data=df)

def cargar_historial():
    try:
        df = conn.read(worksheet="historial", ttl=0)
        if df.empty:
            return pd.DataFrame(columns=["id", "fecha", "perfume", "socio", "tipo_movimiento"])
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "fecha", "perfume", "socio", "tipo_movimiento"])

def guardar_historial(df):
    conn.update(worksheet="historial", data=df)

def cargar_config():
    try:
        df = conn.read(worksheet="config", ttl=0)
        if not df.empty:
            row = df.iloc[0]
            return float(row["cotizacion_dolar"]), float(row["margen_100ml"]), float(row["margen_decant"]), float(row["costo_envase_decant_ars"])
    except Exception:
        pass
    return 1200.0, 30.0, 100.0, 800.0

def guardar_config(dolar, m100, mdec, envase):
    df = pd.DataFrame([{
        "cotizacion_dolar": dolar,
        "margen_100ml": m100,
        "margen_decant": mdec,
        "costo_envase_decant_ars": envase
    }])
    conn.update(worksheet="config", data=df)

# ---------------------------------------------------------
# Funciones Auxiliares
# ---------------------------------------------------------
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
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=22, leading=26, textColor=colors.HexColor("#0F172A"), alignment=1)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=11, leading=14, textColor=colors.HexColor("#64748B"), alignment=1)
    
    story.append(Paragraph("✨ STORIA PARFUMS ✨", title_style))
    story.append(Paragraph("Catálogo de Perfumes de Diseñador y Árabes", subtitle_style))
    story.append(Spacer(1, 15))
    
    data = [["Perfume", "Tipo", "Disponibilidad", "100 ml (ARS)", "Decant 10 ml (ARS)"]]
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
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0F172A")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
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
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=22, leading=26, textColor=colors.HexColor("#0F172A"))
    meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=9, leading=12, textColor=colors.HexColor("#475569"))
    
    story.append(Paragraph("✨ STORIA PARFUMS ✨", title_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph(f"<b>Presupuesto para:</b> {cliente}", meta_style))
    story.append(Paragraph(f"<b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}", meta_style))
    story.append(Spacer(1, 15))
    
    data = [["Producto", "Presentación", "Cantidad", "Precio Unitario", "Subtotal"]]
    for item in items:
        data.append([
            item["nombre"],
            item["presentacion"],
            str(item["cantidad"]),
            f"${item['precio_unitario']:,.0f}",
            f"${item['subtotal']:,.0f}"
        ])
        
    t = Table(data, colWidths=[220, 90, 60, 90, 80])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E293B")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
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
        ('TEXTCOLOR', (0,-1), (-1,-1), colors.HexColor("#1E3A8A")),
        ('PADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_tot)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

# ---------------------------------------------------------
# Interfaz Gráfica (Pestañas)
# ---------------------------------------------------------
st.title("✨ STORIA PARFUMS - Control de Stock & Precios")

tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    "📦 Stock & Precios", 
    "📖 Catálogo Clientes",
    "📋 Crear Presupuesto",
    "🛒 Registrar Venta", 
    "➕ Agregar Perfume", 
    "📄 Cargar PDF Proveedor",
    "✏️ Editar / Eliminar",
    "📜 Historial"
])

dolar_hoy, margen_100_gen, margen_dec_gen, costo_envase = cargar_config()

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
            df = df[df["nombre"].astype(str).str.contains(busqueda, case=False, na=False)]
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
        st.info("No hay perfumes cargados.")

# ---------------------------------------------------------
# TAB 2: Catálogo Público para Clientes + Descarga PDF
# ---------------------------------------------------------
with tab2:
    st.header("📖 Catálogo Público STORIA PARFUMS")
    st.markdown("Lista limpia para compartir con clientes. Los productos **En Stock** aparecen primero.")
    
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
            label="📥 Descargar Catálogo Completo STORIA PARFUMS (PDF)",
            data=pdf_cat_bytes,
            file_name=f"Catalogo_Storia_Parfums_{datetime.now().strftime('%d_%m_%Y')}.pdf",
            mime="application/pdf",
            type="primary"
        )
        
        df_cat_disp = df_cat_base.rename(columns={
            "nombre": "Perfume",
            "tipo": "Tipo",
            "estado": "Disponibilidad",
            "precio_100ml": "Precio 100ml (ARS)",
            "precio_decant": "Decant 10ml (ARS)"
        })
        
        df_cat_disp["Precio 100ml (ARS)"] = df_cat_disp["Precio 100ml (ARS)"].apply(lambda x: f"${x:,.0f} ARS")
        df_cat_disp["Decant 10ml (ARS)"] = df_cat_disp["Decant 10ml (ARS)"].apply(lambda x: f"${x:,.0f} ARS")
        
        st.dataframe(df_cat_disp[["Perfume", "Tipo", "Disponibilidad", "Precio 100ml (ARS)", "Decant 10ml (ARS)"]], use_container_width=True)
    else:
        st.info("No hay productos cargados en catálogo.")

# ---------------------------------------------------------
# TAB 3: Crear Presupuesto Personalizado + PDF
# ---------------------------------------------------------
with tab3:
    st.header("📋 Generador de Presupuestos STORIA PARFUMS")
    
    nombre_cliente = st.text_input("Nombre del Cliente / Contacto:", value="Cliente")
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
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                p_sel = st.selectbox("Selecciona Perfume:", df_p["nombre"].tolist())
            with c2:
                pres_sel = st.selectbox("Presentación:", ["Botella 100ml", "Decant 10ml"])
            with c3:
                cant_sel = st.number_input("Cantidad:", min_value=1, value=1, step=1)
                
            add_item = st.form_submit_button("➕ Agregar al Presupuesto")
            if add_item:
                p_data = df_p[df_p["nombre"] == p_sel].iloc[0]
                p_unit = p_data["precio_100ml"] if pres_sel == "Botella 100ml" else p_data["precio_decant"]
                
                st.session_state.items_presupuesto.append({
                    "nombre": p_sel,
                    "presentacion": pres_sel,
                    "cantidad": cant_sel,
                    "precio_unitario": p_unit,
                    "subtotal": p_unit * cant_sel
                })
                st.success(f"Agregado {p_sel} ({pres_sel}) x{cant_sel}")
                
        if st.session_state.items_presupuesto:
            st.subheader("Items en este Presupuesto")
            df_pres_view = pd.DataFrame(st.session_state.items_presupuesto)
            st.dataframe(df_pres_view[["nombre", "presentacion", "cantidad", "precio_unitario", "subtotal"]], use_container_width=True)
            
            subtotal_pres = df_pres_view["subtotal"].sum()
            
            pct_desc_pres = st.selectbox("Descuento Promocional:", [0, 5, 10, 15, 20])
            monto_desc_pres = subtotal_pres * (pct_desc_pres / 100)
            total_pres = subtotal_pres - monto_desc_pres
            
            st.metric("TOTAL FINAL PRESUPUESTO", f"${total_pres:,.0f} ARS", delta=f"-${monto_desc_pres:,.0f} ARS ({pct_desc_pres}%)" if pct_desc_pres > 0 else None)
            
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                pdf_pres_bytes = generar_pdf_presupuesto(nombre_cliente, st.session_state.items_presupuesto, subtotal_pres, monto_desc_pres, total_pres)
                st.download_button(
                    label="📄 Descargar Presupuesto STORIA PARFUMS (PDF)",
                    data=pdf_pres_bytes,
                    file_name=f"Presupuesto_Storia_{nombre_cliente.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    type="primary"
                )
            with col_b2:
                if st.button("🗑️ Limpiar Presupuesto"):
                    st.session_state.items_presupuesto = []
                    st.rerun()

# ---------------------------------------------------------
# TAB 4: Registrar Ventas
# ---------------------------------------------------------
with tab4:
    st.header("🛒 Registrar Venta y Descuento de Stock")
    df_actual = cargar_datos_stock()

    if not df_actual.empty:
        opciones = [f"ID: {row['id']} | {row['nombre']} (Posee: {row['socio_asignado']})" for _, row in df_actual.iterrows()]
        seleccion = st.selectbox("Selecciona el producto:", opciones)
        id_producto = int(seleccion.split(" | ")[0].replace("ID: ", ""))

        socio_realiza_venta = st.selectbox("¿Qué socio realiza la venta?", SOCIOS)
        tipo_operacion = st.radio("¿Qué movimiento deseas registrar?", ["Venta de Botella 100ml (Cerrada)", "Venta de Decant 10ml (Listo)", "Descontar 10ml de frasco abierto (en uso)"])

        if st.button("Procesar Movimiento", type="primary"):
            row_idx = df_actual[df_actual['id'] == id_producto].index[0]
            nombre_p = df_actual.loc[row_idx, 'nombre']
            botellas = int(df_actual.loc[row_idx, 'botellas_100ml_cerradas'])
            ml = int(df_actual.loc[row_idx, 'ml_disponibles_abiertos'])
            decants = int(df_actual.loc[row_idx, 'decants_10ml_preparados'])

            exito = False
            fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            if tipo_operacion == "Venta de Botella 100ml (Cerrada)":
                if botellas > 0:
                    df_actual.loc[row_idx, 'botellas_100ml_cerradas'] = botellas - 1
                    st.success("Se descontó 1 botella cerrada de 100ml.")
                    exito = True
                else:
                    st.error("No hay botellas cerradas disponibles.")

            elif tipo_operacion == "Venta de Decant 10ml (Listo)":
                if decants > 0:
                    df_actual.loc[row_idx, 'decants_10ml_preparados'] = decants - 1
                    st.success("Se descontó 1 decant listo de 10ml.")
                    exito = True
                else:
                    st.error("No hay decants listos.")

            elif tipo_operacion == "Descontar 10ml de frasco abierto (en uso)":
                if ml >= 10:
                    df_actual.loc[row_idx, 'ml_disponibles_abiertos'] = ml - 10
                    st.success("Se descontaron 10ml del frasco abierto.")
                    exito = True
                elif botellas > 0:
                    df_actual.loc[row_idx, 'botellas_100ml_cerradas'] = botellas - 1
                    df_actual.loc[row_idx, 'ml_disponibles_abiertos'] = ml + 90
                    st.warning("Se abrió una botella de 100ml y se descontaron 10ml.")
                    exito = True
                else:
                    st.error("Sin mililitros ni frascos cerrados.")

            if exito:
                guardar_datos_stock(df_actual)
                df_hist = cargar_historial()
                nuevo_hist_id = int(df_hist['id'].max() + 1) if not df_hist.empty and pd.notnull(df_hist['id'].max()) else 1
                df_nuevo_hist = pd.DataFrame([{
                    "id": nuevo_hist_id,
                    "fecha": fecha_actual,
                    "perfume": nombre_p,
                    "socio": socio_realiza_venta,
                    "tipo_movimiento": tipo_operacion
                }])
                guardar_historial(pd.concat([df_hist, df_nuevo_hist], ignore_index=True))
                st.rerun()

# ---------------------------------------------------------
# TAB 5: Agregar perfume nuevo
# ---------------------------------------------------------
with tab5:
    st.header("Cargar Nuevo Producto Manualmente")
    with st.form("form_alta", clear_on_submit=True):
        nombre = st.text_input("Nombre del perfume")
        tipo = st.selectbox("Categoría", ["Árabe", "Diseñador"])
        estado = st.selectbox("Estado inicial", ESTADOS)
        costo_usd = st.number_input("Costo de compra USD ($)", min_value=0.0, value=0.0, step=1.0)
        
        c1, c2, c3 = st.columns(3)
        with c1:
            botellas = st.number_input("Botellas 100ml", min_value=0, value=1 if estado == "En Stock" else 0)
        with c2:
            ml_abiertos = st.number_input("ml Abiertos", min_value=0, max_value=100, value=0)
        with c3:
            decants = st.number_input("Decants 10ml", min_value=0, value=0)
            
        socio = st.selectbox("Socio a cargo", SOCIOS)
        guardar = st.form_submit_button("Guardar en Inventario")

        if guardar:
            if nombre.strip() != "":
                df_actual = cargar_datos_stock()
                nuevo_id = int(df_actual['id'].max() + 1) if not df_actual.empty and pd.notnull(df_actual['id'].max()) else 1
                nuevo_row = pd.DataFrame([{
                    "id": nuevo_id,
                    "nombre": nombre.strip(),
                    "tipo": tipo,
                    "botellas_100ml_cerradas": botellas,
                    "ml_disponibles_abiertos": ml_abiertos,
                    "decants_10ml_preparados": decants,
                    "costo_usd": costo_usd,
                    "margen_100ml_custom": None,
                    "estado": estado,
                    "socio_asignado": socio
                }])
                guardar_datos_stock(pd.concat([df_actual, nuevo_row], ignore_index=True))
                st.success("¡Producto cargado en Google Sheets!")
                st.rerun()

# ---------------------------------------------------------
# TAB 6: Importación de PDF Proveedor
# ---------------------------------------------------------
with tab6:
    st.header("📄 Procesar PDF del Proveedor")
    with st.form("form_config"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            nuevo_dolar = st.number_input("Cotización Dólar (ARS)", min_value=1.0, value=float(dolar_hoy))
        with col2:
            nuevo_m100 = st.number_input("Margen 100ml %", min_value=0.0, value=float(margen_100_gen))
        with col3:
            nuevo_mdec = st.number_input("Margen Decant %", min_value=0.0, value=float(margen_dec_gen))
        with col4:
            nuevo_envase = st.number_input("Envase Decant (ARS)", min_value=0.0, value=float(costo_envase))
            
        if st.form_submit_button("Guardar Parámetros de Precios"):
            guardar_config(nuevo_dolar, nuevo_m100, nuevo_mdec, nuevo_envase)
            st.success("Parámetros guardados.")
            st.rerun()

    socio_dest = st.selectbox("Asignar perfumes del PDF a:", SOCIOS)
    uploaded_pdf = st.file_uploader("Sube el PDF enviado por tu proveedor", type=["pdf"])

    if uploaded_pdf is not None:
        try:
            reader = pypdf.PdfReader(uploaded_pdf)
            texto_completo = "".join([page.extract_text() + "\n" for page in reader.pages])
            lineas = texto_completo.split("\n")
            items = []
            for l in lineas:
                p_nom, p_cost = extraer_perfume_y_precio(l)
                if p_nom and p_cost and len(p_nom) > 2 and p_cost > 3:
                    items.append({"nombre": p_nom, "costo_usd": p_cost})

            if items:
                df_pdf = pd.DataFrame(items)
                st.write(f"Se detectaron **{len(df_pdf)}** perfumes:")
                st.dataframe(df_pdf, use_container_width=True)

                if st.button("🚀 Sincronizar catálogo del PDF con Google Sheets", type="primary"):
                    df_actual = cargar_datos_stock()
                    cargados, actualizados = 0, 0
                    
                    for _, r in df_pdf.iterrows():
                        mask = df_actual['nombre'].astype(str).str.lower() == r['nombre'].lower()
                        if mask.any():
                            df_actual.loc[mask, 'costo_usd'] = r['costo_usd']
                            actualizados += 1
                        else:
                            nuevo_id = int(df_actual['id'].max() + 1) if not df_actual.empty and pd.notnull(df_actual['id'].max()) else 1
                            nuevo_p = pd.DataFrame([{
                                "id": nuevo_id,
                                "nombre": r['nombre'],
                                "tipo": "Árabe",
                                "botellas_100ml_cerradas": 0,
                                "ml_disponibles_abiertos": 0,
                                "decants_10ml_preparados": 0,
                                "costo_usd": r['costo_usd'],
                                "margen_100ml_custom": None,
                                "estado": "A pedido",
                                "socio_asignado": socio_dest
                            }])
                            df_actual = pd.concat([df_actual, nuevo_p], ignore_index=True)
                            cargados += 1
                            
                    guardar_datos_stock(df_actual)
                    st.success(f"¡Sincronizado! {cargados} creados y {actualizados} actualizados.")
                    st.rerun()
        except Exception as e:
            st.error(f"Error procesando PDF: {e}")

# ---------------------------------------------------------
# TAB 7: Editar Estado, Stock y Vaciar Inventario
# ---------------------------------------------------------
with tab7:
    st.header("✏️ Modificar Producto o Vaciar Inventario")
    df_mod = cargar_datos_stock()

    if not df_mod.empty:
        df_mod["estado"] = df_mod["estado"].replace("Disponible en Proveedor", "A pedido")
        opciones_mod = [f"ID: {row['id']} | {row['nombre']} [{row.get('estado', 'A pedido')}]" for _, row in df_mod.iterrows()]
        prod_sel = st.selectbox("Selecciona producto a modificar:", opciones_mod)
        id_mod = int(prod_sel.split(" | ")[0].replace("ID: ", ""))
        row_idx = df_mod[df_mod['id'] == id_mod].index[0]
        prod_data = df_mod.loc[row_idx]

        with st.form("form_edicion"):
            nuevo_nombre = st.text_input("Nombre", value=prod_data['nombre'])
            nuevo_tipo = st.selectbox("Tipo", ["Árabe", "Diseñador"], index=0 if prod_data['tipo'] == "Árabe" else 1)
            nuevo_estado = st.selectbox("Estado", ESTADOS, index=ESTADOS.index(prod_data['estado']) if prod_data['estado'] in ESTADOS else 0)
            nuevo_costo = st.number_input("Costo USD", value=float(prod_data['costo_usd']))
            nuevo_margen = st.number_input("Margen Custom %", value=float(prod_data['margen_100ml_custom']) if pd.notnull(prod_data['margen_100ml_custom']) else float(margen_100_gen))

            c1, c2, c3 = st.columns(3)
            with c1:
                nbot = st.number_input("Botellas 100ml", min_value=0, value=int(prod_data['botellas_100ml_cerradas']))
            with c2:
                nml = st.number_input("ml Abiertos", min_value=0, max_value=100, value=int(prod_data['ml_disponibles_abiertos']))
            with c3:
                ndec = st.number_input("Decants 10ml", min_value=0, value=int(prod_data['decants_10ml_preparados']))

            nuevo_socio = st.selectbox("Socio a cargo", SOCIOS, index=SOCIOS.index(prod_data['socio_asignado']) if prod_data['socio_asignado'] in SOCIOS else 0)

            if st.form_submit_button("Guardar Cambios"):
                df_mod.loc[row_idx, 'nombre'] = nuevo_nombre
                df_mod.loc[row_idx, 'tipo'] = nuevo_tipo
                df_mod.loc[row_idx, 'estado'] = nuevo_estado
                df_mod.loc[row_idx, 'costo_usd'] = nuevo_costo
                df_mod.loc[row_idx, 'margen_100ml_custom'] = nuevo_margen
                df_mod.loc[row_idx, 'botellas_100ml_cerradas'] = nbot
                df_mod.loc[row_idx, 'ml_disponibles_abiertos'] = nml
                df_mod.loc[row_idx, 'decants_10ml_preparados'] = ndec
                df_mod.loc[row_idx, 'socio_asignado'] = nuevo_socio
                
                guardar_datos_stock(df_mod)
                st.success("¡Producto actualizado en Google Sheets!")
                st.rerun()

    st.markdown("---")
    st.subheader("🚨 ZONA PROTEGIDA: Vaciar Todo el Catálogo")
    clave_inv_input = st.text_input("🔑 Clave de Administrador:", type="password", key="pwd_inv")
    if st.button("🚨 VACIAR CATALOGO Y STOCK COMPLETO", type="primary"):
        if clave_inv_input == CLAVE_ADMIN:
            df_vacio = pd.DataFrame(columns=[
                "id", "nombre", "tipo", "botellas_100ml_cerradas", 
                "ml_disponibles_abiertos", "decants_10ml_preparados", 
                "costo_usd", "margen_100ml_custom", "estado", "socio_asignado"
            ])
            guardar_datos_stock(df_vacio)
            st.success("¡Catálogo vaciado completamente!")
            st.rerun()
        else:
            st.error("❌ Clave incorrecta.")

# ---------------------------------------------------------
# TAB 8: Historial Protegido
# ---------------------------------------------------------
with tab8:
    st.header("📜 Historial de Movimientos")
    df_hist = cargar_historial()

    if not df_hist.empty:
        st.dataframe(df_hist.drop(columns=['id']), use_container_width=True)
        st.markdown("---")
        clave_hist = st.text_input("🔑 Clave de Administrador para modificar historial:", type="password", key="pwd_hist")
        
        opciones_hist = [f"ID: {row['id']} | {row['fecha']} - {row['perfume']}" for _, row in df_hist.iterrows()]
        reg_sel = st.selectbox("Selecciona registro a borrar:", opciones_hist)
        id_h_del = int(reg_sel.split(" | ")[0].replace("ID: ", ""))

        c1, c2 = st.columns(2)
        with c1:
            if st.button("❌ Eliminar Registro Seleccionado"):
                if clave_hist == CLAVE_ADMIN:
                    df_hist = df_hist[df_hist['id'] != id_h_del]
                    guardar_historial(df_hist)
                    st.success("Registro eliminado.")
                    st.rerun()
                else:
                    st.error("❌ Clave incorrecta.")
        with c2:
            if st.button("🚨 VACIAR HISTORIAL COMPLETO", type="secondary"):
                if clave_hist == CLAVE_ADMIN:
                    df_vacio_h = pd.DataFrame(columns=["id", "fecha", "perfume", "socio", "tipo_movimiento"])
                    guardar_historial(df_vacio_h)
                    st.warning("Historial vaciado.")
                    st.rerun()
                else:
                    st.error("❌ Clave incorrecta.")
    else:
        st.info("No hay movimientos registrados.")
