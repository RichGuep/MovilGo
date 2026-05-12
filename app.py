import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta, date
import holidays
from github import Github

# =========================================================
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS
# =========================================================
st.set_page_config(page_title="MovilGo - Gestión Operativa 24/7", layout="wide", initial_sidebar_state="expanded")

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()

# Estructuras de Personal
GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
GRUPOS_ABO = ["Abordaje G1", "Abordaje G2", "Abordaje G3", "Abordaje G4", "Abordaje G5"]
PERSONAL_ABO = {g: [f"Abordaje {g[-2:]}-{i+1:02d}" for i in range(5)] for g in GRUPOS_ABO}
OPCIONES_TURNOS = ["T1", "T2", "T3", "RELEVO", "DISPONIBLE", "T1 APOYO", "DESCANSO", "COMPENSADO"]

PRIMARY_COLOR = "#1E3D59" 
st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px; margin-bottom: 2rem;
    }}
    .stMetric {{ background-color: white; padding: 20px; border-radius: 15px; border: 1px solid #eee; }}
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# 2. FUNCIONES DE CONECTIVIDAD (GITHUB)
# =========================================================
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

def guardar_github(df, nombre_archivo):
    repo = conectar_github()
    if not repo: return
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    try:
        file = repo.get_contents(nombre_archivo)
        repo.update_file(nombre_archivo, f"Update {datetime.now()}", buffer.getvalue(), file.sha)
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())

# =========================================================
# 3. LÓGICAS DE GENERACIÓN Y ESTILO
# =========================================================
def style_malla(df_pivot):
    colores = {"T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8", "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED", "T1 APOYO": "#EBF5FB", "DESCANSO": "#2C3E50", "COMPENSADO": "#FDEBD0"}
    def apply_styles(val):
        bg = colores.get(val, "")
        txt = "white" if val == "DESCANSO" else "black"
        return f'background-color: {bg}; color: {txt}' if bg else ''
    return df_pivot.style.map(apply_styles)

def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_comp = {g: 0 for g in GRUPOS_TEC}
    u_turno = {g: "DESCANSO" for g in GRUPOS_TEC}
    c_bloque = {g: 0 for g in GRUPOS_TEC}
    conflictos = {dia: [g for g, d in descansos_ley.items() if d == dia] for dia in DIAS_ES}

    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday(); dia_nombre = DIAS_ES[dia_idx]; sem_num = fecha.isocalendar()[1]; asignados = {}
        gps_dia = conflictos[dia_nombre]
        if len(gps_dia) > 1:
            idx = sem_num % len(gps_dia); descansador = gps_dia[idx]; asignados[descansador] = "DESCANSO"
            for g in gps_dia: 
                if g != descansador: deudas_comp[g] += 1
        elif len(gps_dia) == 1: asignados[gps_dia[0]] = "DESCANSO"
        
        activos = [g for g in GRUPOS_TEC if g not in asignados]
        if 0 <= dia_idx <= 4 and len(asignados) == 0:
            cands_comp = sorted(activos, key=lambda x: deudas_comp[x], reverse=True)
            if cands_comp and deudas_comp[cands_comp[0]] > 0:
                sel = cands_comp[0]; asignados[sel] = "COMPENSADO"; deudas_comp[sel] -= 1; activos.remove(sel)

        for t in ["T3", "T2", "T1"]:
            for g in activos[:]:
                if u_turno[g] == t and c_bloque[g] < 4: asignados[g] = t; c_bloque[g] += 1; activos.remove(g)
            if t not in asignados.values() and activos:
                posibles = [g for g in activos if not (t in ["T1", "T2"] and u_turno[g] == "T3")]
                sel = posibles[0] if posibles else activos[0]
                asignados[sel] = t; u_turno[sel] = t; c_bloque[sel] = 1; activos.remove(sel)
        for g in activos:
            asignados[g] = "DESCANSO" if u_turno[g] == "T3" else "T1 APOYO"
            c_bloque[g] = 0
        for g in GRUPOS_TEC:
            u_turno[g] = asignados.get(g, "T1 APOYO"); filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignados.get(g, "T1 APOYO"), "Deuda_Compensatorio": deudas_comp[g]})
    return pd.DataFrame(filas)

# =========================================================
# 4. MÓDULOS DE INTERFAZ
# =========================================================

def modulo_inicio():
    st.markdown(f'<div class="welcome-card"><h1>Panel de Control Cable Móvil</h1><p>Garantizando cobertura T1, T2 y T3 con equidad laboral.</p></div>', unsafe_allow_html=True)
    
    df_p = cargar_excel("empleados.xlsx")
    df_m = cargar_excel("malla_historica.xlsx")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Técnicos Totales", len(df_p) if not df_p.empty else "73")
    c2.metric("Grupos Operativos", "4")
    
    # Validación segura para evitar KeyError
    deuda = int(df_m['Deuda_Compensatorio'].sum()) if (not df_m.empty and 'Deuda_Compensatorio' in df_m.columns) else 0
    c3.metric("Deuda Global Descansos", f"{deuda} días")
    c4.metric("Estado de Red", "24/7 Activo", delta="Estable")

    st.divider()
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.subheader("🛠️ Reglas Técnicas")
        st.write("- **Exclusión:** Solo 1 grupo fuera por día.\n- **Viceversa:** Alternancia en días compartidos.\n- **Salud:** Prohibido T3 ➔ Mañana.")
    with col_r2:
        st.subheader("👔 Reglas Abordaje")
        st.write("- **Bloques:** Grupos de 5 rotan juntos.\n- **Cuotas:** 10 T1, 10 T2 fijos.\n- **Apoyo:** 1 Relevo por ciclo.")

def modulo_programacion():
    tipo = st.sidebar.radio("Sección", ["Técnicos", "Abordaje"])
    st.header(f"📅 Programación: {tipo}")
    
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Desde", date.today())
    fin = c2.date_input("Hasta", date.today() + timedelta(days=30))

    descansos = {}
    if tipo == "Técnicos":
        cols = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC): descansos[g] = cols[i].selectbox(f"{g}", DIAS_ES, index=(5 if i<2 else 6))
        if st.button("🚀 Generar Malla"):
            df = generar_malla_tecnicos(inicio, fin, descansos)
            st.session_state.malla_actual = df

    if "malla_actual" in st.session_state:
        df_v = st.session_state.malla_actual.copy()
        df_v["Label"] = df_v["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} - {x.strftime('%Y-%m-%d')}")
        pivot = df_v.pivot(index="Sujeto", columns="Label", values="Turno")
        
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True)
        
        if st.button("💾 Guardar"):
            df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
            guardar_github(df_final, "malla_historica.xlsx")
            st.success("Sincronizado con éxito")

# =========================================================
# 5. FLUJO PRINCIPAL (LOGIN Y NAVEGACIÓN)
# =========================================================
if 'logged_in' not in st.session_state: st.session_state.logged_in = False

if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.title("Acceso MovilGo")
        user = st.text_input("Usuario")
        pw = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            st.session_state.logged_in = True
            st.rerun()
else:
    menu = st.sidebar.radio("NAVEGACIÓN", ["🏠 Inicio", "📅 Programación", "📋 Reporte Detallado", "👥 Personal"])
    
    if menu == "🏠 Inicio": modulo_inicio()
    elif menu == "📅 Programación": modulo_programacion()
    elif menu == "👥 Personal": st.info("Módulo de personal en mantenimiento")
    elif menu == "📋 Reporte Detallado": st.info("Módulo de reportes en mantenimiento")

    if st.sidebar.button("🚪 Salir"):
        st.session_state.logged_in = False
        st.rerun()
