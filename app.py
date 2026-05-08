import streamlit as st
import pandas as pd
import io
import random
from datetime import datetime, timedelta
from github import Github

# --- IMPORTACIÓN DEL MOTOR DE LÓGICA ---
try:
   from logic_programador import pantalla_programador
except ImportError:
    st.error("⚠️ No se encontró 'logic_programador.py'. Asegúrate de que ambos archivos estén en la misma carpeta.")

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo - Gestión Operativa 24/7", layout="wide", initial_sidebar_state="expanded")

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
    .stMetric {{ background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #eee; }}
    .card-empresa {{
        background-color: white; padding: 30px; border-radius: 25px;
        text-align: center; border: 1px solid #eee; transition: 0.4s;
    }}
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
        st.success(f"✅ {nombre_archivo} sincronizado con éxito.")
    except:
        repo.create_file(nombre_archivo, mensaje, output.getvalue())

# --- 2. MÓDULOS DE INTERFAZ ---

def modulo_inicio():
    st.markdown(f'<div class="welcome-card"><h1>Panel de Control {st.session_state.empresa}</h1><p>Garantizando cobertura T1, T2 y T3 con equidad laboral.</p></div>', unsafe_allow_html=True)
    
    df_p = cargar_excel("empleados.xlsx")
    df_m = cargar_excel("malla_historica.xlsx")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Técnicos Totales", len(df_p) if not df_p.empty else "0")
    c2.metric("Grupos Operativos", "4")
    c3.metric("Deuda Global Descansos", int(df_m['Deuda_Compensatorio'].sum()) if not df_m.empty else "0")
    c4.metric("Estado de Red", "24/7 Activo", delta="Estable")

    if not df_m.empty:
        st.subheader("📊 Análisis de Carga Laboral")
        col_a, col_b = st.columns(2)
        with col_a:
            st.write("**Balance de Turnos por Grupo**")
            st.bar_chart(df_m.groupby(["Grupo", "Turno"]).size().unstack(fill_value=0))
        with col_b:
            st.write("**Histórico de Deuda de Compensatorios**")
            # Mostrar la evolución de la deuda por grupo
            st.line_chart(df_m.pivot_table(index='Fecha_Raw', columns='Grupo', values='Deuda_Compensatorio'))

def modulo_personal():
    st.header("👥 Gestión de Plantilla y Roles")
    df_emp = cargar_excel("empleados.xlsx")
    
    if df_emp.empty:
        st.warning("⚠️ No hay personal registrado. Por favor, agregue técnicos a la tabla.")
        df_emp = pd.DataFrame(columns=["Nombre", "Cargo", "Cedula", "Grupo"])
    
    st.info("💡 Clasifique al personal como Master, Técnico A o Técnico B para que el sistema valide el requerimiento diario.")
    df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic", key="editor_plantilla")
    
    if st.button("💾 Guardar Cambios en GitHub"):
        guardar_excel(df_edit, "empleados.xlsx", "Actualización de Personal")
        st.rerun()

def modulo_detallado():
    st.header("📋 Detallado Programación por Técnico")
    df_m = cargar_excel("malla_historica.xlsx")
    df_e = cargar_excel("empleados.xlsx")
    
    if df_m.empty or df_e.empty:
        st.error("⚠️ Datos insuficientes para generar el reporte detallado."); return

    # Cruzar datos
    df_e["Grupo"] = df_e["Grupo"].astype(str)
    df_m["Grupo"] = df_m["Grupo"].astype(str)
    df_det = df_e.merge(df_m, on="Grupo")
    
    # Filtro por cargo o grupo
    st.sidebar.subheader("Filtros de Vista")
    filtro_grupo = st.sidebar.multiselect("Filtrar por Grupo:", options=list(df_e['Grupo'].unique()), default=list(df_e['Grupo'].unique()))
    
    df_v = df_det[df_det['Grupo'].isin(filtro_grupo)]
    
    matriz = df_v.pivot_table(
        index=["Grupo", "Nombre", "Cargo"], 
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
        st.markdown("<h2 style='text-align:center;'>Portal de Acceso</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            user = st.text_input("Usuario Operativo")
            pw = st.text_input("Contraseña", type="password")
            if st.button("Iniciar Sesión"):
                st.session_state.logged_in = True
                st.rerun()

elif st.session_state.empresa is None:
    st.markdown("<h2 style='text-align:center; padding: 2rem;'>Seleccione Unidad de Negocio</h2>", unsafe_allow_html=True)
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_CABLE}" width="200"><h3>Cable Móvil</h3><p>Soporte Técnico y Redes</p></div>', unsafe_allow_html=True)
        if st.button("Gestionar Cable Móvil"):
            st.session_state.empresa = "Cable Móvil"
            st.rerun()

else:

    with st.sidebar:
        st.image(LOGO_CABLE, width=150)
        st.divider()

        menu = st.radio(
            "NAVEGACIÓN",
            [
                "🏠 Inicio",
                "📅 Programación",
                "📋 Reporte Detallado",
                "👥 Personal",
                "🧩 Grupos"
            ]
        )

        st.divider()

        if st.button("🚪 Salir del Sistema"):
            st.session_state.empresa = None
            st.rerun()

    # =====================================================
    # ROUTER LIMPIO (CORREGIDO)
    # =====================================================

    if menu == "🏠 Inicio":
        modulo_inicio()

    elif menu == "📅 Programación":
        pantalla_programador()

    elif menu == "📋 Reporte Detallado":
        modulo_detallado()

    elif menu == "👥 Personal":
        modulo_personal()

    elif menu == "🧩 Grupos":
        pantalla_asignacion_grupos()
