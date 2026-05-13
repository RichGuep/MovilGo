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
        st.toast(f"✅ {nombre_archivo} sincronizado.")
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())
        st.toast(f"🆕 {nombre_archivo} creado.")

def calcular_horas_turno(turno_val):
    # Regla de Jornada 2026: 7 horas por turno para no exceder 42h semanales
    if turno_val in ["DESCANSO", "COMPENSADO", "OFF", None, "DISPONIBLE"]: return 0.0
    return 7.0

# =========================================================
# 3. GESTIÓN DE PERSONAL
# =========================================================
def asignar_grupos_automatico(df):
    df = df.copy()
    if 'GrupoAsignado' in df.columns: df = df.drop(columns=['GrupoAsignado'])
    # Lógica de muestreo por cuotas técnicas
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
    st.subheader("👥 Gestión de Personal y Estructura Operativa")
    if st.button("📥 Importar empleados.xlsx"):
        df = cargar_excel("empleados.xlsx")
        if not df.empty: st.session_state.df_pers = df; st.success("Lista base cargada.")
    
    if 'df_pers' in st.session_state:
        if st.button("🎲 Ejecutar Clasificación Aleatoria de Grupos"):
            st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers)
        if 'df_pers_ready' in st.session_state:
            df_edit = st.data_editor(st.session_state.df_pers_ready, use_container_width=True)
            if st.button("💾 Guardar Estructura en GitHub"):
                guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTOR ABORDAJE (COBERTURA 11/11 + LEY 42H + DÍA SAGRADO)
# =========================================================
def generar_malla_abordaje_individual(inicio, fin, descansos_elegidos):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    personal = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]['Nombre'].tolist()[:27]
    grupo_a, grupo_b = personal[:13], personal[13:]
    
    filas, deudas_comp, desc_real_mes = [], {p: 0 for p in personal}, {p: 0 for p in personal}

    for fecha in pd.date_range(inicio, fin):
        dia_n, asig, cupo_fuera = DIAS_ES[fecha.weekday()], {}, 5
        
        # 1. Prioridad: Día Sagrado (Garantiza mínimo 2 descansos de ley)
        cands_sag = sorted([p for p in grupo_a if dia_n == descansos_elegidos["A"]] + 
                           [p for p in grupo_b if dia_n == descansos_elegidos["B"]], 
                           key=lambda x: desc_real_mes[x])
        for p in cands_sag:
            if cupo_fuera > 0:
                asig[p], desc_real_mes[p], cupo_fuera = "DESCANSO", desc_real_mes[p]+1, cupo_fuera-1
            else: deudas_comp[p] += 1 # Deuda por cobertura en su descanso

        # 2. Compensados (L-V) - Reparto atomizado para no romper los 11/11
        if 1 <= fecha.weekday() <= 5:
            c_comp = sorted([p for p in personal if deudas_comp[p] > 0 and p not in asig], 
                            key=lambda x: deudas_comp[x], reverse=True)
            for p in c_comp:
                if cupo_fuera > 0 and list(asig.values()).count("COMPENSADO") < 2:
                    asig[p], deudas_comp[p], cupo_fuera = "COMPENSADO", deudas_comp[p]-1, cupo_fuera-1

        # 3. Llenado Estricto de Cobertura (11 T1, 11 T2)
        dispos = [p for p in personal if p not in asig]
        np.random.seed(fecha.day)
        np.random.shuffle(dispos)
        for p in dispos:
            if list(asig.values()).count("T1") < 11: asig[p] = "T1"
            elif list(asig.values()).count("T2") < 11: asig[p] = "T2"
            else: asig[p] = "DISPONIBLE"
        for p in personal: filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 5. MOTOR TÉCNICOS (ROTACIÓN CICLICA)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas, deudas_comp = [], {g: 0 for g in GRUPOS_TEC}
    for fecha in pd.date_range(inicio, fin):
        dia_n, sem, asig = DIAS_ES[fecha.weekday()], fecha.isocalendar()[1], {}
        gps_h = [g for g, d in descansos_ley.items() if d == dia_n]
        if len(gps_h) > 1:
            idx = sem % len(gps_h); d_r = gps_h[idx]; asig[d_r] = "DESCANSO"
            for g in gps_h: 
                if g != d_r: deudas_comp[g] += 1
        elif len(gps_h) == 1: asig[gps_h[0]] = "DESCANSO"
        
        if 0 <= fecha.weekday() <= 4:
            g_deuda = sorted([g for g, d in deudas_comp.items() if d > 0 and g not in asig], key=lambda x: deudas_comp[x], reverse=True)
            if g_deuda: asig[g_deuda[0]], deudas_comp[g_deuda[0]] = "COMPENSADO", deudas_comp[g_deuda[0]]-1
        
        activos = sorted([g for g in GRUPOS_TEC if g not in asig], key=lambda x: (GRUPOS_TEC.index(x) + sem) % 4)
        turnos_base = ["T1", "T2", "T3", "T1 APOYO"]
        for g in activos:
            for t in turnos_base:
                if t not in asig.values(): asig[g] = t; break
            if g not in asig: asig[g] = "T1 APOYO"
        for g in GRUPOS_TEC: filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asig.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 6. MÉTRICAS, AUDITORÍA Y EXPORTACIÓN
