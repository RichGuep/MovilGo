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
    # BIENVENIDA
    st.markdown(f'''
        <div class="welcome-card">
            <h1>👋 ¡Bienvenido al Panel de Control Cable Móvil!</h1>
            <p>Sistema inteligente de gestión de personal con transparencia total en reglas de descanso y cobertura.</p>
        </div>
    ''', unsafe_allow_html=True)
    
    # CARGA DE DATOS PARA MÉTRICAS
    df_p = cargar_excel("empleados.xlsx")
    df_m = cargar_excel("malla_historica.xlsx")
    
    # MÉTRICAS SUPERIORES
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👷 Técnicos Totales", len(df_p) if not df_p.empty else "73")
    c2.metric("📂 Grupos Operativos", "4")
    
    # Solución al error KeyError: Verificamos si existe la columna antes de sumar
    deuda = 0
    if not df_m.empty and 'Deuda_Compensatorio' in df_m.columns:
        deuda = int(df_m['Deuda_Compensatorio'].sum())
    
    c3.metric("⚖️ Deuda Global Descansos", f"{deuda} días")
    c4.metric("📡 Estado de Red", "24/7 Activo", delta="Estable")

    st.divider()

    # PANEL DE TRANSPARENCIA (ESTILOS Y FORMAS)
    st.subheader("📝 Declaración de Transparencia y Reglas")
    r1, r2 = st.columns(2)

    with r1:
        with st.expander("🛠️ Reglas Aplicadas a Técnicos", expanded=True):
            st.markdown("""
            - **Exclusión Mutua:** Máximo 1 grupo fuera por día (Descanso o Compensado).
            - **Regla T3:** Obligatorio descansar tras turno noche antes de T1/T2.
            - **Compensados:** Se reponen únicamente de **Lunes a Viernes**.
            - **Viceversa:** Alternancia automática en días de descanso compartidos.
            """)

    with r2:
        with st.expander("👔 Reglas Aplicadas a Abordaje", expanded=True):
            st.markdown("""
            - **Rotación por Bloques:** Los grupos de 5 personas rotan siempre juntos.
            - **Cuotas de Personal:** Garantía de **10 T1 y 10 T2** constantes.
            - **Personal de Apoyo:** 1 Relevo fijo y 4 Disponibles por ciclo.
            """)

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
