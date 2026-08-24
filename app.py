import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime, date
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# =========================================================
# 🔐 1. MOTOR DE SEGURIDAD Y USUARIOS (POSTGRESQL)
# =========================================================
load_dotenv(override=True)
url_db = os.getenv("DATABASE_URL", "sqlite:///movilgo_local.db").replace('"', '').replace("'", "")
engine_seguridad = create_engine(url_db)

# Crear la tabla de usuarios y el Super Admin por defecto
with engine_seguridad.begin() as conn:
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS usuarios_sistema (
            usuario VARCHAR(50) PRIMARY KEY,
            password VARCHAR(50),
            rol VARCHAR(20),
            empresa VARCHAR(50)
        )
    """))
    conteo = conn.execute(text("SELECT COUNT(*) FROM usuarios_sistema")).scalar()
    if conteo == 0:
        conn.execute(text("INSERT INTO usuarios_sistema (usuario, password, rol, empresa) VALUES ('admin', 'movilgo2026', 'Administrador', 'Todas')"))

def autenticar_usuario(usuario, password):
    try:
        df_users = pd.read_sql(f"SELECT * FROM usuarios_sistema WHERE usuario='{usuario}' AND password='{password}'", engine_seguridad)
        if not df_users.empty:
            return df_users.iloc[0] 
        return None
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def panel_gestion_usuarios():
    st.markdown("## 🔐 Gestión de Usuarios y Accesos")
    st.info("Solo los Administradores pueden ver esta pantalla. Aquí puedes crear cuentas para tu equipo.")
    
    st.markdown("### 👥 Usuarios Activos")
    try:
        df_activos = pd.read_sql("SELECT usuario, rol, empresa FROM usuarios_sistema", engine_seguridad)
        st.dataframe(df_activos, use_container_width=True)
    except:
        st.warning("No se pudieron cargar los usuarios.")

    st.markdown("### ➕ Crear Nuevo Usuario")
    with st.form("form_nuevo_usuario"):
        c1, c2 = st.columns(2)
        nuevo_user = c1.text_input("Nombre de Usuario (Ej: jperez)")
        nuevo_pass = c2.text_input("Contraseña", type="password")
        
        c3, c4 = st.columns(2)
        nuevo_rol = c3.selectbox("Rol del Usuario", ["Administrador", "Programador", "Consulta"])
        nueva_emp = c4.selectbox("Empresa Asignada", ["Cablemovil SAS", "Greenmovil SAS", "Todas"])
        
        if st.form_submit_button("💾 Crear Usuario"):
            if nuevo_user and nuevo_pass:
                try:
                    with engine_seguridad.begin() as conn:
                        conn.execute(text(f"INSERT INTO usuarios_sistema (usuario, password, rol, empresa) VALUES ('{nuevo_user}', '{nuevo_pass}', '{nuevo_rol}', '{nueva_emp}')"))
                    st.success(f"✅ Usuario '{nuevo_user}' creado exitosamente.")
                    st.rerun()
                except Exception as e:
                    st.error("❌ Error: El usuario ya existe o hubo un problema en la Base de Datos.")
            else:
                st.error("⚠️ El usuario y la contraseña son obligatorios.")

# --- IMPORTACIÓN DE MOTORES LÓGICOS ---
try:
    from logic_programador import pantalla_programador, pantalla_personal, cargar_excel, pantalla_abordaje, pantalla_otros_cargos
except ImportError:
    st.error("⚠️ No se encontró 'logic_programador.py' (Motor de Cablemovil).")

try:
    from logic_greenmovil import pantalla_personal_green, pantalla_parametrizador_green, pantalla_mallas_green
except ImportError:
    pass 

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="MovilGo - Hub Corporativo", 
    page_icon="🏢",
    layout="wide", 
    initial_sidebar_state="expanded"
)

URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_MÓVILGO = f"{URL_BASE}MovilGo.png"
CONFIG_FILE = "config_estructural.json"

# --- INICIALIZACIÓN DE VARIABLES DE SESIÓN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa_seleccionada' not in st.session_state: st.session_state.empresa_seleccionada = None
if 'rol' not in st.session_state: st.session_state.rol = None
if 'empresa_asignada' not in st.session_state: st.session_state.empresa_asignada = None

def cargar_configuracion():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        default_config = {
            "Técnicos": {
                "descripcion": "Operación 24/7",
                "extension_turno": 7,
                "grupos": ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"],
                "rotacion": "Determinista por Grupos"
            }
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config

if 'config_personal' not in st.session_state:
    st.session_state.config_personal = cargar_configuracion()

# --- 2. TEMATIZACIÓN DINÁMICA ---
empresa_actual = st.session_state.empresa_seleccionada

if empresa_actual == "Greenmovil SAS":
    PRIMARY_COLOR = "#145a4f"
    SIDEBAR_BG = "#145a4f"
    SIDEBAR_TEXT = "#FFFFFF" 
    APP_BG = "#FFFFFF"
    BTN_GRADIENT = "linear-gradient(135deg, #0d3d35 0%, #145a4f 100%)" 
    BTN_SHADOW = "rgba(20, 90, 79, 0.4)"
    CARD_GRADIENT = "linear-gradient(135deg, #0d3d35 0%, #145a4f 100%)"
    MENU_HOVER = "rgba(255, 255, 255, 0.15)"
else:
    PRIMARY_COLOR = "#1E3D59"
    SIDEBAR_BG = "#F8F9FA" 
    SIDEBAR_TEXT = "#1E3D59"
    APP_BG = "#FFFFFF"
    BTN_GRADIENT = "linear-gradient(135deg, #1E3D59 0%, #3a6073 100%)"
    BTN_SHADOW = "rgba(30, 61, 89, 0.4)"
    CARD_GRADIENT = "linear-gradient(135deg, #1E3D59 0%, #3a6073 100%)"
    MENU_HOVER = "rgba(30, 61, 89, 0.1)"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {APP_BG}; transition: 0.5s ease; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
    
    [data-testid="stSidebar"] {{ 
        background-color: {SIDEBAR_BG} !important; 
        border-right: 1px solid #E5E7EB; 
        transition: 0.5s ease;
    }}
    
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] h4 {{
        color: {SIDEBAR_TEXT} !important;
    }}

    div[role="radiogroup"] {{
        gap: 8px !important;
    }}
    div[role="radiogroup"] > label {{
        background-color: transparent;
        padding: 10px 15px;
        border-radius: 12px;
        border: 1px solid transparent;
        transition: all 0.3s ease;
        cursor: pointer;
        width: 100%;
        margin-bottom: 5px;
    }}
    div[role="radiogroup"] > label:hover {{
        background-color: {MENU_HOVER};
        transform: translateX(5px);
    }}
    div[role="radiogroup"] > label > div:first-child {{
        display: none !important;
    }}
    div[role="radiogroup"] > label p {{
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        margin: 0 !important;
    }}
    div[role="radiogroup"] > label[data-checked="true"] {{
        background: {CARD_GRADIENT} !important;
        box-shadow: 0 4px 10px {BTN_SHADOW};
    }}
    div[role="radiogroup"] > label[data-checked="true"] p {{
        color: #FFFFFF !important;
    }}
    
    .stButton>button {{ 
        width: 100%; border-radius: 12px; font-weight: 700; height: 3.2em; 
        transition: all 0.3s ease; border: none; background: {BTN_GRADIENT} !important; color: #FFFFFF !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
    }}
    .stButton>button:hover {{ transform: translateY(-3px); box-shadow: 0 8px 15px {BTN_SHADOW}; }}
    .stButton>button * {{ color: #FFFFFF !important; }}
    
    .stTextInput>div>div>input {{
        border-radius: 10px; border: 1.5px solid #d1d5db; padding: 12px 15px; color: #17202A !important; background-color: #FFFFFF !important;
    }}
    .stTextInput>div>div>input:focus {{ border-color: {PRIMARY_COLOR}; box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.1); }}
    
    /* 🌟 Modificamos el tamaño del botón para que se vea bien debajo de las imágenes */
    .btn-empresa>button {{
        height: 3.5em !important; font-size: 1.2rem !important; background: white !important;
        color: #1E3D59 !important; border: 2px solid #1E3D59 !important;
        margin-top: 10px;
    }}
    .btn-empresa>button:hover {{ background: #1E3D59 !important; color: white !important; }}
    
    .welcome-card {{
        background: {CARD_GRADIENT}; color: white; padding: 3rem; border-radius: 20px; 
        box-shadow: 0 15px 35px rgba(0,0,0,0.15); margin-bottom: 2.5rem; text-align: center; transition: 0.5s ease;
    }}
    .login-title {{ text-align: center; color: {PRIMARY_COLOR}; font-weight: 900; margin-top: 15px; margin-bottom: 5px; font-size: 3.2rem; }}
    .login-subtitle {{ text-align: center; color: #666; font-size: 1.2rem; font-weight: 500; margin-bottom: 30px; }}
    
    .footer-credits {{
        text-align: center;
        margin-top: 50px;
        padding-top: 20px;
        border-top: 1px solid #eee;
        color: #888;
    }}
    .footer-credits h4 {{ color: {PRIMARY_COLOR}; margin-bottom: 5px; font-weight: 800; }}
    .footer-credits p {{ font-size: 0.95rem; margin: 2px; }}
    </style>
    """, unsafe_allow_html=True)

