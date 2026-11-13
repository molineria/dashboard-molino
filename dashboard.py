import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from supabase import create_client

st.set_page_config(page_title="Dashboard Molino y Acopio", layout="wide", page_icon="🌾")

# === CREDENCIALES DE SUPABASE ===
SUPABASE_URL = "https://wyvnwrvumqpztsjyhcgx.supabase.co"
SUPABASE_KEY = "sb_publishable_sXggrAG_UTWzoN_XPWL_fg_AW80e0Tc"

# === CAPACIDADES DE SILOS (EN TONELADAS) ===
CAPACIDADES_SILOS = {
    "1A": 970, "2A": 970, "3A": 970, "4A": 970, "5A": 2700,
    "SMT": 150, "SMM": 90,
    "SP1": 150, "SP2": 150, "SP3": 150, "SP4": 150, "SP5": 150, "SP6": 150
}
ORDEN_SILOS = ["1A", "2A", "3A", "4A", "5A", "SMT", "SMM", "SP1", "SP2", "SP3", "SP4", "SP5", "SP6"]

@st.cache_resource(ttl=600)
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

def cargar_datos_molino():
    res_cab = supabase.table("poc_registro_produccion").select("*").order("fecha", desc=True).execute()
    res_prod = supabase.table("poc_produccion_productos").select("*").execute()
    res_par = supabase.table("poc_paradas").select("*").execute()
    return (
        pd.DataFrame(res_cab.data),
        pd.DataFrame(res_prod.data),
        pd.DataFrame(res_par.data) if res_par.data else pd.DataFrame()
    )

def cargar_datos_acopio():
    try:
        res = supabase.table("poc_stock_acopio").select("*").order("fecha", desc=True).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception:
        return pd.DataFrame()

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

st.title("🌾 Tablero Operativo - Molino de Trigo y Planta de Acopio")

if st.sidebar.button("🔄 Actualizar Datos", use_container_width=True):
    st.cache_resource.clear()
    st.rerun()

tab_molino, tab_acopio = st.tabs(["🌾 Molino de Trigo (Producción)", "🏭 Planta de Acopio (Stock)"])

# ==============================================================================
# PESTAÑA 1: MOLINO DE TRIGO
# ==============================================================================
with tab_molino:
    try:
        df_cabecera, df_productos, df_paradas = cargar_datos_molino()

        if not df_cabecera.empty:
            df_cabecera = df_cabecera[df_cabecera['fecha'] >= '2026-11-10'].copy()

        if df_cabecera.empty:
            st.warning("No hay registros de producción cargados.")
        else:
            st.sidebar.header("Filtros Molino")
            fechas_disp = sorted(df_cabecera['fecha'].dropna().unique().tolist(), reverse=True)
            fecha_sel = st.sidebar.selectbox("Fecha Producción", fechas_disp)

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
                        df_acum_prod, x='producto', y='cantidad_kg', text='cantidad_kg', color='producto',
                        labels={'cantidad_kg': 'Kilogramos Totales', 'producto': 'Producto'}
                    )
                    fig_dia_barras.update_traces(texttemplate='%{text:,.0f} kg', textposition='outside')
                    fig_dia_barras.update_layout(showlegend=False)
                    st.plotly_chart(fig_dia_barras, use_container_width=True)
                else:
                    st.info("Sin desglose de productos acumulado para este día.")

            st.markdown("---")
            turnos_disponibles = df_fecha['turno'].unique().tolist()
            turno_sel = st.sidebar.selectbox("Turno (Detalle Molino)", turnos_disponibles)

            st.header(f"🔍 Detalle del Turno: {turno_sel}")
            registro_actual = df_fecha[df_fecha['turno'] == turno_sel].iloc[0]
            registro_id = registro_actual['id']

            kgs_totales = registro_actual.get('kgs_totales_producidos', 0) or 0
            kgs_str = f"{int(kgs_totales):,} kg" if float(kgs_totales).is_integer() else f"{kgs_totales:,.2f} kg"
            ext_val = float(registro_actual.get('porcentaje_extraccion', 0) or 0)
            ext_str = f"{ext_val * 100:.2f}%" if ext_val <= 1 else f"{ext_val:.2f}%"
            hm = registro_actual.get('horas_marcha')
            hm_str = str(hm) if hm and str(hm).lower() != 'none' else "08:00:00"

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Responsable", registro_actual.get('responsable', 'N/A'))
            c2.metric("Turno", registro_actual.get('turno', 'N/A'))
            c3.metric("Hs. Marcha Netas", hm_str)
            c4.metric("Kgs Totales", kgs_str)
            c5.metric("% Extracción", ext_str)

            df_prod_actual = df_productos[df_productos['registro_id'] == registro_id].copy() if not df_productos.empty else pd.DataFrame()
            col_l, col_r = st.columns(2)
            with col_l:
                st.subheader("📦 Producción del Turno (Kg)")
                if not df_prod_actual.empty:
                    fig_b = px.bar(df_prod_actual, x='producto', y='cantidad_kg', text='cantidad_kg', color='producto')
                    fig_b.update_traces(texttemplate='%{text:,.0f} kg', textposition='outside')
                    st.plotly_chart(fig_b, use_container_width=True)
            with col_r:
                st.subheader("📊 Distribución Porcentual (%)")
                if not df_prod_actual.empty:
                    fig_p = px.pie(df_prod_actual, names='producto', values='porcentaje', hole=0.4)
                    st.plotly_chart(fig_p, use_container_width=True)

            if not df_prod_actual.empty:
                df_tabla = df_prod_actual[['producto', 'cantidad_kg', 'porcentaje']].copy()
                df_tabla['cantidad_kg'] = df_tabla['cantidad_kg'].apply(lambda x: f"{int(x):,} kg" if float(x).is_integer() else f"{x:,.2f} kg")
                df_tabla['porcentaje'] = df_tabla['porcentaje'].apply(lambda x: f"{x*100:.2f}%" if x <= 1 else f"{x:.2f}%")
                st.dataframe(df_tabla, hide_index=True, use_container_width=True)

            st.subheader(f"⏱️ Registro de Paradas - Turno {turno_sel}")
            if not df_paradas.empty and 'registro_id' in df_paradas.columns:
                df_par_act = df_paradas[df_paradas['registro_id'] == registro_id]
                if not df_par_act.empty:
                    st.dataframe(df_par_act[['motivo', 'detalle', 'horas_parada']], hide_index=True, use_container_width=True)
                else:
                    st.success("No se registraron paradas de planta en este turno.")
            else:
                st.success("No se registraron paradas de planta en este turno.")

    except Exception as e:
        st.error(f"Error en sección Molino: {e}")

