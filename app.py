import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta, date

# --- IMPORTACIÓN DEL MOTOR DE LÓGICA ---
try:
    from logic_programador import pantalla_programador, pantalla_personal, cargar_excel, conectar_github
except ImportError:
    st.error("⚠️ No se encontró 'logic_programador.py'. Asegúrate de que ambos archivos estén en la misma carpeta.")

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="MovilGo - Gestión Operativa 24/7", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- URLs DE IMÁGENES GITHUB ---
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_MÓVILGO = f"{URL_BASE}MovilGo.png"

# --- 2. ESTILOS CSS PERSONALIZADOS (Centrado y Tarjetas) ---
PRIMARY_COLOR = "#1E3D59" 
st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; border-right: 1px solid #ffffff22; }}
    [data-testid="stSidebar"] * {{ color: white !important; font-weight: 500; }}
    
    /* Botones Globales */
    .stButton>button {{ 
        width: 100%; border-radius: 12px; font-weight: bold; 
        height: 3em; transition: 0.3s; border: none; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
    }}
    
    /* Contenedor de Bienvenida (Inicio) */
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px; 
        box-shadow: 0 10px 25px rgba(0,0,0,0.1); margin-bottom: 2rem;
    }}
    
    /* Centrado absoluto para Splash y Login */
    .centered-box {{
        display: flex; flex-direction: column; align-items: center; 
        justify-content: center; text-align: center; padding: 2rem;
        margin-top: 5vh;
    }}
    
    .login-card {{
        max-width: 450px; background: white; padding: 3rem; 
        border-radius: 25px; border: 1px solid #eee;
        box-shadow: 0 15px 35px rgba(0,0,0,0.15); margin: auto;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. MÓDULOS DE INTERFAZ ---

def modulo_inicio():
    """Pantalla de Bienvenida con contexto de Reforma Laboral"""
    st.markdown(f'''
        <div class="welcome-card">
            <h1>👋 ¡Bienvenido al Panel de Control {st.session_state.empresa}!</h1>
            <p style="font-size: 1.2rem; opacity: 0.9;">
                Garantizando cobertura técnica 24/7 bajo el cumplimiento estricto de la nueva Reforma Laboral Colombiana 2026.
            </p>
        </div>
    ''', unsafe_allow_html=True)
    
    # Métricas Superiores
    df_p = cargar_excel("empleados.xlsx")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👷 Técnicos Totales", len(df_p) if not df_p.empty else "73")
    c2.metric("📂 Grupos Operativos", "4")
    c3.metric("⚖️ Deuda Global", "0 días")
    c4.metric("📡 Estado de Red", "24/7 Activo", delta="Estable")

    st.divider()

    # Contexto Legal: Reforma Laboral
    st.subheader("🇨🇴 Contexto Legal: Reforma Laboral y Descanso")
    inf1, inf2 = st.columns(2)
    with inf1:
        st.info("""
        **📉 Reducción Gradual de la Jornada (Ley 2101)**
        Para **2026 la jornada máxima es de 42 horas semanales**. El sistema optimiza los turnos 
        para cumplir este límite sin sacrificar la operatividad del servicio.
        """)
    with inf2:
        st.warning("""
        **🛌 Descanso Dominical y Compensatorios**
        MovilGo calcula automáticamente los **descansos compensatorios remunerados** para técnicos 
        que laboran en domingo, asegurando el cumplimiento de la ley y el bienestar del equipo.
        """)

    # Transparencia del Algoritmo
    st.subheader("📝 Reglas del Algoritmo MovilGo")
    r1, r2 = st.columns(2)
    with r1:
        with st.expander("🛠️ Operación Técnicos", expanded=True):
            st.markdown("""
            - **Rotación Dominical:** Equilibrio simétrico entre los 4 grupos.
            - **Protección Noche:** Descanso mínimo de ley tras turnos T3.
            - **Cobertura:** Mínimo 3 grupos activos por día.
            """)
    with r2:
        with st.expander("👔 Operación Abordaje", expanded=True):
            st.markdown("""
            - **Bloques Sólidos:** Gestión de 5 personas por grupo.
            - **Equidad:** Rotación quincenal para acceso justo a fines de semana.
            - **Desconexión:** Respeto total a periodos de descanso.
            """)

# --- 4. FLUJO DE NAVEGACIÓN Y ACCESO ---

# Inicialización de estados de sesión
if 'splash_done' not in st.session_state: st.session_state.splash_done = False
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = "Grupo Movil"

# PASO 1: SPLASH SCREEN (Logo Gigante Centrado)
if not st.session_state.splash_done:
    st.markdown('<div class="centered-box">', unsafe_allow_html=True)
    st.image(LOGO_MÓVILGO, width=550) # Logo en tamaño grande
    st.markdown("<h1 style='color:#1E3D59;'>Optimizer Pro 2026</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#555;'>Cargando sistemas de cumplimiento legal...</p>", unsafe_allow_html=True)
    if st.button("INGRESAR AL PORTAL"):
        st.session_state.splash_done = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# PASO 2: LOGIN (Caja Centrada)
elif not st.session_state.logged_in:
    st.markdown('<div class="centered-box"><div class="login-card">', unsafe_allow_html=True)
    st.image(LOGO_MÓVILGO, width=180) # Logo centrado dentro del login
    st.markdown("### **Acceso Administrativo**")
    
    u = st.text_input("Usuario", placeholder="admin")
    p = st.text_input("Contraseña", type="password", placeholder="••••••••")
    
    if st.button("INICIAR SESIÓN"):
        if u == "admin" and p == "movilgo2026":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.markdown('</div></div>', unsafe_allow_html=True)

# PASO 3: APLICACIÓN PRINCIPAL (Sidebar y Contenido)
else:
    with st.sidebar:
        st.image(LOGO_MÓVILGO, use_container_width=True)
        st.markdown(f"<h3 style='text-align:center;'>{st.session_state.empresa}</h3>", unsafe_allow_html=True)
        st.divider()
        menu = st.radio("NAVEGACIÓN", ["🏠 Inicio", "📅 Programación", "📋 Reportes", "👥 Personal"])
        
        st.markdown("<br>"*10, unsafe_allow_html=True)
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.logged_in = False
            st.session_state.splash_done = False
            st.rerun()

    # ROUTER DE PÁGINAS
    if menu == "🏠 Inicio":
        modulo_inicio()
    elif menu == "📅 Programación":
        pantalla_programador() 
    elif menu == "📋 Reportes":
        st.info("Módulo de Reportes Detallados")
    elif menu == "👥 Personal":
        pantalla_personal() # Ejecuta la lógica de asignación aleatoria por cuotas
