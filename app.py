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

# --- ESTILOS CSS AVANZADOS Y CONTRASTES ---
PRIMARY_COLOR = "#1E3D59" 
st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; }}
    [data-testid="stSidebar"] * {{ color: white !important; font-weight: 500; }}
    .stButton>button {{ width: 100%; border-radius: 12px; font-weight: bold; height: 3em; transition: 0.3s; border: none; }}
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }}
    .stMetric {{ background-color: white; padding: 15px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); border: 1px solid #eee; }}
    .card-empresa {{
        background-color: white; padding: 25px; border-radius: 20px;
        text-align: center; border: 1px solid #eee; transition: 0.4s; height: 280px;
    }}
    .card-empresa:hover {{ transform: translateY(-8px); border-color: {PRIMARY_COLOR}; box-shadow: 0 15px 30px rgba(0,0,0,0.1); }}
    /* Ajuste de contraste para tablas */
    .stDataFrame {{ border-radius: 15px; overflow: hidden; border: 1px solid #e6e9ef; }}
    </style>
    """, unsafe_allow_html=True)

# --- 1. FUNCIONES DE CONEXIÓN Y DATOS ---

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
        return pd.read_excel(io.BytesIO(contents.decoded_content))
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
            df = pd.concat([df_previo, df]).drop_duplicates(subset=['Grupo', 'Fecha_Raw'], keep='last')
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
        repo.update_file(nombre_archivo, mensaje, output.getvalue(), contents.sha)
        st.success(f"✅ Datos sincronizados en GitHub.")
    except:
        repo.create_file(nombre_archivo, mensaje, output.getvalue())

def obtener_ultimo_estado_github(repo):
    try:
        df_hist = cargar_excel("malla_historica.xlsx")
        if df_hist.empty: return {g: {"u": "DESC", "n": 0, "d": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        df_hist['Fecha_Raw'] = pd.to_datetime(df_hist['Fecha_Raw'])
        estado = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            regs = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw', ascending=False)
            if not regs.empty:
                u = regs.iloc[0]
                estado[g] = {"u": u['Turno'], "n": int(u.get('Noches_Acum', 0)) if u['Turno'] == "T3" else 0, "d": int(u.get('Deuda_Compensatorio', 0))}
            else: estado[g] = {"u": "DESC", "n": 0, "d": 0}
        return estado
    except: return {g: {"u": "DESC", "n": 0, "d": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

# --- 2. LÓGICA DE NEGOCIO Y ESTILO DE TURNOS ---

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP", "OFF"] or hoy in ["DESC", "COMP", "OFF"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def color_t(val):
    # Colores con alto contraste y legibilidad
    c = {
        "T1": "#1f77b4", "T2": "#2ca02c", "T3": "#4d4d4d", 
        "DESC": "#d62728", "COMP": "#ff7f0e", "OFF": "#d62728"
    }
    bg = c.get(val, "#ffffff")
    color = "white" if val in c else "black"
    return f'background-color: {bg}; color: {color}; font-weight: bold; border: 1px solid #ffffff33; text-align: center;'

def obtener_horario(turno):
    h = {"T1": ("05:30", "12:50"), "T2": ("13:30", "20:50"), "T3": ("21:30", "28:50"), "DESC": ("OFF", "OFF"), "COMP": ("OFF", "OFF")}
    return h.get(turno, ("OFF", "OFF"))

# --- 3. MÓDULOS DEL MENÚ ---

def modulo_inicio():
    st.markdown(f'<div class="welcome-card"><h1>Panel de Control {st.session_state.empresa}</h1><p>Gestión de turnos saludable y equitativa.</p></div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    df_p = cargar_excel("empleados.xlsx")
    df_m = cargar_excel("malla_historica.xlsx")
    
    c1.metric("Técnicos Activos", len(df_p))
    c2.metric("Grupos Operativos", "4")
    c3.metric("Malla Generada", "Sincronizada" if not df_m.empty else "Pendiente")
    c4.metric("Versión", "V5.2 Pro")

def modulo_personal():
    st.header("👥 Gestión de Personal")
    df_emp = cargar_excel("empleados.xlsx")
    if df_emp.empty: df_emp = pd.DataFrame(columns=["Nombre", "Cargo", "Cedula", "Grupo"])
    
    tab1, tab2 = st.tabs(["📋 Base de Datos de Técnicos", "🛠️ Herramientas de Grupo"])
    with tab1:
        df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic", key="editor_p")
        if st.button("💾 Guardar y Sincronizar Personal"):
            guardar_excel(df_edit, "empleados.xlsx", "Update Personal")
            st.rerun()
    with tab2:
        st.info("Esta acción redistribuye al personal actual en los 4 grupos de trabajo de forma equitativa.")
        if st.button("🎲 Ejecutar Asignación Aleatoria"):
            grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"] * (len(df_edit)//4 + 1)
            random.shuffle(grupos)
            df_edit["Grupo"] = grupos[:len(df_edit)]
            guardar_excel(df_edit, "empleados.xlsx", "Update Grupos")
            st.rerun()

def modulo_programacion():
    st.header("📅 Programación Maestra (Por Grupos)")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    repo = conectar_github()

    with st.expander("🚀 Generar Nuevo Periodo", expanded=st.session_state.malla_generada is None):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Fecha Inicio", datetime.now())
        f_fin = c2.date_input("Fecha Fin", datetime.now() + timedelta(days=28))
        
        if st.button("Generar Malla Inteligente"):
            estado_ayer = obtener_ultimo_estado_github(repo)
            lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
            resultados = []
            mem_t = {g: estado_ayer[g]["u"] for g in grupos_n}
            mem_n = {g: estado_ayer[g]["n"] for g in grupos_n}
            deudas = {g: estado_ayer[g]["d"] for g in grupos_n}
            co_h = holidays.Colombia(years=[2024, 2025, 2026])

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
                    n_a = mem_n[g] + 1 if t_f == "T3" else 0
                    resultados.append({"Grupo": g, "Fecha_Col": col_name, "Turno": t_f, "Fecha_Raw": fecha_dt, "Noches_Acum": n_a, "Deuda_Compensatorio": deudas[g]})
                    mem_t[g] = t_f; mem_n[g] = n_a

            st.session_state.malla_generada = pd.DataFrame(resultados)
            guardar_excel(st.session_state.malla_generada, "malla_historica.xlsx", "Generación Base")
            st.rerun()

    if st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada.copy()
        df_res['Fecha_Raw'] = pd.to_datetime(df_res['Fecha_Raw'])
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_res["Fecha_Col"].unique())
        
        st.subheader("✍️ Editor de Turnos (Cualquier cambio aquí se reflejará en los Detallados)")
        fechas_sel = st.multiselect("Filtrar fechas específicas para ajustar:", options=list(matriz.columns))
        df_edit_view = matriz[fechas_sel] if fechas_sel else matriz
        config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"], width="small") for c in df_edit_view.columns}
        matriz_editada = st.data_editor(df_edit_view, column_config=config_col, use_container_width=True)

        if st.button("💾 Guardar y Aplicar Cambios Manuales"):
            matriz_final = matriz.copy(); matriz_final.update(matriz_editada)
            df_man = matriz_final.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
            df_final = df_res.drop(columns=['Turno']).merge(df_man, on=['Grupo', 'Fecha_Col'])
            st.session_state.malla_generada = df_final
            guardar_excel(df_final, "malla_historica.xlsx", "Ajuste Manual")
            st.rerun()

        # Centro de Corrección interactivo
        st.divider()
        st.subheader("🔍 Localizador de Novedades de Salud")
        alertas = []
        for g in grupos_n:
            h = df_res[df_res["Grupo"] == g].sort_values("Fecha_Raw").to_dict('records')
            for i in range(1, len(h)):
                if not es_cambio_saludable(h[i-1]['Turno'], h[i]['Turno']):
                    alertas.append({"msg": f"⚠️ {g}: Salto Prohibido {h[i-1]['Turno']} -> {h[i]['Turno']}", "grupo": g, "fecha": h[i]['Fecha_Col']})
        
        if alertas:
            sel_alerta = st.selectbox("Analizar falla detectada:", options=alertas, format_func=lambda x: f"{x['msg']} el {x['fecha']}")
            c1, c2 = st.columns([1, 2])
            c1.warning(f"Error en el **{sel_alerta['grupo']}**. Se recomienda intercambiar turnos en la fecha **{sel_alerta['fecha']}**.")
            c2.dataframe(df_res[df_res['Fecha_Col'] == sel_alerta['fecha']][['Grupo', 'Turno']].set_index('Grupo').T)
        else: st.success("✅ Rotación saludable perfecta en todos los grupos.")

def modulo_detallado():
    st.header("📋 Detallado Programación (Vista por Técnico)")
    
    # 1. FUENTE DE VERDAD ÚNICA: Priorizar siempre lo que está en memoria (sesión)
    if st.session_state.malla_generada is not None:
        df_m = st.session_state.malla_generada.copy()
    else:
        df_m = cargar_excel("malla_historica.xlsx")
        
    df_e = cargar_excel("empleados.xlsx")
    
    if df_m.empty or df_e.empty: 
        st.warning("⚠️ No hay datos. Por favor, genere la malla en el módulo de Programación.")
        return

    # Limpieza de datos para asegurar el cruce perfecto
    df_e["Grupo"] = df_e["Grupo"].astype(str).str.strip()
    df_m["Grupo"] = df_m["Grupo"].astype(str).str.strip()
    
    # 2. MÉTRICAS DINÁMICAS (Se actualizan con cada cambio en st.session_state)
    st.subheader("📊 Analítica de la Malla Actualizada")
    d1, d2 = st.columns([2, 1])
    
    with d1:
        # Conteo de turnos por grupo basado en la malla actual
        turnos_qty = df_m.groupby(["Grupo", "Turno"]).size().unstack(fill_value=0)
        st.write("**Distribución Total de Turnos:**")
        st.dataframe(turnos_qty, use_container_width=True)
        
    with d2:
        # Balance de Noches (T3) en tiempo real
        st.write("**Balance de Noches (T3):**")
        noches = df_m[df_m["Turno"] == "T3"].groupby("Grupo").size()
        if not noches.empty:
            st.bar_chart(noches)
        else:
            st.info("No hay turnos T3 asignados.")

    st.divider()
    
    # 3. MALLA ÚNICA FINAL (Cruce de Empleados + Malla de Programación)
    st.subheader("📝 Malla Individualizada (Espejo del Programador)")
    
    # Cruzamos los técnicos con la malla operativa
    df_det = df_e.merge(df_m, on="Grupo", how="inner")
    
    # Creamos la matriz final respetando el orden cronológico de las fechas
    orden_fechas = df_m["Fecha_Col"].unique()
    
    matriz_final = df_det.pivot_table(
        index=["Grupo", "Nombre"], 
        columns="Fecha_Col", 
        values="Turno", 
        aggfunc='first'
    ).reindex(columns=orden_fechas)
    
    # Aplicar estilos de colores y mostrar
    st.dataframe(matriz_final.style.map(color_t), use_container_width=True)

def modulo_nomina():
    st.header("💰 Módulo de Nómina")
    
    if st.session_state.malla_generada is not None:
        df_m = st.session_state.malla_generada.copy()
    else:
        df_m = cargar_excel("malla_historica.xlsx")
        
    df_e = cargar_excel("empleados.xlsx")
    
    if df_m.empty or df_e.empty: 
        st.error("No hay datos suficientes para generar el reporte.")
        return
    
    # Normalizar nombres de columnas
    df_e.columns = [c.replace('é', 'e').title() for c in df_e.columns]
    df_e["Grupo"] = df_e["Grupo"].astype(str).str.strip()
    df_m["Grupo"] = df_m["Grupo"].astype(str).str.strip()
    
    # Unir personal con sus turnos asignados
    df_nom = df_e.merge(df_m, on="Grupo", how="inner")
    
    # Asignar horas basadas en el turno final (el que se ve en pantalla)
    df_nom["Hora Inicio"], df_nom["Hora Fin"] = zip(*df_nom["Turno"].map(obtener_horario))
    df_nom["Fecha"] = pd.to_datetime(df_nom["Fecha_Raw"]).dt.date
    
    cols_finales = ["Fecha", "Nombre", "Cedula", "Cargo", "Grupo", "Turno", "Hora Inicio", "Hora Fin"]
    reporte = df_nom[cols_finales].sort_values(["Fecha", "Nombre"])
    
    st.dataframe(reporte, use_container_width=True, hide_index=True)
    
    csv = reporte.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Descargar Reporte CSV", csv, "nomina_movilgo.csv", "text/csv")
# --- 4. FLUJO DE NAVEGACIÓN PRINCIPAL ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None
if 'malla_generada' not in st.session_state: st.session_state.malla_generada = None

if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(LOGO_APP, use_container_width=True)
        st.markdown("<h2 style='text-align:center;'>Portal de Acceso MovilGo</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            user = st.text_input("Usuario Master")
            pw = st.text_input("Contraseña Operativa", type="password")
            if st.button("Iniciar Sesión"): st.session_state.logged_in = True; st.rerun()

elif st.session_state.empresa is None:
    st.markdown("<h2 style='text-align:center;'>Seleccione la Operación a Gestionar</h2>", unsafe_allow_html=True)
    _, c2, _ = st.columns([1, 1.5, 1])
    with c2:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_CABLE}"><h3>Cable Móvil</h3><p>Módulo de Gestión Saludable 24/7 ACTIVO</p></div>', unsafe_allow_html=True)
        if st.button("Ingresar a Cable Móvil"):
            st.session_state.empresa = "Cable Móvil"
            st.rerun()
else:
    # --- BARRA LATERAL OPERATIVA ---
    with st.sidebar:
        st.image(LOGO_CABLE, width=150)
        st.divider()
        menu = st.radio("MENÚ DE GESTIÓN", ["🏠 Inicio", "📅 Programación", "📋 Detallado Programación", "💰 Nómina", "👥 Personal"])
        st.divider()
        if st.button("🚪 Cerrar Operación"):
            st.session_state.empresa = None
            st.rerun()

    if menu == "🏠 Inicio": modulo_inicio()
    elif menu == "📅 Programación": modulo_programacion()
    elif menu == "📋 Detallado Programación": modulo_detallado()
    elif menu == "💰 Nómina": modulo_nomina()
    elif menu == "👥 Personal": modulo_personal()
