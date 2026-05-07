import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logic_programador as lp  # Importación de la lógica separada

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="MovilGo - Gestión Operativa", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- 2. ESTILOS CSS ---
# Usamos doble llave {{ }} para evitar NameError con f-strings de Python
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
    .card-empresa h3 {{ color: black !important; margin-top: 1rem; }}
    </style>
"""
st.markdown(estilos, unsafe_allow_html=True)

# --- 3. MÓDULOS DE INTERFAZ ---

def modulo_programacion():
    st.header("📅 Programación Maestra")
    
    with st.expander("🚀 Filtros y Generación Automática", expanded=True):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Ver desde:", datetime.now().date())
        f_fin = c2.date_input("Ver hasta:", (datetime.now() + timedelta(days=28)).date())
        
        if st.button("Generar Nueva Malla Inteligente"):
            with st.spinner("Calculando rotación y sincronizando con GitHub..."):
                lp.generar_y_guardar_malla(f_ini, f_fin)
                st.success("¡Malla generada con éxito!")
                st.rerun()

    # Carga de datos filtrados a través de la lógica
    df_base = lp.cargar_excel("malla_historica.xlsx")
    if not df_base.empty:
        df_filtrada = lp.filtrar_por_fecha(df_base, f_ini, f_fin)
        
        if not df_filtrada.empty:
            st.subheader("✍️ Editor Maestro")
            # Convertimos a matriz para edición
            matriz = lp.preparar_matriz(df_filtrada)
            
            # Configuración de columnas con selectbox para turnos
            opciones = ["T1", "T2", "T3", "DESC", "COMP"]
            config_col = {c: st.column_config.SelectboxColumn(options=opciones, width="small") for c in matriz.columns}
            
            matriz_editada = st.data_editor(matriz, column_config=config_col, use_container_width=True)

            if st.button("💾 Guardar Cambios Manuales"):
                with st.spinner("Actualizando histórico..."):
                    lp.guardar_cambios_manuales(df_filtrada, matriz_editada)
                    st.success("Cambios guardados en la nube.")
                    st.rerun()
        else:
            st.info("No hay datos programados para este rango. Intenta generar una malla nueva.")

def modulo_detallado():
    st.header("📋 Detallado por Técnico")
    df_m = lp.cargar_excel("malla_historica.xlsx")
    df_e = lp.cargar_excel("empleados.xlsx")
    
    if not df_m.empty and not df_e.empty:
        matriz_detallada = lp.procesar_vista_detallada(df_m, df_e)
        st.dataframe(
            matriz_detallada.style.map(lp.color_turnos), 
            use_container_width=True
        )
    else:
        st.warning("Se requiere información de malla y empleados para visualizar este módulo.")

def modulo_nomina():
    st.header("💰 Reporte de Nómina")
    df_nom = lp.obtener_reporte_nomina()
    if not df_nom.empty:
        st.dataframe(df_nom, use_container_width=True, hide_index=True)
    else:
        st.info("No hay registros de turnos para generar la nómina.")

def modulo_personal():
    st.header("👥 Gestión de Personal")
    df_emp = lp.cargar_excel("empleados.xlsx")
    if df_emp.empty:
        df_emp = pd.DataFrame(columns=["Nombre", "Cedula", "Cargo", "Grupo"])
        
    df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic")
    
    if st.button("💾 Actualizar Base de Datos de Personal"):
        lp.guardar_excel(df_edit, "empleados.xlsx", "Update Personal")
        st.success("Personal actualizado.")
        st.rerun()

# --- 4. FLUJO DE NAVEGACIÓN Y LOGIN ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None

# Pantalla de Login
if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(lp.LOGO_APP, use_container_width=True)
        if st.button("Entrar al Sistema"): 
            st.session_state.logged_in = True
            st.rerun()

# Selección de Empresa
elif st.session_state.empresa is None:
    _, c2, _ = st.columns([1, 1.5, 1])
    with c2:
        st.markdown('<div class="card-empresa">', unsafe_allow_html=True)
        st.image(lp.LOGO_CABLE, width=220)
        st.markdown('<h3>Cable Móvil</h3></div>', unsafe_allow_html=True)
        if st.button("Acceder a la Operación"): 
            st.session_state.empresa = "Cable Móvil"
            st.rerun()

# Aplicación Principal
else:
    with st.sidebar:
        st.image(lp.LOGO_CABLE, width=150)
        st.markdown("---")
        menu = st.radio("NAVEGACIÓN", ["🏠 Inicio", "📅 Programación", "📋 Detallado", "💰 Nómina", "👥 Personal"])
        st.markdown("---")
        if st.button("🚪 Cerrar Sesión"): 
            st.session_state.clear()
            st.rerun()
    
    # Renderizado de Módulos
    if menu == "🏠 Inicio":
        st.markdown(f"""
            <div class="welcome-card">
                <h1>Operación {st.session_state.empresa}</h1>
                <p>Bienvenido al centro de gestión de técnicos y turnos rotativos.</p>
            </div>
        """, unsafe_allow_html=True)
    elif menu == "📅 Programación": modulo_programacion()
    elif menu == "📋 Detallado": modulo_detallado()
    elif menu == "💰 Nómina": modulo_nomina()
    elif menu == "👥 Personal": modulo_personal()
