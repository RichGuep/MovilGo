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
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_GRUPO_MOVIL = f"{URL_BASE}MovilGo.png" 

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
    .login-container {{
        max-width: 450px; margin: 10% auto; padding: 3rem;
        background: white; border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.2);
        text-align: center;
    }}
    .stMetric {{ background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #eee; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
    </style>
    """, unsafe_allow_html=True)

# --- 1. FUNCIONES DE CONECTIVIDAD ---
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

# --- 2. MÓDULO DE INICIO (BIENVENIDA Y MÉTRICAS RECUPERADAS) ---
def modulo_inicio():
    # BIENVENIDA ESTILIZADA
    st.markdown(f'''
        <div class="welcome-card">
            <h1>👋 ¡Bienvenido al Panel de Control {st.session_state.empresa}!</h1>
            <p style="font-size: 1.2rem; opacity: 0.9;">
                Garantizando cobertura técnica 24/7 bajo el cumplimiento estricto de la nueva Reforma Laboral Colombiana.
            </p>
        </div>
    ''', unsafe_allow_html=True)
    
    # MÉTRICAS SUPERIORES
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

    # CONTEXTO REFORMA LABORAL
    st.subheader("🇨🇴 Contexto Legal: Reforma Laboral y Descanso")
    inf1, inf2 = st.columns(2)
    with inf1:
        st.info("""
        **📉 Reducción Gradual de la Jornada (Ley 2101)**
        El sistema está parametrizado para ajustarse a la reducción de la jornada laboral semanal en Colombia, 
        que para **2026 llegará a las 42 horas semanales**. Por esto, la optimización de los turnos es crítica.
        """)
    with inf2:
        st.warning("""
        **🛌 El Descanso como Derecho Fundamental**
        La reforma enfatiza el **descanso dominical y festivo**. MovilGo asegura que si un técnico trabaja 
        en domingo, el sistema le asigne automáticamente su **descanso compensatorio remunerado**.
        """)

    # TRANSPARENCIA Y REGLAS
    st.subheader("📝 Transparencia en el Algoritmo MovilGo")
    r1, r2 = st.columns(2)
    with r1:
        with st.expander("🛠️ Reglas Aplicadas a Técnicos", expanded=True):
            st.markdown("""
            - **Habitualidad:** Controlamos que el trabajo en domingos sea rotativo para evitar cargas excesivas.
            - **Exclusión Mutua:** Máximo 1 grupo fuera por día para no romper la cobertura 24/7.
            - **Protección T3:** Descanso mínimo de ley tras turnos nocturnos garantizado.
            """)
    with r2:
        with st.expander("👔 Reglas Aplicadas a Abordaje", expanded=True):
            st.markdown("""
            - **Desconexión Laboral:** Respeto total a los periodos de descanso post-turno.
            - **Rotación de Bloques:** Rotación por grupos completos para mantener equidad en descansos.
            """)
    st.caption("Herramienta diseñada para que la productividad no vulnere el derecho al descanso del trabajador.")

# --- 3. SISTEMA DE LOGIN ---
def login_screen():
    st.markdown('<div class="login-container">', unsafe_allow_html=True)
    st.image(LOGO_GRUPO_MOVIL, width=220)
    st.markdown("### **Acceso Administrativo**")
    st.write("Introduzca sus credenciales para gestionar mallas 2026")
    
    usuario = st.text_input("Usuario", placeholder="Ej: admin")
    clave = st.text_input("Contraseña", type="password", placeholder="••••••••")
    
    if st.button("Ingresar al Sistema"):
        if usuario == "admin" and clave == "movilgo2026": # Puedes usar st.secrets aquí
            st.session_state.logged_in = True
            st.session_state.empresa = "Grupo Movil"
            st.rerun()
        else:
            st.error("Credenciales incorrectas. Intente de nuevo.")
    st.markdown('</div>', unsafe_allow_html=True)

# --- 4. FLUJO PRINCIPAL ---
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
        menu = st.radio("NAVEGACIÓN", ["🏠 Inicio", "📅 Programación", "📋 Reporte Detallado", "👥 Personal"])
        
        st.markdown("<br>"*10, unsafe_allow_html=True)
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.logged_in = False
            st.rerun()

    # Router de Pantallas
    if menu == "🏠 Inicio":
        modulo_inicio()
    elif menu == "📅 Programación":
        pantalla_programador()
    elif menu == "📋 Reporte Detallado":
        st.subheader("Reporte de Auditoría")
        st.info("Módulo para visualización histórica de cumplimiento de descansos.")
    elif menu == "👥 Personal":
        st.subheader("Gestión de Colaboradores")
        st.info("Módulo para administrar ingresos y bajas de personal.")
