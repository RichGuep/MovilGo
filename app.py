import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo - Gestión Operativa", layout="wide", initial_sidebar_state="expanded")

# --- URLs DE IMÁGENES GITHUB ---
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGO_GREEN = f"{URL_BASE}logo_empresa_1.png"
LOGO_CABLE = f"{URL_BASE}logo_empresa_2.png"
LOGO_BOGOTA = f"{URL_BASE}logo_empresa_3.png"

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
    .card-empresa {{
        background: white; padding: 1.5rem; border-radius: 15px; text-align: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 2px solid #eee; margin-bottom: 10px;
    }}
    .card-empresa img {{ height: 80px; margin-bottom: 10px; }}
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

def obtener_estado_continuidad(repo, fecha_inicio):
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
        else:
            estado[g] = {"u": "DESC", "n": 0, "d": 0}
    return estado

def guardar_excel(df_nuevo, nombre_archivo, mensaje):
    repo = conectar_github()
    if not repo: return
    try:
        contents = repo.get_contents(nombre_archivo)
        df_previo = pd.read_excel(io.BytesIO(contents.decoded_content))
        df_previo['Fecha_Raw'] = pd.to_datetime(df_previo['Fecha_Raw'])
        if nombre_archivo == "malla_historica.xlsx":
            fechas_nuevas = df_nuevo['Fecha_Raw'].unique()
            df_limpio = df_previo[~df_previo['Fecha_Raw'].isin(fechas_nuevas)]
            df_final = pd.concat([df_limpio, df_nuevo]).sort_values(['Fecha_Raw', 'Grupo'])
        else:
            df_final = df_nuevo
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        repo.update_file(nombre_archivo, mensaje, output.getvalue(), contents.sha)
        st.session_state.malla_generada = df_final
    except:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_nuevo.to_excel(writer, index=False)
        repo.create_file(nombre_archivo, mensaje, output.getvalue())
        st.session_state.malla_generada = df_nuevo

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
    h = {"T1": ("06:00", "14:00"), "T2": ("14:00", "22:00"), "T3": ("22:00", "06:00")}
    return h.get(turno, ("OFF", "OFF"))

# --- 3. MÓDULOS ---

def modulo_programacion():
    st.header("📅 Programación Maestra y Alertas")
    repo = conectar_github()
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]

    with st.expander("🚀 Generar Nuevo Periodo", expanded=True):
        c1, c2 = st.columns(2)
        f_ini_sel = c1.date_input("Fecha Inicio", datetime(2026, 7, 1))
        f_fin_sel = c2.date_input("Fecha Fin", datetime(2026, 7, 31))
        
        if st.button("Generar Malla Inteligente"):
            estado_ayer = obtener_estado_continuidad(repo, f_ini_sel)
            lista_fechas = [f_ini_sel + timedelta(days=x) for x in range((f_fin_sel - f_ini_sel).days + 1)]
            resultados = []
            mem_t, mem_n, deudas = {g: estado_ayer[g]["u"] for g in grupos_n}, {g: estado_ayer[g]["n"] for g in grupos_n}, {g: estado_ayer[g]["d"] for g in grupos_n}
            co_h = holidays.Colombia(years=[2026])

            for fecha in lista_fechas:
                fecha_dt = pd.to_datetime(fecha); dia_idx, sem_iso = fecha_dt.weekday(), fecha_dt.isocalendar()[1]
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
                        for gf in activos:
                            if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                                if es_cambio_saludable(mem_t[gf], tr): turnos_hoy[gf] = tr; break
                for g in grupos_n:
                    t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                    n_a = mem_n[g] + 1 if t_f == "T3" else 0
                    resultados.append({"Grupo": g, "Fecha_Col": col_name, "Turno": t_f, "Fecha_Raw": fecha_dt, "Noches_Acum": n_a, "Deuda_Compensatorio": deudas[g]})
                    mem_t[g], mem_n[g] = t_f, n_a

            df_final = pd.DataFrame(resultados)
            guardar_excel(df_final, "malla_historica.xlsx", "Generación Julio")
            st.rerun()

    # --- EDITOR MAESTRO ---
    df_m = cargar_excel("malla_historica.xlsx")
    if not df_m.empty:
        st.subheader("✍️ Editor Maestro (Vista Filtrada)")
        df_filtrado = df_m[(df_m['Fecha_Raw'] >= pd.to_datetime(f_ini_sel)) & (df_m['Fecha_Raw'] <= pd.to_datetime(f_fin_sel))]
        
        if not df_filtrado.empty:
            matriz = df_filtrado.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_filtrado.sort_values("Fecha_Raw")["Fecha_Col"].unique())
            config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"], width="small") for c in matriz.columns}
            matriz_editada = st.data_editor(matriz, column_config=config_col, use_container_width=True)
            
            if st.button("💾 Guardar Cambios Manuales"):
                df_edit = matriz_editada.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
                df_update = df_filtrado.drop(columns=['Turno']).merge(df_edit, on=['Grupo', 'Fecha_Col'])
                guardar_excel(df_update, "malla_historica.xlsx", "Ajuste Manual")
                st.rerun()

            # --- DETECTOR DE ALERTAS DE SALUD ---
            st.divider()
            st.subheader("🔍 Localizador de Novedades de Salud")
            alertas = []
            for g in grupos_n:
                # Traemos el historial completo del grupo para validar cambios entre el fin de junio y el inicio de julio
                h = df_m[df_m["Grupo"] == g].sort_values("Fecha_Raw").to_dict('records')
                for i in range(1, len(h)):
                    # Solo reportar alertas que caigan dentro del rango que estamos viendo
                    if h[i]['Fecha_Raw'] >= pd.to_datetime(f_ini_sel) and h[i]['Fecha_Raw'] <= pd.to_datetime(f_fin_sel):
                        if not es_cambio_saludable(h[i-1]['Turno'], h[i]['Turno']):
                            alertas.append({"msg": f"⚠️ {g}: Salto Prohibido {h[i-1]['Turno']} -> {h[i]['Turno']}", "f": h[i]['Fecha_Col']})
            
            if alertas:
                for a in alertas:
                    st.error(f"{a['msg']} el día **{a['f']}**")
            else:
                st.success("✅ No se detectan conflictos de salud en los turnos.")

