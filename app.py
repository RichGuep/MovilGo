import streamlit as st
import pandas as pd
import io
import json
import os
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

# --- LÓGICA DE ALMACENAMIENTO DE PARÁMETROS DINÁMICOS ---
CONFIG_FILE = "config_estructural.json"

def cargar_configuracion():
    """Carga los tipos de personal parametrizados"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        # Valores por defecto iniciales (Tus reglas actuales para no romper nada)
        default_config = {
            "Técnicos": {
                "descripcion": "Operación de soporte técnico en campo 24/7.",
                "extension_turno": 8,
                "personas_por_rol": 4,
                "rotacion": "Semanal (6x2)",
                "reglas": ["Rotación Dominical entre 4 grupos.", "Descanso mínimo de ley tras turnos nocturnos.", "Mínimo 3 grupos activos por día."]
            },
            "Abordaje": {
                "descripcion": "Gestión comercial y de abordaje operativo.",
                "extension_turno": 8,
                "personas_por_rol": 5,
                "rotacion": "Quincenal",
                "reglas": ["Bloques sólidos de gestión.", "Acceso justo a fines de semana.", "Respeto total a periodos de desconexión."]
            }
        }
        guardar_configuracion(default_config)
        return default_config

def guardar_configuracion(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

# Cargar configuraciones al inicio
if 'config_personal' not in st.session_state:
    st.session_state.config_personal = cargar_configuracion()


# --- 2. ESTILOS CSS PERSONALIZADOS ---
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
    """Pantalla de Bienvenida Dinámica con contexto de Reforma Laboral"""
    st.markdown(f'''
        <div class="welcome-card">
            <h1>👋 ¡Bienvenido al Panel de Control {st.session_state.empresa}!</h1>
            <p style="font-size: 1.2rem; opacity: 0.9;">
                Garantizando cobertura técnica y operativa bajo el cumplimiento estricto de la Reforma Laboral Colombiana 2026 (42 Horas Semanales).
            </p>
        </div>
    ''', unsafe_allow_html=True)
    
    # Métricas Superiores
    df_p = cargar_excel("empleados.xlsx")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👷 Personal Registrado", len(df_p) if not df_p.empty else "73")
    c2.metric("📂 Modelos Parametrizados", len(st.session_state.config_personal))
    c3.metric("⚖️ Deuda Global", "0 días")
    c4.metric("📡 Estado de Red", "24/7 Activo", delta="Estable")

    st.divider()

    # Contexto Legal: Reforma Laboral
    st.subheader("🇨🇴 Contexto Legal Global: Reforma Laboral")
    inf1, inf2 = st.columns(2)
    with inf1:
        st.info("""
        **📉 Reducción de la Jornada (Ley 2101)**
        Para **2026 la jornada máxima es de 42 horas semanales**. El motor transversal del sistema optimiza los turnos de todos los perfiles sin superar este límite legal.
        """)
    with inf2:
        st.warning("""
        **🛌 Descansos y Compensatorios Obligatorios**
        Se garantiza el descanso inter-turno mínimo y el cálculo automático de los **compensatorios remunerados** según la distribución de la malla horaria.
        """)

    # Transparencia del Algoritmo (DINÁMICO)
    st.subheader("📝 Reglas Operativas por Tipo de Personal")
    
    # Renderizar dinámicamente las tarjetas de reglas según lo que esté guardado
    tipos = list(st.session_state.config_personal.keys())
    
    # Mostrarlos en columnas de a 2
    for i in range(0, len(tipos), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(tipos):
                tipo = tipos[i + j]
                datos = st.session_state.config_personal[tipo]
                with cols[j]:
                    with st.expander(f"💼 Perfil: {tipo}", expanded=True):
                        st.caption(datos["descripcion"])
                        st.markdown(f"**⏱️ Extensión Turno:** {datos['extension_turno']} hrs | **👥 Dotación:** {datos['personas_por_rol']} p/rol | **🔄 Rotación:** {datos['rotacion']}")
                        for regla in datos["reglas"]:
                            st.markdown(f"- {regla}")


def modulo_parametros():
    """Nueva pantalla para agregar o modificar tipos de personal dinámicamente"""
    st.header("⚙️ Parametrización Estructural de Personal")
    st.subheader("Registra un nuevo tipo de personal para que use el motor de programación")

    with st.form("nuevo_perfil_form", clear_on_submit=True):
        nombre_perfil = st.text_input("Nombre del nuevo Tipo de Personal / Área", placeholder="Ej: Call Center, Vigilancia, Administrativos")
        descripcion = st.text_area("Descripción del área", placeholder="Breve descripción de las tareas o el equipo...")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            extension_turno = st.number_input("Extensión de Turno (Horas)", min_value=4, max_value=12, value=8)
        with col2:
            personas_por_rol = st.number_input("Cantidad de Personas requeridas por Rol/Turno", min_value=1, max_value=50, value=5)
        with col3:
            rotacion = st.selectbox("Modelo de Rotación Sugerida", ["Semanal (6x2)", "Quincenal", "Mensual", "Fijo sin rotación"])
            
        st.markdown("**Reglas de negocio específicas (Opcional - Visual):**")
        regla1 = st.text_input("Regla específica 1", placeholder="Ej: No encadenar más de 2 turnos nocturnos")
        regla2 = st.text_input("Regla específica 2", placeholder="Ej: Prioridad de descanso los sábados")

        submit = st.form_submit_button("💾 Guardar y Parametrizar Personal")
        
        if submit:
            if nombre_perfil:
                reglas_lista = [r for r in [regla1, regla2] if r]
                if not reglas_lista:
                    reglas_lista = ["Uso de reglas generales de la Reforma Laboral 2026."]
                
                # Inyección de la nueva estructura
                st.session_state.config_personal[nombre_perfil] = {
                    "descripcion": descripcion,
                    "extension_turno": int(extension_turno),
                    "personas_por_rol": int(personas_por_rol),
                    "rotacion": rotacion,
                    "reglas": reglas_lista
                }
                guardar_configuracion(st.session_state.config_personal)
                st.success(f"🎉 ¡Perfil '{nombre_perfil}' parametrizado con éxito! Ahora puedes asignarle personal y programarlo.")
                st.rerun()
            else:
                st.error("Por favor, ingresa un nombre para el tipo de personal.")

    # Visualizar perfiles actuales
    st.write("---")
    st.subheader("📂 Perfiles de Personal Configurados")
    st.json(st.session_state.config_personal)


# --- 4. FLUJO DE NAVEGACIÓN Y ACCESO ---

if 'splash_done' not in st.session_state: st.session_state.splash_done = False
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = "Grupo Movil"

# PASO 1: SPLASH SCREEN
if not st.session_state.splash_done:
    st.markdown('<div class="centered-box">', unsafe_allow_html=True)
    st.image(LOGO_MÓVILGO, width=550)
    st.markdown("<h1 style='color:#1E3D59;'>Optimizer Pro 2026</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color:#555;'>Cargando sistemas de cumplimiento legal...</p>", unsafe_allow_html=True)
    if st.button("INGRESAR AL PORTAL"):
        st.session_state.splash_done = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# PASO 2: LOGIN
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

# PASO 3: APLICACIÓN PRINCIPAL
else:
    with st.sidebar:
        st.image(LOGO_MÓVILGO, use_container_width=True)
        st.markdown(f"<h3 style='text-align:center;'>{st.session_state.empresa}</h3>", unsafe_allow_html=True)
        st.divider()
        
        # Agregamos "⚙️ Parámetros" al menú de navegación
        menu = st.radio("NAVEGACIÓN", ["🏠 Inicio", "⚙️ Parámetros", "📅 Programación", "📋 Reportes", "👥 Personal"])
        
        st.markdown("<br>"*6, unsafe_allow_html=True)
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.logged_in = False
            st.session_state.splash_done = False
            st.rerun()

    # ROUTER DE PÁGINAS
    if menu == "🏠 Inicio":
        modulo_inicio()
    elif menu == "⚙️ Parámetros":
        modulo_parametros()
    elif menu == "📅 Programación":
        pantalla_programador() 
    elif menu == "📋 Reportes":
        st.info("Módulo de Reportes Detallados")
    elif menu == "👥 Personal":
        pantalla_personal()
