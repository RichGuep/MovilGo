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
LOGO_BOGOTA = f"{URL_BASE}logo_empresa_3.png" 
LOGO_GREEN = f"{URL_BASE}logo_empresa_1.png" 

# --- ESTILOS CSS PERSONALIZADOS ---
PRIMARY_COLOR = "#1E3D59" 

st.markdown(f"""
    <style>
    .main {{ background-color: #f4f7f9; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .stButton>button {{ width: 100%; border-radius: 10px; font-weight: bold; transition: 0.3s; }}
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2rem; border-radius: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }}
    .card-empresa {{
        background-color: white; padding: 20px; border-radius: 15px;
        text-align: center; border: 1px solid #eee; transition: 0.3s; height: 260px;
    }}
    .card-empresa:hover {{ transform: translateY(-5px); border-color: {PRIMARY_COLOR}; }}
    .card-empresa img {{ width: 100px; height: 100px; object-fit: contain; margin-bottom: 15px; }}
    </style>
    """, unsafe_allow_html=True)

# --- 1. FUNCIONES DE CONEXIÓN Y MEMORIA HISTÓRICA ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ GITHUB_TOKEN no configurado.")
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except:
        return None

def obtener_ultimo_estado_github(repo):
    """Recupera el último turno y contadores de la malla histórica para dar continuidad."""
    try:
        contents = repo.get_contents("malla_historica.xlsx")
        df_hist = pd.read_excel(io.BytesIO(contents.decoded_content))
        df_hist['Fecha_Raw'] = pd.to_datetime(df_hist['Fecha_Raw'])
        
        estado = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            # Filtramos por grupo y ordenamos por fecha descendente para tener el último día programado
            regs = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw', ascending=False)
            if not regs.empty:
                u = regs.iloc[0] # El registro más reciente
                estado[g] = {
                    "u": u['Turno'], 
                    "n": int(u.get('Noches_Acum', 0)) if u['Turno'] == "T3" else 0,
                    "d": int(u.get('Deuda_Compensatorio', 0))
                }
            else:
                estado[g] = {"u": "DESC", "n": 0, "d": 0}
        return estado
    except Exception as e:
        # Si el archivo no existe o falla, empezamos de cero
        return {g: {"u": "DESC", "n": 0, "d": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

def cargar_excel(nombre_archivo):
    repo = conectar_github()
    if not repo: return pd.DataFrame()
    try:
        contents = repo.get_contents(nombre_archivo)
        return pd.read_excel(io.BytesIO(contents.decoded_content))
    except:
        return pd.DataFrame()

def guardar_excel_historico(df_nueva):
    """Guarda la nueva malla unificándola con la histórica sin duplicados."""
    repo = conectar_github()
    if not repo: return
    try:
        try:
            contents = repo.get_contents("malla_historica.xlsx")
            df_previo = pd.read_excel(io.BytesIO(contents.decoded_content))
            # Combinamos y eliminamos duplicados basados en Grupo y Fecha exacta
            df_final = pd.concat([df_previo, df_nueva]).drop_duplicates(subset=['Grupo', 'Fecha_Raw'], keep='last')
        except:
            df_final = df_nueva

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        try:
            contents = repo.get_contents("malla_historica.xlsx")
            repo.update_file("malla_historica.xlsx", "Actualización Malla Continua", output.getvalue(), contents.sha)
        except:
            repo.create_file("malla_historica.xlsx", "Creación Malla Histórica", output.getvalue())
        st.success("✅ Histórico sincronizado en GitHub (Memoria de rotación guardada).")
    except Exception as e:
        st.error(f"Error al sincronizar: {e}")

# --- 2. LÓGICA DE SALUD ---

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP"] or hoy in ["DESC", "COMP"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
    return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

# --- 3. MÓDULOS OPERATIVOS ---

def modulo_personal():
    st.header("👥 Gestión de Personal")
    df_emp = cargar_excel("empleados.xlsx")
    if df_emp.empty:
        df_emp = pd.DataFrame(columns=["Nombre", "Cargo", "Cédula", "Grupo"])
    
    tab1, tab2 = st.tabs(["📋 Base de Datos", "🛠️ Asignación de Grupos"])
    with tab1:
        df_editado = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic", key="ed_pers")
        if st.button("💾 Guardar Cambios Personal"):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_editado.to_excel(writer, index=False)
            repo = conectar_github()
            try:
                contents = repo.get_contents("empleados.xlsx")
                repo.update_file("empleados.xlsx", "Update Personal", output.getvalue(), contents.sha)
                st.success("Personal actualizado.")
            except:
                repo.create_file("empleados.xlsx", "Creación Personal", output.getvalue())
            st.rerun()
            
    with tab2:
        if st.button("🎲 Repartir Grupos Aleatoriamente"):
            grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"] * (len(df_editado)//4 + 1)
            random.shuffle(grupos)
            df_editado["Grupo"] = grupos[:len(df_editado)]
            # Guardar automáticamente al repartir
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_editado.to_excel(writer, index=False)
            repo = conectar_github()
            contents = repo.get_contents("empleados.xlsx")
            repo.update_file("empleados.xlsx", "Reparto Grupos", output.getvalue(), contents.sha)
            st.rerun()

def modulo_programacion():
    st.header("📅 Programación Técnicos 24/7")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    repo = conectar_github()
    if not repo: return

    # 1. Configuración de fechas y Recuperación de memoria
    with st.expander("🚀 Generar Nueva Malla Base", expanded=st.session_state.malla_generada is None):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Inicio de periodo", datetime.now())
        f_fin = c2.date_input("Fin de periodo", datetime.now() + timedelta(days=28))
        
        if st.button("Generar Malla con Continuidad"):
            # AQUÍ RECUPERAMOS LA MEMORIA DEL MES ANTERIOR
            estado_ayer = obtener_ultimo_estado_github(repo)
            
            lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
            resultados = []
            
            # Inicializamos memoria de trabajo con lo recuperado de GitHub
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

                # Lógica de libranza legal
                libranza = None
                if dia_idx == 5: # Sáb
                    libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                    deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
                elif dia_idx == 6: # Dom
                    libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                    deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
                else:
                    # Cobro de compensatorios pendientes
                    for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                        if deudas[g] > 0 and mem_t[g] != "T3":
                            libranza = g; deudas[g] -= 1; break

                activos = [g for g in grupos_n if g != libranza]
                turnos_hoy = {}
                for g in activos:
                    idx_g = grupos_n.index(g)
                    t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                    
                    # Validamos contra el ayer (que puede venir de la memoria de GitHub)
                    if not es_cambio_saludable(mem_t[g], t_sug): t_sug = mem_t[g]
                    if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
                    turnos_hoy[g] = t_sug

                # Motor de Cobertura 24/7
                for tr in ["T1", "T2", "T3"]:
                    if tr not in turnos_hoy.values():
                        for gf in sorted(activos, key=lambda x: (mem_t[x] == "T3")):
                            if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                                if es_cambio_saludable(mem_t[gf], tr):
                                    turnos_hoy[gf] = tr; break
                
                for g in grupos_n:
                    t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                    n_a = mem_n[g] + 1 if t_f == "T3" else 0
                    resultados.append({
                        "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                        "Fecha_Raw": fecha_dt, "Noches_Acum": n_a, "Deuda_Compensatorio": deudas[g]
                    })
                    mem_t[g] = t_f; mem_n[g] = n_a

            st.session_state.malla_generada = pd.DataFrame(resultados)
            guardar_excel_historico(st.session_state.malla_generada)
            st.rerun()

    # 2. Editor Maestro y Diagnóstico
    if st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada.copy()
        df_res['Fecha_Raw'] = pd.to_datetime(df_res['Fecha_Raw'])
        
        st.subheader("✍️ Editor de Malla")
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())
        
        fechas_sel = st.multiselect("Filtrar fechas específicas para ajustar:", options=list(matriz.columns))
        df_edit_view = matriz[fechas_sel] if fechas_sel else matriz
        
        config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"], width="small") for c in df_edit_view.columns}
        matriz_editada = st.data_editor(df_edit_view, column_config=config_col, use_container_width=True)

        if st.button("💾 Aplicar y Sincronizar Cambios"):
            matriz_final = matriz.copy()
            matriz_final.update(matriz_editada)
            df_man = matriz_final.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
            df_final = df_res.drop(columns=['Turno']).merge(df_man, on=['Grupo', 'Fecha_Col'])
            st.session_state.malla_generada = df_final
            guardar_excel_historico(df_final)
            st.rerun()

        # Centro de Corrección interactivo
        st.divider()
        st.subheader("🔍 Localizador de Novedades de Salud")
        alertas = []
        for g in grupos_n:
            h = df_res[df_res["Grupo"] == g].sort_values("Fecha_Raw").to_dict('records')
            for i in range(1, len(h)):
                if not es_cambio_saludable(h[i-1]['Turno'], h[i]['Turno']):
                    alertas.append({"msg": f"⚠️ {g}: Salto Prohibido {h[i-1]['Turno']} -> {h[i]['Turno']}", "f": h[i]['Fecha_Col']})
        
        if alertas:
            st.error(f"Se detectaron {len(alertas)} errores de rotación.")
            sel = st.selectbox("Ver detalle de error:", options=alertas, format_func=lambda x: f"{x['msg']} el {x['f']}")
            st.dataframe(df_res[df_res['Fecha_Col'] == sel['f']][['Grupo', 'Turno']].set_index('Grupo').T)
        else:
            st.success("✅ Rotación saludable garantizada.")

        with st.expander("📊 Ver Mapa de Calor"):
            st.dataframe(matriz_editada.style.map(color_t), use_container_width=True)

# --- 5. NAVEGACIÓN ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None
if 'malla_generada' not in st.session_state: st.session_state.malla_generada = None

if not st.session_state.logged_in:
    # Vista de Login
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(LOGO_APP, use_container_width=True)
        st.markdown("<h2 style='text-align:center;'>Portal MovilGo</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            user = st.text_input("Usuario")
            pw = st.text_input("Clave", type="password")
            if st.button("Ingresar"):
                st.session_state.logged_in = True
                st.rerun()
elif st.session_state.empresa is None:
    # Selector de Empresas
    st.markdown("<h2 style='text-align:center;'>Panel de Operaciones</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c2:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_CABLE}"><h3>Cable Móvil</h3><p>Gestión de Malla 24/7</p></div>', unsafe_allow_html=True)
        if st.button("Acceder a Cable Móvil"):
            st.session_state.empresa = "Cable Móvil"
            st.rerun()
    with c1:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_GREEN}"><h3>Greenmovil</h3><p style="color:orange;">Próximamente</p></div>', unsafe_allow_html=True)
        st.button("No disponible", key="g1", disabled=True)
    with c3:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_BOGOTA}"><h3>Bogotá Móvil</h3><p style="color:orange;">Próximamente</p></div>', unsafe_allow_html=True)
        st.button("No disponible", key="b1", disabled=True)
else:
    # Panel Operativo
    with st.sidebar:
        st.image(LOGO_CABLE, width=150)
        st.divider()
        menu = st.radio("MENÚ", ["🏠 Inicio", "📅 Programación", "👥 Personal"])
        st.divider()
        if st.button("🚪 Cambiar Empresa"):
            st.session_state.empresa = None
            st.rerun()

    if menu == "🏠 Inicio":
        st.markdown(f'<div class="welcome-card"><h1>Bienvenido a {st.session_state.empresa}</h1><p>Sistema inteligente de continuidad operativa.</p></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        df_p = cargar_excel("empleados.xlsx")
        col1.metric("Técnicos Activos", len(df_p))
        col2.metric("Configuración", "Malla Saludable")
    elif menu == "📅 Programación":
        modulo_programacion()
    elif menu == "👥 Personal":
        modulo_personal()