def modulo_detallado():
    st.header("📋 Detallado por Técnico")
    df_m = cargar_excel("malla_historica.xlsx"); df_e = cargar_excel("empleados.xlsx")
    if df_m.empty or df_e.empty: return
    df_det = df_e.merge(df_m, on="Grupo")
    matriz_full = df_det.pivot_table(index=["Grupo", "Nombre"], columns="Fecha_Col", values="Turno", aggfunc='first')
    st.dataframe(matriz_full.style.map(color_t), use_container_width=True)

def modulo_nomina():
    st.header("💰 Nómina")
    df_m = cargar_excel("malla_historica.xlsx"); df_e = cargar_excel("empleados.xlsx")
    if df_m.empty or df_e.empty: return
    df_nom = df_e.merge(df_m, on="Grupo")
    df_nom["Hora Inicio"], df_nom["Hora Fin"] = zip(*df_nom["Turno"].map(obtener_horario))
    st.dataframe(df_nom[["Fecha_Raw", "Nombre", "Cedula", "Grupo", "Turno", "Hora Inicio", "Hora Fin"]], use_container_width=True)

def modulo_personal():
    st.header("👥 Personal")
    df_emp = cargar_excel("empleados.xlsx")
    df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic")
    if st.button("💾 Guardar Personal"):
        guardar_excel(df_edit, "empleados.xlsx", "Update Personal"); st.rerun()

# --- 4. FLUJO PRINCIPAL ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None
if 'logo_actual' not in st.session_state: st.session_state.logo_actual = None

if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(LOGO_APP, use_container_width=True)
        user = st.text_input("Usuario")
        passw = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            if user != "" and passw != "": st.session_state.logged_in = True; st.rerun()

elif st.session_state.empresa is None:
    st.markdown("<h2 style='text-align: center;'>Seleccione su Operación</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_GREEN}"><h3>Greenmóvil</h3></div>', unsafe_allow_html=True)
        if st.button("Acceder Greenmóvil"): st.session_state.empresa, st.session_state.logo_actual = "Greenmóvil", LOGO_GREEN; st.rerun()
    with c2:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_CABLE}"><h3>Cable Móvil</h3></div>', unsafe_allow_html=True)
        if st.button("Acceder Cable Móvil"): st.session_state.empresa, st.session_state.logo_actual = "Cable Móvil", LOGO_CABLE; st.rerun()
    with c3:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_BOGOTA}"><h3>BogotáMóvil</h3></div>', unsafe_allow_html=True)
        if st.button("Acceder BogotáMóvil"): st.session_state.empresa, st.session_state.logo_actual = "BogotáMóvil", LOGO_BOGOTA; st.rerun()

else:
    with st.sidebar:
        st.image(st.session_state.logo_actual, width=150)
        st.markdown(f"**Operación:** {st.session_state.empresa}")
        st.divider()
        menu = st.radio("MENÚ", ["🏠 Inicio", "📅 Programación", "📋 Detallado", "💰 Nómina", "👥 Personal"])
        if st.button("🚪 Salir"): st.session_state.empresa = None; st.rerun()
    
    if menu == "🏠 Inicio":
        st.markdown(f'<div class="welcome-card"><h1>Operación {st.session_state.empresa}</h1><p>Sistema MovilGo v2.0</p></div>', unsafe_allow_html=True)
    elif menu == "📅 Programación": modulo_programacion()
    elif menu == "📋 Detallado": modulo_detallado()
    elif menu == "💰 Nómina": modulo_nomina()
    elif menu == "👥 Personal": modulo_personal()
