import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from github import Github
from logic_programador import (
    generar_malla_base, 
    color_t, 
    es_cambio_saludable, 
    obtener_horario, 
    aplicar_estilos
)

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo v2.0", layout="wide", initial_sidebar_state="expanded")

PRIMARY_COLOR = "#1E3D59"
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGOS = {
    "Greenmóvil": f"{URL_BASE}logo_empresa_1.png",
    "Cable Móvil": f"{URL_BASE}logo_empresa_2.png",
    "BogotáMóvil": f"{URL_BASE}logo_empresa_3.png"
}

# --- 2. CSS ---
st.markdown(f"""
    <style>
    .main {{ background-color: #f0f2f6; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .welcome-card {{ background: white; padding: 2rem; border-radius: 15px; border-top: 5px solid {PRIMARY_COLOR}; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
    .stButton>button {{ border-radius: 8px; font-weight: bold; height: 3em; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. PERSISTENCIA ---
def conectar_github():
    try: return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except: return None

def cargar_excel(nombre_archivo):
    repo = conectar_github()
    if not repo: return pd.DataFrame()
    try:
        contents = repo.get_contents(nombre_archivo)
        df = pd.read_excel(io.BytesIO(contents.decoded_content))
        if 'Fecha_Raw' in df.columns: df['Fecha_Raw'] = pd.to_datetime(df['Fecha_Raw'])
        return df
    except: return pd.DataFrame()

def guardar_excel(df_nuevo, nombre_archivo):
    repo = conectar_github()
    if not repo: return
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_nuevo.to_excel(writer, index=False)
    try:
        contents = repo.get_contents(nombre_archivo)
        repo.update_file(nombre_archivo, "Update Malla", output.getvalue(), contents.sha)
    except:
        repo.create_file(nombre_archivo, "Init Malla", output.getvalue())
    st.success(f"Datos guardados en {nombre_archivo}")

# --- 4. MÓDULOS ---
def modulo_programacion():
    st.header("📅 Programación Maestra")
    repo = conectar_github()
    
    with st.container():
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Fecha Inicio", datetime(2026, 7, 1))
        f_fin = c2.date_input("Fecha Fin", datetime(2026, 7, 31))
        
        if st.button("🚀 Calcular Nueva Rotación"):
            with st.spinner("Procesando algoritmo 24/7..."):
                df_res = generar_malla_base(f_ini, f_fin, repo)
                guardar_excel(df_res, "malla_historica.xlsx")
                st.rerun()

    df_m = cargar_excel("malla_historica.xlsx")
    if not df_m.empty:
        df_view = df_m[(df_m['Fecha_Raw'] >= pd.to_datetime(f_ini)) & (df_m['Fecha_Raw'] <= pd.to_datetime(f_fin))]
        
        st.subheader("Vista por Grupos")
        matriz = df_view.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        st.dataframe(aplicar_estilos(matriz), use_container_width=True)

def modulo_detallado():
    st.header("📋 Detallado por Técnico")
    df_m = cargar_excel("malla_historica.xlsx")
    df_e = cargar_excel("empleados.xlsx")
    
    if not df_m.empty and not df_e.empty:
        df_det = df_e.merge(df_m, on="Grupo")
        matriz = df_det.pivot_table(index=["Nombre", "Grupo"], columns="Fecha_Col", values="Turno", aggfunc='first')
        st.dataframe(aplicar_estilos(matriz), use_container_width=True)
    else:
        st.warning("Se requiere cargar la malla y la base de empleados.")

def modulo_nomina():
    st.header("💰 Reporte de Nómina")
    df_m = cargar_excel("malla_historica.xlsx")
    df_e = cargar_excel("empleados.xlsx")
    if not df_m.empty and not df_e.empty:
        df_nom = df_e.merge(df_m, on="Grupo")
        df_nom["Hora Inicio"], df_nom["Hora Fin"] = zip(*df_nom["Turno"].map(obtener_horario))
        st.dataframe(df_nom[["Fecha_Raw", "Nombre", "Cedula", "Grupo", "Turno", "Hora Inicio", "Hora Fin"]], use_container_width=True)

def modulo_personal():
    st.header("👥 Gestión de Personal")
    df_emp = cargar_excel("empleados.xlsx")
    if df_emp.empty:
        df_emp = pd.DataFrame(columns=["Nombre", "Cedula", "Grupo", "Cargo"])
        
    df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic")
    if st.button("💾 Guardar Personal"):
        guardar_excel(df_edit, "empleados.xlsx")

# --- 5. LÓGICA DE NAVEGACIÓN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None

if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(LOGO_APP)
        u, p = st.text_input("Usuario"), st.text_input("Clave", type="password")
        if st.button("Ingresar"):
            if u != "" and p != "": 
                st.session_state.logged_in = True
                st.rerun()
elif st.session_state.empresa is None:
    st.markdown("<h2 style='text-align: center;'>Seleccione su Operación</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    for i, emp in enumerate(LOGOS.keys()):
        with [c1, c2, c3][i]:
            st.image(LOGOS[emp], width=150)
            if st.button(f"Entrar a {emp}"):
                st.session_state.empresa = emp
                st.rerun()
else:
    with st.sidebar:
        st.image(LOGOS[st.session_state.empresa], width=150)
        st.write(f"**Operación:** {st.session_state.empresa}")
        st.divider()
        menu = st.radio("Menú", ["📅 Programación", "📋 Detallado", "💰 Nómina", "👥 Personal"])
        if st.button("🚪 Salir"):
            st.session_state.empresa = None
            st.rerun()

    if menu == "📅 Programación": modulo_programacion()
    elif menu == "📋 Detallado": modulo_detallado()
    elif menu == "💰 Nómina": modulo_nomina()
    elif menu == "👥 Personal": modulo_personal()
