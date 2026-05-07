import streamlit as st
import pandas as pd
import io
import random
from datetime import datetime, timedelta
from github import Github
# Importamos el motor de programación
try:
    from logic_programador import pantalla_programador
except ImportError:
    st.error("⚠️ No se encontró 'logic_programador.py'. Asegúrate de que ambos archivos estén en la misma carpeta.")

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo - Gestión Operativa", layout="wide", initial_sidebar_state="expanded")

# --- URLs DE IMÁGENES GITHUB ---
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGO_CABLE = f"{URL_BASE}logo_empresa_2.png" 

# --- ESTILOS CSS AVANZADOS ---
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
    .stMetric {{ background-color: white; padding: 20px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border: 1px solid #eee; }}
    .card-empresa {{
        background-color: white; padding: 30px; border-radius: 25px;
        text-align: center; border: 1px solid #eee; transition: 0.4s;
    }}
    .card-empresa:hover {{ transform: translateY(-5px); box-shadow: 0 12px 20px rgba(0,0,0,0.1); }}
    </style>
    """, unsafe_allow_html=True)

# --- 1. FUNCIONES DE DATOS ---

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
        repo.update_file(nombre_archivo, mensaje, output.getvalue(), contents.sha)
        st.success(f"✅ {nombre_archivo} sincronizado.")
    except:
        repo.create_file(nombre_archivo, mensaje, output.getvalue())

# --- 2. MÓDULOS DE INTERFAZ ---

def modulo_inicio():
    st.markdown(f'<div class="welcome-card"><h1>Panel de Control {st.session_state.empresa}</h1><p>Gestión de turnos saludable, equitativa y control de staffing.</p></div>', unsafe_allow_html=True)
    
    df_p = cargar_excel("empleados.xlsx")
    df_m = cargar_excel("malla_historica.xlsx")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Técnicos Activos", len(df_p) if not df_p.empty else "0")
    c2.metric("Grupos", "4")
    c3.metric("Última Malla", df_m['Fecha_Raw'].max().strftime('%d/%m/%Y') if not df_m.empty else "N/A")
    c4.metric("Versión", "V5.5 Pro")

    if not df_m.empty:
        st.subheader("📊 Resumen Operativo Actual")
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.write("**Distribución de Turnos por Grupo**")
            st.bar_chart(df_m.groupby(["Grupo", "Turno"]).size().unstack(fill_value=0))
        with col_chart2:
            st.write("**Días de Descanso Acumulados**")
            descansos = df_m[df_m["Turno"].isin(["DESC", "COMP"])].groupby("Grupo").size()
            st.area_chart(descansos)

def modulo_personal():
    st.header("👥 Gestión de Personal y Roles")
    df_emp = cargar_excel("empleados.xlsx")
    if df_emp.empty:
        df_emp = pd.DataFrame(columns=["Nombre", "Cargo", "Cedula", "Grupo"])
    
    tab1, tab2 = st.tabs(["📋 Lista de Técnicos", "⚙️ Configuración de Grupos"])
    
    with tab1:
        st.info("Cualquier cambio en esta tabla se reflejará en los reportes de nómina y detallados.")
        df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic", key="editor_personal")
        if st.button("💾 Guardar Cambios en la Base"):
            guardar_excel(df_edit, "empleados.xlsx", "Update Personal")
            st.rerun()

    with tab2:
        st.subheader("Reasignación Masiva")
        if st.button("🎲 Mezclar y Reasignar Grupos Aleatoriamente"):
            grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"] * (len(df_emp)//4 + 1)
            random.shuffle(grupos)
            df_emp["Grupo"] = grupos[:len(df_emp)]
            guardar_excel(df_emp, "empleados.xlsx", "Reasignacion Grupos")
            st.rerun()

def modulo_detallado():
    st.header("📋 Detallado Programación (Vista por Técnico)")
    df_m = cargar_excel("malla_historica.xlsx")
    df_e = cargar_excel("empleados.xlsx")
    
    if df_m.empty or df_e.empty:
        st.warning("⚠️ Faltan datos. Asegúrate de tener personal registrado y una malla generada."); return

    df_e["Grupo"] = df_e["Grupo"].astype(str)
    df_m["Grupo"] = df_m["Grupo"].astype(str)
    
    df_det = df_e.merge(df_m, on="Grupo")
    
    # Buscador de técnico
    tecnico = st.selectbox("Buscar Técnico Específico:", ["Todos"] + list(df_e['Nombre'].unique()))
    if tecnico != "Todos":
        df_det = df_det[df_det['Nombre'] == tecnico]

    matriz = df_det.pivot_table(
        index=["Grupo", "Nombre"], 
        columns="Fecha_Col", 
        values="Turno", 
        aggfunc='first'
    ).reindex(columns=df_m["Fecha_Col"].unique())

    st.dataframe(matriz, use_container_width=True)

# --- 3. FLUJO PRINCIPAL ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None

if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(LOGO_APP, use_container_width=True)
        st.markdown("<h2 style='text-align:center;'>Portal MovilGo</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            user = st.text_input("Usuario")
            pw = st.text_input("Contraseña", type="password")
            if st.button("Iniciar Sesión"):
                st.session_state.logged_in = True
                st.rerun()

elif st.session_state.empresa is None:
    st.markdown("<h2 style='text-align:center; padding-top:2rem;'>Seleccione la Operación</h2>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown(f'''
            <div class="card-empresa">
                <img src="{LOGO_CABLE}" width="180">
                <h3>Cable Móvil</h3>
                <p>Gestión de Redes y Mantenimiento</p>
            </div>
        ''', unsafe_allow_html=True)
        if st.button("Ingresar a Cable Móvil"):
            st.session_state.empresa = "Cable Móvil"
            st.rerun()

else:
    with st.sidebar:
        st.image(LOGO_CABLE, width=150)
        st.divider()
        menu = st.radio("MENÚ PRINCIPAL", ["🏠 Inicio", "📅 Programación", "📋 Detallado", "👥 Personal"])
        st.divider()
        if st.button("🚪 Cerrar Operación"):
            st.session_state.empresa = None
            st.rerun()

    if menu == "🏠 Inicio":
        modulo_inicio()
    elif menu == "📅 Programación":
        pantalla_programador() # Ejecuta el motor de logic_programador.py
    elif menu == "📋 Detallado":
        modulo_detallado()
    elif menu == "👥 Personal":
        modulo_personal()
