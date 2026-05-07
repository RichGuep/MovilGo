import streamlit as st
import pandas as pd
import io
import holidays
import random
from datetime import datetime, timedelta
from github import Github

# --- IMPORTACIÓN DEL MOTOR CORREGIDO ---
# Esto asegura que app.py use la lógica de descansos parametrizables de logic_programador.py
try:
    from logic_programador import pantalla_programador
except ImportError:
    st.error("No se encontró logic_programador.py. Asegúrate de que ambos archivos estén en la misma carpeta.")

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo - Gestión Operativa", layout="wide", initial_sidebar_state="expanded")

# --- URLs DE IMÁGENES GITHUB ---
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGO_CABLE = f"{URL_BASE}logo_empresa_2.png" 

# --- ESTILOS CSS ---
PRIMARY_COLOR = "#1E3D59" 
st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .stButton>button {{ width: 100%; border-radius: 12px; font-weight: bold; transition: 0.3s; height: 3em; }}
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px; margin-bottom: 2rem;
    }}
    .card-empresa {{
        background-color: white; padding: 25px; border-radius: 20px;
        text-align: center; border: 1px solid #eee; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 1. FUNCIONES DE DATOS Y CONEXIÓN ---

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
        if 'Fecha_Raw' in df.columns:
            df['Fecha_Raw'] = pd.to_datetime(df['Fecha_Raw'])
        return df
    except: return pd.DataFrame()

def guardar_excel(df, nombre_archivo, mensaje):
    repo = conectar_github()
    if not repo: return
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    try:
        contents = repo.get_contents(nombre_archivo)
        if nombre_archivo == "malla_historica.xlsx":
            df_previo = pd.read_excel(io.BytesIO(contents.decoded_content))
            df_previo['Fecha_Raw'] = pd.to_datetime(df_previo['Fecha_Raw'])
            df = pd.concat([df_previo, df]).drop_duplicates(subset=['Grupo', 'Fecha_Raw'], keep='last')
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
        repo.update_file(nombre_archivo, mensaje, output.getvalue(), contents.sha)
    except:
        repo.create_file(nombre_archivo, mensaje, output.getvalue())

def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#4d4d4d", "DESC": "#d62728", "COMP": "#ff7f0e"}
    bg = c.get(val, "#ffffff")
    color = "white" if val in c else "black"
    return f'background-color: {bg}; color: {color}; font-weight: bold; text-align: center;'

def obtener_horario(turno):
    h = {"T1": ("06:00", "14:00"), "T2": ("14:00", "22:00"), "T3": ("22:00", "06:00"), "DESC": ("OFF", "OFF"), "COMP": ("OFF", "OFF")}
    return h.get(turno, ("OFF", "OFF"))

# --- 2. MÓDULOS DEL SISTEMA ---

def modulo_inicio():
    st.markdown(f'<div class="welcome-card"><h1>Operación {st.session_state.empresa}</h1><p>Gestión de turnos y personal.</p></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    df_p = cargar_excel("empleados.xlsx")
    c1.metric("Técnicos Activos", len(df_p))
    c2.metric("Grupos Operativos", "4")
    c3.metric("Estado Sistema", "En línea")

def modulo_detallado():
    st.header("📋 Detallado por Técnico")
    df_m = cargar_excel("malla_historica.xlsx")
    df_e = cargar_excel("empleados.xlsx")
    if df_m.empty or df_e.empty: 
        st.warning("No hay datos en el histórico o personal. Genera una malla primero.")
        return
    
    df_e["Grupo"] = df_e["Grupo"].astype(str)
    df_m["Grupo"] = df_m["Grupo"].astype(str)
    df_det = df_e.merge(df_m, on="Grupo")
    
    # Filtro de rango para la vista detallada
    st.info("Visualización de la malla cargada en el histórico.")
    matriz_full = df_det.pivot_table(
        index=["Grupo", "Nombre"], 
        columns="Fecha_Col", 
        values="Turno", 
        aggfunc='first'
    ).reindex(columns=df_m["Fecha_Col"].unique())
    
    st.dataframe(matriz_full.style.map(color_t), use_container_width=True)

def modulo_nomina():
    st.header("💰 Nómina")
    df_m = cargar_excel("malla_historica.xlsx")
    df_e = cargar_excel("empleados.xlsx")
    if df_m.empty or df_e.empty: return
    
    df_e.columns = [c.replace('é', 'e').title() for c in df_e.columns]
    df_nom = df_e.merge(df_m, on="Grupo")
    df_nom["Hora Inicio"], df_nom["Hora Fin"] = zip(*df_nom["Turno"].map(obtener_horario))
    
    reporte = df_nom[["Fecha_Raw", "Nombre", "Cedula", "Cargo", "Grupo", "Turno", "Hora Inicio", "Hora Fin"]].sort_values(["Fecha_Raw", "Nombre"])
    st.dataframe(reporte, use_container_width=True, hide_index=True)

def modulo_personal():
    st.header("👥 Gestión de Personal")
    df_emp = cargar_excel("empleados.xlsx")
    df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic")
    if st.button("💾 Guardar Personal"):
        guardar_excel(df_edit, "empleados.xlsx", "Update Personal")
        st.success("Personal actualizado.")
        st.rerun()

# --- 3. FLUJO PRINCIPAL ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None

if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(LOGO_APP, use_container_width=True)
        st.markdown("<h3 style='text-align:center;'>Acceso Operativo</h3>", unsafe_allow_html=True)
        with st.container(border=True):
            if st.button("Iniciar Sesión"): 
                st.session_state.logged_in = True
                st.rerun()
elif st.session_state.empresa is None:
    _, c2, _ = st.columns([1, 1.5, 1])
    with c2:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_CABLE}" width="200"><h3>Cable Móvil</h3><p>Gestión 24/7</p></div>', unsafe_allow_html=True)
        if st.button("Ingresar a la Operación"): 
            st.session_state.empresa = "Cable Móvil"
            st.rerun()
else:
    with st.sidebar:
        st.image(LOGO_CABLE, width=150)
        st.divider()
        menu = st.radio("MENÚ PRINCIPAL", ["🏠 Inicio", "📅 Programación", "📋 Detallado", "💰 Nómina", "👥 Personal"])
        st.divider()
        if st.button("🚪 Salir"): 
            st.session_state.empresa = None
            st.rerun()
    
    if menu == "🏠 Inicio":
        modulo_inicio()
    elif menu == "📅 Programación":
        # LLAMADA AL MOTOR DE logic_programador.py
        pantalla_programador() 
    elif menu == "📋 Detallado":
        modulo_detallado()
    elif menu == "💰 Nómina":
        modulo_nomina()
    elif menu == "👥 Personal":
        modulo_personal()
