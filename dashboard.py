import streamlit as st
import pandas as pd
import plotly.express as px
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
    
    return df_cabecera, df_productos, df_paradas

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
st.markdown("---")

# Botón manual en la barra lateral para actualizar al instante
if st.sidebar.button("🔄 Actualizar Datos", use_container_width=True):
    st.cache_resource.clear()
    st.rerun()

try:
    df_cabecera, df_productos, df_paradas = cargar_datos()

    if not df_cabecera.empty:
        # Filtrar fechas de prueba antiguas para dejar solo producción real
        df_cabecera = df_cabecera[df_cabecera['fecha'] >= '2026-11-10'].copy()

    if df_cabecera.empty:
        st.warning("No hay registros cargados en la base de datos.")
    else:
        # --- FILTRO LATERAL DE FECHA ORDENADO DE MÁS RECIENTE A MÁS ANTIGUA ---
        st.sidebar.header("Filtros")
        fechas_disponibles = sorted(df_cabecera['fecha'].dropna().unique().tolist(), reverse=True)
        fecha_sel = st.sidebar.selectbox("Seleccionar Fecha", fechas_disponibles)
        
        # Filtrar todos los registros (turnos) del día seleccionado
        df_fecha = df_cabecera[df_cabecera['fecha'] == fecha_sel].copy()
        
        # Ordenar turnos cronológicamente
        orden_turnos = {'MAÑANA': 1, 'MANANA': 1, 'TARDE': 2, 'NOCHE': 3}
        df_fecha['orden'] = df_fecha['turno'].str.upper().str.strip().map(orden_turnos).fillna(99)
        df_fecha = df_fecha.sort_values(by=['orden', 'id'])

        # =====================================================================
        # SECCIÓN 1: RESUMEN CONSOLIDADO DEL DÍA (LOS TURNOS DE LA JORNADA)
        # =====================================================================
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

        # =====================================================================
        # SECCIÓN 2: DETALLE INDIVIDUAL POR TURNO (PLANILLA ESPECÍFICA)
        # =====================================================================
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

        # --- TABLA DE PRODUCTOS FORMATEADA ---
        st.subheader("📋 Registro Detallado del Turno")
        if not df_prod_actual.empty:
            df_tabla = df_prod_actual[['producto', 'cantidad_kg', 'porcentaje']].copy()
            df_tabla['cantidad_kg'] = df_tabla['cantidad_kg'].apply(lambda x: f"{int(x):,} kg" if float(x).is_integer() else f"{x:,.2f} kg")
            df_tabla['porcentaje'] = df_tabla['porcentaje'].apply(lambda x: f"{x*100:.2f}%" if x <= 1 else f"{x:.2f}%")
            st.dataframe(df_tabla, hide_index=True, use_container_width=True)

        # --- SECCIÓN DE PARADAS DE PLANTA ---
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

except Exception as e:
    st.error(f"Error al conectar o renderizar datos: {e}")
