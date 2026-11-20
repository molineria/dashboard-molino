# === MÓDULO D: SECCIÓN MOLINO AUMAX ===
def render_seccion_aumax(supabase_client):
    st.header("⚙️ Molino Aumax — Caudales en Vivo, Balanzas y Recetas")

    try:
        q_caud = (
            supabase_client.table("aumax_registro_caudales")
            .select("*")
            .order("fecha_captura", desc=True)
            .limit(200)
            .execute()
        )
        df_caud = pd.DataFrame(q_caud.data or [])
    except Exception:
        df_caud = pd.DataFrame()

    q_ext = (
        supabase_client.table("aumax_extraccion_instantanea")
        .select("*")
        .order("fecha_captura", desc=True)
        .limit(10)
        .execute()
    )
    df_ext = pd.DataFrame(q_ext.data or [])

    q_tot = (
        supabase_client.table("aumax_registros_totales")
        .select("*")
        .order("fecha_registro", desc=True)
        .limit(10)
        .execute()
    )
    df_tot = pd.DataFrame(q_tot.data or [])

    q_corte = (
        supabase_client.table("v_aumax_corte_00hs")
        .select("*")
        .order("fecha_corte", desc=True)
        .limit(30)
        .execute()
    )
    df_corte = pd.DataFrame(q_corte.data or [])

    q_rec = (
        supabase_client.table("aumax_diferencia_receta")
        .select("*")
        .order("fecha_evento_actual", desc=True)
        .limit(200)
        .execute()
    )
    df_rec_all = pd.DataFrame(q_rec.data or [])

    # Alertas operativas basadas en caudales
    UMBRAL_EXTRACCION_MIN = 72.0
    alertas = []

    if not df_ext.empty:
        ultima_ext = float(df_ext.iloc[0]["extraccion_pct"])
    elif not df_caud.empty:
        ultima_ext = float(df_caud.iloc[0].get("extraccion_pct") or 0)
    else:
        ultima_ext = None

    if ultima_ext is not None and ultima_ext > 0 and ultima_ext < UMBRAL_EXTRACCION_MIN:
        alertas.append(
            f"📉 **Extracción baja detectada:** {ultima_ext:.2f}% (por debajo del umbral de {UMBRAL_EXTRACCION_MIN:.1f}%)."
        )

    if not df_caud.empty:
        df_caud["dt"] = pd.to_datetime(df_caud["fecha_captura"], format="ISO8601", utc=True)
        ultima_lectura = df_caud.iloc[0]["dt"].astimezone(TZ_AR)
        ahora_ar = datetime.now(TZ_AR)
        minutos_sin_datos = (ahora_ar - ultima_lectura).total_seconds() / 60.0

        if minutos_sin_datos > 20:
            alertas.append(
                f"⏱️ **Sin lecturas recientes de caudales:** última transmisión hace {int(minutos_sin_datos)} min ({ultima_lectura.strftime('%d/%m %H:%M')})."
            )

        caudal_trigo_act = float(df_caud.iloc[0].get("caudal_ing_trg") or 0)
        if caudal_trigo_act <= 0:
            alertas.append("🛑 **Molino detenido / sin caudal de ingreso de trigo:** Caudal IngTrig en 0 kg/h.")

    if alertas:
        for msg in alertas:
            st.error(msg)
    else:
        st.success("✅ Operación Aumax normal: molino en marcha con caudal activo y extracción dentro de parámetro.")

    # KPIs principales
    col1, col2, col3, col4 = st.columns(4)
    ext_val = f"{ultima_ext:.2f}%" if ultima_ext is not None else "S/D"
    receta_act = df_tot.iloc[0]["receta_hab"] if not df_tot.empty else "S/D"
    silo_act = f"Silo {df_tot.iloc[0]['silo_hab']}" if not df_tot.empty else "S/D"

    if not df_caud.empty:
        hora_act = pd.to_datetime(df_caud.iloc[0]["fecha_captura"], format="ISO8601", utc=True).astimezone(TZ_AR).strftime("%d/%m %H:%M")
    elif not df_tot.empty:
        hora_act = pd.to_datetime(df_tot.iloc[0]["fecha_registro"], format="ISO8601", utc=True).astimezone(TZ_AR).strftime("%d/%m %H:%M")
    else:
        hora_act = "S/D"

    col1.metric("Extracción Instantánea", ext_val)
    col2.metric("Receta Activa", receta_act)
    col3.metric("Silo Habilitado", silo_act)
    col4.metric("Último Registro Caudales", hora_act)

    # 6 Medidores de Caudal Instantáneo siempre visibles
    st.subheader("🌊 Registro de Caudales Instantáneos (kg/h)")
    ult_c = df_caud.iloc[0] if not df_caud.empty else {}
    c_k1, c_k2, c_k3, c_k4, c_k5, c_k6 = st.columns(6)
    c_k1.metric("Caudal IngTrig", f"{float(ult_c.get('caudal_ing_trg') or 0):,.2f}")
    c_k2.metric("Caudal 3x0", f"{float(ult_c.get('caudal_3x0') or 0):,.2f}")
    c_k3.metric("Caudal 4x0", f"{float(ult_c.get('caudal_4x0') or 0):,.2f}")
    c_k4.metric("Caudal Afrechillo", f"{float(ult_c.get('caudal_afrechillo') or 0):,.2f}")
    c_k5.metric("Caudal Semolín", f"{float(ult_c.get('caudal_semolin') or 0):,.2f}")
    c_k6.metric("Caudal BIIr", f"{float(ult_c.get('caudal_bllr') or 0):,.2f}")

    if not df_caud.empty:
        df_caud_plot = df_caud.copy()
        df_caud_plot["hora_ar"] = pd.to_datetime(df_caud_plot["fecha_captura"], format="ISO8601", utc=True).dt.tz_convert(TZ_AR)
        df_caud_plot = df_caud_plot.sort_values("hora_ar")

        fig_caud = go.Figure()
        fig_caud.add_trace(go.Scatter(x=df_caud_plot["hora_ar"], y=df_caud_plot["caudal_ing_trg"], name="IngTrig"))
        fig_caud.add_trace(go.Scatter(x=df_caud_plot["hora_ar"], y=df_caud_plot["caudal_3x0"], name="3x0"))
        fig_caud.add_trace(go.Scatter(x=df_caud_plot["hora_ar"], y=df_caud_plot["caudal_4x0"], name="4x0"))
        fig_caud.add_trace(go.Scatter(x=df_caud_plot["hora_ar"], y=df_caud_plot["caudal_afrechillo"], name="Afrechillo"))
        fig_caud.add_trace(go.Scatter(x=df_caud_plot["hora_ar"], y=df_caud_plot["caudal_semolin"], name="Semolín"))
        fig_caud.update_layout(
            title="Curva de Caudales en Tiempo Real (kg/h)",
            xaxis_title="Hora (Planta)",
            yaxis_title="Caudal (kg/h)",
            legend=dict(orientation="h", y=1.12),
            height=300,
        )
        st.plotly_chart(fig_caud, width="stretch")

    st.divider()

    # Tablas compactas (2 renglones visibles)
    col_corte, col_rec = st.columns(2)

    with col_corte:
        st.subheader("🕛 Corte Diario 00:00 hs (Últimos 2 días)")
        if not df_corte.empty:
            df_corte_vista = df_corte.head(2).copy()
            cols_mostrar = [
                "fecha_corte",
                "receta_hab",
                "kg_dia_trigo",
                "kg_dia_3x0",
                "kg_dia_4x0",
                "kg_dia_afrechillo",
            ]
            cols_existentes = [c for c in cols_mostrar if c in df_corte_vista.columns]
            st.dataframe(df_corte_vista[cols_existentes], width="stretch", hide_index=True, height=110)
        else:
            st.info("Sin cortes registrados.")

    with col_rec:
        st.subheader("📊 Producción Neta por Receta (Últimas 2)")
        if not df_rec_all.empty:
            df_rec_limpio = df_rec_all[df_rec_all["receta_anterior"].astype(str) != "0"].copy()
            resumen_receta = (
                df_rec_limpio.groupby("receta_anterior", as_index=False)[
                    ["diff_blz_ing_trg", "diff_blz_4x0", "diff_blz_3x0", "diff_blz_afrch"]
                ]
                .sum()
                .rename(
                    columns={
                        "receta_anterior": "Receta",
                        "diff_blz_ing_trg": "Trigo (kg)",
                        "diff_blz_4x0": "4/0 (kg)",
                        "diff_blz_3x0": "3/0 (kg)",
                        "diff_blz_afrch": "Afrch (kg)",
                    }
                )
            )
            resumen_receta["Ext. (%)"] = (
                (resumen_receta["4/0 (kg)"] + resumen_receta["3/0 (kg)"])
                / resumen_receta["Trigo (kg)"].replace(0, pd.NA)
                * 100
            ).round(2)
            st.dataframe(resumen_receta.head(2), width="stretch", hide_index=True, height=110)
        else:
            st.info("Sin cambios de receta registrados.")


