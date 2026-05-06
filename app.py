import streamlit as st
import pandas as pd
import io
import holidays
import random
from datetime import datetime, timedelta
from github import Github

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
    .stButton>button {{ width: 100%; border-radius: 12px; font-weight: bold; transition: 0.3s; }}
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px; margin-bottom: 2rem;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- 1. FUNCIONES DE CONEXIÓN Y DATOS (SINCRONIZACIÓN TOTAL) ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except: return None

def cargar_excel(nombre_archivo):
    # Priorizar la malla generada en la sesión actual si existe, para evitar desfases
    if nombre_archivo == "malla_historica.xlsx" and st.session_state.get('malla_generada') is not None:
        return st.session_state.malla_generada
        
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
        st.session_state.malla_generada = df # Actualizar sesión inmediatamente
    except:
        repo.create_file(nombre_archivo, mensaje, output.getvalue())
        st.session_state.malla_generada = df

def obtener_ultimo_estado_github(repo):
    df_hist = cargar_excel("malla_historica.xlsx")
    if df_hist.empty: return {g: {"u": "DESC", "n": 0, "d": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
    estado = {}
    for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
        regs = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw', ascending=False)
        if not regs.empty:
            u = regs.iloc[0]
            estado[g] = {"u": u['Turno'], "n": int(u.get('Noches_Acum', 0)), "d": int(u.get('Deuda_Compensatorio', 0))}
        else: estado[g] = {"u": "DESC", "n": 0, "d": 0}
    return estado

# --- 2. LÓGICA DE TURNOS ---

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP", "OFF"] or hoy in ["DESC", "COMP", "OFF"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#4d4d4d", "DESC": "#d62728", "COMP": "#ff7f0e"}
    bg = c.get(val, "#ffffff")
    color = "white" if val in c else "black"
    return f'background-color: {bg}; color: {color}; font-weight: bold; border: 1px solid #ffffff33; text-align: center;'

# --- 3. MÓDULOS ---

def modulo_programacion():
    st.header("📅 Programación Maestra")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    repo = conectar_github()

    with st.expander("🚀 Generar Nuevo Periodo", expanded=st.session_state.malla_generada is None):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Inicio", datetime.now())
        f_fin = c2.date_input("Fin", datetime.now() + timedelta(days=28))
        
        if st.button("Generar Malla Inteligente"):
            estado_ayer = obtener_ultimo_estado_github(repo)
            lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
            resultados = []
            mem_t = {g: estado_ayer[g]["u"] for g in grupos_n}; mem_n = {g: estado_ayer[g]["n"] for g in grupos_n}
            deudas = {g: estado_ayer[g]["d"] for g in grupos_n}; co_h = holidays.Colombia(years=[2024, 2025, 2026])

            for fecha in lista_fechas:
                fecha_dt = pd.to_datetime(fecha); dia_idx = fecha_dt.weekday(); sem_iso = fecha_dt.isocalendar()[1]
                es_fest = fecha_dt in co_h; col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

                libranza = None
                if dia_idx == 5: libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                elif dia_idx == 6: libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                else:
                    for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                        if deudas[g] > 0 and mem_t[g] != "T3": libranza = g; deudas[g] -= 1; break

                activos = [g for g in grupos_n if g != libranza]; turnos_hoy = {}
                for g in activos:
                    idx_g = grupos_n.index(g); t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                    if not es_cambio_saludable(mem_t[g], t_sug): t_sug = mem_t[g]
                    if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
                    turnos_hoy[g] = t_sug

                for tr in ["T1", "T2", "T3"]:
                    if tr not in turnos_hoy.values():
                        for gf in sorted(activos, key=lambda x: (mem_t[x] == "T3")):
                            if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                                if es_cambio_saludable(mem_t[gf], tr): turnos_hoy[gf] = tr; break
                
                for g in grupos_n:
                    t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                    resultados.append({"Grupo": g, "Fecha_Col": col_name, "Turno": t_f, "Fecha_Raw": fecha_dt, "Noches_Acum": mem_n[g]+1 if t_f=="T3" else 0, "Deuda_Compensatorio": deudas[g]})
                    mem_t[g] = t_f; mem_n[g] = mem_n[g]+1 if t_f=="T3" else 0

            st.session_state.malla_generada = pd.DataFrame(resultados)
            guardar_excel(st.session_state.malla_generada, "malla_historica.xlsx", "Generación Base")
            st.rerun()

    if st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada.copy()
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_res["Fecha_Col"].unique())
        st.subheader("✍️ Editor Maestro")
        matriz_editada = st.data_editor(matriz.style.map(color_t), use_container_width=True)
        if st.button("💾 Guardar Cambios"):
            df_man = matriz_editada.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
            df_final = df_res.drop(columns=['Turno']).merge(df_man, on=['Grupo', 'Fecha_Col'])
            guardar_excel(df_final, "malla_historica.xlsx", "Ajuste Manual")
            st.rerun()

