import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from github import Github
from logic_programador import generar_malla_base, color_t, es_cambio_saludable # Importación crítica

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo - Gestión Operativa", layout="wide", initial_sidebar_state="expanded")

PRIMARY_COLOR = "#1E3D59"
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP, LOGO_GREEN = f"{URL_BASE}MovilGo.png", f"{URL_BASE}logo_empresa_1.png"
LOGO_CABLE, LOGO_BOGOTA = f"{URL_BASE}logo_empresa_2.png", f"{URL_BASE}logo_empresa_3.png"

st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .welcome-card {{ background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%); color: white; padding: 2rem; border-radius: 20px; }}
    .metric-card {{ background: white; padding: 15px; border-radius: 10px; border-left: 5px solid {PRIMARY_COLOR}; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
    .card-empresa {{ background: white; padding: 1.5rem; border-radius: 15px; text-align: center; border: 2px solid #eee; }}
    </style>
    """, unsafe_allow_html=True)

# --- PERSISTENCIA ---

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

def obtener_estado_anterior(repo, fecha_inicio):
    """Busca el estado de los grupos el día anterior a la fecha elegida."""
    df_hist = cargar_excel("malla_historica.xlsx")
    grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    if df_hist.empty: return {g: {"u": "DESC", "n": 0, "d": 0} for g in grupos}
    fecha_limite = pd.to_datetime(fecha_inicio)
    estado = {}
    for g in grupos:
        regs = df_hist[(df_hist['Grupo'] == g) & (df_hist['Fecha_Raw'] < fecha_limite)].sort_values('Fecha_Raw', ascending=False)
        if not regs.empty:
            u = regs.iloc[0]
            estado[g] = {"u": u['Turno'], "n": int(u.get('Noches_Acum', 0)), "d": int(u.get('Deuda_Compensatorio', 0))}
        else: estado[g] = {"u": "DESC", "n": 0, "d": 0}
    return estado

def guardar_excel(df_nuevo, nombre_archivo):
    repo = conectar_github()
    if not repo: return
    try:
        contents = repo.get_contents(nombre_archivo)
        df_previo = pd.read_excel(io.BytesIO(contents.decoded_content))
        df_previo['Fecha_Raw'] = pd.to_datetime(df_previo['Fecha_Raw'])
        # Limpiar solapamientos para que el filtro de inicio funcione
        fechas_nuevas = df_nuevo['Fecha_Raw'].unique()
        df_final = pd.concat([df_previo[~df_previo['Fecha_Raw'].isin(fechas_nuevas)], df_nuevo]).sort_values(['Fecha_Raw', 'Grupo'])
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer: df_final.to_excel(writer, index=False)
        repo.update_file(nombre_archivo, "Sync Malla", output.getvalue(), contents.sha)
    except:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer: df_nuevo.to_excel(writer, index=False)
        repo.create_file(nombre_archivo, "Init Malla", output.getvalue())

# --- MÓDULOS ---

def modulo_programacion():
    st.header("📅 Programación Maestra y Auditoría")
    repo = conectar_github()
    
    with st.expander("🚀 Generar Periodo", expanded=True):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Inicio", datetime(2026, 7, 1))
        f_fin = c2.date_input("Fin", datetime(2026, 7, 31))
        if st.button("Calcular Malla con Logic.py"):
            estado_previo = obtener_estado_anterior(repo, f_ini)
            df_resultado = generar_malla_base(f_ini, f_fin, estado_previo)
            guardar_excel(df_resultado, "malla_historica.xlsx")
            st.rerun()

    df_m = cargar_excel("malla_historica.xlsx")
    if not df_m.empty:
        df_view = df_m[(df_m['Fecha_Raw'] >= pd.to_datetime(f_ini)) & (df_m['Fecha_Raw'] <= pd.to_datetime(f_fin))]
        
        # Auditoría de Ley
        st.subheader(f"📊 Auditoría de Deuda ({f_ini.strftime('%B %Y')})")
        cols = st.columns(4)
        for i, g in enumerate(["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]):
            g_data = df_view[df_view["Grupo"] == g]
            deuda = g_data.iloc[-1]["Deuda_Compensatorio"] if not g_data.empty else 0
            cols[i].markdown(f'<div class="metric-card"><b>{g}</b><br><span style="color:{"red" if deuda > 0 else "green"}">Deuda: {deuda} días</span></div>', unsafe_allow_html=True)

        st.subheader("✍️ Editor Maestro")
        matriz = df_view.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_view.sort_values("Fecha_Raw")["Fecha_Col"].unique())
        matriz_editada = st.data_editor(matriz, use_container_width=True)
        if st.button("💾 Guardar Cambios Manuales"):
            df_edit = matriz_editada.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
            df_upd = df_view.drop(columns=['Turno']).merge(df_edit, on=['Grupo', 'Fecha_Col'])
            guardar_excel(df_upd, "malla_historica.xlsx"); st.rerun()

        # Localizador de Alertas
        alertas = []
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            h = df_m[df_m["Grupo"] == g].sort_values("Fecha_Raw").to_dict('records')
            for i in range(1, len(h)):
                if h[i]['Fecha_Raw'] >= pd.to_datetime(f_ini) and h[i]['Fecha_Raw'] <= pd.to_datetime(f_fin):
                    if not es_cambio_saludable(h[i-1]['Turno'], h[i]['Turno']):
                        alertas.append(f"⚠️ {g}: Salto Prohibido {h[i-1]['Turno']} -> {h[i]['Turno']} el {h[i]['Fecha_Col']}")
        for a in alertas: st.error(a)

def modulo_detallado():
    st.header("📋 Detallado por Técnico")
    df_m, df_e = cargar_excel("malla_historica.xlsx"), cargar_excel("empleados.xlsx")
    if not df_m.empty and not df_e.empty:
        df_det = df_e.merge(df_m, on="Grupo")
        matriz = df_det.pivot_table(index=["Grupo", "Nombre"], columns="Fecha_Col", values="Turno", aggfunc='first')
        st.dataframe(matriz.style.applymap(color_t), use_container_width=True)

def modulo_nomina():
    st.header("💰 Reporte de Nómina")
    df_m, df_e = cargar_excel("malla_historica.xlsx"), cargar_excel("empleados.xlsx")
    if not df_m.empty and not df_e.empty:
        df_nom = df_e.merge(df_m, on="Grupo")
        st.dataframe(df_nom[["Fecha_Raw", "Nombre", "Cedula", "Grupo", "Turno"]], use_container_width=True)

def modulo_personal():
    st.header("👥 Gestión de Personal")
    df_emp = cargar_excel("empleados.xlsx")
    df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic")
    if st.button("💾 Guardar Cambios"): guardar_excel(df_edit, "empleados.xlsx"); st.rerun()

# --- FLUJO PRINCIPAL ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None

if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(LOGO_APP, use_container_width=True)
        u, p = st.text_input("Usuario"), st.text_input("Clave", type="password")
        if st.button("Entrar"):
            if u != "" and p != "": st.session_state.logged_in = True; st.rerun()
elif st.session_state.empresa is None:
    st.markdown("<h2 style='text-align: center;'>Seleccione Operación</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_GREEN}" width="100"><br>Greenmóvil</div>', unsafe_allow_html=True)
        if st.button("Acceder Greenmóvil"): st.session_state.empresa, st.session_state.logo_actual = "Greenmóvil", LOGO_GREEN; st.rerun()
    with c2:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_CABLE}" width="100"><br>Cable Móvil</div>', unsafe_allow_html=True)
        if st.button("Acceder Cable Móvil"): st.session_state.empresa, st.session_state.logo_actual = "Cable Móvil", LOGO_CABLE; st.rerun()
    with c3:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_BOGOTA}" width="100"><br>BogotáMóvil</div>', unsafe_allow_html=True)
        if st.button("Acceder BogotáMóvil"): st.session_state.empresa, st.session_state.logo_actual = "BogotáMóvil", LOGO_BOGOTA; st.rerun()
else:
    with st.sidebar:
        st.image(st.session_state.logo_actual, width=150)
        st.divider(); menu = st.radio("MENÚ", ["🏠 Inicio", "📅 Programación", "📋 Detallado", "💰 Nómina", "👥 Personal"])
        if st.button("🚪 Salir"): st.session_state.empresa = None; st.rerun()
    
    if menu == "🏠 Inicio": st.markdown(f'<div class="welcome-card"><h1>{st.session_state.empresa}</h1><p>MovilGo v2.0</p></div>', unsafe_allow_html=True)
    elif menu == "📅 Programación": modulo_programacion()
    elif menu == "📋 Detallado": modulo_detallado()
    elif menu == "💰 Nómina": modulo_nomina()
    elif menu == "👥 Personal": modulo_personal()
