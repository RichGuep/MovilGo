import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# IMPORTANTE: Importamos la lógica personalizada
import logic 

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo - Gestión Operativa", layout="wide", initial_sidebar_state="expanded")

# --- URLs DE IMÁGENES ---
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
    .stButton>button {{ width: 100%; border-radius: 12px; font-weight: bold; transition: 0.3s; }}
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px; margin-bottom: 2rem;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 1. FUNCIONES DE CONEXIÓN (Persistencia) ---

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
        # Si es histórico, concatenamos en lugar de sobrescribir todo
        if nombre_archivo == "malla_historica.xlsx":
            try:
                df_previo = pd.read_excel(io.BytesIO(contents.decoded_content))
                df_previo['Fecha_Raw'] = pd.to_datetime(df_previo['Fecha_Raw'])
                df = pd.concat([df_previo, df]).drop_duplicates(subset=['Grupo', 'Fecha_Raw'], keep='last')
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
            except: pass
        repo.update_file(nombre_archivo, mensaje, output.getvalue(), contents.sha)
        st.session_state.malla_generada = df
    except:
        repo.create_file(nombre_archivo, mensaje, output.getvalue())

def obtener_ultimo_estado():
    repo = conectar_github()
    df_hist = cargar_excel("malla_historica.xlsx")
    grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    if df_hist.empty: 
        return {g: {"u": "DESC", "n": 0, "d": 0} for g in grupos}
    
    estado = {}
    for g in grupos:
        regs = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw', ascending=False)
        if not regs.empty:
            u = regs.iloc[0]
            estado[g] = {
                "u": u['Turno'], 
                "n": int(u.get('Noches_Acum', 0)), 
                "d": int(u.get('Deuda_Compensatorio', 0))
            }
        else: 
            estado[g] = {"u": "DESC", "n": 0, "d": 0}
    return estado

# --- 2. AYUDANTES DE VISTA ---

def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#4d4d4d", "DESC": "#d62728", "COMP": "#ff7f0e"}
    bg = c.get(val, "#ffffff")
    color = "white" if val in c else "black"
    return f'background-color: {bg}; color: {color}; font-weight: bold; text-align: center;'

# --- 3. MÓDULOS ---

def modulo_programacion():
    st.header("📅 Programación Maestra Balanceada")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    # --- SIDEBAR: Configuración de Descansos ---
    with st.sidebar:
        st.markdown("---")
        st.subheader("⚙️ Configuración de Descansos")
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        descansos_config = {}
        for g in grupos_n:
            def_idx = 5 if "1" in g or "2" in g else 6
            sel = st.selectbox(f"Día Descanso {g}", dias, index=def_idx, key=f"d_{g}")
            descansos_config[g] = dias.index(sel)

    # --- GENERACIÓN ---
    with st.expander("🚀 Generar Nuevo Escenario", expanded=st.session_state.malla_generada is None):
        col1, col2 = st.columns(2)
        f_ini = col1.date_input("Fecha Inicio", datetime.now())
        f_fin = col2.date_input("Fecha Fin", datetime.now() + timedelta(days=28))
        
        if st.button("🚀 Calcular Malla Óptima"):
            estado_ayer = obtener_ultimo_estado()
            # LLAMADA A LOGIC.PY
            df_nueva = logic.generar_malla_balanceada(f_ini, f_fin, estado_ayer, descansos_config)
            
            st.session_state.malla_generada = df_nueva
            guardar_excel(df_nueva, "malla_historica.xlsx", "Generación Malla Balanceada")
            st.rerun()

    # --- VISUALIZACIÓN Y AUDITORÍA ---
    if st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada.copy()
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_res["Fecha_Col"].unique())
        
        st.subheader("✍️ Editor y Vista Previa")
        config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"], width="small") for c in matriz.columns}
        matriz_editada = st.data_editor(matriz, column_config=config_col, use_container_width=True)

        if st.button("💾 Guardar Ajustes Manuales"):
            matriz_final = matriz.copy()
            matriz_final.update(matriz_editada)
            df_man = matriz_final.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
            df_final = df_res.drop(columns=['Turno']).merge(df_man, on=['Grupo', 'Fecha_Col'])
            guardar_excel(df_final, "malla_historica.xlsx", "Ajuste Manual en Malla")
            st.rerun()

        # --- SECCIÓN DE AUDITORÍA (Garantía de Ley y Equilibrio) ---
        st.divider()
        st.subheader("⚖️ Auditoría del Escenario")
        aud1, aud2 = st.columns(2)
        
        with aud1:
            st.write("**Equilibrio de Carga (Turnos por Grupo)**")
            conteo = df_res.groupby(['Grupo', 'Turno']).size().unstack(fill_value=0)
            st.dataframe(conteo, use_container_width=True)
            
        with aud2:
            st.write("**Validación de Descansos Semanales (Mínimo 1)**")
            df_res['Semana'] = df_res['Fecha_Raw'].dt.isocalendar().week
            desc_sem = df_res[df_res['Turno'].isin(['DESC', 'COMP'])].groupby(['Grupo', 'Semana']).size().unstack(fill_value=0)
            st.dataframe(desc_sem.style.map(lambda x: 'color: red; font-weight: bold' if x < 1 else 'color: green'), use_container_width=True)

def modulo_personal():
    st.header("👥 Gestión de Personal")
    df_emp = cargar_excel("empleados.xlsx")
    if not df_emp.empty:
        df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic")
        if st.button("💾 Actualizar Base de Datos"):
            guardar_excel(df_edit, "empleados.xlsx", "Update Personal")
            st.success("Personal actualizado.")

# --- 4. FLUJO PRINCIPAL ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None
if 'malla_generada' not in st.session_state: st.session_state.malla_generada = None

if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(LOGO_APP, use_container_width=True)
        if st.button("Entrar al Sistema"): 
            st.session_state.logged_in = True
            st.rerun()
elif st.session_state.empresa is None:
    _, c2, _ = st.columns([1, 1.5, 1])
    with c2:
        st.markdown(f'<div style="text-align:center"><img src="{LOGO_CABLE}" width="200"><h3>Cable Móvil</h3></div>', unsafe_allow_html=True)
        if st.button("Acceder a la Operación"): 
            st.session_state.empresa = "Cable Móvil"
            st.rerun()
else:
    with st.sidebar:
        st.image(LOGO_CABLE, width=150)
        menu = st.radio("MENÚ", ["🏠 Inicio", "📅 Programación", "👥 Personal", "🚪 Salir"])
    
    if menu == "🏠 Inicio":
        st.markdown(f'<div class="welcome-card"><h1>Operación {st.session_state.empresa}</h1><p>Gestión de Mallas Saludables y Auditoría de Ley</p></div>', unsafe_allow_html=True)
    elif menu == "📅 Programación": modulo_programacion()
    elif menu == "👥 Personal": modulo_personal()
    elif menu == "🚪 Salir":
        st.session_state.empresa = None
        st.session_state.logged_in = False
        st.rerun()
