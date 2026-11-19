import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timezone, timedelta
from supabase import create_client

# Configuración de página amplia
st.set_page_config(page_title="Dashboard Molino de Trigo", layout="wide", page_icon="🌾")

# === CREDENCIALES DE SUPABASE ===
SUPABASE_URL = "https://wyvnwrvumqpztsjyhcgx.supabase.co"
SUPABASE_KEY = "sb_publishable_sXggrAG_UTWzoN_XPWL_fg_AW80e0Tc"
TZ_AR = timezone(timedelta(hours=-3))


@st.cache_resource(ttl=600)
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)


supabase = init_supabase()


# === LECTURA DE DATOS DESDE SUPABASE ===
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
    if not val or str(val).lower() == 'none':
        return 0.0
    try:
        partes = str(val).split(':')
        h = float(partes[0])
        m = float(partes[1]) if len(partes) > 1 else 0.0
        s = float(partes[2]) if len(partes) > 2 else 0.0
        return h + (m / 60.0) + (s / 3600.0)
    except Exception:
        return 0.0


def obtener_horas_netas_str(row):
    hn = row.get('horas_netas')
    if hn and str(hn).lower() not in ('none', 'nan', ''):
        return str(hn)
    hm = row.get('horas_marcha')
    if hm and str(hm).lower() not in ('none', 'nan', ''):
        return str(hm)
    return "08:00:00"


