import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date

# --- IMPORTACIÓN DEL MOTOR DE LÓGICA ---
try:
    from logic_programador import pantalla_programador, pantalla_personal, cargar_excel
except ImportError:
    st.error("⚠️ No se encontró 'logic_programador.py'. Asegúrate de que ambos archivos estén en la misma carpeta.")

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="MovilGo - Gestión Operativa 24/7", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_MÓVILGO = f"{URL_BASE}MovilGo.png"

# --- LÓGICA DE ALMACENAMIENTO DE PARÁMETROS ---
CONFIG_FILE = "config_estructural.json"

def cargar_configuracion():
    """Carga los tipos de personal parametrizados"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        default_config = {
            "Técnicos": {
                "descripcion": "Operación de soporte técnico en campo 24/7.",
                "extension_turno": 7,
                "rotacion": "Determinista por Grupos",
                "reglas": ["Garantía total 24/7 de turnos T1, T2 y T3.", "Asignación de un Supervisor por Grupo."]
            },
            "Abordaje": {
                "descripcion": "Gestión comercial y de abordaje operativo.",
                "extension_turno": 7,
                "rotacion": "Alternancia Semanal Quincenal",
                "reglas": ["Bloques de gestión balanceados.", "Cupos de personal parametrizables."]
            }
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config

if 'config_personal' not in st.session_state:
    st.session_state.config_personal = cargar_configuracion()

# --- 2. ESTILOS CSS PERSONALIZADOS ---
PRIMARY_COLOR = "#1E3D59" 
st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; border-right: 1px solid #ffffff22; }}
    [data-testid="stSidebar"] * {{ color: white !important; font-weight: 500; }}
    .stButton>button {{ 
        width: 100%; border-radius: 12px; font-weight: bold; 
        height: 3em; transition: 0.3s; border: none; 
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
    }}
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px; 
        box-shadow: 0 10px 25px rgba(0,0,0,0.1); margin-bottom: 2rem;
    }}
    .centered-box {{
        display: flex; flex-direction: column; align-items: center; 
        justify-content: center; text-align: center; padding: 2rem; margin-top: 5vh;
    }}
    .login-card {{
        max-width: 450px; background: white; padding: 3rem; 
        border-radius: 25px; border: 1px solid #eee; box-shadow: 0 15px 35px rgba(0,0,0,0.15); margin: auto;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. MÓDULOS DE INTERFAZ ---
def modulo_inicio():
    st.markdown(f'''
        <div class="welcome-card">
            <h1>👋 ¡Bienvenido al Panel de Control {st.session_state.empresa}!</h1>
            <p style="font-size: 1.2rem; opacity: 0.9;">
                Garantizando cobertura técnica y operativa por Grupos bajo el cumplimiento estricto de la Reforma Laboral Colombiana 2026.
            </p>
        </div>
    ''', unsafe_allow_html=True)
    
    df_p = cargar_excel("empleados_grupos.xlsx")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👷 Personal Registrado", len(df_p) if not df_p.empty else "0")
    c2.metric("📂 Modelos Activos", len(st.session_state.config_personal))
    c3.metric("⚖️ Deuda Global", "0 días")
    c4.metric("📡 Estado de Red", "24/7 Activo", delta="Estable")

    st.divider()
    st.subheader("🇨🇴 Contexto Legal Global: Reforma Laboral 2026")
    inf1, inf2 = st.columns(2)
    with inf1:
        st.info("""
        **📉 Reducción de la Jornada**
        Para el año **2026 la jornada ordinaria máxima es de 42 horas semanales**. El motor transversal del sistema calcula los acumulados respetando este límite de ley.
        """)
    with inf2:
        st.warning("""
        **🛌 Descansos Compensatorios**
        El sistema genera deudas automáticas de compensación cuando las necesidades del servicio interrumpen los días de descanso base de cada grupo.
        """)

# --- 4. FLUJO DE NAVEGACIÓN Y ACCESO ---
if 'splash_done' not in st.session_state: st.session_state.splash_done = False
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = "Grupo Movil"

if not st.session_state.splash_done:
    st.markdown('<div class="centered-box">', unsafe_allow_html=True)
    st.image(LOGO_MÓVILGO, width=550)
    st.markdown("<h1 style='color:#1E3D59;'>Optimizer Pro 2026</h1>", unsafe_allow_html=True)
    if st.button("INGRESAR AL PORTAL"):
        st.session_state.splash_done = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif not st.session_state.logged_in:
    st.markdown('<div class="centered-box"><div class="login-card">', unsafe_allow_html=True)
    st.image(LOGO_MÓVILGO, width=180)
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

else:
    with st.sidebar:
        st.image(LOGO_MÓVILGO, use_container_width=True)
        st.markdown(f"<h3 style='text-align:center;'>{st.session_state.empresa}</h3>", unsafe_allow_html=True)
        st.divider()
        menu = st.radio("NAVEGACIÓN", ["🏠 Inicio", "👥 Personal", "📅 Programación"])
        
        st.markdown("<br>"*8, unsafe_allow_html=True)
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.logged_in = False
            st.session_state.splash_done = False
            st.rerun()

    if menu == "🏠 Inicio":
        modulo_inicio()
    elif menu == "👥 Personal":
        pantalla_personal()
    elif menu == "📅 Programación":
        pantalla_programador()
