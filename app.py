import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from github import Github

# --- IMPORTACIÓN DEL MOTOR DE LÓGICA (EL CEREBRO) ---
try:
    from logic_programador import pantalla_programador, generar_malla_tecnicos, generar_malla_abordaje, ejecutar_auditoria
except ImportError:
    st.error("⚠️ No se encontró 'logic_programador.py'. Asegúrate de que ambos archivos estén en la misma carpeta.")

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo - Gestión Operativa 24/7", layout="wide", initial_sidebar_state="expanded")

# --- URLs DE IMÁGENES GITHUB ---
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGO_CABLE = f"{URL_BASE}logo_empresa_2.png" 

# --- ESTILOS CSS (FRONT-END) ---
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

# --- 1. FUNCIONES DE CONECTIVIDAD (FRONT) ---

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

# --- 2. MÓDULOS DE INTERFAZ (FRONT) ---

def modulo_inicio():
    # --- BIENVENIDA ESTILIZADA ---
    st.markdown(f'''
        <div class="welcome-card">
            <h1>👋 ¡Bienvenido al Panel de Control {st.session_state.empresa}!</h1>
            <p style="font-size: 1.2rem; opacity: 0.9;">
                Garantizando cobertura técnica 24/7 bajo el cumplimiento estricto de la nueva Reforma Laboral Colombiana.
            </p>
        </div>
    ''', unsafe_allow_html=True)
    
    # --- MÉTRICAS SUPERIORES ---
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

    # --- NUEVA SECCIÓN: CONTEXTO REFORMA LABORAL ---
    st.subheader("🇨🇴 Contexto Legal: Reforma Laboral y Descanso")
    
    inf1, inf2 = st.columns(2)
    
    with inf1:
        st.info("""
        **📉 Reducción Gradual de la Jornada (Ley 2101)**
        El sistema está parametrizado para ajustarse a la reducción de la jornada laboral semanal en Colombia, 
        que para **2026 llegará a las 42 horas semanales**. Por esto, la optimización de los turnos T1, T2 
        y T3 es crítica para no exceder los límites legales sin afectar la operación.
        """)

    with inf2:
        st.warning("""
        **🛌 El Descanso como Derecho Fundamental**
        La reforma enfatiza el **descanso dominical y festivo**. MovilGo asegura que si un técnico trabaja 
        habitualmente en domingo, el sistema le asigne automáticamente su **descanso compensatorio remunerado** en la semana siguiente (Lunes a Viernes), protegiendo su salud mental y bienestar familiar.
        """)

    # --- PANEL DE TRANSPARENCIA Y REGLAS ---
    st.subheader("📝 Transparencia en el Algoritmo MovilGo")
    r1, r2 = st.columns(2)

    with r1:
        with st.expander("🛠️ Reglas Aplicadas a Técnicos", expanded=True):
            st.markdown("""
            - **Habitualidad:** Controlamos que el trabajo en domingos sea rotativo (viceversa) para evitar cargas excesivas en un solo grupo.
            - **Exclusión Mutua:** Máximo 1 grupo fuera por día para no romper la cobertura 24/7.
            - **Protección T3 (Noche):** El sistema exige el descanso mínimo de ley tras turnos nocturnos antes de volver a la habitualidad del día.
            """)

    with r2:
        with st.expander("👔 Reglas Aplicadas a Abordaje", expanded=True):
            st.markdown("""
            - **Desconexión Laboral:** Respeto total a los periodos de descanso post-turno.
            - **Rotación de Bloques:** Garantizamos que los grupos roten completos cada quincena o mes para mantener la equidad en el acceso a descansos de fin de semana.
            """)
            
    st.caption("Esta herramienta ha sido diseñada para que la productividad de Cable Móvil no vulnere el derecho al descanso habitual del trabajador.")

# --- 3. FLUJO PRINCIPAL ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None

if not st.session_state.logged_in:
    # (Tu código de Login se mantiene igual...)
    st.session_state.logged_in = True # Bypass temporal para prueba
    st.rerun()

elif st.session_state.empresa is None:
    st.session_state.empresa = "Cable Móvil"
    st.rerun()

else:
    with st.sidebar:
        st.image(LOGO_CABLE, width=150)
        st.divider()
        menu = st.radio("NAVEGACIÓN", ["🏠 Inicio", "📅 Programación", "📋 Reporte Detallado", "👥 Personal"])

    # ROUTER: LLAMA A LAS FUNCIONES DE LOGICA EN EL OTRO ARCHIVO
    if menu == "🏠 Inicio":
        modulo_inicio()
    elif menu == "📅 Programación":
        pantalla_programador() # Llama al cerebro
    elif menu == "📋 Reporte Detallado":
        st.info("Módulo de reporte detallado")
    elif menu == "👥 Personal":
        st.info("Módulo de gestión de personal")
