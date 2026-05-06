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
PRIMARY_COLOR = "#1E3D59"  # Azul profundo Cable Móvil

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
        text-align: center; border: 1px solid #eee; transition: 0.3s;
    }}
    .card-empresa:hover {{ transform: translateY(-5px); border-color: {PRIMARY_COLOR}; }}
    .card-empresa img {{ width: 100px; height: 100px; object-fit: contain; margin-bottom: 10px; }}
    </style>
    """, unsafe_allow_html=True)

# --- 1. FUNCIONES DE CONEXIÓN GITHUB ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ GITHUB_TOKEN no configurado en st.secrets")
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

def cargar_excel(nombre_archivo):
    repo = conectar_github()
    if not repo: return pd.DataFrame()
    try:
        contents = repo.get_contents(nombre_archivo)
        return pd.read_excel(io.BytesIO(contents.decoded_content))
    except:
        return pd.DataFrame()

def guardar_excel(df, nombre_archivo, mensaje):
    repo = conectar_github()
    if not repo: return
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    try:
        contents = repo.get_contents(nombre_archivo)
        repo.update_file(nombre_archivo, mensaje, output.getvalue(), contents.sha)
        st.success(f"✅ Sincronizado: {nombre_archivo}")
    except:
        repo.create_file(nombre_archivo, mensaje, output.getvalue())

# --- 2. LÓGICA DE PROGRAMACIÓN (CORE) ---

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP"] or hoy in ["DESC", "COMP"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
    return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold;'

# --- 3. MÓDULOS DE CABLE MÓVIL ---

def modulo_personal():
    st.header("👥 Gestión de Personal")
    df_emp = cargar_excel("empleados.xlsx")
    
    if df_emp.empty:
        df_emp = pd.DataFrame(columns=["Nombre", "Cargo", "Cédula", "Grupo"])
    
    tab1, tab2 = st.tabs(["📋 Base de Datos", "🛠️ Asignación de Grupos"])
    
    with tab1:
        st.write("Edita la información de los técnicos:")
        df_editado = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic", key="editor_personal")
        if st.button("💾 Guardar Cambios Personal"):
            guardar_excel(df_editado, "empleados.xlsx", "Update Personal")
            st.rerun()

    with tab2:
        st.subheader("Distribución de Grupos (1-4)")
        if st.button("🎲 Asignación Aleatoria Equitativa"):
            grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"] * (len(df_editado)//4 + 1)
            random.shuffle(grupos)
            df_editado["Grupo"] = grupos[:len(df_editado)]
            guardar_excel(df_editado, "empleados.xlsx", "Update Grupos Aleatorios")
            st.rerun()

def modulo_programacion():
    st.header("📅 Programación de Turnos 24/7")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    repo = conectar_github()
    
    with st.expander("⚙️ Generar Nueva Malla"):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Desde", datetime.now())
        f_fin = c2.date_input("Hasta", datetime.now() + timedelta(days=28))
        
        if st.button("🚀 Iniciar Motor de Programación"):
            # Obtener estado anterior
            estado_ayer = {}
            try:
                hist = cargar_excel("malla_historica.xlsx")
                hist['Fecha_Raw'] = pd.to_datetime(hist['Fecha_Raw'])
                for g in grupos_n:
                    regs = hist[hist['Grupo'] == g].sort_values('Fecha_Raw')
                    u = regs.iloc[-1] if not regs.empty else None
                    estado_ayer[g] = {"u": u['Turno'] if u is not None else "DESC", 
                                      "n": int(u['Noches_Acum']) if u is not None and u['Turno'] == "T3" else 0,
                                      "d": int(u['Deuda_Compensatorio']) if u is not None else 0}
            except:
                estado_ayer = {g: {"u": "DESC", "n": 0, "d": 0} for g in grupos_n}

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
                    resultados.append({"Grupo": g, "Fecha_Col": col_name, "Turno": t_f, "Fecha_Raw": fecha_dt, "Noches_Acum": n_a, "Deuda_Compensatorio": deudas[g]})
                    mem_t[g] = t_f; mem_n[g] = n_a

            st.session_state.malla_generada = pd.DataFrame(resultados)
            guardar_excel(st.session_state.malla_generada, "malla_historica.xlsx", "Nueva Malla")
            st.rerun()

    if st.session_state.malla_generada is not None:
        matriz = st.session_state.malla_generada.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=st.session_state.malla_generada["Fecha_Col"].unique())
        
        st.subheader("✍️ Editor Maestro")
        matriz_editada = st.data_editor(matriz.style.map(color_t), use_container_width=True)
        
        if st.button("💾 Guardar Cambios Manuales"):
            df_man = matriz_editada.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
            df_final = st.session_state.malla_generada.drop(columns=['Turno']).merge(df_man, on=['Grupo', 'Fecha_Col'])
            guardar_excel(df_final, "malla_historica.xlsx", "Ajuste Manual")
            st.session_state.malla_generada = df_final
            st.rerun()

# --- 4. NAVEGACIÓN Y VISTAS ---

def vista_login():
    _, col, _ = st.columns([1, 1.5, 1])
    with col:
        st.image(LOGO_APP, use_container_width=True)
        st.markdown("<h2 style='text-align:center;'>Acceso MovilGo</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            user = st.text_input("Usuario")
            pw = st.text_input("Contraseña", type="password")
            if st.button("Entrar"):
                st.session_state.logged_in = True
                st.rerun()

def vista_seleccion():
    st.markdown("<h2 style='text-align:center;'>Panel de Operaciones</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    
    with c2:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_CABLE}"><h3>Cable Móvil</h3><p>Estado: Activo</p></div>', unsafe_allow_html=True)
        if st.button("Gestionar Cable Móvil"):
            st.session_state.empresa = "Cable Móvil"
            st.rerun()
    
    with c1:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_GREEN}"><h3>Greenmovil</h3><p style="color:orange;">Próximamente</p></div>', unsafe_allow_html=True)
        st.button("Acceder", key="g1", disabled=True)

    with c3:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_BOGOTA}"><h3>Bogotá Móvil</h3><p style="color:orange;">Próximamente</p></div>', unsafe_allow_html=True)
        st.button("Acceder", key="b1", disabled=True)

# --- FLUJO PRINCIPAL ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None
if 'malla_generada' not in st.session_state: st.session_state.malla_generada = None

if not st.session_state.logged_in:
    vista_login()
elif st.session_state.empresa is None:
    vista_seleccion()
else:
    # INTERFAZ OPERATIVA DE EMPRESA
    with st.sidebar:
        st.image(LOGO_CABLE, width=150)
        st.markdown(f"**Operación:** {st.session_state.empresa}")
        st.divider()
        menu = st.radio("MENÚ", ["🏠 Inicio", "📅 Programación", "👥 Personal"])
        st.divider()
        if st.button("🚪 Salir"):
            st.session_state.empresa = None
            st.rerun()

    if menu == "🏠 Inicio":
        st.markdown(f'<div class="welcome-card"><h1>Bienvenido a {st.session_state.empresa}</h1><p>Sistema de gestión de turnos y talento humano.</p></div>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        df_p = cargar_excel("empleados.xlsx")
        col1.metric("Técnicos en Base", len(df_p))
        col2.metric("Grupos Activos", "4")

    elif menu == "📅 Programación":
        modulo_programacion()
    elif menu == "👥 Personal":
        modulo_personal()