def modulo_detallado():
    st.header("📋 Detallado Programación Integral")
    df_m = cargar_excel("malla_historica.xlsx")
    df_e = cargar_excel("empleados.xlsx")
    
    if df_m.empty or df_e.empty: 
        st.warning("No hay datos cargados."); return

    # Forzar mismos tipos para el cruce
    df_e["Grupo"] = df_e["Grupo"].astype(str)
    df_m["Grupo"] = df_m["Grupo"].astype(str)
    df_det = df_e.merge(df_m, on="Grupo")

    # Dashboard de Control
    st.subheader("📊 Métricas de Equidad")
    d1, d2, d3 = st.columns(3)
    d1.bar_chart(df_m[df_m["Turno"].isin(["DESC", "COMP"])].groupby("Grupo").size(), color="#d62728")
    d2.dataframe(df_m.groupby(["Grupo", "Turno"]).size().unstack(fill_value=0))
    d3.bar_chart(df_m[df_m["Turno"] == "T3"].groupby("Grupo").size(), color="#4d4d4d")

    st.divider()
    # Malla Detallada (Nombre vs Fecha)
    matriz_full = df_det.pivot_table(index=["Grupo", "Nombre"], columns="Fecha_Col", values="Turno", aggfunc='first').reindex(columns=df_m["Fecha_Col"].unique())
    st.dataframe(matriz_full.style.map(color_t), use_container_width=True)

def modulo_personal():
    st.header("👥 Personal")
    df_emp = cargar_excel("empleados.xlsx")
    df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic")
    if st.button("💾 Guardar Personal"):
        guardar_excel(df_edit, "empleados.xlsx", "Update Personal"); st.rerun()

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

# --- 4. NAVEGACIÓN ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None
if 'malla_generada' not in st.session_state: st.session_state.malla_generada = None

if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(LOGO_APP, use_container_width=True)
        if st.button("Entrar"): st.session_state.logged_in = True; st.rerun()
elif st.session_state.empresa is None:
    _, c2, _ = st.columns([1, 1.5, 1])
    with c2:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_CABLE}"><h3>Cable Móvil</h3></div>', unsafe_allow_html=True)
        if st.button("Acceder"): st.session_state.empresa = "Cable Móvil"; st.rerun()
else:
    with st.sidebar:
        st.image(LOGO_CABLE, width=150)
        menu = st.radio("MENÚ", ["🏠 Inicio", "📅 Programación", "📋 Detallado", "💰 Nómina", "👥 Personal"])
        if st.button("🚪 Salir"): st.session_state.empresa = None; st.rerun()
    if menu == "🏠 Inicio": modulo_inicio()
    elif menu == "📅 Programación": modulo_programacion()
    elif menu == "📋 Detallado": modulo_detallado()
    elif menu == "💰 Nómina": modulo_nomina()
    elif menu == "👥 Personal": modulo_personal()
