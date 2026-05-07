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
    .card-empresa { text-align: center; padding: 2rem; background: white; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
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

def guardar_excel(df_nuevo, nombre_archivo, mensaje):
    repo = conectar_github()
    if not repo: return
    
    try:
        contents = repo.get_contents(nombre_archivo)
        df_previo = pd.read_excel(io.BytesIO(contents.decoded_content))
        df_previo['Fecha_Raw'] = pd.to_datetime(df_previo['Fecha_Raw'])
        
        # Combinar y eliminar duplicados priorizando lo nuevo
        df_final = pd.concat([df_previo, df_nuevo]).drop_duplicates(subset=['Grupo', 'Fecha_Raw'], keep='last')
        sha = contents.sha
    except:
        df_final = df_nuevo
        sha = None

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False)
    
    if sha:
        repo.update_file(nombre_archivo, mensaje, output.getvalue(), sha)
    else:
        repo.create_file(nombre_archivo, mensaje, output.getvalue())
    
    st.session_state.malla_generada = df_final

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
    return f'background-color: {bg}; color: {color}; font-weight: bold; text-align: center;'

def obtener_horario(turno):
    h = {"T1": ("06:00", "14:00"), "T2": ("14:00", "22:00"), "T3": ("22:00", "06:00"), "DESC": ("OFF", "OFF"), "COMP": ("OFF", "OFF")}
    return h.get(turno, ("OFF", "OFF"))

# --- 3. MÓDULOS ---

def modulo_programacion():
    st.header("📅 Programación Maestra y Validación")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    repo = conectar_github()

    # Filtros de Fecha
    with st.expander("🚀 Parámetros de Visualización y Generación", expanded=True):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Fecha Inicio", datetime.now().date())
        f_fin = c2.date_input("Fecha Fin", (datetime.now() + timedelta(days=28)).date())
        
        f_ini_dt = pd.to_datetime(f_ini)
        f_fin_dt = pd.to_datetime(f_fin)

        if st.button("Generar Nueva Malla Inteligente"):
            estado_ayer = obtener_ultimo_estado_github(repo)
            lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
            resultados = []
            mem_t = {g: estado_ayer[g]["u"] for g in grupos_n}
            mem_n = {g: estado_ayer[g]["n"] for g in grupos_n}
            deudas = {g: estado_ayer[g]["d"] for g in grupos_n}
            co_h = holidays.Colombia(years=[2024, 2025, 2026])

            for fecha in lista_fechas:
                fecha_dt = pd.to_datetime(fecha)
                dia_idx = fecha_dt.weekday()
                sem_iso = fecha_dt.isocalendar()[1]
                es_fest = fecha_dt in co_h
                col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

                libranza = None
                if dia_idx == 5: libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                elif dia_idx == 6: libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                else:
                    for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                        if deudas[g] > 0 and mem_t[g] != "T3": 
                            libranza = g; deudas[g] -= 1; break

                activos = [g for g in grupos_n if g != libranza]
                turnos_hoy = {}
                for g in activos:
                    idx_g = grupos_n.index(g)
                    t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                    if not es_cambio_saludable(mem_t[g], t_sug): t_sug = mem_t[g]
                    if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
                    turnos_hoy[g] = t_sug

                for g in grupos_n:
                    t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                    n_a = mem_n[g] + 1 if t_f == "T3" else 0
                    resultados.append({
                        "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                        "Fecha_Raw": fecha_dt, "Noches_Acum": n_a, "Deuda_Compensatorio": deudas[g]
                    })
                    mem_t[g] = t_f; mem_n[g] = n_a

            df_nueva_malla = pd.DataFrame(resultados)
            guardar_excel(df_nueva_malla, "malla_historica.xlsx", "Generación de Periodo")
            st.rerun()

    # Cargar y FILTRAR Data
    df_base = cargar_excel("malla_historica.xlsx")
    if not df_base.empty:
        # EL FILTRO CORRECTO:
        df_filtrada = df_base[(df_base['Fecha_Raw'] >= f_ini_dt) & (df_base['Fecha_Raw'] <= f_fin_dt)].copy()
        
        if not df_filtrada.empty:
            st.subheader("✍️ Editor de Turnos (Rango Seleccionado)")
            matriz = df_filtrada.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_filtrada["Fecha_Col"].unique())
            
            config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"], width="small") for c in matriz.columns}
            matriz_editada = st.data_editor(matriz, column_config=config_col, use_container_width=True)

            if st.button("💾 Guardar Cambios Manuales"):
                matriz_final = matriz.copy()
                matriz_final.update(matriz_editada)
                df_man = matriz_final.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
                df_final_upd = df_filtrada.drop(columns=['Turno']).merge(df_man, on=['Grupo', 'Fecha_Col'])
                guardar_excel(df_final_upd, "malla_historica.xlsx", "Ajuste Manual")
                st.success("Cambios aplicados correctamente.")
                st.rerun()
        else:
            st.info("No hay datos para las fechas seleccionadas. Usa 'Generar Nueva Malla'.")