def modulo_inicio():
    st.markdown(f'''
        <div class="welcome-card">
            <h1 style="font-size: 2.5rem; font-weight: 800; color: white;">👋 ¡Bienvenido al Panel de {st.session_state.empresa_seleccionada}!</h1>
            <p style="font-size: 1.3rem; opacity: 0.9; margin-top: 10px; color: white;">
                Inteligencia Operativa y Sistematización de Turnos
            </p>
        </div>
    ''', unsafe_allow_html=True)
    
    if st.session_state.empresa_seleccionada == "Cablemovil SAS":
        try:
            df_p = cargar_excel("empleados_grupos.xlsx") 
            total_emp = len(df_p) if not df_p.empty else "0"
        except:
            total_emp = "0"
    else:
        total_emp = "Módulo Dinámico"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👷 Personal Registrado", total_emp)
    c2.metric("📂 Modelos Activos", len(st.session_state.config_personal))
    c3.metric("⚖️ Deuda Global", "0 días")
    c4.metric("📡 Estado de BD", "Conectado", delta="Estable")

    st.write("---")
    
    st.markdown(f"<h3 style='color: {PRIMARY_COLOR}; font-weight: 800;'>⚖️ Reglas de Programación Aplicadas</h3>", unsafe_allow_html=True)
    st.markdown("El motor algorítmico de **MovilGo** rige sus procesos matemáticos bajo las normativas vigentes de la **Reforma Laboral Colombiana**, garantizando una malla operativa justa, humana y legal.")
    
    c_r1, c_r2 = st.columns(2)
    with c_r1:
        st.info("📉 **Reducción de Jornada Máxima:**\nEl sistema audita automáticamente que la programación base no sobrepase el umbral de las **42 horas semanales obligatorias** dictadas para el año 2026.")
        st.success("🛌 **Causación de Descansos Compensatorios:**\nSi el algoritmo programa a un trabajador durante un **Día Domingo**, el sistema forzará de forma automatizada un día compensatorio de descanso en la semana inmediatamente posterior.")
    with c_r2:
        st.warning("🌙 **Protección Circadiana y Fatiga:**\nLos validadores internos bloquean transiciones críticas de fatiga; está prohibido programar un turno diurno (Ej: T1) inmediatamente después de un turno nocturno profundo (Ej: T3/T4) sin un día de descanso intermedio.")
        st.error("⏳ **Horas Extras y Recargos Nocturnos:**\nEl motor de nómina aísla las horas ordinarias, detecta horas adicionales transcurridas post-jornada, y marca como recargo nocturno toda hora laborada en las ventanas de tiempo establecidas por la ley.")

    st.markdown(f'''
        <div class="footer-credits">
            <h4>MovilGo - Plataforma de Inteligencia Operativa</h4>
            <p>Arquitectura, Lógica Algorítmica y Desarrollo por el <b>Ingeniero Richard Guevara</b></p>
            <p><i>Operaciones Greenmovil SAS © {date.today().year}</i></p>
        </div>
    ''', unsafe_allow_html=True)