# === MÓDULO D: SECCIÓN MOLINO AUMAX ===
def render_seccion_aumax(supabase_client):
    st.header("⚙️ Molino Aumax — Balanzas, Extracción y Recetas")

    # ---------------------------------------------------------
    # 1. CARGA DE DATOS DESDE SUPABASE
    # ---------------------------------------------------------
    q_ext = (
        supabase_client.table("aumax_extraccion_instantanea")
        .select("*")
        .order("fecha_captura", desc=True)
        .limit(200)
        .execute()
    )
    df_ext = pd.DataFrame(q_ext.data or [])

    q_tot = (
        supabase_client.table("aumax_registros_totales")
        .select("*")
        .order("fecha_registro", desc=True)
        .limit(50)
        .execute()
    )
    df_tot = pd.DataFrame(q_tot.data or [])

    q_corte = (
        supabase_client.table("v_aumax_corte_00hs")
        .select("*")
        .order("fecha_corte", desc=True)
        .limit(90)
        .execute()
    )
    df_corte = pd.DataFrame(q_corte.data or [])

    q_rec = (
        supabase_client.table("aumax_diferencia_receta")
        .select("*")
        .order("fecha_evento_actual", desc=True)
        .limit(500)
        .execute()
    )
    df_rec_all = pd.DataFrame(q_rec.data or [])

    # ---------------------------------------------------------
    # 2. SISTEMA DE ALERTAS OPERATIVAS
    # ---------------------------------------------------------
    UMBRAL_EXTRACCION_MIN = 77.0  # Ajustar según objetivo de molienda
    alertas = []

    if not df_ext.empty:
        ultima_ext = float(df_ext.iloc[0]["extraccion_pct"])
        if ultima_ext < UMBRAL_EXTRACCION_MIN:
            alertas.append(
                f"📉 **Extracción baja detectada:** {ultima_ext:.2f}% (por debajo del objetivo de {UMBRAL_EXTRACCION_MIN:.1f}%)."
            )

    if not df_tot.empty:
        df_tot["dt"] = pd.to_datetime(df_tot["fecha_registro"])
        ultima_lectura = df_tot.iloc[0]["dt"].astimezone(TZ_AR)
        ahora_ar = datetime.now(TZ_AR)
        minutos_sin_datos = (ahora_ar - ultima_lectura).total_seconds() / 60.0

        if minutos_sin_datos > 20:
            alertas.append(
                f"⏱️ **Sin lecturas recientes de Aumax:** última transmisión hace {int(minutos_sin_datos)} min ({ultima_lectura.strftime('%d/%m %H:%M')})."
            )

        # Verificar si el acumulador de trigo avanzó en los últimos ~30 min (10 registros)
        if len(df_tot) >= 10:
            trigo_actual = float(df_tot.iloc[0]["total_blz_ing_trg"] or 0)
            trigo_hace_30m = float(df_tot.iloc[9]["total_blz_ing_trg"] or 0)
            if trigo_actual == trigo_hace_30m:
                alertas.append(
                    "🛑 **Molino detenido / sin ingreso de trigo:** el acumulador de balanza de trigo no varió en los últimos 30 minutos."
                )

    if alertas:
        for msg in alertas:
            st.error(msg)
    else:
        st.success("✅ Operación Aumax normal: extracción dentro de parámetro y molienda activa.")

    # ---------------------------------------------------------
    # 3. KPIs INSTANTÁNEOS
    # ---------------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    ext_val = f"{df_ext.iloc[0]['extraccion_pct']:.2f}%" if not df_ext.empty else "S/D"
    receta_act = df_tot.iloc[0]["receta_hab"] if not df_tot.empty else "S/D"
    silo_act = f"Silo {df_tot.iloc[0]['silo_hab']}" if not df_tot.empty else "S/D"
    hora_act = (
        pd.to_datetime(df_tot.iloc[0]["fecha_registro"]).astimezone(TZ_AR).strftime("%d/%m %H:%M")
        if not df_tot.empty
        else "S/D"
    )

    col1.metric("Extracción Instantánea", ext_val)
    col2.metric("Receta Activa", receta_act)
    col3.metric("Silo Habilitado", silo_act)
    col4.metric("Último Registro PLC", hora_act)

    st.divider()

    # ---------------------------------------------------------
    # 4. FILTRO POR SEMANA OPERATIVA (SÁBADO A VIERNES)
    # ---------------------------------------------------------
    semanas_disp = sorted(
        list(
            set(
                (df_corte["inicio_sab"].dropna().unique().tolist() if not df_corte.empty else [])
                + (df_rec_all["inicio_sab"].dropna().unique().tolist() if not df_rec_all.empty else [])
            )
        ),
        reverse=True,
    )

    opciones_sem = ["Todas (Últimos registros)"] + semanas_disp
    sem_aumax_sel = st.selectbox(
        "Filtrar por Semana Operativa Aumax (Inicio Sábado)",
        opciones_sem,
        key="filtro_semana_aumax",
    )
    semana_filtro = None if sem_aumax_sel == "Todas (Últimos registros)" else sem_aumax_sel

    # ---------------------------------------------------------
    # 5. CORTE DIARIO DE BALANZAS A LAS 00:00 (±3 MIN)
    # ---------------------------------------------------------
    st.subheader("🕛 Corte Diario de Balanzas a las 00:00 hs (±3 min)")
    if not df_corte.empty:
        if semana_filtro and "inicio_sab" in df_corte.columns:
            df_corte_vista = df_corte[df_corte["inicio_sab"] == semana_filtro].copy()
        else:
            df_corte_vista = df_corte.head(14).copy()

        if not df_corte_vista.empty:
            df_corte_vista["hora_exacta_lectura"] = pd.to_datetime(
                df_corte_vista["hora_exacta_lectura"]
            ).dt.strftime("%Y-%m-%d %H:%M:%S")

            cols_mostrar = [
                "fecha_corte",
                "hora_exacta_lectura",
                "receta_hab",
                "silo_hab",
                "total_blz_ing_trg",
                "total_blz_4x0",
                "total_blz_3x0",
                "total_blz_afrch",
                "kg_dia_trigo",
                "kg_dia_4x0",
                "kg_dia_3x0",
                "kg_dia_afrechillo",
            ]
            cols_existentes = [c for c in cols_mostrar if c in df_corte_vista.columns]
            st.dataframe(df_corte_vista[cols_existentes], width="stretch", hide_index=True)
        else:
            st.info("No hay cortes de medianoche registrados para la semana seleccionada.")
    else:
        st.info("Aún no hay registros de corte de medianoche en el rango consultado.")

    st.divider()

    # ---------------------------------------------------------
    # 6. RENDIMIENTO Y KILOS NETOS POR RECETA
    # ---------------------------------------------------------
    st.subheader("📊 Producción Neta por Cambio de Receta")
    if not df_rec_all.empty:
        df_rec = (
            df_rec_all[df_rec_all["inicio_sab"] == semana_filtro].copy()
            if semana_filtro
            else df_rec_all.copy()
        )

        if not df_rec.empty:
            resumen_receta = (
                df_rec.groupby("receta_anterior", as_index=False)[
                    ["diff_blz_ing_trg", "diff_blz_4x0", "diff_blz_3x0", "diff_blz_afrch"]
                ]
                .sum()
                .rename(
                    columns={
                        "receta_anterior": "Receta",
                        "diff_blz_ing_trg": "Trigo (kg)",
                        "diff_blz_4x0": "Harina 0000 (kg)",
                        "diff_blz_3x0": "Harina 000 (kg)",
                        "diff_blz_afrch": "Afrechillo (kg)",
                    }
                )
            )
            resumen_receta["Extracción Real (%)"] = (
                (resumen_receta["Harina 0000 (kg)"] + resumen_receta["Harina 000 (kg)"])
                / resumen_receta["Trigo (kg)"].replace(0, pd.NA)
                * 100
            ).round(2)

            c1, c2 = st.columns([1.2, 1])
            with c1:
                st.dataframe(resumen_receta, width="stretch", hide_index=True)
            with c2:
                fig = px.bar(
                    resumen_receta,
                    x="Receta",
                    y=["Harina 0000 (kg)", "Harina 000 (kg)", "Afrechillo (kg)"],
                    barmode="stack",
                    title="Distribución de Productos por Receta (kg)",
                )
                st.plotly_chart(fig, width="stretch")
        else:
            st.info("No hay cambios de receta registrados para la semana seleccionada.")
    else:
        st.info("Aún no hay datos de diferencia por receta sincronizados.")


