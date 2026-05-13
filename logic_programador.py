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

def obtener_tipo_dia(fecha):
    if fecha in festivos_co: return "Festivo"
    return "Sábado" if fecha.weekday() == 5 else "Domingo" if fecha.weekday() == 6 else "Hábil"

def calcular_horas_turno(turno_val):
    # Regla: Turnos operativos son de 7 horas para no exceder las 42h semanales
    if turno_val in ["DESCANSO", "COMPENSADO", "OFF", None, "DISPONIBLE"]: 
        return 0.0
    return 7.0

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
        if not df.empty: 
            st.session_state.df_pers = df
            st.success("Lista cargada.")
    if 'df_pers' in st.session_state:
        if st.button("🎲 Clasificar Grupos (Técnicos / Abordaje)"):
            st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers)
        if 'df_pers_ready' in st.session_state:
            df_edit = st.data_editor(st.session_state.df_pers_ready, use_container_width=True)
            if st.button("💾 Guardar Estructura en GitHub"):
                guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTOR ABORDAJE (7H/DÍA - 42H SEMANALES - REPARTO ATÓMICO)
# =========================================================
def generar_malla_abordaje_individual(inicio, fin, descansos_elegidos):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    personal = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]['Nombre'].tolist()[:27]
    grupo_a = personal[:13]; grupo_b = personal[13:]
    filas = []
    deudas_comp = {p: 0 for p in personal}
    descansos_realizados_mes = {p: 0 for p in personal}

    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; asig = {}; cupo_fuera = 5
        
        # 1. Día Sagrado (Prioridad de Descanso)
        candidatos_sagrados = [p for p in grupo_a if dia_n == descansos_elegidos["A"]] + \
                              [p for p in grupo_b if dia_n == descansos_elegidos["B"]]
        candidatos_sagrados = sorted(candidatos_sagrados, key=lambda x: descansos_realizados_mes[x])
        
        for p in candidatos_sagrados:
            if cupo_fuera > 0:
                asig[p] = "DESCANSO"; descansos_realizados_mes[p] += 1; cupo_fuera -= 1
            else:
                deudas_comp[p] += 1 # Gana compensado para cumplir las 42h después

        # 2. Pago de Compensados (L-V) - Reparto Atomizado para Cobertura
        if 1 <= fecha.weekday() <= 5: # Lunes a Viernes
            c_comp = sorted([p for p in personal if deudas_comp[p] > 0 and p not in asig], 
                            key=lambda x: deudas_comp[x], reverse=True)
            for p in c_comp:
                if cupo_fuera > 0 and list(asig.values()).count("COMPENSADO") < 2:
                    asig[p] = "COMPENSADO"; deudas_comp[p] -= 1; cupo_fuera -= 1

        # 3. Cobertura Blindada (11 T1, 11 T2)
        disponibles = [p for p in personal if p not in asig]
        np.random.seed(fecha.day)
        np.random.shuffle(disponibles)
        for p in disponibles:
            if list(asig.values()).count("T1") < 11: asig[p] = "T1"
            elif list(asig.values()).count("T2") < 11: asig[p] = "T2"
            else: asig[p] = "DISPONIBLE"
        for p in personal:
            filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 5. MOTOR TÉCNICOS (ROTACIÓN CICLICA)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_comp = {g: 0 for g in GRUPOS_TEC}
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; sem = fecha.isocalendar()[1]; asig = {}
        gps_h = [g for g, d in descansos_ley.items() if d == dia_n]
        if len(gps_h) > 1:
            idx = sem % len(gps_h); d_r = gps_h[idx]; asig[d_r] = "DESCANSO"
            for g in gps_h: 
                if g != d_r: deudas_comp[g] += 1
        elif len(gps_h) == 1: asig[gps_h[0]] = "DESCANSO"
        if 0 <= fecha.weekday() <= 4:
            gps_con_deuda = [g for g, d in deudas_comp.items() if d > 0 and g not in asig]
            if gps_con_deuda:
                g_c = sorted(gps_con_deuda, key=lambda x: deudas_comp[x], reverse=True)[0]
                asig[g_c] = "COMPENSADO"; deudas_comp[g_c] -= 1
        activos = [g for g in GRUPOS_TEC if g not in asig]
        turnos_base = ["T1", "T2", "T3", "T1 APOYO"]
        desplazamiento = sem % 4 
        act_ordenados = sorted(activos, key=lambda x: (GRUPOS_TEC.index(x) + desplazamiento) % 4)
        for g in act_ordenados:
            for t in turnos_base:
                if t not in asig.values(): asig[g] = t; break
            if g not in asig: asig[g] = "T1 APOYO"
        for g in GRUPOS_TEC: filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asig.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# 6. AUDITORÍA, HORAS Y EXPORTACIÓN
