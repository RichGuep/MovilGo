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
    """Aplica el formato condicional de colores a la tabla."""
    def apply_styles(val):
        key = val if val and str(val).strip() != "" else "DESCANSO"
        bg = COLORES_MAP.get(key, "#1B2631")
        txt = "white" if key in ["DESCANSO", "COMPENSADO"] else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB'
    return df_pivot.style.map(apply_styles)

# =========================================================
# 2. FUNCIONES DE APOYO Y CONECTIVIDAD
# =========================================================
def obtener_tipo_dia(fecha):
    if fecha in festivos_co: return "Festivo"
    if fecha.weekday() == 5: return "Sábado"
    if fecha.weekday() == 6: return "Domingo"
    return "Hábil"

def calcular_horas_turno(row):
    try:
        if row.get('Hora Inicio') in ["OFF", None] or row.get('Hora Fin') in ["OFF", None]: return 0
        fmt = "%H:%M"
        h_ini = datetime.strptime(row['Hora Inicio'], fmt)
        h_fin = datetime.strptime(row['Hora Fin'], fmt)
        if h_fin <= h_ini: h_fin += timedelta(days=1)
        return round((h_fin - h_ini).total_seconds() / 3600, 2)
    except: return 0

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
    st.subheader("👥 Gestión y Parametrización de Personal")
    if st.button("📥 Importar empleados.xlsx"):
        df = cargar_excel("empleados.xlsx")
        if not df.empty: 
            st.session_state.df_pers = df
            st.success("Lista base cargada desde GitHub.")
    
    if 'df_pers' in st.session_state:
        if st.button("🎲 Ejecutar Clasificación por Grupos"):
            st.session_state.df_pers_ready = asignar_grupos_automatico(st.session_state.df_pers)
            st.balloons()
        
        if 'df_pers_ready' in st.session_state:
            df_edit = st.data_editor(st.session_state.df_pers_ready, use_container_width=True)
            if st.button("💾 Guardar Estructura Final"):
                guardar_github(df_edit, "empleados_grupos.xlsx")

# =========================================================
# 4. MOTORES DE GENERACIÓN Y AUDITORÍA
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
        turnos_op = ["T3", "T2", "T1", "T1 APOYO"]
        for g in activos:
            for t in turnos_op:
                if t not in asig.values(): asig[g] = t; break
            if g not in asig: asig[g] = "T1 APOYO"
        for g in GRUPOS_TEC: filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asig.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

def generar_malla_abordaje_individual(inicio, fin, descansos_elegidos):
    df_emp = cargar_excel("empleados_grupos.xlsx")
    if df_emp.empty: return pd.DataFrame()
    
    personal = df_emp[df_emp['GrupoAsignado'] == "Abordaje"]['Nombre'].tolist()[:27]
    grupo_a = personal[:13]
    grupo_b = personal[13:]
    
    filas = []
    deudas_comp = {p: 0 for p in personal}
    
    for fecha in pd.date_range(inicio, fin):
        dia_n = DIAS_ES[fecha.weekday()]; asig = {}
        
        deben_descansar = []
        for p in grupo_a:
            if dia_n == descansos_elegidos["A"]: deben_descansar.append(p)
        for p in grupo_b:
            if dia_n == descansos_elegidos["B"]: deben_descansar.append(p)
            
        np.random.shuffle(deben_descansar)
        for i, p in enumerate(deben_descansar):
            if i < 5: 
                asig[p] = "DESCANSO"
            else: 
                deudas_comp[p] += 1 

        if 0 <= fecha.weekday() <= 4:
            p_con_deuda = [p for p in personal if deudas_comp[p] > 0 and p not in asig]
            p_con_deuda = sorted(p_con_deuda, key=lambda x: deudas_comp[x], reverse=True)
            for p in p_con_deuda:
                if (list(asig.values()).count("DESCANSO") + list(asig.values()).count("COMPENSADO")) < 5:
                    asig[p] = "COMPENSADO"
                    deudas_comp[p] -= 1

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

def ejecutar_auditoria_v2(df):
    """Nueva auditoría: Desglose por turnos diarios y equidad individual."""
    df_temp = df.copy()
    df_temp["Fecha"] = pd.to_datetime(df_temp["Fecha"])
    
    # 1. Auditoría de Cobertura Diaria (Lo que le faltaba)
    cobertura_diaria = df_temp.groupby(["Fecha", "Turno"]).size().unstack(fill_value=0)
    for col in ["T1", "T2", "DESCANSO", "COMPENSADO", "DISPONIBLE"]:
        if col not in cobertura_diaria.columns: cobertura_diaria[col] = 0
    
    # 2. Equidad individual
    equidad = df_temp.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
    
    return cobertura_diaria, equidad

