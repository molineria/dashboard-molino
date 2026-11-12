import streamlit as st
import pandas as pd
import plotly.express as px
from supabase import create_client

# Configuración de página amplia
st.set_page_config(page_title="Dashboard Molino de Trigo", layout="wide", page_icon="🌾")

# === CREDENCIALES DE SUPABASE ===
SUPABASE_URL = "https://wyvnwrvumqpztsjyhcgx.supabase.co"
SUPABASE_KEY = "sb_publishable_sXggrAG_UTWzoN_XPWL_fg_AW80e0Tc"

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# === LECTURA DE DATOS DESDE SUPABASE ===
def cargar_datos():
    res_cabecera = supabase.table("poc_registro_produccion").select("*").order("id", desc=True).execute()
    df_cabecera = pd.DataFrame(res_cabecera.data)
    
    res_productos = supabase.table("poc_produccion_productos").select("*").execute()
    df_productos = pd.DataFrame(res_productos.data)
    
    res_paradas = supabase.table("poc_paradas").select("*").execute()
    df_paradas = pd.DataFrame(res_paradas.data) if res_paradas.data else pd.DataFrame()
    
    return df_cabecera, df_productos, df_paradas

st.title("🌾 Dashboard de Producción - Molino de Trigo")
st.markdown("---")

try:
    df_cabecera, df_productos, df_paradas = cargar_datos()

    if df_cabecera.empty:
        st.warning("No hay registros cargados en la base de datos.")
    else:
        # --- FILTRO LATERAL ---
        st.sidebar.header("Filtros")
        fechas_disponibles = df_cabecera['fecha'].unique().tolist()
        fecha_sel = st.sidebar.selectbox("Seleccionar Fecha", fechas_disponibles)
        
        # Tomar el último registro del día seleccionado
        df_fecha = df_cabecera[df_cabecera['fecha'] == fecha_sel]
        registro_actual = df_fecha.iloc[0]
        registro_id = registro_actual['id']

        # --- FORMATOS KPI ---
        kgs_totales = registro_actual.get('kgs_totales_producidos', 0)
        kgs_str = f"{int(kgs_totales):,} kg" if float(kgs_totales).is_integer() else f"{kgs_totales:,.2f} kg"

        ext_val = float(registro_actual.get('porcentaje_extraccion', 0) or 0)
        ext_str = f"{ext_val * 100:.2f}%" if ext_val <= 1 else f"{ext_val:.2f}%"

        hm = registro_actual.get('horas_marcha')
        hm_str = str(hm) if hm and str(hm).lower() != 'none' else "08:00:00"

        # --- TARJETAS DE KPIS PRINCIPALES ---
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Responsable", registro_actual.get('responsable', 'N/A'))
        col2.metric("Turno", registro_actual.get('turno', 'N/A'))
        col3.metric("Hs. Marcha Netas", hm_str)
        col4.metric("Kgs Totales", kgs_str)
        col5.metric("% Extracción", ext_str)

        st.markdown("---")

        # --- DETALLE DE PRODUCTOS ---
        df_prod_actual = df_productos[df_productos['registro_id'] == registro_id].copy()

        col_left, col_right = st.columns(2)

        with col_left:
            st.subheader("📦 Producción por Producto (Kg)")
            if not df_prod_actual.empty:
                fig_barras = px.bar(
                    df_prod_actual, 
                    x='producto', 
                    y='cantidad_kg', 
                    text='cantidad_kg',
                    color='producto',
                    labels={'cantidad_kg': 'Kilogramos', 'producto': 'Producto'},
                    title="Cantidad producida por variedad"
                )
                fig_barras.update_traces(texttemplate='%{text:,.0f} kg', textposition='outside')
                st.plotly_chart(fig_barras, width='stretch')
            else:
                st.info("No hay desglose de productos para esta fecha.")

        with col_right:
            st.subheader("📊 Distribución Porcentual (%)")
            if not df_prod_actual.empty:
                fig_torta = px.pie(
                    df_prod_actual, 
                    names='producto', 
                    values='porcentaje', 
                    hole=0.4,
                    title="Participación de cada producto"
                )
                st.plotly_chart(fig_torta, width='stretch')
            else:
                st.info("No hay porcentajes registrados para esta fecha.")

        # --- TABLA DE PRODUCTOS FORMATEADA ---
        st.subheader("📋 Registro Detallado del Turno")
        if not df_prod_actual.empty:
            df_tabla = df_prod_actual[['producto', 'cantidad_kg', 'porcentaje']].copy()
            df_tabla['cantidad_kg'] = df_tabla['cantidad_kg'].apply(lambda x: f"{int(x):,} kg" if float(x).is_integer() else f"{x:,.2f} kg")
            df_tabla['porcentaje'] = df_tabla['porcentaje'].apply(lambda x: f"{x*100:.2f}%" if x <= 1 else f"{x:.2f}%")
            st.dataframe(df_tabla, width='stretch')

        # --- SECCIÓN DE PARADAS DE PLANTA ---
        st.markdown("---")
        st.subheader("⏱️ Registro de Paradas de Planta")
        
        if not df_paradas.empty and 'registro_id' in df_paradas.columns:
            df_paradas_actual = df_paradas[df_paradas['registro_id'] == registro_id]
            if not df_paradas_actual.empty:
                st.dataframe(df_paradas_actual[['motivo', 'detalle', 'horas_parada']], width='stretch')
            else:
                st.success("No se registraron paradas de planta en este turno.")
        else:
            st.success("No se registraron paradas de planta en este turno.")

except Exception as e:
    st.error(f"Error al conectar o renderizar datos: {e}")