import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from github import Github

# --- IMPORTACIÓN DEL MOTOR DE LÓGICA ---
try:
    from logic_programador import pantalla_programador, generar_malla_tecnicos, generar_malla_abordaje, ejecutar_auditoria
except ImportError:
    st.error("⚠️ No se encontró 'logic_programador.py'.")

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo - Gestión Operativa 24/7", layout="wide", initial_sidebar_state="expanded")

# --- URLs DE LOGOS ---
# Si no tienes las URLs, puedes usar rutas locales o estas de placeholder
LOGO_GRUPO_MOVIL = "https://raw.githubusercontent.com/RichGuep/movilgo/main/MovilGo.png" 

# --- ESTILOS CSS ---
PRIMARY_COLOR = "#1E3D59" 
st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1); margin-bottom: 2rem;
    }}
    .login-container {{
        max-width: 400px; margin: auto; padding: 2rem;
        background: white; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }}
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE APOYO ---
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except: return None

def cargar_excel(nombre_archivo):
    repo = conectar_github()
    if not repo: return pd.DataFrame()
    try:
        contents = repo.get_contents(nombre_archivo)
        return pd.read_excel(io.BytesIO(contents.decoded_content))
    except: return pd.DataFrame()

# --- MODULO DE INICIO ---
def modulo_inicio():
    st.markdown(f'''
        <div class="welcome-card">
            <h1>👋 ¡Bienvenido al Panel de Control {st.session_state.empresa}!</h1>
            <p style="font-size: 1.2rem; opacity: 0.9;">
                Garantizando cobertura técnica 24/7 bajo cumplimiento de la Reforma Laboral 2026.
            </p>
        </div>
    ''', unsafe_allow_html=True)
    
    # Métricas
    df_p = cargar_excel("empleados.xlsx")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👷 Técnicos Totales", len(df_p) if not df_p.empty else "73")
    c2.metric("📂 Grupos Operativos", "4")
    c3.metric("⚖️ Deuda Global", "0 días")
    c4.metric("📡 Estado", "24/7 Activo", delta="Estable")

# --- SISTEMA DE LOGIN ---
def login_screen():
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.image(LOGO_GRUPO_MOVIL, width=200)
    st.subheader("🔐 Acceso Administrativo")
    
    user = st.text_input("Usuario")
    password = st.text_input("Contraseña", type="password")
    
    if st.button("Ingresar"):
        # Validación simple (puedes cambiarla por st.secrets)
        if user == "admin" and password == "movilgo2026":
            st.session_state.logged_in = True
            st.session_state.empresa = "Grupo Movil"
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.markdown('</div>', unsafe_allow_html=True)

# --- FLUJO PRINCIPAL ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    login_screen()
else:
    # Sidebar con Logo y Navegación
    with st.sidebar:
        st.image(LOGO_GRUPO_MOVIL, use_container_width=True)
        st.markdown(f"<h3 style='text-align:center;'>{st.session_state.empresa}</h3>", unsafe_allow_html=True)
        st.divider()
        menu = st.radio("NAVEGACIÓN", ["🏠 Inicio", "📅 Programación", "📋 Reportes", "👥 Personal"])
        
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.logged_in = False
            st.rerun()

    # Router
    if menu == "🏠 Inicio":
        modulo_inicio()
    elif menu == "📅 Programación":
        pantalla_programador()
    elif menu == "📋 Reportes":
        st.info("Módulo de Reportes en construcción")
    elif menu == "👥 Personal":
        st.info("Módulo de Personal en construcción")
