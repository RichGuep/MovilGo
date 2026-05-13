import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date, time
import holidays
import io
from github import Github

# =========================================================
# 1. CONFIGURACIÓN, CONSTANTES Y ESTILOS
# =========================================================
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()
GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8",
    "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "T1 APOYO": "#EBF5FB", "DESCANSO": "#1B2631", "COMPENSADO": "#2E4053"
}

def style_malla(df_pivot):
    """Aplica el formato visual de celdas según el turno."""
    def apply_styles(val):
        key = val if val and str(val).strip() != "" else "DESCANSO"
        bg = COLORES_MAP.get(key, "#1B2631")
        txt = "white" if key in ["DESCANSO", "COMPENSADO"] else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB'
    return df_pivot.style.map(apply_styles)

# =========================================================
# 2. FUNCIONES DE CONECTIVIDAD Y APOYO
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
        st.toast(f"✅ Sincronizado correctamente.")
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())

def calcular_horas_turno(turno_val):
    """
    REGLA ACTUALIZADA:
    Turnos de 7 horas: T1, T2, T3, RELEVO, T1 APOYO, DISPONIBLE.
    Turnos de 0 horas: DESCANSO, COMPENSADO.
    """
    if turno_val in ["DESCANSO", "COMPENSADO", "OFF", None]: 
        return 0.0
    return 7.0

def obtener_tipo_dia(fecha):
    if fecha in festivos_co: return "Festivo"
    return "Sábado" if fecha.weekday() == 5 else "Domingo" if fecha.weekday() == 6 else "Hábil"

# =========================================================
# 3. GESTIÓN DE PERSONAL
# =========================================================
def asignar_grupos_automatico(df):
    df = df.copy()
    if 'GrupoAsignado' in df.columns: df = df.drop(columns=['GrupoAsignado'])
    m = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    ta = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    tb = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).reset_index(drop=True)
    res = []
    for i, g in enumerate(GRUPOS_TEC):
        temp_m = m.iloc[i*2:(i+1)*2].copy(); temp_m['GrupoAsignado'] = g
        temp_ta = ta.iloc[i*7:(i+1)*7].copy(); temp_ta['GrupoAsignado'] = g
        temp_tb = tb.iloc[i*3:(i+1)*3].copy(); temp_tb['GrupoAsignado'] = g
        res.extend([temp_m, temp_ta, temp_tb])
    abo = df[df['Cargo'].str.contains('Abordaje|Auxiliar', case=False, na=False)].copy()
    abo['GrupoAsignado'] = "Abordaje"
    res.append(abo)
    return pd.concat(res).reset_index(drop=True)

def pantalla_personal():
    st.subheader("👥 Gestión de Plantilla Operativa")
    if st.button("📥 Importar empleados.xlsx"):
        df = cargar_excel("empleados.xlsx")
        if not df.empty: st.session_state.df_pers = df; st.success("Personal cargado.")
    
    if 'df_pers' in st.session_state:
        if st.button("🎲 Ejecutar Clasificación de Grupos"):
            st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers)
        if 'df_pers_ready' in st.session_state:
            df_edit = st.data_editor(st.session_state.df_pers_ready, use_container_width=True)
            if st.button("💾 Guardar Estructura"):
                guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTOR ABORDAJE (DISPONIBLE = 7H | 42H SEMANALES)
# =========================================================
def generar_malla_abordaje_individual(inicio, fin, descansos_elegidos):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    personal = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]['Nombre'].tolist()[:27]
    grupo_a, grupo_b = personal[:13], personal[13:]
    
    filas = []
    cola_compensados_semanal = [] 
    desc_real_mes = {p: 0 for p in personal}

    for fecha in pd.date_range(inicio, fin):
        dia_n, asig, cupo_fuera = DIAS_ES[fecha.weekday()], {}, 5
        
        # 1. Pago de Compensatorios Inmediatos (L-V)
        if 0 <= fecha.weekday() <= 4:
            for p in list(cola_compensados_semanal):
                if cupo_fuera > 0:
                    asig[p] = "COMPENSADO"
                    cola_compensados_semanal.remove(p)
                    cupo_fuera -= 1

        # 2. Día Sagrado (Descanso Programado)
        cands_sag = [p for p in grupo_a if dia_n == descansos_elegidos["A"]] + \
                    [p for p in grupo_b if dia_n == descansos_elegidos["B"]]
        
        for p in cands_sag:
            if p in asig: continue
            if cupo_fuera > 0:
                asig[p], desc_real_mes[p], cupo_fuera = "DESCANSO", desc_real_mes[p]+1, cupo_fuera-1
            else:
                if p not in cola_compensados_semanal:
                    cola_compensados_semanal.append(p)

        # 3. Llenado Estricto (11 T1 y 11 T2)
        dispos = [p for p in personal if p not in asig]
        np.random.seed(fecha.day)
        np.random.shuffle(dispos)
        for p in dispos:
            if list(asig.values()).count("T1") < 11: asig[p] = "T1"
            elif list(asig.values()).count("T2") < 11: asig[p] = "T2"
            else: asig[p] = "DISPONIBLE" # DISPONIBLE AHORA SUMA HORAS
            
        for p in personal:
            filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 5. MOTOR TÉCNICOS (ROTACIÓN)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas, deudas = [], {g: 0 for g in GRUPOS_TEC}
    for fecha in pd.date_range(inicio, fin):
        dia_n, sem, asig = DIAS_ES[fecha.weekday()], fecha.isocalendar()[1], {}
        gps_h = [g for g, d in descansos_ley.items() if d == dia_n]
        if len(gps_h) > 1:
            idx = sem % len(gps_h); d_r = gps_h[idx]; asig[d_r] = "DESCANSO"
            for g in gps_h: 
                if g != d_r: deudas[g] += 1
        elif len(gps_h) == 1: asig[gps_h[0]] = "DESCANSO"
        
        if 0 <= fecha.weekday() <= 4:
            g_d = sorted([g for g, d in deudas.items() if d > 0 and g not in asig], key=lambda x: deudas[x], reverse=True)
            if g_d: asig[g_d[0]], deudas[g_d[0]] = "COMPENSADO", deudas[g_d[0]]-1
        
        activos = sorted([g for g in GRUPOS_TEC if g not in asig], key=lambda x: (GRUPOS_TEC.index(x) + sem) % 4)
        for g in activos:
            for t in ["T1", "T2", "T3", "T1 APOYO"]:
                if t not in asig.values(): asig[g] = t; break
        for g in GRUPOS_TEC: filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asig.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 6. MÉTRICAS Y AUDITORÍA