# --- PANTALLA 1: LOGIN ---
if not st.session_state.logged_in:
    _, login_center, _ = st.columns([1.5, 2.5, 1.5])
    with login_center:
        st.write(""); st.write("")
        with st.container():
            _, img_login, _ = st.columns([1, 4, 1])
            with img_login: 
                st.image(LOGO_MÓVILGO, use_container_width=True)
            
            st.markdown("<h1 class='login-title'>MovilGo</h1>", unsafe_allow_html=True)
            st.markdown("<p class='login-subtitle'>Software Corporativo para la Gestión de Turnos</p>", unsafe_allow_html=True)
            
            u = st.text_input("👤 Nombre de Usuario", placeholder="Ej: admin")
            p = st.text_input("🔒 Contraseña", type="password", placeholder="••••••••")
            
            st.write("")
            if st.button("🚀 INICIAR SESIÓN", use_container_width=True):
                datos_usuario = autenticar_usuario(u, p)
                
                if datos_usuario is not None:
                    st.session_state.logged_in = True
                    st.session_state.rol = datos_usuario["rol"]
                    st.session_state.empresa_asignada = datos_usuario["empresa"]
                    
                    if st.session_state.empresa_asignada != "Todas":
                        st.session_state.empresa_seleccionada = st.session_state.empresa_asignada
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas. Por favor, intenta de nuevo.")