# =========================================================
def auditoria_completa(df, tipo):
    df_temp = df.copy(); df_temp["Fecha"] = pd.to_datetime(df_temp["Fecha"])
    # Cobertura
    cob = df_temp.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for c in ["T1", "T2", "T3", "DESCANSO", "COMPENSADO"]:
        if c not in cob.columns: cob[c] = 0
    # Horas Semanales (Regla 42h)
    df_temp['Semana'] = df_temp['Fecha'].dt.isocalendar().week
    df_temp['Horas'] = df_temp['Turno'].apply(calcular_horas_turno)
    horas_sem = df_temp.groupby(['Sujeto', 'Semana'])['Horas'].sum().unstack(fill_value=0)
    # Equidad Total
    equidad = df_temp.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
    return cob, horas_sem, equidad

def generar_malla_transaccional(df_final, tipo, config_horas):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    detallada = pd.merge(df_final, df_emp[['Nombre', 'Cargo', 'GrupoAsignado']], 
                         left_on="Sujeto", right_on="Nombre" if tipo == "Abordaje" else "GrupoAsignado", how="inner")
    detallada["Hora Inicio"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    detallada["Hora Fin"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    detallada["Horas"] = detallada["Turno"].apply(calcular_horas_turno)
    detallada["Tipo Día"] = detallada["Fecha"].apply(lambda x: obtener_tipo_dia(pd.to_datetime(x)))
    return detallada[["Fecha", "Tipo Día", "Nombre", "Cargo", "Turno", "Hora Inicio", "Hora Fin", "Horas"]]

# =========================================================
# 7. PANTALLA PRINCIPAL
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("Módulo Selección", ["Abordaje", "Técnicos"])
    with st.expander("⏰ Parametrizar Horarios (Ref. 7 horas)"):
        config_h = {}
        t_l = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        def_h = {"T1": [time(6,0), time(13,0)], "T2": [time(13,0), time(20,0)], "T3": [time(22,0), time(5,0)], "RELEVO": [time(8,0), time(15,0)], "T1 APOYO": [time(7,0), time(14,0)], "DISPONIBLE": [time(0,0), time(0,0)]}
        cols = st.columns(3)
        for i, t in enumerate(t_l):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}"); fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}")
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}

    c1, c2 = st.columns(2)
    inicio, fin = c1.date_input("Inicio", date.today()), c2.date_input("Fin", date.today() + timedelta(days=28))
    
    desc_data = {}
    if tipo == "Abordaje":
        ca, cb = st.columns(2)
        desc_data = {"A": ca.selectbox("Descanso Sagrado Grupo A", DIAS_ES, index=6), "B": cb.selectbox("Descanso Sagrado Grupo B", DIAS_ES, index=5)}
    else:
        cols_d = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC): desc_data[g] = cols_d[i].selectbox(f"Descanso {g}", DIAS_ES, index=(i+6)%7)

    if st.button("🚀 GENERAR MALLA COMPLETA"):
        if tipo == "Abordaje": st.session_state.m_base = generar_malla_abordaje_individual(inicio, fin, desc_data)
        else: st.session_state.m_base = generar_malla_tecnicos(inicio, fin, desc_data)

    if 'm_base' in st.session_state and not st.session_state.m_base.empty:
        df_base = st.session_state.m_base.copy()
        pivot = df_base.pivot(index="Sujeto", columns="Fecha", values="Turno").fillna("DESCANSO")
        
        st.subheader("📝 Editor Maestro")
        df_edit = st.data_editor(style_malla(pivot), use_container_width=True)
        
        # Procesamiento de Auditorías
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
        cob, h_sem, eq = auditoria_completa(df_final, tipo)
        
        col_aud1, col_aud2 = st.tabs(["📊 Cobertura Diaria", "⚖️ Horas y Equidad"])
        
        with col_aud1:
            st.dataframe(cob.style.map(lambda v: 'background-color: #D5F5E3' if v==11 else ('background-color: #FADBD8' if v<11 else ''), subset=["T1", "T2"] if "T1" in cob.columns else []), use_container_width=True)
        
        with col_aud2:
            st.write("🔥 **Control Jornada 42h (Alerta > 42)**")
            st.dataframe(h_sem.style.highlight_between(left=42.1, right=100, color="#FADBD8"), use_container_width=True)
            st.write("📈 **Acumulados por Persona**")
            st.dataframe(eq.style.background_gradient(cmap="Blues"), use_container_width=True)
        
        st.subheader("📋 Reporte Transaccional (Listo para Nómina)")
        malla_trans = generar_malla_transaccional(df_final, tipo, config_h)
        st.dataframe(malla_trans, use_container_width=True)
        
        # Botón de Descarga
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            malla_trans.to_excel(writer, index=False, sheet_name='Malla')
        st.download_button(label="📥 Descargar Malla en Excel", data=output.getvalue(), file_name=f"malla_{tipo}_{date.today()}.xlsx")
