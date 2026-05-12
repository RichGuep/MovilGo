import streamlit as st
import pandas as pd
import io
import time
from datetime import datetime, timedelta, date
from github import Github

# =========================================================
# 1. IMPORTACIÓN MODULAR (EL CEREBRO)
# =========================================================
try:
    from logic_programador import pantalla_programador, ejecutar_auditoria, cargar_excel, conectar_github
except ImportError:
    st.error("⚠️ No se encontró 'logic_programador.py'. Asegúrate de que ambos archivos estén en la misma carpeta del repositorio.")

# =========================================================
# 2. CONFIGURACIÓN Y ESTILOS CSS (DISEÑO CENTRADO)
# =========================================================
st.set_page_config(page_title="MovilGo - Gestión Operativa 24/7", layout="wide", initial_sidebar_state="expanded")

PRIMARY_COLOR = "#1E3D59" 

st.markdown(f"""
    <style>
    /* Fondo general */
    .main {{ background-color: #f8f9fa; }}
    
    /* Centrado de contenedores de Login y Splash */
    .stApp {{
        display: flex;
        justify-content: center;
    }}
    
    /* Card de Bienvenida (Inicio) */
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px; 
        box-shadow: 0 10px 25px rgba(0,0,0,0.1); margin-bottom: 2rem;
    }}

    /* Estilo para las métricas */
    .stMetric {{
        background-color: white; padding: 20px; border-radius: 15px; 
        border: 1px solid #eee; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }}

    /* Centrado absoluto para Splash y Login */
    .centered-container {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        width: 100%;
        margin-top: 5%;
    }}

    .login-box {{
        max-width: 450px;
        background: white;
        padding: 3rem;
        border-radius: 20px;
        box-shadow: 0 15px 35px rgba(0,0,0,0.2);
    }}
    
    /* Sidebar */
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; border-right: 1px solid #ffffff22; }}
    [data-testid="stSidebar"] * {{ color: white !important; font-weight: 500; }}
    </style>
    """, unsafe_allow_html=True)

# URLs DE IMÁGENES
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_MÓVILGO = f"{URL_BASE}MovilGo.png"

# =========================================================
# 3. MÓDULOS DE INTERFAZ (INICIO)
# =========================================================
def modulo_inicio():
    st.markdown(f'''
        <div class="welcome-card">
            <h1>👋 ¡Bienvenido al Panel de Control {st.session_state.empresa}!</h1>
            <p style="font-size: 1.2rem; opacity: 0.9;">
                Garantizando cobertura técnica 24/7 bajo el cumplimiento estricto de la nueva Reforma Laboral Colombiana 2026.
            </p>
        </div>
    ''', unsafe_allow_html=True)
    
    # Métricas Superiores (Intentar cargar de logic o usar valores base)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👷 Técnicos Totales", "73")
    c2.metric("📂 Grupos Operativos", "4")
    c3.metric("⚖️ Deuda Global Descansos", "0 días")
    c4.metric("📡 Estado de Red", "24/7 Activo", delta="Estable")

    st.divider()

    # Contexto Legal
    st.subheader("🇨🇴 Contexto Legal: Reforma Laboral y Descanso")
    inf1, inf2 = st.columns(2)
    with inf1:
        st.info("**📉 Jornada Laboral 2026:** Parametrizado para 42 horas semanales.")
    with inf2:
        st.warning("**🛌 Descanso Dominical:** Compensatorios automáticos calculados para los 26 domingos del semestre.")

    # Reglas del algoritmo
    st.subheader("📝 Transparencia en el Algoritmo")
    r1, r2 = st.columns(2)
    with r1:
        with st.expander("🛠️ Reglas Técnicos", expanded=True):
            st.write("- Rotación simétrica de turnos T3.\n- Máximo 1 grupo fuera por día.")
    with r2:
        with st.expander("👔 Reglas Abordaje", expanded=True):
            st.write("- Rotación en bloques sólidos (5 personas).\n- 10 personas fijas en T1 y T2.")

# =========================================================
# 4. LÓGICA DE ESTADO Y NAVEGACIÓN
# =========================================================
if 'splash_done' not in st.session_state: st.session_state.splash_done = False
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = "Grupo Movil"

# FLUJO 1: SPLASH SCREEN (BIENVENIDA VISUAL)
if not st.session_state.splash_done:
    st.markdown('<div class="centered-container">', unsafe_allow_html=True)
    st.image(LOGO_MÓVILGO, width=500) # Logo GIGANTE
    st.markdown("<h1 style='color:#1E3D59;'>MovilGo Optimizer Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p>Gestión de Mallas y Cumplimiento Legal</p>", unsafe_allow_html=True)
    if st.button("ACCEDER AL PORTAL", use_container_width=True):
        st.session_state.splash_done = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# FLUJO 2: LOGIN CENTRADO
elif not st.session_state.logged_in:
    st.markdown('<div class="centered-container"><div class="login-box">', unsafe_allow_html=True)
    st.image(LOGO_MÓVILGO, width=180)
    st.markdown("### **Acceso Administrativo**")
    
    user = st.text_input("Usuario", placeholder="admin")
    password = st.text_input("Contraseña", type="password", placeholder="••••••••")
    
    if st.button("INGRESAR AL SISTEMA", use_container_width=True):
        if user == "admin" and password == "movilgo2026":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Credenciales inválidas")
    st.markdown('</div></div>', unsafe_allow_html=True)

# FLUJO 3: APLICACIÓN PRINCIPAL
else:
    with st.sidebar:
        st.image(LOGO_MÓVILGO, use_container_width=True)
        st.markdown(f"<h3 style='text-align:center;'>{st.session_state.empresa}</h3>", unsafe_allow_html=True)
        st.divider()
        menu = st.radio("NAVEGACIÓN", ["🏠 Inicio", "📅 Programación", "📋 Reporte Detallado", "👥 Personal"])
        
        st.markdown("<br>"*10, unsafe_allow_html=True)
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.splash_done = False
            st.rerun()

    # ROUTER
    if menu == "🏠 Inicio":
        modulo_inicio()
    elif menu == "📅 Programación":
        pantalla_programador() # Función dentro de logic_programador.py
    elif menu == "📋 Reporte Detallado":
        st.info("Módulo de Reportes Históricos en desarrollo.")
    elif menu == "👥 Personal":
        st.info("Módulo de Gestión de Personal en desarrollo.")