# =========================================================
def ejecutar_auditoria_completa(df, tipo):
    df_aud = df.copy(); df_aud["Fecha"] = pd.to_datetime(df_aud["Fecha"])
    cob = df_aud.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "DESCANSO", "COMPENSADO", "DISPONIBLE"]:
        if c not in cob.columns: cob[c] = 0
    df_aud['Semana'] = df_aud['Fecha'].dt.isocalendar().week
    df_aud['Horas'] = df_aud['Turno'].apply(calcular_horas_turno)
    h_sem = df_aud.groupby(['Sujeto', 'Semana'])['Horas'].sum().unstack(fill_value=0)
    eq = df_aud.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
    return cob, h_sem, eq

def generar_malla_transaccional(df_final, tipo, config_horas):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    det = pd.merge(df_final, df_emp[['Nombre', 'Cargo', 'GrupoAsignado']], 
                   left_on="Sujeto", right_on="Nombre" if tipo == "Abordaje" else "GrupoAsignado", how="inner")
    det["Hora Inicio"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    det["Hora Fin"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    det["Horas Prog"] = det["Turno"].apply(calcular_horas_turno)
    det["Tipo Día"] = det["Fecha"].apply(lambda x: obtener_tipo_dia(pd.to_datetime(x)))
    return det[["Fecha", "Tipo Día", "Nombre", "Cargo", "Turno", "Hora Inicio", "Hora Fin", "Horas Prog"]]

# =========================================================
# 7. INTERFAZ DE PROGRAMADOR
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("Módulo", ["Abordaje", "Técnicos"])
    with st.expander("⏰ Horarios (Ref. 7 horas)"):
        config_h = {}
        t_l = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        def_h = {"T1": [time(6,0), time(13,0)], "T2": [time(13,0), time(20,0)], "T3": [time(22,0), time(5,0)], "RELEVO": [time(8,0), time(15,0)], "T1 APOYO": [time(7,0), time(14,0)], "DISPONIBLE": [time(8,0), time(15,0)]}
        cols = st.columns(3)
        for i, t in enumerate(t_l):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}"); fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}")
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}

    c1, c2 = st.columns(2)
    inicio, fin = c1.date_input("Inicio"), c2.date_input("Fin", date.today() + timedelta(days=28))
    
    desc_data = {}
    if tipo == "Abordaje":
        st.write("⚓ **Abordaje: Cobertura Fija 11/11 | Jornada 42h**")
        ca, cb = st.columns(2)
        desc_data = {"A": ca.selectbox("Día Sagrado A", DIAS_ES, index=6), "B": cb.selectbox("Día Sagrado B", DIAS_ES, index=5)}
    else:
        cols = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC): desc_data[g] = cols[i].selectbox(f"Descanso {g}", DIAS_ES, index=(i+6)%7)

    if st.button("🚀 GENERAR MALLA"):
        st.session_state.m_base = generar_malla_abordaje_individual(inicio, fin, desc_data) if tipo == "Abordaje" else generar_malla_tecnicos(inicio, fin, desc_data)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_base = st.session_state.m_base.copy()
        pivot = df_base.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        st.subheader("📝 Editor Maestro")
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True)
        
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        cob, h_sem, eq = ejecutar_auditoria_completa(df_final, tipo)
        
        t1, t2, t3 = st.tabs(["📊 Cobertura Diaria", "⚖️ Auditoría Horas Semanales", "📈 Equidad"])
        with t1:
            st.dataframe(cob.style.map(lambda v: 'background-color: #D5F5E3' if v==11 else ('background-color: #FADBD8' if v<11 else ''), subset=["T1", "T2"] if "T1" in cob.columns else []), use_container_width=True)
        with t2:
            st.write("Celdas en rojo superan las 42 horas permitidas (DISPONIBLE suma 7h):")
            st.dataframe(h_sem.style.highlight_between(left=42.1, right=100, color="#FADBD8"), use_container_width=True)
        with t3:
            st.dataframe(eq.style.background_gradient(cmap="Blues"), use_container_width=True)
        
        st.subheader("📋 Reporte Transaccional")
        m_trans = generar_malla_transaccional(df_final, tipo, config_h)
        st.dataframe(m_trans, use_container_width=True)
        
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer: m_trans.to_excel(writer, index=False)
        st.download_button("📥 Descargar Excel", output.getvalue(), f"Malla_{tipo}_{date.today()}.xlsx")