# ==============================================================================
# PESTAÑA 2: PLANTA DE ACOPIO (STOCK)
# ==============================================================================
with tab_acopio:
    df_stock = cargar_datos_acopio()

    if df_stock.empty:
        st.info("Aún no hay datos en `poc_stock_acopio`. Ejecuta el Paso 1 (SQL) y Paso 2 (`ingesta_acopio.py`) para visualizar el stock.")
    else:
        st.sidebar.markdown("---")
        st.sidebar.header("Filtros Acopio")
        fechas_acopio = sorted(df_stock['fecha'].dropna().unique().tolist(), reverse=True)
        fecha_ac_sel = st.sidebar.selectbox("Fecha Stock Acopio", fechas_acopio)

        df_ac_dia = df_stock[df_stock['fecha'] == fecha_ac_sel].copy()
        horas_acopio = sorted(df_ac_dia['hora'].dropna().unique().tolist(), reverse=True)
        hora_ac_sel = st.sidebar.selectbox("Hora de Medición", horas_acopio)

        df_corte = df_ac_dia[df_ac_dia['hora'] == hora_ac_sel].copy()
        df_corte['toneladas'] = pd.to_numeric(df_corte['toneladas'], errors='coerce').fillna(0.0)
        df_corte['capacidad_tn'] = df_corte['silo'].map(CAPACIDADES_SILOS).fillna(0)
        df_corte['ocupacion_pct'] = df_corte.apply(
            lambda r: round((r['toneladas'] / r['capacidad_tn']) * 100, 1) if r['capacidad_tn'] > 0 else 0.0,
            axis=1
        )
        df_corte['orden_silo'] = df_corte['silo'].apply(lambda s: ORDEN_SILOS.index(s) if s in ORDEN_SILOS else 99)
        df_corte = df_corte.sort_values('orden_silo')

        st.header(f"🏭 Estado de Silos - {fecha_ac_sel} ({hora_ac_sel} hs)")

        total_tn = df_corte['toneladas'].sum()
        cap_total = sum(CAPACIDADES_SILOS.values())
        ocup_total = (total_tn / cap_total) * 100 if cap_total > 0 else 0
        tn_trigo = df_corte[df_corte['grano'] == 'TRIGO']['toneladas'].sum()
        tn_maiz = df_corte[df_corte['grano'] == 'MAIZ']['toneladas'].sum()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Stock Total Acopiado", f"{total_tn:,.2f} TN", f"{ocup_total:.1f}% de {cap_total:,} TN")
        m2.metric("Stock Trigo", f"{tn_trigo:,.2f} TN")
        m3.metric("Stock Maíz", f"{tn_maiz:,.2f} TN")
        m4.metric("Capacidad Disponible", f"{max(cap_total - total_tn, 0):,.2f} TN")

        st.subheader("📊 Nivel de Llenado por Silo (Stock Actual vs Capacidad Máxima)")
        fig_silos = go.Figure()
        fig_silos.add_trace(go.Bar(
            name='Capacidad Total (TN)',
            x=df_corte['silo'],
            y=df_corte['capacidad_tn'],
            marker_color='rgba(180, 180, 180, 0.3)'
        ))
        colores_grano = {'TRIGO': '#E69F00', 'MAIZ': '#2E8B57'}
        for grano in df_corte['grano'].unique():
            sub = df_corte[df_corte['grano'] == grano]
            fig_silos.add_trace(go.Bar(
                name=grano,
                x=sub['silo'],
                y=sub['toneladas'],
                text=sub.apply(lambda r: f"{r['toneladas']:,.1f} TN<br>({r['ocupacion_pct']}%)", axis=1),
                textposition='outside',
                marker_color=colores_grano.get(grano, '#3B82F6')
            ))
        fig_silos.update_layout(barmode='overlay', yaxis_title="Toneladas (TN)", xaxis_title="Silo / Celda")
        st.plotly_chart(fig_silos, use_container_width=True)

        col_ac1, col_ac2 = st.columns([1.4, 1])
        with col_ac1:
            st.subheader("📋 Detalle por Silo")
            df_tabla_silos = df_corte[['silo', 'grano', 'toneladas', 'capacidad_tn', 'ocupacion_pct']].copy()
            df_tabla_silos.columns = ['Silo', 'Grano', 'Stock (TN)', 'Capacidad (TN)', '% Ocupación']
            st.dataframe(df_tabla_silos, hide_index=True, use_container_width=True)

        with col_ac2:
            st.subheader("🌽🌾 Participación por Grano")
            df_grano = df_corte.groupby('grano', as_index=False)['toneladas'].sum()
            fig_grano = px.pie(
                df_grano, names='grano', values='toneladas', hole=0.45,
                color='grano', color_discrete_map=colores_grano
            )
            st.plotly_chart(fig_grano, use_container_width=True)
