import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
# Importamos la lógica externa
import logic_programador as lp

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo - Gestión Operativa", layout="wide", initial_sidebar_state="expanded")

# --- ESTILOS CSS ---
PRIMARY_COLOR = "#1E3D59" 
estilos = f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .stButton>button {{ width: 100%; border-radius: 12px; font-weight: bold; transition: 0.3s; }}
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px; margin-bottom: 2rem;
    }}
    .card-empresa {{ 
        text-align: center; padding: 2rem; background: white; border-radius: 15px; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); color: black !important;
    }}
    .card-empresa h3 {{ color: black !important; }}
    </style>
"""
st.markdown(estilos, unsafe_allow_html=True)

# --- MÓDULOS DE INTERFAZ ---

def modulo_programacion():
    st.header("📅 Programación Maestra")
    
    with st.expander("🚀 Filtros y Generación Automática", expanded=True):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Ver desde:", datetime.now().date())
        f_fin = c2.date_input("Ver hasta:", (datetime.now() + timedelta(days=30)).date())
        
        if st.button("Generar Nueva Malla (Rango Seleccionado)"):
            with st.spinner("Calculando rotación óptima..."):
                lp.generar_y_guardar_malla(f_ini, f_fin)
                st.success("Malla generada exitosamente.")
                st.rerun()

    df_base = lp.cargar_excel("malla_historica.xlsx")
    if not df_base.empty:
        df_filtrada = lp.filtrar_por_fecha(df_base, f_ini, f_fin)
        
        if not df_filtrada.empty:
            st.subheader("✍️ Editor Maestro")
            matriz = lp.crear_matriz_editable(df_filtrada)
            
            config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"], width="small") for c in matriz.columns}
            matriz_editada = st.data_editor(matriz, column_config=config_col, use_container_width=True)

            if st.button("💾 Guardar Cambios"):
                lp.guardar_ajustes_manuales(df_filtrada, matriz_editada)
                st.success("Cambios sincronizados con GitHub.")
                st.rerun()
        else:
            st.info("No hay datos para este rango.")

def modulo_detallado():
    st.header("📋 Detallado por Técnico")
    df_m = lp.cargar_excel("malla_historica.xlsx")
    df_e = lp.cargar_excel("empleados.xlsx")
    
    if not df_m.empty and not df_e.empty:
        matriz_full = lp.procesar_detallado(df_m, df_e)
        st.dataframe(matriz_full.style.map(lp.color_turnos), use_container_width=True)
    else:
        st.warning("Datos insuficientes para mostrar el detallado.")

def modulo_nomina():
    st.header("💰 Reporte de Nómina")
    df_nom = lp.preparar_nomina()
    if not df_nom.empty:
        st.dataframe(df_nom, use_container_width=True, hide_index=True)

def modulo_personal():
    st.header("👥 Gestión de Personal")
    df_emp = lp.cargar_excel("empleados.xlsx")
    df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic")
    if st.button("💾 Actualizar Personal"):
        lp.guardar_excel(df_edit, "empleados.xlsx", "Update Personal")
        st.rerun()

# --- FLUJO DE NAVEGACIÓN ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None

if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(lp.LOGO_APP, use_container_width=True)
        if st.button("Entrar"): 
            st.session_state.logged_in = True
            st.rerun()
elif st.session_state.empresa is None:
    _, c2, _ = st.columns([1, 1.5, 1])
    with c2:
        st.markdown(f'<div class="card-empresa"><img src="{lp.LOGO_CABLE}" width="200"><h3>Cable Móvil</h3></div>', unsafe_allow_html=True)
        if st.button("Acceder"): 
            st.session_state.empresa = "Cable Móvil"
            st.rerun()
else:
    with st.sidebar:
        st.image(lp.LOGO_CABLE, width=150)
        menu = st.radio("MENÚ", ["🏠 Inicio", "📅 Programación", "📋 Detallado", "💰 Nómina", "👥 Personal"])
        if st.button("🚪 Salir"): 
            st.session_state.clear()
            st.rerun()
    
    if menu == "🏠 Inicio":
        st.markdown(f'<div class="welcome-card"><h1>Operación {st.session_state.empresa}</h1></div>', unsafe_allow_html=True)
    elif menu == "📅 Programación": modulo_programacion()
    elif menu == "📋 Detallado": modulo_detallado()
    elif menu == "💰 Nómina": modulo_nomina()
    elif menu == "👥 Personal": modulo_personal()
