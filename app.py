import streamlit as st
import pandas as pd
import io
import random
from datetime import datetime, timedelta
from github import Github

# =========================================================
# IMPORTACIÓN DEL MOTOR DE LÓGICA (NUEVO SISTEMA)
# =========================================================

from logic_programador import main

# =========================================================
# CONFIGURACIÓN DE PÁGINA
# =========================================================

st.set_page_config(
    page_title="MovilGo - Gestión Operativa 24/7",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================================================
# URLs DE IMÁGENES GITHUB
# =========================================================

URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGO_CABLE = f"{URL_BASE}logo_empresa_2.png"

# =========================================================
# ESTILOS CSS
# =========================================================

PRIMARY_COLOR = "#1E3D59"

st.markdown(f"""
<style>
.main {{ background-color: #f8f9fa; }}

[data-testid="stSidebar"] {{
    background-color: {PRIMARY_COLOR};
    border-right: 1px solid #ffffff22;
}}

[data-testid="stSidebar"] * {{
    color: white !important;
    font-weight: 500;
}}

.stButton>button {{
    width: 100%;
    border-radius: 12px;
    font-weight: bold;
    height: 3em;
    transition: 0.3s;
    border: none;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}}

.welcome-card {{
    background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
    color: white;
    padding: 2.5rem;
    border-radius: 20px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.1);
    margin-bottom: 2rem;
}}

.card-empresa {{
    background-color: white;
    padding: 30px;
    border-radius: 25px;
    text-align: center;
    border: 1px solid #eee;
    transition: 0.4s;
}}
</style>
""", unsafe_allow_html=True)

# =========================================================
# CONEXIÓN GITHUB (GENÉRICA UI)
# =========================================================

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except:
        return None

# =========================================================
# MÓDULOS UI SIMPLES (NO PROGRAMACIÓN)
# =========================================================

def modulo_inicio():

    st.markdown(
        f"""
        <div class="welcome-card">
            <h1>Panel de Control {st.session_state.empresa}</h1>
            <p>Gestión operativa de turnos, cobertura y equilibrio laboral.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.info("Usa el módulo de Programación para gestionar Técnicos y Abordaje")

# =========================================================
# PERSONAL (CRUD SIMPLE)
# =========================================================

def modulo_personal():

    st.header("👥 Gestión de Personal")

    st.info("Este módulo puede conectarse al parametrizador del sistema")

    st.warning("La lógica de asignación ahora está en el módulo Parametrizador dentro de logic_programador.py")

# =========================================================
# DETALLADO (MANTENIDO COMPATIBLE)
# =========================================================

def modulo_detallado():

    st.header("📋 Reporte Detallado")

    st.info("Este módulo depende de la malla generada en el sistema de programación")

# =========================================================
# FLUJO PRINCIPAL
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "empresa" not in st.session_state:
    st.session_state.empresa = None

# =========================================================
# LOGIN
# =========================================================

if not st.session_state.logged_in:

    _, col, _ = st.columns([1, 1.2, 1])

    with col:
        st.image(LOGO_APP, use_container_width=True)

        st.markdown("<h2 style='text-align:center;'>Portal de Acceso</h2>", unsafe_allow_html=True)

        with st.container(border=True):

            user = st.text_input("Usuario Operativo")
            pw = st.text_input("Contraseña", type="password")

            if st.button("Iniciar Sesión"):
                st.session_state.logged_in = True
                st.rerun()

# =========================================================
# SELECCIÓN EMPRESA
# =========================================================

elif st.session_state.empresa is None:

    st.markdown(
        "<h2 style='text-align:center; padding: 2rem;'>Seleccione Unidad de Negocio</h2>",
        unsafe_allow_html=True
    )

    _, col, _ = st.columns([1, 1.5, 1])

    with col:

        st.markdown(
            f"""
            <div class="card-empresa">
                <img src="{LOGO_CABLE}" width="200">
                <h3>Cable Móvil</h3>
                <p>Soporte Técnico y Operaciones</p>
            </div>
            """,
            unsafe_allow_html=True
        )

        if st.button("Gestionar Cable Móvil"):
            st.session_state.empresa = "Cable Móvil"
            st.rerun()

# =========================================================
# DASHBOARD PRINCIPAL
# =========================================================

else:

    with st.sidebar:

        st.image(LOGO_CABLE, width=150)
        st.divider()

        menu = st.radio(
            "NAVEGACIÓN",
            ["🏠 Inicio", "📅 Programación", "📋 Reporte Detallado", "👥 Personal"]
        )

        st.divider()

        if st.button("🚪 Salir del Sistema"):
            st.session_state.empresa = None
            st.rerun()

# =========================================================
# ROUTER PRINCIPAL (CLAVE)
# =========================================================

    if menu == "🏠 Inicio":
        modulo_inicio()

    elif menu == "📅 Programación":
        # 🔥 AQUÍ ESTÁ LA CORRECCIÓN IMPORTANTE
        main()

    elif menu == "📋 Reporte Detallado":
        modulo_detallado()

    elif menu == "👥 Personal":
        modulo_personal()