# === FORMULARIO DE CARGA MANUAL (TOTALIZADORES + NETOS) Y CONSOLIDADO COMPACTO ===
def render_formulario_carga_manual(supabase_client):
    st.subheader("📝 Carga Manual Diaria (Lecturas de Totalizadores y Subproductos)")

    fecha_carga = st.date_input(
        "Fecha del parte diario",
        value=datetime.now(TZ_AR).date(),
        key="fecha_carga_manual",
    )
    fecha_iso = fecha_carga.isoformat()

    datos_previos = {}
    try:
        res_prev = (
            supabase_client.table("produccion_cargas_manuales")
            .select("*")
            .eq("fecha", fecha_iso)
            .execute()
        )
        if res_prev.data:
            datos_previos = res_prev.data[0]
            st.info(f"ℹ️ Ya existe registro para el {fecha_carga.strftime('%d/%m/%Y')}. Puedes editarlo.")
    except Exception as e:
        st.warning(f"No se pudo consultar registros previos: {e}")

    with st.form("form_produccion_manual"):
        st.caption("🔢 Lecturas de Totalizadores al Cierre del Día (se resta automáticamente el día anterior)")
        t1, t2, t3, t4 = st.columns(4)
        with t1:
            tot_bza_tl = st.number_input(
                "Totalizador bza TL (Trigo Limpio)",
                min_value=0.0,
                step=100.0,
                format="%.1f",
                value=float(datos_previos.get("tot_bza_tl") or 0.0),
            )
        with t2:
            tot_litros_agua = st.number_input(
                "Totalizador Adición de Agua (Litros)",
                min_value=0.0,
                step=10.0,
                format="%.1f",
                value=float(datos_previos.get("tot_litros_agua") or 0.0),
            )
        with t3:
            tot_bza_b1 = st.number_input(
                "Totalizador Balanza B1 (Trigo A)",
                min_value=0.0,
                step=100.0,
                format="%.1f",
                value=float(datos_previos.get("tot_bza_b1") or 0.0),
            )
        with t4:
            tot_embolse = st.number_input(
                "Totalizador Balanza Embolse",
                min_value=0.0,
                step=100.0,
                format="%.1f",
                value=float(datos_previos.get("tot_embolse") or 0.0),
            )

        st.caption("📦 Kilos Netos del Día (Subproductos Manuales, Desglose y Horas de Marcha)")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            kg_semita = st.number_input(
                "Semita - sta (kg)",
                min_value=0.0,
                step=10.0,
                format="%.1f",
                value=float(datos_previos.get("kg_semita") or 0.0),
            )
            kg_tp = st.number_input(
                "KG TP (kg)",
                min_value=0.0,
                step=10.0,
                format="%.1f",
                value=float(datos_previos.get("kg_tp") or 0.0),
            )
        with m2:
            kg_salvado_grueso = st.number_input(
                "Salvado Grueso - AF/Sdo gr (kg)",
                min_value=0.0,
                step=10.0,
                format="%.1f",
                value=float(datos_previos.get("kg_salvado_grueso") or 0.0),
            )
            kg_pasta = st.number_input(
                "3/0 Pasta (kg)",
                min_value=0.0,
                step=10.0,
                format="%.1f",
                value=float(datos_previos.get("kg_pasta") or 0.0),
            )
        with m3:
            kg_salvado_fino = st.number_input(
                "Salvado Fino - af f (kg)",
                min_value=0.0,
                step=10.0,
                format="%.1f",
                value=float(datos_previos.get("kg_salvado_fino") or 0.0),
            )
            kg_pan = st.number_input(
                "3/0 Pan (kg)",
                min_value=0.0,
                step=10.0,
                format="%.1f",
                value=float(datos_previos.get("kg_pan") or 0.0),
            )
        with m4:
            horas_marcha = st.number_input(
                "Horas de Marcha (hs)",
                min_value=0.0,
                max_value=24.0,
                step=0.25,
                format="%.2f",
                value=float(datos_previos.get("horas_marcha") or 24.0),
            )
            observaciones = st.text_input(
                "Observaciones (opcional)",
                value=str(datos_previos.get("observaciones") or ""),
            )

        guardado = st.form_submit_button("💾 Guardar Carga Manual", type="primary")

        if guardado:
            payload = {
                "fecha": fecha_iso,
                "tot_bza_tl": tot_bza_tl,
                "tot_litros_agua": tot_litros_agua,
                "tot_bza_b1": tot_bza_b1,
                "tot_embolse": tot_embolse,
                "kg_tp": kg_tp,
                "kg_pasta": kg_pasta,
                "kg_pan": kg_pan,
                "kg_semita": kg_semita,
                "kg_salvado_grueso": kg_salvado_grueso,
                "kg_salvado_fino": kg_salvado_fino,
                "horas_marcha": horas_marcha,
                "observaciones": observaciones.strip() if observaciones else None,
                "actualizado_en": datetime.now(TZ_AR).isoformat(),
            }
            try:
                supabase_client.table("produccion_cargas_manuales").upsert(payload).execute()
                st.success(f"✅ Registro guardado para el {fecha_carga.strftime('%d/%m/%Y')}.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar en Supabase: {e}")

    st.subheader("📋 Consolidado Diario: Hoja A y B (Últimos 2 días)")
    try:
        res_vista = (
            supabase_client.table("vw_produccion_diaria")
            .select("*")
            .order("fecha", desc=True)
            .limit(2)
            .execute()
        )
        df_consolidado = pd.DataFrame(res_vista.data or [])
        if not df_consolidado.empty:
            df_mostrar = df_consolidado.rename(
                columns={
                    "fecha": "Fecha",
                    "bza_ts": "bza TS",
                    "bza_tl": "bza TL",
                    "litros_agua": "Litros",
                    "kg_basura": "Basura",
                    "pct_basura": "% Bas.",
                    "bza_b1": "bza B1",
                    "bza_3_0": "bza 3/0",
                    "pasta": "Pasta",
                    "pan": "Pan",
                    "bza_4_0": "bza 4/0",
                    "kg_tp": "KG TP",
                    "slin": "Semolín",
                    "bza_af": "bza Af",
                    "sta": "Semita",
                    "af_sdo_gr": "Sdo Gr",
                    "af_f": "af f",
                    "total_subproductos": "Tot. Subpr.",
                    "total_molido": "Tot. Molido",
                    "pct_extraccion": "% EXT.",
                    "horas_marcha": "Hs",
                    "molienda_x_hora": "Mol/h",
                    "oee_pct": "OEE %",
                    "trigo_a": "Trigo A",
                    "trigo_b": "Trigo B",
                    "pellets": "Pellets",
                    "envasado": "Envasado",
                }
            )
            st.dataframe(df_mostrar, hide_index=True, width="stretch", height=110)
        else:
            st.info("Sin filas consolidadas en `vw_produccion_diaria`.")
    except Exception as e:
        st.error(f"Error al leer la vista consolidada: {e}")