def modulo_detallado():
    st.header("📋 Detallado por Técnico")
    df_m = cargar_excel("malla_historica.xlsx")
    df_e = cargar_excel("empleados.xlsx")
    if df_m.empty or df_e.empty: 
        st.warning("Faltan datos de malla o empleados.")
        return
    
    df_e["Grupo"] = df_e["Grupo"].astype(str)
    df_m["Grupo"] = df_m["Grupo"].astype(str)
    df_det = df_e.merge(df_m, on="Grupo")
    
    matriz_full = df_det.pivot_table(index=["Grupo", "Nombre"], columns="Fecha_Col", values="Turno", aggfunc='first').reindex(columns=df_m["Fecha_Col"].unique())
    st.dataframe(matriz_full.style.map(color_t), use_container_width=True)

def modulo_nomina():
    st.header("💰 Reporte para Nómina")
    df_m = cargar_excel("malla_historica.xlsx")
    df_e = cargar_excel("empleados.xlsx")
    if df_m.empty or df_e.empty: return
    
    df_nom = df_e.merge(df_m, on="Grupo")
    df_nom["Hora Inicio"], df_nom["Hora Fin"] = zip(*df_nom["Turno"].map(obtener_horario))
    reporte = df_nom[["Fecha_Raw", "Nombre", "Cedula", "Cargo", "Turno", "Hora Inicio", "Hora Fin"]].sort_values("Fecha_Raw")
    st.dataframe(reporte, use_container_width=True, hide_index=True)

def modulo_personal():
    st.header("👥 Gestión de Personal")
    df_emp = cargar_excel("empleados.xlsx")
    if df_emp.empty: df_emp = pd.DataFrame(columns=["Nombre", "Cedula", "Cargo", "Grupo"])
    
    df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic")
    if st.button("💾 Guardar Cambios en Personal"):
        guardar_excel(df_edit, "empleados.xlsx", "Update Personal")
        st.rerun()

# --- 4. FLUJO PRINCIPAL ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None
if 'malla_generada' not in st.session_state: st.session_state.malla_generada = None

if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(LOGO_APP, use_container_width=True)
        if st.button("Entrar"): 
            st.session_state.logged_in = True
            st.rerun()
elif st.session_state.empresa is None:
    _, c2, _ = st.columns([1, 1.5, 1])
    with c2:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_CABLE}" width="200"><h3>Cable Móvil</h3></div>', unsafe_allow_html=True)
        if st.button("Acceder a Operación"): 
            st.session_state.empresa = "Cable Móvil"
            st.rerun()
else:
    with st.sidebar:
        st.image(LOGO_CABLE, width=150)
        st.title("MovilGo")
        menu = st.radio("MENÚ", ["🏠 Inicio", "📅 Programación", "📋 Detallado", "💰 Nómina", "👥 Personal"])
        if st.button("🚪 Salir"): 
            st.session_state.clear()
            st.rerun()
    
    if menu == "🏠 Inicio":
        st.markdown(f'<div class="welcome-card"><h1>Operación {st.session_state.empresa}</h1><p>Gestión de turnos y personal técnico</p></div>', unsafe_allow_html=True)
    elif menu == "📅 Programación": modulo_programacion()
    elif menu == "📋 Detallado": modulo_detallado()
    elif menu == "💰 Nómina": modulo_nomina()
    elif menu == "👥 Personal": modulo_personal()
