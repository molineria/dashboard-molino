import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client

# Configuración de página amplia
st.set_page_config(page_title="Dashboard Molino de Trigo", layout="wide", page_icon="🌾")

# === CREDENCIALES DE SUPABASE ===
SUPABASE_URL = "https://wyvnwrvumqpztsjyhcgx.supabase.co"
SUPABASE_KEY = "sb_publishable_sXggrAG_UTWzoN_XPWL_fg_AW80e0Tc"

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

st.title("🌾 Dashboard de Producción - Molino de Trigo")

if st.sidebar.button("🔄 Actualizar Datos", use_container_width=True):
    st.cache_resource.clear()
    st.rerun()

try:
    df_cabecera, df_productos, df_paradas, df_acopio, df_sem, df_lab, df_ev = cargar_datos()

    tab_diario, tab_acopio, tab_semanal = st.tabs([
        "🏭 Producción Diaria & Turnos",
        "🌾 Stock Planta Acopio (Silos)",
        "📊 Gestión Semanal (Plan vs Real · Envasado · Laboratorio)"
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

            st.header(f"📅 Resumen Consolidado del Día ({fecha_sel})")

            cant_turnos = len(df_fecha)
            kgs_dia = pd.to_numeric(df_fecha['kgs_totales_producidos'], errors='coerce').fillna(0).sum()
            kgs_dia_str = f"{int(kgs_dia):,} kg" if float(kgs_dia).is_integer() else f"{kgs_dia:,.2f} kg"

            ext_series = pd.to_numeric(df_fecha['porcentaje_extraccion'], errors='coerce').fillna(0)
            ext_norm = ext_series.apply(lambda x: x * 100 if x <= 1 else x)
            ext_prom_dia = ext_norm.mean() if not ext_norm.empty else 0.0

            horas_dia = df_fecha['horas_marcha'].apply(parsear_horas_a_decimal).sum()

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Turnos Cargados", f"{cant_turnos} / 3")
            k2.metric("Producción Total del Día", kgs_dia_str)
            k3.metric("% Extracción Promedio", f"{ext_prom_dia:.2f}%")
            k4.metric("Horas Marcha Totales", f"{horas_dia:.2f} hs")

            ids_dia = df_fecha['id'].tolist()
            df_prod_dia = df_productos[df_productos['registro_id'].isin(ids_dia)].copy() if not df_productos.empty else pd.DataFrame()

            col_res_izq, col_res_der = st.columns(2)

            with col_res_izq:
                st.subheader("⏱️ Comparativa por Turno")
                df_turnos_tabla = df_fecha[['turno', 'responsable', 'horas_marcha', 'kgs_totales_producidos', 'porcentaje_extraccion']].copy()
                df_turnos_tabla['kgs_totales_producidos'] = df_turnos_tabla['kgs_totales_producidos'].apply(
                    lambda x: f"{int(x):,} kg" if pd.notna(x) and float(x).is_integer() else f"{float(x or 0):,.2f} kg"
                )
                df_turnos_tabla['porcentaje_extraccion'] = df_turnos_tabla['porcentaje_extraccion'].apply(
                    lambda x: f"{float(x)*100:.2f}%" if pd.notna(x) and float(x) <= 1 else f"{float(x or 0):.2f}%"
                )
                df_turnos_tabla.columns = ['Turno', 'Responsable', 'Hs. Marcha', 'Kgs Producidos', '% Extracción']
                st.dataframe(df_turnos_tabla, hide_index=True, use_container_width=True)

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
                    st.plotly_chart(fig_dia_barras, use_container_width=True)
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

            hm = registro_actual.get('horas_marcha')
            hm_str = str(hm) if hm and str(hm).lower() != 'none' else "08:00:00"

            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Responsable", registro_actual.get('responsable', 'N/A'))
            col2.metric("Turno", registro_actual.get('turno', 'N/A'))
            col3.metric("Hs. Marcha Netas", hm_str)
            col4.metric("Kgs Totales", kgs_str)
            col5.metric("% Extracción", ext_str)

            df_prod_actual = df_productos[df_productos['registro_id'] == registro_id].copy() if not df_productos.empty else pd.DataFrame()

            col_left, col_right = st.columns(2)

            with col_left:
                st.subheader("📦 Producción del Turno (Kg)")
                if not df_prod_actual.empty:
                    fig_barras = px.bar(
                        df_prod_actual,
                        x='producto',
                        y='cantidad_kg',
                        text='cantidad_kg',
                        color='producto',
                        labels={'cantidad_kg': 'Kilogramos', 'producto': 'Producto'},
                        title=f"Cantidad producida - {turno_sel}"
                    )
                    fig_barras.update_traces(texttemplate='%{text:,.0f} kg', textposition='outside')
                    st.plotly_chart(fig_barras, use_container_width=True)
                else:
                    st.info("No hay desglose de productos para este turno.")

            with col_right:
                st.subheader("📊 Distribución Porcentual (%)")
                if not df_prod_actual.empty:
                    fig_torta = px.pie(
                        df_prod_actual,
                        names='producto',
                        values='porcentaje',
                        hole=0.4,
                        title=f"Participación por producto - {turno_sel}"
                    )
                    st.plotly_chart(fig_torta, use_container_width=True)
                else:
                    st.info("No hay porcentajes registrados para este turno.")

            st.subheader("📋 Registro Detallado del Turno")
            if not df_prod_actual.empty:
                df_tabla = df_prod_actual[['producto', 'cantidad_kg', 'porcentaje']].copy()
                df_tabla['cantidad_kg'] = df_tabla['cantidad_kg'].apply(lambda x: f"{int(x):,} kg" if float(x).is_integer() else f"{x:,.2f} kg")
                df_tabla['porcentaje'] = df_tabla['porcentaje'].apply(lambda x: f"{x*100:.2f}%" if x <= 1 else f"{x:.2f}%")
                st.dataframe(df_tabla, hide_index=True, use_container_width=True)

            st.markdown("---")
            st.subheader(f"⏱️ Registro de Paradas - Turno {turno_sel}")

            if not df_paradas.empty and 'registro_id' in df_paradas.columns:
                df_paradas_actual = df_paradas[df_paradas['registro_id'] == registro_id]
                if not df_paradas_actual.empty:
                    st.dataframe(df_paradas_actual[['motivo', 'detalle', 'horas_parada']], hide_index=True, use_container_width=True)
                else:
                    st.success("No se registraron paradas de planta en este turno.")
            else:
                st.success("No se registraron paradas de planta en este turno.")

    # =========================================================================
    # PESTAÑA 2: STOCK PLANTA ACOPIO (SILOS)
    # =========================================================================
    with tab_acopio:
        if df_acopio.empty:
            st.info("Aún no hay registros de stock de acopio sincronizados en Supabase.")
        else:
            df_acopio["toneladas"] = pd.to_numeric(df_acopio["toneladas"], errors="coerce").fillna(0.0)
            df_acopio["corte"] = df_acopio["fecha"].astype(str) + " " + df_acopio["hora"].astype(str)
            cortes_unicos = sorted(df_acopio["corte"].unique().tolist(), reverse=True)

            corte_sel = st.selectbox("Seleccionar Corte de Inventario (Fecha y Hora)", cortes_unicos)
            df_corte = df_acopio[df_acopio["corte"] == corte_sel].copy()

            df_corte = df_corte.sort_values(by=["grano", "silo"])

            total_tn = df_corte["toneladas"].sum()
            trigo_tn = df_corte[df_corte["grano"].str.contains("TRIGO", na=False)]["toneladas"].sum()
            maiz_tn = df_corte[df_corte["grano"].str.contains("MAIZ|MAÍZ", na=False)]["toneladas"].sum()
            silos_activos = len(df_corte[df_corte["toneladas"] > 0])

            a1, a2, a3, a4 = st.columns(4)
            a1.metric("Stock Total Acopio", f"{total_tn:,.2f} t")
            a2.metric("Total Trigo", f"{trigo_tn:,.2f} t")
            a3.metric("Total Maíz", f"{maiz_tn:,.2f} t")
            a4.metric("Silos con Existencia", f"{silos_activos} / {len(df_corte)}")

            st.markdown("---")

            col_ac_izq, col_ac_der = st.columns([1.4, 1])

            with col_ac_izq:
                st.subheader("🏗️ Existencia por Silo (Toneladas)")
                fig_silos = px.bar(
                    df_corte,
                    x="silo",
                    y="toneladas",
                    color="grano",
                    text="toneladas",
                    labels={"silo": "Silo", "toneladas": "Toneladas (t)", "grano": "Grano"},
                    title=f"Distribución por Silo ({corte_sel})"
                )
                fig_silos.update_traces(texttemplate="%{text:,.1f} t", textposition="outside")
                st.plotly_chart(fig_silos, use_container_width=True)

            with col_ac_der:
                st.subheader("🌾 Participación por Grano")
                df_grano = df_corte.groupby("grano", as_index=False)["toneladas"].sum()
                fig_grano = px.pie(
                    df_grano,
                    names="grano",
                    values="toneladas",
                    hole=0.4,
                    title="Proporción de stock por grano"
                )
                st.plotly_chart(fig_grano, use_container_width=True)

            st.subheader("📋 Detalle de Silos del Corte")
            df_acopio_tabla = df_corte[["silo", "grano", "toneladas"]].copy()
            df_acopio_tabla["toneladas"] = df_acopio_tabla["toneladas"].apply(lambda x: f"{x:,.2f} t")
            df_acopio_tabla.columns = ["Silo", "Grano / Calidad", "Stock (t)"]
            st.dataframe(df_acopio_tabla, hide_index=True, use_container_width=True)

    # =========================================================================
    # PESTAÑA 3: GESTIÓN SEMANAL (KAN BAN PLANIFICACIÓN)
    # =========================================================================
    with tab_semanal:
        if df_sem.empty:
            st.info("Aún no hay datos sincronizados de Gestión Semanal. Ejecuta `ingesta_gestion.py` en la PC de Planta.")
        else:
            hoy_iso = pd.Timestamp.now().strftime("%Y-%m-%d")

            def formatear_semana(row):
                ini = str(row["inicio_sab"])
                fin = str(row["fin_vie"])
                ini_fmt = pd.to_datetime(ini).strftime("%d/%m/%Y")
                fin_fmt = pd.to_datetime(fin).strftime("%d/%m/%Y")
                dias = float(row.get("dias_dato_real") or 0)
                if ini <= hoy_iso <= fin:
                    estado = f"🟢 Semana en curso ({dias:g} días)"
                elif ini > hoy_iso:
                    estado = "📅 Planificada (futura)"
                else:
                    estado = f"✅ Cerrada ({dias:g} días)"
                return f"Sáb {ini_fmt} al Vie {fin_fmt} — {estado}"

            df_sem = df_sem.sort_values("inicio_sab", ascending=False).reset_index(drop=True)
            df_sem["etiqueta"] = df_sem.apply(formatear_semana, axis=1)

            en_curso = df_sem[(df_sem["inicio_sab"] <= hoy_iso) & (df_sem["fin_vie"] >= hoy_iso)]
            if not en_curso.empty:
                default_idx = int(en_curso.index[0])
            else:
                pasadas = df_sem[df_sem["inicio_sab"] <= hoy_iso]
                default_idx = int(pasadas.index[0]) if not pasadas.empty else 0

            sem_sel_label = st.selectbox("Seleccionar Semana Operativa (Sábado a Viernes)", df_sem["etiqueta"].tolist(), index=default_idx)
            sem = df_sem[df_sem["etiqueta"] == sem_sel_label].iloc[0]
            ini_sel = sem["inicio_sab"]

            trigo_mol = float(sem.get("trigo_molido_t") or 0)
            obj_trigo = float(sem.get("objetivo_trigo_t") or 0)
            cumpl = float(sem.get("cumplimiento_pct") or 0)
            hs_plan = float(sem.get("horas_plan_h") or sem.get("horas_trabajadas") or 0)
            hs_real = float(sem.get("horas_reales_h") or 0)
            ext_real = float(sem.get("extraccion_real_pct") or 0)
            desv_harina = float(sem.get("desvio_real_t_harina") or 0)
            env_tot = float(sem.get("envasado_total_t") or 0)
            pal_tot = float(sem.get("pallets_reales_total") or 0)

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Trigo Molido / Obj.", f"{trigo_mol:,.1f} t", f"{cumpl:.1f}% cumpl. (Obj: {obj_trigo:,.0f} t)")
            m2.metric("Horas Plan vs Real", f"{hs_real:,.1f} h" if hs_real > 0 else f"{hs_plan:,.1f} h plan", f"Plan: {hs_plan:,.1f} h")
            m3.metric("Extracción Real", f"{ext_real:.2f}%" if ext_real > 0 else "Sin cierre", f"{desv_harina:+.2f} t harina vs meta" if ext_real > 0 else None)
            m4.metric("Total Envasado", f"{env_tot:,.2f} t" if env_tot > 0 else "–")
            m5.metric("Pallets Reales", f"{int(pal_tot):,} plts" if pal_tot > 0 else "–")

            st.markdown("---")

            c_izq, c_der = st.columns(2)

            with c_izq:
                st.subheader("🎯 Harina: Plan vs Real vs Envasado (t)")
                productos_comp = ["3/0 Pan", "3/0 Pasta", "4/0", "TP", "Semolín"]
                plan_vals = [
                    float(sem.get("plan_30_pan_t") or 0),
                    float(sem.get("plan_30_pasta_t") or 0),
                    float(sem.get("plan_40_t") or 0),
                    float(sem.get("plan_tp_t") or 0),
                    float(sem.get("plan_semolin_t") or 0),
                ]
                real_vals = [
                    float(sem.get("real_30_pan_t") or 0),
                    float(sem.get("real_30_pasta_t") or 0),
                    float(sem.get("real_40_t") or 0),
                    float(sem.get("real_tp_t") or 0),
                    float(sem.get("real_semolin_t") or 0),
                ]
                env_vals = [
                    float(sem.get("envasado_30_t") or 0),
                    0.0,
                    float(sem.get("envasado_40_t") or 0),
                    float(sem.get("envasado_tp_t") or 0),
                    float(sem.get("envasado_semolin_t") or 0),
                ]

                fig_comp = go.Figure(data=[
                    go.Bar(name="Plan (t)", x=productos_comp, y=plan_vals),
                    go.Bar(name="Real Producido (t)", x=productos_comp, y=real_vals),
                    go.Bar(name="Envasado Real (t)", x=productos_comp, y=env_vals),
                ])
                fig_comp.update_layout(barmode="group", yaxis_title="Toneladas (t)", legend=dict(orientation="h", y=1.12))
                st.plotly_chart(fig_comp, use_container_width=True)

            with c_der:
                st.subheader("📈 Evolución Semanal de Cumplimiento (%)")
                df_hist = df_sem[(df_sem["inicio_sab"] <= hoy_iso) & (pd.to_numeric(df_sem["cumplimiento_pct"], errors="coerce").notna())].sort_values("inicio_sab")
                if not df_hist.empty:
                    fig_evol = px.line(
                        df_hist,
                        x="inicio_sab",
                        y="cumplimiento_pct",
                        markers=True,
                        labels={"inicio_sab": "Inicio Semana", "cumplimiento_pct": "Cumplimiento (%)"},
                        title="Cumplimiento de molienda por semana"
                    )
                    fig_evol.add_hline(y=100, line_dash="dash", line_color="green", annotation_text="Objetivo 100%")
                    st.plotly_chart(fig_evol, use_container_width=True)

            st.markdown("---")

            col_lab, col_ev = st.columns([1.4, 1])

            with col_lab:
                st.subheader("🧪 Calidad de Laboratorio (Promedio Semanal)")
                df_lab_sem = df_lab[df_lab["inicio_sab"] == ini_sel].copy() if not df_lab.empty else pd.DataFrame()
                if not df_lab_sem.empty:
                    df_lab_show = df_lab_sem[["producto", "parametro", "criterio", "promedio", "desvio", "estado"]].copy()
                    df_lab_show.columns = ["Producto", "Parámetro", "Criterio", "Promedio", "Desvío", "Estado"]
                    st.dataframe(df_lab_show, hide_index=True, use_container_width=True)
                else:
                    st.info("Sin registros de laboratorio cargados para esta semana.")

            with col_ev:
                st.subheader("⚠️ Eventos No Programados")
                df_ev_sem = df_ev[df_ev["inicio_sab"] == ini_sel].copy() if not df_ev.empty else pd.DataFrame()
                if not df_ev_sem.empty:
                    df_ev_show = df_ev_sem[["evento", "motivo", "minutos"]].copy()
                    df_ev_show.columns = ["Evento", "Motivo", "Minutos"]
                    st.dataframe(df_ev_show, hide_index=True, use_container_width=True)
                else:
                    st.success("Sin eventos no programados registrados en esta semana.")

            st.markdown("---")
            st.subheader("🌽 Subproductos, Pellet y Línea de Maíz")
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Pellet Subprod. Trigo", f"{float(sem.get('pellet_subprod_trigo_t') or 0):,.2f} t")
            s2.metric("Pellet Total / Camiones", f"{float(sem.get('pellet_total_t') or 0):,.2f} t", f"{float(sem.get('camiones_pellet_total') or 0):.1f} camiones")
            s3.metric("Maíz Molido", f"{float(sem.get('maiz_molido_t') or 0):,.2f} t")
            s4.metric("Polenta / Harina Maíz", f"{float(sem.get('polenta_t') or 0):,.2f} t / {float(sem.get('harina_maiz_t') or 0):,.2f} t")

except Exception as e:
    st.error(f"Error al conectar o renderizar datos: {e}")