def generar_malla_transaccional(df_final, tipo, config_horas):
    df_empleados = cargar_excel("empleados_grupos.xlsx")
    if df_empleados.empty: return pd.DataFrame()
    
    if tipo == "Técnicos":
        detallada = pd.merge(df_final, df_empleados[['Nombre', 'Cargo', 'GrupoAsignado']], left_on="Sujeto", right_on="GrupoAsignado", how="inner")
    else:
        detallada = pd.merge(df_final, df_empleados[['Nombre', 'Cargo']], left_on="Sujeto", right_on="Nombre", how="inner")

    detallada["Hora Inicio"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Inicio", "OFF"))
    detallada["Hora Fin"] = detallada["Turno"].apply(lambda x: config_horas.get(x, {}).get("Fin", "OFF"))
    detallada["Horas Prog."] = detallada.apply(calcular_horas_turno, axis=1)
    detallada["Tipo Día"] = detallada["Fecha"].apply(obtener_tipo_dia)
    return detallada[["Fecha", "Tipo Día", "Nombre", "Cargo", "Turno", "Hora Inicio", "Hora Fin", "Horas Prog."]]

# =========================================================
# 5. INTERFAZ DE PROGRAMACIÓN
# =========================================================
def pantalla_programador():
    tipo = st.sidebar.radio("Módulo de Trabajo", ["Técnicos", "Abordaje"])
    
    with st.expander("⏰ Configuración de Horarios"):
        config_h = {}
        t_l = ["T1", "T2", "T3", "RELEVO", "T1 APOYO", "DISPONIBLE"]
        def_h = {"T1": [time(6,0), time(14,0)], "T2": [time(14,0), time(22,0)], "T3": [time(22,0), time(6,0)], "RELEVO": [time(8,0), time(16,0)], "T1 APOYO": [time(7,0), time(15,0)], "DISPONIBLE": [time(0,0), time(0,0)]}
        cols = st.columns(3)
        for i, t in enumerate(t_l):
            with cols[i%3]:
                ini = st.time_input(f"Inicia {t}", def_h[t][0], key=f"i{t}")
                fin = st.time_input(f"Fin {t}", def_h[t][1], key=f"f{t}")
                config_h[t] = {"Inicio": ini.strftime("%H:%M"), "Fin": fin.strftime("%H:%M")}
        config_h["DESCANSO"] = config_h["COMPENSADO"] = {"Inicio": "OFF", "Fin": "OFF"}

    c1, c2 = st.columns(2)
    inicio = c1.date_input("Fecha Inicio", date.today())
    fin = c2.date_input("Fecha Fin", date.today() + timedelta(days=21))
    
    desc_data = {}
    if tipo == "Técnicos":
        st.write("⚙️ **Parametrización Técnicos**")
        cols_d = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC):
            desc_data[g] = cols_d[i].selectbox(f"Descanso {g}", DIAS_ES, index=(i+6)%7)
    else:
        st.write("⚓ **Parametrización Abordaje**")
        cola, colb = st.columns(2)
        desc_data["A"] = cola.selectbox("Descanso Grupo A (1-13)", DIAS_ES, index=5)
        desc_data["B"] = colb.selectbox("Descanso Grupo B (14-27)", DIAS_ES, index=6)

    if st.button("🚀 Generar Malla y Auditoría"):
        if tipo == "Técnicos":
            st.session_state.m_tec = generar_malla_tecnicos(inicio, fin, desc_data)
        else:
            st.session_state.m_abo = generar_malla_abordaje_individual(inicio, fin, desc_data)

    m_key = "m_tec" if tipo == "Técnicos" else "m_abo"
    if m_key in st.session_state and not st.session_state[m_key].empty:
        df_base = st.session_state[m_key].copy()
        df_base["Label"] = df_base["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        pivot = df_base.pivot(index="Sujeto", columns="Label", values="Turno").fillna("DESCANSO")
        sorted_cols = sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + "/2026", '%d/%m/%Y'))
        
        st.subheader("📝 Editor Maestro de Turnos")
        df_edit = st.data_editor(style_malla(pivot[sorted_cols]), use_container_width=True)
        
        # Procesar datos finales del editor
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        df_final["Fecha"] = df_final["Label"].apply(lambda x: datetime.strptime(x.split(" ")[1] + "/2026", '%d/%m/%Y'))
        
        # --- AUDITORÍA DE NIVEL SUPERIOR ---
        cob_diaria, equidad = ejecutar_auditoria_v2(df_final)
        
        st.subheader("📊 Auditoría de Cobertura Diaria")
        st.write("Verificación de cupos (Meta: 11 en T1, 11 en T2)")
        # Aplicamos estilo para resaltar cuando se cumple el cupo de 11
        st.dataframe(cob_diaria.style.highlight_between(left=11, right=11, subset=["T1", "T2"], color="#D5F5E3"), use_container_width=True)
        
        st.subheader("📋 Malla Transaccional Detallada")
        malla_det = generar_malla_transaccional(df_final, tipo, config_h)
        st.dataframe(malla_det, use_container_width=True)
        
        st.subheader("⚖️ Equidad y Acumulados")
        st.dataframe(equidad.style.background_gradient(cmap="Blues"), use_container_width=True)
