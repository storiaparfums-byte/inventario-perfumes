if st.button("🚀 Sincronizar catálogo del PDF con Google Sheets", type="primary"):
                    df_actual = cargar_datos_stock()
                    
                    # Convertir IDs a enteros para evitar incompatibilidades de tipo
                    if not df_actual.empty and "id" in df_actual.columns:
                        df_actual["id"] = pd.to_numeric(df_actual["id"], errors="coerce").fillna(0).astype(int)

                    cargados, actualizados = 0, 0
                    
                    for _, r in df_pdf.iterrows():
                        mask = df_actual['nombre'].astype(str).str.lower() == str(r['nombre']).lower()
                        if mask.any():
                            df_actual.loc[mask, 'costo_usd'] = float(r['costo_usd'])
                            actualizados += 1
                        else:
                            nuevo_id = int(df_actual['id'].max() + 1) if not df_actual.empty and pd.notnull(df_actual['id'].max()) else 1
                            nuevo_p = pd.DataFrame([{
                                "id": int(nuevo_id),
                                "nombre": str(r['nombre']),
                                "tipo": "Árabe",
                                "botellas_100ml_cerradas": 0,
                                "ml_disponibles_abiertos": 0,
                                "decants_10ml_preparados": 0,
                                "costo_usd": float(r['costo_usd']),
                                "margen_100ml_custom": None,
                                "estado": "A pedido",
                                "socio_asignado": str(socio_dest)
                            }])
                            df_actual = pd.concat([df_actual, nuevo_p], ignore_index=True)
                            cargados += 1
                            
                    guardar_datos_stock(df_actual)
                    st.success(f"¡Sincronizado con éxito en Google Sheets! {cargados} creados y {actualizados} actualizados.")
                    st.rerun()