# --- PANTALLA 2: SELECCIÓN DE EMPRESA ---
elif st.session_state.empresa_seleccionada is None:
    st.markdown("<h2 class='login-title' style='margin-top: 5vh; font-size: 3rem;'>🏢 Seleccione el Entorno Operativo</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#666; margin-bottom: 50px; font-size: 1.2rem;'>¿Qué operación desea gestionar hoy?</p>", unsafe_allow_html=True)
    
    _, col1, col2, _ = st.columns([1, 2, 2, 1])
    
    with col1:
        # 🌟 Carga dinámica de la imagen de Cablemovil
        try:
            st.image("logo_cablemovil.jpg", use_container_width=True)
        except Exception:
            st.info("💡 Coloca la imagen 'logo_cablemovil.jpg' en la carpeta.")
            
        st.markdown('<div class="btn-empresa">', unsafe_allow_html=True)
        if st.button("Entrar a Cablemovil SAS", use_container_width=True):
            st.session_state.empresa_seleccionada = "Cablemovil SAS"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        
    with col2:
        # 🌟 Carga dinámica de la imagen de Greenmovil
        try:
            st.image("logo_greenmovil.png", use_container_width=True)
        except Exception:
            st.info("💡 Coloca la imagen 'logo_greenmovil.png' en la carpeta.")
            
        st.markdown('<div class="btn-empresa">', unsafe_allow_html=True)
        if st.button("Entrar a Greenmovil SAS", use_container_width=True):
            st.session_state.empresa_seleccionada = "Greenmovil SAS"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# --- PANTALLA 3: INTERIOR DE LA APLICACIÓN ---
else:
    with st.sidebar:
        st.write("")
        st.image(LOGO_MÓVILGO, use_container_width=True)
        
        st.markdown(f"<div style='text-align: center; color: #888; font-size: 0.9em; margin-bottom: 5px;'>👤 Rol: <b>{st.session_state.rol}</b></div>", unsafe_allow_html=True)
        st.markdown(f"<h4 style='text-align:center; color: {SIDEBAR_TEXT}; margin-bottom: 25px;'>{st.session_state.empresa_seleccionada}</h4>", unsafe_allow_html=True)
        
        # --- MENÚ DINÁMICO ---
        if st.session_state.empresa_seleccionada == "Cablemovil SAS":
            opciones_menu = ["🏠 Inicio", "👥 Personal", "🔧 Prog. Técnicos", "🚀 Prog. Abordaje", "📦 Otros Cargos"]
        elif st.session_state.empresa_seleccionada == "Greenmovil SAS":
            opciones_menu = ["🏠 Inicio", "👥 Personal", "⚙️ Parametrizador", "📅 Mallas Operaciones"]
        else:
            opciones_menu = ["🏠 Inicio"]
            
        if st.session_state.rol == "Administrador":
            opciones_menu.append("🔐 Gestión Usuarios")
            
        menu = st.radio("Navegación del Sistema", opciones_menu, label_visibility="collapsed")
        
        st.divider()
        
        if st.session_state.empresa_asignada == "Todas":
            if st.button("🔄 Cambiar de Empresa"):
                st.session_state.empresa_seleccionada = None
                st.rerun()
            
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.logged_in = False
            st.session_state.empresa_seleccionada = None
            st.session_state.rol = None
            st.rerun()

    # --- RUTEO DE LÓGICA ---
    if menu == "🏠 Inicio": 
        modulo_inicio()
        
    elif menu == "🔐 Gestión Usuarios":
        panel_gestion_usuarios()
        
    elif st.session_state.empresa_seleccionada == "Cablemovil SAS":
        if menu == "👥 Personal": pantalla_personal()
        elif menu == "🔧 Prog. Técnicos": pantalla_programador()
        elif menu == "🚀 Prog. Abordaje": pantalla_abordaje()
        elif menu == "📦 Otros Cargos": pantalla_otros_cargos()
            
    elif st.session_state.empresa_seleccionada == "Greenmovil SAS":
        if menu == "👥 Personal": pantalla_personal_green()
        elif menu == "⚙️ Parametrizador": pantalla_parametrizador_green()
        elif menu == "📅 Mallas Operaciones": pantalla_mallas_green()
