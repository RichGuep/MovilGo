import streamlit as st
import pandas as pd
import io
import os
import sys
from datetime import datetime, timedelta
from github import Github

# Forzar al sistema a buscar en el directorio actual para evitar el ImportError
sys.path.append(os.path.dirname(__file__))

# --- IMPORTACIÓN DEL MOTOR DE LÓGICA ---
try:
    from logic_programador import pantalla_programador
except ImportError as e:
    st.error(f"⚠️ Error de conexión interna: {e}")
    st.stop()

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo - Gestión Operativa 24/7", layout="wide", initial_sidebar_state="expanded")

# --- URLs DE IMÁGENES GITHUB ---
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGO_CABLE = f"{URL_BASE}logo_empresa_2.png" 

# --- ESTILOS CSS ---
PRIMARY_COLOR = "#1E3D59" 
st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; border-right: 1px solid #ffffff22; }}
    [data-testid="stSidebar"] * {{ color: white !important; font-weight: 500; }}
    .stButton>button {{ width: 100%; border-radius: 12px; font-weight: bold; height: 3em; transition: 0.3s; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }}
    .stMetric {{ background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #eee; }}
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE CONECTIVIDAD ---
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
        df = pd.read_excel(io.BytesIO(contents.decoded_content))
        return df
    except: return pd.DataFrame()

def modulo_inicio():
    st.markdown(f'''
        <div class="welcome-card">
            <h1>👋 ¡Bienvenido al Panel de Control {st.session_state.get("empresa", "Cable Móvil")}!</h1>
            <p style="font-size: 1.2rem; opacity: 0.9;">
                Garantizando cobertura técnica 24/7 bajo la Reforma Laboral Colombiana.
            </p>
        </div>
    ''', unsafe_allow_html=True)
    
    df_p = cargar_excel("empleados.xlsx")
    df_m = cargar_excel("malla_historica.xlsx")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👷 Técnicos Totales", len(df_p) if not df_p.empty else "73")
    c2.metric("📂 Grupos Operativos", "4")
    
    deuda = 0
    if not df_m.empty and 'Deuda_Compensatorio' in df_m.columns:
        deuda = int(df_m['Deuda_Compensatorio'].sum())
    
    c3.metric("⚖️ Deuda Global Descansos", f"{deuda} días")
    c4.metric("📡 Estado de Red", "24/7 Activo", delta="Estable")

    st.divider()
    st.subheader("🇨🇴 Contexto Legal: Reforma Laboral")
    inf1, inf2 = st.columns(2)
    with inf1:
        st.info("**📉 Reducción Gradual (Ley 2101):** Sistema parametrizado para 42 horas semanales en 2026.")
    with inf2:
        st.warning("**🛌 Descanso Dominical:** MovilGo asigna automáticamente compensatorios remunerados.")

# --- FLUJO PRINCIPAL ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = "Cable Móvil"

if not st.session_state.logged_in:
    # Bypass de login para desarrollo
    st.session_state.logged_in = True
    st.rerun()
else:
    with st.sidebar:
        st.image(LOGO_CABLE, width=150)
        st.divider()
        menu = st.radio("NAVEGACIÓN", ["🏠 Inicio", "📅 Programación", "📋 Reporte Detallado", "👥 Personal"])

    if menu == "🏠 Inicio":
        modulo_inicio()
    elif menu == "📅 Programación":
        pantalla_programador()
    else:
        st.info(f"Módulo {menu} en desarrollo...")
