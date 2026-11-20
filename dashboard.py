import pathlib

codigo = '''import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
from supabas
e import create_client

st.set_page_config(page_title="Dashboard Molino de Trigo", layout="wide", page_icon="🌾")

SUPABASE_URL = "https://wyvnwrvumqpztsjyhcgx.supabase.co"
SUPABASE_KEY = "sb_publishable_sXggrAG_UTWzoN_XPWL_fg_AW80e0Tc"
TZ_AR = timezone(timedelta(hours=-3))


@st.cache_resource(ttl=600)
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


supabase = init_supabase()


def cargar_datos():
    res_cabecera = supabase.table("poc_registro_produccion").select("*").order("fecha", desc=True).execute()
    df_cabecera = pd.DataFrame(res_cabecera.data)

    res_productos = supabase.table("poc_produccion_productos").select("*").execute()
    df_productos = pd.DataFrame(res_productos.data)

    res_paradas = supabase.table("poc_paradas").select("*").execute()
    df_paradas = pd.DataFrame(res_paradas.data) if res_paradas.data else pd.DataFrame()

    try:
        res_acopio = supabase.table("poc_stock_acopio").select("*").order("fecha", desc=True).execute()
        df_acopio = pd.DataFrame(res_acopio.data) if res_acopio.data else pd.DataFrame()
    except Exception:
        df_acopio = pd.DataFrame()

    try:
        res_sem = supabase.table("poc_gestion_semanal").select("*").order("inicio_sab", desc=True).execute()
        df_sem = pd.DataFrame(res_sem.data) if res_sem.data else pd.DataFrame()
    except Exception:
        df_sem = pd.DataFrame()

    try:
        res_lab = supabase.table("poc_laboratorio_semanal").select("*").execute()
        df_lab = pd.DataFrame(res_lab.data) if res_lab.data else pd.DataFrame()
    except Exception:
        df_lab = pd.DataFrame()

    try:
        res_ev = supabase.table("poc_eventos_semanales").select("*").execute()
        df_ev = pd.DataFrame(res_ev.data) if res_ev.data else pd.DataFrame()
    except Exception:
        df_ev = pd.DataFrame()

    return df_cabecera, df_productos, df_paradas, df_acopio, df_sem, df_lab, df_ev


def parsear_horas_a_decimal(val):
    if not val or str(val).lower() == "none":
        return 0.0
    try:
        partes = str(val).split(":")
        h = float(partes[0])
        m = float(partes[1]) if len(partes) > 1 else 0.0
        s = float(partes[2]) if len(partes) > 2 else 0.0
        return h + (m / 60.0) + (s / 3600.0)
    except Exception:
        return 0.0


def obtener_horas_netas_str(row):
    hn = row.get("horas_netas")
    if hn and str(hn).lower() not in ("none", "nan", ""):
        return str(hn)
    hm = row.get("horas_marcha")
    if hm and str(hm).lower() not in ("none", "nan", ""):
        return str(hm)
    return "08:00:00"


def fmt_kg(val):
    num = float(pd.to_numeric(val, errors="coerce") or 0.0)
    return f"{int(num):,} kg" if num.is_integer() else f"{num:,.2f} kg"


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
        .limit(10)
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
        df_caud = df_caud.dropna(subset=["fecha_captura"]).copy()
    if not df_caud.empty:
        df_caud["dt"] = pd.to_datetime(df_caud["fecha_captura"], format="ISO8601", utc=True)
        ultima_lectura = df_caud.iloc[0]["dt"].astimezone(TZ_AR)
        minutos_sin_datos = (datetime.now(TZ_AR) - ultima_lectura).total_seconds() / 60.0

        if pd.notna(minutos_sin_datos) and minutos_sin_datos > 20:
            alertas.append(
                f"⏱️ **Sin lecturas recientes de caudales:** última transmisión hace {int(minutos_sin_datos)} min ({ultima_lectura.strftime('%d/%m %H:%M')})."
            )

        if float(df_caud.iloc[0].get("caudal_ing_trg") or 0) <= 0:
            alertas.append("🛑 **Molino detenido / sin caudal de ingreso de trigo:** Caudal IngTrig en 0 kg/h.")

    if alertas:
        for msg in alertas:
            st.error(msg)
    else:
        st.success("✅ Operación Aumax normal: molino en marcha con caudal activo y extracción dentro de parámetro.")

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
            height=290,
        )
        st.plotly_chart(fig_caud, width="stretch")

    st.divider()

    col_corte, col_rec = st.columns(2)
    with col_corte:
        st.subheader("🕛 Corte Diario 00:00 hs (Últimos 2 días)")
        if not df_corte.empty:
            cols_c = ["fecha_corte", "receta_hab", "kg_dia_trigo", "kg_dia_3x0", "kg_dia_4x0", "kg_dia_afrechillo"]
            cols_ok = [c for c in cols_c if c in df_corte.columns]
            st.dataframe(df_corte[cols_ok].head(2), width="stretch", hide_index=True, height=110)
        else:
            st.info("Sin cortes registrados.")

    with col_rec:
        st.subheader("📊 Producción Neta por Receta (Últimas 2)")
        if not df_rec_all.empty:
            df_rec_limpio = df_rec_all[df_rec_all["receta_anterior"].astype(str) != "0"].copy()
            res_rec = (
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
            res_rec["Ext. (%)"] = (
                (res_rec["4/0 (kg)"] + res_rec["3/0 (kg)"]) / res_rec["Trigo (kg)"].replace(0, pd.NA) * 100
            ).round(2)
            st.dataframe(res_rec.head(2), width="stretch", hide_index=True, height=110)
        else:
            st.info("Sin cambios de receta registrados.")


def render_formulario_carga_manual(supabase_client):
    st.subheader("📝 Carga Manual Diaria (Lecturas de Totalizadores y Subproductos)")

    fecha_carga = st.date_input("Fecha del parte diario", value=datetime.now(TZ_AR).date(), key="fecha_carga_manual")
    fecha_iso = fecha_carga.isoformat()

    datos_previos = {}
    try:
        res_prev = supabase_client.table("produccion_cargas_manuales").select("*").eq("fecha", fecha_iso).execute()
        if res_prev.data:
            datos_previos = res_prev.data[0]
            st.info(f"ℹ️ Ya existe registro para el {fecha_carga.strftime('%d/%m/%Y')}. Puedes editarlo.")
    except Exception as e:
        st.warning(f"No se pudo consultar registros previos: {e}")

    with st.form("form_produccion_manual"):
        st.caption("🔢 Lecturas de Totalizadores al Cierre del Día (se resta automáticamente el día anterior)")
        t1, t2, t3, t4 = st.columns(4)
        with t1:
            tot_bza_tl = st.number_input("Totalizador bza TL (Trigo Limpio)", min_value=0.0, step=100.0, format="%.1f", value=float(datos_previos.get("tot_bza_tl") or 0.0))
        with t2:
            tot_litros_agua = st.number_input("Totalizador Adición de Agua (Litros)", min_value=0.0, step=10.0, format="%.1f", value=float(datos_previos.get("tot_litros_agua") or 0.0))
        with t3:
            tot_bza_b1 = st.number_input("Totalizador Balanza B1 (Trigo A)", min_value=0.0, step=100.0, format="%.1f", value=float(datos_previos.get("tot_bza_b1") or 0.0))
        with t4:
            tot_embolse = st.number_input("Totalizador Balanza Embolse", min_value=0.0, step=100.0, format="%.1f", value=float(datos_previos.get("tot_embolse") or 0.0))

        st.caption("📦 Kilos Netos del Día (Subproductos Manuales, Desglose y Horas de Marcha)")
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            kg_semita = st.number_input("Semita - sta (kg)", min_value=0.0, step=10.0, format="%.1f", value=float(datos_previos.get("kg_semita") or 0.0))
            kg_tp = st.number_input("KG TP (kg)", min_value=0.0, step=10.0, format="%.1f", value=float(datos_previos.get("kg_tp") or 0.0))
        with m2:
            kg_salvado_grueso = st.number_input("Salvado Grueso - AF/Sdo gr (kg)", min_value=0.0, step=10.0, format="%.1f", value=float(datos_previos.get("kg_salvado_grueso") or 0.0))
            kg_pasta = st.number_input("3/0 Pasta (kg)", min_value=0.0, step=10.0, format="%.1f", value=float(datos_previos.get("kg_pasta") or 0.0))
        with m3:
            kg_salvado_fino = st.number_input("Salvado Fino - af f (kg)", min_value=0.0, step=10.0, format="%.1f", value=float(datos_previos.get("kg_salvado_fino") or 0.0))
            kg_pan = st.number_input("3/0 Pan (kg)", min_value=0.0, step=10.0, format="%.1f", value=float(datos_previos.get("kg_pan") or 0.0))
        with m4:
            horas_marcha = st.number_input("Horas de Marcha (hs)", min_value=0.0, max_value=24.0, step=0.25, format="%.2f", value=float(datos_previos.get("horas_marcha") or 24.0))
            observaciones = st.text_input("Observaciones (opcional)", value=str(datos_previos.get("observaciones") or ""))

        if st.form_submit_button("💾 Guardar Carga Manual", type="primary"):
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
        res_vista = supabase_client.table("vw_produccion_diaria").select("*").order("fecha", desc=True).limit(2).execute()
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


st.title("🌾 Dashboard de Producción - Molino de Trigo")

if st.sidebar.button("🔄 Actualizar Datos", width="stretch"):
    st.cache_resource.clear()
    st.rerun()

try:
    df_cabecera, df_productos, df_paradas, df_acopio, df_sem, df_lab, df_ev = cargar_datos()

    tab_diario, tab_acopio, tab_semanal, tab_aumax = st.tabs([
        "🏭 Producción Diaria & Turnos",
        "🌾 Stock Planta Acopio (Silos)",
        "📊 Gestión Semanal (Plan vs Real · Envasado · Laboratorio)",
        "⚙️ Molino Aumax (Balanzas & Recetas)",
    ])

    with tab_diario:
        if not df_cabecera.empty:
            df_cabecera = df_cabecera[df_cabecera["fecha"] >= "2026-11-10"].copy()

        if df_cabecera.empty:
            st.warning("No hay registros cargados en la base de datos.")
        else:
            st.sidebar.header("Filtros Producción Diaria")
            fechas_disp = sorted(df_cabecera["fecha"].dropna().unique().tolist(), reverse=True)
            fecha_sel = st.sidebar.selectbox("Seleccionar Fecha", fechas_disp)
            df_fecha = df_cabecera[df_cabecera["fecha"] == fecha_sel].copy()

            orden_turnos = {"MAÑANA": 1, "MANANA": 1, "TARDE": 2, "NOCHE": 3}
            df_fecha["orden"] = df_fecha["turno"].str.upper().str.strip().map(orden_turnos).fillna(99)
            df_fecha = df_fecha.sort_values(by=["orden", "id"])
            df_fecha["hs_netas_efectivas"] = df_fecha.apply(obtener_horas_netas_str, axis=1)

            st.header(f"📅 Resumen Consolidado del Día ({fecha_sel})")
            cant_turnos = len(df_fecha)
            kgs_dia = pd.to_numeric(df_fecha["kgs_totales_producidos"], errors="coerce").fillna(0).sum()
            kgs_dia_str = fmt_kg(kgs_dia)

            ext_series = pd.to_numeric(df_fecha["porcentaje_extraccion"], errors="coerce").fillna(0)
            ext_prom_dia = ext_series.apply(lambda x: x * 100 if x <= 1 else x).mean() if not ext_series.empty else 0.0
            horas_dia = df_fecha["hs_netas_efectivas"].apply(parsear_horas_a_decimal).sum()

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Turnos Cargados", f"{cant_turnos} / 3")
            k2.metric("Producción Total del Día", kgs_dia_str)
            k3.metric("% Extracción Promedio", f"{ext_prom_dia:.2f}%")
            k4.metric("Horas Marcha Netas (Día)", f"{horas_dia:.2f} hs")

            ids_dia = df_fecha["id"].tolist()
            df_prod_dia = df_productos[df_productos["registro_id"].isin(ids_dia)].copy() if not df_productos.empty else pd.DataFrame()

            col_res_izq, col_res_der = st.columns(2)
            with col_res_izq:
                st.subheader("⏱️ Comparativa por Turno")
                df_t = df_fecha[["turno", "responsable", "hs_netas_efectivas", "kgs_totales_producidos", "porcentaje_extraccion"]].copy()
                df_t["kgs_totales_producidos"] = df_t["kgs_totales_producidos"].apply(fmt_kg)
                df_t["porcentaje_extraccion"] = df_t["porcentaje_extraccion"].apply(
                    lambda x: f"{float(x)*100:.2f}%" if pd.notna(x) and float(x) <= 1 else f"{float(pd.to_numeric(x, errors='coerce') or 0):.2f}%"
                )
                df_t.columns = ["Turno", "Responsable", "Hs. Marcha Netas", "Kgs Producidos", "% Extracción"]
                st.dataframe(df_t, hide_index=True, width="stretch")

            with col_res_der:
                st.subheader("📦 Acumulado por Producto en el Día (Kg)")
                if not df_prod_dia.empty:
                    df_acum = df_prod_dia.groupby("producto", as_index=False)["cantidad_kg"].sum()
                    fig_d = px.bar(df_acum, x="producto", y="cantidad_kg", text="cantidad_kg", color="producto")
                    fig_d.update_traces(texttemplate="%{text:,.0f} kg", textposition="outside")
                    fig_d.update_layout(showlegend=False)
                    st.plotly_chart(fig_d, width="stretch")
                else:
                    st.info("Sin desglose de productos acumulado para este día.")

            st.markdown("---")
            turno_sel = st.sidebar.selectbox("Seleccionar Turno (Detalle)", df_fecha["turno"].unique().tolist())
            st.header(f"🔍 Detalle del Turno: {turno_sel}")

            reg = df_fecha[df_fecha["turno"] == turno_sel].iloc[0]
            reg_id = reg["id"]
            kgs_str = fmt_kg(reg.get("kgs_totales_producidos"))
            ext_v = float(pd.to_numeric(reg.get("porcentaje_extraccion"), errors="coerce") or 0)
            ext_s = f"{ext_v * 100:.2f}%" if ext_v <= 1 else f"{ext_v:.2f}%"

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Responsable", reg.get("responsable", "N/A"))
            c2.metric("Turno", reg.get("turno", "N/A"))
            c3.metric("Hs. Marcha Netas", obtener_horas_netas_str(reg))
            c4.metric("Kgs Totales", kgs_str)
            c5.metric("% Extracción", ext_s)

            df_p_act = df_productos[df_productos["registro_id"] == reg_id].copy() if not df_productos.empty else pd.DataFrame()
            col_l, col_r = st.columns(2)
            with col_l:
                st.subheader("📦 Producción del Turno (Kg)")
                if not df_p_act.empty:
                    fig_b = px.bar(df_p_act, x="producto", y="cantidad_kg", text="cantidad_kg", color="producto")
                    fig_b.update_traces(texttemplate="%{text:,.0f} kg", textposition="outside")
                    st.plotly_chart(fig_b, width="stretch")
                else:
                    st.info("No hay desglose de productos para este turno.")
            with col_r:
                st.subheader("📊 Distribución Porcentual (%)")
                if not df_p_act.empty:
                    fig_t = px.pie(df_p_act, names="producto", values="porcentaje", hole=0.4)
                    st.plotly_chart(fig_t, width="stretch")
                else:
                    st.info("No hay porcentajes registrados para este turno.")

            st.subheader(f"⏱️ Registro de Paradas - Turno {turno_sel}")
            if not df_paradas.empty and "registro_id" in df_paradas.columns:
                df_par_act = df_paradas[df_paradas["registro_id"] == reg_id]
                if not df_par_act.empty:
                    st.dataframe(df_par_act[["motivo", "detalle", "horas_parada"]], hide_index=True, width="stretch")
                else:
                    st.success("No se registraron paradas de planta en este turno.")
            else:
                st.success("No se registraron paradas de planta en este turno.")

    with tab_acopio:
        if df_acopio.empty:
            st.info("Aún no hay registros de stock de acopio sincronizados en Supabase.")
        else:
            df_acopio["toneladas"] = pd.to_numeric(df_acopio["toneladas"], errors="coerce").fillna(0.0)
            df_acopio["corte"] = df_acopio["fecha"].astype(str) + " " + df_acopio["hora"].astype(str)
            corte_sel = st.selectbox("Seleccionar Corte de Inventario", sorted(df_acopio["corte"].unique().tolist(), reverse=True))
            df_corte = df_acopio[df_acopio["corte"] == corte_sel].sort_values(by=["grano", "silo"]).copy()

            total_tn = df_corte["toneladas"].sum()
            trigo_tn = df_corte[df_corte["grano"].str.contains("TRIGO", na=False)]["toneladas"].sum()
            maiz_tn = df_corte[df_corte["grano"].str.contains("MAIZ|MAÍZ", na=False)]["toneladas"].sum()
            silos_act = len(df_corte[df_corte["toneladas"] > 0])

            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Stock Total Acopio", f"{total_tn:,.2f} t")
            a2.metric("Total Trigo", f"{trigo_tn:,.2f} t")
            a3.metric("Total Maíz", f"{maiz_tn:,.2f} t")
            a4.metric("Silos con Existencia", f"{silos_act} / {len(df_corte)}")

            col_ai, col_ad = st.columns([1.4, 1])
            with col_ai:
                fig_s = px.bar(df_corte, x="silo", y="toneladas", color="grano", text="toneladas")
                fig_s.update_traces(texttemplate="%{text:,.1f} t", textposition="outside")
                st.plotly_chart(fig_s, width="stretch")
            with col_ad:
                df_g = df_corte.groupby("grano", as_index=False)["toneladas"].sum()
                st.plotly_chart(px.pie(df_g, names="grano", values="toneladas", hole=0.4), width="stretch")

    with tab_semanal:
        if df_sem.empty:
            st.info("Aún no hay datos sincronizados de Gestión Semanal.")
        else:
            hoy_iso = pd.Timestamp.now().strftime("%Y-%m-%d")

            def fmt_sem(row):
                ini, fin = str(row["inicio_sab"]), str(row["fin_vie"])
                dias = float(pd.to_numeric(row.get("dias_dato_real"), errors="coerce") or 0)
                est = f"🟢 En curso ({dias:g}d)" if ini <= hoy_iso <= fin else ("📅 Futura" if ini > hoy_iso else f"✅ Cerrada ({dias:g}d)")
                return f"Sáb {pd.to_datetime(ini).strftime('%d/%m/%Y')} al Vie {pd.to_datetime(fin).strftime('%d/%m/%Y')} — {est}"

            df_sem = df_sem.sort_values("inicio_sab", ascending=False).reset_index(drop=True)
            df_sem["etiqueta"] = df_sem.apply(fmt_sem, axis=1)
            sem_sel = st.selectbox("Seleccionar Semana Operativa", df_sem["etiqueta"].tolist())
            sem = df_sem[df_sem["etiqueta"] == sem_sel].iloc[0]
            ini_sel = sem["inicio_sab"]

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Trigo Molido / Obj.", f"{float(pd.to_numeric(sem.get('trigo_molido_t'), errors='coerce') or 0):,.1f} t", f"{float(pd.to_numeric(sem.get('cumplimiento_pct'), errors='coerce') or 0):.1f}%")
            m2.metric("Horas Reales", f"{float(pd.to_numeric(sem.get('horas_reales_h'), errors='coerce') or 0):,.1f} h", f"Plan: {float(pd.to_numeric(sem.get('horas_plan_h'), errors='coerce') or 0):,.1f} h")
            m3.metric("Extracción Real", f"{float(pd.to_numeric(sem.get('extraccion_real_pct'), errors='coerce') or 0):.2f}%")
            m4.metric("Total Envasado", f"{float(pd.to_numeric(sem.get('envasado_total_t'), errors='coerce') or 0):,.2f} t")
            m5.metric("Pallets Reales", f"{int(float(pd.to_numeric(sem.get('pallets_reales_total'), errors='coerce') or 0)):,} plts")

            col_l, col_e = st.columns([1.4, 1])
            with col_l:
                st.subheader("🧪 Calidad de Laboratorio")
                df_ls = df_lab[df_lab["inicio_sab"] == ini_sel].copy() if not df_lab.empty else pd.DataFrame()
                if not df_ls.empty:
                    st.dataframe(df_ls[["producto", "parametro", "criterio", "promedio", "desvio", "estado"]], hide_index=True, width="stretch")
                else:
                    st.info("Sin registros de laboratorio para esta semana.")
            with col_e:
                st.subheader("⚠️ Eventos No Programados")
                df_es = df_ev[df_ev["inicio_sab"] == ini_sel].copy() if not df_ev.empty else pd.DataFrame()
                if not df_es.empty:
                    st.dataframe(df_es[["evento", "motivo", "minutos"]], hide_index=True, width="stretch")
                else:
                    st.success("Sin eventos no programados en esta semana.")

    with tab_aumax:
        render_seccion_aumax(supabase)
        st.divider()
        render_formulario_carga_manual(supabase)

except Exception as e:
    st.error(f"Error al conectar o renderizar datos: {e}")
'''

pathlib.Path("dashboard.py").write_text(codigo, encoding="utf-8")
print("OK - dashboard.py generado sin cortes.")