# === FORMULARIO DE CARGA MANUAL Y CONSOLIDADO DIARIO ===
def render_formulario_carga_manual(supabase_client):
    st.subheader("📝 Carga Manual Diaria (Balanzas Manuales, Subproductos y Envasado)")

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
            st.info(
                f"ℹ️ Ya existe una carga para el {fecha_carga.strftime('%d/%m/%Y')}. "
                "Puedes modificar los valores y volver a guardar."
            )
    except Exception as e:
        st.warning(f"No se pudo consultar registros previos: {e}")

    with st.form("form_produccion_manual"):
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            kg_bza_tl = st.number_input(
                "Trigo Limpio - bza TL (kg)",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                value=float(datos_previos.get("kg_bza_tl") or 0.0),
            )
            kg_bza_b1 = st.number_input(
                "Balanza B1 (kg)",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                value=float(datos_previos.get("kg_bza_b1") or 0.0),
            )

        with c2:
            kg_tp = st.number_input(
                "KG TP (kg)",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                value=float(datos_previos.get("kg_tp") or 0.0),
            )
            kg_semita = st.number_input(
                "Semita - sta (kg)",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                value=float(datos_previos.get("kg_semita") or 0.0),
            )

        with c3:
            kg_salvado_grueso = st.number_input(
                "Salvado Grueso - AF/Sdo gr (kg)",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                value=float(datos_previos.get("kg_salvado_grueso") or 0.0),
            )
            kg_salvado_fino = st.number_input(
                "Salvado Fino - af f (kg)",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                value=float(datos_previos.get("kg_salvado_fino") or 0.0),
            )

        with c4:
            kg_envasado = st.number_input(
                "Envasado - Embolse (kg)",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                value=float(datos_previos.get("kg_envasado") or 0.0),
            )
            observaciones = st.text_input(
                "Observaciones (opcional)",
                value=str(datos_previos.get("observaciones") or ""),
            )

        guardado = st.form_submit_button("💾 Guardar Carga Manual", type="primary")

        if guardado:
            payload = {
                "fecha": fecha_iso,
                "kg_bza_tl": kg_bza_tl,
                "kg_bza_b1": kg_bza_b1,
                "kg_tp": kg_tp,
                "kg_semita": kg_semita,
                "kg_salvado_grueso": kg_salvado_grueso,
                "kg_salvado_fino": kg_salvado_fino,
                "kg_envasado": kg_envasado,
                "observaciones": observaciones.strip() if observaciones else None,
                "actualizado_en": datetime.now(TZ_AR).isoformat(),
            }
            try:
                supabase_client.table("produccion_cargas_manuales").upsert(payload).execute()
                st.success(f"✅ Datos guardados correctamente para el {fecha_carga.strftime('%d/%m/%Y')}.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error al guardar en Supabase: {e}")

    st.subheader("📋 Consolidado Diario: Aumax + Cargas Manuales + Cálculos")
    try:
        res_vista = (
            supabase_client.table("vw_produccion_diaria")
            .select("*")
            .order("fecha", desc=True)
            .limit(15)
            .execute()
        )
        df_consolidado = pd.DataFrame(res_vista.data or [])
        if not df_consolidado.empty:
            df_mostrar = df_consolidado.rename(
                columns={
                    "fecha": "Fecha",
                    "bza_ts": "bza TS (kg)",
                    "bza_tl": "bza TL (kg)",
                    "kg_basura": "Basura (kg)",
                    "bza_b1": "bza B1 (kg)",
                    "bza_3_0": "bza 3/0 (kg)",
                    "bza_4_0": "bza 4/0 (kg)",
                    "slin": "Semolín (kg)",
                    "kg_tp": "KG TP (kg)",
                    "bza_af": "bza Af (kg)",
                    "sta": "Semita (kg)",
                    "af_sdo_gr": "Salvado Gr. (kg)",
                    "af_f": "Salvado Fino (kg)",
                    "total_subproductos": "Total Subprod. (kg)",
                    "pellet": "Pellet (kg)",
                    "total_molido": "Total Molido (kg)",
                    "envasado": "Envasado (kg)",
                }
            )
            st.dataframe(df_mostrar, hide_index=True, width="stretch")
        else:
            st.info("Aún no hay filas consolidadas en `vw_produccion_diaria`.")
    except Exception as e:
        st.error(f"Error al leer la vista consolidada: {e}")


