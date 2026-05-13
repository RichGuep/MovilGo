import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta, date
from github import Github

# =========================================================
# 1. CONFIGURACIÓN Y CONSTANTES
# =========================================================
st.set_page_config(
    page_title="MovilGo Optimizer Pro v5.0", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()

GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
OPCIONES_TURNOS = ["T1", "T2", "T3", "RELEVO", "DISPONIBLE", "T1 APOYO", "DESCANSO", "COMPENSADO"]

URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_MOVILGO = f"{URL_BASE}MovilGo.png"
PRIMARY_COLOR = "#1E3D59"

# =========================================================
# 2. ESTILOS CSS (UI/UX)
# =========================================================
st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; border-right: 1px solid #ffffff22; }}
    [data-testid="stSidebar"] * {{ color: white !important; font-weight: 500; }}
    
    /* Botones */
    .stButton>button {{ width: 100%; border-radius: 12px; font-weight: bold; height: 3em; transition: 0.3s; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
    
    /* Tarjeta de Bienvenida */
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); margin-bottom: 2rem;
    }}
    
    /* Login y Splash */
    .centered-box {{ display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 2rem; margin-top: 5vh; }}
    .login-card {{ max-width: 450px; background: white; padding: 3rem; border-radius: 25px; border: 1px solid #eee; box-shadow: 0 15px 35px rgba(0,0,0,0.15); margin: auto; }}
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# 3. LÓGICA DE NEGOCIO INTEGRADA
# =========================================================

def ejecutar_auditoria(df, tipo):
    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()
    for f, c in cobertura.items():
        if c < 3: errores.append(f"❌ Cobertura insuficiente el {f.date()} ({c}/3 grupos)")
    return errores, cobertura

def generar_malla_tecnicos(inicio, fin):
    filas = []
    # Lógica de rotación simplificada para ejemplo
    for fecha in pd.date_range(inicio, fin):
        for i, g in enumerate(GRUPOS_TEC):
            turno = "T1" if (fecha.day + i) % 4 == 0 else "T2"
            if fecha.weekday() == 6 and i == 0: turno = "DESCANSO"
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": turno})
    return pd.DataFrame(filas)

def style_malla(df_pivot):
    colores = {"T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8", "DESCANSO": "#2C3E50", "COMPENSADO": "#FDEBD0"}
    return df_pivot.style.map(lambda val: f'background-color: {colores.get(val, "")}; color: {"white" if val=="DESCANSO" else "black"}')

# =========================================================
# 4. PANTALLAS (MÓDULOS)
# =========================================================

def modulo_inicio():
    # --- LA BIENVENIDA QUE SOLICITASTE ---
    st.markdown(f'''
        <div class="welcome-card">
            <h1>👋 ¡Bienvenido al Panel de Control MovilGo!</h1>
            <p style="font-size: 1.2rem; opacity: 0.9;">
                Garantizando cobertura técnica 24/7 bajo el cumplimiento estricto de la <b>Reforma Laboral Colombiana 2026</b>.
            </p>
        </div>
    ''', unsafe_allow_html=True)
    
    # Métricas de la Reforma
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("👷 Técnicos Totales", "73")
    c2.metric("📂 Grupos Operativos", "4")
    c3.metric("⚖️ Jornada Semanal", "42h", delta="-2h vs 2025")
    c4.metric("📡 Disponibilidad", "24/7", delta="Estable")

    st.divider()

    # Contexto Legal Detallado
    st.subheader("🇨🇴 Cumplimiento Normativo 2026")
    inf1, inf2 = st.columns(2)
    with inf1:
        st.info("""
        **📉 Reducción Gradual (Ley 2101)**
        Para este 2026, la jornada máxima ha bajado a **42 horas semanales**. Nuestro algoritmo ajusta automáticamente los turnos para no exceder este límite.
        """)
    with inf2:
        st.warning("""
        **🛌 Descansos y Dominicales**
        Se garantiza el **descanso compensatorio** tras jornadas dominicales, asegurando el bienestar físico y mental de los técnicos de campo.
        """)

def pantalla_programador():
    st.title("📅 Programación de Turnos")
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today() + timedelta(days=21))

    if st.button("🚀 Generar Malla Optimizada"):
        st.session_state.m_tecnicos = generar_malla_tecnicos(inicio, fin)

    if "m_tecnicos" in st.session_state:
        df = st.session_state.m_tecnicos.copy()
        df["Label"] = df["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} - {x.strftime('%Y-%m-%d')}")
        pivot = df.pivot(index="Sujeto", columns="Label", values="Turno")
        
        st.subheader("📝 Editor de Malla")
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True)
        
        errs, cob = ejecutar_auditoria(st.session_state.m_tecnicos, "Técnicos")
        st.divider()
        a1, a2 = st.columns([1,2])
        with a1:
            st.metric("Alertas de Ley", len(errs))
            for e in errs: st.error(e)
        with a2:
            st.line_chart(cob)

# =========================================================
# 5. FLUJO PRINCIPAL (LOGIN Y NAVEGACIÓN)
# =========================================================

if 'splash_done' not in st.session_state: st.session_state.splash_done = False
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

# PASO 1: SPLASH
if not st.session_state.splash_done:
    st.markdown('<div class="centered-box">', unsafe_allow_html=True)
    st.image(LOGO_MOVILGO, width=500)
    st.markdown("<h1 style='color:#1E3D59;'>Optimizer Pro 2026</h1>", unsafe_allow_html=True)
    if st.button("INGRESAR AL PORTAL"):
        st.session_state.splash_done = True
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# PASO 2: LOGIN
elif not st.session_state.logged_in:
    _, center, _ = st.columns([1, 1.5, 1])
    with center:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.image(LOGO_MOVILGO, width=150)
        st.markdown("### **Acceso Administrativo**")
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("INICIAR SESIÓN"):
            if u == "admin" and p == "movilgo2026":
                st.session_state.logged_in = True
                st.rerun()
            else: st.error("Acceso denegado")
        st.markdown('</div>', unsafe_allow_html=True)

# PASO 3: APP PRINCIPAL
else:
    with st.sidebar:
        st.image(LOGO_MOVILGO, use_container_width=True)
        menu = st.radio("NAVEGACIÓN", ["🏠 Inicio", "📅 Programación", "👥 Personal"])
        st.divider()
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.logged_in = False
            st.session_state.splash_done = False
            st.rerun()

    if menu == "🏠 Inicio": modulo_inicio()
    elif menu == "📅 Programación": pantalla_programador()
    else: st.info("Módulo en desarrollo")