# =========================================================
def auditoria_integral(df, tipo, desc_elegidos=None):
    df_aud = df.copy(); df_aud["Fecha"] = pd.to_datetime(df_aud["Fecha"])
    # 1. Cobertura Diaria
    cob = df_aud.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "DESCANSO", "COMPENSADO"]:
        if c not in cob.columns: cob[c] = 0
    # 2. Control Jornada 42h (7h x turno)
    df_aud['Semana'] = df_aud['Fecha'].dt.isocalendar().week
    df_aud['Horas'] = df_aud['Turno'].apply(calcular_horas_turno)
    h_sem = df_aud.groupby(['Sujeto', 'Semana'])['Horas'].sum().unstack(fill_value=0)
    # 3. Cumplimiento Legal Descansos
    res_legal = []
    if tipo == "Abordaje" and desc_elegidos:
        for sujeto in df_aud["Sujeto"].unique():
            data_s = df_aud[df_aud["Sujeto"] == sujeto]
            d_ley = data_s[data_s["Turno"] == "DESCANSO"].shape[0]
            d_comp = data_s[data_s["Turno"] == "COMPENSADO"].shape[0]
            res_legal.append({"Sujeto": sujeto, "Descansos Ley": d_ley, "Compensatorios": d_comp, "Total Libres": d_ley + d_comp, "Cumple Min 2 Ley": "✅" if d_ley >= 2 else "❌"})
    return cob, h_sem, pd.DataFrame(res_legal).set_index("Sujeto") if res_legal else pd.DataFrame()

def generar_malla_transaccional(df_final, tipo, config_horas):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    det = pd.merge(df_final, df_emp[['Nombre', 'Cargo', 'GrupoAsignado']], left_on="Sujeto", right_on="Nombre" if tipo == "Abordaje" else "GrupoAsignado", how="inner")
    det["Hora Inicio"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    det["Hora Fin"] = det["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    det["Horas"] = det["Turno"].apply(calcular_horas_turno)
    return det[["Fecha", "Nombre", "Cargo", "Turno", "Hora Inicio", "Hora Fin", "Horas"]]

# =========================================================
# 7. PANTALLA PRINCIPAL (FRONT-END)
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("Seleccionar Módulo", ["Abordaje", "Técnicos"])
    with st.expander("⏰ Parametrización Horaria (Ref. 7 horas)"):
        config_h = {}
        t_l = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        def_h = {"T1": [time(6,0), time(13,0)], "T2": [time(13,0), time(20,0)], "T3": [time(22,0), time(5,0)], "RELEVO": [time(8,0), time(15,0)], "T1 APOYO": [time(7,0), time(14,0)], "DISPONIBLE": [time(0,0), time(0,0)]}
        cols = st.columns(3)
        for i, t in enumerate(t_l):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}"); fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}")
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}

    inicio, fin = st.columns(2)[0].date_input("Fecha Inicio"), st.columns(2)[1].date_input("Fecha Fin", date.today() + timedelta(days=28))
    
    desc_data = {}
    if tipo == "Abordaje":
        ca, cb = st.columns(2)
        desc_data = {"A": ca.selectbox("Descanso Sagrado A", DIAS_ES, index=6), "B": cb.selectbox("Descanso Sagrado B", DIAS_ES, index=5)}
    else:
        cols_d = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC): desc_data[g] = cols_d[i].selectbox(f"Descanso {g}", DIAS_ES, index=(i+6)%7)

    if st.button("🚀 GENERAR MALLA OPERATIVA"):
        st.session_state.m_base = generar_malla_abordaje_individual(inicio, fin, desc_data) if tipo == "Abordaje" else generar_malla_tecnicos(inicio, fin, desc_data)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_base = st.session_state.m_base.copy()
        pivot = df_base.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        st.subheader("📝 Editor Maestro")
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True)
        
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        cob, h_sem, leg = auditoria_integral(df_final, tipo, desc_data)
        
        tabs = st.tabs(["📊 Cobertura Diaria", "⚖️ Control Jornada 42h", "🛡️ Auditoría Legal", "📋 Reporte Nómina"])
        
        with tabs[0]:
            st.dataframe(cob.style.map(lambda v: 'background-color: #D5F5E3' if v==11 else ('background-color: #FADBD8' if v<11 else ''), subset=["T1", "T2"] if "T1" in cob.columns else []), use_container_width=True)
        with tabs[1]:
            st.dataframe(h_sem.style.highlight_between(left=42.1, right=100, color="#FADBD8"), use_container_width=True)
        with tabs[2]:
            st.dataframe(leg, use_container_width=True)
        with tabs[3]:
            malla_trans = generar_malla_transaccional(df_final, tipo, config_h)
            st.dataframe(malla_trans, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer: malla_trans.to_excel(writer, index=False)
            st.download_button("📥 Descargar Excel para Nómina", output.getvalue(), f"Malla_{tipo}_{date.today()}.xlsx")
