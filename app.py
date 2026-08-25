# Reemplaza la inicialización de la conexión por esta versión más robusta:
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos_stock():
    try:
        df = conn.read(worksheet="stock", ttl=0)
        if df is None or df.empty:
            return pd.DataFrame(columns=[
                "id", "nombre", "tipo", "botellas_100ml_cerradas", 
                "ml_disponibles_abiertos", "decants_10ml_preparados", 
                "costo_usd", "margen_100ml_custom", "estado", "socio_asignado"
            ])
        return df
    except Exception as e:
        st.error(f"Error leyendo la pestaña 'stock': {e}")
        return pd.DataFrame(columns=[
            "id", "nombre", "tipo", "botellas_100ml_cerradas", 
            "ml_disponibles_abiertos", "decants_10ml_preparados", 
            "costo_usd", "margen_100ml_custom", "estado", "socio_asignado"
        ])
