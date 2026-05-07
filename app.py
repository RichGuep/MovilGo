import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo - Gestión Operativa", layout="wide", initial_sidebar_state="expanded")

# --- URLs DE IMÁGENES GITHUB ---
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGO_GREEN = f"{URL_BASE}logo_empresa_1.png"   # Greenmóvil
LOGO_CABLE = f"{URL_BASE}logo_empresa_2.png"   # Cablemóvil
LOGO_BOGOTA = f"{URL_BASE}logo_empresa_3.png"  # BogotáMóvil

# --- ESTILOS CSS AVANZADOS ---
PRIMARY_COLOR = "#1E3D59" 
st.markdown(f"""
    <style>
    .main {{ background-color: #f4f7f6; }}
    
    /* Estilo para las Tarjetas de Selección de Empresa */
    .card-empresa {{
        background: white;
        padding: 2rem;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border: 2px solid transparent;
        transition: 0.3s;
        margin-bottom: 10px;
    }}
    .card-empresa:hover {{
        border-color: {PRIMARY_COLOR};
        transform: translateY(-5px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.1);
    }}
    .card-empresa img {{
        height: 80px;
        margin-bottom: 15px;
    }}
    
    /* Login Container */
    .login-box {{
        background: white;
        padding: 3rem;
        border-radius: 25px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.1);
    }}

    /* Sidebar Customization */
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; }}
    [data-testid="stSidebar"] * {{ color: white !important; font-weight: 500; }}
    
    /* Botones */
    .stButton>button {{
        border-radius: 10px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- (Funciones de GitHub y Lógica de Turnos se mantienen igual que en tu código original) ---
# ... [Insertar aquí tus funciones conectar_github, cargar_excel, guardar_excel, etc.] ...

# --- 4. FLUJO DE NAVEGACIÓN MEJORADO ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None

# PASO 1: LOGIN ESTILIZADO
if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.markdown('<div style="height: 100px;"></div>', unsafe_allow_html=True)
        st.image(LOGO_APP, use_container_width=True)
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.subheader("🚀 Bienvenido a MovilGo")
        user = st.text_input("Usuario")
        pw = st.text_input("Contraseña", type="password")
        if st.button("Ingresar al Portal"):
            # Aquí podrías validar credenciales reales
            st.session_state.logged_in = True
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# PASO 2: SELECCIÓN DE EMPRESA (MULTIMARCA)
elif st.session_state.empresa is None:
    st.markdown("<h1 style='text-align: center; color: #1E3D59;'>Seleccione Operación</h1>", unsafe_allow_html=True)
    st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_GREEN}"><h4>Greenmóvil</h4></div>', unsafe_allow_html=True)
        if st.button("Acceder Greenmóvil", key="btn_green"):
            st.session_state.empresa = "Greenmóvil"
            st.session_state.logo_actual = LOGO_GREEN
            st.rerun()

    with c2:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_CABLE}"><h4>Cable Móvil</h4></div>', unsafe_allow_html=True)
        if st.button("Acceder Cable Móvil", key="btn_cable"):
            st.session_state.empresa = "Cable Móvil"
            st.session_state.logo_actual = LOGO_CABLE
            st.rerun()

    with c3:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_BOGOTA}"><h4>BogotáMóvil</h4></div>', unsafe_allow_html=True)
        if st.button("Acceder BogotáMóvil", key="btn_bogota"):
            st.session_state.empresa = "BogotáMóvil"
            st.session_state.logo_actual = LOGO_BOGOTA
            st.rerun()

# PASO 3: APLICACIÓN PRINCIPAL
else:
    # Sidebar con logo dinámico según empresa
    with st.sidebar:
        st.markdown(f'<div style="text-align: center;"><img src="{st.session_state.logo_actual}" width="150"></div>', unsafe_allow_html=True)
        st.markdown(f"<h3 style='text-align: center;'>{st.session_state.empresa}</h3>", unsafe_allow_html=True)
        st.divider()
        
        # Menú con iconos
        menu = st.radio(
            "GESTIÓN OPERATIVA",
            ["🏠 Inicio", "📅 Programación", "📋 Detallado", "💰 Nómina", "👥 Personal"],
            index=0
        )
        
        st.spacer = st.markdown('<div style="height: 15vh;"></div>', unsafe_allow_html=True)
        if st.button("🚪 Cambiar de Empresa"):
            st.session_state.empresa = None
            st.rerun()
        if st.button("🔒 Salir"):
            st.session_state.logged_in = False
            st.session_state.empresa = None
            st.rerun()

    # --- Renderizado de Módulos ---
    if menu == "🏠 Inicio":
        st.markdown(f'''
            <div class="welcome-card">
                <h1>Operación {st.session_state.empresa}</h1>
                <p>Bienvenido al sistema de gestión operativa. Seleccione una opción en el menú lateral para comenzar.</p>
            </div>
            ''', unsafe_allow_html=True)
        
        # Dashboard simple de bienvenida
        db1, db2, db3 = st.columns(3)
        db1.metric("Estado del Sistema", "Online", "v2.0")
        db2.metric("Turnos Activos", "24/7")
        db3.metric("País", "Colombia 🇨🇴")

    elif menu == "📅 Programación":
        modulo_programacion()
    elif menu == "📋 Detallado":
        modulo_detallado()
    elif menu == "💰 Nómina":
        modulo_nomina()
    elif menu == "👥 Personal":
        modulo_personal()