# === INTERFAZ PRINCIPAL ===
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

    # =========================================================================
    # PESTAÑA 1: PRODUCCIÓN DIARIA Y TURNOS
    # =========================================================================
    with tab_diario:
        if not df_cabecera.empty:
            df_cabecera = df_cabecera[df_cabecera['fecha'] >= '2026-11-10'].copy()

        if df_cabecera.empty:
            st.warning("No hay registros cargados en la base de datos.")
        else:
            st.sidebar.header("Filtros Producción Diaria")
            fechas_disponibles = sorted(df_cabecera['fecha'].dropna().unique().tolist(), reverse=True)
            fecha_sel = st.sidebar.selectbox("Seleccionar Fecha", fechas_disponibles)

            df_fecha = df_cabecera[df_cabecera['fecha'] == fecha_sel].copy()

            orden_turnos = {'MAÑANA': 1, 'MANANA': 1, 'TARDE': 2, 'NOCHE': 3}
            df_fecha['orden'] = df_fecha['turno'].str.upper().str.strip().map(orden_turnos).fillna(99)
            df_fecha = df_fecha.sort_values(by=['orden', 'id'])
            df_fecha['hs_netas_efectivas'] = df_fecha.apply(obtener_horas_netas_str, axis=1)

            st.header(f"📅 Resumen Consolidado del Día ({fecha_sel})")

            cant_turnos = len(df_fecha)
            kgs_dia = pd.to_numeric(df_fecha['kgs_totales_producidos'], errors='coerce').fillna(0).sum()
            kgs_dia_str = f"{int(kgs_dia):,} kg" if float(kgs_dia).is_integer() else f"{kgs_dia:,.2f} kg"

            ext_series = pd.to_numeric(df_fecha['porcentaje_extraccion'], errors='coerce').fillna(0)
            ext_norm = ext_series.apply(lambda x: x * 100 if x <= 1 else x)
            ext_prom_dia = ext_norm.mean() if not ext_norm.empty else 0.0

            horas_dia = df_fecha['hs_netas_efectivas'].apply(parsear_horas_a_decimal).sum()

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Turnos Cargados", f"{cant_turnos} / 3")
            k2.metric("Producción Total del Día", kgs_dia_str)
            k3.metric("% Extracción Promedio", f"{ext_prom_dia:.2f}%")
            k4.metric("Horas Marcha Netas (Día)", f"{horas_dia:.2f} hs")

            ids_dia = df_fecha['id'].tolist()
            df_prod_dia = df_productos[df_productos['registro_id'].isin(ids_dia)].copy() if not df_productos.empty else pd.DataFrame()

            col_res_izq, col_res_der = st.columns(2)

            with col_res_izq:
                st.subheader("⏱️ Comparativa por Turno")
                df_turnos_tabla = df_fecha[['turno', 'responsable', 'hs_netas_efectivas', 'kgs_totales_producidos', 'porcentaje_extraccion']].copy()
                df_turnos_tabla['kgs_totales_producidos'] = df_turnos_tabla['kgs_totales_producidos'].apply(
                    lambda x: f"{int(x):,} kg" if pd.notna(x) and float(x).is_integer() else f"{float(x or 0):,.2f} kg"
                )
                df_turnos_tabla['porcentaje_extraccion'] = df_turnos_tabla['porcentaje_extraccion'].apply(
                    lambda x: f"{float(x)*100:.2f}%" if pd.notna(x) and float(x) <= 1 else f"{float(x or 0):.2f}%"
                )
                df_turnos_tabla.columns = ['Turno', 'Responsable', 'Hs. Marcha Netas', 'Kgs Producidos', '% Extracción']
                st.dataframe(df_turnos_tabla, hide_index=True, width="stretch")

            with col_res_der:
                st.subheader("📦 Acumulado por Producto en el Día (Kg)")
                if not df_prod_dia.empty:
                    df_acum_prod = df_prod_dia.groupby('producto', as_index=False)['cantidad_kg'].sum()
                    fig_dia_barras = px.bar(
                        df_acum_prod,
                        x='producto',
                        y='cantidad_kg',
                        text='cantidad_kg',
                        color='producto',
                        labels={'cantidad_kg': 'Kilogramos Totales', 'producto': 'Producto'},
                        title="Total diario producido por variedad"
                    )
                    fig_dia_barras.update_traces(texttemplate='%{text:,.0f} kg', textposition='outside')
                    fig_dia_barras.update_layout(showlegend=False)
                    st.plotly_chart(fig_dia_barras, width="stretch")
                else:
                    st.info("Sin desglose de productos acumulado para este día.")

            st.markdown("---")

            turnos_disponibles = df_fecha['turno'].unique().tolist()
            turno_sel = st.sidebar.selectbox("Seleccionar Turno (Detalle)", turnos_disponibles)

            st.header(f"🔍 Detalle del Turno: {turno_sel}")

            registro_actual = df_fecha[df_fecha['turno'] == turno_sel].iloc[0]
            registro_id = registro_actual['id']

            kgs_totales = registro_actual.get('kgs_totales_producidos', 0) or 0
            kgs_str = f"{int(kgs_totales):,} kg" if float(kgs_totales).is_integer() else f"{kgs_totales:,.2f} kg"

            ext_val = float(registro_actual.get('porcentaje_extraccion', 0) or 0)
            ext_str = f"{ext_val * 100:.2f}%" if ext_val <= 1 else f"{ext_val:.2f}%"

            hm_str = obtener_horas_netas_str(registro_actual)

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Responsable", registro_actual.get('responsable', 'N/A'))
            col2.metric
